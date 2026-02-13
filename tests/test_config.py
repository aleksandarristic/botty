
from botty.config import BottyConfig


def test_config_defaults(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("AUTHORIZED_USER_ID", raising=False)
    monkeypatch.delenv("GOHOME_API_URL", raising=False)
    monkeypatch.delenv("GOHOME_TIMEOUT_SECONDS", raising=False)
    monkeypatch.delenv("EMBY_DATA_PATH", raising=False)
    monkeypatch.delenv("MEDIA_PATH", raising=False)
    monkeypatch.delenv("TOTP_SECRET", raising=False)
    monkeypatch.delenv("TOTP_WINDOW_STEPS", raising=False)

    config = BottyConfig.from_env()

    assert config.telegram_bot_token is None
    assert config.authorized_user_ids == []
    assert config.gohome_api_url == "http://localhost:8080/status"
    assert config.gohome_timeout_seconds == 10
    assert config.emby_data_path == "/mnt/embydata"
    assert config.media_path == "/mnt/media"
    assert config.totp_secret is None
    assert config.totp_window_steps == 1


def test_config_parses_authorized_users(monkeypatch):
    monkeypatch.setenv("AUTHORIZED_USER_ID", "123, 456,789")

    config = BottyConfig.from_env()

    assert config.authorized_user_ids == ["123", "456", "789"]


def test_config_custom_values(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setenv("AUTHORIZED_USER_ID", "999")
    monkeypatch.setenv("GOHOME_API_URL", "http://example.local/status")
    monkeypatch.setenv("GOHOME_TIMEOUT_SECONDS", "4.5")
    monkeypatch.setenv("EMBY_DATA_PATH", "/data/emby")
    monkeypatch.setenv("MEDIA_PATH", "/data/media")
    monkeypatch.setenv("TOTP_SECRET", "JBSWY3DPEHPK3PXP")
    monkeypatch.setenv("TOTP_WINDOW_STEPS", "2")

    config = BottyConfig.from_env()

    assert config.telegram_bot_token == "token"
    assert config.authorized_user_ids == ["999"]
    assert config.gohome_api_url == "http://example.local/status"
    assert config.gohome_timeout_seconds == 4.5
    assert config.emby_data_path == "/data/emby"
    assert config.media_path == "/data/media"
    assert config.totp_secret == "JBSWY3DPEHPK3PXP"
    assert config.totp_window_steps == 2


def test_config_enabled_commands_unset_means_all(monkeypatch):
    monkeypatch.delenv("ENABLED_COMMANDS", raising=False)

    config = BottyConfig.from_env()

    assert config.enabled_commands is None


def test_config_enabled_commands_empty_means_all(monkeypatch):
    monkeypatch.setenv("ENABLED_COMMANDS", "")

    config = BottyConfig.from_env()

    assert config.enabled_commands is None


def test_config_enabled_commands_parsed_list(monkeypatch):
    monkeypatch.setenv("ENABLED_COMMANDS", "status, logs, ping")

    config = BottyConfig.from_env()

    assert config.enabled_commands == ["status", "logs", "ping"]
