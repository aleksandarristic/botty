from pathlib import Path

import pytest

from botty.command_creator import _collect_interactive_inputs, scaffold_command


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


def test_scaffold_command_rejects_cwd_without_shell(tmp_path):
    project_root = _make_project(tmp_path)
    with pytest.raises(ValueError):
        scaffold_command(
            project_root=project_root,
            command_name="invalid",
            description="invalid",
            shell_cwd="/tmp",
        )
