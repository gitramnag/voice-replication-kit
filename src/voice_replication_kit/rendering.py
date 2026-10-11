"""Render validated private request packs and append tamper-evident outcomes."""
from __future__ import annotations

import builtins
import errno
import hashlib
import json
import os
import platform
import random
import shutil
import sys
import tempfile
import time
import wave
from collections.abc import Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Protocol

from voice_replication_kit.matrix import (
    load_requests,
    next_output_path,
    resolve_reference_path,
    sha256_file,
)
from voice_replication_kit.errors import (
    PrivateInputError as FileNotFoundError,
    UserValidationError as ValueError,
)
from voice_replication_kit.runtime import (
    load_runtime_pins,
    runtime_provenance,
    verify_model_snapshot,
    verify_source_checkout,
)


EXPECTED_SAMPLE_RATE = 24_000
_BuiltinValueError = builtins.ValueError


class ManifestIntegrityError(ValueError):
    """Raised when a manifest line or its link to the previous line is invalid."""


def canonical_record_bytes(record: Mapping[str, Any]) -> bytes:
    """Return the canonical bytes signed by a manifest record digest."""
    unsigned = {key: value for key, value in record.items() if key != "record_sha256"}
    return json.dumps(
        unsigned,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def _append_jsonl_fsync(path: Path, record: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(
        record, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    with path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(payload + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def _read_manifest(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError) as error:
        raise ManifestIntegrityError(f"cannot read manifest: {path}") from error
    for line_number, raw in enumerate(lines, 1):
        if not raw.strip():
            raise ManifestIntegrityError(f"manifest line {line_number} is empty")
        try:
            record = json.loads(raw)
        except json.JSONDecodeError as error:
            raise ManifestIntegrityError(
                f"manifest line {line_number} is not valid JSON"
            ) from error
        if not isinstance(record, dict):
            raise ManifestIntegrityError(
                f"manifest line {line_number} must be an object"
            )
        records.append(record)
    return records


def _verify_manifest_chain_unlocked(path: Path) -> None:
    previous: str | None = None
    for line_number, record in enumerate(_read_manifest(path), 1):
        if record.get("previous_record_sha256") != previous:
            raise ManifestIntegrityError(
                f"manifest line {line_number} has an invalid previous record digest"
            )
        actual = record.get("record_sha256")
        expected = hashlib.sha256(canonical_record_bytes(record)).hexdigest()
        if actual != expected:
            raise ManifestIntegrityError(
                f"manifest line {line_number} has an invalid record digest"
            )
        previous = expected


@contextmanager
def _manifest_lock(path: Path):
    lock_path = path.with_name(f".{path.name}.lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+b") as stream:
        stream.seek(0, os.SEEK_END)
        if stream.tell() == 0:
            stream.write(b"\0")
            stream.flush()
            os.fsync(stream.fileno())
        stream.seek(0)
        if os.name == "nt":
            import msvcrt

            while True:
                try:
                    msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                    break
                except OSError as error:
                    if error.errno not in {
                        errno.EACCES,
                        errno.EAGAIN,
                        errno.EDEADLK,
                    }:
                        raise
                    time.sleep(0.01)
            try:
                yield
            finally:
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def verify_manifest_chain(path: Path) -> None:
    """Verify every record digest and previous-record link in a JSONL manifest."""
    manifest = Path(path)
    with _manifest_lock(manifest):
        _verify_manifest_chain_unlocked(manifest)


def _manifest_output_path(
    private_root: Path,
    output_directory: Path,
    raw: object,
    line_number: int,
) -> Path:
    if not isinstance(raw, str) or not raw.strip():
        raise ManifestIntegrityError(
            f"manifest line {line_number} success record has no output file"
        )
    relative = PurePosixPath(raw)
    if relative.is_absolute() or ".." in relative.parts:
        raise ManifestIntegrityError(
            f"manifest line {line_number} output path escapes the private output directory"
        )
    output = (private_root / Path(*relative.parts)).resolve(strict=False)
    try:
        output.relative_to(output_directory)
    except _BuiltinValueError as error:
        raise ManifestIntegrityError(
            f"manifest line {line_number} output path escapes the private output directory"
        ) from error
    if output.suffix.casefold() != ".wav":
        raise ManifestIntegrityError(
            f"manifest line {line_number} output is not a WAV file"
        )
    return output


def _output_wavs(output_directory: Path) -> set[Path]:
    if not output_directory.exists():
        return set()
    if not output_directory.is_dir():
        raise ManifestIntegrityError("private output path is not a directory")
    outputs: set[Path] = set()
    try:
        candidates = output_directory.rglob("*")
        for candidate in candidates:
            if candidate.suffix.casefold() != ".wav":
                continue
            if candidate.is_symlink() or not candidate.is_file():
                raise ManifestIntegrityError("private WAV output is not a regular file")
            resolved = candidate.resolve(strict=True)
            try:
                resolved.relative_to(output_directory)
            except _BuiltinValueError as error:
                raise ManifestIntegrityError(
                    "private WAV output escapes the output directory"
                ) from error
            outputs.add(resolved)
    except OSError as error:
        raise ManifestIntegrityError("cannot inventory private WAV output") from error
    return outputs


def verify_manifest_state(
    manifest: Path, output_directory: Path, private_root: Path
) -> None:
    """Reconcile the append-only manifest with every prior private WAV."""
    manifest = Path(manifest)
    output_directory = Path(output_directory).resolve(strict=False)
    private_root = Path(private_root).resolve(strict=False)
    with _manifest_lock(manifest):
        _verify_manifest_chain_unlocked(manifest)
        records = _read_manifest(manifest)
        outputs = _output_wavs(output_directory)
        if not records:
            if outputs:
                raise ManifestIntegrityError(
                    "manifest is missing or empty while prior WAV output exists"
                )
            return

        referenced: set[Path] = set()
        for line_number, record in enumerate(records, 1):
            if record.get("status") != "success":
                continue
            output = _manifest_output_path(
                private_root,
                output_directory,
                record.get("output_file"),
                line_number,
            )
            if output in referenced:
                raise ManifestIntegrityError(
                    f"manifest line {line_number} reuses an earlier output file"
                )
            if output.is_symlink() or not output.is_file():
                raise ManifestIntegrityError(
                    f"manifest line {line_number} output file is missing"
                )
            expected = record.get("output_sha256")
            if (
                not isinstance(expected, str)
                or len(expected) != 64
                or any(character not in "0123456789abcdef" for character in expected)
            ):
                raise ManifestIntegrityError(
                    f"manifest line {line_number} output digest is invalid"
                )
            try:
                actual = sha256_file(output)
            except OSError as error:
                raise ManifestIntegrityError(
                    f"manifest line {line_number} output file cannot be read"
                ) from error
            if actual != expected:
                raise ManifestIntegrityError(
                    f"manifest line {line_number} output digest does not match"
                )
            referenced.add(output)

        unreferenced = outputs - referenced
        if unreferenced:
            raise ManifestIntegrityError("unreferenced prior WAV output exists")


class ManifestChain:
    """Append-only JSONL records linked by canonical SHA-256 digests."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    def last_digest(self) -> str | None:
        with _manifest_lock(self.path):
            _verify_manifest_chain_unlocked(self.path)
            records = _read_manifest(self.path)
            if not records:
                return None
            return str(records[-1]["record_sha256"])

    def append(self, record: Mapping[str, Any]) -> dict[str, Any]:
        with _manifest_lock(self.path):
            _verify_manifest_chain_unlocked(self.path)
            records = _read_manifest(self.path)
            previous = (
                None if not records else str(records[-1]["record_sha256"])
            )
            complete = dict(record, previous_record_sha256=previous)
            complete["record_sha256"] = hashlib.sha256(
                canonical_record_bytes(complete)
            ).hexdigest()
            _append_jsonl_fsync(self.path, complete)
            return complete


@dataclass(frozen=True)
class RenderOptions:
    """Selection and safety options for one request-pack render invocation."""

    smoke: bool = False
    accept_smoke: str | None = None
    validate_only: bool = False
    request_id: str | None = None
    max_batch_seconds: float | None = 8 * 60 * 60
    profile: Path | None = None


@dataclass(frozen=True)
class RenderSummary:
    """Counts from a validation or render run."""

    validated: int
    rendered: int = 0
    failed: int = 0
    stopped: int = 0
    stop_reason: str | None = None


class RenderBackend(Protocol):
    """Boundary that keeps accelerator and CosyVoice imports out of validation."""

    def prepare(self, private_root: Path) -> Mapping[str, Any]: ...

    def validate_requests(self, requests: Sequence[Mapping[str, Any]]) -> None: ...

    def render(
        self, request: Mapping[str, Any], reference: Path, output: Path
    ) -> None: ...


def _canonical_mapping_digest(value: Mapping[str, Any]) -> str:
    payload = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _request_digest(request: Mapping[str, Any]) -> str:
    return _canonical_mapping_digest(request)


def _contained_private_path(
    private_root: Path,
    path: Path,
    description: str,
    repository_root: Path | None = None,
) -> Path:
    root = private_root.resolve(strict=False)
    candidate = path.expanduser().resolve(strict=False)
    try:
        candidate.relative_to(root)
    except _BuiltinValueError as error:
        raise ValueError(f"{description} must resolve beneath the private root") from error
    if repository_root is not None:
        repository = repository_root.resolve(strict=False)
        try:
            candidate.relative_to(repository)
        except _BuiltinValueError:
            pass
        else:
            raise ValueError(f"{description} must resolve outside the Git checkout")
    return candidate


def _profile_digest(
    private_root: Path,
    options: RenderOptions,
    repository_root: Path | None,
) -> str:
    supplied = options.profile
    path = private_root / "upload" / "private-profile.json" if supplied is None else supplied
    profile = _contained_private_path(
        private_root, Path(path), "private profile", repository_root
    )
    if not profile.is_file():
        raise FileNotFoundError(f"private profile does not exist: {profile.name}")
    return sha256_file(profile)


def _validate_inputs(
    private_root: Path,
    request_pack: Path,
    options: RenderOptions,
    repository_root: Path | None,
) -> tuple[list[dict[str, Any]], dict[str, Path], str, str]:
    pack = _contained_private_path(
        private_root, request_pack, "request pack", repository_root
    )
    rows = load_requests(pack)
    references: dict[str, Path] = {}
    for row in rows:
        reference = resolve_reference_path(private_root, row)
        reference = _contained_private_path(
            private_root, reference, "private reference", repository_root
        )
        actual_digest = sha256_file(reference)
        if actual_digest != row["reference_sha256"]:
            raise ValueError(
                f"private reference hash changed for request {row['request_id']}"
            )
        references[str(row["request_id"])] = reference
    return (
        rows,
        references,
        sha256_file(pack),
        _profile_digest(private_root, options, repository_root),
    )


def _backend_repository_root(backend: RenderBackend) -> Path | None:
    raw = getattr(backend, "publication_root", None)
    if raw is None:
        raw = getattr(backend, "repository_root", None)
    return None if raw is None else Path(raw).resolve(strict=False)


def _validate_private_artifact_paths(
    private_root: Path, repository_root: Path | None
) -> tuple[Path, Path]:
    fixed_paths = (
        (private_root / "results", "private results directory"),
        (private_root / "results" / "raw" / "cosyvoice3", "private output directory"),
        (private_root / "results" / "manifest.jsonl", "private manifest"),
        (private_root / "results" / ".manifest.jsonl.lock", "private manifest lock"),
        (private_root / "runtime", "private runtime directory"),
        (private_root / "runtime" / "cosyvoice", "private source checkout"),
        (
            private_root / "runtime" / "cosyvoice" / "third_party" / "Matcha-TTS",
            "private Matcha-TTS checkout",
        ),
        (private_root / "runtime" / "models", "private model directory"),
        (
            private_root / "runtime" / "models" / "cosyvoice3",
            "private model snapshot",
        ),
        (private_root / "runtime" / "provenance.json", "private runtime provenance"),
    )
    resolved = {
        description: _contained_private_path(
            private_root, path, description, repository_root
        )
        for path, description in fixed_paths
    }
    return resolved["private manifest"], resolved["private output directory"]


def _select_rows(
    rows: Sequence[dict[str, Any]], options: RenderOptions
) -> list[dict[str, Any]]:
    selected = list(rows)
    if options.request_id is not None:
        selected = [row for row in selected if row["request_id"] == options.request_id]
        if not selected:
            raise ValueError(f"unknown request id: {options.request_id}")
    if options.smoke:
        selected = selected[:1]
    return selected


def _require_accepted_smoke(
    manifest: Path,
    accepted_request_id: str | None,
    request_pack_sha256: str,
    render_context_sha256: str | None = None,
) -> None:
    if not accepted_request_id:
        raise ValueError("a full batch requires --accept-smoke REQUEST_ID")
    verify_manifest_chain(manifest)
    matches = [
        record
        for record in _read_manifest(manifest)
        if record.get("status") == "success"
        and record.get("smoke") is True
        and record.get("request_id") == accepted_request_id
        and record.get("request_pack_sha256") == request_pack_sha256
    ]
    if not matches:
        raise ValueError("accepted smoke request does not match a successful smoke record")
    if render_context_sha256 is not None and not any(
        record.get("render_context_sha256") == render_context_sha256
        for record in matches
    ):
        raise ValueError("accepted smoke render context does not match this batch")


def _wav_sample_rate(path: Path) -> int:
    try:
        with wave.open(str(path), "rb") as stream:
            sample_rate = stream.getframerate()
            if stream.getnframes() < 1:
                raise ValueError("rendered WAV contains no audio frames")
    except (OSError, EOFError, wave.Error) as error:
        raise ValueError("rendered output is not a readable WAV") from error
    if sample_rate != EXPECTED_SAMPLE_RATE:
        raise ValueError(
            f"rendered WAV sample rate must be {EXPECTED_SAMPLE_RATE} Hz"
        )
    return sample_rate


def _pending_wav(
    private_root: Path, directory: Path, repository_root: Path | None
) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    directory = _contained_private_path(
        private_root, directory, "private output directory", repository_root
    )
    with tempfile.NamedTemporaryFile(
        dir=directory,
        prefix=".render-",
        suffix=".wav",
        delete=False,
    ) as stream:
        path = Path(stream.name)
    path.unlink()
    return path


def _publish_wav_immutable(private_root: Path, request_id: str, pending: Path) -> Path:
    while True:
        destination = next_output_path(private_root, request_id)
        try:
            os.link(pending, destination)
        except FileExistsError:
            continue
        return destination


def _provenance_fields(raw: Mapping[str, Any]) -> dict[str, Any]:
    required = (
        "python_version",
        "torch_version",
        "cuda_version",
        "device",
        "precision",
        "source_revisions",
        "model_repository",
        "model_revision",
        "model_manifest_sha256",
        "runtime_lock_sha256",
        "runtime_provenance_sha256",
    )
    missing = [field for field in required if field not in raw]
    if missing:
        raise ValueError(f"render backend provenance is missing fields: {missing}")
    sources = raw["source_revisions"]
    if not isinstance(sources, Mapping):
        raise ValueError("render backend source_revisions must be an object")
    model_digest = str(raw["model_manifest_sha256"])
    runtime_identity = {
        "lock_sha256": str(raw["runtime_lock_sha256"]),
        "provenance_sha256": str(raw["runtime_provenance_sha256"]),
    }
    return {
        "python": str(raw["python_version"]),
        "python_version": str(raw["python_version"]),
        "torch": str(raw["torch_version"]),
        "torch_version": str(raw["torch_version"]),
        "cuda": str(raw["cuda_version"]),
        "cuda_version": str(raw["cuda_version"]),
        "device": str(raw["device"]),
        "precision": str(raw["precision"]),
        "source_revisions": dict(sources),
        "source_sha256": _canonical_mapping_digest(dict(sources)),
        "model_repository": str(raw["model_repository"]),
        "model_revision": str(raw["model_revision"]),
        "model_manifest_sha256": model_digest,
        "model_sha256": model_digest,
        "runtime_lock_sha256": runtime_identity["lock_sha256"],
        "runtime_provenance_sha256": runtime_identity["provenance_sha256"],
        "runtime_sha256": _canonical_mapping_digest(runtime_identity),
    }


def _render_context_digest(
    request_pack_sha256: str,
    profile_sha256: str,
    provenance: Mapping[str, Any],
) -> str:
    return _canonical_mapping_digest(
        {
            "request_pack_sha256": request_pack_sha256,
            "profile_sha256": profile_sha256,
            "device": provenance["device"],
            "precision": provenance["precision"],
            "source_sha256": provenance["source_sha256"],
            "model_repository": provenance["model_repository"],
            "model_revision": provenance["model_revision"],
            "model_sha256": provenance["model_sha256"],
            "runtime_sha256": provenance["runtime_sha256"],
        }
    )


def _base_record(
    request: Mapping[str, Any],
    options: RenderOptions,
    request_pack_sha256: str,
    profile_sha256: str,
    provenance: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "request_id": request["request_id"],
        "prompt_id": request["prompt_id"],
        "style": request["style"],
        "seed": request["seed"],
        "smoke": options.smoke,
        "request_sha256": _request_digest(request),
        "request_pack_sha256": request_pack_sha256,
        "profile_sha256": profile_sha256,
        "reference_sha256": request["reference_sha256"],
        "render_context_sha256": _render_context_digest(
            request_pack_sha256, profile_sha256, provenance
        ),
        **provenance,
    }


def render_requests(
    private_root: Path,
    request_pack: Path,
    options: RenderOptions,
    backend: RenderBackend,
) -> RenderSummary:
    """Validate and render a private pack while preserving every prior outcome.

    ``max_batch_seconds`` is observed only between backend calls. It cannot and
    does not attempt to interrupt an inference call already in progress.
    """
    root = Path(private_root).resolve(strict=False)
    repository_root = _backend_repository_root(backend)
    manifest, output_directory = _validate_private_artifact_paths(
        root, repository_root
    )
    verify_manifest_state(manifest, output_directory, root)
    rows, references, pack_digest, profile_digest = _validate_inputs(
        root, Path(request_pack), options, repository_root
    )
    selected = _select_rows(rows, options)
    validate_requests = getattr(backend, "validate_requests", None)
    if validate_requests is not None:
        validate_requests(selected)
    chain = ManifestChain(manifest)
    verify_manifest_chain(manifest)
    if not options.smoke and options.validate_only:
        _require_accepted_smoke(manifest, options.accept_smoke, pack_digest)

    if options.max_batch_seconds is not None and options.max_batch_seconds < 0:
        raise ValueError("max_batch_seconds must be non-negative")
    if options.validate_only:
        return RenderSummary(validated=len(selected))
    provenance = _provenance_fields(backend.prepare(root))
    if not options.smoke:
        _require_accepted_smoke(
            manifest,
            options.accept_smoke,
            pack_digest,
            _render_context_digest(pack_digest, profile_digest, provenance),
        )
    batch_started = time.monotonic()
    rendered = 0
    failed = 0
    stopped = 0
    for index, request in enumerate(selected):
        if index and options.max_batch_seconds is not None:
            if time.monotonic() - batch_started >= options.max_batch_seconds:
                stopped = len(selected) - index
                break
        pending = _pending_wav(root, output_directory, repository_root)
        started = time.monotonic()
        record = _base_record(
            request, options, pack_digest, profile_digest, provenance
        )
        try:
            backend.render(request, references[str(request["request_id"])], pending)
        except Exception:
            pending.unlink(missing_ok=True)
            record.update(
                {
                    "status": "failure",
                    "failure_code": "inference-error",
                    "elapsed_seconds": round(time.monotonic() - started, 3),
                }
            )
            chain.append(record)
            failed += 1
            continue
        try:
            sample_rate = _wav_sample_rate(pending)
        except (OSError, _BuiltinValueError):
            pending.unlink(missing_ok=True)
            record.update(
                {
                    "status": "failure",
                    "failure_code": "output-validation-error",
                    "elapsed_seconds": round(time.monotonic() - started, 3),
                }
            )
            chain.append(record)
            failed += 1
            continue
        try:
            output_digest = sha256_file(pending)
            output = _publish_wav_immutable(
                root, str(request["request_id"]), pending
            )
        except (OSError, _BuiltinValueError):
            pending.unlink(missing_ok=True)
            record.update(
                {
                    "status": "failure",
                    "failure_code": "output-publication-error",
                    "elapsed_seconds": round(time.monotonic() - started, 3),
                }
            )
            chain.append(record)
            failed += 1
            continue
        record.update(
            {
                "status": "success",
                "output_file": output.relative_to(root).as_posix(),
                "output_sha256": output_digest,
                "sample_rate": sample_rate,
                "elapsed_seconds": round(time.monotonic() - started, 3),
            }
        )
        pending.unlink()
        try:
            chain.append(record)
        except Exception:
            output.unlink(missing_ok=True)
            raise
        rendered += 1
    return RenderSummary(
        validated=len(selected),
        rendered=rendered,
        failed=failed,
        stopped=stopped,
        stop_reason="max-batch-seconds" if stopped else None,
    )


class CosyVoiceBackend:
    """Concrete pinned CosyVoice backend; heavyweight imports stay in methods."""

    def __init__(
        self,
        repository_root: Path,
        precision: str = "fp16",
        publication_root: Path | None = None,
    ) -> None:
        if precision not in {"fp16", "fp32"}:
            raise ValueError("precision must be fp16 or fp32")
        self.repository_root = Path(repository_root).resolve()
        self.publication_root = (
            self.repository_root
            if publication_root is None
            else Path(publication_root).resolve()
        )
        self.precision = precision
        self._model: Any = None

    def _set_seed(self, seed: int) -> None:
        random.seed(seed)
        try:
            import numpy as np

            np.random.seed(seed)
        except ImportError:
            pass
        import torch

        torch.manual_seed(seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(seed)

    def validate_requests(self, requests: Sequence[Mapping[str, Any]]) -> None:
        """Check public pins without importing or acquiring the model runtime."""
        pins = load_runtime_pins(self.repository_root / "configs" / "pins.json")
        expected = pins["model"]["revision"]
        for request in requests:
            if request["model_revision"] != expected:
                raise ValueError(
                    f"request {request['request_id']} does not use the reviewed model revision"
                )

    def prepare(self, private_root: Path) -> Mapping[str, Any]:
        if self._model is not None:
            raise RuntimeError("CosyVoice backend was prepared more than once")
        pins = load_runtime_pins(self.repository_root / "configs" / "pins.json")
        source_root = _contained_private_path(
            private_root,
            private_root / "runtime" / "cosyvoice",
            "private source checkout",
            self.publication_root,
        )
        verify_source_checkout(
            source_root,
            str(pins["sources"]["cosyvoice"]["url"]),
            str(pins["sources"]["cosyvoice"]["commit"]),
        )
        matcha_root = _contained_private_path(
            private_root,
            source_root / "third_party" / "Matcha-TTS",
            "private Matcha-TTS checkout",
            self.publication_root,
        )
        verify_source_checkout(
            matcha_root,
            str(pins["sources"]["matcha_tts"]["url"]),
            str(pins["sources"]["matcha_tts"]["commit"]),
        )

        sys.dont_write_bytecode = True
        for path in (source_root, matcha_root):
            if str(path) not in sys.path:
                sys.path.insert(0, str(path))
        from huggingface_hub import snapshot_download

        model_pin = pins["model"]
        model_root = _contained_private_path(
            private_root,
            private_root / "runtime" / "models" / "cosyvoice3",
            "private model snapshot",
            self.publication_root,
        )
        cache_root = _contained_private_path(
            private_root,
            private_root / "runtime" / "cache" / "huggingface",
            "private Hugging Face cache",
            self.publication_root,
        )
        _download_model_snapshot(
            snapshot_download,
            repository=str(model_pin["repository"]),
            revision=str(model_pin["revision"]),
            model_root=model_root,
            cache_root=cache_root,
        )
        model_root = _contained_private_path(
            private_root,
            model_root,
            "private model snapshot",
            self.publication_root,
        )
        model_manifest_path = self.repository_root / "configs" / "model-manifest.json"
        model_manifest = json.loads(model_manifest_path.read_text(encoding="utf-8"))
        verify_model_snapshot(model_root, model_manifest)

        import torch
        from cosyvoice.cli.cosyvoice import CosyVoice3

        self._model = CosyVoice3(str(model_root), fp16=self.precision == "fp16")
        _contained_private_path(
            private_root,
            private_root / "runtime" / "provenance.json",
            "private runtime provenance",
            self.publication_root,
        )
        runtime = runtime_provenance(private_root)
        provenance_path = private_root / "runtime" / "provenance.json"
        runtime_lock_path = self.repository_root / "configs" / "runtime-lock.txt"
        packages = runtime.get("packages", {})
        torch_version = next(
            (
                str(value)
                for key, value in packages.items()
                if str(key).casefold() == "torch"
            ),
            str(torch.__version__),
        )
        cuda_version = str(torch.version.cuda or "unavailable")
        device = (
            str(torch.cuda.get_device_name(torch.cuda.current_device()))
            if torch.cuda.is_available()
            else "cpu"
        )
        return {
            "python_version": str(runtime.get("python", platform.python_version())),
            "torch_version": torch_version,
            "cuda_version": cuda_version,
            "device": device,
            "precision": self.precision,
            "source_revisions": {
                name: source["commit"] for name, source in pins["sources"].items()
            },
            "model_repository": model_pin["repository"],
            "model_revision": model_pin["revision"],
            "model_manifest_sha256": sha256_file(model_manifest_path),
            "runtime_lock_sha256": sha256_file(runtime_lock_path),
            "runtime_provenance_sha256": sha256_file(provenance_path),
        }

    def render(
        self, request: Mapping[str, Any], reference: Path, output: Path
    ) -> None:
        if self._model is None:
            raise RuntimeError("CosyVoice backend is not prepared")
        import soundfile as sf
        import torch

        self._set_seed(int(request["seed"]))
        reference_text = str(request["reference_text"])
        if "<|endofprompt|>" not in reference_text:
            reference_text = "You are a helpful assistant.<|endofprompt|>" + reference_text
        chunks = self._model.inference_zero_shot(
            str(request["text"]),
            reference_text,
            str(reference),
            stream=False,
        )
        tensors = [part["tts_speech"].detach().cpu() for part in chunks]
        if not tensors:
            raise RuntimeError("CosyVoice returned no audio")
        audio = torch.cat(tensors, dim=-1).float().numpy().squeeze()
        sf.write(output, audio, int(getattr(self._model, "sample_rate", 24_000)))


def _download_model_snapshot(
    snapshot_download: Any,
    *,
    repository: str,
    revision: str,
    model_root: Path,
    cache_root: Path,
) -> None:
    """Download one pinned snapshot without retaining local-dir metadata."""
    snapshot_download(
        repo_id=repository,
        revision=revision,
        local_dir=model_root,
        cache_dir=cache_root,
    )
    metadata = model_root / ".cache" / "huggingface"
    if not metadata.exists():
        return
    if not metadata.is_dir() or metadata.is_symlink():
        raise ValueError("Hugging Face metadata is not a local directory")
    root = model_root.resolve(strict=True)
    for path in (model_root / ".cache", metadata, *metadata.rglob("*")):
        if path.is_symlink():
            raise ValueError("Hugging Face metadata contains a filesystem alias")
        try:
            path.resolve(strict=True).relative_to(root)
        except (OSError, _BuiltinValueError) as error:
            raise ValueError("Hugging Face metadata escapes the model snapshot") from error
    shutil.rmtree(metadata)
    local_cache = model_root / ".cache"
    if not any(local_cache.iterdir()):
        local_cache.rmdir()
