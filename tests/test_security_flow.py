import hashlib
import json
import os

import numpy as np
import pytest

from utils.crypto_utils_pqc import save_signature_file
from workflows import encrypt_workflow, decrypt_workflow
from workflows.encrypt_workflow import _build_signature_path as build_encrypt_signature_path
from workflows.decrypt_workflow import (
    _build_signature_path as build_decrypt_signature_path,
    _enforce_signature_gate,
)


def test_signature_path_contract_consistency(tmp_path):
    metadata_path = str(tmp_path / "sample_metadata.json")
    expected_signature_path = os.path.join(str(tmp_path), "sample_metadata_bundle.sig")

    encrypt_sig_path = build_encrypt_signature_path(metadata_path)
    decrypt_sig_path = build_decrypt_signature_path(metadata_path)

    assert encrypt_sig_path == expected_signature_path
    assert decrypt_sig_path == expected_signature_path
    assert encrypt_sig_path == decrypt_sig_path


def test_signature_gate_fails_closed_when_signature_missing(tmp_path):
    metadata_path = tmp_path / "sample_metadata.json"
    metadata_path.write_text(json.dumps({"encryption_metadata": {}}), encoding="utf-8")

    config = {
        "security_policy": {
            "require_metadata_signature": True,
            "allow_unsigned_decryption": False,
        },
        "metadata_signature": {
            "sender_public_key_path": str(tmp_path / "sender_dilithium3_public.key"),
        },
    }

    with pytest.raises(RuntimeError, match="Signature required by policy but file is missing"):
        _enforce_signature_gate(str(metadata_path), config)


def test_signature_gate_fails_closed_when_sender_public_key_missing(tmp_path):
    metadata_path = tmp_path / "sample_metadata.json"
    metadata_path.write_text(json.dumps({"encryption_metadata": {}}), encoding="utf-8")

    sig_path = build_decrypt_signature_path(str(metadata_path))
    with open(sig_path, "w", encoding="utf-8") as f:
        f.write("deadbeef")

    config = {
        "security_policy": {
            "require_metadata_signature": True,
            "allow_unsigned_decryption": False,
        },
        "metadata_signature": {
            "sender_public_key_path": str(tmp_path / "missing_sender_dilithium3_public.key"),
        },
    }

    with pytest.raises(RuntimeError, match="sender public key is missing"):
        _enforce_signature_gate(str(metadata_path), config)


def test_metadata_file_hash_is_stable_after_writing_sidecar_signature(tmp_path):
    metadata_path = tmp_path / "sample_metadata.json"
    metadata_path.write_text(
        json.dumps({"encryption_metadata": {"version": "1.0", "timestamp": "2026-04-21T00:00:00"}}),
        encoding="utf-8",
    )

    metadata_hash_before = hashlib.sha256(metadata_path.read_bytes()).hexdigest()

    sig_path = build_encrypt_signature_path(str(metadata_path))
    save_signature_file("deadbeef", sig_path)

    metadata_hash_after = hashlib.sha256(metadata_path.read_bytes()).hexdigest()

    assert metadata_hash_after == metadata_hash_before
    assert os.path.exists(sig_path)


def _patch_encrypt_pipeline_for_metadata_tests(monkeypatch, tmp_path):
    dummy_image = np.zeros((2, 2, 3), dtype=np.uint8)
    roi_mask = np.array([[1, 0], [0, 1]], dtype=np.uint8)
    background_mask = 1 - roi_mask

    monkeypatch.setattr(encrypt_workflow, "load_image", lambda _: dummy_image)
    monkeypatch.setattr(
        encrypt_workflow,
        "get_image_info",
        lambda *_: {"filename": "dummy.png", "size": [2, 2], "channels": 3, "hash": "deadbeef"},
    )
    monkeypatch.setattr(
        encrypt_workflow,
        "segment_image_fleximo",
        lambda *_: (roi_mask, background_mask, np.zeros((2, 2), dtype=np.uint8)),
    )
    monkeypatch.setattr(encrypt_workflow, "save_segmentation_visualization", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        encrypt_workflow,
        "divide_roi_into_blocks",
        lambda *_: ([np.ones((32, 32), dtype=np.uint8)], [{"position": [0, 0]}], np.array([0, 0, 2, 2])),
    )
    monkeypatch.setattr(
        encrypt_workflow,
        "get_block_statistics",
        lambda block_map: {"total_blocks": len(block_map), "padded_blocks": 0},
    )
    monkeypatch.setattr(
        encrypt_workflow,
        "encrypt_all_blocks",
        lambda blocks, *_: (blocks, [{"block_id": 0, "nonce": "n"}]),
    )
    monkeypatch.setattr(
        encrypt_workflow,
        "encrypt_background",
        lambda image, *_: (b"\x01" * image.size, b"tag", {"nonce": "nonce", "tag": "tag", "image_shape": list(image.shape)}),
    )
    monkeypatch.setattr(encrypt_workflow, "fuse_encrypted_image", lambda *_: dummy_image)

    def _save_image(_image, path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(b"png")

    monkeypatch.setattr(encrypt_workflow, "save_image", _save_image)
    monkeypatch.setattr(encrypt_workflow, "embed_png_metadata", lambda *args, **kwargs: None)

    def _save_protected_keys(_keys, _passphrase, path):
        with open(path, "wb") as f:
            f.write(b"enc")

    monkeypatch.setattr(encrypt_workflow, "save_protected_keys", _save_protected_keys)


def test_salt_b64_present_in_encryption_metadata_when_keys_derived(tmp_path, monkeypatch):
    _patch_encrypt_pipeline_for_metadata_tests(monkeypatch, tmp_path)

    config = {
        "paths": {"output_dir": str(tmp_path / "out")},
        "quantum_encryption": {"shots": 8},
        "security_policy": {"allow_plaintext_key_export": False},
        "key_protection": {"passphrase": "unit-test-passphrase"},
        "post_quantum": {},
        "metadata_signature": {},
    }

    result = encrypt_workflow.run_encryption(str(tmp_path / "dummy.png"), config=config)
    with open(result["metadata_path"], "r", encoding="utf-8") as f:
        metadata = json.load(f)

    enc_meta = metadata["encryption_metadata"]
    assert "salt_b64" in enc_meta
    assert enc_meta["salt_b64"]


def test_key_protection_metadata_present_when_protected_keys_emitted(tmp_path, monkeypatch):
    _patch_encrypt_pipeline_for_metadata_tests(monkeypatch, tmp_path)

    config = {
        "paths": {"output_dir": str(tmp_path / "out")},
        "quantum_encryption": {"shots": 8},
        "security_policy": {"allow_plaintext_key_export": False},
        "key_protection": {"passphrase": "unit-test-passphrase"},
        "post_quantum": {},
        "metadata_signature": {},
    }

    result = encrypt_workflow.run_encryption(str(tmp_path / "dummy.png"), config=config)
    with open(result["metadata_path"], "r", encoding="utf-8") as f:
        metadata = json.load(f)

    key_protection = metadata["encryption_metadata"].get("key_protection")
    assert key_protection is not None
    assert key_protection.get("enabled") is True
    assert key_protection.get("protected_keys_file", "").endswith("_keys.enc")


def test_legacy_plaintext_branch_denied_by_default_policy(tmp_path):
    metadata_path = tmp_path / "legacy_metadata.json"
    metadata_path.write_text(
        json.dumps(
            {
                "encryption_metadata": {
                    "original_image": {"size": [2, 2], "channels": 3},
                    "block_map": [],
                    "roi_information": {"roi_bbox": [0, 0, 2, 2]},
                    "block_encryption_info": [],
                    "output_files": {},
                    "classical_encryption": {
                        "nonce": "AA==",
                        "tag": "AA==",
                        "image_shape": [2, 2, 3],
                    },
                }
            }
        ),
        encoding="utf-8",
    )

    config = {
        "paths": {"output_dir": str(tmp_path / "out")},
        "security_policy": {
            "require_metadata_signature": False,
            "allow_unsigned_decryption": True,
            "allow_legacy_plaintext_keys": False,
        },
        "metadata_signature": {},
    }

    with pytest.raises(RuntimeError, match="Legacy plaintext key fallback is disabled"):
        decrypt_workflow.run_decryption(str(metadata_path), config=config)


def test_encryption_fails_closed_when_no_key_recovery_path_exists(tmp_path, monkeypatch):
    _patch_encrypt_pipeline_for_metadata_tests(monkeypatch, tmp_path)

    config = {
        "paths": {"output_dir": str(tmp_path / "out")},
        "quantum_encryption": {"shots": 8},
        "security_policy": {"allow_plaintext_key_export": False},
        "key_protection": {},
        "post_quantum": {},
        "metadata_signature": {},
    }

    with pytest.raises(RuntimeError, match="no valid key recovery path available"):
        encrypt_workflow.run_encryption(str(tmp_path / "dummy.png"), config=config)


def _write_minimal_decryption_metadata(tmp_path, *, encrypted_background_path, enc_file_hash):
    roi_mask = np.array([[1, 0], [0, 1]], dtype=np.uint8)
    roi_mask_path = tmp_path / "roi_mask.npy"
    np.save(roi_mask_path, roi_mask)

    metadata = {
        "encryption_metadata": {
            "original_image": {"size": [2, 2], "channels": 3, "filename": "orig.png"},
            "block_map": [],
            "roi_information": {
                "roi_bbox": [0, 0, 2, 2],
                "roi_mask_path": str(roi_mask_path),
            },
            "block_encryption_info": [],
            "output_files": {
                "keys": str(tmp_path / "legacy_keys.json"),
                "encrypted_background": str(encrypted_background_path),
                "encrypted_image": str(tmp_path / "encrypted.png"),
            },
            "classical_encryption": {
                "nonce": "AAAAAAAAAAAAAAAA",
                "tag": "AAAAAAAAAAAAAAAAAAAAAA==",
                "image_shape": [2, 2, 3],
                "enc_file_hash": enc_file_hash,
            },
        }
    }

    metadata_path = tmp_path / "metadata.json"
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
    return metadata_path


def _build_unsigned_legacy_decrypt_config(tmp_path):
    return {
        "paths": {"output_dir": str(tmp_path / "out")},
        "security_policy": {
            "require_metadata_signature": False,
            "allow_unsigned_decryption": True,
            "allow_legacy_plaintext_keys": True,
        },
        "metadata_signature": {},
    }


def test_signature_gate_rejects_tampered_metadata_after_signing(tmp_path, monkeypatch):
    metadata_path = tmp_path / "sample_metadata.json"
    metadata_path.write_text(json.dumps({"encryption_metadata": {"version": "1.0"}}), encoding="utf-8")

    sig_path = build_decrypt_signature_path(str(metadata_path))
    sig_path = str(sig_path)
    with open(sig_path, "w", encoding="utf-8") as f:
        f.write("deadbeef")

    sender_public_key_path = tmp_path / "sender_dilithium3_public.key"
    sender_public_key_path.write_bytes(b"dummy-public-key")

    monkeypatch.setattr(decrypt_workflow, "load_dilithium_public_key", lambda _: b"public-key")
    monkeypatch.setattr(decrypt_workflow, "verify_bundle", lambda *_: False)

    config = {
        "security_policy": {
            "require_metadata_signature": True,
            "allow_unsigned_decryption": False,
        },
        "metadata_signature": {
            "sender_public_key_path": str(sender_public_key_path),
        },
    }

    with pytest.raises(RuntimeError, match="Metadata verification failed"):
        _enforce_signature_gate(str(metadata_path), config)


def test_decryption_rejects_when_encrypted_background_file_missing(tmp_path, monkeypatch):
    missing_background = tmp_path / "st2_background.enc"
    metadata_path = _write_minimal_decryption_metadata(
        tmp_path,
        encrypted_background_path=missing_background,
        enc_file_hash=hashlib.sha256(b"expected").hexdigest(),
    )

    config = _build_unsigned_legacy_decrypt_config(tmp_path)
    monkeypatch.setattr(decrypt_workflow, "load_key_material", lambda *_: (b"m" * 32, b"k" * 32, b"s" * 16))

    with pytest.raises(FileNotFoundError, match=r"st2_background\.enc"):
        decrypt_workflow.run_decryption(str(metadata_path), config=config)


def test_decryption_rejects_when_encrypted_background_hash_mismatch(tmp_path, monkeypatch):
    background_path = tmp_path / "st2_background.enc"
    background_path.write_bytes(b"actual-ciphertext")

    metadata_path = _write_minimal_decryption_metadata(
        tmp_path,
        encrypted_background_path=background_path,
        enc_file_hash=hashlib.sha256(b"different-ciphertext").hexdigest(),
    )

    config = _build_unsigned_legacy_decrypt_config(tmp_path)
    monkeypatch.setattr(decrypt_workflow, "load_key_material", lambda *_: (b"m" * 32, b"k" * 32, b"s" * 16))

    with pytest.raises(RuntimeError, match="integrity check failed"):
        decrypt_workflow.run_decryption(str(metadata_path), config=config)
