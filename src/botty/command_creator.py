"""CLI scaffold for creating bot commands."""

from __future__ import annotations

import argparse
import json
import re
import shlex
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse
from urllib.request import Request, urlopen

HANDLERS_PACKAGE_PATH = Path("src/botty/cmd/handlers")
DEFAULT_BEHAVIOR_SUMMARY = "Custom command scaffold"

COMMANDS_JSON_SCHEMA: dict[str, object] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "https://example.com/schemas/botty-command-batch.schema.json",
    "title": "Botty Command Batch",
    "type": "object",
    "additionalProperties": False,
    "required": ["commands"],
    "properties": {
        "commands": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["name", "description"],
                "properties": {
                    "name": {"type": "string"},
                    "description": {"type": "string"},
                    "class_name": {"type": "string"},
                    "behavior_summary": {"type": "string"},
                    "auth_required": {"type": "boolean"},
                    "sudo": {"type": "boolean"},
                    "requires_totp": {"type": "boolean"},
                    "shell_command": {
                        "oneOf": [
                            {"type": "string"},
                            {
                                "type": "array",
                                "minItems": 1,
                                "items": {"type": "string"},
                            },
                        ]
                    },
                    "cwd": {"type": "string"},
                },
            },
        }
    },
}


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
        "        raw_args = [str(arg) for arg in context.args] if context.args else []",
        '        args = " ".join(raw_args).strip() if raw_args else "(no args)"',
        f"        purpose = {json.dumps(behavior)}",
    ]

    if shell_command:
        command_literal = "[" + ", ".join(json.dumps(part) for part in shell_command) + "]"
        cwd_literal = json.dumps(shell_cwd) if shell_cwd else None
        run_command_line = (
            f"        output = await self._run_command(command, cwd={cwd_literal})"
            if cwd_literal
            else "        output = await self._run_command(command)"
        )
        lines.extend(
            [
                f"        command = {command_literal}",
                "        script_args = list(raw_args)",
                "        if self.requires_totp and script_args:",
                "            maybe_totp = script_args[-1].strip()",
                "            if maybe_totp.isdigit() and len(maybe_totp) == 6:",
                "                script_args = script_args[:-1]",
                "        if script_args:",
                "            command.extend(script_args)",
                '        args = " ".join(script_args).strip() if script_args else "(no args)"',
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


def get_commands_json_schema() -> dict[str, object]:
    return json.loads(json.dumps(COMMANDS_JSON_SCHEMA))


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
    args: argparse.Namespace,
    defaults: dict[str, object] | None = None,
    input_fn: Callable[[str], str] | None = None,
) -> dict[str, object]:
    defaults = defaults or {}
    default_name = str(defaults.get("command_name") or args.name or "")
    default_description = str(
        defaults.get("description") or args.description or DEFAULT_BEHAVIOR_SUMMARY
    )
    default_class_name = defaults.get("class_name")
    default_behavior = str(
        defaults.get("behavior_summary") or DEFAULT_BEHAVIOR_SUMMARY
    )
    default_auth = bool(defaults.get("auth_required", True))
    default_sudo = bool(defaults.get("sudo", False))
    default_totp = bool(defaults.get("requires_totp", False))
    default_shell_command = defaults.get("shell_command")
    default_shell_cwd = defaults.get("shell_cwd")

    while True:
        raw_name = _prompt_text(
            "Command name",
            default=default_name or None,
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
        default=default_description,
        required=True,
        input_fn=input_fn,
    )
    class_name = _prompt_text(
        "Class name (leave blank for auto)",
        default=str(default_class_name) if default_class_name else None,
        required=False,
        input_fn=input_fn,
    )
    behavior_summary = _prompt_text(
        "What should this command do",
        default=default_behavior,
        required=True,
        input_fn=input_fn,
    )
    auth_required = _prompt_bool(
        "Require authorized users",
        default=default_auth,
        input_fn=input_fn,
    )
    sudo = _prompt_bool(
        "Run shell commands with sudo by default",
        default=default_sudo,
        input_fn=input_fn,
    )
    requires_totp = _prompt_bool(
        "Require TOTP code",
        default=default_totp,
        input_fn=input_fn,
    )

    if isinstance(default_shell_command, list):
        default_shell = " ".join(shlex.quote(str(part)) for part in default_shell_command)
    elif isinstance(default_shell_command, str):
        default_shell = default_shell_command
    else:
        default_shell = ""
    use_shell = _prompt_bool(
        "Include a shell command in the initial template",
        default=bool(default_shell),
        input_fn=input_fn,
    )
    shell_command = None
    shell_cwd = None
    if use_shell:
        while True:
            raw_shell = _prompt_text(
                "Shell command (example: uptime -p)",
                default=default_shell or None,
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
            default=str(default_shell_cwd) if default_shell_cwd else None,
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


def _is_http_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _load_json_payload(source: str) -> object:
    if _is_http_url(source):
        req = Request(source, headers={"User-Agent": "botty-create-command/0.1"})
        with urlopen(req, timeout=15) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            return json.loads(response.read().decode(charset))

    payload_path = Path(source).expanduser()
    if not payload_path.exists():
        raise FileNotFoundError(f"json source does not exist: {payload_path}")
    return json.loads(payload_path.read_text(encoding="utf-8"))


def _expect_type(value: object, expected_type: type, context: str) -> None:
    if not isinstance(value, expected_type):
        raise ValueError(f"{context} must be {expected_type.__name__}")


def _normalize_shell_command(raw_shell_command: object, context: str) -> list[str] | None:
    if raw_shell_command is None:
        return None
    if isinstance(raw_shell_command, str):
        text = raw_shell_command.strip()
        if not text:
            raise ValueError(f"{context}.shell_command cannot be empty")
        try:
            parsed = shlex.split(text)
        except ValueError as exc:
            raise ValueError(f"{context}.shell_command is invalid: {exc}") from exc
        if not parsed:
            raise ValueError(f"{context}.shell_command cannot be empty")
        return parsed
    if isinstance(raw_shell_command, list):
        if not raw_shell_command:
            raise ValueError(f"{context}.shell_command array cannot be empty")
        parsed = []
        for idx, part in enumerate(raw_shell_command):
            if not isinstance(part, str) or not part:
                raise ValueError(
                    f"{context}.shell_command[{idx}] must be a non-empty string"
                )
            parsed.append(part)
        return parsed
    raise ValueError(f"{context}.shell_command must be a string or an array of strings")


def _normalize_json_command(raw: object, index: int) -> dict[str, object]:
    context = f"commands[{index}]"
    _expect_type(raw, dict, context)
    command = dict(raw)
    allowed = {
        "name",
        "description",
        "class_name",
        "behavior_summary",
        "auth_required",
        "sudo",
        "requires_totp",
        "shell_command",
        "cwd",
    }
    unknown = sorted(set(command.keys()) - allowed)
    if unknown:
        raise ValueError(f"{context} has unknown fields: {', '.join(unknown)}")

    if "name" not in command:
        raise ValueError(f"{context}.name is required")
    if "description" not in command:
        raise ValueError(f"{context}.description is required")

    _expect_type(command["name"], str, f"{context}.name")
    _expect_type(command["description"], str, f"{context}.description")
    command_name = _normalize_command_name(command["name"])
    description = command["description"].strip()
    if not description:
        raise ValueError(f"{context}.description cannot be empty")

    class_name = command.get("class_name")
    if class_name is not None:
        _expect_type(class_name, str, f"{context}.class_name")
        if not class_name.strip():
            class_name = None

    behavior_summary = command.get("behavior_summary", DEFAULT_BEHAVIOR_SUMMARY)
    _expect_type(behavior_summary, str, f"{context}.behavior_summary")
    if not behavior_summary.strip():
        behavior_summary = DEFAULT_BEHAVIOR_SUMMARY

    auth_required = command.get("auth_required", True)
    sudo = command.get("sudo", False)
    requires_totp = command.get("requires_totp", False)
    if not isinstance(auth_required, bool):
        raise ValueError(f"{context}.auth_required must be boolean")
    if not isinstance(sudo, bool):
        raise ValueError(f"{context}.sudo must be boolean")
    if not isinstance(requires_totp, bool):
        raise ValueError(f"{context}.requires_totp must be boolean")

    shell_command = _normalize_shell_command(command.get("shell_command"), context)

    shell_cwd = command.get("cwd")
    if shell_cwd is not None:
        _expect_type(shell_cwd, str, f"{context}.cwd")
        shell_cwd = shell_cwd.strip()
        if not shell_cwd:
            shell_cwd = None
    if shell_cwd and not shell_command:
        raise ValueError(f"{context}.cwd requires shell_command")

    return {
        "command_name": command_name,
        "description": description,
        "class_name": class_name,
        "behavior_summary": behavior_summary,
        "auth_required": auth_required,
        "sudo": sudo,
        "requires_totp": requires_totp,
        "shell_command": shell_command,
        "shell_cwd": shell_cwd,
    }


def _parse_json_commands(source: str) -> list[dict[str, object]]:
    payload = _load_json_payload(source)
    if not isinstance(payload, dict):
        raise ValueError("json root must be an object with a 'commands' array")
    if set(payload.keys()) - {"commands"}:
        unknown = sorted(set(payload.keys()) - {"commands"})
        raise ValueError(f"json root has unknown fields: {', '.join(unknown)}")
    commands = payload.get("commands")
    if not isinstance(commands, list):
        raise ValueError("'commands' must be an array")
    if not commands:
        raise ValueError("'commands' must not be empty")
    return [_normalize_json_command(item, index) for index, item in enumerate(commands)]


def _build_non_interactive_options(args: argparse.Namespace) -> dict[str, object]:
    if not args.name:
        raise ValueError("name is required unless --interactive or --json is used")
    parsed_shell_command = None
    if isinstance(args.shell_command, str) and args.shell_command.strip():
        try:
            parsed_shell_command = shlex.split(args.shell_command)
        except ValueError as exc:
            raise ValueError(f"invalid --shell-command: {exc}") from exc
    return {
        "command_name": args.name,
        "description": args.description,
        "class_name": args.class_name,
        "behavior_summary": DEFAULT_BEHAVIOR_SUMMARY,
        "auth_required": True,
        "sudo": False,
        "requires_totp": False,
        "shell_command": parsed_shell_command,
        "shell_cwd": args.cwd,
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
        "--json",
        default=None,
        help="JSON file path or HTTP(S) URL containing one or more command definitions",
    )
    parser.add_argument(
        "--print-json-schema",
        action="store_true",
        help="print the JSON schema for --json payloads and exit",
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

    if args.print_json_schema:
        print(json.dumps(get_commands_json_schema(), indent=2, sort_keys=True))
        return 0

    if args.json and args.name:
        print("error: positional name cannot be used with --json")
        return 1

    if args.json:
        try:
            entries = _parse_json_commands(args.json)
        except (ValueError, FileNotFoundError, json.JSONDecodeError) as exc:
            print(f"error: {exc}")
            return 1

        print(f"loaded {len(entries)} command definition(s) from {args.json}")
        success_count = 0
        failure_count = 0

        for index, base_options in enumerate(entries, start=1):
            scaffold_options = base_options
            if args.interactive:
                scaffold_options = _collect_interactive_inputs(args, defaults=base_options)

            command_name = str(scaffold_options["command_name"])
            try:
                result = scaffold_command(
                    project_root=project_root,
                    force=args.force,
                    dry_run=args.dry_run,
                    **scaffold_options,
                )
            except (ValueError, FileNotFoundError, FileExistsError) as exc:
                failure_count += 1
                print(f"[{index}] FAIL /{command_name}: {exc}")
                continue

            success_count += 1
            action = "would create" if args.dry_run and result["action"] == "create" else (
                "would overwrite" if args.dry_run else result["action"]
            )
            print(
                f"[{index}] OK /{result['command_name']} ({result['class_name']}) - {action}"
            )
            print(f"      command file: {result['command_file']}")
            print(f"      package init: {result['package_init']}")
            if result["shell_command"]:
                print(f"      shell command: {result['shell_command']}")
            if result["shell_cwd"]:
                print(f"      shell cwd: {result['shell_cwd']}")

        if args.dry_run:
            print("dry run: no files were written")
        print(f"summary: {success_count} succeeded, {failure_count} failed")
        return 0 if failure_count == 0 else 1

    if args.interactive:
        scaffold_options = _collect_interactive_inputs(args)
    else:
        try:
            scaffold_options = _build_non_interactive_options(args)
        except ValueError as exc:
            print(f"error: {exc}")
            return 1

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
