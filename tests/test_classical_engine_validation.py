import numpy as np
import pytest

from engines.classical_engine import decrypt_background, encrypt_background


def test_invalid_aes_key_length_rejected_in_encrypt_background():
    image = np.zeros((2, 2, 3), dtype=np.uint8)
    background_mask = np.ones((2, 2), dtype=np.uint8)
    invalid_aes_key = b"k" * 31
    nonce = b"n" * 12

    with pytest.raises(ValueError, match="AES key must be 32 bytes"):
        encrypt_background(image, background_mask, invalid_aes_key, nonce)


def test_invalid_nonce_length_rejected_in_decrypt_background():
    ciphertext = b""
    tag = b""
    aes_key = b"k" * 32
    invalid_nonce = b"n" * 11

    with pytest.raises(ValueError, match="Nonce must be 12 bytes"):
        decrypt_background(ciphertext, tag, aes_key, invalid_nonce, (1, 1, 3))
