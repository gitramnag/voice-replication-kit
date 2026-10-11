# Pass 07: audit publication without opening the private root

This is a maintainer-only publication branch. It is not a step in ordinary
voice reuse. Run it from a public-only clone that has no private runtime,
recording, profile, scorecard, request pack, generated WAV, private hash, or
credential.

## Inspect staged public content

Set the repository-local public identity in every publication clone. The staged
audit checks the next author and committer identities.

```powershell
git config --local user.name gitramnag
git config --local user.email 315322897+gitramnag@users.noreply.github.com
voice-kit audit --root . --mode staged
git diff --cached --name-status
git diff --cached
```

Input: staged public files. Public output: sanitised audit results and the diff.
Next: remove or rewrite every unsafe item before committing. Automated checks
cannot recognise every revealing transcript or neutral-looking filename.

## Test a fresh public-only clone

```powershell
git clone --no-local . ..\voice-replication-kit-public-audit
Set-Location ..\voice-replication-kit-public-audit
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts/check_links.py --root .
.\.venv\Scripts\voice-kit.exe --help
.\.venv\Scripts\voice-kit.exe audit --root . --mode tree
.\.venv\Scripts\voice-kit.exe audit --root . --mode history
```

Input: committed public history only. Public output: tests, link and command
checks, and tree and history decisions. Next: inspect tracked and ignored
paths:

```powershell
git ls-files
git status --short --ignored
```

Only expected public caches and environments may appear ignored. The path-only
inventory allows `.pytest_cache`, `*.egg-info`, and everything below `.venv`.
A private workspace means this is not a public-only clone.

The tree audit rejects ignored browser state and `.superpowers` work state by
path name. It accepts ignored `.pyc` and `.pyo` files because Git does not
publish them. Tracked or staged Python bytecode remains forbidden. The audit
never reads or prints ignored private bytes.

After the final code review, move every ignored `.superpowers` file to private
review storage outside the repository. Preserve its repository-relative path
and refuse to overwrite a target. Do not use `git clean`, recursive deletion,
or an operation that opens ignored private bytes.

Run local searches for the real private names, filenames, transcript phrases,
profile keys, and credentials known to the repository owner. Keep those search
terms and results out of scripts, issues, continuous-integration logs, and the
commit. Set `VOICE_KIT_PRIVATE_TERMS_FILE` to the external terms file before
you run either clean-room script. The scripts pass it to the tree and history
audits when it is present.

Publish only when tests pass, links resolve, every documented
`voice-kit` command matches help, tree and history scans pass, private local
searches are empty, and a person has read the headings and command blocks as a
new operator.

If private material entered an unpublished commit, stop before pushing and
rewrite local history. If it was pushed, treat it as disclosed. Deleting the
current file or branch cannot undisclose Git history. Follow
[the disclosure procedure](../privacy-boundary.md#recover-according-to-how-far-the-data-travelled),
rotate exposed credentials, and notify the represented person privately.

Audit commands and clean public results may be shared. Real private terms,
paths, hashes, evaluator identities, and voice-specific settings remain local.

Return to the [README](../../README.md) after the publication decision.

Publish with `git push`. To make a source archive, use `git archive` from the
reviewed commit. Do not ZIP the working folder. Ignored caches can contain a
personal path or other local data that Git excludes.
