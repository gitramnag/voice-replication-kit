# Report voice-data exposure privately

Use a private security advisory in the Git hosting service when a repository
file, commit, release asset, log, or documented workflow may expose
identity-bearing voice data. Do not open a public issue and do not attach the
recording, transcript, embedding, checkpoint, generated sample, private hash,
profile, path, or credential.

Report the affected public path, commit or release identifier, artifact class,
when it became accessible, and the containment already attempted. Maintainers
can reproduce scanner failures with synthetic data.

## Contain disclosure without copying it again

Restrict access and remove public refs or release assets where possible. Use
the hosting provider's sensitive-data removal process. Rotate exposed
credentials, tokens, and deploy keys, then revoke the old values. Notify the
represented person and authorised operators through a private channel and
follow the applicable incident and reporting process.

Deleting a working-tree file, branch, tag, or release does not undisclose
pushed Git history. Treat a pushed voice artifact as disclosed even after the
host removes reachable copies. Check forks, caches, automation logs, and
backups as far as the operator can control them.

The [privacy recovery procedure](docs/privacy-boundary.md#recover-according-to-how-far-the-data-travelled)
separates staged, committed, and pushed cases.

## Protect private operation

Original and derived audio, transcripts, profiles, scorecards, model bytes,
requests, manifests, hashes of private inputs, evaluator notes, and credentials
stay outside the checkout. Limit access to authorised people. Encrypt the
private root at rest and keep an encrypted backup under the same policy.
Apply the consent record's retention and deletion schedule to working copies,
caches, exports, and backups.

## Record the reviewed runtime dependency decision

Decision date: 11 October 2026.

Keep the current CosyVoice runtime lock for upstream compatibility. The
external audit found 186 findings in 16 locked packages. Upgrading this large
GPU stack without an authorised GPU test can cause a different failure or an
unverified output.

Run the lock only in an isolated private runtime. Do not bind it as an
untrusted public service. Do not give it untrusted files, requests, or network
access. The public kit remains a local operator workflow.

A reviewed CosyVoice runtime upgrade triggers a new dependency audit, a clean
bootstrap, a smoke render with consented inputs, and an update to this
decision. Remove this temporary acceptance when a compatible reviewed lock
has no unresolved high-risk finding.

Security fixes apply to the latest commit on the default branch. A historical
release may be withdrawn when its Git objects contain excluded material, but
withdrawal does not reverse disclosure.

## Verify the publication boundary before release

Run the PowerShell or Bash clean-room audit from the repository root. Each
script makes a `git clone --no-local`, installs only the public development
dependencies, rebuilds every committed public asset, runs the complete test
and link suites, scans the tree and every reachable historical blob, and
requires the clone to remain clean.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/clean_room_audit.ps1
```

```bash
bash scripts/clean_room_audit.sh
```

The release operator also supplies an owner-controlled private-terms file to
the final history audit. Keep that file outside the repository and do not copy
its terms into a report or automation log.

```powershell
voice-kit audit --mode history --root . `
  --private-terms-file $env:VOICE_KIT_PRIVATE_TERMS_FILE
```

These checks prove the public method and generated fixtures. They do not run a
real GPU render or authorise use of any voice. An authorised operator performs
that acceptance step with consented inputs in the external private root.

Publish with `git push`. To make a source package, use `git archive` from the
reviewed commit. Do not ZIP the working folder. A folder ZIP can include
ignored bytecode, caches, credentials, or personal paths that Git excludes.

## Require zero reviewed history exceptions

`configs/reviewed-history-exceptions.json` records 0 accepted findings on 0
immutable historical blob IDs. The sanitized public history needs no
exception.

Tree, staged, working-tree, direct-byte, and history scans remain strict.
Missing objects, malformed IDs, unknown codes, duplicate pairs, stale entries,
and owner-supplied private-term matches always stop the audit.
