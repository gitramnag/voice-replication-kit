from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess

import pytest

from voice_replication_kit.runtime import (
    RuntimeVerificationError,
    load_runtime_pins,
    runtime_provenance,
    verify_model_snapshot,
    verify_runtime_lock,
    verify_source_checkout,
)


ROOT = Path(__file__).resolve().parents[1]

REVIEWED_DIRECT_REQUIREMENTS = {
    "conformer==0.3.2",
    'deepspeed==0.15.1 ; sys_platform == "linux"',
    "diffusers==0.29.0",
    "fastapi==0.115.6",
    "fastapi-cli==0.0.4",
    "gdown==5.1.0",
    "gradio==5.4.0",
    "grpcio==1.57.0",
    "grpcio-tools==1.57.0",
    "hydra-core==1.3.2",
    "hyperpyyaml==1.2.3",
    "inflect==7.3.1",
    "librosa==0.10.2",
    "lightning==2.2.4",
    "matplotlib==3.7.5",
    "modelscope==1.20.0",
    "networkx==3.1",
    "numpy==1.26.4",
    "omegaconf==2.3.0",
    "onnx==1.16.0",
    'onnxruntime-gpu==1.18.0 ; sys_platform == "linux"',
    'onnxruntime==1.18.0 ; sys_platform == "darwin" or sys_platform == "win32"',
    "openai-whisper==20231117",
    "protobuf==4.25.0",
    "pyarrow==18.1.0",
    "pydantic==2.7.0",
    "pyworld==0.3.4",
    "rich==13.7.1",
    "soundfile==0.12.1",
    "tensorboard==2.14.0",
    'tensorrt-cu12==10.13.3.9 ; sys_platform == "linux"',
    'tensorrt-cu12-bindings==10.13.3.9 ; sys_platform == "linux"',
    'tensorrt-cu12-libs==10.13.3.9 ; sys_platform == "linux"',
    "torch==2.3.1+cu121",
    "torchaudio==2.3.1+cu121",
    "transformers==4.51.3",
    "uvicorn==0.30.0",
    "wetext==0.0.4",
    "wget==3.2",
    "x-transformers==2.11.24",
}
REVIEWED_INDEX_DIRECTIVES = (
    "--extra-index-url https://download.pytorch.org/whl/cu121",
    "--extra-index-url https://aiinfra.pkgs.visualstudio.com/"
    "PublicPackages/_packaging/onnxruntime-cuda-12/pypi/simple/",
)


def runtime_lock_text(*requirement_lines: str) -> str:
    return "\n".join((*REVIEWED_INDEX_DIRECTIVES, *requirement_lines, ""))


def make_git_repository(tmp_path: Path) -> tuple[Path, str]:
    repository = tmp_path / "source"
    repository.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repository, check=True)
    subprocess.run(
        ["git", "config", "user.name", "Runtime Test"],
        cwd=repository,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "runtime-test" + "@" + "example.invalid"],
        cwd=repository,
        check=True,
    )
    (repository / "README.md").write_text("pinned\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=repository, check=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", "pinned source"],
        cwd=repository,
        check=True,
    )
    origin = repository.as_uri()
    subprocess.run(
        ["git", "remote", "add", "origin", origin], cwd=repository, check=True
    )
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    return repository, head


def git_blob_sha1(data: bytes) -> str:
    header = b"blob " + str(len(data)).encode("ascii") + b"\0"
    return hashlib.sha1(header + data).hexdigest()


def test_source_checkout_accepts_exact_origin_and_head(tmp_path: Path) -> None:
    repository, head = make_git_repository(tmp_path)

    verify_source_checkout(repository, repository.as_uri(), head)


def test_source_checkout_rejects_a_tracked_source_modification(tmp_path: Path) -> None:
    repository, head = make_git_repository(tmp_path)
    (repository / "README.md").write_text("changed\n", encoding="utf-8")

    with pytest.raises(RuntimeVerificationError, match="clean"):
        verify_source_checkout(repository, repository.as_uri(), head)


def test_source_checkout_rejects_an_untracked_python_file(tmp_path: Path) -> None:
    repository, head = make_git_repository(tmp_path)
    (repository / "injected.py").write_text("raise SystemExit\n", encoding="utf-8")

    with pytest.raises(RuntimeVerificationError, match="clean"):
        verify_source_checkout(repository, repository.as_uri(), head)


def test_source_checkout_rejects_an_ignored_untracked_python_file(
    tmp_path: Path,
) -> None:
    repository, head = make_git_repository(tmp_path)
    (repository / ".gitignore").write_text("generated/\n", encoding="utf-8")
    subprocess.run(["git", "add", ".gitignore"], cwd=repository, check=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", "review ignore policy"],
        cwd=repository,
        check=True,
    )
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    injected = repository / "generated" / "injected.py"
    injected.parent.mkdir()
    injected.write_text("raise SystemExit\n", encoding="utf-8")

    with pytest.raises(RuntimeVerificationError, match="clean"):
        verify_source_checkout(repository, repository.as_uri(), head)


@pytest.mark.parametrize("suffix", [".pyc", ".pyo"])
def test_source_checkout_rejects_ignored_python_bytecode(
    tmp_path: Path, suffix: str
) -> None:
    repository, _head = make_git_repository(tmp_path)
    (repository / ".gitignore").write_text("generated/\n", encoding="utf-8")
    subprocess.run(["git", "add", ".gitignore"], cwd=repository, check=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", "review ignore policy"],
        cwd=repository,
        check=True,
    )
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repository, check=True,
        capture_output=True, text=True,
    ).stdout.strip()
    bytecode = repository / "generated" / "__pycache__" / f"injected{suffix}"
    bytecode.parent.mkdir(parents=True)
    bytecode.write_bytes(b"synthetic bytecode")

    with pytest.raises(RuntimeVerificationError, match="clean"):
        verify_source_checkout(repository, repository.as_uri(), head)


def test_source_checkout_allows_ignored_non_executable_cache(tmp_path: Path) -> None:
    repository, _head = make_git_repository(tmp_path)
    (repository / ".gitignore").write_text("generated/\n", encoding="utf-8")
    subprocess.run(["git", "add", ".gitignore"], cwd=repository, check=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", "review ignore policy"],
        cwd=repository,
        check=True,
    )
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repository, check=True,
        capture_output=True, text=True,
    ).stdout.strip()
    cache = repository / "generated" / "cache.json"
    cache.parent.mkdir()
    cache.write_text("{}\n", encoding="utf-8")

    verify_source_checkout(repository, repository.as_uri(), head)


@pytest.mark.parametrize("mutable_revision", ["main", "074ca6d", "A" * 40])
def test_source_checkout_rejects_nonimmutable_revision(
    tmp_path: Path, mutable_revision: str
) -> None:
    repository, _head = make_git_repository(tmp_path)

    with pytest.raises(RuntimeVerificationError, match="40 lowercase hex"):
        verify_source_checkout(repository, repository.as_uri(), mutable_revision)


def test_source_checkout_rejects_wrong_head(tmp_path: Path) -> None:
    repository, _head = make_git_repository(tmp_path)

    with pytest.raises(RuntimeVerificationError, match="HEAD"):
        verify_source_checkout(repository, repository.as_uri(), "0" * 40)


def test_source_checkout_rejects_unexpected_remote(tmp_path: Path) -> None:
    repository, head = make_git_repository(tmp_path)

    with pytest.raises(RuntimeVerificationError, match="origin"):
        verify_source_checkout(repository, "https://example.invalid/source.git", head)


def test_public_runtime_pins_are_immutable_https_revisions() -> None:
    pins = load_runtime_pins(ROOT / "configs" / "pins.json")

    assert pins["python"] == "3.10"
    assert pins["sources"] == {
        "cosyvoice": {
            "url": "https://github.com/QwenAudio/CosyVoice.git",
            "commit": "074ca6dc9e80a2f424f1f74b48bdd7d3fea531cc",
        },
        "matcha_tts": {
            "url": "https://github.com/shivammehta25/Matcha-TTS.git",
            "commit": "dd9105b34bf2be2230f4aa1e4769fb586a3c824e",
        },
    }
    assert pins["model"]["revision"] == (
        "29e01c4e8d000f4bcd70751be16fa94bf3d85a18"
    )


@pytest.mark.parametrize(
    "broken_source",
    [
        {"url": "http://github.com/owner/repository.git", "commit": "a" * 40},
        {"url": "https://github.com/owner/repository.git", "commit": "main"},
    ],
)
def test_runtime_pins_reject_mutable_or_non_https_sources(
    tmp_path: Path, broken_source: dict[str, str]
) -> None:
    pins = {
        "schema_version": 1,
        "python": "3.10",
        "sources": {"cosyvoice": broken_source},
        "model": {"repository": "owner/model", "revision": "b" * 40},
    }
    path = tmp_path / "pins.json"
    path.write_text(json.dumps(pins), encoding="utf-8")

    with pytest.raises(RuntimeVerificationError):
        load_runtime_pins(path)


def test_runtime_pins_reject_mutable_model_revision(tmp_path: Path) -> None:
    pins = {
        "schema_version": 1,
        "python": "3.10",
        "sources": {
            "cosyvoice": {
                "url": "https://github.com/owner/repository.git",
                "commit": "a" * 40,
            }
        },
        "model": {"repository": "owner/model", "revision": "main"},
    }
    path = tmp_path / "pins.json"
    path.write_text(json.dumps(pins), encoding="utf-8")

    with pytest.raises(RuntimeVerificationError, match="model revision"):
        load_runtime_pins(path)


def test_checked_runtime_lock_has_exact_hashed_requirements() -> None:
    requirements = verify_runtime_lock(ROOT / "configs" / "runtime-lock.txt")

    assert len(REVIEWED_DIRECT_REQUIREMENTS) == 40
    assert REVIEWED_DIRECT_REQUIREMENTS <= set(requirements)
    assert len(requirements) > 40


def test_runtime_lock_rejects_unpinned_requirement(tmp_path: Path) -> None:
    lock = tmp_path / "runtime-lock.txt"
    lock.write_text(
        runtime_lock_text("unsafe>=1.0 --hash=sha256:" + "0" * 64),
        encoding="utf-8",
    )

    with pytest.raises(RuntimeVerificationError, match="exactly pinned"):
        verify_runtime_lock(lock)


def test_runtime_lock_rejects_requirement_without_hash(tmp_path: Path) -> None:
    lock = tmp_path / "runtime-lock.txt"
    lock.write_text(runtime_lock_text("unsafe==1.0"), encoding="utf-8")

    with pytest.raises(RuntimeVerificationError, match="sha256 hash"):
        verify_runtime_lock(lock)


@pytest.mark.parametrize(
    "unsafe_line",
    [
        "--extra-index-url https://example.invalid/simple/",
        "--index-url https://example.invalid/simple/",
        "--no-index",
        "--trusted-host example.invalid",
        "--requirement other.txt",
        "-r other.txt",
        "--constraint constraints.txt",
        "-c constraints.txt",
        "--editable .",
        "-e .",
        "https://example.invalid/packages/runtime.whl",
        "runtime @ https://example.invalid/packages/runtime.whl",
    ],
)
def test_runtime_lock_rejects_unreviewed_directives_and_urls(
    tmp_path: Path, unsafe_line: str
) -> None:
    lock = tmp_path / "runtime-lock.txt"
    lock.write_text(
        runtime_lock_text(
            unsafe_line,
            "safe==1.0 --hash=sha256:" + "0" * 64,
        ),
        encoding="utf-8",
    )

    with pytest.raises(RuntimeVerificationError, match="unsupported.*directive"):
        verify_runtime_lock(lock)


@pytest.mark.parametrize("missing_index", REVIEWED_INDEX_DIRECTIVES)
def test_runtime_lock_requires_both_reviewed_indexes(
    tmp_path: Path, missing_index: str
) -> None:
    lock = tmp_path / "runtime-lock.txt"
    retained_indexes = [
        directive
        for directive in REVIEWED_INDEX_DIRECTIVES
        if directive != missing_index
    ]
    lock.write_text(
        "\n".join(
            (
                *retained_indexes,
                "safe==1.0 --hash=sha256:" + "0" * 64,
                "",
            )
        ),
        encoding="utf-8",
    )

    with pytest.raises(RuntimeVerificationError, match="exact reviewed indexes"):
        verify_runtime_lock(lock)


def test_model_snapshot_accepts_raw_and_git_blob_digests(tmp_path: Path) -> None:
    raw = b"raw model bytes"
    git_blob = b"small tracked file\n"
    (tmp_path / "weights.bin").write_bytes(raw)
    (tmp_path / "config.json").write_bytes(git_blob)
    manifest = {
        "files": [
            {
                "path": "weights.bin",
                "size": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
            },
            {
                "path": "config.json",
                "size": len(git_blob),
                "git_sha1": git_blob_sha1(git_blob),
            },
        ]
    }

    verify_model_snapshot(tmp_path, manifest)


def test_model_snapshot_rejects_missing_file(tmp_path: Path) -> None:
    manifest = {
        "files": [{"path": "config.json", "size": 2, "sha256": "0" * 64}]
    }

    with pytest.raises(RuntimeVerificationError, match="config.json"):
        verify_model_snapshot(tmp_path, manifest)


def test_model_snapshot_rejects_extra_file(tmp_path: Path) -> None:
    data = b"{}"
    (tmp_path / "config.json").write_bytes(data)
    (tmp_path / "unreviewed.bin").write_bytes(b"extra")
    manifest = {
        "files": [
            {
                "path": "config.json",
                "size": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
            }
        ]
    }

    with pytest.raises(RuntimeVerificationError, match="unreviewed.bin"):
        verify_model_snapshot(tmp_path, manifest)


def test_model_snapshot_rejects_size_mismatch(tmp_path: Path) -> None:
    data = b"wrong"
    (tmp_path / "config.json").write_bytes(data)
    manifest = {
        "files": [
            {
                "path": "config.json",
                "size": len(data) + 1,
                "sha256": hashlib.sha256(data).hexdigest(),
            }
        ]
    }

    with pytest.raises(RuntimeVerificationError, match="config.json"):
        verify_model_snapshot(tmp_path, manifest)


@pytest.mark.parametrize("digest_key", ["sha256", "git_sha1"])
def test_model_snapshot_rejects_digest_mismatch(
    tmp_path: Path, digest_key: str
) -> None:
    data = b"wrong"
    (tmp_path / "config.json").write_bytes(data)
    manifest = {
        "files": [
            {
                "path": "config.json",
                "size": len(data),
                digest_key: "0" * (64 if digest_key == "sha256" else 40),
            }
        ]
    }

    with pytest.raises(RuntimeVerificationError, match="config.json"):
        verify_model_snapshot(tmp_path, manifest)


@pytest.mark.parametrize("escaped", ["../outside.bin", "/absolute.bin"])
def test_model_snapshot_rejects_path_escaping_snapshot_root(
    tmp_path: Path, escaped: str
) -> None:
    manifest = {
        "files": [{"path": escaped, "size": 0, "sha256": hashlib.sha256().hexdigest()}]
    }

    with pytest.raises(RuntimeVerificationError, match="escapes"):
        verify_model_snapshot(tmp_path, manifest)


def test_runtime_provenance_reads_only_private_record(tmp_path: Path) -> None:
    private_root = tmp_path / "private"
    record = private_root / "runtime" / "provenance.json"
    record.parent.mkdir(parents=True)
    expected = {
        "schema_version": 1,
        "python": "3.10.19",
        "packages": {"torch": "2.3.1"},
    }
    record.write_text(json.dumps(expected), encoding="utf-8")

    assert runtime_provenance(private_root) == expected
