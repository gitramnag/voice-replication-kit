from __future__ import annotations

import json
import re
from pathlib import Path

from scripts.check_links import check_links


ROOT = Path(__file__).resolve().parents[1]
OPERATOR_FILES = (
    ROOT / "README.md",
    ROOT / "SECURITY.md",
    ROOT / "CONTRIBUTING.md",
    ROOT / "docs" / "architecture.md",
    ROOT / "docs" / "replication-guide.md",
    ROOT / "docs" / "evaluation-guide.md",
    ROOT / "docs" / "privacy-boundary.md",
    ROOT / "docs" / "troubleshooting.md",
    *(sorted((ROOT / "docs" / "passes").glob("*.md"))),
)
USER_COMMANDS = (
    "init-private",
    "validate-profile",
    "build-requests",
    "build-matrix",
    "build-blind-map",
    "render",
)


def _shell_fences(path: Path) -> list[str]:
    fences: list[str] = []
    language = ""
    body: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not language:
            match = re.match(r"^```(powershell|pwsh|bash|sh)\s*$", line, re.I)
            if match:
                language = match.group(1).lower()
                body = []
            continue
        if line == "```":
            fences.append("\n".join(body))
            language = ""
            body = []
            continue
        body.append(line)
    return fences


def _command_details(tmp_path: Path, markdown: str) -> list[str]:
    (tmp_path / "guide.md").write_text(markdown, encoding="utf-8")
    findings, _, _ = check_links(tmp_path)
    return [finding.detail for finding in findings]


def test_readme_quickstart_uses_external_root_and_all_user_commands() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "VOICE_KIT_PRIVATE_ROOT" in readme
    for command in (
        "init-private",
        "validate-profile",
        "build-requests",
        "build-matrix",
        "build-blind-map",
        "render --validate-only",
        "render --smoke",
    ):
        assert f"voice-kit {command}" in readme
    assert "new 24 kHz WAV" in readme
    assert "ready for the next script" in readme.lower()


def test_readme_keeps_the_six_step_outcome_ladder_verbatim() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    expected = """1. Record the public script in your own voice.
   Output: private WAV recordings outside the Git checkout.
2. Test reference clips, seeds and text shapes through Passes 00 to 04.
   Output: private scorecards and one accepted recipe for each needed style.
3. Freeze the accepted recipes in Pass 05.
   Output: a validated private profile that points to your own reference WAVs.
4. Build and validate immutable requests in Pass 06.
   Output: a private request pack bound to the script, profile and model revision.
5. Render one smoke item, listen, then render the batch.
   Output: new 24 kHz WAV files and appended private manifest records.
6. Supply another script and repeat from request construction.
   Output: the same private voice setup is ready for the next script."""
    assert expected in readme


def test_pass_07_is_maintainer_only() -> None:
    architecture = (ROOT / "docs" / "architecture.md").read_text(encoding="utf-8")
    assert "Maintainer publication branch" in architecture
    assert architecture.index("Ready for the next script") < architecture.index(
        "Maintainer publication branch"
    )


def test_security_history_exception_summary_matches_reviewed_manifest() -> None:
    security = (ROOT / "SECURITY.md").read_text(encoding="utf-8")
    manifest = json.loads(
        (ROOT / "configs" / "reviewed-history-exceptions.json").read_text(
            encoding="utf-8"
        )
    )
    summary = re.search(
        r"records (\d+) accepted findings on (\d+)\s+immutable historical blob IDs",
        security,
    )

    assert summary is not None
    assert tuple(map(int, summary.groups())) == (
        len(manifest["exceptions"]),
        len({item["object_id"] for item in manifest["exceptions"]}),
    )


def test_operator_manual_names_every_cli_command() -> None:
    manual = "\n".join(path.read_text(encoding="utf-8") for path in OPERATOR_FILES)
    for command in (*USER_COMMANDS, "audit"):
        assert f"voice-kit {command}" in manual


def test_shell_examples_never_use_checkout_relative_private_paths() -> None:
    relative_private = re.compile(r"(?i)(?<![$\w-])(?:\.[/\\])?private[/\\]")
    offenders = [
        path.relative_to(ROOT).as_posix()
        for path in OPERATOR_FILES
        if any(relative_private.search(fence) for fence in _shell_fences(path))
    ]
    assert offenders == []


def test_manual_does_not_claim_that_a_real_gpu_render_ran_here() -> None:
    for path in OPERATOR_FILES:
        prose = path.read_text(encoding="utf-8")
        for sentence in re.split(r"(?<=[.!?])\s+", prose):
            if "real GPU render" not in sentence:
                continue
            assert re.search(r"\b(?:not|never|no)\b", sentence, re.I), (
                path.relative_to(ROOT).as_posix(),
                sentence,
            )


def test_full_batch_docs_include_the_smoke_request_again() -> None:
    relevant = (
        ROOT / "README.md",
        ROOT / "docs" / "architecture.md",
        ROOT / "docs" / "replication-guide.md",
        ROOT / "docs" / "troubleshooting.md",
        ROOT / "docs" / "passes" / "06-production-renderer.md",
    )
    for path in relevant:
        prose = " ".join(path.read_text(encoding="utf-8").lower().split())
        assert "including the smoke request again" in prose, path.relative_to(ROOT)
        assert "manifest record" in prose, path.relative_to(ROOT)

    manual = "\n".join(path.read_text(encoding="utf-8") for path in OPERATOR_FILES)
    assert re.search(
        r"(?i)\b(?:remaining|rest of (?:the )?)\s+"
        r"(?:matrix|batch|requests?|items?)\b",
        manual,
    ) is None


def test_link_checker_parses_a_direct_voice_kit_invocation(tmp_path: Path) -> None:
    details = _command_details(
        tmp_path,
        """# Guide

```powershell
voice-kit render --smoke-only --private-root 'D:\\voice-kit-private\\demo-voice'
```
""",
    )
    assert any(
        "unsupported flag for voice-kit render: --smoke-only" in item
        for item in details
    )


def test_link_checker_parses_an_environment_prefixed_invocation(
    tmp_path: Path,
) -> None:
    details = _command_details(
        tmp_path,
        """# Guide

```bash
VOICE_KIT_PRIVATE_ROOT=/srv/voice-kit-private/demo-voice voice-kit render --smoke-only
```
""",
    )
    assert details == ["unsupported flag for voice-kit render: --smoke-only"]


def test_link_checker_parses_a_quoted_executable(tmp_path: Path) -> None:
    details = _command_details(
        tmp_path,
        """# Guide

```bash
"$VOICE_KIT_PRIVATE_ROOT/runtime/venv/bin/voice-kit" render --smoke-only
```
""",
    )
    assert details == ["unsupported flag for voice-kit render: --smoke-only"]


def test_link_checker_preserves_native_shell_continuations(tmp_path: Path) -> None:
    details = _command_details(
        tmp_path,
        """# Guide

```powershell
voice-kit render `
  --smoke-only
```

```bash
voice-kit render \\
  --smoke-only
```
""",
    )
    assert details == [
        "unsupported flag for voice-kit render: --smoke-only",
        "unsupported flag for voice-kit render: --smoke-only",
    ]


def test_link_checker_isolates_separated_invocations_and_quoted_separators(
    tmp_path: Path,
) -> None:
    details = _command_details(
        tmp_path,
        """# Guide

```bash
voice-kit render --smoke ; voice-kit validate-profile --profile /srv/voice-kit-private/demo-voice/upload/private-profile.json
voice-kit render --smoke && voice-kit invent --later-only
voice-kit build-requests --document '/srv/voice-kit-private/demo-voice/upload/script;v2.json' --output /srv/voice-kit-private/demo-voice/upload/requests.jsonl && voice-kit render --smoke
voice-kit build-requests --document /srv/voice-kit-private/demo-voice/upload/script\\;v3.json --output /srv/voice-kit-private/demo-voice/upload/requests-v3.jsonl ; voice-kit render --smoke
```
""",
    )
    assert details == ["unsupported voice-kit command: invent"]


def test_link_checker_never_executes_fenced_shell_text(tmp_path: Path) -> None:
    sentinel = tmp_path / "must-not-exist.txt"
    details = _command_details(
        tmp_path,
        f"""# Guide

```bash
touch '{sentinel.as_posix()}' ; voice-kit render --smoke
```
""",
    )
    assert details == []
    assert not sentinel.exists()


def test_all_documented_voice_kit_commands_match_the_parser() -> None:
    findings, _, _ = check_links(ROOT)
    command_findings = [
        finding
        for finding in findings
        if "voice-kit command" in finding.detail
        or "flag for voice-kit" in finding.detail
    ]
    assert command_findings == []


def test_evaluation_guide_uses_current_sheet_names() -> None:
    guide = (ROOT / "docs" / "evaluation-guide.md").read_text(encoding="utf-8")
    assert "`Instructions`" in guide
    assert "`Ratings`" in guide
    assert "`Decisions`" in guide
    assert "`Scorecard` sheet" not in guide


def test_inference_requirements_match_the_approved_diagram_and_runtime_lock() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    guide = (ROOT / "docs" / "replication-guide.md").read_text(encoding="utf-8")
    troubleshooting = (ROOT / "docs" / "troubleshooting.md").read_text(
        encoding="utf-8"
    )

    for document in (readme, guide):
        assert "16 GB RAM" in document
        assert "20 GB free disk" in document
        assert "8 GB VRAM" in document
        assert "PYTHON_BIN" in document
        assert "PyTorch 2.3.1" in document
        assert "CUDA 12.1" in document
        assert "sm_50" in document
        assert "sm_90" in document
        assert "sm_120" in document
    assert "sm_120" in troubleshooting
    assert "new external private root" in troubleshooting


def test_evaluation_plan_guide_names_all_required_prompt_fields() -> None:
    guide = (ROOT / "docs" / "replication-guide.md").read_text(encoding="utf-8")

    for field in (
        "source_segment_id",
        "unit_index",
        "language",
        "pronunciation_overrides",
    ):
        assert f"`{field}`" in guide


def test_publication_docs_set_the_approved_identity_and_forbid_folder_zips() -> None:
    pass_07 = (ROOT / "docs" / "passes" / "07-publication-audit.md").read_text(
        encoding="utf-8"
    )
    contributing = (ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")
    security = (ROOT / "SECURITY.md").read_text(encoding="utf-8")

    for document in (pass_07, contributing):
        assert "git config --local user.name gitramnag" in document
        assert (
            "git config --local user.email "
            "315322897+gitramnag@users.noreply.github.com"
        ) in document
    for document in (pass_07, security):
        assert "git push" in document
        assert "git archive" in document
        assert "Do not ZIP the working folder" in document


def test_public_tool_install_docs_use_the_hash_lock() -> None:
    for path in (ROOT / "README.md", ROOT / "CONTRIBUTING.md"):
        document = path.read_text(encoding="utf-8")
        assert (
            "python -m pip install --require-hashes "
            "-r configs/public-tools-lock.txt"
        ) in document
        assert (
            "python -m pip install --no-build-isolation --no-deps -e ."
            in document
        )
        assert 'pip install -e ".[dev]"' not in document
        assert "pip install -e '.[dev]'" not in document


def test_security_records_the_reviewed_runtime_dependency_decision() -> None:
    security = (ROOT / "SECURITY.md").read_text(encoding="utf-8")
    for required in (
        "11 October 2026",
        "186 findings in 16 locked packages",
        "isolated private runtime",
        "untrusted public service",
        "reviewed CosyVoice runtime upgrade",
    ):
        assert required in security
