from __future__ import annotations

import hashlib
import json
import os
from concurrent.futures import ProcessPoolExecutor
import subprocess
import sys
import types
import wave
from pathlib import Path

import pytest

from voice_replication_kit.matrix import write_jsonl_immutable
from voice_replication_kit.rendering import (
    _download_model_snapshot,
    CosyVoiceBackend,
    ManifestChain,
    ManifestIntegrityError,
    RenderOptions,
    render_requests,
    verify_manifest_chain,
)
from voice_replication_kit.requests import request_identity


MODEL_REVISION = "29e01c4e8d000f4bcd70751be16fa94bf3d85a18"
REFERENCE_BYTES = b"synthetic reference fixture"
ROOT = Path(__file__).resolve().parents[1]


def _pinned_source_checkout(
    path: Path, origin: str, files: dict[str, str]
) -> str:
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    subprocess.run(
        ["git", "config", "user.name", "Runtime Test"], cwd=path, check=True
    )
    subprocess.run(
        ["git", "config", "user.email", "runtime-test" + "@" + "example.invalid"],
        cwd=path,
        check=True,
    )
    for relative, content in files.items():
        target = path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=path, check=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", "pinned synthetic source"],
        cwd=path,
        check=True,
    )
    subprocess.run(["git", "remote", "add", "origin", origin], cwd=path, check=True)
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=path,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _request(index: int = 1) -> dict:
    reference_text = "Synthetic speaker-agnostic reference transcript."
    row = {
        "schema_version": 1,
        "prompt_id": f"synthetic_prompt_{index:02d}",
        "source_segment_id": f"synthetic-segment-{index}",
        "unit_index": 1,
        "style": "narration_neutral",
        "language": "en",
        "text": f"Synthetic render request number {index}.",
        "seed": 4200 + index,
        "reference_file": "refs/synthetic-reference.wav",
        "reference_text": reference_text,
        "reference_sha256": hashlib.sha256(REFERENCE_BYTES).hexdigest(),
        "reference_text_sha256": hashlib.sha256(reference_text.encode()).hexdigest(),
        "text_shape": "connected_sentence",
        "model_revision": MODEL_REVISION,
        "pronunciation_overrides": {},
    }
    row["request_id"] = request_identity(row)
    return row


def _private_root(tmp_path: Path, count: int = 1) -> tuple[Path, Path]:
    root = tmp_path / "authorised-private-root"
    reference = root / "upload" / "refs" / "synthetic-reference.wav"
    reference.parent.mkdir(parents=True)
    reference.write_bytes(REFERENCE_BYTES)
    profile = root / "upload" / "private-profile.json"
    profile.write_text(
        json.dumps({"schema_version": 1, "fixture": "speaker-agnostic"}),
        encoding="utf-8",
    )
    requests = root / "upload" / "requests.jsonl"
    write_jsonl_immutable(requests, [_request(index) for index in range(1, count + 1)])
    return root, requests


def _write_wav(path: Path, sample_rate: int = 24_000) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(sample_rate)
        stream.writeframes(b"\x00\x00" * 24)


class SyntheticBackend:
    def __init__(
        self,
        *,
        sample_rate: int = 24_000,
        fail: bool = False,
        provenance: dict[str, object] | None = None,
    ) -> None:
        self.sample_rate = sample_rate
        self.fail = fail
        self.provenance = provenance or {}
        self.prepare_calls = 0
        self.render_calls = 0
        self.repository_root = ROOT

    def prepare(self, _private_root: Path) -> dict:
        self.prepare_calls += 1
        base = {
            "python_version": "3.10.19",
            "torch_version": "2.3.1+cu121",
            "cuda_version": "12.1",
            "device": "Synthetic GPU",
            "precision": "fp16",
            "source_revisions": {
                "cosyvoice": "0" * 40,
                "matcha_tts": "1" * 40,
            },
            "model_repository": "synthetic/model",
            "model_revision": MODEL_REVISION,
            "model_manifest_sha256": "2" * 64,
            "runtime_lock_sha256": "3" * 64,
            "runtime_provenance_sha256": "4" * 64,
        }
        return dict(base, **self.provenance)

    def render(self, _request: dict, _reference: Path, output: Path) -> None:
        self.render_calls += 1
        if self.fail:
            raise RuntimeError("out of memory")
        _write_wav(output, self.sample_rate)


def _records(root: Path) -> list[dict]:
    manifest = root / "results" / "manifest.jsonl"
    return [json.loads(line) for line in manifest.read_text(encoding="utf-8").splitlines()]


def _append_concurrently(path_text: str, worker: int, count: int) -> int:
    chain = ManifestChain(Path(path_text))
    for index in range(count):
        chain.append(
            {
                "request_id": f"worker-{worker}-record-{index}",
                "status": "success",
            }
        )
    return count


def _make_directory_alias(target: Path, alias: Path) -> None:
    alias.parent.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        result = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(alias), str(target)],
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            pytest.skip(f"Windows denied junction creation: {result.stderr.strip()}")
    else:
        alias.symlink_to(target, target_is_directory=True)


def _remove_directory_alias(alias: Path) -> None:
    if os.name == "nt":
        os.rmdir(alias)
    else:
        alias.unlink()


def _tamper_jsonl_line(path: Path, line: int, field: str, value: object) -> None:
    rows = path.read_text(encoding="utf-8").splitlines()
    record = json.loads(rows[line - 1])
    record[field] = value
    rows[line - 1] = json.dumps(record, sort_keys=True, separators=(",", ":"))
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def test_manifest_chain_detects_modified_record(tmp_path: Path) -> None:
    chain = ManifestChain(tmp_path / "manifest.jsonl")
    first = chain.append({"request_id": "request-a", "status": "success"})
    second = chain.append(
        {"request_id": "request-b", "status": "failure", "failure_code": "cuda"}
    )
    assert second["previous_record_sha256"] == first["record_sha256"]
    verify_manifest_chain(chain.path)

    _tamper_jsonl_line(chain.path, line=1, field="status", value="failure")

    with pytest.raises(ManifestIntegrityError, match="line 1"):
        verify_manifest_chain(chain.path)


def test_manifest_chain_serializes_concurrent_process_appends(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.jsonl"

    with ProcessPoolExecutor(max_workers=4) as executor:
        counts = list(
            executor.map(
                _append_concurrently,
                [str(manifest)] * 4,
                range(4),
                [12] * 4,
            )
        )

    assert sum(counts) == 48
    verify_manifest_chain(manifest)
    assert len(manifest.read_text(encoding="utf-8").splitlines()) == 48


def test_failed_inference_is_recorded_without_output_digest(tmp_path: Path) -> None:
    root, requests = _private_root(tmp_path)

    summary = render_requests(
        root, requests, RenderOptions(smoke=True), SyntheticBackend(fail=True)
    )

    record = _records(root)[0]
    assert summary.failed == 1
    assert record["status"] == "failure"
    assert "output_sha256" not in record
    assert record["failure_code"] == "inference-error"


def test_success_records_all_input_and_runtime_provenance(tmp_path: Path) -> None:
    root, requests = _private_root(tmp_path)
    backend = SyntheticBackend()

    summary = render_requests(root, requests, RenderOptions(smoke=True), backend)

    record = _records(root)[0]
    request = _request()
    assert summary.rendered == 1
    assert record["status"] == "success"
    assert record["request_sha256"] == hashlib.sha256(
        json.dumps(request, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()
    assert record["request_pack_sha256"] == hashlib.sha256(requests.read_bytes()).hexdigest()
    assert record["profile_sha256"] == hashlib.sha256(
        (root / "upload" / "private-profile.json").read_bytes()
    ).hexdigest()
    assert record["reference_sha256"] == hashlib.sha256(REFERENCE_BYTES).hexdigest()
    assert record["source_revisions"] == {
        "cosyvoice": "0" * 40,
        "matcha_tts": "1" * 40,
    }
    assert record["model_revision"] == MODEL_REVISION
    assert record["model_manifest_sha256"] == "2" * 64
    assert record["python_version"] == "3.10.19"
    assert record["torch_version"] == "2.3.1+cu121"
    assert record["cuda_version"] == "12.1"
    assert record["device"] == "Synthetic GPU"
    assert record["precision"] == "fp16"
    assert record["sample_rate"] == 24_000
    assert backend.prepare_calls == 1


def test_existing_output_is_not_overwritten(tmp_path: Path) -> None:
    root, requests = _private_root(tmp_path)
    render_requests(root, requests, RenderOptions(smoke=True), SyntheticBackend())
    first = root / "results" / "raw" / "cosyvoice3" / f"{_request()['request_id']}.wav"
    original = first.read_bytes()

    render_requests(root, requests, RenderOptions(smoke=True), SyntheticBackend())

    assert first.read_bytes() == original
    assert _records(root)[1]["output_file"].endswith("__r2.wav")


def test_racing_output_creation_is_preserved(tmp_path: Path, monkeypatch) -> None:
    root, requests = _private_root(tmp_path)
    real_link = os.link
    raced = False

    def race_once(source: Path, destination: Path) -> None:
        nonlocal raced
        if not raced:
            raced = True
            Path(destination).write_bytes(b"another renderer won")
        real_link(source, destination)

    monkeypatch.setattr("voice_replication_kit.rendering.os.link", race_once)

    render_requests(root, requests, RenderOptions(smoke=True), SyntheticBackend())

    first = root / "results" / "raw" / "cosyvoice3" / f"{_request()['request_id']}.wav"
    assert first.read_bytes() == b"another renderer won"
    assert _records(root)[0]["output_file"].endswith("__r2.wav")


def test_non_24_khz_output_is_recorded_as_validation_failure(tmp_path: Path) -> None:
    root, requests = _private_root(tmp_path)

    summary = render_requests(
        root, requests, RenderOptions(smoke=True), SyntheticBackend(sample_rate=16_000)
    )

    record = _records(root)[0]
    assert summary.failed == 1
    assert record["status"] == "failure"
    assert record["failure_code"] == "output-validation-error"
    assert "output_sha256" not in record
    assert not list((root / "results" / "raw" / "cosyvoice3").glob("*.wav"))


def test_huggingface_local_metadata_stays_out_of_verified_model_tree(
    tmp_path: Path,
) -> None:
    model_root = tmp_path / "private" / "runtime" / "models" / "cosyvoice3"
    cache_root = tmp_path / "private" / "runtime" / "cache" / "huggingface"
    payload = b"reviewed synthetic model bytes"
    manifest = {
        "files": [
            {
                "path": "config.json",
                "size": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest(),
            }
        ]
    }

    def pinned_layout(**kwargs: object) -> str:
        local_dir = Path(str(kwargs["local_dir"]))
        local_dir.mkdir(parents=True)
        (local_dir / "config.json").write_bytes(payload)
        metadata = local_dir / ".cache" / "huggingface" / "download"
        metadata.mkdir(parents=True)
        (metadata / "config.json.metadata").write_text("metadata", encoding="utf-8")
        Path(str(kwargs["cache_dir"])).mkdir(parents=True)
        return str(local_dir)

    _download_model_snapshot(
        pinned_layout,
        repository="synthetic/model",
        revision="a" * 40,
        model_root=model_root,
        cache_root=cache_root,
    )

    from voice_replication_kit.runtime import verify_model_snapshot

    verify_model_snapshot(model_root, manifest)
    assert not (model_root / ".cache").exists()
    (model_root / "unrelated.txt").write_text("surplus", encoding="utf-8")
    with pytest.raises(ValueError, match="unexpected model file"):
        verify_model_snapshot(model_root, manifest)


def test_cosyvoice_backend_keeps_verified_source_checkouts_clean_across_prepares(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    public_root = tmp_path / "public"
    private_root = tmp_path / "private"
    source_root = private_root / "runtime" / "cosyvoice"
    matcha_root = source_root / "third_party" / "Matcha-TTS"
    cosyvoice_origin = "https://example.invalid/cosyvoice.git"
    matcha_origin = "https://example.invalid/matcha-tts.git"
    ignored_bytecode = "__pycache__/\n*.py[co]\n"
    matcha_commit = _pinned_source_checkout(
        matcha_root,
        matcha_origin,
        {
            ".gitignore": ignored_bytecode,
            "matcha/__init__.py": "MATCHA_READY = True\n",
        },
    )
    cosyvoice_commit = _pinned_source_checkout(
        source_root,
        cosyvoice_origin,
        {
            ".gitignore": ignored_bytecode,
            "cosyvoice/__init__.py": "",
            "cosyvoice/cli/__init__.py": "",
            "cosyvoice/cli/cosyvoice.py": (
                "from matcha import MATCHA_READY\n\n"
                "class CosyVoice3:\n"
                "    sample_rate = 24000\n\n"
                "    def __init__(self, model_root, fp16):\n"
                "        self.model_root = model_root\n"
                "        self.fp16 = fp16\n"
                "        assert MATCHA_READY\n"
            ),
        },
    )

    configs = public_root / "configs"
    configs.mkdir(parents=True)
    (configs / "pins.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "python": "3.10",
                "sources": {
                    "cosyvoice": {
                        "url": cosyvoice_origin,
                        "commit": cosyvoice_commit,
                    },
                    "matcha_tts": {
                        "url": matcha_origin,
                        "commit": matcha_commit,
                    },
                },
                "model": {
                    "repository": "synthetic/cosyvoice-model",
                    "revision": MODEL_REVISION,
                },
            }
        ),
        encoding="utf-8",
    )
    model_bytes = b"{}\n"
    (configs / "model-manifest.json").write_text(
        json.dumps(
            {
                "files": [
                    {
                        "path": "config.json",
                        "size": len(model_bytes),
                        "sha256": hashlib.sha256(model_bytes).hexdigest(),
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    (configs / "runtime-lock.txt").write_text("synthetic lock\n", encoding="utf-8")
    provenance = private_root / "runtime" / "provenance.json"
    provenance.write_text(
        json.dumps({"python": "3.10.19", "packages": {"torch": "2.3.1"}}),
        encoding="utf-8",
    )

    huggingface_hub = types.ModuleType("huggingface_hub")

    def snapshot_download(**kwargs: object) -> str:
        model_root = Path(str(kwargs["local_dir"]))
        model_root.mkdir(parents=True, exist_ok=True)
        (model_root / "config.json").write_bytes(model_bytes)
        return str(model_root)

    huggingface_hub.snapshot_download = snapshot_download
    torch = types.ModuleType("torch")
    torch.__version__ = "2.3.1"
    torch.version = types.SimpleNamespace(cuda=None)
    torch.cuda = types.SimpleNamespace(is_available=lambda: False)
    monkeypatch.setitem(sys.modules, "huggingface_hub", huggingface_hub)
    monkeypatch.setitem(sys.modules, "torch", torch)
    for imported in (
        "cosyvoice.cli.cosyvoice",
        "cosyvoice.cli",
        "cosyvoice",
        "matcha",
    ):
        monkeypatch.delitem(sys.modules, imported, raising=False)
    monkeypatch.setattr(sys, "path", sys.path.copy())

    monkeypatch.setattr(sys, "dont_write_bytecode", False)
    first = CosyVoiceBackend(public_root).prepare(private_root)
    monkeypatch.setattr(sys, "dont_write_bytecode", False)
    second = CosyVoiceBackend(public_root).prepare(private_root)

    assert first["source_revisions"] == second["source_revisions"]
    assert not list(source_root.rglob("*.pyc"))
    assert not list(matcha_root.rglob("*.pyc"))


def test_validate_only_does_not_prepare_or_render_backend(tmp_path: Path) -> None:
    root, requests = _private_root(tmp_path)
    backend = SyntheticBackend()

    summary = render_requests(
        root, requests, RenderOptions(smoke=True, validate_only=True), backend
    )

    assert summary.validated == 1
    assert backend.prepare_calls == 0
    assert backend.render_calls == 0
    assert not (root / "results" / "manifest.jsonl").exists()


def test_empty_output_workspace_can_start_a_manifest_chain(tmp_path: Path) -> None:
    root, requests = _private_root(tmp_path)
    backend = SyntheticBackend()

    summary = render_requests(root, requests, RenderOptions(smoke=True), backend)

    assert summary.rendered == 1
    assert backend.prepare_calls == 1
    assert len(_records(root)) == 1
    assert len(list((root / "results" / "raw" / "cosyvoice3").glob("*.wav"))) == 1


def test_prior_wav_without_a_manifest_fails_before_backend_preparation(
    tmp_path: Path,
) -> None:
    root, requests = _private_root(tmp_path)
    _write_wav(root / "results" / "raw" / "cosyvoice3" / "prior.wav")
    backend = SyntheticBackend()

    with pytest.raises(ManifestIntegrityError, match="manifest"):
        render_requests(root, requests, RenderOptions(smoke=True), backend)

    assert backend.prepare_calls == 0
    assert backend.render_calls == 0


@pytest.mark.parametrize("reset", ["deleted", "truncated"])
def test_reset_manifest_with_prior_output_fails_before_backend_preparation(
    tmp_path: Path, reset: str
) -> None:
    root, requests = _private_root(tmp_path)
    render_requests(root, requests, RenderOptions(smoke=True), SyntheticBackend())
    manifest = root / "results" / "manifest.jsonl"
    if reset == "deleted":
        manifest.unlink()
    else:
        manifest.write_text("", encoding="utf-8")
    backend = SyntheticBackend()

    with pytest.raises(ManifestIntegrityError, match="manifest"):
        render_requests(root, requests, RenderOptions(smoke=True), backend)

    assert backend.prepare_calls == 0
    assert backend.render_calls == 0


@pytest.mark.parametrize("damage", ["missing", "digest-mismatch"])
def test_success_manifest_output_must_exist_with_its_recorded_digest(
    tmp_path: Path, damage: str
) -> None:
    root, requests = _private_root(tmp_path)
    render_requests(root, requests, RenderOptions(smoke=True), SyntheticBackend())
    record = _records(root)[0]
    output = root / record["output_file"]
    if damage == "missing":
        output.unlink()
    else:
        output.write_bytes(output.read_bytes() + b"changed")
    backend = SyntheticBackend()

    with pytest.raises(ManifestIntegrityError, match="output"):
        render_requests(root, requests, RenderOptions(smoke=True), backend)

    assert backend.prepare_calls == 0
    assert backend.render_calls == 0


def test_unreferenced_prior_wav_fails_before_backend_preparation(
    tmp_path: Path,
) -> None:
    root, requests = _private_root(tmp_path)
    render_requests(root, requests, RenderOptions(smoke=True), SyntheticBackend())
    _write_wav(root / "results" / "raw" / "cosyvoice3" / "unreferenced.wav")
    backend = SyntheticBackend()

    with pytest.raises(ManifestIntegrityError, match="unreferenced"):
        render_requests(root, requests, RenderOptions(smoke=True), backend)

    assert backend.prepare_calls == 0
    assert backend.render_calls == 0


def test_validate_only_requires_the_profile_used_for_render_provenance(
    tmp_path: Path,
) -> None:
    root, requests = _private_root(tmp_path)
    (root / "upload" / "private-profile.json").unlink()

    with pytest.raises(FileNotFoundError, match="private profile"):
        render_requests(
            root,
            requests,
            RenderOptions(smoke=True, validate_only=True),
            SyntheticBackend(),
        )


def test_validate_only_rejects_a_full_batch_without_an_accepted_smoke(
    tmp_path: Path,
) -> None:
    root, requests = _private_root(tmp_path, count=2)

    with pytest.raises(ValueError, match="accept-smoke"):
        render_requests(
            root, requests, RenderOptions(validate_only=True), SyntheticBackend()
        )


def test_validate_only_rejects_a_negative_batch_timeout(tmp_path: Path) -> None:
    root, requests = _private_root(tmp_path)

    with pytest.raises(ValueError, match="max_batch_seconds"):
        render_requests(
            root,
            requests,
            RenderOptions(
                smoke=True, validate_only=True, max_batch_seconds=-0.001
            ),
            SyntheticBackend(),
        )


def test_smoke_validation_rejects_a_corrupt_existing_manifest(tmp_path: Path) -> None:
    root, requests = _private_root(tmp_path)
    chain = ManifestChain(root / "results" / "manifest.jsonl")
    chain.append({"request_id": "prior", "status": "success"})
    _tamper_jsonl_line(chain.path, line=1, field="status", value="failure")

    with pytest.raises(ManifestIntegrityError, match="line 1"):
        render_requests(
            root,
            requests,
            RenderOptions(smoke=True, validate_only=True),
            SyntheticBackend(),
        )


def test_smoke_render_rejects_manifest_corruption_before_inference(
    tmp_path: Path,
) -> None:
    root, requests = _private_root(tmp_path)
    chain = ManifestChain(root / "results" / "manifest.jsonl")
    chain.append({"request_id": "prior", "status": "success"})
    _tamper_jsonl_line(chain.path, line=1, field="status", value="failure")
    backend = SyntheticBackend()

    with pytest.raises(ManifestIntegrityError, match="line 1"):
        render_requests(root, requests, RenderOptions(smoke=True), backend)

    assert backend.prepare_calls == 0
    assert backend.render_calls == 0
    assert not list((root / "results").rglob("*.wav"))


def test_output_hash_failure_records_failure_without_publishing_audio(
    tmp_path: Path, monkeypatch
) -> None:
    root, requests = _private_root(tmp_path)
    from voice_replication_kit import rendering

    actual_sha256_file = rendering.sha256_file

    def fail_output_hash(path: Path) -> str:
        candidate = Path(path)
        if "results" in candidate.parts and candidate.suffix == ".wav":
            raise OSError("synthetic digest failure")
        return actual_sha256_file(candidate)

    monkeypatch.setattr(rendering, "sha256_file", fail_output_hash)

    summary = render_requests(
        root, requests, RenderOptions(smoke=True), SyntheticBackend()
    )

    assert summary.failed == 1
    assert _records(root)[0]["failure_code"] == "output-publication-error"
    assert not list((root / "results" / "raw").rglob("*.wav"))


def test_output_publish_failure_records_failure_and_removes_pending_audio(
    tmp_path: Path, monkeypatch
) -> None:
    root, requests = _private_root(tmp_path)

    def deny_publish(_source: Path, _destination: Path) -> None:
        raise PermissionError("synthetic publish denial")

    monkeypatch.setattr("voice_replication_kit.rendering.os.link", deny_publish)

    summary = render_requests(
        root, requests, RenderOptions(smoke=True), SyntheticBackend()
    )

    assert summary.failed == 1
    assert _records(root)[0]["failure_code"] == "output-publication-error"
    assert not list((root / "results" / "raw").rglob("*.wav"))


def test_success_append_failure_removes_published_and_pending_audio(
    tmp_path: Path, monkeypatch
) -> None:
    root, requests = _private_root(tmp_path)

    def reject_append(_self: ManifestChain, _record: dict) -> dict:
        raise OSError("synthetic manifest write failure")

    monkeypatch.setattr(ManifestChain, "append", reject_append)

    with pytest.raises(OSError, match="manifest write failure"):
        render_requests(root, requests, RenderOptions(smoke=True), SyntheticBackend())

    assert not list((root / "results" / "raw").rglob("*.wav"))


@pytest.mark.parametrize(
    "aliased_directory",
    [Path("results"), Path("runtime"), Path("runtime/models")],
)
def test_validate_only_rejects_private_write_directory_aliases(
    tmp_path: Path, aliased_directory: Path
) -> None:
    root, requests = _private_root(tmp_path)
    outside = tmp_path / "outside" / "target"
    outside.mkdir(parents=True)
    alias = root / aliased_directory
    _make_directory_alias(outside, alias)

    try:
        with pytest.raises(ValueError, match="private root"):
            render_requests(
                root,
                requests,
                RenderOptions(smoke=True, validate_only=True),
                SyntheticBackend(),
            )
    finally:
        _remove_directory_alias(alias)


def test_validate_only_rejects_reference_directory_alias_outside_private_root(
    tmp_path: Path,
) -> None:
    root, requests = _private_root(tmp_path)
    original_reference = root / "upload" / "refs" / "synthetic-reference.wav"
    original_reference.unlink()
    original_reference.parent.rmdir()
    outside_refs = tmp_path / "outside-refs"
    outside_refs.mkdir()
    (outside_refs / "synthetic-reference.wav").write_bytes(REFERENCE_BYTES)
    alias = root / "upload" / "refs"
    _make_directory_alias(outside_refs, alias)

    try:
        with pytest.raises(ValueError, match="private root"):
            render_requests(
                root,
                requests,
                RenderOptions(smoke=True, validate_only=True),
                SyntheticBackend(),
            )
    finally:
        _remove_directory_alias(alias)


def test_model_is_prepared_once_for_a_non_validation_batch(tmp_path: Path) -> None:
    root, requests = _private_root(tmp_path, count=2)
    backend = SyntheticBackend()
    smoke_id = _request(1)["request_id"]
    render_requests(root, requests, RenderOptions(smoke=True), SyntheticBackend())

    summary = render_requests(
        root,
        requests,
        RenderOptions(accept_smoke=smoke_id),
        backend,
    )

    assert summary.rendered == 2
    assert backend.prepare_calls == 1
    assert backend.render_calls == 2


def test_smoke_acceptance_binds_complete_render_context(tmp_path: Path) -> None:
    root, requests = _private_root(tmp_path, count=2)
    smoke_id = _request(1)["request_id"]
    render_requests(root, requests, RenderOptions(smoke=True), SyntheticBackend())

    summary = render_requests(
        root,
        requests,
        RenderOptions(accept_smoke=smoke_id),
        SyntheticBackend(),
    )

    assert summary.rendered == 2
    smoke_record = _records(root)[0]
    assert len(smoke_record["render_context_sha256"]) == 64


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("device", "Different synthetic GPU"),
        ("precision", "fp32"),
        ("model_revision", "f" * 40),
        ("model_manifest_sha256", "a" * 64),
        ("source_revisions", {"cosyvoice": "9" * 40, "matcha_tts": "1" * 40}),
        ("runtime_lock_sha256", "b" * 64),
        ("runtime_provenance_sha256", "c" * 64),
    ],
)
def test_full_batch_rejects_smoke_from_different_runtime_context(
    tmp_path: Path, field: str, replacement: object
) -> None:
    root, requests = _private_root(tmp_path, count=2)
    smoke_id = _request(1)["request_id"]
    render_requests(root, requests, RenderOptions(smoke=True), SyntheticBackend())

    with pytest.raises(ValueError, match="render context"):
        render_requests(
            root,
            requests,
            RenderOptions(accept_smoke=smoke_id),
            SyntheticBackend(provenance={field: replacement}),
        )


def test_full_batch_rejects_smoke_after_profile_changes(tmp_path: Path) -> None:
    root, requests = _private_root(tmp_path, count=2)
    smoke_id = _request(1)["request_id"]
    render_requests(root, requests, RenderOptions(smoke=True), SyntheticBackend())
    (root / "upload" / "private-profile.json").write_text(
        json.dumps({"schema_version": 1, "fixture": "changed synthetic profile"}),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="render context"):
        render_requests(
            root,
            requests,
            RenderOptions(accept_smoke=smoke_id),
            SyntheticBackend(),
        )


def test_full_batch_rejects_an_accepted_smoke_id_without_matching_success(
    tmp_path: Path,
) -> None:
    root, requests = _private_root(tmp_path, count=2)
    ManifestChain(root / "results" / "manifest.jsonl").append(
        {
            "schema_version": 1,
            "status": "failure",
            "failure_code": "synthetic-fixture",
            "smoke": True,
            "request_id": _request(1)["request_id"],
            "request_pack_sha256": hashlib.sha256(requests.read_bytes()).hexdigest(),
        }
    )

    with pytest.raises(ValueError, match="accepted smoke request"):
        render_requests(
            root,
            requests,
            RenderOptions(accept_smoke=_request(2)["request_id"]),
            SyntheticBackend(),
        )


def test_max_batch_seconds_stops_only_between_inference_calls(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, requests = _private_root(tmp_path, count=2)
    smoke_id = _request(1)["request_id"]
    render_requests(root, requests, RenderOptions(smoke=True), SyntheticBackend())
    readings = iter([10.0, 10.0, 12.5, 12.5])
    monkeypatch.setattr("voice_replication_kit.rendering.time.monotonic", lambda: next(readings))
    backend = SyntheticBackend()

    summary = render_requests(
        root,
        requests,
        RenderOptions(accept_smoke=smoke_id, max_batch_seconds=2.0),
        backend,
    )

    assert summary.rendered == 1
    assert summary.stopped == 1
    assert summary.stop_reason == "max-batch-seconds"
    assert backend.render_calls == 1
