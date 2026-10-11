#!/usr/bin/env bash
set -euo pipefail

source_root="${1:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)}"
temporary_root="${TMPDIR:-/tmp}"
audit_root="$(mktemp -d "${temporary_root%/}/voice-kit-clean-room.XXXXXXXX")"
clone_root="$audit_root/repository"
private_terms_args=()
if [[ -n "${VOICE_KIT_PRIVATE_TERMS_FILE:-}" ]]; then
  private_terms_args=(--private-terms-file "$VOICE_KIT_PRIVATE_TERMS_FILE")
fi

cleanup() {
  case "$audit_root" in
    "${temporary_root%/}"/voice-kit-clean-room.*) rm -rf -- "$audit_root" ;;
    *) printf 'Refusing to remove unexpected clean-room path: %s\n' "$audit_root" >&2 ;;
  esac
}
trap cleanup EXIT

printf '+ git clone --no-local %s %s\n' "$source_root" "$clone_root"
git clone --no-local --quiet -- "$source_root" "$clone_root"
cd "$clone_root"

if command -v python >/dev/null 2>&1; then
  printf '%s\n' '+ python -m venv .venv'
  python -m venv .venv
else
  printf '%s\n' '+ python3 -m venv .venv'
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate

printf '%s\n' '+ python -m pip install --require-hashes -r configs/public-tools-lock.txt'
python -m pip install --require-hashes -r configs/public-tools-lock.txt

printf '%s\n' '+ python -m pip install --no-build-isolation --no-deps -e .'
python -m pip install --no-build-isolation --no-deps -e .

printf '%s\n' '+ python -m pytest'
python -m pytest

printf '%s\n' '+ python -m voice_replication_kit.corpus'
python -m voice_replication_kit.corpus --source corpus/recording-script.json --output-dir corpus

printf '%s\n' '+ python tools/build_scorecard.py --check'
python tools/build_scorecard.py --check evaluation/voice-evaluation-scorecard.xlsx

printf '%s\n' '+ python tools/build_diagrams.py --check'
python tools/build_diagrams.py --check

printf '%s\n' '+ python scripts/check_links.py'
python scripts/check_links.py --root .

printf '%s\n' '+ voice-kit audit --mode tree'
voice-kit audit --mode tree --root . "${private_terms_args[@]}"

printf '%s\n' '+ voice-kit audit --mode history'
voice-kit audit --mode history --root . "${private_terms_args[@]}"

printf '%s\n' '+ git status --porcelain'
status="$(git status --porcelain)"
if [[ -n "$status" ]]; then
  printf '%s\n' "$status" >&2
  printf '%s\n' 'Generated public assets differ from committed bytes' >&2
  exit 1
fi

printf '%s\n' 'Clean-room release audit passed.'
