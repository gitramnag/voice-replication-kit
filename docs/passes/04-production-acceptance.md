# Pass 04: make every required style survive production copy

Question: does the provisional profile handle every routed style and difficult
text without a hidden regression?

Change the prompt, declared style, intent, and whole-word pronunciation
override. Hold the provisional profile, reviewed runtime, output policy, and
evaluation method constant.

Cover every style that production may use:

`narration_neutral`, `warm_friendly`, `excited_energetic`,
`serious_authoritative`, `curious_questioning`, `empathetic_calm`,
`emphatic_punchy`, `awe_wonder`, `sorrow_grief`, `anger_fierce`,
`tender_intimate`, `suspense_hushed`, `playful_wry`, and
`triumphant_declaratory`.

For each included style, use an emotion-specific corpus line and an ordinary
sentence that should preserve the style without becoming theatrical. Add
numbers, abbreviations, terms needing a pronunciation override, multiple
sentences, and a long-form neutral passage.

Build a versioned private evaluation plan, then run:

```powershell
voice-kit build-matrix --plan "$env:VOICE_KIT_PRIVATE_ROOT\upload\evaluation-plan-pass-04.json" --output "$env:VOICE_KIT_PRIVATE_ROOT\evaluation\matrix-pass-04.jsonl"
voice-kit build-blind-map --matrix "$env:VOICE_KIT_PRIVATE_ROOT\evaluation\matrix-pass-04.jsonl" --output "$env:VOICE_KIT_PRIVATE_ROOT\evaluation\blind-pass-04.jsonl" --secret-output "$env:VOICE_KIT_PRIVATE_ROOT\evaluation\unblinding-pass-04.json"
```

```bash
voice-kit build-matrix --plan "$VOICE_KIT_PRIVATE_ROOT/upload/evaluation-plan-pass-04.json" --output "$VOICE_KIT_PRIVATE_ROOT/evaluation/matrix-pass-04.jsonl"
voice-kit build-blind-map --matrix "$VOICE_KIT_PRIVATE_ROOT/evaluation/matrix-pass-04.jsonl" --output "$VOICE_KIT_PRIVATE_ROOT/evaluation/blind-pass-04.jsonl" --secret-output "$VOICE_KIT_PRIVATE_ROOT/evaluation/unblinding-pass-04.json"
```

Input: the acceptance plan, provisional profile, and unchanged references.
Private output: immutable candidates, listener-safe rows, a secret map,
rendered raw units, a completed workbook, and a defect list. Next: resolve each
defect at the pass that owns it.

A known-term misread belongs in `pronunciation_overrides` and creates a new
request pack. A shape-specific weakness returns to Pass 03. Repeating identity
or naturalness failure returns to Pass 02 or Pass 01. Empty output,
repetition, truncation, or a digest mismatch blocks acceptance. A weak seed
reopens the declared matrix; it is not replaced silently.

Set the quality threshold before rendering and store it privately. Every
required style needs complete ratings and a recorded decision. Resolve ties
blind and hear pronunciation overrides in context. Rerun affected cases after
a recipe change. A workbook that scored older settings cannot approve the new
profile.

Acceptance WAVs, completed workbooks, thresholds, blind maps, scores, and
decisions remain private.

Next: [freeze the private profile](05-freeze-private-profile.md).
