"""
Decryption Workflow - End-to-End Decryption Pipeline.

Orchestrates the complete decryption pipeline to perfectly reconstruct
the original image from encrypted data:
1. Load encrypted data and metadata
2. Unfuse encrypted image into components
3. Classical decryption of background (AES-256-GCM)
4. Quantum decryption of ROI blocks (reverse NEQR)
5. Reconstruct full image from decrypted components
6. Verify zero data loss
"""

import os
import json
import time
import numpy as np
from datetime import datetime

from utils.logger import setup_logger, get_config_path, load_config
from utils.image_utils import load_image, save_image
from utils.crypto_utils import load_key_material, derive_quantum_seeds, decode_bytes_b64
from utils.block_utils import reconstruct_from_blocks, place_roi_on_image
from engines.classical_engine import decrypt_background
from engines.quantum_engine import decrypt_all_blocks
from engines.fusion_engine import unfuse_encrypted_image
from engines.verification_engine import verify_zero_data_loss, generate_verification_report

logger = setup_logger("DECRYPT_WORKFLOW", get_config_path())


def run_decryption(
    metadata_path: str,
    output_dir: str = None,
    original_image_path: str = None,
    config: dict = None,
) -> dict:
    """
    Run the complete decryption pipeline.

    Args:
        metadata_path: Path to encryption metadata JSON file.
        output_dir: Output directory for decrypted files.
        original_image_path: Optional path to original image for verification.
        config: Configuration dict.

    Returns:
        Dictionary with decryption results and verification report.
    """
    total_start = time.time()

    if config is None:
        config = load_config()

    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    if output_dir is None:
        output_dir = os.path.join(project_root, config["paths"]["output_dir"])

    decrypted_dir = os.path.join(output_dir, "decrypted")
    os.makedirs(decrypted_dir, exist_ok=True)

    logger.info("=" * 70)
    logger.info("HYBRID AI-QUANTUM SATELLITE IMAGE ENCRYPTION SYSTEM")
    logger.info("DECRYPTION PIPELINE STARTED")
    logger.info("=" * 70)
    logger.info(f"Metadata: {metadata_path}")
    logger.info(f"Timestamp: {datetime.now().isoformat()}")

    # ─────────────────────────────────────────────────────────────────
    # STEP 1: Load Metadata and Encrypted Data
    # ─────────────────────────────────────────────────────────────────
    logger.info("\n>>> STEP 1: Loading encrypted data and metadata...")

    if not os.path.exists(metadata_path):
        raise FileNotFoundError(f"Metadata file not found: {metadata_path}")

    with open(metadata_path, "r") as f:
        metadata = json.load(f)

    enc_meta = metadata["encryption_metadata"]
    original_info = enc_meta["original_image"]
    original_shape = tuple([original_info["size"][1], original_info["size"][0], original_info["channels"]])
    # shape is (H, W, C) but size was stored as [W, H]

    block_map = enc_meta["block_map"]
    roi_bbox = np.array(enc_meta["roi_information"]["roi_bbox"])
    all_encryption_info = enc_meta["block_encryption_info"]

    # Load keys
    key_path = enc_meta["output_files"]["keys"]
    master_seed, aes_key, salt = load_key_material(key_path)

    # Load classical encryption info
    classical_info = enc_meta["classical_encryption"]
    nonce = decode_bytes_b64(classical_info["nonce"])
    tag = decode_bytes_b64(classical_info["tag"])
    bg_image_shape = tuple(classical_info["image_shape"])

    # ════════════════════════════════════════════════════════════════════
    # HYBRID PHASE 4: Load ROI mask from metadata (no .npy files)
    # ════════════════════════════════════════════════════════════════════
    from utils.crypto_utils import decode_ndarray_b64

    roi_mask_b64 = enc_meta["roi_information"].get("roi_mask_b64")
    if roi_mask_b64:
        roi_mask_shape = tuple(enc_meta["roi_information"]["roi_mask_shape"])
        roi_mask_dtype = enc_meta["roi_information"]["roi_mask_dtype"]
        roi_mask = decode_ndarray_b64(roi_mask_b64, roi_mask_shape, roi_mask_dtype)
        logger.info(f"Loaded ROI mask from metadata: {roi_mask_shape}")
    else:
        # Fallback for old format (backward compat)
        roi_mask_path = enc_meta["roi_information"].get("roi_mask_path")
        if roi_mask_path and os.path.exists(roi_mask_path):
            roi_mask = np.load(roi_mask_path)
            logger.info(f"Loaded ROI mask from {roi_mask_path} (old .npy format)")
        else:
            raise ValueError("ROI mask not found in metadata or file")

    # Load encrypted background
    bg_cipher_path = enc_meta["output_files"]["encrypted_background"]
    with open(bg_cipher_path, "rb") as f:
        ciphertext = f.read()

    # Load encrypted image
    encrypted_image_path = enc_meta["output_files"]["encrypted_image"]
    encrypted_image = load_image(encrypted_image_path)

    logger.info(f"Metadata loaded: {len(block_map)} blocks, {len(all_encryption_info)} encryption records")
    logger.info(f"Original image shape: {original_shape}")

    # ─────────────────────────────────────────────────────────────────
    # STEP 2: Load Encrypted Blocks from Metadata (Pure Image-Only)
    # ─────────────────────────────────────────────────────────────────
    logger.info("\n>>> STEP 2: Loading encrypted blocks from metadata...")

    # Load encrypted blocks from metadata (PRIMARY SOURCE - no .npy fallback)
    blocks_b64 = enc_meta["output_files"].get("encrypted_blocks_b64")
    if blocks_b64:
        blocks_shapes = enc_meta["output_files"]["encrypted_blocks_shapes"]
        blocks_dtype = enc_meta["output_files"]["encrypted_blocks_dtype"]
        
        encrypted_blocks = []
        for b64_str, shape in zip(blocks_b64, blocks_shapes):
            block = decode_ndarray_b64(b64_str, tuple(shape), blocks_dtype)
            encrypted_blocks.append(block)
        
        logger.info(
            f"Loaded {len(encrypted_blocks)} encrypted blocks from metadata "
            f"(aligned bbox: all {encrypted_blocks[0].shape[0]}×{encrypted_blocks[0].shape[1]}, no padding, image-only)"
        )
    else:
        # Fallback for old format (backward compat with .npy)
        enc_blocks_path = enc_meta["output_files"].get("encrypted_blocks")
        if enc_blocks_path and os.path.exists(enc_blocks_path):
            enc_blocks_array = np.load(enc_blocks_path)
            encrypted_blocks = [enc_blocks_array[i] for i in range(enc_blocks_array.shape[0])]
            logger.info(f"Loaded blocks from {enc_blocks_path} (old .npy format)")
        else:
            raise RuntimeError(
                "Encrypted blocks not found in metadata or .npy file. "
                "Cannot proceed with image-only decryption."
            )
    
    logger.info(f"Separated {len(encrypted_blocks)} encrypted blocks")

    # ─────────────────────────────────────────────────────────────────
    # STEP 3: Classical Decryption of Background
    # ─────────────────────────────────────────────────────────────────
    logger.info("\n>>> STEP 3: Classical decryption of background (AES-256-GCM)...")
    decrypted_background = decrypt_background(
        ciphertext, tag, aes_key, nonce, bg_image_shape
    )
    logger.info(f"Background decrypted: {decrypted_background.shape}")

    # ─────────────────────────────────────────────────────────────────
    # STEP 4: Quantum Decryption of ROI Blocks
    # ─────────────────────────────────────────────────────────────────
    logger.info("\n>>> STEP 4: Quantum decryption of ROI blocks...")
    quantum_seeds = derive_quantum_seeds(master_seed, len(block_map))

    decrypted_blocks = decrypt_all_blocks(
        encrypted_blocks, quantum_seeds, all_encryption_info, config
    )
    logger.info(f"Quantum decryption complete: {len(decrypted_blocks)} blocks")

    # ─────────────────────────────────────────────────────────────────
    # STEP 5: Reconstruct Full Image
    # ─────────────────────────────────────────────────────────────────
    logger.info("\n>>> STEP 5: Reconstructing full image...")

    # Start with decrypted background (full image with ROI pixels zeroed)
    reconstructed_image = decrypted_background.copy()

    # Use quantum-decrypted blocks directly (no bypass)
    reconstruction_blocks = decrypted_blocks

    # Reconstruct ROI from blocks
    roi_region = reconstruct_from_blocks(
        reconstruction_blocks, block_map, roi_bbox, original_shape
    )

    # Place ROI onto image — ONLY at ROI mask pixels, not the entire bbox.
    # The bbox may contain background pixels that were already correctly
    # decrypted in the background image; overwriting the full bbox would
    # destroy those pixels with zeros from the roi_region canvas.
    y_min, x_min, y_max, x_max = int(roi_bbox[0]), int(roi_bbox[1]), int(roi_bbox[2]), int(roi_bbox[3])

    if roi_region.ndim == 2:
        roi_region_3ch = np.stack([roi_region] * 3, axis=-1)
    else:
        roi_region_3ch = roi_region

    # Extract the ROI mask patch for the bounding box area
    roi_mask_patch = roi_mask[y_min:y_max, x_min:x_max]

    # Only overwrite pixels that are actually ROI
    roi_pixels = roi_mask_patch > 0
    if roi_pixels.ndim == 2 and roi_region_3ch.ndim == 3:
        roi_pixels_3d = np.stack([roi_pixels] * roi_region_3ch.shape[2], axis=-1)
    else:
        roi_pixels_3d = roi_pixels

    reconstructed_image[y_min:y_max, x_min:x_max][roi_pixels_3d] = roi_region_3ch[roi_pixels_3d]

    logger.info(f"Image reconstructed: {reconstructed_image.shape}")

    # Save masked reconstructed ROI (zero out non-ROI pixels for clean comparison)
    reconstructed_roi_masked = roi_region_3ch.copy()
    roi_mask_3d = np.stack([roi_mask_patch] * reconstructed_roi_masked.shape[2], axis=-1) if reconstructed_roi_masked.ndim == 3 else roi_mask_patch
    reconstructed_roi_masked[roi_mask_3d == 0] = 0
    roi_masked_path = os.path.join(decrypted_dir, "reconstructed_roi_masked.png")
    save_image(reconstructed_roi_masked, roi_masked_path)
    logger.info(f"Reconstructed ROI (masked) saved: {roi_masked_path}")

    # Save decrypted background
    bg_path = os.path.join(decrypted_dir, "decrypted_background.png")
    save_image(decrypted_background, bg_path)
    logger.info(f"Decrypted background saved: {bg_path}")

    # Save ROI mask as image
    roi_mask_path_out = os.path.join(decrypted_dir, "roi_mask.png")
    save_image((roi_mask * 255).astype(np.uint8), roi_mask_path_out)
    logger.info(f"ROI mask saved: {roi_mask_path_out}")

    # Force PNG output for lossless file storage (JPEG would introduce artifacts)
    original_filename = original_info.get("filename", "decrypted.png")
    basename_no_ext = os.path.splitext(original_filename)[0]
    decrypted_path = os.path.join(decrypted_dir, f"decrypted_{basename_no_ext}.png")
    save_image(reconstructed_image, decrypted_path)
    logger.info(f"Decrypted image saved (PNG, lossless): {decrypted_path}")

    # ─────────────────────────────────────────────────────────────────
    # STEP 6: Verification (if original available)
    # ─────────────────────────────────────────────────────────────────
    verification_report = None
    if original_image_path and os.path.exists(original_image_path):
        logger.info("\n>>> STEP 6: Verifying zero data loss...")
        original_image = load_image(original_image_path)
        verification_report = verify_zero_data_loss(original_image, reconstructed_image)

        # Save verification report
        report_path = os.path.join(
            decrypted_dir, f"verification_report_{original_filename.split('.')[0]}.txt"
        )
        generate_verification_report(verification_report, report_path)
    else:
        logger.info("\n>>> STEP 6: Skipped verification (original image not provided)")

    # ─────────────────────────────────────────────────────────────────
    # COMPLETE
    # ─────────────────────────────────────────────────────────────────
    total_time = time.time() - total_start

    logger.info("\n" + "=" * 70)
    logger.info("DECRYPTION PIPELINE COMPLETE")
    logger.info("=" * 70)
    logger.info(f"Total time: {total_time:.2f}s ({total_time / 60:.1f} minutes)")
    logger.info(f"Decrypted image: {decrypted_path}")
    if verification_report:
        logger.info(f"Verification: {verification_report['status']}")
    logger.info("=" * 70)

    return {
        "decrypted_image_path": decrypted_path,
        "reconstructed_image": reconstructed_image,
        "verification_report": verification_report,
        "total_time_seconds": total_time,
    }
