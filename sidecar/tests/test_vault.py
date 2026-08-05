from pathlib import Path

from cyberforge_sidecar.config import SETTINGS
from cyberforge_sidecar.vault import SecureVault


def test_vault_roundtrip_and_data_key_rotation(tmp_path: Path):
    original = SETTINGS.data_dir
    object.__setattr__(SETTINGS, "data_dir", tmp_path)
    try:
        vault = SecureVault()
        token = vault.create("correct horse battery staple")
        vault.set_secret(token, "xai", "synthetic-test-key")
        assert vault.get_secret("xai") == "synthetic-test-key"
        first_key_id = vault.status().active_data_key_id
        second_key_id = vault.rotate_data_key(token)
        assert second_key_id != first_key_id
        vault.lock()
        token = vault.unlock("correct horse battery staple")
        vault.validate_session(token)
        assert vault.get_secret("xai") == "synthetic-test-key"
    finally:
        object.__setattr__(SETTINGS, "data_dir", original)
