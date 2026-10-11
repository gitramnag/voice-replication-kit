from __future__ import annotations

import builtins
import hashlib
import json
from pathlib import Path

from voice_replication_kit.cli import _dispatch as main
from voice_replication_kit.matrix import write_jsonl_immutable
from voice_replication_kit.requests import request_identity


MODEL_REVISION = "29e01c4e8d000f4bcd70751be16fa94bf3d85a18"


def _private_pack(tmp_path: Path) -> Path:
    private_root = tmp_path / "external-private-root"
    reference = private_root / "upload" / "refs" / "synthetic.wav"
    reference.parent.mkdir(parents=True)
    reference.write_bytes(b"synthetic reference")
    reference_text = "Synthetic speaker-agnostic reference."
    request = {
        "schema_version": 1,
        "prompt_id": "synthetic_prompt",
        "source_segment_id": "synthetic-segment",
        "unit_index": 1,
        "style": "narration_neutral",
        "language": "en",
        "text": "Synthetic sentence for validation.",
        "seed": 4242,
        "reference_file": "refs/synthetic.wav",
        "reference_text": reference_text,
        "reference_sha256": hashlib.sha256(reference.read_bytes()).hexdigest(),
        "reference_text_sha256": hashlib.sha256(reference_text.encode()).hexdigest(),
        "text_shape": "connected_sentence",
        "model_revision": MODEL_REVISION,
        "pronunciation_overrides": {},
    }
    request["request_id"] = request_identity(request)
    write_jsonl_immutable(private_root / "upload" / "requests.jsonl", [request])
    (private_root / "upload" / "private-profile.json").write_text(
        json.dumps({"schema_version": 1, "fixture": "speaker-agnostic"}),
        encoding="utf-8",
    )
    return private_root


def test_render_validate_only_checks_pack_without_importing_gpu_dependencies(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    private_root = _private_pack(tmp_path)
    real_import = builtins.__import__

    def reject_gpu_import(name: str, *args, **kwargs):
        if name.split(".", 1)[0] in {"torch", "cosyvoice", "huggingface_hub"}:
            raise AssertionError(f"validate-only imported {name}")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", reject_gpu_import)

    exit_code = main(
        [
            "render",
            "--private-root",
            str(private_root),
            "--smoke",
            "--validate-only",
        ]
    )

    assert exit_code == 0
    assert capsys.readouterr().out.strip() == "validated 1 private CosyVoice requests"


def test_render_requires_external_private_root(monkeypatch) -> None:
    monkeypatch.delenv("VOICE_KIT_PRIVATE_ROOT", raising=False)

    try:
        main(["render", "--validate-only"])
    except ValueError as error:
        assert "--private-root or VOICE_KIT_PRIVATE_ROOT" in str(error)
    else:
        raise AssertionError("render accepted no private root")


def test_render_rejects_request_pack_outside_private_root(tmp_path: Path) -> None:
    private_root = _private_pack(tmp_path)
    outside = tmp_path / "outside.jsonl"
    outside.write_text("{}\n", encoding="utf-8")

    try:
        main(
            [
                "render",
                "--private-root",
                str(private_root),
                "--requests",
                str(outside),
                "--validate-only",
            ]
        )
    except ValueError as error:
        assert "beneath the private root" in str(error)
    else:
        raise AssertionError("render accepted an external request pack")
