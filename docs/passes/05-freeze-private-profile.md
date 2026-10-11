# Pass 05: freeze the accepted recipes

Question: are the accepted recipes complete, internally consistent, and bound
to unchanged reference bytes?

Do not change a synthesis variable in this pass. Use the locked workbook,
unblinding map, accepted references, exact transcripts, and freshly calculated
digests. Build a new `upload/private-profile.json` beneath the external
private root according to
[the public schema](../../configs/schemas/private-profile.schema.json).

The profile contains `schema_version: 1`, `model: cosyvoice3`, and a
non-empty `recipes` object. It includes `narration_neutral` and every style
used by production. Each recipe contains only a direct `refs/*.wav` path, the
exact transcript, a fresh lowercase SHA-256 digest, the accepted 32-bit
unsigned seed, and the accepted text shape.

Use a neutral profile filename and keep the represented person's name out of
paths. Validate the frozen file:

```powershell
voice-kit validate-profile
```

```bash
voice-kit validate-profile
```

Input: the populated profile and its unchanged WAV files. Expected output:
`validated N private profile recipes`. The command does not write a public
artifact. Next: create the production document and run
`voice-kit build-requests`.

Record the profile version, freeze date, profile digest, reviewed source and
model revisions, acceptance-workbook digest, and authorised approver in a
private freeze record. Do not put any of those private values in public logs.

Never edit an accepted profile in place or replace a reference while retaining
its filename. A changed reference, transcript, seed, shape, model revision, or
acceptance rule creates a new version and reopens the earliest affected pass.

The profile advances when structure and reference digests validate, settings
match the locked decisions, and the Pass 06 smoke item is accepted. Changing a
digest without reevaluation is a failure.

Keep the profile, freeze record, references, transcripts, hashes, seeds,
selected styles, and approver identity access controlled and encrypted at
rest. Maintain an encrypted backup under the same policy and deletion
schedule.

Next: [build and render production requests](06-production-renderer.md).
