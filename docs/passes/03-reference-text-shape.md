# Pass 03: choose a text shape without hiding reference defects

Question: which text grouping preserves continuity for each provisional recipe
without carrying a mistake across too much copy?

Change one reference strategy or one text shape per comparison. Hold the
reviewed model, selected seed, source text, pronunciation overrides, precision,
and listening conditions constant.

The builder supports three shapes:

- `short_clause` splits further after commas, semicolons, and colons;
- `connected_sentence` renders sentence-like units separately;
- `two_sentences` pairs adjacent sentences when the result stays within 220
  characters.

Build a complete private matrix in which each reference strategy sees the same
short and multi-sentence public copy. Keep every exact transcript with its own
WAV. Render raw units and listen for boundary clicks, reset intonation, rushed
pairs, dropped endings, unwanted pauses, and emotion that fades within a pair.
Do not assemble units before scoring because assembly can hide a boundary
defect.

Input: provisional recipes and a versioned evaluation plan. Private outputs:
immutable candidates, blind ratings, and one recorded text-shape choice per
recipe. Next: transfer provisional choices to a new profile version and test
them on production acceptance copy.

Select a shape only after every declared cell is rated and ties are resolved.
Prefer the simpler grouping when results are audibly equivalent. A
style-specific shape needs the same improvement on another relevant prompt.
If no shape is stable, return to Pass 01 instead of adding punctuation tricks
to production text.

References, transcripts, seeds, audio, ratings, and selected shapes remain
private.

Next: [run production acceptance](04-production-acceptance.md).
