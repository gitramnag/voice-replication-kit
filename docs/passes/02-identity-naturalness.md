# Pass 02: balance identity and naturalness

Question: which shortlisted reference and seed combination gives repeatable
identity without making the speech sound artificial?

Change the shortlisted reference and seed. Hold model revision, prompt text,
text shape, precision, raw-output policy, and listening conditions constant.

Declare the complete private matrix before rendering. The evaluation builder
expands every prompt, reference, seed, and text-shape combination and gives it
a stable request ID. Do not remove a weak cell after hearing it. Preserve a
runtime failure as a result instead of making the comparison look complete.

Use several public prompts with different sentence rhythm. Compare candidates
within the same style. Rate all six workbook metrics even though Identity and
Naturalness answer the main question. A pronunciation defect, repetition, or
other artifact can still veto a high mean.

Start with neutral narration, warm speech, and serious speech. Pass 04 expands
the accepted strategy to every style that production may route.

The private outputs are the matrix, rendered candidates, completed
`Ratings`, resolved `Decisions`, and provisional recipe selections. A
recipe advances only with complete ratings, no unresolved tie, and consistent
results on more than one prompt. Resemblance caused by an artifact, exaggerated
emotion, or text copied from the reference does not pass.

Record the blind label before unblinding. Transfer the revealed values into a
new provisional private profile, then run `voice-kit validate-profile`.
Input: the provisional profile and unchanged references. Expected output: the
number of validated recipes. Next: compare text shapes without changing the
chosen seed.

Seeds, reference pairings, WAVs, scores, labels, and provisional recipes remain
private.

Next: [test reference and text shape](03-reference-text-shape.md).
