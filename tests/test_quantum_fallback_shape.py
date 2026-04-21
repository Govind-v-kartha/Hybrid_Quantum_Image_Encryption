import numpy as np

from engines import quantum_engine
from utils.block_utils import BLOCK_SIZE


class _FakeFuture:
    def result(self, timeout=None):
        raise Exception("simulated worker failure")


class _FakeExecutor:
    def __init__(self, *args, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def submit(self, fn, item):
        return _FakeFuture()


def test_encrypt_parallel_failure_uses_block_sized_rgb_fallback(monkeypatch):
    monkeypatch.setattr(quantum_engine, "ThreadPoolExecutor", _FakeExecutor)
    monkeypatch.setattr(quantum_engine, "ProcessPoolExecutor", _FakeExecutor)
    monkeypatch.setattr(quantum_engine, "as_completed", lambda futures: list(futures))

    blocks = [np.ones((BLOCK_SIZE, BLOCK_SIZE, 3), dtype=np.uint8)]
    encrypted_blocks = [None]
    all_encryption_info = [None]

    ok = quantum_engine._encrypt_blocks_parallel(
        blocks=blocks,
        encrypted_blocks=encrypted_blocks,
        all_encryption_info=all_encryption_info,
        quantum_seeds={},
        repo_path="unused",
        shots=1,
        total_start=0.0,
        log_interval=1,
        logger=quantum_engine.logger,
    )

    assert ok is True
    assert encrypted_blocks[0].shape == (BLOCK_SIZE, BLOCK_SIZE, 3)
    assert encrypted_blocks[0].dtype == np.uint8


def test_decrypt_parallel_failure_uses_block_sized_rgb_fallback(monkeypatch):
    monkeypatch.setattr(quantum_engine, "ThreadPoolExecutor", _FakeExecutor)
    monkeypatch.setattr(quantum_engine, "ProcessPoolExecutor", _FakeExecutor)
    monkeypatch.setattr(quantum_engine, "as_completed", lambda futures: list(futures))

    encrypted_blocks = [np.ones((BLOCK_SIZE, BLOCK_SIZE, 3), dtype=np.uint8)]
    decrypted_blocks = [None]

    ok = quantum_engine._decrypt_blocks_parallel(
        encrypted_blocks=encrypted_blocks,
        decrypted_blocks=decrypted_blocks,
        quantum_seeds={},
        all_encryption_info=[{}],
        repo_path="unused",
        shots=1,
        total_start=0.0,
        log_interval=1,
        logger=quantum_engine.logger,
    )

    assert ok is True
    assert decrypted_blocks[0].shape == (BLOCK_SIZE, BLOCK_SIZE, 3)
    assert decrypted_blocks[0].dtype == np.uint8
