from pathlib import Path

from cyberforge_sidecar.crypto import aes_gcm_decrypt, aes_gcm_encrypt, decrypt_file_aes_gcm, encrypt_file_aes_gcm


def test_aes_gcm_authenticates_bytes():
    key = bytes(range(32))
    aad = b"cyberforge-test"
    envelope = aes_gcm_encrypt(b"sensitive packet", key, aad)
    assert aes_gcm_decrypt(envelope, key, aad) == b"sensitive packet"


def test_stream_roundtrip(tmp_path: Path):
    key = bytes(reversed(range(32)))
    clear = tmp_path / "clear.bin"
    encrypted = tmp_path / "encrypted.cfg"
    restored = tmp_path / "restored.bin"
    clear.write_bytes((b"cyberforge" * 100_000) + b"end")
    encrypt_file_aes_gcm(clear, encrypted, key)
    decrypt_file_aes_gcm(encrypted, restored, key)
    assert restored.read_bytes() == clear.read_bytes()
