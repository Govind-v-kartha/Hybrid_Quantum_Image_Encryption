"""
Fusion Engine - Combines Encrypted ROI Blocks and Background.

Handles the fusion of quantum-encrypted ROI blocks and classically-encrypted
background into a single encrypted image, and the reverse unfusion for decryption.
"""

import numpy as np
from typing import List, Tuple

from utils.logger import setup_logger, get_config_path
from utils.block_utils import BLOCK_SIZE

logger = setup_logger("FUSION_ENGINE", get_config_path())


def fuse_encrypted_image(
    encrypted_blocks: List[np.ndarray],
    block_map: List[dict],
    encrypted_background_image: np.ndarray,
    original_shape: tuple,
) -> np.ndarray:
    """
    Combine encrypted ROI blocks and encrypted background into a single image.

    Places encrypted 32x32 blocks at their original positions (from block_map)
    and fills remaining pixels with encrypted background data.

    Args:
        encrypted_blocks: List of encrypted 32x32 blocks (grayscale, uint8).
        block_map: Block metadata with positions.
        encrypted_background_image: Encrypted background image (H, W, 3).
        original_shape: Original image shape (H, W, 3).

    Returns:
        Fused encrypted image (H, W, 3), dtype uint8.
    """
    logger.info("=" * 60)
    logger.info("STARTING FUSION OF ENCRYPTED COMPONENTS")
    logger.info("=" * 60)

    H, W, _ = original_shape

    # Start with the encrypted background
    fused_image = encrypted_background_image.copy()

    # Place encrypted ROI blocks
    for enc_block, bmap in zip(encrypted_blocks, block_map):
        x, y = int(bmap["position"][0]), int(bmap["position"][1])  # Global position (x = col, y = row)

        # Encrypted blocks are grayscale; replicate to 3 channels for the fused image
        if enc_block.ndim == 2:
            block_3ch = np.stack([enc_block] * 3, axis=-1)
        else:
            block_3ch = enc_block

        # Place at position (clip to image bounds)
        y_end = min(y + BLOCK_SIZE, H)
        x_end = min(x + BLOCK_SIZE, W)
        block_h = y_end - y
        block_w = x_end - x

        fused_image[y : y_end, x : x_end] = block_3ch[:block_h, :block_w]

    # Verify complete coverage
    logger.info(
        f"Fusing {len(encrypted_blocks)} quantum blocks + classical background"
    )
    logger.info(f"Fused image shape: {fused_image.shape}")
    logger.info(f"Fused image dtype: {fused_image.dtype}")

    # Check dimensions match
    assert fused_image.shape == original_shape, (
        f"Fused image shape {fused_image.shape} != original {original_shape}"
    )

    logger.info("Fusion complete: encrypted image created")
    logger.info("=" * 60)

    return fused_image


def unfuse_encrypted_image(
    fused_image: np.ndarray,
    block_map: List[dict],
) -> Tuple[List[np.ndarray], np.ndarray]:
    """
    Separate a fused encrypted image back into ROI blocks and background.

    Args:
        fused_image: Fused encrypted image (H, W, 3).
        block_map: Block metadata with positions.

    Returns:
        Tuple of:
            - encrypted_blocks: List of 32x32 encrypted blocks (grayscale).
            - encrypted_background: Background image (H, W, 3).
    """
    logger.info("Unfusing encrypted image into components...")

    # Extract encrypted ROI blocks
    encrypted_blocks = []
    for bmap in block_map:
        x, y = int(bmap["position"][0]), int(bmap["position"][1])

        block = fused_image[y : y + BLOCK_SIZE, x : x + BLOCK_SIZE].copy()

        # Pad back to full BLOCK_SIZE if at image edge
        if block.shape[0] != BLOCK_SIZE or block.shape[1] != BLOCK_SIZE:
            if block.ndim == 3:
                padded = np.zeros((BLOCK_SIZE, BLOCK_SIZE, block.shape[2]), dtype=block.dtype)
            else:
                padded = np.zeros((BLOCK_SIZE, BLOCK_SIZE), dtype=block.dtype)
            padded[: block.shape[0], : block.shape[1]] = block
            block = padded

        encrypted_blocks.append(block)

    # Extract background (everything not covered by ROI blocks)
    encrypted_background = fused_image.copy()

    logger.info(
        f"Unfused: {len(encrypted_blocks)} blocks extracted, background preserved"
    )

    return encrypted_blocks, encrypted_background
