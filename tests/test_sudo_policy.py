from botty.config import BottyConfig
from botty.sudo_policy import build_startup_sudoers_guidance


def _config(enabled_commands, service_allowlist):
    return BottyConfig(
        telegram_bot_token="token",
        authorized_user_ids=["123"],
        authorized_chat_ids=[],
        service_allowlist=service_allowlist,
        enabled_commands=enabled_commands,
        gohome_api_url="http://localhost:8080/status",
        gohome_timeout_seconds=10.0,
        emby_data_path="/mnt/embydata",
        media_path="/mnt/media",
        telegram_poll_timeout_seconds=300.0,
        totp_secret="JBSWY3DPEHPK3PXP",
        totp_window_steps=1,
    )


def test_guidance_reports_no_sudoers_needed_when_no_privileged_commands_enabled():
    config = _config(enabled_commands=["status"], service_allowlist=["nginx"])

    lines = build_startup_sudoers_guidance(config, runtime_user="alice")
    joined = "\n".join(lines)

    assert "Sudo/TOTP matrix for runtime user 'alice':" in joined
    assert "No sudoers additions currently required" in joined
    assert "Cmnd_Alias" not in joined


def test_guidance_builds_aliases_for_service_logs_reboot_and_restart_paths():
    config = _config(
        enabled_commands=["service", "logs", "restartbot", "reboot", "upgrade_bot"],
        service_allowlist=["nginx", "botty"],
    )

    lines = build_startup_sudoers_guidance(config, runtime_user="alice")
    joined = "\n".join(lines)

    assert "Cmnd_Alias BOTTY_SYSTEMCTL =" in joined
    assert "/usr/bin/systemctl restart botty" in joined
    assert "/usr/bin/systemctl start nginx" in joined
    assert "Cmnd_Alias BOTTY_LOGS =" in joined
    assert "/usr/bin/journalctl -u nginx -n 20 --no-pager" in joined
    assert "Cmnd_Alias BOTTY_REBOOT =" in joined
    assert "alice ALL=(root) NOPASSWD: BOTTY_SYSTEMCTL, BOTTY_LOGS, BOTTY_REBOOT" in joined


def test_guidance_warns_when_service_allowlist_is_missing():
    config = _config(
        enabled_commands=["service", "logs", "restartbot"],
        service_allowlist=[],
    )

    lines = build_startup_sudoers_guidance(config, runtime_user="alice")
    joined = "\n".join(lines)

    assert "Warning: service enabled but BOTTY_SERVICE_ALLOWLIST is empty" in joined
    assert "Warning: logs enabled but BOTTY_SERVICE_ALLOWLIST is empty" in joined
    assert "Warning: restartbot enabled but 'botty' is not in BOTTY_SERVICE_ALLOWLIST" in joined
