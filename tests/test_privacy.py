from __future__ import annotations

from io import BytesIO
import json
from pathlib import Path, PurePosixPath
import subprocess
import zipfile

import pytest

import voice_replication_kit.privacy as privacy
from voice_replication_kit.audit_sources import AuditEntry
from voice_replication_kit.privacy import (
    AuditPolicy,
    MAX_PUBLIC_BYTES,
    scan_entries,
    scan_repository,
    scan_staged,
)


REVIEWED_DIAGRAM_PNGS = (
    "docs/assets/voice-replication-studio-journey.png",
)
REVIEWED_FONT_FILES = (
    "docs/assets/fonts/source-sans-3-latin.woff2",
    "docs/assets/fonts/source-sans-3-variable.ttf",
    "docs/assets/fonts/source-serif-4-latin.woff2",
    "docs/assets/fonts/source-serif-4-variable.ttf",
)
RETIRED_DIAGRAM_PNGS = (
    "docs/assets/voice-replication-one-view-transit.png",
    "docs/assets/voice-replication-one-view-control-plane.png",
    "docs/assets/voice-replication-one-view-field-atlas.png",
    "docs/assets/voice-replication-architecture-github.png",
    "docs/assets/voice-replication-architecture-presentation.png",
    "docs/assets/voice-replication-architecture-social.png",
    "docs/assets/voice-replication-first-build-github.png",
    "docs/assets/voice-replication-first-build-presentation.png",
    "docs/assets/voice-replication-first-build-social.png",
    "docs/assets/voice-replication-repeat-workflow-github.png",
    "docs/assets/voice-replication-repeat-workflow-presentation.png",
    "docs/assets/voice-replication-repeat-workflow-social.png",
)
ALLOWED_PNGS = frozenset(PurePosixPath(path) for path in REVIEWED_DIAGRAM_PNGS)
ALLOWED_XLSX = frozenset(
    {PurePosixPath("evaluation/voice-evaluation-scorecard.xlsx")}
)


def policy(private_terms_file: Path | None = None) -> AuditPolicy:
    return AuditPolicy(private_terms_file, ALLOWED_PNGS, ALLOWED_XLSX)


@pytest.mark.parametrize(
    "name",
    [
        "voice.flac",
        "voice.m4a",
        "voice.aac",
        "voice.ogg",
        "voice.opus",
        "video.mp4",
        "video.mov",
        "video.webm",
        "weights.bin",
        "weights.onnx",
        "embedding.npz",
        "state.pkl",
        "state.joblib",
        "secret.pem",
        "secret.key",
        ".env",
        "private.7z",
        "private.rar",
        "private.tar",
        "private.zip",
        "program.exe",
        "library.dll",
        "library.so",
        "library.dylib",
        "records.db",
        "records.sqlite",
        "records.sqlite3",
        "graph.pb",
        "weights.gguf",
        "private.bz2",
        "private.xz",
        "private.zst",
        "installer.msi",
        "model.tflite",
    ],
)
def test_private_capable_formats_are_rejected(name: str) -> None:
    findings = scan_entries(
        [AuditEntry(PurePosixPath(name), b"fixture", "test")], policy()
    )
    assert any(item.code == "forbidden-extension" for item in findings)


@pytest.mark.parametrize(
    "data",
    [
        b"-----BEGIN " + b"PRIVATE KEY-----\n",
        b"gh" + b"p_abcdefghijklmnopqrstuvwxyz1234567890",
        b"AK" + b"IAIOSFODNN7EXAMPLE",
        b"https://user:" + b"password" + b"@example.invalid/repository.git",
    ],
)
def test_credentials_are_rejected_by_content(data: bytes) -> None:
    findings = scan_entries(
        [AuditEntry(PurePosixPath("notes.txt"), data, "test")], policy()
    )
    assert any(item.code == "credential-content" for item in findings)


@pytest.mark.parametrize(
    "data",
    [
        b"Authorization: " + b"Bear" + b"er " + b"opaque_access_token_0123456789",
        (
            b"eyJhbGciOiJIUzI1NiJ9."
            + b"eyJzdWIiOiIxMjM0NTY3ODkwIn0."
            + b"signaturevalue1234567890"
        ),
        b"API_" + b"KEY = " + b"fixture_" + b"A" * 24,
        b"TOK" + b"EN: " + b"fixture_" + b"B" * 24,
        b"SEC" + b"RET='" + b"fixture_" + b"C" * 24 + b"'",
        b"PASS" + b"WORD=\"" + b"fixture_" + b"D" * 24 + b"\"",
        b"AWS_SECRET_" + b"ACCESS_KEY=" + b"E" * 40,
        b"sk-" + b"proj-" + b"F" * 48,
        b"sk-" + b"ant-api03-" + b"G" * 48,
        b"hf_" + b"H" * 36,
        b"rk_" + b"live_" + b"I" * 24,
    ],
)
def test_additional_credential_shapes_are_rejected_without_echoing_values(
    data: bytes,
) -> None:
    findings = scan_entries(
        [AuditEntry(PurePosixPath("notes.txt"), data, "test")], policy()
    )
    rendered = privacy._render_findings(findings)

    assert any(item.code == "credential-content" for item in findings)
    assert data.decode("ascii") not in rendered


@pytest.mark.parametrize(
    "data",
    [
        b"password" + b"=\"" + b"long-secret-value-" + b"A" * 12 + b"\"",
        b"token" + b"='" + b"fixture-token-" + b"B" * 16 + b"'",
        b"secret" + b": " + b"fixture-secret-" + b"C" * 16,
        b"api_" + b"key = " + b"fixture-key-" + b"D" * 16,
    ],
)
def test_mixed_case_generic_credential_assignments_are_rejected(
    data: bytes,
) -> None:
    findings = scan_entries(
        [AuditEntry(PurePosixPath("notes.txt"), data, "test")], policy()
    )

    assert any(item.code == "credential-content" for item in findings)
    assert data.decode("ascii") not in privacy._render_findings(findings)


@pytest.mark.parametrize(
    "data",
    [
        b"secret" + b" = build_blind_pack(rows)",
        b"token" + b" = create_runtime_token(config)",
        b"password" + b" = getpass()",
        b"api_" + b"key = os.getenv(name)",
    ],
)
def test_generic_credential_names_assigned_function_calls_are_accepted(
    data: bytes,
) -> None:
    assert scan_entries(
        [AuditEntry(PurePosixPath("notes.txt"), data, "test")], policy()
    ) == []


def test_bearer_detection_requires_token_boundaries() -> None:
    data = b"not" + b"Bear" + b"er " + b"opaque_access_token_0123456789"

    assert scan_entries(
        [AuditEntry(PurePosixPath("notes.txt"), data, "test")], policy()
    ) == []


@pytest.mark.parametrize(
    "data",
    [
        b"RIFF\x24\x00\x00\x00WAVEfmt ",
        b"PK\x03\x04archive",
        b"\x80\x04serialized",
        b"\x7fELFbinary",
        b"MZbinary",
        b"SQLite format 3\x00data",
        b"GGUFmodel",
        b"BZh91AY&SYarchive",
        b"\x1f\x8b\x08gzip",
        b"7z\xbc\xaf'\x1carchive",
        b"Rar!\x1a\x07\x00archive",
        b"\xfe\xed\xfa\xcfmach-o",
        b"\xfd7zXZ\x00archive",
        b"\x28\xb5\x2f\xfdarchive",
        b"\x00" * 257 + b"ustar\x0000archive",
    ],
)
def test_disguised_binary_signatures_are_rejected(data: bytes) -> None:
    findings = scan_entries(
        [AuditEntry(PurePosixPath("apparently-safe.md"), data, "test")], policy()
    )
    assert any(item.code == "forbidden-signature" for item in findings)


def test_unapproved_identity_email_is_rejected() -> None:
    findings = scan_entries(
        [
            AuditEntry(
                PurePosixPath("notes.txt"),
                b"Contact private.person" + b"@mail.example.com",
                "test",
            )
        ],
        policy(),
    )
    assert any(item.code == "identity-content" for item in findings)


def test_approved_public_identity_is_accepted() -> None:
    data = (
        b"gitramnag\n"
        b"315322897+gitramnag@users.noreply.github.com\n"
    )
    assert scan_entries(
        [AuditEntry(PurePosixPath("notes.txt"), data, "test")], policy()
    ) == []


def test_synthetic_email_is_not_globally_exempt() -> None:
    data = b"test" + b"@" + b"example" + b"." + b"invalid"

    findings = scan_entries(
        [AuditEntry(PurePosixPath("notes.txt"), data, "test")], policy()
    )

    assert any(item.code == "identity-content" for item in findings)


def test_owner_private_terms_match_case_insensitively_without_echoing_term(
    tmp_path: Path,
) -> None:
    private_terms = tmp_path / "owner-terms.txt"
    private_terms.write_text("Sensitive Codename\n", encoding="utf-8")
    findings = scan_entries(
        [
            AuditEntry(
                PurePosixPath("notes.txt"), b"sensitive codename", "test"
            )
        ],
        policy(private_terms),
    )
    rendered = privacy._render_findings(findings)
    assert any(item.code == "private-term-content" for item in findings)
    assert "Sensitive Codename" not in rendered
    assert "sensitive codename" not in rendered


def test_owner_private_terms_are_matched_inside_decoded_workbook_xml(
    tmp_path: Path,
) -> None:
    private_term = "Hidden Workbook Codename"
    terms = tmp_path / "owner-terms.txt"
    terms.write_text(private_term + "\n", encoding="utf-8")
    source = (
        Path(__file__).resolve().parents[1]
        / "evaluation"
        / "voice-evaluation-scorecard.xlsx"
    ).read_bytes()
    output = BytesIO()
    with zipfile.ZipFile(BytesIO(source)) as input_archive, zipfile.ZipFile(
        output, "w"
    ) as output_archive:
        for info in input_archive.infolist():
            payload = input_archive.read(info)
            if info.filename == "xl/worksheets/sheet3.xml":
                payload = payload.replace(
                    b"</x:sheetData>",
                    b'<x:row r="40"><x:c r="A40" t="str"><x:v>'
                    + private_term.lower().encode()
                    + b"</x:v></x:c></x:row></x:sheetData>",
                )
            output_archive.writestr(info, payload)

    findings = scan_entries(
        [
            AuditEntry(
                PurePosixPath("evaluation/voice-evaluation-scorecard.xlsx"),
                output.getvalue(),
                "test",
            )
        ],
        policy(terms),
    )
    assert any(item.code == "private-term-content" for item in findings)


@pytest.mark.parametrize(
    ("path", "data"),
    [
        ("diagram.svg", b"<svg><script>alert(1)</script></svg>"),
        ("diagram.svg", b'<svg><image href="https://example.invalid/x.png"/></svg>'),
        (
            "diagram.svg",
            b'<svg><image href="http://www.w3.org/2000/svg"/></svg>',
        ),
        ("diagram.svg", b'<svg><rect onload="alert(1)"/></svg>'),
        ("page.html", b'<link href="https://example.invalid/theme.css">'),
        ("page.html", b'<video src="data:video/mp4;base64,AAAA"></video>'),
        ("diagram.svg", b"<svg><g></svg>"),
        ("page.html", b"<html><body><div></body></html>"),
    ],
)
def test_active_or_remote_markup_is_rejected(path: str, data: bytes) -> None:
    findings = scan_entries(
        [AuditEntry(PurePosixPath(path), data, "test")], policy()
    )
    assert any(item.code == "unsafe-markup" for item in findings)


@pytest.mark.parametrize(
    ("path", "data"),
    [
        (
            "diagram.svg",
            b'<svg xmlns="http://www.w3.org/2000/svg"><a href="java'
            b'script:alert(1)"><rect width="1" height="1"/></a></svg>',
        ),
        (
            "diagram.svg",
            b'<svg xmlns="http://www.w3.org/2000/svg"><foreignObject/></svg>',
        ),
        (
            "diagram.svg",
            b'<svg xmlns="http://www.w3.org/2000/svg"><iframe srcdoc="safe"/></svg>',
        ),
        ("page.html", b'<html><body><a href="javascript:alert(1)">x</a></body></html>'),
        ("page.html", b'<html><body><iframe srcdoc="safe"></iframe></body></html>'),
        ("page.html", b'<html><body><form action="/submit"></form></body></html>'),
        ("page.html", b'<html><body><object data="local"></object></body></html>'),
        ("page.html", b'<html><body><embed src="local"></body></html>'),
        ("page.html", b'<html><style>@import "theme.css";</style><body></body></html>'),
        (
            "page.html",
            b'<html><style>body{background:url(/asset)}</style><body></body></html>',
        ),
        (
            "page.html",
            b'<html><style>body{width:'
            b'expression(alert(1))}</style><body></body></html>',
        ),
        (
            "page.html",
            b'<html><style>body{background:'
            b'javascript:alert(1)}</style><body></body></html>',
        ),
        ("page.html", b'<html><body><img src="//example.invalid/x.png"></body></html>'),
        (
            "page.html",
            b'<html><body><img src="data:text/html;base64,PHNjcmlwdD4="></body></html>',
        ),
    ],
)
def test_semantic_active_markup_bypasses_are_rejected(path: str, data: bytes) -> None:
    findings = scan_entries(
        [AuditEntry(PurePosixPath(path), data, "test")], policy()
    )
    assert any(item.code == "unsafe-markup" for item in findings)


@pytest.mark.parametrize(
    ("path", "data"),
    [
        (
            "page.html",
            b'<html><style>@\\69mport "theme.css";</style><body></body></html>',
        ),
        (
            "page.html",
            b"<html><style>body{background:u\\rl(/asset)}</style></html>",
        ),
        (
            "page.html",
            b"<html><style>@im/**/port 'theme.css';</style></html>",
        ),
        (
            "page.html",
            b"<html><style>body{background:u/**/rl(/asset)}</style></html>",
        ),
        (
            "diagram.svg",
            b'<svg xmlns="http://www.w3.org/2000/svg"><style>'
            b"rect{fill:java\\script:alert(1)}</style></svg>",
        ),
        (
            "diagram.svg",
            b'<svg xmlns="http://www.w3.org/2000/svg"><style>'
            b"rect{fill:java/**/script:alert(1)}</style></svg>",
        ),
        (
            "page.html",
            b'<html><body style="background:u\\72l(/asset)"></body></html>',
        ),
        (
            "diagram.svg",
            b'<svg xmlns="http://www.w3.org/2000/svg">'
            b'<rect style="fill:java/**/script:alert(1)"/></svg>',
        ),
    ],
)
def test_css_escapes_and_comments_cannot_hide_active_tokens(
    path: str, data: bytes
) -> None:
    findings = scan_entries(
        [AuditEntry(PurePosixPath(path), data, "test")], policy()
    )

    assert any(item.code == "unsafe-markup" for item in findings)


def test_safe_local_svg_fixture_is_accepted() -> None:
    fixture = Path(__file__).parent / "fixtures" / "public-safe.svg"
    assert scan_entries(
        [AuditEntry(PurePosixPath("diagram.svg"), fixture.read_bytes(), "test")],
        policy(),
    ) == []


@pytest.mark.parametrize("relative_path", REVIEWED_DIAGRAM_PNGS)
def test_default_policy_accepts_reviewed_diagram_png_exports(
    relative_path: str,
) -> None:
    path = Path(__file__).resolve().parents[1] / relative_path
    assert scan_entries(
        [AuditEntry(PurePosixPath(relative_path), path.read_bytes(), "test")]
    ) == []


@pytest.mark.parametrize("relative_path", RETIRED_DIAGRAM_PNGS)
def test_default_policy_rejects_every_retired_diagram_png_path(
    relative_path: str,
) -> None:
    findings = scan_entries(
        [
            AuditEntry(
                PurePosixPath(relative_path),
                b"retired diagram bytes",
                "test",
            )
        ]
    )

    assert [(item.code, item.path.as_posix()) for item in findings] == [
        ("unapproved-binary", relative_path)
    ]


@pytest.mark.parametrize("relative_path", RETIRED_DIAGRAM_PNGS)
def test_history_policy_grandfathers_only_exact_retired_diagram_png_paths(
    relative_path: str,
) -> None:
    reviewed_png = (
        Path(__file__).resolve().parents[1]
        / "docs/assets/voice-replication-studio-journey.png"
    ).read_bytes()

    findings, accepted = privacy.scan_history_entries(
        [
            AuditEntry(
                PurePosixPath(relative_path),
                reviewed_png,
                "history",
                object_id="a" * 40,
            )
        ]
    )

    assert findings == []
    assert accepted == ()


@pytest.mark.parametrize(
    ("path", "data"),
    [
        (
            "page.html",
            b'<html><body><svg data-layout="landscape" data-grammar="trust-zones">'
            b'<g data-node-id="public-kit" data-flow="primary">'
            b'<text><tspan x="0" dy="0">Public kit</tspan></text></g>'
            b"</svg></body></html>",
        ),
        (
            "diagram.svg",
            b'<svg xmlns="http://www.w3.org/2000/svg" data-layout="social" '
            b'data-grammar="production-loop"><g data-node-id="new-script" '
            b'data-flow="primary" data-geometry-id="new-script" '
            b'data-region="repeat" data-visible="true">'
            b'<path data-connector="repeat" data-source="create" '
            b'data-target="package" stroke="#087565" stroke-width="4" '
            b'stroke-linecap="round" fill="none"/>'
            b'<text data-copy="New script" data-text="true">'
            b'<tspan x="0" dy="0">New script</tspan>'
            b"</text></g></svg>",
        ),
    ],
)
def test_static_diagram_metadata_attributes_are_accepted(
    path: str, data: bytes
) -> None:
    assert scan_entries(
        [AuditEntry(PurePosixPath(path), data, "test")], policy()
    ) == []


@pytest.mark.parametrize("path", ["page.html", "diagram.svg"])
def test_unreviewed_data_attributes_remain_rejected(path: str) -> None:
    tag = "html" if path.endswith(".html") else "svg"
    data = f'<{tag} data-unreviewed="value"></{tag}>'.encode()
    findings = scan_entries(
        [AuditEntry(PurePosixPath(path), data, "test")], policy()
    )

    assert any(item.code == "unsafe-markup" for item in findings)


@pytest.mark.parametrize("attribute", ["data-target-x", "data-target-y"])
@pytest.mark.parametrize("path", ["page.html", "diagram.svg"])
def test_legacy_diagram_target_attributes_are_rejected(
    path: str, attribute: str
) -> None:
    tag = "html" if path.endswith(".html") else "svg"
    data = f'<{tag} {attribute}="12"></{tag}>'.encode()
    findings = scan_entries(
        [AuditEntry(PurePosixPath(path), data, "test")], policy()
    )

    assert any(item.code == "unsafe-markup" for item in findings)


@pytest.mark.parametrize("path", ["renamed.png", "renamed.xlsx"])
def test_public_binary_allowlist_is_exact(path: str) -> None:
    findings = scan_entries(
        [AuditEntry(PurePosixPath(path), b"not a public asset", "test")], policy()
    )
    assert any(item.code == "unapproved-binary" for item in findings)


def test_public_font_allowlist_is_exact_and_digest_locked() -> None:
    assert hasattr(privacy, "ALLOWED_FONTS")
    allowed_fonts = privacy.ALLOWED_FONTS
    assert set(path.as_posix() for path in allowed_fonts) == set(REVIEWED_FONT_FILES)

    for relative, digest in allowed_fonts.items():
        path = Path(*relative.parts)
        assert path.is_file()
        data = path.read_bytes()
        assert scan_entries([AuditEntry(relative, data, "test")], AuditPolicy()) == []
        renamed = PurePosixPath("docs/assets/fonts/renamed.woff2")
        findings = scan_entries([AuditEntry(renamed, data, "test")], AuditPolicy())
        assert any(item.code == "unapproved-binary" for item in findings)


def test_only_reviewed_font_bytes_may_be_embedded_in_markup() -> None:
    assert hasattr(privacy, "ALLOWED_FONTS")
    relative = PurePosixPath(REVIEWED_FONT_FILES[0])
    path = Path(*relative.parts)
    assert path.is_file()
    encoded = __import__("base64").b64encode(path.read_bytes()).decode("ascii")
    safe = (
        "<svg><style>@font-face{font-family:'Pinned';"
        f"src:url(data:font/woff2;base64,{encoded}) format('woff2')}}"
        ".body{font-family:'Pinned'}</style></svg>"
    ).encode()
    assert scan_entries([AuditEntry(PurePosixPath("diagram.svg"), safe, "test")]) == []

    altered = safe.replace(b"d09GMg", b"d09GMx", 1)
    findings = scan_entries(
        [AuditEntry(PurePosixPath("diagram.svg"), altered, "test")]
    )
    assert any(item.code == "unsafe-markup" for item in findings)


@pytest.mark.parametrize(
    "filename",
    [
        "sample.wav",
        "sample.mp3",
        "checkpoint.pt",
        "checkpoint.pth",
        "speaker.ckpt",
        "speaker.safetensors",
        "embedding.npy",
    ],
)
def test_scan_repository_rejects_identity_bearing_extensions(
    tmp_path: Path, filename: str
) -> None:
    (tmp_path / filename).write_bytes(b"private")

    findings = scan_repository(tmp_path)

    assert [(item.code, item.path.as_posix()) for item in findings] == [
        ("forbidden-extension", filename)
    ]


@pytest.mark.parametrize(
    "relative_path",
    [
        "speakers/example/state/manifest.jsonl",
        "private/upload/refs/reference.json",
        "results/raw/cosyvoice3/manifest.jsonl",
        "profiles/private-profile.json",
    ],
)
def test_scan_repository_rejects_private_tree_paths(
    tmp_path: Path, relative_path: str
) -> None:
    path = tmp_path / relative_path
    path.parent.mkdir(parents=True)
    path.write_text("{}", encoding="utf-8")

    findings = scan_repository(tmp_path)

    assert [(item.code, item.path.as_posix()) for item in findings] == [
        ("private-path", relative_path)
    ]


def test_scan_repository_rejects_user_profile_paths_in_text(tmp_path: Path) -> None:
    path = tmp_path / "notes.md"
    path.write_text(
        "Run C:\\" + "Users\\ExamplePerson\\voice\\render.py before upload.\n",
        encoding="utf-8",
    )

    findings = scan_repository(tmp_path)

    assert [(item.code, item.path.as_posix()) for item in findings] == [
        ("personal-path-in-text", "notes.md")
    ]


def test_scan_repository_rejects_spaced_windows_user_profile_paths(
    tmp_path: Path,
) -> None:
    path = tmp_path / "notes.md"
    path.write_bytes(
        b"Run C:\\" + b"Users\\Jane" + b" Doe\\voice\\render.py before upload.\n"
    )

    findings = scan_repository(tmp_path)

    assert [(item.code, item.path.as_posix()) for item in findings] == [
        ("personal-path-in-text", "notes.md")
    ]


@pytest.mark.parametrize(
    "content",
    [
        "Use /mnt/c/" + "Users/ExamplePerson/voice/render.py.\n",
        r'{"path":"C:\\' + r'Users\\ExamplePerson\\voice\\render.py"}',
        "Cache key: c--" + "Users-ExamplePerson-voice-render.py\n",
    ],
)
def test_scan_repository_rejects_additional_user_profile_path_forms(
    tmp_path: Path, content: str
) -> None:
    path = tmp_path / "notes.md"
    path.write_text(content, encoding="utf-8")

    findings = scan_repository(tmp_path)

    assert [(item.code, item.path.as_posix()) for item in findings] == [
        ("personal-path-in-text", "notes.md")
    ]


@pytest.mark.parametrize(
    ("path", "data"),
    [
        (
            "configs/my-profile.json",
            json.dumps(
                {
                    "recipes": {
                        "neutral": {
                            "reference_text": "Synthetic private transcript",
                            "reference_sha256": "a" * 64,
                        }
                    }
                }
            ).encode("utf-8"),
        ),
        (
            "scratch/renamed-plan.json",
            json.dumps(
                {
                    "references": [
                        {
                            "reference_text": "Synthetic private transcript",
                            "reference_sha256": "b" * 64,
                        }
                    ]
                }
            ).encode("utf-8"),
        ),
        (
            "scratch/renamed-requests.jsonl",
            (
                json.dumps(
                    {
                        "reference_text": "Synthetic private transcript",
                        "reference_sha256": "c" * 64,
                    }
                )
                + "\n"
            ).encode("utf-8"),
        ),
        (
            "scratch/renamed-manifest.jsonl",
            (json.dumps({"record_sha256": "d" * 64}) + "\n").encode("utf-8"),
        ),
        (
            "scratch/renamed-map.json",
            json.dumps({"unblinding": {"V001": "request-private-001"}}).encode(
                "utf-8"
            ),
        ),
    ],
)
def test_renamed_private_structured_content_is_rejected(
    path: str, data: bytes
) -> None:
    findings = scan_entries(
        [AuditEntry(PurePosixPath(path), data, "test")], policy()
    )

    assert any(item.code == "private-structured-content" for item in findings)


@pytest.mark.parametrize(
    ("path", "text"),
    [
        ("notes.md", "data:" + "audio/wav;base64," + "A" * 512),
        ("payload.json", json.dumps({"audio": "A" * 1024})),
        ("payload.txt", "52" * 512),
    ],
)
def test_encoded_private_content_is_rejected(path: str, text: str) -> None:
    findings = scan_entries(
        [AuditEntry(PurePosixPath(path), text.encode("utf-8"), "test")], policy()
    )

    assert any(item.code == "encoded-private-content" for item in findings)


@pytest.mark.parametrize(
    "path",
    [
        "evaluation-plan.json",
        "requests.jsonl",
        "matrix.jsonl",
        "unblinding-map.json",
        "production-script-v2.json",
        "private-profile-v2.json",
        "evaluation/pass-00.xlsx",
    ],
)
def test_private_workflow_filenames_are_rejected(path: str) -> None:
    findings = scan_entries(
        [AuditEntry(PurePosixPath(path), b"{}", "test")], policy()
    )

    assert any(item.code in {"private-path", "unapproved-binary"} for item in findings)


def test_scan_repository_rejects_files_larger_than_public_limit(tmp_path: Path) -> None:
    path = tmp_path / "large.txt"
    with path.open("wb") as stream:
        stream.seek(MAX_PUBLIC_BYTES)
        stream.write(b"x")

    findings = scan_repository(tmp_path)

    assert [(item.code, item.path.as_posix()) for item in findings] == [
        ("oversized-file", "large.txt")
    ]


def test_scan_repository_accepts_public_documentation(tmp_path: Path) -> None:
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "guide.md").write_text(
        "Keep recordings and speaker embeddings outside Git.\n", encoding="utf-8"
    )
    assert scan_repository(tmp_path) == []


def test_tree_and_release_audit_reject_an_ignored_edge_browser_profile(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    (tmp_path / ".gitignore").write_text(
        ".impeccable/edge-review/\n", encoding="utf-8"
    )
    profile = tmp_path / ".impeccable" / "edge-review" / "Default"
    sensitive_paths = (
        profile / "Login Data",
        profile / "Cookies",
        profile / "History",
        profile / "Sessions" / "Session_1",
        profile / "Local Storage" / "leveldb" / "000003.log",
    )
    private_marker = b"browser-private-marker-must-not-be-read-or-printed"
    for path in sensitive_paths:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(private_marker)

    findings = scan_repository(tmp_path)

    assert any(item.code == "ignored-browser-profile" for item in findings)
    assert any(
        item.path == PurePosixPath(".impeccable/edge-review") for item in findings
    )
    assert private_marker.decode("ascii") not in privacy._render_findings(findings)

    assert privacy.run_audit(tmp_path, "tree", environ={}) == 1
    output = capsys.readouterr().out
    assert "ignored-browser-profile" in output
    assert private_marker.decode("ascii") not in output


def test_tree_audit_rejects_an_ignored_sensitive_browser_database_name(
    tmp_path: Path,
) -> None:
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    (tmp_path / ".gitignore").write_text("scratch-profile/\n", encoding="utf-8")
    login_data = tmp_path / "scratch-profile" / "Default" / "Login Data"
    login_data.parent.mkdir(parents=True)
    login_data.write_bytes(b"browser-private-marker")

    findings = scan_repository(tmp_path)

    assert ("ignored-browser-state", "scratch-profile/Default/Login Data") in {
        (item.code, item.path.as_posix()) for item in findings
    }


def test_tree_audit_accepts_ignored_bytecode_but_rejects_workflow_residue(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    (tmp_path / ".gitignore").write_text(
        ".superpowers/\n__pycache__/\n", encoding="utf-8"
    )
    private_marker = b"ignored-private-marker-must-not-be-read-or-printed"
    residue_paths = (
        tmp_path / ".superpowers" / "review.md",
        tmp_path / "package" / "__pycache__" / "module.pyc",
    )
    for path in residue_paths:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(private_marker)

    original_read_bytes = Path.read_bytes
    forbidden = {path.resolve() for path in residue_paths}

    def reject_residue_read(path: Path) -> bytes:
        if path.resolve() in forbidden:
            raise AssertionError("ignored residue bytes must remain unopened")
        return original_read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", reject_residue_read)

    findings = scan_repository(tmp_path)
    finding_pairs = {(item.code, item.path.as_posix()) for item in findings}

    assert ("ignored-workflow-state", ".superpowers") in finding_pairs
    assert not any(code == "ignored-python-bytecode" for code, _path in finding_pairs)
    assert private_marker.decode("ascii") not in privacy._render_findings(findings)

    assert privacy.run_audit(tmp_path, "tree", environ={}) == 1
    output = capsys.readouterr().out
    assert "ignored-workflow-state" in output
    assert "ignored-python-bytecode" not in output
    assert private_marker.decode("ascii") not in output


@pytest.mark.parametrize("path", ["package/module.pyc", "package/module.pyo"])
def test_tracked_python_bytecode_remains_forbidden(path: str) -> None:
    findings = scan_entries(
        [AuditEntry(PurePosixPath(path), b"synthetic-bytecode", "index")], policy()
    )

    assert any(item.code == "forbidden-extension" for item in findings)


def test_ignored_private_roots_are_reported_once_at_their_boundary() -> None:
    paths = (
        PurePosixPath("private/recordings/take.wav"),
        PurePosixPath("speakers/owner/profile.json"),
        PurePosixPath("profiles/accepted/profile.json"),
        PurePosixPath("results/raw/render.wav"),
        PurePosixPath("runtime/models/model.pt"),
        PurePosixPath("runtime/cache/features.npy"),
        PurePosixPath("upload/refs/reference.wav"),
    )

    findings = privacy.scan_ignored_release_paths(paths)

    assert {(item.code, item.path.as_posix()) for item in findings} == {
        ("ignored-private-path", "private"),
        ("ignored-private-path", "profiles"),
        ("ignored-private-path", "results/raw"),
        ("ignored-private-path", "runtime/cache"),
        ("ignored-private-path", "runtime/models"),
        ("ignored-private-path", "speakers"),
        ("ignored-private-path", "upload/refs"),
    }


def test_ignored_private_files_and_local_secrets_are_rejected_by_name() -> None:
    paths = (
        PurePosixPath(".voice-replication-private.json"),
        PurePosixPath("settings/.voice-kit-private-terms"),
        PurePosixPath("work/private-profile.yaml"),
        PurePosixPath("scratch/reference.wav"),
        PurePosixPath("scratch/model.pt"),
        PurePosixPath("scratch/features.npy"),
        PurePosixPath("settings/.env.local"),
        PurePosixPath("settings/owner.key"),
    )

    findings = privacy.scan_ignored_release_paths(paths)

    assert {(item.code, item.path.as_posix()) for item in findings} == {
        ("ignored-local-secret", "settings/.env.local"),
        ("ignored-local-secret", "settings/owner.key"),
        ("ignored-private-artifact", "scratch/features.npy"),
        ("ignored-private-artifact", "scratch/model.pt"),
        ("ignored-private-artifact", "scratch/reference.wav"),
        ("ignored-private-marker", ".voice-replication-private.json"),
        ("ignored-private-marker", "settings/.voice-kit-private-terms"),
        ("ignored-private-path", "work/private-profile.yaml"),
    }


def test_ignored_workflow_roots_are_matched_without_case_sensitivity() -> None:
    paths = (
        PurePosixPath(".SUPERPOWERS/review.md"),
        PurePosixPath(".IMPECCABLE/review/desktop.png"),
        PurePosixPath(".Impeccable/review/unapproved.png"),
    )

    findings = privacy.scan_ignored_release_paths(paths)

    assert {(item.code, item.path.as_posix()) for item in findings} == {
        ("ignored-workflow-state", ".impeccable"),
        ("ignored-workflow-state", ".superpowers"),
    }


def test_ignored_public_tooling_and_venv_paths_are_release_safe() -> None:
    paths = (
        PurePosixPath(".pytest_cache/v/cache/nodeids"),
        PurePosixPath("build/voice_replication_kit.egg-info/PKG-INFO"),
        PurePosixPath(".venv/package/__pycache__/module.pyc"),
        PurePosixPath(".venv/package.egg-info/PKG-INFO"),
        PurePosixPath(".venv/lib/site-packages/model.pth"),
        PurePosixPath(".venv/Scripts/tool.exe"),
        PurePosixPath(".VENV/settings/local.pem"),
        PurePosixPath("nested/.Venv/fixtures/reference.wav"),
        PurePosixPath(".impeccable/review/desktop.png"),
        PurePosixPath(".impeccable/review/mobile.png"),
        PurePosixPath(".impeccable/review/standalone-svg.png"),
    )

    findings = privacy.scan_ignored_release_paths(paths)

    assert findings == []


def test_tree_audit_never_reads_new_ignored_private_classes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    (tmp_path / ".gitignore").write_text(
        "private/\n.voice-replication-private.json\n*.npy\n.env.*\n.pytest_cache/\n*.egg-info/\n",
        encoding="utf-8",
    )
    ignored_paths = (
        tmp_path / "private" / "reference.wav",
        tmp_path / ".voice-replication-private.json",
        tmp_path / "features.npy",
        tmp_path / ".env.local",
        tmp_path / ".pytest_cache" / "CACHEDIR.TAG",
        tmp_path / "package.egg-info" / "PKG-INFO",
    )
    marker = b"ignored-private-bytes-must-remain-unopened"
    for path in ignored_paths:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(marker)

    original_read_bytes = Path.read_bytes
    forbidden = {path.resolve() for path in ignored_paths}

    def reject_private_read(path: Path) -> bytes:
        if path.resolve() in forbidden:
            raise AssertionError("ignored private bytes must remain unopened")
        return original_read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", reject_private_read)

    findings = scan_repository(tmp_path)
    finding_pairs = {(item.code, item.path.as_posix()) for item in findings}

    assert ("ignored-private-path", "private") in finding_pairs
    assert (
        "ignored-private-marker",
        ".voice-replication-private.json",
    ) in finding_pairs
    assert ("ignored-private-artifact", "features.npy") in finding_pairs
    assert ("ignored-local-secret", ".env.local") in finding_pairs
    assert not any(
        path in {".pytest_cache", "package.egg-info"}
        for _code, path in finding_pairs
    )
    assert marker.decode("ascii") not in privacy._render_findings(findings)


def test_scan_staged_checks_only_supplied_relative_paths(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    (tmp_path / "public.md").write_text("Safe instructions.\n", encoding="utf-8")
    (tmp_path / "private.wav").write_bytes(b"private")
    subprocess.run(
        ["git", "add", "public.md", "private.wav"], cwd=tmp_path, check=True
    )

    findings = scan_staged(tmp_path, [Path("private.wav")])

    assert [(item.code, item.path.as_posix()) for item in findings] == [
        ("forbidden-extension", "private.wav")
    ]


def test_scan_staged_reads_selected_path_bytes_from_index(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    path = tmp_path / "notes.md"
    path.write_text("Safe staged bytes.\n", encoding="utf-8")
    subprocess.run(["git", "add", "notes.md"], cwd=tmp_path, check=True)
    path.write_text(
        "Run C:\\" + "Users\\PrivatePerson\\voice\\render.py\n", encoding="utf-8"
    )

    findings = scan_staged(tmp_path, [Path("notes.md")])

    assert findings == []


@pytest.mark.parametrize(
    ("variable", "environment_name", "environment_email", "expected_path"),
    [
        (
            "author",
            "GIT_AUTHOR_NAME",
            "GIT_AUTHOR_EMAIL",
            ".git/next-author-identity",
        ),
        (
            "committer",
            "GIT_COMMITTER_NAME",
            "GIT_COMMITTER_EMAIL",
            ".git/next-committer-identity",
        ),
    ],
)
def test_staged_audit_rejects_an_unapproved_next_git_identity_without_echoing_it(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    variable: str,
    environment_name: str,
    environment_email: str,
    expected_path: str,
) -> None:
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "gitramnag"], cwd=tmp_path, check=True)
    subprocess.run(
        [
            "git",
            "config",
            "user.email",
            "315322897+gitramnag@users.noreply.github.com",
        ],
        cwd=tmp_path,
        check=True,
    )
    (tmp_path / "safe.md").write_text("Safe public content.\n", encoding="utf-8")
    subprocess.run(["git", "add", "safe.md"], cwd=tmp_path, check=True)
    private_name = f"Synthetic Private {variable}"
    private_email = f"private-{variable}@" + "example.invalid"
    environment = {
        environment_name: private_name,
        environment_email: private_email,
    }

    exit_code = privacy.run_audit(tmp_path, "staged", environ=environment)

    assert exit_code == 1
    output = capsys.readouterr().out
    assert f"unapproved-git-identity: {expected_path}" in output
    assert private_name not in output
    assert private_email not in output


def test_staged_audit_accepts_the_approved_next_git_identity(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "gitramnag"], cwd=tmp_path, check=True)
    subprocess.run(
        [
            "git",
            "config",
            "user.email",
            "315322897+gitramnag@users.noreply.github.com",
        ],
        cwd=tmp_path,
        check=True,
    )
    (tmp_path / "safe.md").write_text("Safe public content.\n", encoding="utf-8")
    subprocess.run(["git", "add", "safe.md"], cwd=tmp_path, check=True)

    assert privacy.run_audit(tmp_path, "staged", environ={}) == 0
    assert capsys.readouterr().out.strip() == "publication boundary check passed"


def test_scan_entries_applies_path_and_content_policy_to_supplied_bytes() -> None:
    entries = [
        AuditEntry(
            PurePosixPath("notes.md"),
            b"Run C:\\" + b"Users\\PrivatePerson\\voice\\render.py\n",
            "index",
            "0123456789abcdef",
        )
    ]

    findings = scan_entries(entries, AuditPolicy())

    assert [(item.code, item.path.as_posix()) for item in findings] == [
        ("personal-path-in-text", "notes.md")
    ]


def test_run_audit_returns_two_for_malformed_git_records(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def malformed_source(_root: Path) -> list[AuditEntry]:
        raise privacy.AuditSourceError("malformed NUL-delimited index output")

    monkeypatch.setattr(privacy, "index_entries", malformed_source)

    exit_code = privacy.run_audit(tmp_path, "staged")

    assert exit_code == 2
    assert capsys.readouterr().out.strip() == (
        "audit source error: malformed NUL-delimited index output"
    )


def test_run_audit_rejects_a_tracked_terms_file_above_a_nested_root(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    nested = tmp_path / "docs"
    nested.mkdir()
    terms = tmp_path / "owner-terms.txt"
    terms.write_text("private codename\n", encoding="utf-8")
    (nested / "guide.md").write_text("Safe.\n", encoding="utf-8")
    subprocess.run(["git", "add", "owner-terms.txt", "docs/guide.md"], cwd=tmp_path, check=True)

    exit_code = privacy.run_audit(nested, "tree", terms, {})

    assert exit_code == 2
    output = capsys.readouterr().out.strip()
    assert output == "private terms file must remain external or ignored"
    assert "private codename" not in output


def test_run_audit_reads_private_terms_from_environment_without_echoing_them(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    private_term = "Environment-only Codename"
    terms = tmp_path.parent / f"{tmp_path.name}-owner-terms.txt"
    terms.write_text(private_term + "\n", encoding="utf-8")
    (tmp_path / "notes.md").write_text(private_term.lower(), encoding="utf-8")

    exit_code = privacy.run_audit(
        tmp_path,
        "tree",
        environ={"VOICE_KIT_PRIVATE_TERMS_FILE": str(terms)},
    )

    assert exit_code == 1
    output = capsys.readouterr().out.strip()
    assert "private-term-content: notes.md" in output
    assert private_term.casefold() not in output.casefold()


def _history_exception(object_id: str, code: str) -> object:
    return privacy.HistoryException(
        object_id=object_id,
        finding_code=code,
        reason="reviewed synthetic fixture",
    )


def test_history_exceptions_accept_only_an_exact_object_and_finding_pair() -> None:
    object_id = "1" * 40
    entry = AuditEntry(
        PurePosixPath("fixture.md"),
        b"test" + b"@" + b"example.invalid\n",
        "history",
        object_id,
    )

    findings, accepted = privacy.scan_history_entries(
        [entry],
        AuditPolicy(),
        (_history_exception(object_id, "identity-content"),),
    )

    assert findings == []
    assert [(item.object_id, item.finding_code) for item in accepted] == [
        (object_id, "identity-content")
    ]


def test_history_exception_with_the_wrong_finding_code_fails_closed() -> None:
    object_id = "2" * 40
    entry = AuditEntry(
        PurePosixPath("fixture.md"),
        b"test" + b"@" + b"example.invalid\n",
        "history",
        object_id,
    )

    with pytest.raises(privacy.AuditSourceError, match="stale or unconsumed"):
        privacy.scan_history_entries(
            [entry],
            AuditPolicy(),
            (_history_exception(object_id, "credential-content"),),
        )


def test_history_exception_cannot_suppress_an_owner_private_term(
    tmp_path: Path,
) -> None:
    object_id = "3" * 40
    private_term = "Owner-only Zephyr"
    terms = tmp_path / "terms.txt"
    terms.write_text(private_term + "\n", encoding="utf-8")
    entry = AuditEntry(
        PurePosixPath("fixture.md"),
        ("test" + "@" + "example.invalid\n" + private_term).encode("utf-8"),
        "history",
        object_id,
    )

    findings, accepted = privacy.scan_history_entries(
        [entry],
        AuditPolicy(private_terms_file=terms),
        (_history_exception(object_id, "identity-content"),),
    )

    assert [item.code for item in findings] == ["private-term-content"]
    assert [item.finding_code for item in accepted] == ["identity-content"]


def test_history_exceptions_do_not_weaken_direct_or_non_history_scans() -> None:
    object_id = "4" * 40
    entry = AuditEntry(
        PurePosixPath("fixture.md"),
        b"test" + b"@" + b"example.invalid\n",
        "tree",
        object_id,
    )

    assert [item.code for item in scan_entries([entry], AuditPolicy())] == [
        "identity-content"
    ]
    with pytest.raises(privacy.AuditSourceError, match="non-history entry"):
        privacy.scan_history_entries(
            [entry],
            AuditPolicy(),
            (_history_exception(object_id, "identity-content"),),
        )


@pytest.mark.parametrize(
    ("definitions", "message"),
    [
        (
            (
                ("5" * 40, "identity-content"),
                ("5" * 40, "identity-content"),
            ),
            "duplicate",
        ),
        ((("short", "identity-content"),), "40 lowercase"),
        ((("6" * 40, "unknown-code"),), "unknown finding code"),
    ],
)
def test_history_exception_definitions_fail_closed_when_malformed(
    definitions: tuple[tuple[str, str], ...], message: str
) -> None:
    exceptions = tuple(
        _history_exception(object_id, code) for object_id, code in definitions
    )
    with pytest.raises(privacy.AuditSourceError, match=message):
        privacy.scan_history_entries([], AuditPolicy(), exceptions)


def test_history_exception_fails_when_object_is_missing() -> None:
    with pytest.raises(privacy.AuditSourceError, match="missing historical object"):
        privacy.scan_history_entries(
            [],
            AuditPolicy(),
            (_history_exception("7" * 40, "identity-content"),),
        )


def test_history_exception_fails_when_pair_is_stale() -> None:
    object_id = "8" * 40
    entry = AuditEntry(
        PurePosixPath("safe.md"), b"safe\n", "history", object_id
    )

    with pytest.raises(privacy.AuditSourceError, match="stale or unconsumed"):
        privacy.scan_history_entries(
            [entry],
            AuditPolicy(),
            (_history_exception(object_id, "identity-content"),),
        )


def test_history_scan_rejects_a_malformed_entry_object_id() -> None:
    entry = AuditEntry(PurePosixPath("safe.md"), b"safe\n", "history", "bad")

    with pytest.raises(privacy.AuditSourceError, match="malformed history object ID"):
        privacy.scan_history_entries([entry], AuditPolicy(), ())


def test_history_audit_rejects_private_text_in_a_commit_message(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "config", "user.name", "gitramnag"], cwd=tmp_path, check=True
    )
    subprocess.run(
        [
            "git",
            "config",
            "user.email",
            "315322897+gitramnag@users.noreply.github.com",
        ],
        cwd=tmp_path,
        check=True,
    )
    (tmp_path / "safe.md").write_text("safe bytes\n", encoding="utf-8")
    subprocess.run(["git", "add", "safe.md"], cwd=tmp_path, check=True)
    subprocess.run(
        [
            "git",
            "commit",
            "-q",
            "-m",
            "record C:" + r"\Users\PrivatePerson\voice\render.py",
        ],
        cwd=tmp_path,
        check=True,
    )
    commit_id = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()

    exit_code = privacy.run_audit(tmp_path, "history")

    assert exit_code == 1
    output = capsys.readouterr().out
    assert f"personal-path-in-text: .git-history/{commit_id}.commit" in output
    assert "PrivatePerson" not in output


def _initialise_history_exception_repository(root: Path, content: str) -> str:
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "gitramnag"], cwd=root, check=True)
    subprocess.run(
        [
            "git",
            "config",
            "user.email",
            "315322897+gitramnag@users.noreply.github.com",
        ],
        cwd=root,
        check=True,
    )
    fixture = root / "fixture.md"
    fixture.write_text(content, encoding="utf-8")
    object_id = subprocess.run(
        ["git", "hash-object", "-w", "fixture.md"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    manifest = root / privacy.HISTORY_EXCEPTIONS_PATH
    manifest.parent.mkdir(parents=True)
    manifest.write_text(
        json.dumps(
            {
                "version": 1,
                "exceptions": [
                    {
                        "object_id": object_id,
                        "finding_code": "identity-content",
                        "reason": "synthetic reserved-domain fixture",
                    }
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "add", "."], cwd=root, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "fixture"], cwd=root, check=True)
    return object_id


def test_run_audit_history_loads_exact_exceptions_and_reports_acceptance(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _initialise_history_exception_repository(
        tmp_path, "test" + "@" + "example.invalid\n"
    )

    exit_code = privacy.run_audit(tmp_path, "history")

    assert exit_code == 0
    output = capsys.readouterr().out
    assert "accepted 1 reviewed history exception" in output
    assert "identity-content=1" in output
    assert output.rstrip().endswith("publication boundary check passed")


def test_run_audit_tree_ignores_history_exceptions(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _initialise_history_exception_repository(
        tmp_path, "test" + "@" + "example.invalid\n"
    )

    exit_code = privacy.run_audit(tmp_path, "tree")

    assert exit_code == 1
    output = capsys.readouterr().out
    assert "identity-content: fixture.md" in output
    assert "reviewed history exception" not in output


def test_run_audit_history_keeps_private_term_findings_blocking(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    private_term = "Owner-only Zephyr"
    _initialise_history_exception_repository(
        tmp_path, "test" + "@" + "example.invalid\n" + private_term
    )
    terms = tmp_path.parent / f"{tmp_path.name}-terms.txt"
    terms.write_text(private_term + "\n", encoding="utf-8")

    exit_code = privacy.run_audit(tmp_path, "history", terms, {})

    assert exit_code == 1
    output = capsys.readouterr().out
    assert "accepted 1 reviewed history exception" in output
    assert "private-term-content: fixture.md" in output
    assert private_term.casefold() not in output.casefold()


def test_run_audit_history_fails_closed_for_malformed_manifest(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=tmp_path, check=True)
    manifest = tmp_path / privacy.HISTORY_EXCEPTIONS_PATH
    manifest.parent.mkdir(parents=True)
    manifest.write_text("{not-json}\n", encoding="utf-8")

    exit_code = privacy.run_audit(tmp_path, "history")

    assert exit_code == 2
    assert capsys.readouterr().out.strip() == (
        "audit source error: reviewed history exception manifest is malformed"
    )


@pytest.mark.parametrize("version", [True, 1.0, 2])
def test_history_exception_manifest_requires_exact_integer_version(
    tmp_path: Path, version: object
) -> None:
    manifest = tmp_path / privacy.HISTORY_EXCEPTIONS_PATH
    manifest.parent.mkdir(parents=True)
    manifest.write_text(
        json.dumps({"version": version, "exceptions": []}) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(privacy.AuditSourceError, match="manifest is malformed"):
        privacy.load_history_exceptions(tmp_path)


def test_history_exception_manifest_accepts_exact_integer_version_one(
    tmp_path: Path,
) -> None:
    manifest = tmp_path / privacy.HISTORY_EXCEPTIONS_PATH
    manifest.parent.mkdir(parents=True)
    manifest.write_text(
        json.dumps({"version": 1, "exceptions": []}) + "\n",
        encoding="utf-8",
    )

    assert privacy.load_history_exceptions(tmp_path) == ()


def test_scanner_accepts_its_own_public_files_apart_from_release_residue() -> None:
    repository_root = Path(__file__).resolve().parents[1]

    findings = scan_repository(repository_root)

    assert {item.code for item in findings} <= {"ignored-workflow-state"}
