#!/usr/bin/env python3
"""Check local Markdown links and heading fragments without network access."""
from __future__ import annotations

import argparse
import html
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence
from urllib.parse import unquote, urlsplit

from voice_replication_kit.cli import build_parser


SKIPPED_DIRECTORIES = {
    ".git",
    ".superpowers",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "private",
}

INLINE_LINK = re.compile(
    r"!?\[[^\]]*\]\(\s*(?P<target><[^>]+>|[^\s)]+)"
    r"(?:\s+(?:\"[^\"]*\"|'[^']*'))?\s*\)"
)
REFERENCE_USE = re.compile(
    r"!?\[(?P<text>[^\]]+)\]\[(?P<label>[^\]]*)\]"
)
REFERENCE_DEFINITION = re.compile(
    r"^\s*\[(?P<label>[^\]]+)\]:\s*(?P<target><[^>]+>|\S+)"
)
HEADING = re.compile(r"^\s{0,3}#{1,6}\s+(?P<text>.+?)\s*#*\s*$")
SHELL_FENCE = re.compile(r"^\s*```(?P<language>powershell|pwsh|bash|sh)\s*$", re.I)
ENVIRONMENT_ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=.*$", re.S)


@dataclass(frozen=True)
class Finding:
    source: Path
    line: int
    detail: str


def _markdown_files(root: Path) -> list[Path]:
    return sorted(
        path
        for path in root.rglob("*.md")
        if path.is_file()
        and not any(part in SKIPPED_DIRECTORIES for part in path.relative_to(root).parts)
    )


def _slug(value: str) -> str:
    value = html.unescape(value).lower()
    value = re.sub(r"!?\[([^\]]+)\]\([^)]*\)", r"\1", value)
    value = re.sub(r"[`*_~]", "", value)
    value = re.sub(r"[^\w\- ]", "", value)
    return re.sub(r"\s+", "-", value.strip())


def _heading_slugs(path: Path) -> set[str]:
    counts: dict[str, int] = {}
    slugs: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        match = HEADING.match(line)
        if not match:
            continue
        base = _slug(match.group("text"))
        suffix = counts.get(base, 0)
        counts[base] = suffix + 1
        slugs.add(base if suffix == 0 else f"{base}-{suffix}")
    return slugs


def _target_value(raw: str) -> str:
    value = raw.strip()
    if value.startswith("<") and value.endswith(">"):
        value = value[1:-1]
    return unquote(value)


def _is_external(target: str) -> bool:
    return urlsplit(target).scheme.lower() in {"http", "https", "mailto"}


def _resolve_target(root: Path, source: Path, target: str) -> tuple[Path, str]:
    path_text, separator, fragment = target.partition("#")
    if path_text.startswith("/"):
        path = root / path_text.lstrip("/")
    elif path_text:
        path = source.parent / path_text
    else:
        path = source
    return path.resolve(), fragment if separator else ""


def _line_links(lines: Sequence[str]) -> Iterable[tuple[int, str]]:
    definitions: dict[str, str] = {}
    fenced = False
    for line in lines:
        if line.lstrip().startswith("```"):
            fenced = not fenced
            continue
        if fenced:
            continue
        match = REFERENCE_DEFINITION.match(line)
        if match:
            definitions[match.group("label").strip().lower()] = _target_value(
                match.group("target")
            )

    fenced = False
    for line_number, line in enumerate(lines, 1):
        if line.lstrip().startswith("```"):
            fenced = not fenced
            continue
        if fenced or REFERENCE_DEFINITION.match(line):
            continue
        for match in INLINE_LINK.finditer(line):
            yield line_number, _target_value(match.group("target"))
        for match in REFERENCE_USE.finditer(line):
            label = (match.group("label") or match.group("text")).strip().lower()
            target = definitions.get(label)
            if target is None:
                yield line_number, f"reference:{label}"
            else:
                yield line_number, target


def _voice_kit_surface() -> tuple[set[str], dict[str, set[str]]]:
    parser = build_parser()
    root_flags = {
        option
        for action in parser._actions
        for option in action.option_strings
        if option.startswith("--")
    }
    subparsers = next(
        action
        for action in parser._actions
        if isinstance(action, argparse._SubParsersAction)
    )
    surfaces: dict[str, set[str]] = {}
    for command, command_parser in subparsers.choices.items():
        surfaces[command] = {
            option
            for action in command_parser._actions
            for option in action.option_strings
            if option.startswith("--")
        }
    return root_flags, surfaces


def _shell_commands(lines: Sequence[str]) -> Iterable[tuple[int, str, str]]:
    language = ""
    start_line = 0
    logical: list[str] = []
    for line_number, line in enumerate(lines, 1):
        if not language:
            match = SHELL_FENCE.match(line)
            if match:
                language = match.group("language").lower()
            continue
        if line.lstrip().startswith("```"):
            if logical:
                yield start_line, language, " ".join(logical)
            language = ""
            logical = []
            continue

        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            if logical:
                yield start_line, language, " ".join(logical)
                logical = []
            continue
        if not logical:
            start_line = line_number
        continuation = (
            stripped.endswith("`")
            if language in {"powershell", "pwsh"}
            else stripped.endswith("\\")
        )
        logical.append(stripped[:-1].rstrip() if continuation else stripped)
        if not continuation:
            yield start_line, language, " ".join(logical)
            logical = []


def _shell_segments(command_line: str, language: str) -> list[str]:
    segments: list[str] = []
    current: list[str] = []
    quote = ""
    index = 0
    escape = "`" if language in {"powershell", "pwsh"} else "\\"

    def finish() -> None:
        value = "".join(current).strip()
        if value:
            segments.append(value)
        current.clear()

    while index < len(command_line):
        character = command_line[index]
        if character == escape and quote != "'":
            current.append(character)
            index += 1
            if index < len(command_line):
                current.append(command_line[index])
                index += 1
            continue
        if quote:
            current.append(character)
            if character == quote:
                quote = ""
            index += 1
            continue
        if character in {"'", '"'}:
            quote = character
            current.append(character)
            index += 1
            continue
        if character == "#" and (
            not current or current[-1].isspace()
        ):
            break
        pair = command_line[index : index + 2]
        if pair in {"&&", "||"}:
            finish()
            index += 2
            continue
        if character in {";", "|"}:
            finish()
            index += 1
            continue
        if character == "&":
            if language in {"powershell", "pwsh"} and not "".join(current).strip():
                current.append(character)
            else:
                finish()
            index += 1
            continue
        current.append(character)
        index += 1
    finish()
    return segments


def _shell_tokens(segment: str, language: str) -> list[str]:
    tokens: list[str] = []
    current: list[str] = []
    quote = ""
    index = 0
    escape = "`" if language in {"powershell", "pwsh"} else "\\"

    def finish() -> None:
        if current:
            tokens.append("".join(current))
            current.clear()

    while index < len(segment):
        character = segment[index]
        if character == escape and quote != "'":
            index += 1
            if index < len(segment):
                current.append(segment[index])
                index += 1
            continue
        if quote:
            if character == quote:
                quote = ""
            else:
                current.append(character)
            index += 1
            continue
        if character in {"'", '"'}:
            quote = character
            index += 1
            continue
        if character.isspace():
            finish()
            index += 1
            continue
        current.append(character)
        index += 1
    finish()
    return tokens


def _basename(token: str) -> str:
    return token.replace("\\", "/").rsplit("/", 1)[-1].lower()


def _voice_kit_index(tokens: Sequence[str]) -> int | None:
    index = 0
    while index < len(tokens) and ENVIRONMENT_ASSIGNMENT.fullmatch(tokens[index]):
        index += 1
    if index < len(tokens) and tokens[index] == "&":
        index += 1
    if index < len(tokens) and _basename(tokens[index]) in {"voice-kit", "voice-kit.exe"}:
        return index

    if index < len(tokens) and _basename(tokens[index]) == "env":
        index += 1
        while index < len(tokens) and ENVIRONMENT_ASSIGNMENT.fullmatch(tokens[index]):
            index += 1
        if index < len(tokens) and _basename(tokens[index]) in {"voice-kit", "voice-kit.exe"}:
            return index

    if index < len(tokens) and _basename(tokens[index]) in {"wsl", "wsl.exe"}:
        index += 1
        if index < len(tokens) and _basename(tokens[index]) == "env":
            index += 1
            while index < len(tokens) and ENVIRONMENT_ASSIGNMENT.fullmatch(tokens[index]):
                index += 1
        if index < len(tokens) and _basename(tokens[index]) in {"voice-kit", "voice-kit.exe"}:
            return index
    return None


def _voice_kit_invocations(
    command_line: str, language: str
) -> Iterable[tuple[str, list[str]]]:
    for segment in _shell_segments(command_line, language):
        tokens = _shell_tokens(segment, language)
        executable = _voice_kit_index(tokens)
        if executable is None or executable + 1 >= len(tokens):
            continue
        command = tokens[executable + 1]
        flags = [
            token.partition("=")[0]
            for token in tokens[executable + 2 :]
            if token.startswith("--")
        ]
        yield command, flags


def _command_findings(source: Path, lines: Sequence[str]) -> Iterable[Finding]:
    root_flags, surfaces = _voice_kit_surface()
    for line_number, language, command_line in _shell_commands(lines):
        for command, flags in _voice_kit_invocations(command_line, language):
            if command.startswith("--"):
                if command not in root_flags:
                    yield Finding(
                        source,
                        line_number,
                        f"unsupported flag for voice-kit: {command}",
                    )
                continue
            if command not in surfaces:
                yield Finding(
                    source,
                    line_number,
                    f"unsupported voice-kit command: {command}",
                )
                continue
            for flag in flags:
                if flag not in surfaces[command]:
                    yield Finding(
                        source,
                        line_number,
                        f"unsupported flag for voice-kit {command}: {flag}",
                    )


def check_links(root: Path) -> tuple[list[Finding], int, int]:
    root = Path(root).resolve()
    files = _markdown_files(root)
    findings: list[Finding] = []
    local_links = 0
    headings: dict[Path, set[str]] = {}

    for source in files:
        relative = source.relative_to(root)
        lines = source.read_text(encoding="utf-8").splitlines()
        findings.extend(_command_findings(relative, lines))
        for line_number, target in _line_links(lines):
            if target.startswith("reference:"):
                findings.append(
                    Finding(
                        relative,
                        line_number,
                        f"missing reference definition: {target.removeprefix('reference:')}",
                    )
                )
                continue
            if _is_external(target):
                continue
            local_links += 1
            resolved, fragment = _resolve_target(root, source, target)
            try:
                resolved.relative_to(root)
            except ValueError:
                findings.append(
                    Finding(relative, line_number, f"target escapes root: {target}")
                )
                continue
            if not resolved.exists():
                findings.append(
                    Finding(relative, line_number, f"missing target: {target}")
                )
                continue
            if fragment and resolved.suffix.lower() == ".md":
                available = headings.setdefault(resolved, _heading_slugs(resolved))
                if fragment.lower() not in available:
                    findings.append(
                        Finding(relative, line_number, f"missing heading: {target}")
                    )

    return findings, len(files), local_links


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="repository root",
    )
    args = parser.parse_args(argv)

    if not args.root.resolve().is_dir():
        print("repository root is not a directory")
        return 2
    findings, file_count, link_count = check_links(args.root)
    if findings:
        for finding in findings:
            print(f"{finding.source.as_posix()}:{finding.line}: {finding.detail}")
        return 1
    print(
        f"link check passed ({file_count} Markdown files, "
        f"{link_count} local {'link' if link_count == 1 else 'links'})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
