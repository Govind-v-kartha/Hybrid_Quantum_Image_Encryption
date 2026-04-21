# Hybrid AI-Quantum Satellite Image Encryption System — Context

> **Living document** — Updated whenever changes are made to the logic, architecture, or data flow.
> Last updated: 2026-04-07

---

## 1. System Architecture Overview

```
┌─────────────┐    ┌──────────────┐    ┌───────────────┐
│  AI Engine   │───▶│Decision Engine│───▶│ Quantum Engine │
│  (FlexiMo)  │    │ (32×32 blocks)│    │(NEQR per-ch)  │
│  ROI/BG mask │    └──────────────┘    └───────┬───────┘
└──────┬──────┘                                 │
       │           ┌──────────────┐    ┌────────▼───────┐
       └──────────▶│Classical Eng. │───▶│  Fusion Engine  │──▶ Encrypted Image
                   │ (AES-256-GCM)│    │ (ROI+BG merge)  │
                   └──────────────┘    └─────────────────┘
```

### Component Roles

| Engine | File | Responsibility |
|--------|------|----------------|
| AI Engine | `engines/ai_engine.py` | FlexiMo ViT semantic segmentation → ROI/background masks |
| Decision Engine | `engines/decision_engine.py` | Divide ROI bounding box into 32×32 blocks with padding info |
| Quantum Engine | `engines/quantum_engine.py` | **Per-channel** NEQR encoding, quantum scrambling, DNA encryption |
| Classical Engine | `engines/classical_engine.py` | AES-256-GCM encryption of background pixels |
| Fusion Engine | `engines/fusion_engine.py` | Merge quantum-encrypted ROI blocks + classical background |
| Verification Engine | `engines/verification_engine.py` | PSNR, SSIM, entropy, hash verification |

---

## 2. Encryption Pipeline (Forward)

**File:** `workflows/encrypt_workflow.py`

1. **Load Image** — Read satellite image as RGB `(H,W,3)` uint8
2. **Segment** — FlexiMo ViT produces `roi_mask` (binary) and `background_mask`
3. **Block Division** — ROI bounding box → 32×32 blocks (zero-padded at edges)
4. **Key Generation** — `generate_master_seed()` → `derive_quantum_seeds()` + `derive_aes_key()`
5. **Quantum Encryption (Per-Channel NEQR):**
   - For each 32×32×3 block, split into R, G, B channels
   - For each channel independently:
     - NEQR quantum circuit encoding (8-bit grayscale)
     - Quantum scrambling (X, Z gates via Henon chaotic key `bpk`)
     - Quantum permutation (SWAP gates via Henon chaotic key `ksk`)
     - Shot-based measurement with **majority vote** reconstruction
     - DNA encoding (4 planes) + XOR diffusion with chaotic key image
   - Stack encrypted channels → 32×32×3 encrypted block
6. **Classical Encryption** — AES-256-GCM on background pixels
7. **Fusion** — Place encrypted ROI blocks + encrypted background into fused image
8. **Metadata** — Save block_map, encryption_info (per-channel keys), masks, encrypted blocks

---

## 3. Decryption Pipeline (Reverse — True Mirror)

**File:** `workflows/decrypt_workflow.py`

1. **Load Metadata** — Keys, masks, block_map, encryption records
2. **Load Encrypted Blocks** — From saved `.npy` (lossless) or unfuse from image
3. **Classical Decryption** — AES-256-GCM → perfect background recovery
4. **Quantum Decryption (Per-Channel — Exact Mirror):**
   - For each encrypted 32×32×3 block, split into R', G', B' channels
   - For each channel (using stored per-channel keys):
     - DNA decryption (reverse XOR + reverse substitution) → scrambled channel
     - NEQR re-encode scrambled channel
     - Reverse quantum permutation (reverse SWAP order)
     - Reverse quantum scrambling (reverse X, Z order)
     - Shot-based measurement with **majority vote** → original channel
   - Stack → 32×32×3 decrypted RGB block
5. **Reconstruct** — Place decrypted blocks onto background using block_map + ROI mask
6. **Verify** — PSNR=∞, SSIM=1.0, hash match, zero pixel difference

---

## 4. Key Technical Decisions

### 4.1 Per-Channel NEQR (Why Not Grayscale?)

**Problem:** Original code converted RGB→grayscale before NEQR encoding. This permanently discards color information. No quantum operation can recover the original RGB from grayscale alone.

**Solution:** Process R, G, B channels independently through the complete NEQR pipeline. This triples the quantum circuits per block but preserves all color information for truly lossless encryption.

**Trade-off:** 3× computation time per block. With 16384 shots/channel (configurable), each channel takes similar time as the old grayscale processing.

### 4.2 Majority Vote Shot-Based Reconstruction

**Problem:** Original `reconstruct_neqr_image()` iterated through measurement bitstrings and overwrote pixel values — "last write wins". While theoretically correct for deterministic circuits (each position has exactly one intensity), this provides no safety margin.

**Solution:** Accumulate `{(row, col): {intensity: count}}` for all measurements, then select `argmax(count)` per position. This is provably correct for deterministic NEQR circuits and robust against any theoretical edge cases.

**Lossless guarantee:** With 16384 shots and 1024 positions (32×32), each position receives ~16 samples on average. The probability of any position being unsampled is e^{-16} ≈ 1.1×10^{-7}. With 1024 positions, expected missing: ~0.00011 positions — effectively zero.

### 4.3 No Bypass — No `original_blocks.npy`

**Removed:** The encryption workflow no longer saves `original_blocks.npy` (raw plaintext ROI blocks). The decryption workflow no longer checks for or loads this file. All reconstruction relies purely on quantum-decrypted blocks.

---

## 5. Quantum Pipeline Detail

### NEQR Encoding (`repos/quantum_repo/quantum/neqr.py`)

For a 32×32 pixel channel:
- **Position qubits:** 10 (2 × log₂(32) = 2×5)
- **Intensity qubits:** 8 (256 grayscale levels)
- **Total qubits:** 18
- Creates superposition: `|ψ⟩ = (1/√1024) Σ |pos⟩ |intensity(pos)⟩`
- Uses multi-controlled X gates (MCX) for intensity encoding

### Quantum Scrambling (`repos/quantum_repo/quantum/scrambling.py`)

- **`quantum_scramble`**: X and Z gates on position qubits based on `bpk` key
- **`quantum_permutation`**: SWAP gates on position qubits based on `ksk` key
- **Reverse operations**: Apply gates in reverse order (self-inverse for X/Z)

### DNA Encryption (`repos/quantum_repo/dna/`)

- **Encode**: Split 8-bit pixel → 4 DNA planes (2-bit each) + key-based substitution
- **XOR Diffusion**: XOR DNA planes with chaotic key image DNA planes
- **Decode (decrypt)**: Perfectly reversible — XOR → reverse substitution → reassemble

### Key Generation

- Master seed → HMAC-SHA512 → Henon map initial conditions (x₀, y₀)
- Henon map (α=1.8 or 1.4, β=0.3 or 0.015) → chaotic sequences
- Sequences → `bpk` and `ksk` arrays (uint8) for gate control
- Per-channel: channel_id incorporated into seed perturbation

---

## 6. Changelog

| Date | Change | Files Modified |
|------|--------|----------------|
| 2026-04-07 | Initial context.md creation | — |
| 2026-04-07 | Planned: Per-channel NEQR encryption | `quantum_engine.py`, `quantum_worker.py` |
| 2026-04-07 | Planned: Majority vote reconstruction | `neqr.py` |
| 2026-04-07 | Planned: Remove bypass | `encrypt_workflow.py`, `decrypt_workflow.py` |
| 2026-04-07 | Planned: 3-channel fusion support | `fusion_engine.py` |

---

## 7. Configuration Reference

**File:** `config/config.json`

| Parameter | Value | Purpose |
|-----------|-------|---------|
| `quantum_encryption.block_size` | 32 | Pixel block size for NEQR (32×32) |
| `quantum_encryption.shots` | 16384 | Measurement shots per quantum circuit |
| `quantum_encryption.backend` | AerSimulator | Qiskit Aer local simulator |
| `quantum_encryption.encoding` | NEQR | Novel Enhanced Quantum Representation |
| `classical_encryption.algorithm` | AES-256-GCM | Authenticated encryption for background |

### Security Policy Defaults (Fail-Closed)

| Parameter | Default | Effect |
|-----------|---------|--------|
| `security_policy.require_metadata_signature` | `true` | Decryption requires a verifiable metadata signature. |
| `security_policy.allow_unsigned_decryption` | `false` | Unsigned decryption is blocked unless explicitly overridden. |
| `security_policy.allow_legacy_plaintext_keys` | `false` | Legacy plaintext key fallback is blocked unless explicitly overridden. |

This means the legacy plaintext key path exists for compatibility with old bundles but is disabled by default.
