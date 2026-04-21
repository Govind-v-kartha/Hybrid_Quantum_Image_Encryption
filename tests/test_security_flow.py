import hashlib
import json
import os

import pytest

from utils.crypto_utils_pqc import save_signature_file
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
