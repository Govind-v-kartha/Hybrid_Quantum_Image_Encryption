import numpy as np

from quantum.neqr_new import NEQRQuantumEncoder, reconstruct_neqr_image as _reconstruct_neqr_image


def encode_neqr(image):
    """Encode a square grayscale image using the canonical NEQR convention."""
    image = np.asarray(image)
    if image.ndim != 2 or image.shape[0] != image.shape[1]:
        raise ValueError(f"Expected square grayscale image, got shape={image.shape}")

    encoder = NEQRQuantumEncoder(image_size=int(image.shape[0]))
    return encoder.encode(image).circuit


def reconstruct_neqr_image(qc, height, width, shots=8192):
    """Compatibility wrapper that reconstructs from the exact statevector."""
    return _reconstruct_neqr_image(qc, height, width, shots=shots)