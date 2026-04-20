# Setup Guide - Hybrid AI-Quantum Satellite Image Encryption System

## Prerequisites
- **Python 3.8+** (tested with Python 3.10)
- **Git** (for cloning repositories)
- **Visual C++ Build Tools** (Windows only, needed for some packages)

---

## Installation Steps

### 1. Clone Required External Repositories

```bash
cd File_To_Link

# Clone FlexiMo (AI Segmentation - Vision Transformer)
git clone https://github.com/danfenghong/IEEE_TGRS_Fleximo repos/fleximo_repo

# Clone Quantum Encryption (NEQR)
git clone https://github.com/ManavMNair/Quantum-image-encryption repos/quantum_repo
```

### 2. Install Python Dependencies

```bash
# Install main dependencies
pip install -r requirements.txt

# If liboqs-python installation fails (common on Windows), try:
pip install --upgrade --force-reinstall liboqs-python
```

### 3. Verify Installation

```bash
# Test imports
python -c "import oqs; print('✓ liboqs-python OK')"
python -c "import torch; print('✓ PyTorch OK')"
python -c "import qiskit; print('✓ Qiskit OK')"

# Run minimal startup check
python main.py --mode analyze --input input/test.png
```

---

## Troubleshooting

### Error: "No oqs shared libraries found"

This occurs when `liboqs-python` is installed but the compiled library is missing.

**Solution:**
```bash
# Force reinstall with prebuilt binaries
pip install --upgrade --force-reinstall --no-cache-dir liboqs-python

# If that still fails, install from conda (more reliable)
conda install -c conda-forge liboqs-python
```

### Error: "Remote branch 0.14.1 not found"

The old version tried to build liboqs from source with an outdated branch.

**Solution:**
```bash
# Use pip's prebuilt binary (version 0.9.0+)
pip uninstall liboqs-python
pip install liboqs-python==0.9.1
```

### Error: "liboqs-python not installed. Install with: pip install liboqs-python"

The package didn't install properly.

**Solution:**
```bash
# Check system dependencies
# On Ubuntu/Debian:
sudo apt-get install liboqs libssl-dev

# On Windows:
# - Install Visual C++ Build Tools
# - Or use conda: conda install -c conda-forge liboqs-python

# Then reinstall
pip install --upgrade liboqs-python
```

### PyTorch Installation Issues

**On Windows with NVIDIA GPU:**
```bash
# Install CUDA-enabled PyTorch
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118
```

**On CPU only:**
```bash
pip install torch torchvision
```

### Qiskit Import Issues

```bash
pip install --upgrade qiskit qiskit-aer
```

---

## Dependencies Summary

| Package | Version | Purpose | Status |
|---------|---------|---------|--------|
| liboqs-python | ≥0.9.0 | Post-quantum crypto (ML-KEM, ML-DSA) | **Critical** |
| cryptography | ≥41.0.0 | AES-256-GCM, key derivation | **Critical** |
| torch | ≥2.0.0 | Deep learning (FlexiMo) | **Critical** |
| torchvision | ≥0.15.0 | Image utilities | **Critical** |
| qiskit | ≥1.0.0 | Quantum simulation (NEQR) | **Critical** |
| Pillow | ≥10.0.0 | PNG/image I/O | **Critical** |
| numpy | ≥1.24.0 | Numerical computing | **Critical** |
| opencv-python | ≥4.8.0 | Image processing | **Critical** |
| matplotlib | ≥3.7.0 | Visualization | Optional |

---

## Running the System

### Full Pipeline (Encrypt → Decrypt → Verify)
```bash
python main.py
```

### Single Mode Operations
```bash
# Encryption only
python main.py --mode encrypt --input input/satellite.png

# Decryption only
python main.py --mode decrypt --metadata output/metadata/satellite_metadata.json

# Analysis only
python main.py --mode analyze --input input/satellite.png

# Verification only
python main.py --mode verify --original input/satellite.png --decrypted output/decrypted/satellite.png
```

---

## Configuration

Edit `config/config.json` to customize:
- **Key protection passphrase** (STEP 4.5: FIX #3)
- **ML-KEM recipient public key path** (STEP 9: FIX #1)
- **ML-DSA sender private key path** (STEP 10: FIX #2)
- **Maximum ROI blocks** (for quick testing)

---

## Security Fixes Implemented

✅ **FIX #1**: ML-KEM (Kyber768) Post-Quantum Key Transport (NIST FIPS 203)  
✅ **FIX #2**: ML-DSA (Dilithium3) Metadata Signatures (NIST FIPS 204)  
✅ **FIX #3**: Scrypt + AES-256-GCM Key Protection at Rest  
✅ **FIX #4**: PNG tEXt Metadata Embedding (Dependency Warnings)  
✅ **FIX #5**: Per-Block Ephemeral Seeds (Forward Secrecy)  
✅ **FIX #6**: SHA-256 Hash of .enc File (File Integrity)  

---

## Performance Notes

- **First run may be slow** due to DOFA ViT model download (~300MB)
- **Quantum encryption is computationally intensive**: ~1-3 minutes per satellite image (100MP)
- **Use --max-blocks N** for quick testing on large images

---

## For Production Deployment

⚠️ **Security Recommendations:**
1. Replace config passphrase with HSM/TPM key storage (FIX #3)
2. Generate new ML-KEM/ML-DSA keys for your organization
3. Store keys separately from the application
4. Enable audit logging of all encryption/decryption operations
5. Test backup and recovery procedures with v1.0 legacy format

---

## References

- **NIST FIPS 203** (ML-KEM): https://nvlpubs.nist.gov/nistpubs/FIPS/NIST.FIPS.203.pdf
- **NIST FIPS 204** (ML-DSA): https://nvlpubs.nist.gov/nistpubs/FIPS/NIST.FIPS.204.pdf
- **liboqs**: https://github.com/open-quantum-safe/liboqs-python
- **FlexiMo**: https://github.com/danfenghong/IEEE_TGRS_Fleximo
- **NEQR**: https://github.com/ManavMNair/Quantum-image-encryption
