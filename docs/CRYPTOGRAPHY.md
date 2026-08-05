# Cryptography and Key Handling

## Vault

CyberForge stores provider credentials and local model-encryption keys as independent AES-256-GCM records. Each record has unique nonce material and associated data bound to its hashed logical identifier and data-key version.

The stable vault root key is wrapped using a password-derived key. Password derivation uses Argon2id. A platform device key may assist local unlock where the host secure store supports it. The Flutter UI never persists provider secrets and stores only a short-lived bearer session in platform secure storage.

## Key hierarchy

```text
Password + Argon2id ─┐
Platform device key ─┴─> wrapped vault root key
                              │
                              ├─> encrypted index key
                              ├─> encrypted data-key ring
                              └─> model-encryption key record
                                         │
                                         └─> AES-GCM encrypted model file
```

Data-key rotation decrypts and re-encrypts records transactionally under a new active key. Old in-memory key buffers are overwritten on lock or successful rotation where the language runtime permits.

## Model storage

A model download is streamed to a temporary file, hashed with SHA-256, compared in constant time to the pinned digest, encrypted with AES-256-GCM, and then deleted. Loading reverses the process into a restrictive temporary file, checks the digest again, starts the runtime, and deletes or overwrites the temporary file when unloaded.

Disk overwrite cannot be guaranteed on copy-on-write filesystems or SSD wear-leveling. Full-disk encryption remains strongly recommended.

## Post-quantum recovery

When `liboqs-python` and a supported liboqs build are present, CyberForge can create a hybrid recovery identity using ML-KEM and X25519, derive a content key through HKDF, and encrypt the payload with AES-256-GCM. The encrypted private recovery material is protected with Argon2id and AES-GCM.

Post-quantum recovery does not replace TLS, operating-system hardening, device encryption, access control, or provider-side security. Keep the encrypted private recovery kit separate from the live device.

## Non-goals

- AES-GCM record encryption is not SQLite page encryption.
- Side-channel jitter is not a formal constant-time guarantee.
- Memory zeroization in managed runtimes is best effort.
- PQ algorithms protect recovery material; they do not make a compromised endpoint safe.
