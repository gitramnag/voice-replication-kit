# Keep the voice outside the public repository

The repository reproduces a method, not a person. Store identity-bearing
material in an external private root and never in the checkout, including an
ignored directory.

## Confirm permission before collection

Obtain informed consent from the represented person before recording or using
their existing audio. The consent record should name the intended scripts,
audience, operators, storage locations, retention period, deletion process,
and whether generated speech may be shared. A licence to use text or a model
does not grant permission to reproduce a person's voice.

Stop collection or rendering if the intended use exceeds that permission.
Keep the consent record private with the voice package.

## Apply the same controls to every private artifact

Private material includes:

- original recordings, derived clips, generated speech, listening copies, and
  acoustic fingerprints;
- exact reference transcripts, populated evaluation plans, completed
  scorecards, blind maps, evaluator notes, and acceptance thresholds;
- populated profiles, seeds, hashes of private inputs, request packs,
  manifests, runtime provenance, model bytes, and speaker features;
- credentials, account details, billing records, private absolute paths, and
  the identities of speakers, listeners, and authorisers.

Browser automation profiles are private runtime state too. Keep Edge review
profiles, cookies, login databases, history, sessions, and local storage in a
dedicated directory outside the repository rather than under `.impeccable`.

Limit access to people named by the consent and operating policy. Use
individual accounts instead of shared credentials. Encrypt the private root at
rest. Keep an encrypted backup under the same access policy and test that the
authorised operator can restore it.

Set a deletion date or review interval. Deletion covers working files, caches,
exports, temporary listening copies, manifests when policy permits, and every
backup copy. Record what was deleted and when without copying voice-specific
values into a public log.

The public corpus, empty workbook, schemas, source code, tests, reviewed pins,
and speaker-agnostic examples may be public.

## Initialise and check the boundary

```powershell
$env:VOICE_KIT_PRIVATE_ROOT = 'D:\voice-kit-private\demo-voice'
voice-kit init-private
voice-kit audit --root . --mode staged
```

```bash
export VOICE_KIT_PRIVATE_ROOT=/srv/voice-kit-private/demo-voice
voice-kit init-private
voice-kit audit --root . --mode staged
```

Input to `init-private`: an external empty directory or a valid existing
private workspace. Private output: the marked fixed layout. Input to
`audit`: public staged content only. Public output: a pass message or
sanitised findings. Next: correct every finding before committing.

`.gitignore` is an accident barrier, not access control. The tree audit must
fail if private material is present in the checkout, even when Git ignores it.
For ignored paths, the audit inventories names only. It rejects private
workflow roots and markers, private-capable artifact names, credential or
local-secret names, browser state, local workflow state, and source-tree `.pyc`
or `.pyo` files outside `.venv`. Ignored paths below `.venv`, `.pytest_cache`,
and `*.egg-info` are public tooling state. Three static finish-review PNGs under
`.impeccable/review` are the only local evidence exception. The audit does not
read or print ignored private bytes.

## Recover according to how far the data travelled

If a private file is only staged, unstage it, move it to the external private
root, and rerun the staged audit.

If it entered an unpublished commit, stop before pushing. Rewrite the affected
local history or start from a clean public clone, then verify the object
database and history. Removing the working-tree copy is not enough.

If it was pushed, treat it as disclosed. Removing a branch, release, or file
does not undisclose pushed Git history. Preserve the facts needed for response,
then:

1. restrict access and remove public refs or release assets where possible;
2. use the hosting provider's sensitive-data removal process;
3. rotate every exposed credential or token and revoke old access;
4. notify the represented person and repository security contact through a
   private channel;
5. follow the consent terms, organisational incident process, and applicable
   reporting duties;
6. verify public clones, forks, caches, logs, and backups as far as the
   operator can control them.

Do not paste the exposed audio, transcript, hash, profile value, private path,
or credential into an issue or disclosure ticket. Report the affected public
path, commit or release identifier, artifact class, and containment status.
Use synthetic data to reproduce a scanner failure.
