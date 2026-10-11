# Contribute without importing a private voice

Contributions change the public method. Recordings, generated speech, exact
reference transcripts, populated profiles, completed scorecards, speaker
features, model bytes, hashes of private inputs, private paths, credentials,
and personal evaluation notes remain outside the checkout and Git history.

If sensitive material has entered a commit, stop before pushing and follow the
[privacy recovery procedure](docs/privacy-boundary.md). A pushed artifact is a
disclosure; deleting later history does not undisclose it.

## Set up public tooling

Use a 64-bit Windows, Linux, or WSL environment with Git, Python 3.10 to 3.12,
and enough disk for the checkout and tests.

```powershell
python -m venv .venv
. .\.venv\Scripts\Activate.ps1
python -m pip install --require-hashes -r configs/public-tools-lock.txt
python -m pip install --no-build-isolation --no-deps -e .
python -m pytest -q
```

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --require-hashes -r configs/public-tools-lock.txt
python -m pip install --no-build-isolation --no-deps -e .
python -m pytest -q
```

Input: public source only. Public output: an editable installation and test
result. Next: add a focused failing test for executable behaviour, or edit the
human documentation and verify every command against help.

## Keep executable changes test first

Write one test that names the missing or broken behaviour. Run it and confirm
the expected failure. Make the smallest change that passes. Run the focused
test again, then the complete suite. Refactor only while it remains green.

Tests should exercise a command or function rather than mirror source text.
Documentation contract tests may parse command blocks and compare them with
the live parser. Human prose itself does not need brittle wording assertions
unless the wording is a required safety contract.

## Edit generated public artifacts at their source

The recording source is `corpus/recording-script.json`. Regenerate every
Markdown and CSV view after editing it:

```powershell
python -m voice_replication_kit.corpus `
  --source corpus/recording-script.json `
  --output-dir corpus
```

The scorecard source is `tools/build_scorecard.mjs`. Rebuild the workbook and
run `tests/test_scorecard_workbook.py`. Never use the public template for a
real listening session.

Documentation uses repository-relative links and public synthetic names. A
command description names its required input, private or public output, and
the next command. Do not add a checkout-relative private workspace, real voice
detail, or unsupported CLI flag.

## Rebuild the release in a no-local clone

Before proposing a release, run the same clean-room gate used by continuous
integration. It clones without local object sharing, installs the public
package, regenerates the corpus, scorecard, and diagrams, runs the complete
suite and link checker, audits the tree and reachable history, and rejects any
generated diff.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/clean_room_audit.ps1
```

```bash
bash scripts/clean_room_audit.sh
```

Input: the current public repository and reachable history. Public output: a
pass or a named failing gate; the temporary clone is removed. Next: inspect the
staged release diff and resolve every failure before publication.

The scripts do not render a real voice. No real GPU render runs in the public
gate; it remains an authorised-user acceptance step against consented data
outside the checkout.
The sanitized public history has no reviewed exception. The manifest at
`configs/reviewed-history-exceptions.json` must stay empty. It cannot suppress
private-term findings or weaken scans of current bytes.

## Run focused release gates

Use a public-only checkout:

```powershell
python -m pytest -q
python scripts/check_links.py --root .
python scripts/check_publication.py --root .
voice-kit --help
python -m voice_replication_kit.corpus `
  --source corpus/recording-script.json `
  --output-dir corpus
git diff --exit-code -- corpus
```

Input: the proposed public tree. Public output: test, link, command, generated
artifact, and publication results. Next: inspect the complete diff. During
authorised private work, check only staged public content from the work
checkout:

```powershell
voice-kit audit --root . --mode staged
git diff --cached --name-status
git diff --cached
```

Run the tree and history audits again from a fresh public-only clone before
release.

## Write commits from the staged evidence

Set the approved identity in each new clone before you run the staged audit or
create a commit:

```powershell
git config --local user.name gitramnag
git config --local user.email 315322897+gitramnag@users.noreply.github.com
```

Use one subject naming the biggest change, one imperative summary line, and at
most ten one-line bullets. Do not add a test bullet or attribution trailer.
Split unrelated changes.

Pull requests state what changed, where it lands, how correctness is protected,
which commands ran, what was not run, and any known limitation. Do not attach
private audio, completed scorecards, model caches, private logs, or screenshots
of populated profiles.
