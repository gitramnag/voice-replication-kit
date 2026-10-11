# Build once, then reuse the private voice package

The approved [Studio Journey diagram](assets/voice-replication-studio-journey.html)
shows where everything lives, the first private build through Pass 05, repeat
production for a new script, and the publication boundary in one frame. Static
[SVG](assets/voice-replication-studio-journey.svg) and
[PNG](assets/voice-replication-studio-journey.png) versions are also available.

## The public checkout never becomes the private workspace

```text
voice-replication-kit/                 public Git checkout
├── configs/                           public schemas and reviewed pins
├── corpus/                            public recording script
├── evaluation/                        public blank workbook
├── scripts/                           public bootstrap and checks
└── docs/                              public operator manual

D:\voice-kit-private\demo-voice\       external private root on Windows
/srv/voice-kit-private/demo-voice/     external private root on Linux or WSL
├── upload/
│   ├── refs/                          private reference WAVs
│   ├── evaluation-plan.json           private experiment definition
│   ├── private-profile.json           private accepted recipes
│   ├── production-script.json         private production text when required
│   └── requests.jsonl                 immutable private request pack
├── evaluation/                        matrices, scorecards and decisions
├── runtime/                           pinned source, environment and model
└── results/
    ├── raw/cosyvoice3/                24 kHz WAV output
    └── manifest.jsonl                 append-only outcome records
```

`voice-kit init-private` creates the fixed private layout and marker. Every
other user command accepts `--private-root` or reads
`VOICE_KIT_PRIVATE_ROOT`. The resolver rejects a path inside the checkout.

## Recording produces candidates, not a production profile

The canonical [recording source](../corpus/recording-script.json) generates the
[156-prompt script](../corpus/full-recording-script.md), twelve part files, and
the [emotion catalogue](../corpus/emotion-catalog.csv). The complete capture
target is 2,155 seconds across three tiers. These are capture goals from the
public source, checked 2 October 2026, not guaranteed recording durations.

Record lossless mono WAVs with stable room, microphone, gain, distance, and
orientation. Keep masters unchanged and save retakes separately. A runtime
recipe uses a selected excerpt, its exact transcript, a 32-bit unsigned seed,
and one text shape. The full corpus is evidence for selecting that recipe; it
is not sent to the model for every render.

Each reference path in a profile is relative to `upload`, for example
`refs/synthetic-neutral.wav`. The profile stores a fresh SHA-256 digest and
the exact transcript. Those values remain private.

## Passes 00 to 04 change one controlled variable at a time

Pass 00 screens the reviewed model. Pass 01 stabilises reference candidates.
Pass 02 balances identity and naturalness. Pass 03 compares reference and text
shape. Pass 04 tests every production style and difficult text. A failed gate
returns to the earliest changed input instead of reopening every setting.

`voice-kit build-matrix` turns `upload/evaluation-plan.json` into immutable
`evaluation/matrix.jsonl`. `voice-kit build-blind-map` creates listener-safe
candidate rows and a separate private unblinding map. Listeners work from a
private copy of the blank workbook and do not see references, transcripts,
seeds, request IDs, hashes, or source filenames.

## Pass 05 freezes what listening accepted

The populated profile conforms to
[the public profile schema](../configs/schemas/private-profile.schema.json).
It must include `narration_neutral` and every style used by the production
document. `voice-kit validate-profile` checks the structure, resolves each
reference beneath the private root, and verifies its digest.

Changing a reference, transcript, seed, text shape, model revision, or
acceptance rule creates a new profile version and reopens the affected pass.
The earlier profile and its decisions remain unchanged.

## Pass 06 binds each script to the frozen package

`voice-kit build-requests` combines the production document, profile, and
reviewed model revision. It writes immutable JSON Lines and refuses to replace
different existing content. Request IDs derive from the synthesis identity, so
a changed input creates a changed request.

`voice-kit render --validate-only --smoke` checks the first request,
reference, profile, and model pin without loading GPU libraries. The pinned
runtime then renders one smoke item. The operator listens before passing the
successful smoke request ID to `--accept-smoke` for the batch.

The accepted full batch selects every request in the pack, including the smoke
request again. Outputs are write-once, so that repeated request creates a new
collision-safe output and appends another manifest record instead of replacing
the smoke WAV.

The renderer writes 24,000 Hz WAV units beneath
`results/raw/cosyvoice3`. It never overwrites an earlier WAV. Every success
or failure appends a hash-chained record to `results/manifest.jsonl`.

The reviewed runtime has three pinned inputs:

| Component | Reviewed identifier | Private location |
|---|---|---|
| CosyVoice source | `074ca6dc9e80a2f424f1f74b48bdd7d3fea531cc` | `runtime/cosyvoice` |
| Matcha-TTS source | `dd9105b34bf2be2230f4aa1e4769fb586a3c824e` | `runtime/cosyvoice/third_party/Matcha-TTS` |
| CosyVoice 3 model | `FunAudioLLM/Fun-CosyVoice3-0.5B-2512` at `29e01c4e8d000f4bcd70751be16fa94bf3d85a18` | `runtime/models/cosyvoice3` |

The public model manifest lists 20 files totalling 9,747,516,745 bytes, about
9.08 GiB, checked on 2 October 2026. Allow additional space for source,
packages, caches, private references, and rendered WAVs.

## Ready for the next script

Reuse starts at request construction. Store the next production document under
a new versioned name, build a new versioned request pack, validate it, render
and listen to one smoke item, then accept that smoke for the batch. Do not
repeat recording or Passes 00 to 05 unless the voice package changes.

## Maintainer publication branch

Pass 07 begins only after the authorised user path reaches reusable output. A
maintainer uses a separate public-only clone to check the tree, staged content,
links, tests, and Git history. Private audio, runtime files, profiles,
scorecards, paths, terms, and hashes do not enter that clone or its logs.

The [replication guide](replication-guide.md) provides executable PowerShell and
Bash procedures. The [evaluation guide](evaluation-guide.md) covers the workbook.
The [troubleshooting guide](troubleshooting.md) maps a failed gate to the input
that must be corrected.
