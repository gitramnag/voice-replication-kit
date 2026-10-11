# Recording corpus

`recording-script.json` is the canonical speaker-agnostic capture pack. It
contains 156 prompts across three tiers, including calibration, fourteen named
emotions, phonetic coverage, technical vocabulary, paralinguistic sounds,
public-domain readings, natural-register top-ups, and long-form passages.

`full-recording-script.md` and the files in `parts/` are generated views. Edit
the JSON, then regenerate the views:

```powershell
python -m voice_replication_kit.corpus `
  --source corpus/recording-script.json `
  --output-dir corpus
```

The prompt text and directions are public. Recordings made from them are not.
Store every recording, transcript alignment, derived clip, and reference
selection outside this repository.

The original pack contains a few Chatterbox-era tuning fields because capture
began as a multi-model comparison. CosyVoice ignores `exaggeration` and
`cfg_weight`. They remain in the canonical JSON to preserve the script's
history; the final workflow uses CosyVoice 3 zero-shot reference conditioning.
