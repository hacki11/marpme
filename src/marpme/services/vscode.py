from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path

from marpme.errors import InvalidConfigError

MARP_EXTENSION = "marp-team.marp-vscode"


def _jsonc_for_parsing(text: str) -> str:
    """Replace JSONC comments/trailing commas with spaces while retaining offsets."""
    chars = list(text)
    index = 0
    in_string = False
    escaped = False
    while index < len(chars):
        char = chars[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            index += 1
            continue
        if char == '"':
            in_string = True
            index += 1
            continue
        if char == "/" and index + 1 < len(chars) and chars[index + 1] == "/":
            chars[index] = chars[index + 1] = " "
            index += 2
            while index < len(chars) and chars[index] not in "\r\n":
                chars[index] = " "
                index += 1
            continue
        if char == "/" and index + 1 < len(chars) and chars[index + 1] == "*":
            chars[index] = chars[index + 1] = " "
            index += 2
            while index + 1 < len(chars):
                if chars[index] == "*" and chars[index + 1] == "/":
                    chars[index] = chars[index + 1] = " "
                    index += 2
                    break
                if chars[index] not in "\r\n":
                    chars[index] = " "
                index += 1
            continue
        index += 1
    sanitized = "".join(chars)
    for match in re.finditer(r",(?=\s*[}\]])", sanitized):
        chars[match.start()] = " "
    return "".join(chars)


def _matching_bracket(text: str, opening: int) -> int:
    pairs = {"[": "]", "{": "}"}
    expected = pairs[text[opening]]
    depth = 0
    in_string = False
    escaped = False
    for index in range(opening, len(text)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == text[opening]:
            depth += 1
        elif char == expected:
            depth -= 1
            if depth == 0:
                return index
    raise InvalidConfigError("Unbalanced JSONC structure in .vscode/extensions.json.")


def _string_spans(text: str, start: int, end: int) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    index = start
    while index < end:
        if text[index] != '"':
            index += 1
            continue
        begin = index
        index += 1
        escaped = False
        while index < end:
            if escaped:
                escaped = False
            elif text[index] == "\\":
                escaped = True
            elif text[index] == '"':
                spans.append((begin, index + 1))
                index += 1
                break
            index += 1
    return spans


class VsCodeService:
    def validate(self, repository_root: Path) -> None:
        path = repository_root / ".vscode" / "extensions.json"
        if not path.exists():
            return
        try:
            parsed = json.loads(_jsonc_for_parsing(path.read_text(encoding="utf-8")))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise InvalidConfigError(
                f"Cannot merge {path}: it is not valid JSON or JSONC.\nDetails: {exc}"
            ) from exc
        if not isinstance(parsed, dict):
            raise InvalidConfigError(f"{path} must contain a JSON object.")
        recommendations = parsed.get("recommendations")
        if recommendations is not None and (
            not isinstance(recommendations, list)
            or any(not isinstance(item, str) for item in recommendations)
        ):
            raise InvalidConfigError(f'"recommendations" in {path} must be an array of strings.')

    def ensure_recommendation(self, repository_root: Path) -> bool:
        path = repository_root / ".vscode" / "extensions.json"
        if not path.exists():
            self._atomic_write(
                path,
                json.dumps({"recommendations": [MARP_EXTENSION]}, indent=2) + "\n",
            )
            return True
        try:
            original = path.read_text(encoding="utf-8")
            sanitized = _jsonc_for_parsing(original)
            parsed = json.loads(sanitized)
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise InvalidConfigError(
                f"Cannot merge {path}: it is not valid JSON or JSONC.\nDetails: {exc}"
            ) from exc
        if not isinstance(parsed, dict):
            raise InvalidConfigError(f"{path} must contain a JSON object.")
        recommendations = parsed.get("recommendations")
        if recommendations is not None and (
            not isinstance(recommendations, list)
            or any(not isinstance(item, str) for item in recommendations)
        ):
            raise InvalidConfigError(f'"recommendations" in {path} must be an array of strings.')
        if recommendations and MARP_EXTENSION in recommendations:
            return False
        updated = self._insert_recommendation(original, sanitized, recommendations)
        self._atomic_write(path, updated)
        return True

    def is_integrated(self, repository_root: Path) -> bool:
        path = repository_root / ".vscode" / "extensions.json"
        if not path.is_file():
            return False
        try:
            parsed = json.loads(_jsonc_for_parsing(path.read_text(encoding="utf-8")))
        except (OSError, UnicodeError, json.JSONDecodeError):
            return False
        return isinstance(parsed, dict) and MARP_EXTENSION in parsed.get("recommendations", [])

    @staticmethod
    def _insert_recommendation(
        original: str, sanitized: str, recommendations: list[str] | None
    ) -> str:
        newline = "\r\n" if "\r\n" in original else "\n"
        if recommendations is None:
            opening = sanitized.find("{")
            if opening < 0:
                raise InvalidConfigError("Invalid .vscode/extensions.json object.")
            closing = _matching_bracket(sanitized, opening)
            indent = "  "
            comma = "," if sanitized[opening + 1 : closing].strip() else ""
            addition = (
                f'{newline}{indent}"recommendations": ['
                f'{newline}{indent}{indent}"{MARP_EXTENSION}"{newline}{indent}]{comma}'
            )
            return original[: opening + 1] + addition + original[opening + 1 :]

        key_match = re.search(r'"recommendations"\s*:', sanitized)
        if key_match is None:
            raise InvalidConfigError("Cannot locate recommendations in .vscode/extensions.json.")
        opening = sanitized.find("[", key_match.end())
        closing = _matching_bracket(sanitized, opening)
        line_start = original.rfind("\n", 0, key_match.start()) + 1
        base_indent = re.match(r"\s*", original[line_start : key_match.start()]).group(0)  # type: ignore[union-attr]
        item_indent = base_indent + "  "
        spans = _string_spans(sanitized, opening + 1, closing)
        value = f'"{MARP_EXTENSION}"'
        if spans:
            insert_at = spans[-1][1]
            addition = f",{newline}{item_indent}{value}"
            return original[:insert_at] + addition + original[insert_at:]
        addition = f"{newline}{item_indent}{value}{newline}{base_indent}"
        return original[: opening + 1] + addition + original[closing:]

    @staticmethod
    def _atomic_write(path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        except Exception:
            Path(temporary).unlink(missing_ok=True)
            raise
