"""CLI scaffold for creating bot commands."""

from __future__ import annotations

import argparse
import json
import re
import shlex
from pathlib import Path
from typing import Callable

HANDLERS_PACKAGE_PATH = Path("src/botty/cmd/handlers")


def _normalize_command_name(raw_name: str) -> str:
    command_name = raw_name.strip().lower()
    if not re.fullmatch(r"[a-z][a-z0-9_]*", command_name):
        raise ValueError(
            "command name must match [a-z][a-z0-9_]* (example: hello or disk_status)"
        )
    return command_name


def _derive_class_name(command_name: str, explicit_class_name: str | None) -> str:
    if explicit_class_name:
        class_name = explicit_class_name.strip()
        if not re.fullmatch(r"[A-Z][A-Za-z0-9]*", class_name):
            raise ValueError("class name must match [A-Z][A-Za-z0-9]*")
        if not class_name.endswith("Command"):
            class_name = f"{class_name}Command"
        return class_name

    pieces = [part for part in command_name.split("_") if part]
    base_name = "".join(part[:1].upper() + part[1:] for part in pieces)
    return f"{base_name}Command"


def _render_command_template(
    class_name: str,
    command_name: str,
    description: str,
    behavior_summary: str,
    auth_required: bool,
    sudo: bool,
    requires_totp: bool,
    shell_command: list[str] | None,
    shell_cwd: str | None,
) -> str:
    title = class_name.removesuffix("Command")
    behavior = behavior_summary.strip() or "Custom command scaffold"

    lines = [
        "from telegram import Update",
        "from telegram.ext import ContextTypes",
        "",
        "from botty.cmd.handlers.base import Command",
        "from botty.utils import escape_markdown_code",
        "",
        "",
        f"class {class_name}(Command):",
        f'    name = "{command_name}"',
        f'    description = "{description}"',
        f"    auth_required = {auth_required}",
        f"    sudo = {sudo}",
        f"    requires_totp = {requires_totp}",
        "",
        "    async def run(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:",
        "        message = self._require_message(update)",
        '        args = " ".join(context.args).strip() if context.args else "(no args)"',
        f"        purpose = {json.dumps(behavior)}",
    ]

    if shell_command:
        command_literal = "[" + ", ".join(json.dumps(part) for part in shell_command) + "]"
        cwd_literal = json.dumps(shell_cwd) if shell_cwd else None
        run_command_line = (
            f"        output = await self._run_command({command_literal}, cwd={cwd_literal})"
            if cwd_literal
            else f"        output = await self._run_command({command_literal})"
        )
        lines.extend(
            [
                run_command_line,
                '        output_text = output.strip() if output.strip() else "(no output)"',
                "        reply = (",
                f'            "*{title}*\\n\\n"',
                '            f"*Purpose:* `{escape_markdown_code(purpose)}`\\n"',
                '            f"*Args:* `{escape_markdown_code(args)}`\\n\\n"',
                (
                    '            f"*CWD:* `{escape_markdown_code('
                    + json.dumps(shell_cwd)
                    + ')}`\\n\\n"'
                    if shell_cwd
                    else ""
                ),
                '            "*Output:*\\n```\\n"',
                '            f"{escape_markdown_code(output_text)}\\n```"',
                "        )",
            ]
        )
    else:
        lines.extend(
            [
                "        reply = (",
                f'            "*{title}*\\n\\n"',
                '            f"*Purpose:* `{escape_markdown_code(purpose)}`\\n"',
                '            f"*Args:* `{escape_markdown_code(args)}`\\n\\n"',
                '            "_TODO: implement command logic_"',
                "        )",
            ]
        )

    lines.append("        await self._reply_markdown(message, reply)")
    return "\n".join(lines) + "\n"


def _render_package_init_template(class_name: str) -> str:
    return (
        f"from .command import {class_name} as {class_name}\n\n"
        f'__all__ = ["{class_name}"]\n'
    )


def scaffold_command(
    project_root: Path,
    command_name: str,
    description: str,
    class_name: str | None = None,
    force: bool = False,
    dry_run: bool = False,
    behavior_summary: str = "Custom command scaffold",
    auth_required: bool = True,
    sudo: bool = False,
    requires_totp: bool = False,
    shell_command: list[str] | None = None,
    shell_cwd: str | None = None,
) -> dict[str, str]:
    normalized_name = _normalize_command_name(command_name)
    resolved_class_name = _derive_class_name(normalized_name, class_name)

    handlers_root = project_root / HANDLERS_PACKAGE_PATH
    handlers_init = handlers_root / "__init__.py"
    if not handlers_init.exists():
        raise FileNotFoundError(
            f"missing handlers package init file: {handlers_init}"
        )

    command_dir = handlers_root / normalized_name
    command_path = command_dir / "command.py"
    init_path = command_dir / "__init__.py"
    command_exists = command_dir.exists()

    if command_exists and not force:
        raise FileExistsError(
            f"{command_dir} already exists. Re-run with --force to overwrite."
        )

    normalized_cwd = shell_cwd.strip() if isinstance(shell_cwd, str) else None
    if normalized_cwd == "":
        normalized_cwd = None
    if normalized_cwd and not shell_command:
        raise ValueError("cwd can only be used when a shell command is provided")

    if not dry_run:
        command_dir.mkdir(parents=True, exist_ok=True)
        command_path.write_text(
            _render_command_template(
                class_name=resolved_class_name,
                command_name=normalized_name,
                description=description.strip(),
                behavior_summary=behavior_summary,
                auth_required=auth_required,
                sudo=sudo,
                requires_totp=requires_totp,
                shell_command=shell_command,
                shell_cwd=normalized_cwd,
            ),
            encoding="utf-8",
        )
        init_path.write_text(
            _render_package_init_template(resolved_class_name), encoding="utf-8"
        )

    return {
        "command_name": normalized_name,
        "class_name": resolved_class_name,
        "command_file": str(command_path),
        "package_init": str(init_path),
        "handlers_package_init": str(handlers_init),
        "action": "overwrite" if command_exists else "create",
        "shell_command": " ".join(shell_command) if shell_command else "",
        "shell_cwd": normalized_cwd or "",
    }


def _prompt_text(
    prompt: str,
    *,
    default: str | None = None,
    required: bool = False,
    input_fn: Callable[[str], str] | None = None,
) -> str:
    reader = input if input_fn is None else input_fn
    while True:
        default_suffix = f" [{default}]" if default is not None else ""
        value = reader(f"{prompt}{default_suffix}: ").strip()
        if not value and default is not None:
            return default
        if value:
            return value
        if required:
            print("value is required.")
            continue
        return ""


def _prompt_bool(
    prompt: str,
    *,
    default: bool,
    input_fn: Callable[[str], str] | None = None,
) -> bool:
    reader = input if input_fn is None else input_fn
    hint = "Y/n" if default else "y/N"
    while True:
        value = reader(f"{prompt} [{hint}]: ").strip().lower()
        if not value:
            return default
        if value in {"y", "yes"}:
            return True
        if value in {"n", "no"}:
            return False
        print("please answer y or n.")


def _collect_interactive_inputs(
    args: argparse.Namespace, input_fn: Callable[[str], str] | None = None
) -> dict[str, object]:
    while True:
        raw_name = _prompt_text(
            "Command name",
            default=args.name,
            required=True,
            input_fn=input_fn,
        )
        try:
            command_name = _normalize_command_name(raw_name)
            break
        except ValueError as exc:
            print(f"invalid command name: {exc}")

    description = _prompt_text(
        "Description shown in /start",
        default=args.description,
        required=True,
        input_fn=input_fn,
    )
    class_name = _prompt_text(
        "Class name (leave blank for auto)",
        default=args.class_name,
        required=False,
        input_fn=input_fn,
    )
    behavior_summary = _prompt_text(
        "What should this command do",
        default="Custom command scaffold",
        required=True,
        input_fn=input_fn,
    )
    auth_required = _prompt_bool(
        "Require authorized users",
        default=True,
        input_fn=input_fn,
    )
    sudo = _prompt_bool(
        "Run shell commands with sudo by default",
        default=False,
        input_fn=input_fn,
    )
    requires_totp = _prompt_bool(
        "Require TOTP code",
        default=False,
        input_fn=input_fn,
    )

    use_shell = _prompt_bool(
        "Include a shell command in the initial template",
        default=False,
        input_fn=input_fn,
    )
    shell_command = None
    shell_cwd = None
    if use_shell:
        while True:
            raw_shell = _prompt_text(
                "Shell command (example: uptime -p)",
                required=True,
                input_fn=input_fn,
            )
            try:
                shell_command = shlex.split(raw_shell)
            except ValueError as exc:
                print(f"invalid shell command: {exc}")
                continue
            if not shell_command:
                print("shell command cannot be empty.")
                continue
            break
        shell_cwd = _prompt_text(
            "Working directory for shell command (blank = bot process cwd)",
            default=None,
            required=False,
            input_fn=input_fn,
        )

    return {
        "command_name": command_name,
        "description": description,
        "class_name": class_name or None,
        "behavior_summary": behavior_summary,
        "auth_required": auth_required,
        "sudo": sudo,
        "requires_totp": requires_totp,
        "shell_command": shell_command,
        "shell_cwd": shell_cwd or None,
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="botty-create-command",
        description="Create a new Botty command scaffold.",
    )
    parser.add_argument(
        "name",
        nargs="?",
        help="command name (example: hello or disk_status)",
    )
    parser.add_argument(
        "--description",
        default="Custom command scaffold",
        help="description shown in /start",
    )
    parser.add_argument(
        "--class-name",
        default=None,
        help="optional class name (defaults to <Name>Command)",
    )
    parser.add_argument(
        "--project-root",
        default=".",
        help="project root path (defaults to current directory)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="overwrite an existing command package",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="show what would be created without writing files",
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="prompt for command details interactively",
    )
    parser.add_argument(
        "--shell-command",
        default=None,
        help="optional shell command for the template (example: ./update.sh)",
    )
    parser.add_argument(
        "--cwd",
        default=None,
        help="working directory for --shell-command",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    project_root = Path(args.project_root).resolve()

    if args.interactive:
        scaffold_options = _collect_interactive_inputs(args)
    else:
        if not args.name:
            print("error: name is required unless --interactive is used")
            return 1
        parsed_shell_command = None
        if isinstance(args.shell_command, str) and args.shell_command.strip():
            try:
                parsed_shell_command = shlex.split(args.shell_command)
            except ValueError as exc:
                print(f"error: invalid --shell-command: {exc}")
                return 1
        scaffold_options = {
            "command_name": args.name,
            "description": args.description,
            "class_name": args.class_name,
            "behavior_summary": "Custom command scaffold",
            "auth_required": True,
            "sudo": False,
            "requires_totp": False,
            "shell_command": parsed_shell_command,
            "shell_cwd": args.cwd,
        }

    try:
        result = scaffold_command(
            project_root=project_root,
            force=args.force,
            dry_run=args.dry_run,
            **scaffold_options,
        )
    except (ValueError, FileNotFoundError, FileExistsError) as exc:
        print(f"error: {exc}")
        return 1

    if args.dry_run:
        print("dry run: no files were written")
        print(f"- would {result['action']} command scaffold:")
    else:
        print("created command scaffold:")
    print(f"- /{result['command_name']} ({result['class_name']})")
    print(f"- {result['command_file']}")
    print(f"- {result['package_init']}")
    print(f"- discovered automatically via {result['handlers_package_init']}")
    if result["shell_command"]:
        print(f"- shell command: {result['shell_command']}")
    if result["shell_cwd"]:
        print(f"- shell cwd: {result['shell_cwd']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
