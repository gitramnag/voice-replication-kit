# Pass 00: decide whether the reviewed model fits the use

Question: does the reviewed CosyVoice 3 revision produce intelligible,
controllable speech for the authorised language, content, and delivery risk?

Change only the synthesis engine and its required invocation. Hold reference
audio, exact transcripts, test copy, listening conditions, and post-processing
policy constant. Use public corpus text for the comparison.

The private input is a compact screening plan containing neutral explanation,
matched warm and serious delivery, numbers or abbreviations, one declared
pronunciation override, and a longer passage. Pin every source and model
revision before rendering. Keep raw outputs. If gain would reveal an engine,
make matched-gain listening copies and record that transformation privately.
Do not repair timing or artifacts before scoring.

Build the plan with the
[evaluation schema](../../configs/schemas/evaluation-plan.schema.json), then
run the matrix, blind-map, smoke, and batch procedure in the
[replication guide](../replication-guide.md#2-test-reference-clips-seeds-and-text-shapes-through-passes-00-to-04).

Private outputs are raw candidates, blind listening files, a completed
scorecard, and a written model decision. Advance only when every required row
is complete, ties are resolved blind, the decision survives more than one
prompt, and no repeating defect makes the intended use unsafe or
unintelligible. Set any numeric threshold before listening and keep it private.

If another engine wins, stop this workflow. Record the divergence privately
before adapting later passes; do not describe another system as the reviewed
CosyVoice build.

Public pins and speaker-agnostic prompts may remain public. References,
transcripts, model bytes, generated candidates, scores, notes, and decision
maps stay beneath the external private root.

Next: [stabilise reference candidates](01-reference-stabilization.md).
