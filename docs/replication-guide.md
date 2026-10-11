# Produce reusable private audio from public source

Use this guide only for a voice whose speaker has given informed permission
for the intended scripts, audience, storage, and retention period. The public
clone or extracted GitHub source ZIP holds the method. One external private
root holds every recording, transcript, score, profile, request, model byte,
output, and manifest.

## Check the two environments

Public tooling needs a 64-bit Windows, Linux, or WSL environment with Python
3.10 to 3.12 and enough disk for the source and tests. Git is required only to
clone or to run staged and history publication audits. Extracted GitHub source
ZIPs support initialisation, validation, request and matrix construction, and
rendering from any directory beneath the extracted root.

For private inference, start with 16 GB RAM, 20 GB free disk, and a GPU with
8 GB VRAM. These values are starting points, not guarantees. Bootstrap also
needs 64-bit Linux or WSL2, Bash, Git, and Python 3.10. Set `PYTHON_BIN` to a
Python 3.10 executable when `python3.10` is not the correct command.

The reviewed lock uses PyTorch 2.3.1 and CUDA 12.1. Its prebuilt GPU code
supports NVIDIA compute capabilities `sm_50` through `sm_90`. This includes
the RTX 40 series, A100, and H100. It does not support Blackwell GPUs such as
the RTX 50 series at `sm_120`. The reviewed lock does not include an AMD GPU
runtime. A real GPU render was not run here. Use the smoke render to confirm
memory and workload compatibility.

From the clone or extracted source root, install and test the public tooling.

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
. .\.venv\Scripts\Activate.ps1
.\.venv\Scripts\python.exe -m pytest -q
$env:VOICE_KIT_PRIVATE_ROOT = Join-Path $env:LOCALAPPDATA 'voice-replication-kit\demo-voice'
voice-kit init-private
```

Bash:

```bash
python3 -m venv .venv
./.venv/bin/python -m pip install -e '.[dev]'
source .venv/bin/activate
./.venv/bin/python -m pytest -q
export VOICE_KIT_PRIVATE_ROOT=/srv/voice-kit-private/demo-voice
voice-kit init-private
```

Input: the public source tree and an empty or previously initialised external
directory. Public output: the tested editable installation. Private output:
the marked directory layout under `VOICE_KIT_PRIVATE_ROOT`. Next: record the
public script.

## 1. Record the public script in your own voice

Output: private WAV recordings outside the Git checkout.

Read [the recording script](../corpus/full-recording-script.md) and the
[emotion catalogue](../corpus/emotion-catalog.csv). Record lossless mono WAVs
with stable room, microphone, gain, distance, and orientation. Keep masters
unchanged. Save retakes as separate files and maintain a private take ledger.

Put selected clean excerpts directly beneath
`VOICE_KIT_PRIVATE_ROOT/upload/refs`. Use neutral synthetic filenames such as
`synthetic-neutral-01.wav`; do not put a person's name in a filename. For
each candidate, record the exact spoken transcript in private storage.

There is no minimum reference duration in this kit. Accept a reference because
controlled listening shows repeatable identity and naturalness, not because it
meets an invented duration.

Next: describe a controlled Pass 00 experiment in
`upload/evaluation-plan.json`.

## 2. Test reference clips, seeds and text shapes through Passes 00 to 04

Output: private scorecards and one accepted recipe for each needed style.

Build the evaluation plan against
[the public schema](../configs/schemas/evaluation-plan.schema.json). It must
contain:

- one non-empty `experiment_question`;
- prompts no longer than 220 characters, each with a unique public-safe ID,
  `source_segment_id`, `unit_index`, `language`, and
  `pronunciation_overrides` object;
- references named as direct `refs/*.wav` children with exact transcripts and
  fresh lowercase SHA-256 digests;
- unique 32-bit unsigned seeds;
- one or more of `short_clause`, `connected_sentence`, and `two_sentences`.

Keep populated plans private. Do not paste a real digest, transcript, seed, or
recording detail into an issue or public log.

Build the immutable candidate matrix.

Windows PowerShell:

```powershell
voice-kit build-matrix
voice-kit build-blind-map
Copy-Item evaluation\voice-evaluation-scorecard.xlsx "$env:VOICE_KIT_PRIVATE_ROOT\evaluation\pass-00-scorecard.xlsx"
```

Bash:

```bash
voice-kit build-matrix
voice-kit build-blind-map
cp evaluation/voice-evaluation-scorecard.xlsx "$VOICE_KIT_PRIVATE_ROOT/evaluation/pass-00-scorecard.xlsx"
```

Input: `upload/evaluation-plan.json` and its referenced WAVs. Private outputs:
`evaluation/matrix.jsonl`, `evaluation/blind-candidates.jsonl`,
`evaluation/unblinding-map.json`, and the private workbook copy. Next:
bootstrap the pinned inference environment and render the matrix.

PowerShell with WSL:

```powershell
$privateRootWsl = (& wsl.exe --exec wslpath -a -u -- "$env:VOICE_KIT_PRIVATE_ROOT").Trim()
if ($LASTEXITCODE -ne 0) { throw 'WSL could not map VOICE_KIT_PRIVATE_ROOT.' }
wsl.exe --exec bash scripts/bootstrap_cosyvoice.sh --private-root "$privateRootWsl"
wsl.exe --exec env "VOICE_KIT_PRIVATE_ROOT=$privateRootWsl" "$privateRootWsl/runtime/venv/bin/voice-kit" render --requests "$privateRootWsl/evaluation/matrix.jsonl" --profile "$privateRootWsl/upload/private-profile.json" --smoke
```

Bash:

```bash
bash scripts/bootstrap_cosyvoice.sh --private-root "$VOICE_KIT_PRIVATE_ROOT"
"$VOICE_KIT_PRIVATE_ROOT/runtime/venv/bin/voice-kit" render --requests "$VOICE_KIT_PRIVATE_ROOT/evaluation/matrix.jsonl" --profile "$VOICE_KIT_PRIVATE_ROOT/upload/private-profile.json" --smoke
```

The renderer requires a profile digest even during evaluation. Create a
schema-valid provisional profile in `upload/private-profile.json` from the
current reference, seed, and text-shape decision before running these commands.
Input: the matrix, provisional profile, references, and reviewed runtime pins.
Private output: one 24 kHz smoke WAV plus one manifest record. Next: listen to
the smoke WAV. If it is intelligible and correctly conditioned, accept its
request ID for the full matrix batch.

Use the manifest procedure in the README to obtain the smoke request ID, then
run the full batch with the same `--requests` and `--profile` values plus
`--accept-smoke REQUEST_ID`. It selects every matrix request, including the
smoke request again. The repeated request creates a new collision-safe output
and appends another manifest record instead of replacing the smoke WAV. Copy or
rename listening files according to `blind-candidates.jsonl`; keep
`unblinding-map.json` away from listeners.

Enter ratings on the workbook's `Ratings` sheet and lock choices on
`Decisions`. Read `Instructions` before each listening session. Repeat
Passes 00 to 04 with new versioned plan, matrix, blind-map, and workbook names.
Use explicit `--plan`, `--output`, `--matrix`, and `--secret-output`
paths when the default immutable files already exist.

Next: freeze only the accepted blind decisions.

## 3. Freeze the accepted recipes in Pass 05

Output: a validated private profile that points to your own reference WAVs.

Build `upload/private-profile.json` against
[the profile schema](../configs/schemas/private-profile.schema.json). The top
level contains only `schema_version`, `model`, and `recipes`. Each recipe
contains only:

- a direct `refs/*.wav` path;
- the exact spoken transcript;
- the fresh lowercase SHA-256 digest of the WAV bytes;
- the accepted 32-bit unsigned seed;
- the accepted text shape.

The profile must include `narration_neutral` and every style named by the
production document. Transfer values from the locked decisions and
unblinding map, not from memory.

Windows PowerShell:

```powershell
voice-kit validate-profile
```

Bash:

```bash
voice-kit validate-profile
```

Input: `upload/private-profile.json` and its reference WAVs. Expected output:
`validated N private profile recipes`. This command writes nothing. Next:
create `upload/production-script.json`.

Keep the profile under access control with encryption at rest and an encrypted
backup. Version it instead of editing an accepted file in place.

## 4. Build and validate immutable requests in Pass 06

Output: a private request pack bound to the script, profile and model revision.

Build the production document against
[the public document schema](../configs/schemas/production-document.schema.json).
It needs `schema_version: 1`, a language, and at least one segment with a
unique ID and speakable text. A segment may add a supported style, intent, and
whole-word pronunciation overrides.

Windows PowerShell:

```powershell
voice-kit build-requests
voice-kit render --validate-only --smoke
```

Bash:

```bash
voice-kit build-requests
voice-kit render --validate-only --smoke
```

Input to the builder: `upload/production-script.json`, the validated profile,
references, and public model pin. Private output:
`upload/requests.jsonl`. The second command validates the first request,
profile digest, reference digest, and model revision without loading the GPU
runtime. Next: render one smoke item with the pinned runtime.

The builder refuses to replace different existing content. Preserve an
earlier pack and choose a new versioned `--output` when the script changes.

## 5. Render one smoke item, listen, then render the batch

Output: new 24 kHz WAV files and appended private manifest records.

PowerShell with WSL:

```powershell
wsl.exe --exec env "VOICE_KIT_PRIVATE_ROOT=$privateRootWsl" "$privateRootWsl/runtime/venv/bin/voice-kit" render --smoke
$manifest = "$env:VOICE_KIT_PRIVATE_ROOT\results\manifest.jsonl"
$smokeRequestId = (Get-Content $manifest | Select-Object -Last 1 | ConvertFrom-Json).request_id
wsl.exe --exec env "VOICE_KIT_PRIVATE_ROOT=$privateRootWsl" "$privateRootWsl/runtime/venv/bin/voice-kit" render --accept-smoke $smokeRequestId --max-batch-seconds 28800
```

Bash:

```bash
"$VOICE_KIT_PRIVATE_ROOT/runtime/venv/bin/voice-kit" render --smoke
SMOKE_REQUEST_ID="$(tail -n 1 "$VOICE_KIT_PRIVATE_ROOT/results/manifest.jsonl" | "$VOICE_KIT_PRIVATE_ROOT/runtime/venv/bin/python" -c 'import json,sys; print(json.load(sys.stdin)["request_id"])')"
"$VOICE_KIT_PRIVATE_ROOT/runtime/venv/bin/voice-kit" render --accept-smoke "$SMOKE_REQUEST_ID" --max-batch-seconds 28800
```

The accepted full batch selects every request in the pack, including the smoke
request again. Outputs are write-once, so that repeated request creates a new
collision-safe output and appends another manifest record instead of replacing
the smoke WAV.

Input: the default request pack, profile, references, verified source checkouts,
and verified upstream model snapshot. The first non-validation render may
download the pinned model. Private output: write-once WAV units beneath
`results/raw/cosyvoice3` and hash-chained records in
`results/manifest.jsonl`.

Before backend preparation, every render reconciles those two locations. A
missing or empty manifest is accepted only when the output directory contains
no prior WAV. Every successful record must name an existing digest-matching
WAV, and every prior WAV must have a success record. Restore the manifest and
outputs together after an interruption; do not delete or truncate the manifest
to restart a batch.

Listen to the smoke WAV before running the batch command. Accept only the
request ID from a successful smoke record for the same request pack. The
28,800-second ceiling is checked between inference calls and cannot interrupt
one inference call already in progress.

Reconcile every request ID against the manifest. Spot-listen the first and last
outputs, every retry, and every style transition. Next: retain the package for
the next script.

## 6. Supply another script and repeat from request construction

Output: the same private voice setup is ready for the next script.

Use versioned filenames so immutable evidence stays intact.

Windows PowerShell:

```powershell
voice-kit build-requests --document "$env:VOICE_KIT_PRIVATE_ROOT\upload\production-script-002.json" --output "$env:VOICE_KIT_PRIVATE_ROOT\upload\requests-002.jsonl"
voice-kit render --requests "$env:VOICE_KIT_PRIVATE_ROOT\upload\requests-002.jsonl" --validate-only --smoke
```

Bash:

```bash
voice-kit build-requests --document "$VOICE_KIT_PRIVATE_ROOT/upload/production-script-002.json" --output "$VOICE_KIT_PRIVATE_ROOT/upload/requests-002.jsonl"
voice-kit render --requests "$VOICE_KIT_PRIVATE_ROOT/upload/requests-002.jsonl" --validate-only --smoke
```

Input: a new private production document and the unchanged accepted profile.
Private output: a new immutable request pack. Next: render that same pack with
`--smoke`, listen, and pass its successful request ID with
`--accept-smoke`. Recording and Passes 00 to 05 remain closed unless the
voice package or acceptance rules change.

## Ready for the next script

The reusable package consists of accepted reference WAVs and transcripts, the
validated profile, pinned runtime, model snapshot, listening decisions, and
append-only manifests. Keep it private, access controlled, encrypted at rest,
and covered by an encrypted backup and deletion schedule.

## Maintainer publication branch

An authorised user does not run Pass 07 to reuse the voice. A maintainer runs
the [publication audit](passes/07-publication-audit.md) from a public-only
clone after repository changes. Never move the external private root into that
clone.
