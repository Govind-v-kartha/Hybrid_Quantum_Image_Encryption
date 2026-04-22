# Complete Setup and Run Guide

**Hybrid AI-Quantum Satellite Image Encryption System v1.0.0**

Complete guide from GitHub clone to running the system.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Clone & Initial Setup](#clone--initial-setup)
3. [Environment Configuration](#environment-configuration)
4. [Install Dependencies](#install-dependencies)
5. [Setup Encryption Keys](#setup-encryption-keys)
6. [Running the System](#running-the-system)
7. [Different Modes Explained](#different-modes-explained)
8. [Example Workflows](#example-workflows)
9. [Troubleshooting](#troubleshooting)
10. [Project Structure](#project-structure)

---

## Prerequisites

### System Requirements

- **Python**: 3.8 or later
- **RAM**: 8GB minimum (16GB recommended for large images)
- **Disk Space**: 10GB (for dependencies and test images)
- **OS**: Windows, macOS, or Linux

### Required Tools

- **Git**: For cloning the repository
- **Python pip**: Package manager (usually comes with Python)
- **VS Code** (optional): Recommended IDE

### Verify Installation

```bash
# Check Python version
python --version
# Should be 3.8 or later

# Check pip
pip --version

# Check git
git --version
```

---

## Clone & Initial Setup

### Step 1: Clone the Repository

```bash
# Clone from GitHub
git clone https://github.com/YOUR-USERNAME/satellite-image-encryption.git

# Navigate to project directory
cd satellite-image-encryption

# Verify structure
ls -la
# Should see: main.py, config/, repos/, utils/, etc.
```

### Step 2: Create Project Directories

```bash
# These are auto-created by the system, but you can pre-create them:
mkdir -p input output/encrypted output/decrypted output/metadata output/analysis logs keys
```

### Step 3: Clone External Repositories

The system requires 2 external repositories for AI and quantum encryption:

```bash
# Clone FlexiMo (AI Segmentation)
git clone https://github.com/danfenghong/IEEE_TGRS_Fleximo repos/fleximo_repo

# Clone Quantum Encryption (NEQR)
git clone https://github.com/ManavMNair/Quantum-image-encryption repos/quantum_repo

# Verify they were cloned
ls -la repos/
# Should see: fleximo_repo/, quantum_repo/
```

---

## Environment Configuration

### Step 1: Setup .env File

The system uses `.env` files for secure secret management:

```bash
# Copy the template
cp .env.example .env

# Now .env contains placeholder values - keep this file LOCAL
# This file is in .gitignore (never committed to git)
```

### Step 2: Edit .env with Your Values

Open `.env` in your editor and set actual values:

```bash
# Windows
notepad .env

# macOS/Linux
nano .env
vim .env
```

**Edit these values:**

```
# Your strong passphrase for key encryption
ENCRYPTION_PASSPHRASE=your-very-strong-passphrase-here-min-16-chars

# Path to post-quantum cryptography keys (you'll generate these next)
RECIPIENT_PRIVATE_KEY_PATH=keys/recipient_kyber768_private.key
SENDER_PRIVATE_KEY_PATH=keys/sender_dilithium3_private.key
```

**Make it strong:**
- Minimum 16 characters
- Mix uppercase, lowercase, numbers, symbols
- Example: `MyEncryption@2026_v1#Quantum`

### Step 3: Verify .env is Loaded

```bash
# Check that .env exists and is readable
cat .env
# Should show your actual values (not placeholders)

# Verify .env is in .gitignore
cat .gitignore | grep ".env"
# Should show: .env
```

---

## Install Dependencies

### Step 1: Create Virtual Environment (Recommended)

```bash
# Create virtual environment
python -m venv venv

# Activate it
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# Verify activation (should show (venv) in prompt)
which python
```

### Step 2: Install Requirements

```bash
# Upgrade pip first
pip install --upgrade pip

# Install all dependencies from requirements.txt
pip install -r requirements.txt

# This installs:
# - Quantum: qiskit, qiskit-aer
# - Post-Quantum Crypto: liboqs-python
# - Deep Learning: torch, torchvision, timm
# - Image Processing: Pillow, opencv-python, scikit-image
# - Utilities: numpy, scipy, matplotlib
# - Environment: python-dotenv
```

**Installation time**: ~10-15 minutes (depending on internet speed)

### Step 3: Verify Installation

```bash
# Test critical imports
python -c "import torch; print(f'PyTorch {torch.__version__}')"
python -c "import qiskit; print(f'Qiskit {qiskit.__version__}')"
python -c "from oqs import KeyEncapsulation; print('✓ Kyber (ML-KEM) available')"
python -c "from dotenv import load_dotenv; print('✓ python-dotenv available')"
```

All should print without errors.

---

## Setup Encryption Keys

### Step 1: Generate Post-Quantum Cryptography Keys

The system uses NIST FIPS 203/204 algorithms for post-quantum security:

```bash
# Generate keys (creates Kyber768 ML-KEM and Dilithium3 ML-DSA keys)
python << 'EOF'
import os
from liboqs.python import OQS

# Create keys directory
os.makedirs('keys', exist_ok=True)

# Generate Kyber768 (ML-KEM) keys for key encapsulation
print("Generating Kyber768 (ML-KEM) keys...")
kem = OQS.KeyEncapsulation("Kyber768")
public_key = kem.generate_keyset()
private_key = kem.export_secret_key()

with open('keys/recipient_kyber768_public.key', 'wb') as f:
    f.write(public_key)
with open('keys/recipient_kyber768_private.key', 'wb') as f:
    f.write(private_key)
print("✓ Kyber768 keys generated")

# Generate Dilithium3 (ML-DSA) keys for signatures
print("Generating Dilithium3 (ML-DSA) keys...")
sig = OQS.Signature("Dilithium3")
public_key = sig.generate_keyset()
private_key = sig.export_secret_key()

with open('keys/sender_dilithium3_public.key', 'wb') as f:
    f.write(public_key)
with open('keys/sender_dilithium3_private.key', 'wb') as f:
    f.write(private_key)
print("✓ Dilithium3 keys generated")

# Verify files
import glob
key_files = glob.glob('keys/*.key')
print(f"\n✓ Generated {len(key_files)} key files:")
for f in sorted(key_files):
    size = os.path.getsize(f)
    print(f"  - {os.path.basename(f)} ({size} bytes)")
EOF
```

**Output should be:**
```
Generating Kyber768 (ML-KEM) keys...
✓ Kyber768 keys generated
Generating Dilithium3 (ML-DSA) keys...
✓ Dilithium3 keys generated

✓ Generated 4 key files:
  - recipient_kyber768_private.key (2400 bytes)
  - recipient_kyber768_public.key (1184 bytes)
  - sender_dilithium3_private.key (4432 bytes)
  - sender_dilithium3_public.key (1312 bytes)
```

### Step 2: Set File Permissions (Security)

```bash
# Linux/macOS: Restrict to owner only
chmod 0o600 keys/*.key      # Read/write for owner only
chmod 0o700 keys/           # Execute for owner only (directory)
chmod 0o600 config/config.json

# Windows: Right-click → Properties → Security → Edit → Remove Everyone, keep only your user
# Or use PowerShell:
# icacls "keys" /reset
# icacls "config\config.json" /reset
```

### Step 3: Verify Key Paths in .env

Verify .env points to your generated keys:

```bash
# Should match your actual key locations
cat .env | grep "KEY_PATH"

# Output should show:
# RECIPIENT_PRIVATE_KEY_PATH=keys/recipient_kyber768_private.key
# SENDER_PRIVATE_KEY_PATH=keys/sender_dilithium3_private.key
```

---

## Running the System

### Step 1: Prepare Input Image

```bash
# Copy a test image to input directory
# Supported formats: PNG, JPG, JPEG, TIFF, TIF

mkdir -p input

# Copy your image (or create a test image)
cp /path/to/your/image.png input/
# Or: cp your_satellite_image.tif input/

# Verify image exists
ls -la input/
```

### Step 2: Run Startup Verification

```bash
# Verify everything is set up correctly
python main.py --help

# This will:
# 1. Check all dependencies
# 2. Verify both external repositories exist
# 3. Validate file permissions
# 4. Load and validate .env configuration
# 5. Check Kyber and Dilithium support

# Should output:
# ✓ Dependencies verified
# ✓ Repositories found
# ✓ File permissions secure
# ✓ Configuration loaded from .env
```

### Step 3: Run Full Pipeline

```bash
# Run complete: encrypt → decrypt → verify
python main.py

# This will:
# 1. Load first image from input/
# 2. Run AI segmentation (FlexiMo)
# 3. Encrypt ROI with quantum (NEQR)
# 4. Encrypt background with AES-256-GCM
# 5. Decrypt and verify
# 6. Compare SSIM

# Output directories:
# output/encrypted/     - Encrypted images
# output/metadata/      - Encryption metadata
# output/decrypted/     - Decrypted images
# output/analysis/      - SSIM comparison results
# logs/                 - Detailed logs
```

---

## Different Modes Explained

### Full Pipeline (Default)

```bash
# Encrypt → Decrypt → Verify in one command
python main.py

# Or explicitly:
python main.py --mode full
```

**What it does:**
1. Loads first image from `input/`
2. AI segmentation (identifies ROI)
3. Quantum encryption of ROI blocks
4. Classical encryption of background
5. Decryption
6. Similarity verification (SSIM)

---

### Encryption Only

```bash
# Encrypt a specific image
python main.py --mode encrypt --input input/satellite_image.png

# Output:
# - output/encrypted/satellite_image_encrypted.png
# - output/metadata/satellite_image_metadata.json
# - logs/encryption_TIMESTAMP.log
```

**Metadata contains:**
- Encryption parameters
- Session nonce for forward secrecy
- Kyber768 ciphertext (wrapped key)
- Dilithium3 signature

---

### Decryption Only

```bash
# Decrypt using metadata file
python main.py --mode decrypt --metadata output/metadata/satellite_image_metadata.json

# Or auto-find metadata:
python main.py --mode decrypt

# Output:
# - output/decrypted/satellite_image_decrypted.png
# - logs/decryption_TIMESTAMP.log
```

**Requires:**
- Metadata JSON file (contains encryption params)
- Private keys in `keys/` directory
- Matching ENCRYPTION_PASSPHRASE in `.env`

---

### Analysis Only

```bash
# Analyze image without encryption
python main.py --mode analyze --input input/satellite_image.png

# Output:
# - output/analysis/satellite_image_analysis.json
# - output/analysis/satellite_image_segmentation.png
# - output/analysis/satellite_image_roi_mask.png
```

**Shows:**
- AI segmentation results
- ROI identification
- Block division
- Statistics

---

### Verification Only

```bash
# Compare original vs decrypted (SSIM)
python main.py --mode verify \
  --original input/satellite_image.png \
  --decrypted output/decrypted/satellite_image_decrypted.png

# Or auto-find decrypted:
python main.py --mode verify --original input/satellite_image.png

# Output:
# - SSIM score (should be > 0.95)
# - MSE (mean squared error)
# - Verification report
```

---

## Example Workflows

### Workflow 1: Quick Test

```bash
# 1. Verify setup
python main.py --help

# 2. Analyze an image (non-destructive)
python main.py --mode analyze --input input/test_image.png

# 3. Full encrypt-decrypt-verify cycle
python main.py --mode full
```

### Workflow 2: Encryption Only (Save Encrypted Data)

```bash
# 1. Encrypt image
python main.py --mode encrypt --input input/satellite.tif

# 2. Save metadata securely (in production, use encrypted storage)
cp output/metadata/* /secure/storage/

# 3. Save encrypted image
cp output/encrypted/* /secure/storage/
```

### Workflow 3: Distributed Encryption/Decryption

**Sender (has private keys for encryption):**
```bash
# Encrypt and save metadata
python main.py --mode encrypt --input satellite.png
# Sends: encrypted image + metadata to receiver
```

**Receiver (has different private keys for decryption):**
```bash
# Copy metadata from sender
cp sender_satellite_metadata.json output/metadata/

# Decrypt
python main.py --mode decrypt --metadata output/metadata/sender_satellite_metadata.json
# Result: decrypted image in output/decrypted/
```

### Workflow 4: Batch Processing

```bash
# Encrypt multiple images
for img in input/*.png; do
    python main.py --mode encrypt --input "$img"
done

# Verify all
for meta in output/metadata/*_metadata.json; do
    python main.py --mode decrypt --metadata "$meta"
done

# Verify all
for decrypted in output/decrypted/*.png; do
    original="${decrypted/decrypted/input}"
    python main.py --mode verify --original "$original" --decrypted "$decrypted"
done
```

---

## Troubleshooting

### Issue: "Module not found: qiskit"

**Cause:** Dependencies not installed

**Fix:**
```bash
pip install -r requirements.txt
# Or specific package:
pip install qiskit qiskit-aer
```

---

### Issue: "ImportError: liboqs-python not found"

**Cause:** Post-quantum cryptography library not installed

**Fix:**
```bash
# Install liboqs-python
pip install liboqs-python

# Verify installation
python -c "from oqs import KeyEncapsulation; print('✓ OK')"
```

---

### Issue: "ENCRYPTION_PASSPHRASE not found"

**Cause:** `.env` file not set up

**Fix:**
```bash
# 1. Check .env exists
ls -la .env

# 2. Check it contains the variable
cat .env | grep ENCRYPTION_PASSPHRASE

# 3. If missing, create it:
cp .env.example .env

# 4. Edit with your passphrase
nano .env
```

---

### Issue: "Repository not found at repos/fleximo_repo"

**Cause:** External repositories not cloned

**Fix:**
```bash
# Clone the required repositories
git clone https://github.com/danfenghong/IEEE_TGRS_Fleximo repos/fleximo_repo
git clone https://github.com/ManavMNair/Quantum-image-encryption repos/quantum_repo

# Verify
ls -la repos/
```

---

### Issue: "File permission denied on config.json"

**Cause:** File permissions too restrictive

**Fix:**
```bash
# Linux/macOS
chmod 0o600 config/config.json
chmod 0o700 keys/

# Windows: Right-click → Properties → Security → Edit
# Or use Python:
python -c "from utils.security_manager import fix_all_permissions; import os; fix_all_permissions(os.getcwd())"
```

---

### Issue: "No images found in input/"

**Cause:** Test image not in input directory

**Fix:**
```bash
# Create test image
mkdir -p input

# Option 1: Copy your own image
cp /path/to/satellite_image.png input/

# Option 2: Download test image
# wget -O input/test_image.png https://example.com/satellite_image.png

# Option 3: Verify images exist
ls -la input/
```

---

### Issue: "SSIM score very low (< 0.95)"

**Cause:** Data loss during encryption/decryption

**Reason:** This is normal for compressed formats or lossy operations

**Note:** Even with perfect encryption, JPEG compression can reduce SSIM to 0.85-0.95

**Fix:**
- Use lossless formats: PNG, TIFF
- Check log files for warnings: `tail -50 logs/*.log`
- Verify key files weren't corrupted: Check file sizes match expected

---

### Issue: "Memory error - out of RAM"

**Cause:** Image too large or insufficient RAM

**Reason:** Quantum encryption process loads entire block structure in memory

**Fix:**
```bash
# Close other applications
# Or use a smaller image:
# pip install Pillow
python << 'EOF'
from PIL import Image
img = Image.open('input/large_image.tif')
img.resize((512, 512)).save('input/small_image.png')
EOF

# Run with smaller image
python main.py --input input/small_image.png
```

---

### Issue: "RuntimeError: No quantum backend available"

**Cause:** Qiskit AER simulator not installed

**Fix:**
```bash
pip install qiskit-aer
python -c "from qiskit_aer import AerSimulator; print('✓ AER ready')"
```

---

### Issue: "Assertion error: Config structure invalid"

**Cause:** `config.json` structure doesn't match template

**Fix:**
```bash
# Check config.json structure
python << 'EOF'
import json
with open('config/config.json') as f:
    config = json.load(f)
    
# Verify required sections exist
required = ['key_protection', 'post_quantum', 'metadata_signature']
for section in required:
    if section not in config:
        print(f"✗ Missing section: {section}")
    else:
        print(f"✓ {section} OK")
EOF

# If broken, restore from template
cp config/config.example.json config/config.json

# Then edit .env again to set placeholder values
```

---

## Project Structure

```
satellite-image-encryption/
│
├── main.py                          # Main entry point
├── requirements.txt                 # Python dependencies
├── setup_env.py                     # Setup utility (optional)
├── verify_env_setup.py              # Verification utility (optional)
│
├── config/
│   ├── config.example.json          # Template (commits to git)
│   ├── config.json                  # Instance (in .gitignore)
│   └── __init__.py
│
├── .env.example                     # Template (commits to git)
├── .env                             # Local secrets (in .gitignore)
├── .gitignore                       # Blocks .env and config.json
│
├── engines/
│   ├── ai_engine.py                 # FlexiMo AI segmentation
│   ├── quantum_engine.py            # NEQR quantum encryption
│   ├── classical_engine.py          # AES-256-GCM background
│   ├── fusion_engine.py             # Combine encrypted components
│   ├── decision_engine.py           # Mode dispatcher
│   ├── verification_engine.py       # SSIM comparison
│   └── quantum_worker.py            # Qiskit backend
│
├── workflows/
│   ├── encrypt_workflow.py          # Encryption pipeline
│   ├── decrypt_workflow.py          # Decryption pipeline
│   ├── analyze_workflow.py          # Analysis mode
│   └── verify_workflow.py           # Verification mode
│
├── utils/
│   ├── config_loader_secure.py      # .env file loader
│   ├── security_manager.py          # Permission enforcement
│   ├── logger.py                    # Logging setup
│   ├── crypto_utils.py              # Key derivation
│   ├── crypto_utils_pqc.py          # Post-quantum crypto
│   ├── image_utils.py               # Image processing
│   ├── block_utils.py               # Block operations
│   ├── block_analysis.py            # Block statistics
│   └── __init__.py
│
├── repos/
│   ├── fleximo_repo/                # External: AI segmentation
│   │   └── fleximo/
│   └── quantum_repo/                # External: Quantum encryption
│       └── quantum/
│
├── input/                           # Your images (add here)
├── output/
│   ├── encrypted/                   # Encrypted images
│   ├── decrypted/                   # Decrypted images
│   ├── metadata/                    # Encryption metadata
│   └── analysis/                    # Analysis results
│
├── keys/                            # Cryptographic keys (auto-created)
│   ├── recipient_kyber768_public.key
│   ├── recipient_kyber768_private.key
│   ├── sender_dilithium3_public.key
│   └── sender_dilithium3_private.key
│
├── logs/                            # Execution logs
│
├── SETUP_AND_RUN_GUIDE.md          # This file
├── README.md                        # Project overview
└── .env.md                          # .env file guide
```

---

## Quick Reference

### First Time Setup

```bash
# 1. Clone
git clone https://github.com/YOUR-USERNAME/satellite-image-encryption.git
cd satellite-image-encryption

# 2. Clone external repos
git clone https://github.com/danfenghong/IEEE_TGRS_Fleximo repos/fleximo_repo
git clone https://github.com/ManavMNair/Quantum-image-encryption repos/quantum_repo

# 3. Setup environment
cp .env.example .env
# Edit .env with your passphrase and key paths

# 4. Install
pip install -r requirements.txt

# 5. Generate keys
python << 'EOF'
import os
from liboqs.python import OQS
os.makedirs('keys', exist_ok=True)
kem = OQS.KeyEncapsulation("Kyber768")
public_key = kem.generate_keyset()
private_key = kem.export_secret_key()
with open('keys/recipient_kyber768_public.key', 'wb') as f:
    f.write(public_key)
with open('keys/recipient_kyber768_private.key', 'wb') as f:
    f.write(private_key)
sig = OQS.Signature("Dilithium3")
public_key = sig.generate_keyset()
private_key = sig.export_secret_key()
with open('keys/sender_dilithium3_public.key', 'wb') as f:
    f.write(public_key)
with open('keys/sender_dilithium3_private.key', 'wb') as f:
    f.write(private_key)
EOF

# 6. Test
python main.py --help
```

### Normal Usage

```bash
# Add your image
cp /path/to/satellite_image.png input/

# Run full pipeline
python main.py

# Or specific mode
python main.py --mode encrypt --input input/image.png
python main.py --mode decrypt --metadata output/metadata/image_metadata.json
python main.py --mode verify --original input/image.png
```

---

## Getting Help

- **Setup issues?** See [Troubleshooting](#troubleshooting)
- **Environment variables?** See [ENVIRONMENT_SETUP.md](ENVIRONMENT_SETUP.md)
- **Security details?** See [SECURITY_TESTING_GUIDE.md](SECURITY_TESTING_GUIDE.md)
- **How it works?** See [HOW_IT_WORKS_REAL_WORLD.md](HOW_IT_WORKS_REAL_WORLD.md)
- **Code issues?** Check logs: `tail -100 logs/*.log`

---

## Next Steps

1. ✅ Follow [Clone & Initial Setup](#clone--initial-setup)
2. ✅ Follow [Environment Configuration](#environment-configuration)
3. ✅ Follow [Install Dependencies](#install-dependencies)
4. ✅ Follow [Setup Encryption Keys](#setup-encryption-keys)
5. ✅ Follow [Running the System](#running-the-system)
6. ✅ Try an [Example Workflow](#example-workflows)

**You're ready to encrypt satellite images with post-quantum cryptography!** 🚀
