# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

Public documentation and self-contained HTML/SVG diagrams in a Python repository.

## Users

Technical leaders, engineers, creators, and authorised speakers who want to
reproduce a controlled CosyVoice zero-shot workflow for their own voice. A
first-time builder must be able to understand the complete system without LLM
assistance.

## Product Purpose

The kit provides a reproducible method for recording, evaluating, freezing,
and operating a private voice-production workflow. Its durable outcome is a
private voice package that can render future narration, dialogue, and approved
delivery styles from new scripts.

## Positioning

The repository publishes the method, speaker-agnostic recording programme,
evaluation structures, validators, and renderer while excluding every artifact
that could reproduce a particular person's voice. It uses CosyVoice zero-shot
conditioning, with upstream model weights kept outside the public repository.

## Operating Context

Builders start from a public-only checkout, create private storage, record the
authorised speaker, prepare clean reference and transcript pairs, install the
pinned CosyVoice runtime, compare candidates through blind listening, freeze a
private profile, and render new scripts through immutable requests. A release
audit runs from a checkout that contains no private material.

## Capabilities and Constraints

- The public recording programme contains 156 prompts across 14 delivery
  styles with a target duration of 35:55.
- Eight ordered passes cover model screening, reference stability, identity and
  naturalness, text shape, style acceptance, profile freeze, production render,
  and publication audit.
- The evaluation workbook rates identity, naturalness, pacing, pronunciation,
  artifact-free output, and emotion fit on a 1 to 5 scale.
- The renderer produces 24 kHz WAV units and an append-only manifest.
- The practical render baseline is Linux or WSL2, Python 3.10, 16 GB RAM, 20 GB
  free disk, and an NVIDIA GPU. The project's 8 GB VRAM starting point is not an
  upstream guarantee.
- Personal recordings, real reference transcripts, voice-derived audio,
  completed scorecards, populated profiles, hashes, seeds, model weights, and
  speaker features never enter public Git history.

## Brand Commitments

Create a precise, distinctive visual identity that can become a foundation for
future technical projects. Diagrams must read as authored engineering
communication, not generic AI artwork. Question-led language, visible control
gates, and the public/private boundary are durable traits.

## Evidence on Hand

- `corpus/recording-script.json` is the canonical recording programme.
- `configs/pins.json` is the authority for source and model revisions.
- `evaluation/voice-evaluation-scorecard.xlsx` is the blank
  listening workbook.
- `docs/passes/00-model-screening.md` through
  `docs/passes/07-publication-audit.md` define the ordered gates.
- `src/voice_replication_kit/requests.py` and
  `scripts/run_cosyvoice3.py` implement request validation and rendering.
- `docs/privacy-boundary.md` defines the publication exclusions.

No personal voice, recording, generated audio, populated profile, completed
evaluation, or model weight is available or required for the public diagram.

## Product Principles

- Explain the complete operating system before exposing implementation detail.
- Keep private voice assets local by construction, not by convention.
- Change one experimental variable at a time and reopen the earliest affected
  gate when evidence fails.
- Treat the reusable private voice package as the product outcome and rendered
  WAV files as repeatable outputs from it.
- Prefer exact, actionable language over internal identifiers and jargon.

## Accessibility & Inclusion

Public diagrams require an accessible SVG title and description, WCAG AA
contrast, a logical reading order, and a plain-language explanation in the
surrounding documentation.
