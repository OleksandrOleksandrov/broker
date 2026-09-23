"""Text processing utilities."""

from typing import Optional


def normalize_quotes(text: Optional[str]) -> Optional[str]:
    """Replace straight quotes with Ukrainian guillemets."""
    if text is None:
        return None
    result = []
    use_open = True
    for char in text:
        if char == '"':
            result.append("«" if use_open else "»")
            use_open = not use_open
        else:
            result.append(char)
    return "".join(result)