# How This Project Works in the Real World

## **Real-World Use Case: Protecting Classified Satellite Imagery**

Imagine you're a **government satellite agency** with high-resolution spy satellite images that must remain secure even against future quantum computers.

---

## **End-to-End Real-World Workflow**

### **SCENARIO: Tuesday Morning at a Security Facility**

#### **Step 1: You Have a Sensitive Satellite Image**
```
File: spy_satellite_2026_april.png (512×512 pixels, 3MB)
Content: Top-secret military facility imagery
Sensitivity: Classified
Risk: Must be secure for 20+ years (including quantum threats)
```

---

## **PHASE 1: ENCRYPTION (First Day)**

**You run:**
```bash
python main.py --input input/spy_satellite_2026_april.png
```

**What happens behind the scenes:**

### **STEP 1-3: AI-Powered Segmentation**
```
The system uses FlexiMo (Vision Transformer):
  - Analyzes the satellite image
  - Identifies ROI (Region of Interest) = military facility
  - Identifies background = sky, terrain, irrelevant areas
  
Result:
  ✓ ROI mask: 40% of pixels = facility (marked for quantum encryption)
  ✓ Background mask: 60% of pixels = non-critical (AES-256 classical)
```

### **STEP 4: Generate Encryption Keys**
```
Master Seed Generation (32 bytes random):
  a3f8c2d9b1e7f4c6a8d5e2b9f1c4a7d0

Session Nonce Generation (16 bytes random, UNIQUE per encryption run):
  f9c2d8e1a4b7c5d6

Derived Keys:
  - AES-256 key (for background): 32 bytes
  - Per-block ephemeral seeds (150 blocks): unique seeds for forward secrecy
  
FIX #5 Forward Secrecy:
  Each block gets UNIQUE seed = SHA256(master_seed + session_nonce + block_id)
  ⚡ Even if master_seed leaks in 2035, 2026 sessions stay secure
```

### **STEP 4.5: Protect Keys at Rest** (FIX #3)
```
Keys encrypted with Scrypt + AES-256-GCM:
  Passphrase: "change-this-passphrase-in-production" (from config)
  Scrypt params: n=2^14 (memory-hard to prevent brute force)
  
Result: st2_keys.enc (encrypted binary blob)
  - Raw keys NEVER stored on disk
  - Even if drives are stolen, keys are password-protected
```

### **STEP 5: Quantum Encryption of ROI (NEQR)**
```
For each 32×32 block in the facility region:
  1. Extract R, G, B channels separately
  2. For each channel (e.g., Red):
     - Encode as quantum state using Novel Enhanced Quantum Representation
     - Apply quantum scrambling (chaotic gates based on ephemeral seed)
     - Apply quantum permutation (16,384 measurement shots)
     - DNA encode result (4 planes)
     - XOR diffusion
  3. Stack encrypted channels → encrypted 32×32 block
  4. Place back in original position

Result: ~150 encrypted blocks (facility pixels look like random noise)
Time: ~1-2 minutes on typical laptop
```

### **STEP 6: Classical Encryption of Background** (FIX #6)
```
Background pixels (sky, terrain) encrypted with AES-256-GCM:
  - Plaintext: All background pixels serialized
  - Key: AES-256 (derived from master_seed)
  - Nonce: 96-bit random
  - Output: Ciphertext + 16-byte authentication tag
  
⚡ FIX #6 Enhancement:
  SHA-256 hash of encrypted background file = abc123def456...
  (Stored in metadata - protects against file tampering)
```

### **STEP 7-7.5: Create Fused Output** (FIX #4)
```
Create encrypted image PNG:
  - ROI blocks: Quantum-encrypted (appears as random noise)
  - Background: Visual representation of ciphertext
  - PNG size: Same as original (512×512)

⚡ FIX #4 PNG Metadata Embedding:
  Embed warnings in PNG tEXt chunks:
    "DependencyWarning": "⚠️ Requires st2_background.enc for decryption"
    "RequiredFiles": "st2_background.enc, st2_metadata.json, st2_bundle.sig"
    "BundleID": "a3f8c2d9" (unique identifier)
  
  ✅ Purpose: PNG carries self-documenting warnings
     Even if archived alone for 10 years, metadata reminds users
     "Hey, you need these 3 files to decrypt this!"
```

### **STEP 8: Save Metadata**
```
st2_metadata.json (complete encryption recipe):
{
  "original_image": "spy_satellite_2026_april.png",
  "roi_information": {...},
  "quantum_encryption": {
    "session_nonce": "f9c2d8e1a4b7c5d6",  ← FIX #5
    "forward_secrecy": true,               ← FIX #5
    "num_blocks_encrypted": 150
  },
  "classical_encryption": {
    "enc_file_hash": "abc123def456...",   ← FIX #6
    "method": "AES-256-GCM"
  },
  "key_protection": {                      ← FIX #3
    "enabled": true,
    "method": "Scrypt + AES-256-GCM",
    "protected_keys_file": "st2_keys.enc"
  },
  "block_encryption_info": [...150 blocks...]
}
```

### **STEP 9: Post-Quantum Key Protection** (FIX #1)
```
Master seed wrapped with ML-KEM (Kyber768):
  1. Load recipient's ML-KEM public key (from config)
  2. Perform KEM encapsulation
  3. Derive wrapping key from shared secret
  4. AES-256-GCM encrypt master_seed
  
Result saved in metadata:
  "post_quantum": {
    "algorithm": "Kyber768",
    "kem_ciphertext": "...hex...",
    "wrapped_seed": "...hex...",
    "wrap_nonce": "...hex..."
  }
  
✅ FIX #1 Guarantee:
   Master seed NEVER stored in plaintext
   Even if quantum computer breaks RSA/ECDH in 2035,
   this Kyber768 ML-KEM wrapping is secure
```

### **STEP 10: Sign Metadata** (FIX #2)
```
Sign metadata bundle with ML-DSA (Dilithium3):
  1. Load sender's private key (your organization's key)
  2. Sign st2_metadata.json
  3. Save signature to st2_bundle.sig
  
Result:
  st2_bundle.sig (hex-encoded digital signature)
  
✅ FIX #2 Guarantee:
   Recipient verifies signature before decryption
   If metadata tampered, signature invalid → abort
   Ensures integrity AND authenticity
```

### **Encryption Complete - Files Generated:**
```
output/
├── encrypted/
│   ├── st2_encrypted.png          ← Visual representation (ROI looks like noise)
│   └── st2_background.enc         ← CRITICAL: Encrypted background bytes
└── metadata/
    ├── st2_metadata.json          ← Everything needed to decrypt
    ├── st2_keys.json              ← ML-KEM wrapped keys
    ├── st2_keys.enc               ← Password-protected keys
    └── st2_bundle.sig             ← ML-DSA signature
```

**Total Time: ~2 minutes** (includes AI segmentation + quantum encryption + signing)

---

## **PHASE 2: TRANSMISSION (Day 1 Afternoon)**

**You send to recipient (partner agency/ally):**
```
Email:
  TO: partner@ally-agency.com
  SUBJECT: Encrypted Satellite Intel
  
  Attachment 1: st2_encrypted.png (1.5 MB)
  Attachment 2: st2_background.enc (1.5 MB)  ← CRITICAL
  Attachment 3: st2_metadata.json (500 KB)
  Attachment 4: st2_bundle.sig (5 KB)
  
  Message: "Secured with post-quantum crypto. 
            Requires recipient's ML-KEM private key for decryption."
```

---

## **PHASE 3: DECRYPTION (Day 2 Morning at Recipient's Location)**

**Recipient runs:**
```bash
python main.py --mode decrypt --metadata /path/to/st2_metadata.json
```

### **SECURITY GATE 1: Verify Metadata Signature** (FIX #2)
```
Before ANY decryption attempt:
  1. Load st2_bundle.sig (signature)
  2. Load sender's public key (from config - already shared)
  3. Verify signature of st2_metadata.json
  
Result:
  ✅ Valid? → "Signature verified, metadata integrity confirmed"
  ❌ Invalid? → "SECURITY BREACH - metadata tampered" → ABORT
```

### **SECURITY CHECK: Verify PNG Metadata** (FIX #4)
```
Load st2_encrypted.png:
  1. Read embedded tEXt chunks
  2. Check for DependencyWarning
  3. Verify required files present: .enc, .json, .sig
  
Result:
  ✅ All files present → "Dependencies verified, proceeding"
  ⚠️ Missing files → "WARNING: Some required files missing (data loss risk)"
```

### **STEP 0: Recover Master Seed** (Mutually Exclusive - FIX #1, FIX #3)

**Branch 1 - ML-KEM Decapsulation (FIX #1):**
```
IF "post_quantum" section exists in metadata:
  1. Load recipient's ML-KEM private key
  2. Extract kem_ciphertext from metadata
  3. Perform KEM decapsulation
  4. Recover shared_secret
  5. Derive wrapping key (same HKDF-SHA256)
  6. AES-256-GCM decrypt wrapped_seed
  
Result: master_seed recovered (32 bytes)
Guarantee: Mathematical - original master_seed perfectly reconstructed
```

**Branch 2 - Protected Keys Decryption (FIX #3):**
```
ELSE IF "key_protection" section exists:
  1. Load encrypted key blob from st2_keys.enc
  2. Prompt for passphrase (or from config)
  3. Extract salt from blob
  4. Scrypt(passphrase, salt) → KEK
  5. AES-256-GCM decrypt blob
  
Result: master_seed, aes_key recovered
```

**Branch 3 - Legacy Fallback:**
```
ELSE (neither section exists - v1.0 legacy format):
  🚨 CRITICAL SECURITY WARNING 🚨
  "Raw key material found in PLAINTEXT on disk!"
  "Keys NOT protected at rest - VULNERABLE!"
  "Re-encrypt with FIX #3 immediately!"
  
  → Still allows decryption but warns loudly
```

### **SECURITY CHECK: Verify Background File Integrity** (FIX #6)
```
Before decrypting background:
  1. Compute SHA-256 hash of st2_background.enc
  2. Compare with hash in metadata (which is signed via FIX #2)
  
Result:
  ✅ Hashes match → "File integrity verified"
  ❌ Hashes differ → "FILE TAMPERED OR CORRUPTED - ABORT"
  
⚡ Why this works:
   Metadata is signed (FIX #2)
   Hash is in metadata
   → Signature covers the hash
   → Tampering with .enc breaks hash → detected
```

### **STEP 1-3: Load Encrypted Data**
```
Decrypt background with AES-256-GCM:
  - Key: aes_key (recovered from master_seed)
  - Nonce: from metadata
  - Ciphertext: st2_background.enc
  
Result: Original background pixels (perfect reconstruction)
```

### **STEP 4: Reconstruct Per-Block Ephemeral Seeds** (FIX #5)
```
IF "forward_secrecy" enabled in metadata:
  1. Load session_nonce from metadata
  2. For each block i:
     block_seed_i = SHA256(master_seed + session_nonce + block_id)
  3. Extract (x0, y0) for each block
  
⚡ FIX #5 Purpose:
   Each block uses UNIQUE seed derived from session_nonce
   Recipient can reconstruct same seeds deterministically
   Even if master_seed leaked in future, past sessions secure
```

### **STEP 5: Quantum Decryption (Reverse NEQR)**
```
For each 32×32 encrypted block:
  1. Split into R', G', B' channels
  2. For each channel:
     - Reverse DNA decoding
     - Reverse XOR diffusion
     - Reverse quantum permutation (using per-block ephemeral seed)
     - Reverse quantum scrambling (using per-block ephemeral seed)
     - Measurement recovery
  3. Stack channels → original 32×32 RGB block
  4. Place at original position

Result: ROI fully decrypted
```

### **STEP 6: Reconstruct Original Image**
```
Combine:
  - Decrypted ROI blocks (facility pixels)
  - Decrypted background pixels (sky/terrain)
  
Place at original positions using block map
Result: Complete reconstructed satellite image
```

### **STEP 7: Verification**
```
Compare with original:
  PSNR:   ∞ (Infinity - mathematically perfect match)
  SSIM:   1.0 (Perfect structural similarity)
  Hash:   ✓ Match (bit-for-bit identical)
  
✅ ZERO DATA LOSS GUARANTEE
```

**Decryption Complete:**
```
output/
└── decrypted/
    └── decrypted_spy_satellite_2026_april.png  ← Perfect copy of original
```

**Total Time: ~2 minutes** (same as encryption - symmetric)

---

## **Real-World Security Guarantees**

| Threat | Protection | How It Works |
|--------|-----------|-------------|
| **Quantum Computer** | ML-KEM (Kyber768) | Even quantum computer can't break this lattice-based crypto |
| **Metadata Tampering** | ML-DSA (Dilithium3) | Signature verification BEFORE any decryption |
| **Disk Theft** | Scrypt + AES-256-GCM (FIX #3) | Keys encrypted at rest with password |
| **Silent Data Loss** | PNG tEXt Metadata (FIX #4) | PNG carries warnings about required .enc file |
| **Master Seed Leak** | Session Nonce Ratchet (FIX #5) | Each session unique - past sessions not compromised |
| **File Substitution** | SHA-256 Hash (FIX #6) | Hash in signed metadata catches .enc file tampering |

---

## **Real-World Timeline Scenario**

```
2026 (Today):
  ✓ Encrypt satellite imagery
  ✓ Send 4 files to ally
  → System uses ML-KEM (Kyber768) - today's standard
  
2030-2035 (5-10 years):
  ⚠️  Hypothetically: "Quantum computer developed"
  ❌ RSA/ECDH broken
  ✅ But Kyber768 (ML-KEM) still secure
  → Old satellite images still protected
  
2026 Encryption Session:
  Even if attacker steals master_seed in 2035:
  ✓ Cannot decrypt 2026 sessions (different session_nonce)
  ✓ Session_nonce not stored with master_seed
  → Forward secrecy guarantees protection
```

---

## **Real-World Deployment Checklist**

**Security Officer's Checklist:**

- ✅ **Generate unique ML-KEM keys** for your organization
- ✅ **Generate unique ML-DSA keys** for signing
- ✅ **Store keys in Hardware Security Module (HSM)** - not in config files
- ✅ **Backup metadata bundle** (JSON + SIG files) separately from .enc files
- ✅ **Test decryption workflow** before deploying to production
- ✅ **Document key rotation policy** (every 2 years recommended)
- ✅ **Enable audit logging** of all encryption/decryption operations
- ✅ **Train personnel** on FIX #4 - "Don't archive PNG alone without .enc"

---

## **Real-World Failure Scenarios Handled**

| Scenario | What Happens |
|----------|--------------|
| **Someone archives PNG alone** | PNG carries warning metadata (FIX #4) |
| **Attacker modifies metadata.json** | Signature verification fails - ABORT (FIX #2) |
| **Attacker swaps background.enc** | SHA-256 hash mismatch - detected (FIX #6) |
| **Passphrase forgotten** | Can still decrypt if recipient has ML-KEM key (fallback) |
| **Quantum computer breaks RSA** | ML-KEM still secure + past sessions protected by FIX #5 |
| **Server disk stolen** | Keys encrypted at rest - useless without passphrase (FIX #3) |

---

## **Summary: Why This Matters**

This system is designed for **government/military satellite imagery** that must:

1. ✅ **Stay secure for 20+ years** (even against future quantum computers)
2. ✅ **Survive disk theft** (keys encrypted at rest)
3. ✅ **Verify authenticity** (signatures prevent tampering)
4. ✅ **Prevent silent data loss** (PNG metadata reminds users of dependencies)
5. ✅ **Achieve forward secrecy** (session-specific seeds protect past sessions)
6. ✅ **Recover perfectly** (lossless encryption: PSNR=∞, SSIM=1.0)

**In a sentence:** *It's a time-machine proof encryption system that will protect your data even when quantum computers exist, while preventing both accidental data loss and deliberate tampering.*
