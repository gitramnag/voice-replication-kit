"""Fail-closed checks for files that must never enter the public repository."""
from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
from html.parser import HTMLParser
import json
import os
import re
import subprocess
from dataclasses import dataclass
from dataclasses import field
from pathlib import Path, PurePosixPath
from typing import Iterable, Mapping, Sequence
from xml.etree import ElementTree

from voice_replication_kit.audit_sources import (
    AuditEntry,
    AuditSourceError,
    history_entries,
    ignored_paths,
    index_entries,
    tree_entries,
)
from voice_replication_kit.public_formats import (
    decoded_scorecard_text,
    detect_signature,
    validate_blank_scorecard,
    validate_public_png,
)


MAX_PUBLIC_BYTES = 100 * 1024 * 1024
HISTORY_EXCEPTIONS_PATH = Path("configs/reviewed-history-exceptions.json")
IGNORED_BROWSER_PROFILE_ROOTS = (
    PurePosixPath(".impeccable/edge-review"),
    PurePosixPath(".impeccable/edge-review-mobile"),
    PurePosixPath(".impeccable/edge-review-svg"),
)
ALLOWED_IGNORED_PATHS = frozenset(
    {
        PurePosixPath(".impeccable/review/desktop.png"),
        PurePosixPath(".impeccable/review/mobile.png"),
        PurePosixPath(".impeccable/review/standalone-svg.png"),
    }
)
IGNORED_WORKFLOW_ROOTS = (
    PurePosixPath(".superpowers"),
    PurePosixPath(".impeccable"),
)
IGNORED_PRIVATE_MARKER_NAMES = frozenset(
    {".voice-replication-private.json", ".voice-kit-private-terms"}
)
LOCAL_SECRET_EXTENSIONS = frozenset({".key", ".pem", ".token"})
SENSITIVE_BROWSER_NAMES = frozenset(
    {
        "cookies",
        "history",
        "login data",
        "local state",
        "preferences",
        "secure preferences",
        "web data",
    }
)
SENSITIVE_BROWSER_DIRECTORIES = frozenset(
    {"local storage", "session storage", "sessions"}
)

FORBIDDEN_EXTENSIONS = {
    ".7z",
    ".aac",
    ".bin",
    ".bz2",
    ".ckpt",
    ".db",
    ".dll",
    ".dylib",
    ".exe",
    ".flac",
    ".gguf",
    ".gz",
    ".joblib",
    ".key",
    ".m4a",
    ".mov",
    ".mp3",
    ".mp4",
    ".msi",
    ".npy",
    ".npz",
    ".ogg",
    ".onnx",
    ".opus",
    ".pem",
    ".pickle",
    ".pkl",
    ".pb",
    ".pt",
    ".pth",
    ".pyc",
    ".pyo",
    ".rar",
    ".safetensors",
    ".so",
    ".sqlite",
    ".sqlite3",
    ".tar",
    ".tgz",
    ".tflite",
    ".token",
    ".wav",
    ".webm",
    ".xz",
    ".zip",
    ".zst",
}

FORBIDDEN_NAMES = {".env"}

ALLOWED_PNGS = frozenset(
    {
        PurePosixPath("docs/assets/voice-replication-studio-journey.png"),
    }
)
RETIRED_HISTORY_DIAGRAM_PNGS = frozenset(
    {
        PurePosixPath("docs/assets/voice-replication-one-view-transit.png"),
        PurePosixPath("docs/assets/voice-replication-one-view-control-plane.png"),
        PurePosixPath("docs/assets/voice-replication-one-view-field-atlas.png"),
        PurePosixPath("docs/assets/voice-replication-architecture-github.png"),
        PurePosixPath("docs/assets/voice-replication-architecture-presentation.png"),
        PurePosixPath("docs/assets/voice-replication-architecture-social.png"),
        PurePosixPath("docs/assets/voice-replication-first-build-github.png"),
        PurePosixPath("docs/assets/voice-replication-first-build-presentation.png"),
        PurePosixPath("docs/assets/voice-replication-first-build-social.png"),
        PurePosixPath("docs/assets/voice-replication-repeat-workflow-github.png"),
        PurePosixPath("docs/assets/voice-replication-repeat-workflow-presentation.png"),
        PurePosixPath("docs/assets/voice-replication-repeat-workflow-social.png"),
    }
)
ALLOWED_XLSX = frozenset(
    {PurePosixPath("evaluation/voice-evaluation-scorecard.xlsx")}
)
ALLOWED_FONTS = {
    PurePosixPath("docs/assets/fonts/source-sans-3-latin.woff2"): (
        "19143dca075972bc84e3fd9eab7416dd40cc565dccb2435a044bdfabe060c7d5"
    ),
    PurePosixPath("docs/assets/fonts/source-sans-3-variable.ttf"): (
        "042fe2cc0b933e328410d7acbd0aa6a1873dca5aef81875f4bc214b08825c7b9"
    ),
    PurePosixPath("docs/assets/fonts/source-serif-4-latin.woff2"): (
        "382475f38242c52d42a3e5ff8dc69b5d73f10d0d21e4550b5fe232984688779a"
    ),
    PurePosixPath("docs/assets/fonts/source-serif-4-variable.ttf"): (
        "97b2d4da6e3cb494b5a1e66ae176914d852ccabef49e0c02c0df25f3e39aca0b"
    ),
}

TEXT_EXTENSIONS = {
    ".cfg",
    ".cmd",
    ".csv",
    ".html",
    ".ini",
    ".json",
    ".jsonl",
    ".md",
    ".ps1",
    ".py",
    ".sh",
    ".svg",
    ".toml",
    ".txt",
    ".yaml",
    ".yml",
}

SKIPPED_DIRECTORIES = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
}

PRIVATE_TOP_LEVEL_DIRECTORIES = {"private", "profiles", "speakers"}
PRIVATE_PATH_SEQUENCES = {
    ("results", "raw"),
    ("runtime", "cache"),
    ("runtime", "models"),
    ("upload", "refs"),
}

PERSONAL_PATH_PATTERNS = (
    re.compile(r"(?i)\b[A-Z]:\\Users\\[^\\\x00-\x1f]+\\"),
    re.compile(r"(?i)\b[A-Z]:(?:\\\\)Users(?:\\\\)[^\\\x00-\x1f]+(?:\\\\)"),
    re.compile(r"(?i)(?<![\w.-])/" "home" r"/[^/\s]+/"),
    re.compile(r"(?i)(?<![\w.-])/" "Users" r"/[^/\s]+/"),
    re.compile(r"(?i)(?<![\w.-])/" "mnt" r"/[a-z]/" "Users" r"/[^/\s]+/"),
    re.compile(r"(?i)(?<![\w.-])[a-z]--" "Users" r"-[^-\s]+-"),
    re.compile(r"(?<![\w.-])~[/\\]"),
)

APPROVED_EMAILS = {
    "315322897+gitramnag@users.noreply.github.com",
}
APPROVED_GIT_NAME = "gitramnag"
APPROVED_GIT_EMAIL = "315322897+gitramnag@users.noreply.github.com"
GIT_IDENTITY_PATTERN = re.compile(r"^(.+?) <([^<>]+)> \d+ [+-]\d{4}$")
HISTORY_OBJECT_ID_PATTERN = re.compile(r"[0-9a-f]{40}")
REVIEWABLE_HISTORY_FINDING_CODES = frozenset(
    {
        "credential-content",
        "identity-content",
        "personal-path-in-text",
        "unapproved-binary",
        "unsafe-markup",
        "unsafe-xlsx",
    }
)
EMAIL_PATTERN = re.compile(
    r"(?i)(?<![\w.+-])([a-z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-z0-9.-]+\.[a-z]{2,})(?![\w.-])"
)
CREDENTIAL_PATTERNS = (
    re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----"),
    re.compile(r"(?i)\b(?:gh[pousr]_|github_pat_)[A-Za-z0-9_]{20,}"),
    re.compile(r"\bAKIA[A-Z0-9]{16}\b"),
    re.compile(r"(?i)\bAIza[0-9A-Za-z_-]{30,}"),
    re.compile(r"(?i)\bxox[baprs]-[0-9A-Za-z-]{10,}"),
    re.compile(r"(?i)\bsk_live_[0-9A-Za-z]{12,}"),
    re.compile(
        r"(?i)(?<![A-Za-z0-9_-])Bearer[ \t]+"
        r"[A-Za-z0-9._~+/=-]{16,}(?![A-Za-z0-9._~+/=-])"
    ),
    re.compile(
        r"(?<![A-Za-z0-9_-])[A-Za-z0-9_-]{10,}\."
        r"[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{16,}(?![A-Za-z0-9_-])"
    ),
    re.compile(
        r"(?<![\w-])(?i:API[_-]?KEY|TOKEN|SECRET|PASSWORD)\b"
        r"[ \t]*[:=][ \t]*"
        r"(?:[\"'][A-Za-z0-9._~+/=-]{12,}[\"']|"
        r"(?=[A-Za-z0-9._~+/=-]{12,}(?![A-Za-z0-9._~+/=-]))"
        r"(?=[A-Za-z0-9._~+/=-]*(?:[A-Z0-9.+/~=-]))"
        r"[A-Za-z0-9._~+/=-]{12,}(?![ \t]*\())"
    ),
    re.compile(
        r"(?i)\bAWS_SECRET_ACCESS_KEY[ \t]*[:=][ \t]*[\"']?"
        r"[A-Za-z0-9/+=]{40}(?![A-Za-z0-9/+=])"
    ),
    re.compile(r"(?i)\bsk-(?:proj|svcacct)-[A-Za-z0-9_-]{20,}"),
    re.compile(r"(?i)\bsk-ant-api[0-9]{2}-[A-Za-z0-9_-]{20,}"),
    re.compile(r"(?i)\bhf_[A-Za-z0-9]{20,}"),
    re.compile(r"(?i)\brk_live_[0-9A-Za-z]{12,}"),
    re.compile(r"(?i)\b[a-z][a-z0-9+.-]*://[^/@\s:]+:[^/@\s]+@"),
)
MARKUP_PATTERNS = (
    re.compile(r"(?i)<\s*script\b"),
    re.compile(r"(?i)<[^>]+\son[a-z]+\s*="),
    re.compile(r"(?i)https?://"),
    re.compile(r"(?i)//fonts\."),
    re.compile(r"(?i)data:(?:audio|video)"),
)
SAFE_XMLNS_PATTERN = re.compile(
    r'''(?i)\bxmlns(?:\:[\w.-]+)?\s*=\s*(?:"http://www\.w3\.org/(?:2000/svg|1999/xlink)"|'http://www\.w3\.org/(?:2000/svg|1999/xlink)')'''
)

SAFE_MARKUP_TAGS = {
    "body",
    "circle",
    "defs",
    "desc",
    "g",
    "head",
    "html",
    "line",
    "main",
    "marker",
    "meta",
    "path",
    "rect",
    "style",
    "svg",
    "text",
    "title",
    "tspan",
}
SAFE_MARKUP_ATTRIBUTES = {
    "aria-hidden",
    "aria-label",
    "aria-labelledby",
    "charset",
    "class",
    "content",
    "cx",
    "cy",
    "d",
    "data-flow",
    "data-grammar",
    "data-layout",
    "data-node-id",
    "data-background",
    "data-collision",
    "data-connector",
    "data-copy",
    "data-geometry-id",
    "data-moment",
    "data-obstacle",
    "data-pictogram",
    "data-privacy-seam",
    "data-region",
    "data-region-box",
    "data-repeat-loop",
    "data-source",
    "data-system-rule",
    "data-target",
    "data-text",
    "data-visible",
    "data-zone",
    "dy",
    "fill",
    "fill-opacity",
    "font-size",
    "height",
    "id",
    "lang",
    "marker-end",
    "markerheight",
    "markerunits",
    "markerwidth",
    "name",
    "orient",
    "r",
    "refx",
    "refy",
    "role",
    "rx",
    "stroke",
    "stroke-linecap",
    "stroke-opacity",
    "stroke-width",
    "text-anchor",
    "transform",
    "viewbox",
    "width",
    "x",
    "x1",
    "x2",
    "xmlns",
    "y",
    "y1",
    "y2",
}
SCRIPTABLE_VALUE_PATTERN = re.compile(
    r"(?i)(?:^|[\s;(])(?:javascript|vbscript|data)\s*:|https?\s*:|^\s*//"
)
CSS_ACTIVE_PATTERN = re.compile(
    r"(?i)@import\b|url\s*\(|expression\s*\(|javascript\s*:|vbscript\s*:|data\s*:"
)
CSS_OBFUSCATION_PATTERN = re.compile(r"\\|/\*|\*/")
LOCAL_MARKER_PATTERN = re.compile(r"url\(#[A-Za-z_][A-Za-z0-9_.:-]*\)")
EMBEDDED_WOFF2_PATTERN = re.compile(
    r"url\(data:font/woff2;base64,([A-Za-z0-9+/]+={0,2})\)", re.IGNORECASE
)
DATA_AUDIO_PATTERN = re.compile(
    r"(?i)data:" "audio" r"(?:/[a-z0-9.+-]+)?(?:;[^,\s]+)*,"
)
LONG_BASE64_PATTERN = re.compile(
    r"(?<![A-Za-z0-9+/=])[A-Za-z0-9+/]{512,}={0,2}(?![A-Za-z0-9+/=])"
)
LONG_HEX_PATTERN = re.compile(r"(?<![0-9A-Fa-f])[0-9A-Fa-f]{512,}(?![0-9A-Fa-f])")
PRIVATE_STRUCTURED_KEYS = frozenset(
    {
        "previous_record_sha256",
        "record_sha256",
        "reference_sha256",
        "reference_text",
        "reference_text_sha256",
        "speaker_embedding",
        "unblinding",
        "voice_embedding",
    }
)
PRIVATE_STRUCTURED_TEXT_SUFFIXES = frozenset({".md", ".txt"})
EMPTY_PRIVATE_STRUCTURED_TEXT_VALUES = frozenset(
    {"", '""', "''", "[]", "{}", "null", "none", "~"}
)
APPROVED_SCHEMA_TEXT_VALUES = frozenset(
    {
        ("configs/schemas/example.md", "reference_text", "{ type: string }"),
        (
            "evaluation/schemas/example.txt",
            "record_sha256",
            "lowercase sha-256 string",
        ),
    }
)
APPROVED_JSON_SCHEMA_PATHS = frozenset(
    {
        "configs/schemas/evaluation-plan.schema.json",
        "configs/schemas/private-profile.schema.json",
        "configs/schemas/production-document.schema.json",
        "configs/schemas/request.schema.json",
        "evaluation/schemas/scorecard.schema.json",
    }
)
PRIVATE_SCHEMA_VALUE_KEYWORDS = frozenset(
    {"const", "default", "enum", "example", "examples"}
)
PRIVATE_STRUCTURED_KEY_PATTERN = "|".join(
    re.escape(key) for key in sorted(PRIVATE_STRUCTURED_KEYS)
)
PRIVATE_STRUCTURED_LINE_PATTERN = re.compile(
    r"^[ \t]*(?:>[ \t]*)*(?:[-*+][ \t]+)?(?P<quote>[\"']?)"
    rf"(?P<key>{PRIVATE_STRUCTURED_KEY_PATTERN})"
    r"(?P=quote)[ \t]*[:=][ \t]*(?P<value>.*?)[ \t]*$",
    re.IGNORECASE,
)
PRIVATE_STRUCTURED_TABLE_PATTERN = re.compile(
    r"^[ \t]*\|[ \t]*(?P<quote>[\"']?)"
    rf"(?P<key>{PRIVATE_STRUCTURED_KEY_PATTERN})"
    r"(?P=quote)[ \t]*\|[ \t]*(?P<value>[^|]*?)[ \t]*\|(?:.*\|)?[ \t]*$",
    re.IGNORECASE,
)
PRIVATE_WORKFLOW_FILENAMES = frozenset(
    {
        "blind-candidates.jsonl",
        "evaluation-plan.json",
        "manifest.jsonl",
        "matrix.jsonl",
        "requests.jsonl",
        "unblinding-map.json",
    }
)


@dataclass(frozen=True, order=True)
class Finding:
    """One publication boundary violation."""

    code: str
    path: Path
    detail: str


def _path_is_beneath(path: PurePosixPath, root: PurePosixPath) -> bool:
    path_parts = tuple(part.casefold() for part in path.parts)
    root_parts = tuple(part.casefold() for part in root.parts)
    return path_parts[: len(root_parts)] == root_parts


def _has_forbidden_name(path: PurePosixPath) -> bool:
    name = path.name.casefold()
    return name in FORBIDDEN_NAMES or (
        name.startswith(".env.") and name != ".env.example"
    )


def _private_path_boundary(path: PurePosixPath) -> PurePosixPath | None:
    if not _is_private_path(Path(*path.parts)):
        return None
    lowered = tuple(part.casefold() for part in path.parts)
    if lowered and lowered[0] in PRIVATE_TOP_LEVEL_DIRECTORIES:
        return PurePosixPath(path.parts[0])
    if path.name.casefold() in {"private-profile.json", "private-profile.yaml"}:
        return path
    for sequence in PRIVATE_PATH_SEQUENCES:
        for index in range(len(lowered) - len(sequence) + 1):
            if lowered[index : index + len(sequence)] == sequence:
                return PurePosixPath(*path.parts[: index + len(sequence)])
    return None


def scan_ignored_release_paths(paths: Iterable[PurePosixPath]) -> list[Finding]:
    """Reject ignored release residue by path name without reading private bytes."""
    inventory = sorted(set(paths), key=PurePosixPath.as_posix)
    findings: list[Finding] = []
    known_members = {
        path
        for path in inventory
        if ".venv" in {part.casefold() for part in path.parts[:-1]}
    }
    for root in IGNORED_BROWSER_PROFILE_ROOTS:
        members = {
            path
            for path in inventory
            if path not in known_members and _path_is_beneath(path, root)
        }
        if members:
            known_members.update(members)
            findings.append(
                Finding(
                    "ignored-browser-profile",
                    root,
                    "ignored browser profile root must remain outside the repository",
                )
            )
    known_members.update(path for path in inventory if path in ALLOWED_IGNORED_PATHS)
    for workflow_root in IGNORED_WORKFLOW_ROOTS:
        workflow_members = {
            path
            for path in inventory
            if path not in known_members and _path_is_beneath(path, workflow_root)
        }
        if workflow_members:
            known_members.update(workflow_members)
            findings.append(
                Finding(
                    "ignored-workflow-state",
                    workflow_root,
                    "ignored workflow state must remain outside the repository",
                )
            )
    private_boundaries: dict[PurePosixPath, set[PurePosixPath]] = {}
    for path in inventory:
        if path in known_members:
            continue
        boundary = _private_path_boundary(path)
        if boundary is not None:
            private_boundaries.setdefault(boundary, set()).add(path)
    for boundary, members in private_boundaries.items():
        known_members.update(members)
        findings.append(
            Finding(
                "ignored-private-path",
                boundary,
                "ignored private workflow path must remain outside the repository",
            )
        )
    for path in inventory:
        if path in known_members:
            continue
        lowered_parts = tuple(part.casefold() for part in path.parts)
        if path.suffix.casefold() in {".pyc", ".pyo"}:
            continue
        if path.name.casefold() in IGNORED_PRIVATE_MARKER_NAMES:
            findings.append(
                Finding(
                    "ignored-private-marker",
                    path,
                    "ignored private workflow marker must remain outside the repository",
                )
            )
        elif (
            _has_forbidden_name(path)
            or path.suffix.casefold() in LOCAL_SECRET_EXTENSIONS
        ):
            findings.append(
                Finding(
                    "ignored-local-secret",
                    path,
                    "ignored credential or local-secret path must remain outside the repository",
                )
            )
        elif path.suffix.casefold() in FORBIDDEN_EXTENSIONS:
            findings.append(
                Finding(
                    "ignored-private-artifact",
                    path,
                    "ignored private-capable artifact must remain outside the repository",
                )
            )
        if (
            path.name.casefold() in SENSITIVE_BROWSER_NAMES
            or any(part in SENSITIVE_BROWSER_DIRECTORIES for part in lowered_parts[:-1])
        ):
            findings.append(
                Finding(
                    "ignored-browser-state",
                    path,
                    "ignored browser database or session path must remain outside the repository",
                )
            )
    return sorted(findings, key=lambda item: (item.path.as_posix(), item.code))


@dataclass(frozen=True)
class AuditPolicy:
    """Publication rules applied to every byte source."""

    private_terms_file: Path | None = None
    allowed_pngs: frozenset[PurePosixPath] = field(default_factory=lambda: ALLOWED_PNGS)
    allowed_xlsx: frozenset[PurePosixPath] = field(default_factory=lambda: ALLOWED_XLSX)
    allowed_fonts: Mapping[PurePosixPath, str] = field(
        default_factory=lambda: ALLOWED_FONTS
    )


class PrivateTermsError(ValueError):
    """A private-term file could not be used without risking disclosure."""


@dataclass(frozen=True)
class HistoryException:
    """One reviewed historical blob finding accepted by exact object identity."""

    object_id: str
    finding_code: str
    reason: str


def _load_private_terms(path: Path | None) -> tuple[str, ...]:
    if path is None:
        return ()
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise PrivateTermsError("private terms file could not be read") from error
    terms = tuple(line.strip().casefold() for line in text.splitlines() if line.strip())
    if not terms:
        raise PrivateTermsError("private terms file must contain at least one term")
    return terms


def _resolved_private_terms_file(
    root: Path,
    supplied: Path | None,
    environ: Mapping[str, str],
) -> Path | None:
    configured = supplied
    if configured is None and environ.get("VOICE_KIT_PRIVATE_TERMS_FILE"):
        configured = Path(environ["VOICE_KIT_PRIVATE_TERMS_FILE"])
    if configured is None:
        return None
    try:
        path = configured.expanduser().resolve(strict=True)
    except OSError as error:
        raise PrivateTermsError("private terms file could not be read") from error
    if not path.is_file():
        raise PrivateTermsError("private terms file could not be read")
    boundary = root
    try:
        repository_probe = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--show-toplevel"],
            capture_output=True,
            check=False,
            text=True,
        )
    except OSError as error:
        raise PrivateTermsError("private terms file must remain external or ignored") from error
    if repository_probe.returncode == 0 and repository_probe.stdout.strip():
        try:
            repository = Path(repository_probe.stdout.strip()).resolve(strict=True)
            root.relative_to(repository)
        except (OSError, ValueError) as error:
            raise PrivateTermsError("private terms file must remain external or ignored") from error
        boundary = repository
    try:
        relative = path.relative_to(boundary)
    except ValueError:
        return path
    tracked = subprocess.run(
        ["git", "-C", str(boundary), "ls-files", "--error-unmatch", "--", relative.as_posix()],
        capture_output=True,
        check=False,
    )
    ignored = subprocess.run(
        ["git", "-C", str(boundary), "check-ignore", "-q", "--", relative.as_posix()],
        capture_output=True,
        check=False,
    )
    if tracked.returncode == 0 or ignored.returncode != 0:
        raise PrivateTermsError("private terms file must remain external or ignored")
    return path


def _is_private_path(relative: Path) -> bool:
    lowered = tuple(part.lower() for part in relative.parts)
    if lowered and lowered[0] in PRIVATE_TOP_LEVEL_DIRECTORIES:
        return True
    if len(lowered) >= 2 and lowered[:2] in {
        ("configs", "schemas"),
        ("evaluation", "schemas"),
    }:
        return False
    name = relative.name.casefold()
    if name in {"private-profile.json", "private-profile.yaml"}:
        return True
    if name in PRIVATE_WORKFLOW_FILENAMES:
        return True
    if name.startswith("private-profile") and name.endswith((".json", ".yaml", ".yml")):
        return True
    if name.startswith("production-script") and name.endswith(".json"):
        return True
    if (
        name.startswith("pass-")
        and name.endswith(".xlsx")
        and "evaluation" in lowered[:-1]
    ):
        return True
    return any(
        lowered[index : index + len(sequence)] == sequence
        for sequence in PRIVATE_PATH_SEQUENCES
        for index in range(len(lowered) - len(sequence) + 1)
    )


def _decoded_text(data: bytes) -> str | None:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return None
    return None if "\x00" in text else text


class _MalformedHtml(ValueError):
    pass


class _StrictHtmlParser(HTMLParser):
    _VOID_TAGS = {
        "area",
        "base",
        "br",
        "col",
        "embed",
        "hr",
        "img",
        "input",
        "link",
        "meta",
        "param",
        "source",
        "track",
        "wbr",
    }

    def __init__(self, allowed_font_hashes: frozenset[str]) -> None:
        super().__init__(convert_charrefs=True)
        self.stack: list[str] = []
        self.allowed_font_hashes = allowed_font_hashes

    def _validate_element(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> str:
        lowered = tag.casefold()
        if lowered not in SAFE_MARKUP_TAGS:
            raise _MalformedHtml("unsafe tag")
        names = [name.casefold() for name, _value in attrs]
        if len(names) != len(set(names)):
            raise _MalformedHtml("duplicate attribute")
        for (name, value), normalized in zip(attrs, names):
            if normalized.startswith("on") or normalized not in SAFE_MARKUP_ATTRIBUTES:
                raise _MalformedHtml("unsafe attribute")
            if not _markup_attribute_is_safe(normalized, value or ""):
                raise _MalformedHtml("unsafe attribute value")
        return lowered

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        lowered = self._validate_element(tag, attrs)
        if tag.casefold() not in self._VOID_TAGS:
            self.stack.append(lowered)

    def handle_startendtag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        self._validate_element(tag, attrs)

    def handle_endtag(self, tag: str) -> None:
        lowered = tag.casefold()
        if lowered in self._VOID_TAGS:
            return
        if not self.stack or self.stack[-1] != lowered:
            raise _MalformedHtml("mismatched tag")
        self.stack.pop()

    def handle_pi(self, _data: str) -> None:
        raise _MalformedHtml("processing instruction")

    def handle_decl(self, declaration: str) -> None:
        if declaration.strip().casefold() != "doctype html":
            raise _MalformedHtml("unsafe declaration")

    def handle_data(self, data: str) -> None:
        if self.stack and self.stack[-1] == "style" and _css_is_unsafe(
            data, self.allowed_font_hashes
        ):
            raise _MalformedHtml("unsafe CSS")


def _without_reviewed_embedded_fonts(
    text: str, allowed_font_hashes: frozenset[str]
) -> tuple[str, bool]:
    rejected = False

    def replace(match: re.Match[str]) -> str:
        nonlocal rejected
        try:
            data = base64.b64decode(match.group(1), validate=True)
        except (binascii.Error, ValueError):
            rejected = True
            return match.group(0)
        if not data.startswith(b"wOF2") or hashlib.sha256(data).hexdigest() not in (
            allowed_font_hashes
        ):
            rejected = True
            return match.group(0)
        return "reviewed-font"

    return EMBEDDED_WOFF2_PATTERN.sub(replace, text), rejected


def _css_is_unsafe(
    text: str, allowed_font_hashes: frozenset[str] = frozenset()
) -> bool:
    candidate, rejected_font = _without_reviewed_embedded_fonts(
        text, allowed_font_hashes
    )
    return (
        rejected_font
        or CSS_OBFUSCATION_PATTERN.search(candidate) is not None
        or CSS_ACTIVE_PATTERN.search(candidate) is not None
    )


def _markup_attribute_is_safe(name: str, value: str) -> bool:
    stripped = value.strip()
    if name == "xmlns":
        return stripped == "http://www.w3.org/2000/svg"
    if name == "marker-end":
        return LOCAL_MARKER_PATTERN.fullmatch(stripped) is not None
    return (
        SCRIPTABLE_VALUE_PATTERN.search(stripped) is None
        and not _css_is_unsafe(stripped)
    )


def _markup_is_unsafe(
    text: str, suffix: str, allowed_font_hashes: frozenset[str] = frozenset()
) -> bool:
    candidate = SAFE_XMLNS_PATTERN.sub("", text)
    if any(pattern.search(candidate) for pattern in MARKUP_PATTERNS):
        return True
    if suffix == ".svg":
        if "<!DOCTYPE" in text.upper() or "<!ENTITY" in text.upper():
            return True
        try:
            root = ElementTree.fromstring(text)
        except ElementTree.ParseError:
            return True
        if root.tag.rsplit("}", 1)[-1].casefold() != "svg":
            return True
        for element in root.iter():
            tag = element.tag.rsplit("}", 1)[-1].casefold()
            if tag not in SAFE_MARKUP_TAGS:
                return True
            if tag == "style" and _css_is_unsafe(
                element.text or "", allowed_font_hashes
            ):
                return True
            for raw_name, value in element.attrib.items():
                name = raw_name.rsplit("}", 1)[-1].casefold()
                if (
                    name.startswith("on")
                    or name not in SAFE_MARKUP_ATTRIBUTES
                    or not _markup_attribute_is_safe(name, value)
                ):
                    return True
        return False
    parser = _StrictHtmlParser(allowed_font_hashes)
    try:
        parser.feed(text)
        parser.close()
    except (_MalformedHtml, ValueError):
        return True
    return bool(parser.stack)


def _scan_text(
    relative: Path,
    text: str,
    private_terms: tuple[str, ...],
    allowed_font_hashes: frozenset[str] = frozenset(),
) -> list[Finding]:
    findings: list[Finding] = []
    if any(pattern.search(text) for pattern in PERSONAL_PATH_PATTERNS):
        findings.append(
            Finding(
                "personal-path-in-text",
                relative,
                "text contains a user-profile path",
            )
        )

    if any(pattern.search(text) for pattern in CREDENTIAL_PATTERNS):
        findings.append(
            Finding("credential-content", relative, "text contains credential-shaped content")
        )

    emails = {match.casefold() for match in EMAIL_PATTERN.findall(text)}
    if any(email not in APPROVED_EMAILS for email in emails):
        findings.append(
            Finding("identity-content", relative, "text contains an unapproved email address")
        )

    folded = text.casefold()
    if any(term in folded for term in private_terms):
        findings.append(
            Finding("private-term-content", relative, "text contains a private owner term")
        )

    encoded_candidate, _rejected_font = _without_reviewed_embedded_fonts(
        text, allowed_font_hashes
    )
    if (
        DATA_AUDIO_PATTERN.search(encoded_candidate)
        or LONG_BASE64_PATTERN.search(encoded_candidate)
        or LONG_HEX_PATTERN.search(encoded_candidate)
    ):
        findings.append(
            Finding(
                "encoded-private-content",
                relative,
                "text contains encoded private-capable content",
            )
        )
    return findings


def _contains_private_structured_value(value: object) -> bool:
    if isinstance(value, Mapping):
        for raw_key, item in value.items():
            key = str(raw_key).casefold()
            if key in PRIVATE_STRUCTURED_KEYS:
                if isinstance(item, str) and item.strip():
                    return True
                if isinstance(item, (Mapping, list)) and bool(item):
                    return True
            if _contains_private_structured_value(item):
                return True
    elif isinstance(value, list):
        return any(_contains_private_structured_value(item) for item in value)
    return False


def _is_populated_private_value(value: object) -> bool:
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (Mapping, list)):
        return bool(value)
    return value is not None


def _contains_private_schema_value(
    value: object,
    *,
    property_definitions: bool = False,
    private_definition: bool = False,
) -> bool:
    if isinstance(value, Mapping):
        if private_definition and any(
            keyword in value and _is_populated_private_value(value[keyword])
            for keyword in PRIVATE_SCHEMA_VALUE_KEYWORDS
        ):
            return True
        for raw_key, item in value.items():
            key = str(raw_key).casefold()
            if property_definitions and key in PRIVATE_STRUCTURED_KEYS:
                if not isinstance(item, Mapping):
                    return _is_populated_private_value(item)
                if _contains_private_schema_value(item, private_definition=True):
                    return True
                continue
            if key in PRIVATE_STRUCTURED_KEYS and _is_populated_private_value(item):
                return True
            if _contains_private_schema_value(
                item,
                property_definitions=key == "properties",
                private_definition=private_definition,
            ):
                return True
    elif isinstance(value, list):
        return any(
            _contains_private_schema_value(
                item, private_definition=private_definition
            )
            for item in value
        )
    return False


def _is_reviewed_json_schema(relative: Path, document: object) -> bool:
    if relative.as_posix().casefold() not in APPROVED_JSON_SCHEMA_PATHS:
        return False
    if not isinstance(document, Mapping):
        return False
    schema_uri = document.get("$schema")
    return isinstance(schema_uri, str) and "json-schema.org/" in schema_uri


def _has_private_structured_content(relative: Path, text: str) -> bool:
    suffix = relative.suffix.casefold()
    if suffix in PRIVATE_STRUCTURED_TEXT_SUFFIXES:
        for line in text.splitlines():
            match = PRIVATE_STRUCTURED_LINE_PATTERN.fullmatch(line)
            if match is None:
                match = PRIVATE_STRUCTURED_TABLE_PATTERN.fullmatch(line)
            if match is None:
                continue
            value = match.group("value").strip()
            if value.endswith(","):
                value = value[:-1].rstrip()
            normalized = value.casefold()
            approved_schema_value = (
                relative.as_posix().casefold(),
                match.group("key").casefold(),
                normalized,
            )
            if (
                normalized not in EMPTY_PRIVATE_STRUCTURED_TEXT_VALUES
                and approved_schema_value not in APPROVED_SCHEMA_TEXT_VALUES
            ):
                return True
        return False
    if suffix not in {".json", ".jsonl"}:
        return False
    try:
        if suffix == ".json":
            documents = [json.loads(text)]
        else:
            documents = [json.loads(line) for line in text.splitlines() if line.strip()]
    except json.JSONDecodeError:
        return False
    if len(documents) == 1 and _is_reviewed_json_schema(relative, documents[0]):
        return _contains_private_schema_value(documents[0])
    return any(_contains_private_structured_value(document) for document in documents)


def _scan_entry(
    entry: AuditEntry, policy: AuditPolicy, private_terms: tuple[str, ...]
) -> list[Finding]:
    relative = Path(*entry.path.parts)
    findings: list[Finding] = []

    if _is_private_path(relative):
        findings.append(
            Finding("private-path", relative, "private workflow paths cannot be public")
        )

    suffix = entry.path.suffix.lower()
    forbidden_name = _has_forbidden_name(entry.path)
    if suffix in FORBIDDEN_EXTENSIONS or forbidden_name:
        findings.append(
            Finding(
                "forbidden-extension",
                relative,
                "this file type may contain private or identity-bearing data",
            )
        )

    size = len(entry.data)
    if size > MAX_PUBLIC_BYTES:
        findings.append(
            Finding(
                "oversized-file",
                relative,
                f"{size} bytes exceeds the {MAX_PUBLIC_BYTES}-byte public limit",
            )
        )
        return findings

    if suffix == ".png":
        if entry.path not in policy.allowed_pngs:
            findings.append(
                Finding("unapproved-binary", relative, "PNG path is not publicly allowlisted")
            )
            return findings
        findings.extend(validate_public_png(entry.path, entry.data))
        return findings
    if suffix == ".xlsx":
        if entry.path not in policy.allowed_xlsx:
            findings.append(
                Finding("unapproved-binary", relative, "workbook path is not publicly allowlisted")
            )
            return findings
        findings.extend(validate_blank_scorecard(entry.path, entry.data))
        container_is_unsafe = any(
            item.code == "unsafe-xlsx-container" for item in findings
        )
        if not container_is_unsafe:
            try:
                workbook_text = decoded_scorecard_text(entry.data)
            except ValueError:
                findings.append(
                    Finding(
                        "unsafe-xlsx-container",
                        relative,
                        "Open XML container is unsafe",
                    )
                )
            else:
                findings.extend(_scan_text(relative, workbook_text, private_terms))
        return findings
    if suffix in {".woff2", ".ttf"}:
        expected = policy.allowed_fonts.get(entry.path)
        digest = hashlib.sha256(entry.data).hexdigest()
        expected_header = b"wOF2" if suffix == ".woff2" else b"\x00\x01\x00\x00"
        if (
            expected is None
            or digest != expected
            or not entry.data.startswith(expected_header)
        ):
            findings.append(
                Finding(
                    "unapproved-binary",
                    relative,
                    "font path, format, or digest is not publicly allowlisted",
                )
            )
        return findings

    signature = detect_signature(entry.data)
    if signature is not None:
        findings.append(
            Finding("forbidden-signature", relative, "content has a private-capable binary signature")
        )
        return findings

    text = _decoded_text(entry.data)
    if text is None:
        findings.append(
            Finding("unapproved-binary", relative, "binary content is not publicly allowlisted")
        )
        return findings

    if suffix in {".svg", ".html", ".htm"} and _markup_is_unsafe(
        text, suffix, frozenset(policy.allowed_fonts.values())
    ):
        findings.append(
            Finding("unsafe-markup", relative, "markup contains active or remote content")
        )

    if _has_private_structured_content(relative, text):
        findings.append(
            Finding(
                "private-structured-content",
                relative,
                "text contains populated private workflow fields",
            )
        )

    findings.extend(
        _scan_text(
            relative,
            text,
            private_terms,
            frozenset(policy.allowed_fonts.values()),
        )
    )

    return findings


def scan_entries(
    entries: Iterable[AuditEntry], policy: AuditPolicy | None = None
) -> list[Finding]:
    """Apply publication policy to exact bytes supplied by an audit source."""
    active_policy = AuditPolicy() if policy is None else policy
    private_terms = _load_private_terms(active_policy.private_terms_file)
    findings = [
        finding
        for entry in entries
        for finding in _scan_entry(entry, active_policy, private_terms)
    ]
    return sorted(findings, key=lambda item: (item.path.as_posix(), item.code))


def scan_history_entries(
    entries: Iterable[AuditEntry],
    policy: AuditPolicy | None = None,
    exceptions: Iterable[HistoryException] = (),
) -> tuple[list[Finding], tuple[HistoryException, ...]]:
    """Scan history and consume only exact reviewed object/finding pairs."""
    configured = tuple(exceptions)
    exception_pairs: dict[tuple[str, str], HistoryException] = {}
    for exception in configured:
        if not isinstance(exception, HistoryException):
            raise AuditSourceError("malformed history exception entry")
        if HISTORY_OBJECT_ID_PATTERN.fullmatch(exception.object_id) is None:
            raise AuditSourceError(
                "history exception object ID must be 40 lowercase hexadecimal characters"
            )
        if exception.finding_code not in REVIEWABLE_HISTORY_FINDING_CODES:
            raise AuditSourceError("history exception has an unknown finding code")
        if not exception.reason.strip():
            raise AuditSourceError("history exception reason must not be empty")
        pair = (exception.object_id, exception.finding_code)
        if pair in exception_pairs:
            raise AuditSourceError("duplicate history exception pair")
        exception_pairs[pair] = exception

    active_policy = AuditPolicy() if policy is None else policy
    history_policy = AuditPolicy(
        active_policy.private_terms_file,
        active_policy.allowed_pngs | RETIRED_HISTORY_DIAGRAM_PNGS,
        active_policy.allowed_xlsx,
        active_policy.allowed_fonts,
    )
    private_terms = _load_private_terms(history_policy.private_terms_file)
    seen_objects: set[str] = set()
    consumed_pairs: set[tuple[str, str]] = set()
    findings: list[Finding] = []
    for entry in entries:
        if entry.source != "history":
            raise AuditSourceError("history exception scan received a non-history entry")
        if (
            entry.object_id is None
            or HISTORY_OBJECT_ID_PATTERN.fullmatch(entry.object_id) is None
        ):
            raise AuditSourceError("malformed history object ID")
        seen_objects.add(entry.object_id)
        for finding in _scan_entry(entry, history_policy, private_terms):
            pair = (entry.object_id, finding.code)
            if pair in exception_pairs:
                consumed_pairs.add(pair)
            else:
                findings.append(finding)

    missing_objects = {item.object_id for item in configured} - seen_objects
    if missing_objects:
        raise AuditSourceError("reviewed exception references a missing historical object")
    unconsumed = set(exception_pairs) - consumed_pairs
    if unconsumed:
        raise AuditSourceError("reviewed history exception is stale or unconsumed")

    accepted = tuple(
        exception for exception in configured
        if (exception.object_id, exception.finding_code) in consumed_pairs
    )
    return (
        sorted(findings, key=lambda item: (item.path.as_posix(), item.code)),
        accepted,
    )


def load_history_exceptions(root: Path) -> tuple[HistoryException, ...]:
    """Load the repository's reviewed, history-only exception manifest."""
    path = root.resolve() / HISTORY_EXCEPTIONS_PATH
    if not path.exists():
        return ()
    if path.is_symlink() or not path.is_file():
        raise AuditSourceError("reviewed history exception manifest is malformed")
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise AuditSourceError(
            "reviewed history exception manifest is malformed"
        ) from error
    if (
        not isinstance(document, dict)
        or set(document) != {"version", "exceptions"}
        or type(document["version"]) is not int
        or document["version"] != 1
        or not isinstance(document["exceptions"], list)
    ):
        raise AuditSourceError("reviewed history exception manifest is malformed")

    exceptions: list[HistoryException] = []
    for item in document["exceptions"]:
        if (
            not isinstance(item, dict)
            or set(item) != {"object_id", "finding_code", "reason"}
            or not all(isinstance(value, str) for value in item.values())
        ):
            raise AuditSourceError("reviewed history exception manifest is malformed")
        exceptions.append(
            HistoryException(
                object_id=item["object_id"],
                finding_code=item["finding_code"],
                reason=item["reason"],
            )
        )
    return tuple(exceptions)


def _history_exception_summary(exceptions: Sequence[HistoryException]) -> str:
    code_counts: dict[str, int] = {}
    for exception in exceptions:
        code_counts[exception.finding_code] = (
            code_counts.get(exception.finding_code, 0) + 1
        )
    codes = ", ".join(
        f"{code}={count}" for code, count in sorted(code_counts.items())
    )
    objects = len({item.object_id for item in exceptions})
    noun = "exception" if len(exceptions) == 1 else "exceptions"
    object_noun = "object" if objects == 1 else "objects"
    return (
        f"accepted {len(exceptions)} reviewed history {noun} "
        f"across {objects} blob {object_noun} ({codes})"
    )


def scan_repository(root: Path) -> list[Finding]:
    """Scan every public candidate file beneath *root*."""
    root = Path(root).resolve()
    findings = scan_entries(tree_entries(root), AuditPolicy())
    findings.extend(scan_ignored_release_paths(ignored_paths(root)))
    return sorted(findings, key=lambda item: (item.path.as_posix(), item.code))


def scan_staged(root: Path, paths: Iterable[Path] | None = None) -> list[Finding]:
    """Scan only the repository-relative files supplied by Git staging."""
    root = Path(root).resolve()
    entries = list(index_entries(root))
    if paths is None:
        return scan_entries(entries, AuditPolicy())
    selected: set[PurePosixPath] = set()
    findings: list[Finding] = []
    for relative in paths:
        path = (root / relative).resolve()
        try:
            normalized = path.relative_to(root)
        except ValueError:
            findings.append(
                Finding("path-escape", Path(relative), "staged path escapes repository root")
            )
            continue
        selected.add(PurePosixPath(normalized.as_posix()))
    findings.extend(
        scan_entries(
            (entry for entry in entries if entry.path in selected), AuditPolicy()
        )
    )
    return sorted(findings, key=lambda item: (item.path.as_posix(), item.code))


def _next_git_identity_findings(
    root: Path, environ: Mapping[str, str]
) -> list[Finding]:
    process_environment = os.environ.copy()
    process_environment.update(environ)
    findings: list[Finding] = []
    for role, variable in (
        ("author", "GIT_AUTHOR_IDENT"),
        ("committer", "GIT_COMMITTER_IDENT"),
    ):
        try:
            completed = subprocess.run(
                ["git", "-C", str(root), "var", variable],
                capture_output=True,
                check=False,
                text=True,
                env=process_environment,
            )
        except OSError:
            completed = None
        match = (
            None
            if completed is None or completed.returncode != 0
            else GIT_IDENTITY_PATTERN.fullmatch(completed.stdout.strip())
        )
        if (
            match is None
            or match.group(1) != APPROVED_GIT_NAME
            or match.group(2).casefold() != APPROVED_GIT_EMAIL.casefold()
        ):
            findings.append(
                Finding(
                    "unapproved-git-identity",
                    Path(f".git/next-{role}-identity"),
                    f"next Git {role} identity is not approved for publication",
                )
            )
    return findings


def _render_findings(findings: Sequence[Finding]) -> str:
    return "\n".join(
        f"{item.code}: {item.path.as_posix()} ({item.detail})" for item in findings
    )


def run_audit(
    root: Path,
    mode: str,
    private_terms_file: Path | None = None,
    environ: Mapping[str, str] | None = None,
) -> int:
    """Run one audit mode with stable command-line exit behavior."""
    root = root.resolve()
    if not root.is_dir():
        print("repository root is not a directory")
        return 2
    sources = {
        "tree": tree_entries,
        "staged": index_entries,
        "history": history_entries,
    }
    accepted: tuple[HistoryException, ...] = ()
    try:
        terms_path = _resolved_private_terms_file(
            root, private_terms_file, os.environ if environ is None else environ
        )
        policy = AuditPolicy(private_terms_file=terms_path)
        if mode == "history":
            findings, accepted = scan_history_entries(
                sources[mode](root),
                policy,
                load_history_exceptions(root),
            )
        else:
            findings = scan_entries(sources[mode](root), policy)
            if mode == "staged":
                findings.extend(
                    _next_git_identity_findings(
                        root, {} if environ is None else environ
                    )
                )
                findings.sort(key=lambda item: (item.path.as_posix(), item.code))
            if mode == "tree":
                findings.extend(scan_ignored_release_paths(ignored_paths(root)))
                findings.sort(key=lambda item: (item.path.as_posix(), item.code))
    except (AuditSourceError, PrivateTermsError) as error:
        if isinstance(error, PrivateTermsError):
            print(str(error))
            return 2
        if mode == "staged" and str(error) == "audit mode requires a Git worktree":
            print("staged scan requires a Git worktree")
        elif mode == "history" and str(error) == "audit mode requires a Git worktree":
            print("history scan requires a Git worktree")
        else:
            print(f"audit source error: {error}")
        return 2
    if accepted:
        print(_history_exception_summary(accepted))
    if findings:
        print(_render_findings(findings))
        return 1
    print("publication boundary check passed")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--mode", choices=("tree", "staged", "history"), default="tree"
    )
    parser.add_argument(
        "--staged", action="store_true", help="scan only files staged in Git"
    )
    parser.add_argument("--private-terms-file", type=Path)
    args = parser.parse_args(argv)
    mode = "staged" if args.staged else args.mode
    return run_audit(args.root, mode, args.private_terms_file)


if __name__ == "__main__":
    raise SystemExit(main())
