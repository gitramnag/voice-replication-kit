# Pass 01: stabilise references before changing seeds

Question: which authorised reference and exact-transcript pairs behave
consistently across representative prompts?

Change the reference WAV and its paired transcript. Hold the reviewed runtime,
test copy, text shape, precision, seed set, and listening method constant.

Prepare each pair under the external `upload/refs` directory. Trim only
unrelated silence or noise outside the spoken excerpt. Do not denoise,
compress, splice, or repair the candidate. Transcribe what the WAV contains,
not what the speaker intended to read. Reject clipping, overlapping speech,
music, strong reverberation, and transcript mismatch before using GPU time.

Create one reference object per pair in a versioned private evaluation plan.
Use a neutral public-safe `reference_key`, a direct `refs/*.wav` path, the
exact transcript, and a fresh lowercase SHA-256 digest. Include the same
neutral, warm, and serious test copy for every reference and the same declared
seed set. Add a second prompt when a candidate works only on text close to its
reference transcript.

Run `voice-kit build-matrix` and `voice-kit build-blind-map` with versioned
private `--plan`, `--output`, `--matrix`, and `--secret-output` paths.
Input: the plan and unchanged WAVs. Private output: the complete matrix,
listener-safe rows, and secret map. Next: render the declared matrix and score
every cell.

Naturalness, pacing, pronunciation, and Artifact-free ratings are the primary
stability evidence. Identity still matters, but Pass 02 tests its trade-off
directly. A reference advances only when its transcript and digest verify,
ratings are complete, and acceptable behaviour repeats across prompts. Break a
tie with another controlled prompt, not by changing reference, seed, and shape
together.

Candidate files, transcripts, hashes, filenames, blind maps, ratings, and the
shortlist remain private.

Next: [balance identity and naturalness](02-identity-naturalness.md).
