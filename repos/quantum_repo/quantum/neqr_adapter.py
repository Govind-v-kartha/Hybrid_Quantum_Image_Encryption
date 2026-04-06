"""
Compatibility adapter for NEQR encoding.

Exposes the legacy function-style interface used by the current pipeline,
while internally delegating encoding to the new class-based implementation.
"""

from __future__ import annotations

from typing import Dict

import numpy as np

from quantum.neqr_new import NEQRQuantumEncoder, reconstruct_neqr_image as _reconstruct_neqr_image

_ENCODER_CACHE: Dict[int, NEQRQuantumEncoder] = {}


def encode_neqr(image: np.ndarray):
    """Encode grayscale image to a NEQR quantum circuit using the new encoder."""
    image = np.asarray(image)
    if image.ndim != 2 or image.shape[0] != image.shape[1]:
        raise ValueError(f"Expected square grayscale image, got shape={image.shape}")

    image_size = int(image.shape[0])
    encoder = _ENCODER_CACHE.get(image_size)
    if encoder is None:
        encoder = NEQRQuantumEncoder(image_size=image_size)
        _ENCODER_CACHE[image_size] = encoder

    encoding = encoder.encode(image)
    return encoding.circuit


def reconstruct_neqr_image(qc, height, width, shots=8192):
    """Reconstruct an NEQR image using the matching little-endian flat index."""
    return _reconstruct_neqr_image(qc, height, width, shots=shots)
