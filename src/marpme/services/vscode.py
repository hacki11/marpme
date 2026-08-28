from __future__ import annotations

import json
import os
import re
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from marpme.errors import InvalidConfigError

VSCODE_FILES = ("extensions.json", "settings.json", "tasks.json")
VSCODE_STATE_VERSION = 1
_MISSING = object()


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
    raise InvalidConfigError("Unbalanced JSONC structure in VS Code configuration.")


def _array_item_ends(text: str, opening: int, closing: int) -> list[int]:
    ends: list[int] = []
    index = opening + 1
    while index < closing:
        while index < closing and (text[index].isspace() or text[index] == ","):
            index += 1
        if index >= closing:
            break
        if text[index] in "[{":
            index = _matching_bracket(text, index) + 1
        elif text[index] == '"':
            index += 1
            escaped = False
            while index < closing:
                if escaped:
                    escaped = False
                elif text[index] == "\\":
                    escaped = True
                elif text[index] == '"':
                    index += 1
                    break
                index += 1
        else:
            while index < closing and text[index] not in ",]":
                index += 1
            while index > opening and text[index - 1].isspace():
                index -= 1
        ends.append(index)
    return ends


def _string_end(text: str, opening: int) -> int:
    index = opening + 1
    escaped = False
    while index < len(text):
        if escaped:
            escaped = False
        elif text[index] == "\\":
            escaped = True
        elif text[index] == '"':
            return index + 1
        index += 1
    raise InvalidConfigError("Unterminated string in VS Code configuration.")


def _value_end(text: str, start: int, closing: int) -> int:
    if text[start] in "[{":
        return _matching_bracket(text, start) + 1
    if text[start] == '"':
        return _string_end(text, start)
    end = start
    while end < closing and text[end] not in ",}":
        end += 1
    while end > start and text[end - 1].isspace():
        end -= 1
    return end


def _object_properties(text: str) -> dict[str, tuple[int, int, int, int | None]]:
    opening = text.find("{")
    if opening < 0:
        raise InvalidConfigError("Invalid VS Code JSON object.")
    closing = _matching_bracket(text, opening)
    properties: dict[str, tuple[int, int, int, int | None]] = {}
    index = opening + 1
    while index < closing:
        while index < closing and (text[index].isspace() or text[index] == ","):
            index += 1
        if index >= closing:
            break
        key_start = index
        if text[index] != '"':
            raise InvalidConfigError("Invalid property in VS Code configuration.")
        key_end = _string_end(text, index)
        key = json.loads(text[key_start:key_end])
        index = key_end
        while index < closing and text[index].isspace():
            index += 1
        if index >= closing or text[index] != ":":
            raise InvalidConfigError("Invalid property in VS Code configuration.")
        index += 1
        while index < closing and text[index].isspace():
            index += 1
        value_start = index
        value_end = _value_end(text, value_start, closing)
        index = value_end
        while index < closing and text[index].isspace():
            index += 1
        comma = index if index < closing and text[index] == "," else None
        properties[key] = (key_start, value_start, value_end, comma)
        if comma is not None:
            index += 1
    return properties


class VsCodeService:
    """Validate and additively merge template-supplied VS Code configuration."""

    def validate(self, repository_root: Path) -> None:
        for filename in VSCODE_FILES:
            path = repository_root / ".vscode" / filename
            if path.exists():
                self._read_jsonc_object(path)

    def merge_template(
        self, repository_root: Path, configuration: Mapping[str, str]
    ) -> bool:
        """Merge template JSON/JSONC while preserving target values and comments.

        Missing properties and array entries are added. Existing scalar values and
        tasks with the same label remain user-owned and are never overwritten.
        """
        parsed_template: dict[str, dict[str, object]] = {}
        for filename, content in configuration.items():
            if filename not in VSCODE_FILES:
                continue
            parsed_template[filename] = self._parse_jsonc_object(
                content, description=f"template .vscode/{filename}"
            )

        self.validate(repository_root)
        changed = False
        for filename in VSCODE_FILES:
            if filename not in parsed_template:
                continue
            path = repository_root / ".vscode" / filename
            if not path.exists():
                content = configuration[filename]
                self._atomic_write(path, content if content.endswith("\n") else content + "\n")
                changed = True
                continue
            changed |= self._merge_object(path, parsed_template[filename], filename=filename)
        self._write_state(repository_root, parsed_template)
        return changed

    def update_template(
        self, repository_root: Path, configuration: Mapping[str, str]
    ) -> tuple[bool, tuple[Path, ...]]:
        """Three-way merge a newer template configuration into the workspace."""
        current_template = {
            filename: self._parse_jsonc_object(
                content, description=f"template .vscode/{filename}"
            )
            for filename, content in configuration.items()
            if filename in VSCODE_FILES
        }
        previous_template = self._read_state(repository_root)
        if previous_template is None:
            return self.merge_template(repository_root, configuration), ()

        self.validate(repository_root)
        changed = False
        conflicts: list[Path] = []
        for filename in VSCODE_FILES:
            path = repository_root / ".vscode" / filename
            base = previous_template.get(filename, _MISSING)
            remote = current_template.get(filename, _MISSING)
            local = self._read_jsonc_object(path) if path.is_file() else _MISSING
            merged, conflict = self._three_way_file(base, local, remote, filename=filename)
            if merged != local:
                if merged is _MISSING:
                    path.unlink(missing_ok=True)
                elif local is _MISSING:
                    self._atomic_write(
                        path, json.dumps(merged, indent=2, ensure_ascii=False) + "\n"
                    )
                else:
                    self._reconcile_object(path, local, merged)
                changed = True
            if conflict:
                conflicts.append(Path(".vscode") / filename)
        self._write_state(repository_root, current_template)
        return changed, tuple(conflicts)

    def is_integrated(self, repository_root: Path) -> bool:
        vscode = repository_root / ".vscode"
        files = [vscode / filename for filename in VSCODE_FILES if (vscode / filename).is_file()]
        if not files:
            return False
        try:
            self.validate(repository_root)
        except InvalidConfigError:
            return False
        return True

    def _merge_object(
        self, path: Path, source: dict[str, object], *, filename: str
    ) -> bool:
        changed = False
        for key, source_value in source.items():
            original = path.read_text(encoding="utf-8")
            sanitized = _jsonc_for_parsing(original)
            target = self._parse_jsonc_object(original, description=str(path))
            if key not in target:
                updated = self._insert_property(original, sanitized, key, source_value)
                self._atomic_write(path, updated)
                changed = True
                continue
            target_value = target[key]
            if not isinstance(source_value, list) or not isinstance(target_value, list):
                continue
            for item in source_value:
                original = path.read_text(encoding="utf-8")
                sanitized = _jsonc_for_parsing(original)
                target = self._parse_jsonc_object(original, description=str(path))
                current = target[key]
                if not isinstance(current, list) or self._list_contains(
                    current, item, tasks=filename == "tasks.json" and key == "tasks"
                ):
                    continue
                self._atomic_write(path, self._append_array_item(original, sanitized, key, item))
                changed = True
        return changed

    def _reconcile_object(
        self, path: Path, before: dict[str, object], after: dict[str, object]
    ) -> None:
        for key in before.keys() | after.keys():
            if before.get(key, _MISSING) == after.get(key, _MISSING):
                continue
            original = path.read_text(encoding="utf-8")
            sanitized = _jsonc_for_parsing(original)
            if key not in before:
                updated = self._insert_property(original, sanitized, key, after[key])
            elif key not in after:
                updated = self._remove_property(original, sanitized, key)
            else:
                updated = self._replace_property(original, sanitized, key, after[key])
            self._atomic_write(path, updated)

    @staticmethod
    def _replace_property(original: str, sanitized: str, key: str, value: object) -> str:
        properties = _object_properties(sanitized)
        if key not in properties:
            raise InvalidConfigError(f"Cannot locate {key} in VS Code configuration.")
        _, value_start, value_end, _ = properties[key]
        line_start = original.rfind("\n", 0, value_start) + 1
        indent_match = re.match(r"\s*", original[line_start:value_start])
        indent = indent_match.group(0) if indent_match else ""
        rendered = json.dumps(value, indent=2, ensure_ascii=False).replace("\n", f"\n{indent}")
        return original[:value_start] + rendered + original[value_end:]

    @staticmethod
    def _remove_property(original: str, sanitized: str, key: str) -> str:
        properties = _object_properties(sanitized)
        if key not in properties:
            return original
        key_start, _, value_end, comma = properties[key]
        if comma is not None:
            return original[:key_start] + original[comma + 1 :]
        previous_commas = [
            item_comma
            for item_key, (_, _, _, item_comma) in properties.items()
            if item_key != key and item_comma is not None and item_comma < key_start
        ]
        if previous_commas:
            previous_comma = max(previous_commas)
            return (
                original[:previous_comma]
                + original[previous_comma + 1 : key_start]
                + original[value_end:]
            )
        closing = _matching_bracket(sanitized, sanitized.find("{"))
        trailing_comma = original.find(",", value_end, closing)
        end = trailing_comma + 1 if trailing_comma >= 0 else value_end
        return original[:key_start] + original[end:]

    @classmethod
    def _three_way_file(
        cls, base: object, local: object, remote: object, *, filename: str
    ) -> tuple[object, bool]:
        if local == base:
            return remote, False
        if remote == base or local == remote:
            return local, False
        if any(value is _MISSING for value in (base, local, remote)):
            return local, True
        if not all(isinstance(value, dict) for value in (base, local, remote)):
            return local, True

        merged = dict(local)
        conflict = False
        keys = set(base) | set(local) | set(remote)
        for key in keys:
            base_value = base.get(key, _MISSING)
            local_value = local.get(key, _MISSING)
            remote_value = remote.get(key, _MISSING)
            if all(isinstance(value, list) for value in (base_value, local_value, remote_value)):
                value, item_conflict = cls._three_way_list(
                    base_value,
                    local_value,
                    remote_value,
                    tasks=filename == "tasks.json" and key == "tasks",
                )
            else:
                value, item_conflict = cls._three_way_value(
                    base_value, local_value, remote_value
                )
            conflict |= item_conflict
            if value is _MISSING:
                merged.pop(key, None)
            else:
                merged[key] = value
        return merged, conflict

    @staticmethod
    def _three_way_value(base: object, local: object, remote: object) -> tuple[object, bool]:
        if local == base:
            return remote, False
        if remote == base or local == remote:
            return local, False
        return local, True

    @classmethod
    def _three_way_list(
        cls,
        base: list[object],
        local: list[object],
        remote: list[object],
        *,
        tasks: bool,
    ) -> tuple[list[object], bool]:
        if not tasks:
            result = list(local)
            for item in base:
                if item not in remote and item in result:
                    result.remove(item)
            for item in remote:
                if item not in base and item not in result:
                    result.append(item)
            return result, False

        def identity(item: object) -> str:
            if isinstance(item, dict) and isinstance(item.get("label"), str):
                return f"label:{item['label']}"
            return f"value:{json.dumps(item, sort_keys=True, ensure_ascii=False)}"

        base_items = {identity(item): item for item in base}
        local_items = {identity(item): item for item in local}
        remote_items = {identity(item): item for item in remote}
        merged_items: dict[str, object] = dict(local_items)
        conflict = False
        for item_id in set(base_items) | set(local_items) | set(remote_items):
            value, item_conflict = cls._three_way_value(
                base_items.get(item_id, _MISSING),
                local_items.get(item_id, _MISSING),
                remote_items.get(item_id, _MISSING),
            )
            conflict |= item_conflict
            if value is _MISSING:
                merged_items.pop(item_id, None)
            else:
                merged_items[item_id] = value
        order = [identity(item) for item in local]
        order.extend(item_id for item_id in remote_items if item_id not in order)
        return [merged_items[item_id] for item_id in order if item_id in merged_items], conflict

    @staticmethod
    def _list_contains(existing: list[object], item: object, *, tasks: bool) -> bool:
        if item in existing:
            return True
        if not tasks or not isinstance(item, dict) or not isinstance(item.get("label"), str):
            return False
        return any(
            isinstance(candidate, dict) and candidate.get("label") == item["label"]
            for candidate in existing
        )

    @staticmethod
    def _insert_property(original: str, sanitized: str, key: str, value: object) -> str:
        opening = sanitized.find("{")
        if opening < 0:
            raise InvalidConfigError("Invalid VS Code JSON object.")
        closing = _matching_bracket(sanitized, opening)
        newline = "\r\n" if "\r\n" in original else "\n"
        indent = "  "
        populated = bool(sanitized[opening + 1 : closing].strip())
        comma = "," if populated else ""
        rendered = json.dumps(value, indent=2, ensure_ascii=False)
        rendered = rendered.replace("\n", f"\n{indent}")
        addition = f'{newline}{indent}{json.dumps(key)}: {rendered}{comma}'
        return original[: opening + 1] + addition + original[opening + 1 :]

    @staticmethod
    def _append_array_item(
        original: str, sanitized: str, key: str, value: object
    ) -> str:
        key_match = re.search(rf"{re.escape(json.dumps(key))}\s*:", sanitized)
        if key_match is None:
            raise InvalidConfigError(f"Cannot locate {key} in VS Code configuration.")
        opening = sanitized.find("[", key_match.end())
        if opening < 0:
            raise InvalidConfigError(f"{key} in VS Code configuration must be an array.")
        closing = _matching_bracket(sanitized, opening)
        newline = "\r\n" if "\r\n" in original else "\n"
        line_start = original.rfind("\n", 0, key_match.start()) + 1
        base_indent_match = re.match(r"\s*", original[line_start : key_match.start()])
        base_indent = base_indent_match.group(0) if base_indent_match else ""
        item_indent = base_indent + "  "
        rendered = json.dumps(value, indent=2, ensure_ascii=False)
        rendered = rendered.replace("\n", f"\n{item_indent}")
        item_ends = _array_item_ends(sanitized, opening, closing)
        if item_ends:
            insert_at = item_ends[-1]
            addition = f",{newline}{item_indent}{rendered}"
            return original[:insert_at] + addition + original[insert_at:]
        addition = f"{newline}{item_indent}{rendered}{newline}{base_indent}"
        return original[: opening + 1] + addition + original[closing:]

    @classmethod
    def _read_jsonc_object(cls, path: Path) -> dict[str, object]:
        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            raise InvalidConfigError(f"Cannot read {path}: {exc}") from exc
        return cls._parse_jsonc_object(content, description=str(path))

    @staticmethod
    def _parse_jsonc_object(content: str, *, description: str) -> dict[str, object]:
        try:
            parsed = json.loads(_jsonc_for_parsing(content))
        except json.JSONDecodeError as exc:
            raise InvalidConfigError(
                f"Cannot merge {description}: it is not valid JSON or JSONC.\nDetails: {exc}"
            ) from exc
        if not isinstance(parsed, dict):
            raise InvalidConfigError(f"{description} must contain a JSON object.")
        return parsed

    @staticmethod
    def _state_path(repository_root: Path) -> Path:
        return repository_root / ".marpme" / "vscode-template-state.json"

    @classmethod
    def _read_state(cls, repository_root: Path) -> dict[str, dict[str, object]] | None:
        path = cls._state_path(repository_root)
        if not path.is_file():
            return None
        try:
            raw: Any = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise InvalidConfigError(f"Invalid marpme VS Code state in {path}: {exc}") from exc
        if not isinstance(raw, dict) or raw.get("version") != VSCODE_STATE_VERSION:
            raise InvalidConfigError(f"Unsupported marpme VS Code state in {path}.")
        files = raw.get("files")
        if not isinstance(files, dict) or any(
            filename not in VSCODE_FILES or not isinstance(content, dict)
            for filename, content in files.items()
        ):
            raise InvalidConfigError(f"Invalid marpme VS Code state in {path}.")
        return files

    @classmethod
    def _write_state(
        cls, repository_root: Path, configuration: Mapping[str, dict[str, object]]
    ) -> None:
        content = json.dumps(
            {"version": VSCODE_STATE_VERSION, "files": configuration},
            indent=2,
            ensure_ascii=False,
            sort_keys=True,
        )
        cls._atomic_write(cls._state_path(repository_root), content + "\n")

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
