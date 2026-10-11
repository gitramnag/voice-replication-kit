---
name: Voice Replication Kit
description: A broadcast-control visual system for governed technical workflows.
colors:
  process-cobalt: "#214FD0"
  process-cobalt-soft: "#DDE5FA"
  boundary-red: "#CF3E34"
  boundary-red-soft: "#F5DFDC"
  gate-amber: "#E7BD3C"
  gate-amber-soft: "#F7EDC9"
  gate-amber-text: "#725800"
  cool-paper: "#E8EDF0"
  signal-field: "#F8FAFA"
  graphite: "#17272F"
  muted-slate: "#52656F"
  rule-grey: "#AAB8BF"
typography:
  display:
    fontFamily: "Barlow Condensed, Arial Narrow, sans-serif"
    fontSize: "32px"
    fontWeight: 700
    lineHeight: 1.05
  headline:
    fontFamily: "Barlow Condensed, Arial Narrow, sans-serif"
    fontSize: "16px"
    fontWeight: 700
    lineHeight: 1.1
  title:
    fontFamily: "Barlow Condensed, Arial Narrow, sans-serif"
    fontSize: "10px"
    fontWeight: 700
    lineHeight: 1.2
  body:
    fontFamily: "Atkinson Hyperlegible, Verdana, sans-serif"
    fontSize: "11px"
    fontWeight: 400
    lineHeight: 1.35
  label:
    fontFamily: "Atkinson Hyperlegible, Verdana, sans-serif"
    fontSize: "14px rendered minimum"
    fontWeight: 700
    lineHeight: 1.2
  docket:
    fontFamily: "Atkinson Hyperlegible, Verdana, sans-serif"
    fontSize: "15px rendered minimum"
    fontWeight: 700
    lineHeight: 1.2
  rendered-floor:
    displayLandscape: "38px"
    displaySocial: "42px"
    zoneStagePhase: "20px"
    primary: "16px"
    supporting: "15px"
    connectorControl: "14px"
rounded:
  square: "0px"
  signal: "2px"
spacing:
  grid: "4px"
  compact: "8px"
  standard: "16px"
  section: "24px"
  field: "32px"
components:
  stage-cell:
    backgroundColor: "{colors.signal-field}"
    textColor: "{colors.graphite}"
    rounded: "{rounded.square}"
    padding: "8px"
  decision-pivot:
    backgroundColor: "{colors.gate-amber-soft}"
    textColor: "{colors.graphite}"
    rounded: "{rounded.square}"
    padding: "8px"
  private-package:
    backgroundColor: "{colors.process-cobalt-soft}"
    textColor: "{colors.graphite}"
    rounded: "{rounded.signal}"
    padding: "16px"
  boundary-stop:
    backgroundColor: "{colors.boundary-red-soft}"
    textColor: "{colors.boundary-red}"
    rounded: "{rounded.square}"
    padding: "8px"
  reuse-end-state:
    backgroundColor: "{colors.process-cobalt-soft}"
    textColor: "{colors.graphite}"
    rounded: "{rounded.signal}"
    padding: "16px"
---

# Design System: Voice Replication Kit

## Overview

**Creative North Star: "The Signal Room"**

The system borrows its discipline from broadcast engineering service plans and
control-room signal maps. It presents complex technical work as a governed path
with visible inputs, gates, evidence, boundaries, and outputs. The tone is
precise and calm. Density is welcome when a reader can scan it by lane.

The visual anti-reference is a generic AI or SaaS interface. This system avoids
soft card walls, ornamental technology motifs, and color applied without an
operational meaning. The approved proof is the Studio Journey diagram in
`docs/assets/voice-replication-studio-journey.html`.

**Key Characteristics:**

- Flat, cool, print-first surfaces.
- Condensed operational headings paired with highly legible body copy.
- Question-led stages with what you do, what you get, and how to use it next.
- Orthogonal connectors and explicit trust boundaries.
- Uneven emphasis: the reusable private package and future-audio loop carry the
  most visual weight.

## Colors

The palette behaves like a signal plan: a cool neutral field carries the
system, and each accent has exactly one job.

### Primary

- **Process Cobalt** (`process-cobalt`): successful process flow, primary
  hand-offs, approved output, and the reusable package.

### Secondary

- **Boundary Red** (`boundary-red`): the standing edge around the private
  workspace and voice files.

### Tertiary

- **Gate Amber** (`gate-amber`): the single evaluation pivot where a result is
  accepted or returned.
- **Gate Amber Text** (`gate-amber-text`): readable labels used only inside the
  amber decision field.

### Neutral

- **Cool Paper** (`cool-paper`): the canvas and large quiet regions.
- **White Signal Field** (`signal-field`): working surfaces and nodes.
- **Graphite** (`graphite`): primary text, structural rules, and default
  connectors.
- **Muted Slate** (`muted-slate`): secondary explanation and supporting facts.
- **Rule Grey** (`rule-grey`): hairlines and low-priority subdivisions.

### Named Rules

**The One Signal Rule.** Cobalt means forward production flow, red means the
privacy boundary, and amber marks one decision pivot. Never swap those jobs.

**The Boundary Test.** A red element must answer what stops, where it stops, and
why. If it cannot, remove the red.

## Typography

**Display Font:** Barlow Condensed, with Arial Narrow then sans-serif fallback.

**Body Font:** Atkinson Hyperlegible, with Verdana then sans-serif fallback.

**Character:** Barlow Condensed gives operating labels and questions the direct
voice of a service plan. Atkinson Hyperlegible keeps dense evidence and setup
facts readable at export sizes.

### Hierarchy

- **Display** (700, at least 38px landscape / 42px social after export, 1.05):
  the system outcome.
- **Headline** (700, at least 20px after export, 1.1): zones, stages, phases,
  packages, and major outputs.
- **Primary** (400 or 700, at least 16px after export, 1.35): stage questions,
  actions, evidence, and results.
- **Supporting** (400 or 700, at least 15px after export, 1.35): reasons and
  system facts.
- **Control** (700, at least 14px after export, 1.2): stage numbers, pass
  numbers, connector labels, and correction targets.

### Named Rules

**The Question First Rule.** A process stage begins with the reader's question.
What the reader does, the output, and how to use that output next follow in that
order.

**The Two-Voice Rule.** Condensed type names the system. Hyperlegible type
explains it. Do not add a third display or technical font.

## Layout

All structural geometry follows a 4px grid. Landscape diagrams use a 1280 by
720 viewBox and keep a 40px outer safe area. The social composition uses a 1080
by 1350 viewBox and rebuilds the reading order instead of cropping the
landscape.

Architecture uses a secure corridor with unequal public, firewall, private, and
reuse regions plus separate approved and blocked route gutters. The first build
uses an unequal five-stage runbook: compact setup stages, a wide evaluation
stage, attached output bands, and a dedicated correction gutter. Repeat use is
a four-phase production console with a continuous numbered spine, one failure
gutter, one outer reuse gutter, and a full-width private output band. On narrow
browser surfaces, the SVG keeps its designed width inside a local horizontal
scroller; print releases the minimum width and fits the whole figure.

## Elevation & Depth

The system is flat by design. It uses no shadows. Depth comes from tonal fields,
one- and two-pixel rules, grouping, and the relative weight of boundaries.

### Named Rules

**The Flat Control Rule.** A surface earns separation through a border, a tonal
field, or whitespace. Never combine border and shadow.

## Shapes

Shapes are square or use a restrained 2px signal radius. Hairlines divide
supporting content; two-pixel strokes mark focal paths and trust boundaries.
Connectors are orthogonal, use rounded elbows where needed, and attach at
distinct points. Dashed red rectangles define private zones. Pills, organic
blobs, decorative masks, and generic icon tiles do not belong to this system.

## Components

### Five-stage Runbook

The signature first-build component gives each stage a question header, action
area, attached output band, and short reason line. Stage 04 expands for the five
passes and one amber listening decision. Four named correction returns occupy a
separate gutter and never cross stage content.

### Private Package

The durable system outcome uses Process Cobalt Soft with a stronger cobalt
border and heading. Its contents name the approved references, exact text,
recipes, settings, runtime, and validation evidence without exposing populated
private values.

### Future-Audio Loop

The operating loop uses a numbered cobalt spine in landscape and a short ordered
list in portrait. Its final output is a solid cobalt band naming the 24 kHz WAV
units and append-only manifest.

### Trust Boundary

The privacy boundary is a dashed Boundary Red enclosure with a plain-language
label. It remains visible while the process ends at reuse; it is not a process
step.

### Reuse End State

The process ends with a compact statement that the saved package is ready for
the next script. It names the repeatable result—new 24 kHz WAV files and a
manifest—without repeating the numbered operating loop.

## Do's and Don'ts

### Do:

- **Do** give every accent a stable semantic role.
- **Do** write questions, actions, gates, and outputs in plain language.
- **Do** keep private/public boundaries visible in the diagram topology.
- **Do** draw connectors before nodes and route them orthogonally.
- **Do** recompose for a new aspect ratio instead of cropping or shrinking.

### Don't:

- **Don't** use gradients, glows, glass, shadows, decorative dot fields, or
  background grids.
- **Don't** use raw revision identifiers, internal paths, or populated private
  values as visual content.
- **Don't** turn process stages into equal rounded cards when a matrix carries
  the comparison more clearly.
- **Don't** use red to mean general importance or amber to decorate several
  gates.
- **Don't** describe zero-shot conditioning as newly trained model weights.
