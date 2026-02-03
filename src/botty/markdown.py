import re


def escape_markdown(text: str) -> str:
    """Escapes special characters for Telegram MarkdownV2 (outside of code blocks)."""
    escape_chars = r"_*[]()~`>#+-=|{}.!"
    # We need 3 backslashes in the file: r"\"
    return re.sub(f"([{re.escape(escape_chars)}])", r"\\\1", text)


def escape_markdown_code(text: str) -> str:
    """Escapes special characters for Telegram MarkdownV2 (inside inline code/pre blocks)."""
    # Only backslash and backtick need escaping inside code blocks
    return text.replace("\\", "\\\\").replace("`", "\\`")
