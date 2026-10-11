from __future__ import annotations

import os
from pathlib import Path
import subprocess

from voice_replication_kit.private_root import initialise_private_root


ROOT = Path(__file__).resolve().parents[1]


def run_bootstrap(
    *arguments: str, environment: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    if environment:
        env.update(environment)
        inherited = env.get("WSLENV", "")
        names = ":".join(environment)
        env["WSLENV"] = ":".join(value for value in (inherited, names) if value)
    return subprocess.run(
        ["bash", "scripts/bootstrap_cosyvoice.sh", *arguments],
        cwd=ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )


def bash_path(path: Path, *, resolve: bool = True) -> str:
    resolved = (path.resolve() if resolve else path.absolute()).as_posix()
    if os.name != "nt":
        return resolved
    drive, remainder = resolved.split(":", 1)
    return f"/mnt/{drive.casefold()}{remainder}"


def make_bash_directory_symlink(target: Path, link: Path) -> None:
    env = os.environ.copy()
    env.update(
        {
            "BOOTSTRAP_SYMLINK_TARGET": bash_path(target),
            "BOOTSTRAP_SYMLINK_LINK": bash_path(link),
        }
    )
    inherited = env.get("WSLENV", "")
    env["WSLENV"] = ":".join(
        value
        for value in (
            inherited,
            "BOOTSTRAP_SYMLINK_TARGET:BOOTSTRAP_SYMLINK_LINK",
        )
        if value
    )
    subprocess.run(
        ["bash", "-c", 'ln -s -- "$BOOTSTRAP_SYMLINK_TARGET" "$BOOTSTRAP_SYMLINK_LINK"'],
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )


def remove_bash_symlink(link: Path) -> None:
    env = os.environ.copy()
    env["BOOTSTRAP_SYMLINK_LINK"] = bash_path(link, resolve=False)
    inherited = env.get("WSLENV", "")
    env["WSLENV"] = ":".join(
        value for value in (inherited, "BOOTSTRAP_SYMLINK_LINK") if value
    )
    subprocess.run(
        ["bash", "-c", 'rm -f -- "$BOOTSTRAP_SYMLINK_LINK"'],
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )


def test_bootstrap_requires_explicit_external_private_root() -> None:
    result = run_bootstrap("--dry-run", environment={"VOICE_KIT_PRIVATE_ROOT": ""})

    assert result.returncode != 0
    assert "--private-root or VOICE_KIT_PRIVATE_ROOT" in result.stderr


def test_bootstrap_rejects_runtime_symlink_into_checkout(tmp_path: Path) -> None:
    private_root = tmp_path / "private"
    private_root.mkdir()
    runtime_link = private_root / "runtime"
    make_bash_directory_symlink(ROOT, runtime_link)

    try:
        result = run_bootstrap("--dry-run", "--private-root", bash_path(private_root))
    finally:
        remove_bash_symlink(runtime_link)

    assert result.returncode != 0
    assert "outside the repository checkout" in result.stderr


def test_remove_bash_symlink_unlinks_link_without_resolving_target(
    tmp_path: Path,
) -> None:
    target = tmp_path / "target"
    target.mkdir()
    link = tmp_path / "runtime"
    make_bash_directory_symlink(target, link)

    remove_bash_symlink(link)

    assert target.is_dir()
    assert not link.exists()


def test_bootstrap_refuses_existing_source_checkout(tmp_path: Path) -> None:
    private_root = tmp_path / "private"
    (private_root / "runtime" / "cosyvoice" / ".git").mkdir(parents=True)

    result = run_bootstrap("--dry-run", "--private-root", bash_path(private_root))

    assert result.returncode != 0
    assert "Refusing to reuse existing source checkout" in result.stderr


def test_bootstrap_accepts_empty_source_directory_created_by_init_private(
    tmp_path: Path,
) -> None:
    private_root = tmp_path / "private"
    initialise_private_root(ROOT, private_root)

    result = run_bootstrap("--dry-run", "--private-root", bash_path(private_root))

    assert result.returncode == 0, result.stderr


def test_bootstrap_dry_run_isolates_git_before_checkout(tmp_path: Path) -> None:
    private_root = tmp_path / "private"

    result = run_bootstrap("--dry-run", "--private-root", bash_path(private_root))

    assert result.returncode == 0, result.stderr
    git_commands = [
        line for line in result.stdout.splitlines() if " git " in f" {line} "
    ]
    assert git_commands
    assert all("GIT_CONFIG_NOSYSTEM=1" in line for line in git_commands)
    assert all("GIT_CONFIG_GLOBAL=/dev/null" in line for line in git_commands)
    assert all("GIT_CONFIG_KEY_0=core.hooksPath" in line for line in git_commands)
    assert all("GIT_CONFIG_VALUE_0=/dev/null" in line for line in git_commands)
    clone_command = next(line for line in git_commands if " clone " in f" {line} ")
    assert "--no-checkout" in clone_command
    assert any(" submodule update " in f" {line} " for line in git_commands)


def test_bootstrap_dry_run_uses_python_310_and_reviewed_lock(tmp_path: Path) -> None:
    private_root = tmp_path.parent / f"{tmp_path.name}-private"

    result = run_bootstrap("--dry-run", "--private-root", bash_path(private_root))

    assert result.returncode == 0, result.stderr
    commands = result.stdout
    assert "python3.10 -m venv" in commands
    assert "pip==25.2 setuptools==75.8.0 wheel==0.45.1" in commands
    assert "--require-hashes" in commands
    assert "configs/runtime-lock.txt" in commands
    assert "PIP_CONSTRAINT=" in commands
    assert "runtime/build-constraints.txt" in commands
    assert "runtime/provenance.json" in commands


def test_bootstrap_dry_run_checks_full_source_heads_without_model_download(
    tmp_path: Path,
) -> None:
    private_root = tmp_path.parent / f"{tmp_path.name}-private"

    result = run_bootstrap("--dry-run", "--private-root", bash_path(private_root))

    assert result.returncode == 0, result.stderr
    commands = result.stdout
    assert "https://github.com/QwenAudio/CosyVoice.git" in commands
    assert "074ca6dc9e80a2f424f1f74b48bdd7d3fea531cc" in commands
    assert "https://github.com/shivammehta25/Matcha-TTS.git" in commands
    assert "dd9105b34bf2be2230f4aa1e4769fb586a3c824e" in commands
    assert commands.count("rev-parse HEAD") == 2
    assert "huggingface" not in commands.casefold()
    assert "snapshot_download" not in commands
    assert "modelscope" not in commands.casefold()


def test_bootstrap_accepts_private_root_from_environment(tmp_path: Path) -> None:
    private_root = tmp_path.parent / f"{tmp_path.name}-private"

    result = run_bootstrap(
        "--dry-run", environment={"VOICE_KIT_PRIVATE_ROOT": bash_path(private_root)}
    )

    assert result.returncode == 0, result.stderr
    assert bash_path(private_root) in result.stdout


def test_bootstrap_dry_run_accepts_a_documented_python_override(
    tmp_path: Path,
) -> None:
    private_root = tmp_path.parent / f"{tmp_path.name}-private"

    result = run_bootstrap(
        "--dry-run",
        "--private-root",
        bash_path(private_root),
        environment={"PYTHON_BIN": "python3.10-reviewed"},
    )

    assert result.returncode == 0, result.stderr
    assert "python3.10-reviewed -m venv" in result.stdout
