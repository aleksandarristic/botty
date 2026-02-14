
from types import SimpleNamespace

from botty.config import BottyConfig


def test_config_defaults(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("AUTHORIZED_USER_ID", raising=False)
    monkeypatch.delenv("AUTHORIZED_CHAT_ID", raising=False)
    monkeypatch.delenv("BOTTY_SERVICE_ALLOWLIST", raising=False)
    monkeypatch.delenv("GOHOME_API_URL", raising=False)
    monkeypatch.delenv("GOHOME_TIMEOUT_SECONDS", raising=False)
    monkeypatch.delenv("EMBY_DATA_PATH", raising=False)
    monkeypatch.delenv("MEDIA_PATH", raising=False)
    monkeypatch.delenv("TOTP_SECRET", raising=False)
    monkeypatch.delenv("TOTP_WINDOW_STEPS", raising=False)

    config = BottyConfig.from_env()

    assert config.telegram_bot_token is None
    assert config.authorized_user_ids == []
    assert config.authorized_chat_ids == []
    assert config.service_allowlist == []
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
    monkeypatch.setenv("AUTHORIZED_CHAT_ID", "-100111,-100222")
    monkeypatch.setenv("BOTTY_SERVICE_ALLOWLIST", "botty,nginx")
    monkeypatch.setenv("GOHOME_API_URL", "http://example.local/status")
    monkeypatch.setenv("GOHOME_TIMEOUT_SECONDS", "4.5")
    monkeypatch.setenv("EMBY_DATA_PATH", "/data/emby")
    monkeypatch.setenv("MEDIA_PATH", "/data/media")
    monkeypatch.setenv("TOTP_SECRET", "JBSWY3DPEHPK3PXP")
    monkeypatch.setenv("TOTP_WINDOW_STEPS", "2")

    config = BottyConfig.from_env()

    assert config.telegram_bot_token == "token"
    assert config.authorized_user_ids == ["999"]
    assert config.authorized_chat_ids == ["-100111", "-100222"]
    assert config.service_allowlist == ["botty", "nginx"]
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


def test_config_parses_authorized_chats(monkeypatch):
    monkeypatch.setenv("AUTHORIZED_CHAT_ID", "-1001, -1002")

    config = BottyConfig.from_env()

    assert config.authorized_chat_ids == ["-1001", "-1002"]


def test_config_parses_service_allowlist(monkeypatch):
    monkeypatch.setenv("BOTTY_SERVICE_ALLOWLIST", "botty, nginx")

    config = BottyConfig.from_env()

    assert config.service_allowlist == ["botty", "nginx"]


def test_is_authorized_private_chat_requires_authorized_user():
    config = BottyConfig(
        telegram_bot_token="token",
        authorized_user_ids=["123"],
        authorized_chat_ids=[],
        service_allowlist=[],
        enabled_commands=None,
        gohome_api_url="http://localhost:8080/status",
        gohome_timeout_seconds=10.0,
        emby_data_path="/mnt/embydata",
        media_path="/mnt/media",
    )
    update = SimpleNamespace(
        effective_user=SimpleNamespace(id=123),
        effective_chat=SimpleNamespace(id=111, type="private"),
    )

    assert config.is_authorized(update) is True


def test_is_authorized_group_chat_requires_chat_allowlist():
    config = BottyConfig(
        telegram_bot_token="token",
        authorized_user_ids=["123"],
        authorized_chat_ids=["-1001"],
        service_allowlist=[],
        enabled_commands=None,
        gohome_api_url="http://localhost:8080/status",
        gohome_timeout_seconds=10.0,
        emby_data_path="/mnt/embydata",
        media_path="/mnt/media",
    )
    allowed_update = SimpleNamespace(
        effective_user=SimpleNamespace(id=123),
        effective_chat=SimpleNamespace(id=-1001, type="group"),
    )
    denied_update = SimpleNamespace(
        effective_user=SimpleNamespace(id=123),
        effective_chat=SimpleNamespace(id=-1002, type="group"),
    )

    assert config.is_authorized(allowed_update) is True
    assert config.is_authorized(denied_update) is False


def test_is_authorized_group_chat_denied_when_allowlist_empty():
    config = BottyConfig(
        telegram_bot_token="token",
        authorized_user_ids=["123"],
        authorized_chat_ids=[],
        service_allowlist=[],
        enabled_commands=None,
        gohome_api_url="http://localhost:8080/status",
        gohome_timeout_seconds=10.0,
        emby_data_path="/mnt/embydata",
        media_path="/mnt/media",
    )
    update = SimpleNamespace(
        effective_user=SimpleNamespace(id=123),
        effective_chat=SimpleNamespace(id=-1002, type="group"),
    )

    assert config.is_authorized(update) is False


def test_is_service_allowed_normalizes_service_suffix():
    config = BottyConfig(
        telegram_bot_token="token",
        authorized_user_ids=["123"],
        authorized_chat_ids=[],
        service_allowlist=["botty", "nginx.service"],
        enabled_commands=None,
        gohome_api_url="http://localhost:8080/status",
        gohome_timeout_seconds=10.0,
        emby_data_path="/mnt/embydata",
        media_path="/mnt/media",
    )

    assert config.is_service_allowed("botty.service") is True
    assert config.is_service_allowed("nginx") is True
    assert config.is_service_allowed("ssh") is False


def test_is_service_allowed_false_when_allowlist_empty():
    config = BottyConfig(
        telegram_bot_token="token",
        authorized_user_ids=["123"],
        authorized_chat_ids=[],
        service_allowlist=[],
        enabled_commands=None,
        gohome_api_url="http://localhost:8080/status",
        gohome_timeout_seconds=10.0,
        emby_data_path="/mnt/embydata",
        media_path="/mnt/media",
    )

    assert config.is_service_allowed("botty") is False
