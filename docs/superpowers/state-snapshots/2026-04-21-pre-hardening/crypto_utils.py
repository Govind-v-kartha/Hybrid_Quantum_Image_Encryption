"""
Cryptographic utilities for key generation and management.
Handles AES key derivation, seed management, and nonce generation.
"""

import os
import hashlib
import secrets
import base64
import json
from typing import Tuple
import numpy as np

from utils.logger import setup_logger, get_config_path

logger = setup_logger("CRYPTO_UTILS", get_config_path())


def generate_master_seed(seed_length: int = 32) -> bytes:
    """
    Generate a cryptographically secure master seed.

    Args:
        seed_length: Length of the seed in bytes (default 32 = 256 bits).

    Returns:
        Random bytes of specified length.
    """
    seed = secrets.token_bytes(seed_length)
    logger.info(f"Generated master seed: {seed_length * 8} bits")
    return seed


def derive_aes_key(master_seed: bytes, salt: bytes = None) -> bytes:
    """
    Derive a 256-bit AES key from the master seed using PBKDF2.

    Args:
        master_seed: The master seed bytes.
        salt: Optional salt bytes. Generated randomly if not provided.

    Returns:
        32-byte AES-256 key.
    """
    if salt is None:
        salt = secrets.token_bytes(16)
    key = hashlib.pbkdf2_hmac("sha256", master_seed, salt, 100000, dklen=32)
    logger.info("Derived AES-256 key from master seed")
    return key


def generate_nonce(nonce_size: int = 12) -> bytes:
    """
    Generate a random nonce for AES-GCM.

    Args:
        nonce_size: Size of nonce in bytes (default 12 = 96 bits for GCM).

    Returns:
        Random bytes of specified length.
    """
    nonce = secrets.token_bytes(nonce_size)
    logger.info(f"Generated random nonce: {nonce_size * 8} bits")
    return nonce


def derive_quantum_seeds(master_seed: bytes, num_blocks: int) -> dict:
    """
    Derive deterministic seeds for quantum encryption of each block.

    Uses HMAC-based key derivation so that the same master seed
    produces the same block seeds, ensuring deterministic encryption.

    Args:
        master_seed: The master seed bytes.
        num_blocks: Number of blocks to generate seeds for.

    Returns:
        Dictionary with quantum seed parameters.
    """
    # Derive x0, y0 for Henon map from master seed
    h = hashlib.sha512(master_seed + b"quantum_henon_seed").digest()
    x0 = (int.from_bytes(h[:8], "big") % 10000) / 10000.0
    y0 = (int.from_bytes(h[8:16], "big") % 10000) / 10000.0
    # Ensure valid Henon map initial conditions
    x0 = max(0.01, min(0.99, x0))
    y0 = max(0.01, min(0.99, y0))

    seeds = {
        "x0": x0,
        "y0": y0,
        "alpha": 1.4,
        "beta": 0.3,
        "num_blocks": num_blocks,
        "master_seed_hash": hashlib.sha256(master_seed).hexdigest(),
    }
    logger.info(
        f"Derived quantum seeds for {num_blocks} blocks: x0={x0:.6f}, y0={y0:.6f}"
    )
    return seeds


def generate_session_nonce(nonce_length: int = 16) -> bytes:
    """
    Generate a random session nonce for per-block ephemeral seeds.
    
    This provides forward secrecy: even if master_seed leaks, past sessions
    using different session_nonce values remain secure.
    
    Args:
        nonce_length: Length of nonce in bytes (default 16 = 128 bits).
    
    Returns:
        Random nonce bytes.
    """
    nonce = secrets.token_bytes(nonce_length)
    logger.info(f"Generated session nonce: {nonce.hex()[:16]}... ({nonce_length} bytes)")
    return nonce


def derive_block_seed(
    master_seed: bytes,
    block_id: int,
    session_nonce: bytes,
) -> Tuple[float, float]:
    """
    Derive per-block ephemeral seeds using a ratchet mechanism.
    
    This provides forward secrecy: each block gets a unique seed derived from:
    - master_seed: Base key material
    - block_id: Block identifier (0 to num_blocks-1)
    - session_nonce: Random per-encryption-run nonce
    
    If master_seed leaks later, an adversary cannot reconstruct seeds for
    past sessions without also having their specific session_nonce.
    
    Args:
        master_seed: The master seed bytes.
        block_id: Block identifier (0 to num_blocks-1).
        session_nonce: Random nonce specific to this encryption session.
    
    Returns:
        Tuple of (x0, y0) for Henon map initialization.
    """
    # Derive unique seed for this block + session
    block_material = master_seed + session_nonce + block_id.to_bytes(4, 'big')
    block_hash = hashlib.sha256(block_material).digest()
    
    # Extract x0, y0 from hash (same approach as derive_quantum_seeds)
    x0 = (int.from_bytes(block_hash[:8], "big") % 10000) / 10000.0
    y0 = (int.from_bytes(block_hash[8:16], "big") % 10000) / 10000.0
    
    # Ensure valid Henon map initial conditions
    x0 = max(0.01, min(0.99, x0))
    y0 = max(0.01, min(0.99, y0))
    
    return x0, y0


def derive_all_block_seeds(
    master_seed: bytes,
    num_blocks: int,
    session_nonce: bytes,
) -> dict:
    """
    Derive ephemeral seeds for all blocks using the ratchet mechanism.
    
    Args:
        master_seed: The master seed bytes.
        num_blocks: Number of blocks to generate seeds for.
        session_nonce: Random session nonce.
    
    Returns:
        Dictionary with per-block seeds and session info:
        {
            "session_nonce": session_nonce_hex,
            "session_nonce_b64": base64,
            "alpha": 1.4,
            "beta": 0.3,
            "num_blocks": num_blocks,
            "master_seed_hash": hash,
            "block_seeds": [
                {"block_id": 0, "x0": ..., "y0": ...},
                {"block_id": 1, "x0": ..., "y0": ...},
                ...
            ]
        }
    """
    block_seeds = []
    
    for block_id in range(num_blocks):
        x0, y0 = derive_block_seed(master_seed, block_id, session_nonce)
        block_seeds.append({
            "block_id": block_id,
            "x0": x0,
            "y0": y0,
        })
    
    seeds = {
        "session_nonce": session_nonce.hex(),
        "session_nonce_b64": encode_bytes_b64(session_nonce),
        "alpha": 1.4,
        "beta": 0.3,
        "num_blocks": num_blocks,
        "master_seed_hash": hashlib.sha256(master_seed).hexdigest(),
        "block_seeds": block_seeds,
    }
    
    logger.info(f"Derived ephemeral seeds for {num_blocks} blocks with session nonce")
    logger.info(f"Forward secrecy enabled: seeds independent per session")
    
    return seeds


def encode_bytes_b64(data: bytes) -> str:
    """Encode bytes to base64 string for JSON storage."""
    return base64.b64encode(data).decode("utf-8")


def decode_bytes_b64(b64_str: str) -> bytes:
    """Decode base64 string back to bytes."""
    return base64.b64decode(b64_str.encode("utf-8"))


def save_key_material(
    master_seed: bytes,
    aes_key: bytes,
    salt: bytes,
    output_path: str,
) -> str:
    """
    Save key material to a secure JSON file.
    NOTE: In production, this should use a proper key management system.

    Args:
        master_seed: Master seed bytes.
        aes_key: AES key bytes.
        salt: Salt bytes used for key derivation.
        output_path: Path to save the key file.

    Returns:
        Path to the saved key file.
    """
    key_data = {
        "master_seed": encode_bytes_b64(master_seed),
        "aes_key": encode_bytes_b64(aes_key),
        "salt": encode_bytes_b64(salt),
        "key_size_bits": len(aes_key) * 8,
    }
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(key_data, f, indent=2)
    logger.info(f"Key material saved to {output_path}")
    return output_path


def load_key_material(key_path: str) -> Tuple[bytes, bytes, bytes]:
    """
    Load key material from a JSON file.

    Args:
        key_path: Path to the key file.

    Returns:
        Tuple of (master_seed, aes_key, salt).
    """
    if not os.path.exists(key_path):
        raise FileNotFoundError(f"Key file not found: {key_path}")
    with open(key_path, "r") as f:
        key_data = json.load(f)
    master_seed = decode_bytes_b64(key_data["master_seed"])
    aes_key = decode_bytes_b64(key_data["aes_key"])
    salt = decode_bytes_b64(key_data["salt"])
    logger.info(f"Key material loaded from {key_path}")
    return master_seed, aes_key, salt


def encode_ndarray_b64(arr: np.ndarray) -> str:
    """
    Encode numpy array to base64 string for JSON storage.

    Args:
        arr: NumPy array (any shape/dtype).

    Returns:
        Base64-encoded string of array bytes.
    """
    buffer = np.ascontiguousarray(arr).tobytes()
    return base64.b64encode(buffer).decode("utf-8")


def decode_ndarray_b64(b64_str: str, shape: tuple, dtype: str) -> np.ndarray:
    """
    Decode base64 string back to numpy array.

    Args:
        b64_str: Base64-encoded string.
        shape: Target array shape (e.g., (512, 512)).
        dtype: NumPy data type name (e.g., "uint8").

    Returns:
        Reconstructed NumPy array.
    """
    buffer = base64.b64decode(b64_str.encode("utf-8"))
    arr = np.frombuffer(buffer, dtype=np.dtype(dtype))
    return arr.reshape(shape)
