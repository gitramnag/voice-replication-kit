# Choose recipes without letting filenames choose for you

Blind evaluation separates generation from judgement. A listener sees a blind
label and hears a candidate. The listener does not see the reference,
transcript, seed, request ID, source filename, model revision, or unblinding
map until the decision is recorded.

## Prepare one controlled question

Each evaluation plan changes one declared variable and holds the others
constant. Examples include changing a reference while keeping the text and
seed fixed, or changing a seed while keeping the reference and text shape
fixed.

Write the question, changed variable, held values, prompts, stopping rule, and
acceptance rule before generation. Store them in a populated
`upload/evaluation-plan.json` beneath the external private root. The
[public schema](../configs/schemas/evaluation-plan.schema.json) defines the
accepted fields.

Build the immutable rows and separate the listener view from the secret map:

```powershell
voice-kit build-matrix
voice-kit build-blind-map
Copy-Item evaluation\voice-evaluation-scorecard.xlsx "$env:VOICE_KIT_PRIVATE_ROOT\evaluation\listening-pass.xlsx"
```

```bash
voice-kit build-matrix
voice-kit build-blind-map
cp evaluation/voice-evaluation-scorecard.xlsx "$VOICE_KIT_PRIVATE_ROOT/evaluation/listening-pass.xlsx"
```

Input: the private plan and its referenced WAV files. Private outputs:
`evaluation/matrix.jsonl`, `evaluation/blind-candidates.jsonl`,
`evaluation/unblinding-map.json`, and a private workbook copy. Next: render
the matrix with the pinned runtime, then present files under blind labels in a
privately recorded random playback order.

The deterministic blind labels preserve the audit trail. Random playback order
reduces order bias. Neither replaces the other. Keep the unblinding map away
from the listener.

## Use the workbook in sheet order

Read `Instructions` first. Enter candidates and all listening scores on
`Ratings`. Record resolved selections on `Decisions`. A populated workbook
stays under the external private root and never replaces the public template.

Rate all six questions from 1 to 5:

- Identity: does it sound like the authorised speaker?
- Naturalness: does it sound like ordinary human speech?
- Pacing: do speed and pauses fit the text?
- Pronunciation: are words and names spoken as intended?
- Artifact-free: is the candidate free of glitches, repetition, and cut words?
- Emotion fit: does the delivery match the requested style?

The scale describes audible behaviour. A score of 1 is unusable because the
problem is obvious. A score of 2 has several distracting problems. A score of
3 is acceptable with audible limitations. A score of 4 has only minor
limitations. A score of 5 has no meaningful issue in that listening pass.

Write evidence in notes, such as a repeated syllable or misplaced pause. Do
not place listener names, speaker names, real request IDs, reference filenames,
hashes, transcripts, or settings in fields intended for listener-safe data.

## Incomplete ratings and ties stop the pass

`Ratings` calculates a mean only after all six metric cells contain valid
numbers. `Decisions` reports the state for each of the fourteen styles:

- `Await candidates`: no rating rows exist for the style.
- `Finish ratings`: at least one required rating is missing.
- `Review tie`: several complete candidates share the best mean.
- `Choose candidate`: one candidate leads but no human choice is recorded.
- `Decision recorded`: a human entered the selected blind label.

The workbook does not break ties. Replay tied candidates on the same text and,
if needed, a second relevant prompt. Record the selection and reason before
unblinding. The Python scoring function applies the same rule: an incomplete
style or tied best score has no winner.

Pass 04 covers every style that production may route:

`narration_neutral`, `warm_friendly`, `excited_energetic`,
`serious_authoritative`, `curious_questioning`, `empathetic_calm`,
`emphatic_punchy`, `awe_wonder`, `sorrow_grief`, `anger_fierce`,
`tender_intimate`, `suspense_hushed`, `playful_wry`, and
`triumphant_declaratory`.

Include one ordinary production sentence for every routed style. This prevents
a theatrical corpus prompt from hiding weak performance on normal copy.

## Lock the workbook before unblinding

When every included style says `Decision recorded`:

1. Save a read-only private copy of the completed workbook.
2. Record its digest in the private experiment ledger.
3. Reveal the candidate-to-request map.
4. Transfer selected recipe values into a new populated profile version.
5. Run `voice-kit validate-profile`.

Input to the final command: the frozen profile and referenced WAVs. Expected
output: the number of validated recipes. Next: build the production request
pack and run the Pass 06 smoke gate.

Scores, notes, selections, blind maps, hashes, and populated profiles remain
private. The public evidence is the method and empty workbook.
