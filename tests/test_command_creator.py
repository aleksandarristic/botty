import argparse
import json
from pathlib import Path

import pytest

from botty.command_creator import (
    _collect_interactive_inputs,
    _parse_json_commands,
    get_commands_json_schema,
    main,
    scaffold_command,
)


def _make_project(tmp_path: Path) -> Path:
    project_root = tmp_path / "project"
    handlers_root = project_root / "src/botty/cmd/handlers"
    handlers_root.mkdir(parents=True)
    (handlers_root / "__init__.py").write_text("# handlers package\n", encoding="utf-8")
    return project_root


def test_scaffold_command_creates_package_without_registry_edit(tmp_path):
    project_root = _make_project(tmp_path)

    result = scaffold_command(
        project_root=project_root,
        command_name="hello_world",
        description="Hello world command",
    )

    command_file = Path(result["command_file"])
    package_init = Path(result["package_init"])
    handlers_init = project_root / "src/botty/cmd/handlers/__init__.py"

    assert command_file.exists()
    assert package_init.exists()
    assert result["class_name"] == "HelloWorldCommand"
    assert result["command_name"] == "hello_world"

    command_source = command_file.read_text(encoding="utf-8")
    assert 'name = "hello_world"' in command_source
    assert 'description = "Hello world command"' in command_source
    assert "class HelloWorldCommand(Command):" in command_source

    package_init_source = package_init.read_text(encoding="utf-8")
    assert "from .command import HelloWorldCommand as HelloWorldCommand" in package_init_source
    assert '__all__ = ["HelloWorldCommand"]' in package_init_source

    assert handlers_init.read_text(encoding="utf-8") == "# handlers package\n"


def test_scaffold_command_requires_force_when_command_exists(tmp_path):
    project_root = _make_project(tmp_path)

    scaffold_command(
        project_root=project_root,
        command_name="hello",
        description="hello command",
    )
    with pytest.raises(FileExistsError):
        scaffold_command(
            project_root=project_root,
            command_name="hello",
            description="hello command",
        )


def test_scaffold_command_applies_custom_class_suffix(tmp_path):
    project_root = _make_project(tmp_path)

    result = scaffold_command(
        project_root=project_root,
        command_name="disk",
        class_name="DiskHealth",
        description="disk command",
    )

    assert result["class_name"] == "DiskHealthCommand"


def test_scaffold_command_dry_run_writes_nothing(tmp_path):
    project_root = _make_project(tmp_path)

    result = scaffold_command(
        project_root=project_root,
        command_name="preview",
        description="preview command",
        dry_run=True,
    )

    assert result["action"] == "create"
    assert not (project_root / "src/botty/cmd/handlers/preview").exists()


def test_scaffold_command_dry_run_reports_overwrite_when_forced(tmp_path):
    project_root = _make_project(tmp_path)
    existing_dir = project_root / "src/botty/cmd/handlers/existing"
    existing_dir.mkdir(parents=True)
    (existing_dir / "command.py").write_text("old", encoding="utf-8")
    (existing_dir / "__init__.py").write_text("old", encoding="utf-8")

    result = scaffold_command(
        project_root=project_root,
        command_name="existing",
        description="existing command",
        force=True,
        dry_run=True,
    )

    assert result["action"] == "overwrite"
    assert (existing_dir / "command.py").read_text(encoding="utf-8") == "old"
    assert (existing_dir / "__init__.py").read_text(encoding="utf-8") == "old"


def test_scaffold_command_renders_security_and_shell_options(tmp_path):
    project_root = _make_project(tmp_path)

    result = scaffold_command(
        project_root=project_root,
        command_name="uptime_check",
        description="Check uptime",
        behavior_summary="Check current system uptime",
        auth_required=True,
        sudo=True,
        requires_totp=True,
        shell_command=["uptime", "-p"],
        shell_cwd="/tmp",
    )

    source = Path(result["command_file"]).read_text(encoding="utf-8")
    assert "auth_required = True" in source
    assert "sudo = True" in source
    assert "requires_totp = True" in source
    assert 'command = ["uptime", "-p"]' in source
    assert "command.extend(script_args)" in source
    assert "if self.requires_totp and script_args:" in source
    assert 'output = await self._run_command(command, cwd="/tmp")' in source
    assert '*CWD:*' in source


def test_collect_interactive_inputs(monkeypatch):
    class Args:
        name = None
        description = "default desc"
        class_name = None

    responses = iter(
        [
            "interactive_cmd",
            "",
            "",
            "Runs an interactive check",
            "y",
            "n",
            "y",
            "y",
            "uptime -p",
            "/tmp",
        ]
    )

    monkeypatch.setattr("builtins.input", lambda _prompt: next(responses))

    options = _collect_interactive_inputs(Args())
    assert options["command_name"] == "interactive_cmd"
    assert options["description"] == "default desc"
    assert options["class_name"] is None
    assert options["behavior_summary"] == "Runs an interactive check"
    assert options["auth_required"] is True
    assert options["sudo"] is False
    assert options["requires_totp"] is True
    assert options["shell_command"] == ["uptime", "-p"]
    assert options["shell_cwd"] == "/tmp"


def test_collect_interactive_inputs_uses_json_defaults(monkeypatch):
    class Args:
        name = None
        description = "default desc"
        class_name = None

    responses = iter(
        [
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
        ]
    )
    monkeypatch.setattr("builtins.input", lambda _prompt: next(responses))

    options = _collect_interactive_inputs(
        Args(),
        defaults={
            "command_name": "from_json",
            "description": "From JSON description",
            "class_name": "FromJsonCommand",
            "behavior_summary": "From JSON behavior",
            "auth_required": False,
            "sudo": True,
            "requires_totp": True,
            "shell_command": ["echo", "hello"],
            "shell_cwd": "/tmp",
        },
    )
    assert options["command_name"] == "from_json"
    assert options["description"] == "From JSON description"
    assert options["class_name"] == "FromJsonCommand"
    assert options["behavior_summary"] == "From JSON behavior"
    assert options["auth_required"] is False
    assert options["sudo"] is True
    assert options["requires_totp"] is True
    assert options["shell_command"] == ["echo", "hello"]
    assert options["shell_cwd"] == "/tmp"


def test_scaffold_command_rejects_cwd_without_shell(tmp_path):
    project_root = _make_project(tmp_path)
    with pytest.raises(ValueError):
        scaffold_command(
            project_root=project_root,
            command_name="invalid",
            description="invalid",
            shell_cwd="/tmp",
        )


def test_parse_json_commands_valid(tmp_path):
    payload = {
        "commands": [
            {
                "name": "hello",
                "description": "Hello command",
                "shell_command": "uptime -p",
                "cwd": "/tmp",
            },
            {
                "name": "disk_status",
                "description": "Disk status",
                "shell_command": ["df", "-h", "/"],
                "sudo": True,
                "requires_totp": True,
            },
        ]
    }
    payload_path = tmp_path / "commands.json"
    payload_path.write_text(json.dumps(payload), encoding="utf-8")

    commands = _parse_json_commands(str(payload_path))
    assert len(commands) == 2
    assert commands[0]["command_name"] == "hello"
    assert commands[0]["shell_command"] == ["uptime", "-p"]
    assert commands[0]["shell_cwd"] == "/tmp"
    assert commands[1]["command_name"] == "disk_status"
    assert commands[1]["shell_command"] == ["df", "-h", "/"]
    assert commands[1]["sudo"] is True
    assert commands[1]["requires_totp"] is True


def test_parse_json_commands_rejects_unknown_fields(tmp_path):
    payload_path = tmp_path / "commands.json"
    payload_path.write_text(
        json.dumps(
            {"commands": [{"name": "hello", "description": "x", "unknown": True}]}
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="unknown fields"):
        _parse_json_commands(str(payload_path))


def test_parse_json_commands_rejects_cwd_without_shell(tmp_path):
    payload_path = tmp_path / "commands.json"
    payload_path.write_text(
        json.dumps({"commands": [{"name": "hello", "description": "x", "cwd": "/tmp"}]}),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="cwd requires shell_command"):
        _parse_json_commands(str(payload_path))


def test_main_json_batch_reports_success_and_failure(monkeypatch, capsys, tmp_path):
    args = argparse.Namespace(
        name=None,
        description="Custom command scaffold",
        class_name=None,
        project_root=str(tmp_path),
        force=False,
        dry_run=True,
        interactive=False,
        json="commands.json",
        print_json_schema=False,
        shell_command=None,
        cwd=None,
    )

    monkeypatch.setattr("botty.command_creator._parse_args", lambda: args)
    monkeypatch.setattr(
        "botty.command_creator._parse_json_commands",
        lambda _source: [
            {
                "command_name": "ok_cmd",
                "description": "ok",
                "class_name": None,
                "behavior_summary": "ok",
                "auth_required": True,
                "sudo": False,
                "requires_totp": False,
                "shell_command": None,
                "shell_cwd": None,
            },
            {
                "command_name": "bad_cmd",
                "description": "bad",
                "class_name": None,
                "behavior_summary": "bad",
                "auth_required": True,
                "sudo": False,
                "requires_totp": False,
                "shell_command": None,
                "shell_cwd": None,
            },
        ],
    )

    calls = {"n": 0}

    def _fake_scaffold(*_args, **kwargs):
        calls["n"] += 1
        if kwargs["command_name"] == "bad_cmd":
            raise FileExistsError("already exists")
        return {
            "command_name": kwargs["command_name"],
            "class_name": "OkCmdCommand",
            "command_file": "x/command.py",
            "package_init": "x/__init__.py",
            "handlers_package_init": "src/botty/cmd/handlers/__init__.py",
            "action": "create",
            "shell_command": "",
            "shell_cwd": "",
        }

    monkeypatch.setattr("botty.command_creator.scaffold_command", _fake_scaffold)

    exit_code = main()
    output = capsys.readouterr().out
    assert exit_code == 1
    assert calls["n"] == 2
    assert "loaded 2 command definition(s) from commands.json" in output
    assert "[1] OK /ok_cmd" in output
    assert "[2] FAIL /bad_cmd: already exists" in output
    assert "summary: 1 succeeded, 1 failed" in output
    assert "dry run: no files were written" in output


def test_main_print_json_schema(monkeypatch, capsys):
    args = argparse.Namespace(
        name=None,
        description="Custom command scaffold",
        class_name=None,
        project_root=".",
        force=False,
        dry_run=False,
        interactive=False,
        json=None,
        print_json_schema=True,
        shell_command=None,
        cwd=None,
    )
    monkeypatch.setattr("botty.command_creator._parse_args", lambda: args)
    exit_code = main()
    output = capsys.readouterr().out
    assert exit_code == 0
    assert '"required": [' in output
    assert '"commands"' in output


def test_get_commands_json_schema_shape():
    schema = get_commands_json_schema()
    assert schema["type"] == "object"
    assert "commands" in schema["properties"]
