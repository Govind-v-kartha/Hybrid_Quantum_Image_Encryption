"""
Image utilities for the Hybrid AI-Quantum Satellite Image Encryption System.
Handles image loading, validation, saving, and format conversions.
"""

import os
import hashlib
import numpy as np
from PIL import Image

from utils.logger import setup_logger, get_config_path

logger = setup_logger("IMAGE_UTILS", get_config_path())

SUPPORTED_FORMATS = {"png", "jpg", "jpeg", "tiff", "tif"}


def validate_image(image_path: str) -> bool:
    """
    Validate that the image file exists, is a supported format, and can be opened.

    Args:
        image_path: Path to the image file.

    Returns:
        True if valid, raises exception otherwise.
    """
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Image file not found: {image_path}")

    ext = os.path.splitext(image_path)[1].lower().lstrip(".")
    if ext not in SUPPORTED_FORMATS:
        raise ValueError(
            f"Unsupported image format: .{ext}. Supported: {SUPPORTED_FORMATS}"
        )

    try:
        with Image.open(image_path) as img:
            img.verify()
        logger.info(f"Image validated successfully: {image_path}")
        return True
    except Exception as e:
        raise ValueError(f"Image file is corrupted or invalid: {image_path}. Error: {e}")


def load_image(image_path: str) -> np.ndarray:
    """
    Load an image as a NumPy RGB array (H, W, 3).

    Args:
        image_path: Path to the image file.

    Returns:
        NumPy array of shape (H, W, 3) with dtype uint8.
    """
    validate_image(image_path)
    img = Image.open(image_path).convert("RGB")
    img_array = np.array(img, dtype=np.uint8)
    logger.info(
        f"Image loaded: {image_path}, shape={img_array.shape}, dtype={img_array.dtype}"
    )
    return img_array


def save_image(image_array: np.ndarray, output_path: str) -> str:
    """
    Save a NumPy array as an image file.

    Args:
        image_array: NumPy array of shape (H, W, 3) or (H, W), dtype uint8.
        output_path: Path where the image will be saved.

    Returns:
        The output path.
    """
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    img = Image.fromarray(image_array.astype(np.uint8))
    img.save(output_path)
    logger.info(f"Image saved: {output_path}")
    return output_path


def compute_image_hash(image_array: np.ndarray) -> str:
    """
    Compute SHA-256 hash of an image array for integrity verification.

    Args:
        image_array: NumPy array of the image.

    Returns:
        SHA-256 hex digest string.
    """
    return hashlib.sha256(image_array.tobytes()).hexdigest()


def rgb_to_grayscale(image_array: np.ndarray) -> np.ndarray:
    """
    Convert an RGB image to grayscale using luminance weights.

    Args:
        image_array: NumPy array of shape (H, W, 3).

    Returns:
        NumPy array of shape (H, W) with dtype uint8.
    """
    if image_array.ndim == 2:
        return image_array
    weights = np.array([0.2989, 0.5870, 0.1140])
    gray = np.dot(image_array[..., :3], weights)
    return gray.astype(np.uint8)


def get_image_info(image_array: np.ndarray, filename: str = "") -> dict:
    """
    Get metadata information about an image.

    Args:
        image_array: NumPy array of the image.
        filename: Original filename.

    Returns:
        Dictionary with image metadata.
    """
    h, w = image_array.shape[:2]
    channels = image_array.shape[2] if image_array.ndim == 3 else 1
    return {
        "filename": filename,
        "size": [w, h],
        "channels": channels,
        "dtype": str(image_array.dtype),
        "hash": compute_image_hash(image_array),
    }


def list_input_images(input_dir: str) -> list:
    """
    List all supported image files in the input directory.

    Args:
        input_dir: Path to the input directory.

    Returns:
        List of full paths to image files.
    """
    if not os.path.exists(input_dir):
        logger.warning(f"Input directory does not exist: {input_dir}")
        return []

    images = []
    for fname in sorted(os.listdir(input_dir)):
        ext = os.path.splitext(fname)[1].lower().lstrip(".")
        if ext in SUPPORTED_FORMATS:
            images.append(os.path.join(input_dir, fname))

    logger.info(f"Found {len(images)} image(s) in {input_dir}")
    return images


# ═════════════════════════════════════════════════════════════════════════════
# PNG Metadata Embedding - Dependency Warning & Bundle ID
# ═════════════════════════════════════════════════════════════════════════════


def embed_png_metadata(image_path: str, metadata_dict: dict) -> None:
    """
    Embed custom tEXt chunks into a PNG file to store dependency information.
    
    This prevents silent data loss by explicitly marking that the PNG requires
    accompanying files (specifically st2_background.enc) for full decryption.
    
    Args:
        image_path: Path to the PNG file
        metadata_dict: Dictionary with keys like:
            - "DependencyWarning": "This image requires st2_background.enc"
            - "BundleID": SHA256 hash of metadata.json
            - "ImageType": "Encrypted"
            - "EncryptionMethod": "Hybrid Quantum-Classical"
            - "RequiredFiles": "st2_background.enc, st2_metadata.json, st2_bundle.sig"
    
    Raises:
        FileNotFoundError: If image file not found
        ValueError: If not a PNG file
    """
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"PNG file not found: {image_path}")
    
    if not image_path.lower().endswith('.png'):
        raise ValueError(f"File must be PNG format: {image_path}")
    
    logger.info(f"🏷️  Embedding PNG metadata: {image_path}")
    
    try:
        # Open PNG with PIL to access metadata
        with Image.open(image_path) as img:
            # Create PIL metadata for tEXt chunks
            pil_metadata = img.info.copy() if hasattr(img, 'info') else {}
            
            # Add custom tEXt chunks (prefixed with special marker)
            for key, value in metadata_dict.items():
                if isinstance(value, bytes):
                    value = value.decode('utf-8')
                pil_metadata[key] = str(value)
            
            # Save PNG with embedded metadata
            # PNG metadata is automatically saved with tEXt chunks
            img.save(image_path, 'PNG', pnginfo=Image.PngImagePlugin.PngInfo())
            
            # Re-open and add metadata manually using PIL's lower-level API
            # because PIL doesn't always preserve metadata on save
            from PIL.PngImagePlugin import PngImageFile, PngInfo
            
            img = Image.open(image_path)
            pnginfo = PngInfo()
            
            # Add tEXt chunks
            for key, value in metadata_dict.items():
                if isinstance(value, bytes):
                    value = value.decode('utf-8')
                # PNG tEXt chunk format: keyword + null terminator + text
                pnginfo.add_text(str(key), str(value))
            
            img.save(image_path, 'PNG', pnginfo=pnginfo)
            logger.info(f"✅ PNG metadata embedded: {len(metadata_dict)} chunks added")
    
    except Exception as e:
        logger.error(f"❌ Failed to embed PNG metadata: {e}")
        raise RuntimeError(f"PNG metadata embedding failed: {e}")


def read_png_metadata(image_path: str) -> dict:
    """
    Read custom tEXt chunks from a PNG file.
    
    Extracts dependency information embedded by embed_png_metadata().
    
    Args:
        image_path: Path to the PNG file
    
    Returns:
        Dictionary with embedded metadata (tEXt chunks)
        Empty dict if no metadata found
    
    Raises:
        FileNotFoundError: If image file not found
        ValueError: If not a PNG file
    """
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"PNG file not found: {image_path}")
    
    if not image_path.lower().endswith('.png'):
        raise ValueError(f"File must be PNG format: {image_path}")
    
    try:
        with Image.open(image_path) as img:
            # PIL stores PNG tEXt chunks in img.info dictionary
            metadata = {}
            
            if hasattr(img, 'info') and img.info:
                # Extract all tEXt chunk data
                for key, value in img.info.items():
                    # PNG tEXt chunks that aren't standard PIL keys
                    if key not in ['DPI', 'gamma', 'duration', 'loop', 'default_image']:
                        metadata[key] = value
            
            logger.info(f"📖 PNG metadata read: {len(metadata)} chunks found")
            return metadata
    
    except Exception as e:
        logger.error(f"❌ Failed to read PNG metadata: {e}")
        raise RuntimeError(f"PNG metadata reading failed: {e}")


def verify_png_dependencies(image_path: str, metadata_path: str = None) -> dict:
    """
    Verify that PNG has dependency metadata and optionally verify bundle ID.
    
    Args:
        image_path: Path to the encrypted PNG file
        metadata_path: Optional path to metadata.json for bundle ID verification
    
    Returns:
        Dictionary with verification results:
            - "has_metadata": bool
            - "has_dependency_warning": bool
            - "has_bundle_id": bool
            - "bundle_id_matches": bool (if metadata_path provided)
            - "required_files": list of required files
    
    Raises:
        FileNotFoundError: If image not found
    """
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"PNG file not found: {image_path}")
    
    logger.info(f"🔍 Verifying PNG dependencies: {image_path}")
    
    verification = {
        "has_metadata": False,
        "has_dependency_warning": False,
        "has_bundle_id": False,
        "bundle_id_matches": False,
        "required_files": []
    }
    
    try:
        # Read embedded metadata
        metadata = read_png_metadata(image_path)
        
        if metadata:
            verification["has_metadata"] = True
            
            # Check for dependency warning
            if "DependencyWarning" in metadata:
                verification["has_dependency_warning"] = True
                logger.info(f"⚠️  Dependency warning found: {metadata['DependencyWarning']}")
            
            # Check for bundle ID
            if "BundleID" in metadata:
                verification["has_bundle_id"] = True
                embedded_bundle_id = metadata["BundleID"]
                logger.info(f"Bundle ID: {embedded_bundle_id}")
                
                # Verify bundle ID if metadata path provided
                if metadata_path and os.path.exists(metadata_path):
                    with open(metadata_path, "rb") as f:
                        metadata_bytes = f.read()
                    expected_bundle_id = hashlib.sha256(metadata_bytes).hexdigest()[:16]
                    
                    if embedded_bundle_id.startswith(expected_bundle_id):
                        verification["bundle_id_matches"] = True
                        logger.info("✅ Bundle ID verified")
                    else:
                        logger.warning(f"❌ Bundle ID mismatch: embedded={embedded_bundle_id}, expected={expected_bundle_id}")
            
            # Extract required files
            if "RequiredFiles" in metadata:
                required_str = metadata["RequiredFiles"]
                verification["required_files"] = [f.strip() for f in required_str.split(",")]
                logger.info(f"Required files: {verification['required_files']}")
        else:
            logger.warning("⚠️  No embedded metadata found in PNG")
    
    except Exception as e:
        logger.warning(f"⚠️  Failed to verify PNG dependencies: {e}")
    
    return verification
