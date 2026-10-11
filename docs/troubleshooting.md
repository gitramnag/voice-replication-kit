# Fix the gate that stopped

Keep the failing input and error. Correct its stated cause, then run the same
gate again. Changing several experiment inputs at once makes the result
unusable as evidence.

## Public setup

### `No module named pytest`

The shell is using another Python. Create the public environment and invoke its
interpreter directly:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m pytest -q
```

```bash
python3 -m venv .venv
./.venv/bin/python -m pip install -e '.[dev]'
./.venv/bin/python -m pytest -q
```

Input: public source and the development dependency lock. Public output: test
results. Next: rerun the command that first failed.

### `supply --private-root or VOICE_KIT_PRIVATE_ROOT`

Set one external absolute path and initialise it:

```powershell
$env:VOICE_KIT_PRIVATE_ROOT = 'D:\voice-kit-private\demo-voice'
voice-kit init-private
```

```bash
export VOICE_KIT_PRIVATE_ROOT=/srv/voice-kit-private/demo-voice
voice-kit init-private
```

Private output: the fixed workspace and marker. Next: rerun the original
`voice-kit` command.

### `private root must be outside the Git checkout`

Choose a sibling directory, separate drive, or protected storage mount. Do not
work around the check with a symlink. The resolved path must stay outside the
public clone or extracted source tree.

### `voice-kit: private profile: file is missing or malformed`

The command could not read a valid private profile object. Confirm that the
file exists, is UTF-8 JSON, and matches the public profile schema. The message
does not print the private path or content.

### `voice-kit: private profile: reference hash changed`

Restore the accepted reference bytes if the change was accidental. If the
change was deliberate, repeat the affected blind evaluation and freeze a new
profile version. Do not change only the digest.

### `voice-kit: evaluation matrix: file is missing or malformed`

Build the matrix again from the private evaluation plan, or supply the correct
immutable matrix. The message does not print its path or content.

### `voice-kit: INPUT TYPE: input validation failed`

The named input failed a validation rule that is not safe to print. Validate
it against the matching public schema. An unexpected software failure is not
converted to this message and retains its traceback for repair.

### `history scan requires a Git worktree`

The ordinary replication commands work from an extracted GitHub source ZIP,
but a ZIP contains no reachable commit history. Run staged and history audits
from a complete Git clone. Do not treat a successful tree audit as a history
audit.

### `refusing non-empty private root without a workspace marker`

The directory may contain unrelated data. Inspect it. Choose a new empty
directory unless an authorised operator confirms the content can be moved.
Do not delete an unknown directory.

### The tree publication audit reports private content

The audit is doing its job. Move all private material to the external root.
Use `voice-kit audit --root . --mode staged` while preparing a public commit.
Run `--mode tree` and `--mode history` from a public-only clone.

## Profiles and requests

### `reference_file must name one restricted lowercase .wav beneath refs/`

Use a direct POSIX-style relative name such as
`refs/synthetic-neutral.wav`. The actual file belongs under the external
`upload/refs` directory. Absolute paths, backslashes, nested reference
directories, and `..` are rejected.

### `private reference does not exist`

The profile name and WAV filename differ, or the file is in another directory.
Compare spelling and case. Keep the reference under `upload/refs`; do not
weaken path containment.

### A reference digest does not match

Restore the accepted reference bytes if the change was accidental. If the
change was deliberate, create a new candidate, rerun the affected blind pass,
and freeze a new profile version. Changing only the digest is not a repair.

### `refusing to replace existing request pack`

The file is immutable and the new bytes differ. Preserve it and use a new
versioned `--output` path beneath the external root.

### `request text exceeds 220 characters`

Build requests with `voice-kit build-requests`, which splits at sentence or
word boundaries. If one token exceeds the limit, change the private script or
add an exact pronunciation override before rebuilding.

### `unknown production style`

The document names a style with no profile recipe. Evaluate and add that
recipe, or correct the document to a supported accepted style. A named style
does not silently fall back to neutral.

## Evaluation

### A `Ratings` row is incomplete

One of Identity, Naturalness, Pacing, Pronunciation, Artifact-free, or Emotion
fit is blank or nonnumeric. Enter a whole number from 1 to 5 for every metric.

### `Decisions` says `Review tie`

Replay the tied blind labels without opening the unblinding map. Use a second
relevant prompt if needed, then record the human choice and reason before
unblinding.

### The public workbook contains ratings

Restore the unused public template from a clean public clone. Move the
completed workbook to the external private root and run staged, tree, and
history audits as appropriate. If it was pushed, use the private disclosure
procedure; deleting the latest copy does not undisclose history.

## Pinned runtime and rendering

### Bootstrap refuses an existing CosyVoice source directory

Bootstrap accepts the empty `runtime/cosyvoice` directory created by
`init-private`, but never reuses a populated source checkout because its origin
or worktree may have changed. Inspect the directory and preserve anything
needed. After a partial setup, choose a new external private root, run
`voice-kit init-private`, and run bootstrap there. Copy only reviewed private
inputs from the old root. Keep the old root until the new setup passes. Do not
weaken source verification or delete an unknown runtime.

### CosyVoice or Matcha-TTS cannot be imported

Use the runtime executable beneath
`VOICE_KIT_PRIVATE_ROOT/runtime/venv/bin/voice-kit`, not the public
`.venv`. Rerun pinned bootstrap only into a new runtime location and review
the first installation error. Do not install arbitrary newer packages.

### The first render downloads a model

Bootstrap installs pinned source and Python packages but leaves the verified
model snapshot for the first non-validation render. Provide network access and
free private storage before the smoke session.

### CUDA runs out of memory

Close other GPU work and render one request with `--smoke` or
`--request-id`. Keep `--precision fp16` if the device supports the pinned
runtime. Try `--precision fp32` only for compatibility; it commonly needs
more memory. Record the device, workload, precision, and error privately.
Start with 8 GB VRAM, but treat it as a planning value, not a guarantee.

### The pinned runtime does not support the GPU

The reviewed lock uses PyTorch 2.3.1 and CUDA 12.1. Its prebuilt GPU code
supports NVIDIA compute capabilities `sm_50` through `sm_90`. It does not
support Blackwell `sm_120` GPUs, including the RTX 50 series, and it does not
include an AMD GPU runtime. Use a supported GPU. Do not install unreviewed
packages into the pinned private runtime.

### A full batch requires `--accept-smoke REQUEST_ID`

Render one item with `--smoke`, listen to its WAV, and take the request ID
from its successful manifest record. The ID must belong to the same immutable
request pack. The accepted full batch selects every request in the pack,
including the smoke request again. Outputs are write-once, so that repeated
request creates a new collision-safe output and appends another manifest record
instead of replacing the smoke WAV.

### A rerun creates a suffixed WAV

Outputs are write-once. Compare the manifest records and send any candidate
used for a recipe change back through blind evaluation. Do not replace the
earlier file.

### `CosyVoice returned no audio`

The backend returned no speech chunks. Preserve the request and failure record,
then retry that request. If it repeats, verify non-empty text, the reference
digest, and the pinned runtime. Do not score an empty output.
