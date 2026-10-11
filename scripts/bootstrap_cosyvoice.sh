#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
pins_file="${repo_root}/configs/pins.json"
lock_file="${repo_root}/configs/runtime-lock.txt"
python_bin="${PYTHON_BIN:-python3.10}"
config_python="${CONFIG_PYTHON_BIN:-python3}"
private_root="${VOICE_KIT_PRIVATE_ROOT:-}"
dry_run=0

usage() {
  echo "Usage: bootstrap_cosyvoice.sh [--dry-run] --private-root PATH" >&2
}

while (($#)); do
  case "$1" in
    --dry-run)
      dry_run=1
      shift
      ;;
    --private-root)
      if (($# < 2)); then
        usage
        exit 2
      fi
      private_root="$2"
      shift 2
      ;;
    *)
      usage
      exit 2
      ;;
  esac
done

if [[ -z "${private_root}" ]]; then
  echo "Bootstrap requires --private-root or VOICE_KIT_PRIVATE_ROOT." >&2
  exit 2
fi
if command -v wslpath >/dev/null 2>&1 && [[ "${private_root}" =~ ^[A-Za-z]:\\ ]]; then
  private_root="$(wslpath -u "${private_root}")"
fi
private_root="$(realpath -m "${private_root}")"
case "${private_root}/" in
  "${repo_root}/"*)
    echo "Private root must be outside the repository checkout." >&2
    exit 2
    ;;
esac
runtime_root="$(realpath -m "${private_root}/runtime")"
case "${runtime_root}/" in
  "${repo_root}/"*)
    echo "Runtime root must be outside the repository checkout." >&2
    exit 2
    ;;
esac
case "${runtime_root}/" in
  "${private_root}/"*) ;;
  *)
    echo "Runtime root must remain beneath the private root." >&2
    exit 2
    ;;
esac

mapfile -t pin_values < <("${config_python}" - "${pins_file}" <<'PY'
import json
import pathlib
import re
import sys
from urllib.parse import urlsplit

pins = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
if pins.get("schema_version") != 1 or pins.get("python") != "3.10":
    raise SystemExit("pins require schema 1 and Python 3.10")
sources = pins.get("sources", {})
values = []
for name in ("cosyvoice", "matcha_tts"):
    source = sources.get(name, {})
    url = source.get("url", "")
    parsed = urlsplit(url)
    if parsed.scheme != "https" or not parsed.netloc or parsed.username:
        raise SystemExit(f"{name} source must use HTTPS")
    commit = source.get("commit", "")
    if re.fullmatch(r"[0-9a-f]{40}", commit) is None:
        raise SystemExit(f"{name} source commit must be full lowercase SHA-1")
    values.extend((url, commit))
model = pins.get("model", {})
model_revision = model.get("revision", "")
if re.fullmatch(r"[0-9a-f]{40}", model_revision) is None:
    raise SystemExit("model revision must be full lowercase SHA-1")
values.extend((model.get("repository", ""), model_revision))
print("\n".join(values))
PY
)

if ((${#pin_values[@]} != 6)); then
  echo "Could not read complete runtime pins." >&2
  exit 2
fi
cosyvoice_url="${pin_values[0]}"
cosyvoice_commit="${pin_values[1]}"
matcha_url="${pin_values[2]}"
matcha_commit="${pin_values[3]}"
model_repository="${pin_values[4]}"
model_revision="${pin_values[5]}"

source_dir="${runtime_root}/cosyvoice"
matcha_dir="${source_dir}/third_party/Matcha-TTS"
venv_dir="${runtime_root}/venv"
provenance_file="${runtime_root}/provenance.json"
build_constraints="${runtime_root}/build-constraints.txt"

run() {
  if ((dry_run)); then
    printf '%q ' "$@"
    printf '\n'
  else
    "$@"
  fi
}

git_environment=(
  env
  GIT_CONFIG_NOSYSTEM=1
  GIT_CONFIG_GLOBAL=/dev/null
  GIT_CONFIG_COUNT=1
  GIT_CONFIG_KEY_0=core.hooksPath
  GIT_CONFIG_VALUE_0=/dev/null
)

git_run() {
  run "${git_environment[@]}" git "$@"
}

git_text() {
  "${git_environment[@]}" git "$@"
}

verify_checkout() {
  local directory="$1"
  local expected_url="$2"
  local expected_commit="$3"
  if ((dry_run)); then
    git_run -C "${directory}" remote get-url origin
    git_run -C "${directory}" rev-parse HEAD
    return
  fi
  local actual_url actual_commit
  actual_url="$(git_text -C "${directory}" remote get-url origin)"
  actual_commit="$(git_text -C "${directory}" rev-parse HEAD)"
  if [[ "${actual_url}" != "${expected_url}" ]]; then
    echo "Source origin does not match reviewed pin: ${directory}" >&2
    exit 1
  fi
  if [[ "${actual_commit}" != "${expected_commit}" ]]; then
    echo "Source HEAD does not match reviewed pin: ${directory}" >&2
    exit 1
  fi
}

if ((!dry_run)); then
  mkdir -p "${runtime_root}"
fi
if [[ -L "${source_dir}" ]] \
  || [[ -e "${source_dir}" && ! -d "${source_dir}" ]] \
  || [[ -d "${source_dir}" && -n "$(find "${source_dir}" -mindepth 1 -maxdepth 1 -print -quit)" ]]; then
  echo "Refusing to reuse existing source checkout: ${source_dir}" >&2
  exit 1
fi
git_run clone --no-checkout --filter=blob:none "${cosyvoice_url}" "${source_dir}"
git_run -C "${source_dir}" fetch --depth=1 origin "${cosyvoice_commit}"
git_run -C "${source_dir}" checkout --detach "${cosyvoice_commit}"
git_run -C "${source_dir}" config submodule.third_party/Matcha-TTS.url "${matcha_url}"
git_run -C "${source_dir}" -c protocol.file.allow=never submodule update --init --depth=1 third_party/Matcha-TTS
git_run -C "${matcha_dir}" fetch --depth=1 origin "${matcha_commit}"
git_run -C "${matcha_dir}" checkout --detach "${matcha_commit}"
verify_checkout "${source_dir}" "${cosyvoice_url}" "${cosyvoice_commit}"
verify_checkout "${matcha_dir}" "${matcha_url}" "${matcha_commit}"

run "${python_bin}" -m venv "${venv_dir}"
venv_python="${venv_dir}/bin/python"
run "${venv_python}" -m pip install pip==25.2 setuptools==75.8.0 wheel==0.45.1
if ((dry_run)); then
  printf 'write pinned build constraints to %q\n' "${build_constraints}"
else
  "${config_python}" - "${build_constraints}" <<'PY'
import pathlib
import sys

pathlib.Path(sys.argv[1]).write_text(
    "setuptools==75.8.0\nwheel==0.45.1\n", encoding="utf-8"
)
PY
fi
run env "PIP_CONSTRAINT=${build_constraints}" "${venv_python}" -m pip install --require-hashes -r "${lock_file}"

if ((dry_run)); then
  printf '%q ' "${venv_python}" - "${provenance_file}" "${cosyvoice_commit}" "${matcha_commit}" "${model_repository}" "${model_revision}"
  printf '\n'
else
  "${venv_python}" - "${provenance_file}" "${cosyvoice_commit}" "${matcha_commit}" "${model_repository}" "${model_revision}" <<'PY'
import importlib.metadata
import json
import pathlib
import platform
import sys

path = pathlib.Path(sys.argv[1])
packages = {
    distribution.metadata["Name"]: distribution.version
    for distribution in importlib.metadata.distributions()
    if distribution.metadata["Name"]
}
record = {
    "schema_version": 1,
    "python": platform.python_version(),
    "platform": platform.platform(),
    "packages": dict(sorted(packages.items(), key=lambda item: item[0].casefold())),
    "sources": {"cosyvoice": sys.argv[2], "matcha_tts": sys.argv[3]},
    "model": {"repository": sys.argv[4], "revision": sys.argv[5]},
}
path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
fi

run "${venv_python}" -m pip install --no-deps --no-build-isolation -e "${repo_root}"
if ((!dry_run)); then
  echo "Verified CosyVoice sources and installed the pinned runtime under ${runtime_root}."
  echo "No model weights were downloaded by this bootstrap step."
fi
