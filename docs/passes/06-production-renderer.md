# Pass 06: bind a script to immutable requests and render it

Question: can the frozen profile render a new production document without a
hidden setting change or overwritten evidence?

The production document may change text, declared style, intent, and
pronunciation overrides. Hold the profile, model revision, reference bytes,
seeds, text shapes, and precision policy constant.

## Build and validate the request pack

Place a schema-valid `upload/production-script.json` beneath the external
private root. Then run:

```powershell
voice-kit build-requests
voice-kit render --validate-only --smoke
```

```bash
voice-kit build-requests
voice-kit render --validate-only --smoke
```

Input: the production document, validated profile, references, and reviewed
model pin. Private output: immutable `upload/requests.jsonl`. The validation
command checks the first request, profile digest, reference digest, and pin
without importing GPU libraries. Next: render that first request with the
pinned runtime.

The builder routes an explicit style first, then recognised intent, then
`narration_neutral`. It applies whole-word pronunciation overrides, shapes
units without exceeding 220 characters, derives stable request IDs, and
refuses to replace different existing content.

## Render one item and listen

```bash
"$VOICE_KIT_PRIVATE_ROOT/runtime/venv/bin/voice-kit" render --smoke
```

Input: the default request pack, profile, references, pinned source checkout,
and verified model snapshot. Private output: one 24 kHz WAV under
`results/raw/cosyvoice3` plus an appended manifest record. Next: listen for
intelligibility, correct conditioning, pronunciation, and gross artifacts.

Do not accept a failed or unheard smoke. Read the request ID from its successful
manifest record and run the batch:

```bash
"$VOICE_KIT_PRIVATE_ROOT/runtime/venv/bin/voice-kit" render --accept-smoke "$SMOKE_REQUEST_ID" --max-batch-seconds 28800
```

The accepted full batch selects every request in the pack, including the smoke
request again. Outputs are write-once, so that repeated request creates a new
collision-safe output and appends another manifest record instead of replacing
the smoke WAV.

The 28,800-second ceiling is checked between inference calls; it cannot stop an
inference call already running. Successful WAVs are write-once. A retry gets a
new filename. Every success and failure appends a hash-chained manifest record.

Reconcile every request ID against the manifest. Verify output paths and
digests, then spot-listen the first output, last output, every retry, and each
style transition. The public kit stops at raw units; mastering and final
encoding must not hide a synthesis defect.

## Reuse the frozen package

Preserve the first document and request pack. Use versioned paths for another
script:

```powershell
voice-kit build-requests --document "$env:VOICE_KIT_PRIVATE_ROOT\upload\production-script-002.json" --output "$env:VOICE_KIT_PRIVATE_ROOT\upload\requests-002.jsonl"
voice-kit render --requests "$env:VOICE_KIT_PRIVATE_ROOT\upload\requests-002.jsonl" --validate-only --smoke
```

```bash
voice-kit build-requests --document "$VOICE_KIT_PRIVATE_ROOT/upload/production-script-002.json" --output "$VOICE_KIT_PRIVATE_ROOT/upload/requests-002.jsonl"
voice-kit render --requests "$VOICE_KIT_PRIVATE_ROOT/upload/requests-002.jsonl" --validate-only --smoke
```

Input: the next production document and unchanged profile. Private output: a
new immutable pack. Next: render the same pack with `--smoke`, listen, then
pass its successful ID with `--accept-smoke`.

Requests, profiles, references, generated WAVs, manifests, private hashes, and
failure logs remain outside Git.

Ready for the next script. Maintainers continue separately to
[Pass 07](07-publication-audit.md) only when preparing a public release.
