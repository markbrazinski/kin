# Architecture diagram — change log

For Mark's reference. Records what changed across diagram revisions
and why. Not a Devpost artifact.

## v1 — TB layout, baked-in legend

Initial Mermaid sketch with `flowchart TB` (top-to-bottom layers)
and the legend embedded as a subgraph inside the main flowchart.

Issues that prompted the v2 pivot:
- Aspect ratio rendered at 1584×483 (3.3:1) — far too wide for a
  TB layout. Mermaid's auto-solver placed subgraphs side-by-side
  rather than stacking layers vertically, so the three-layer story
  did not read at all.
- Legend sprawled across the top edge of the canvas as a single
  flat row, eating presentation real estate.
- Caseworker entry point (`USER_CW`) sat orphaned in the upper-
  left away from the External cluster it pointed into.
- Many crossing Integration→Core edges because Core ended up in
  the bottom-right and Integration in the upper-middle.

## v2 — LR layout, separated artifacts

Switched `flowchart TB` → `flowchart LR`. Pulled the legend out
of the main flowchart. First attempt had the legend as a sibling
Mermaid file (`docs/architecture-diagram-legend.mmd`). When
rendered, the three sub-subgraphs (NODES / EDGES / BADGES) laid
out horizontally as a single 1184×128 flat strip — visually
poor.

User decision: drop the standalone Mermaid legend entirely and
use a markdown table in `README.md` next to the embedded
diagram. The Mermaid legend file was deleted.

Also at this stage:
- Added invisible `~~~` chain edges inside each subgraph to pin
  vertical node order (UI / Integration / Core / External /
  CI).
- Split External cluster into two — `EXT_INT` (Integration's
  externals: Ollama, faster-whisper, ffmpeg, filesystem) and a
  free-floating `CCIDE` (Claude Code IDE) near `USER_CW`.
  Visual separation matches conceptual separation: tools KIN
  drives vs separate processes the user launches.
- Promoted `TranscriptionResult` out of an implied nesting
  under `RFLRecord` and into a sibling node inside the Schemas
  subgraph.
- Moved `test_layer_boundaries.py` and `FakeClock` into a
  dedicated `Tooling / CI` subgraph at the bottom, distinct
  from the runtime stack.
- Caseworker review path now correctly shown as **external**
  Claude Code IDE → Ollama via Anthropic-compat API. KIN's UI
  has zero edges into Ollama. (Audit confirmed via AST scan
  in the prior turn — `src/ui/server/*.py` and `src/ui/web/
  src/**` contain no `ollama` / `11434` / `anthropic` /
  `/v1/` references.)

Final v2 render: 2384×743 PNG at `-w 2400 -b transparent`.

## v3 — Final revision pass (this rev)

Five fixes in one pass before shipping.

### Fix 1 — Core node reorder

Changed vertical order inside the Core subgraph from
`SCHEMAS → SAFETY → MATCH → LANGMTX → CLOCK → SCORING` to
`SCHEMAS → SAFETY → LANGMTX → MATCH → CLOCK → SCORING`.

Reasoning: `language_matrix` is imported by both
`whisper_adapter` and `ollama_adapter` (top of the Integration
column), so positioning it higher in the Core column shortens
those edges. `matching` moved down because it's imported by
post-orchestration glue, less edge-density to the top of
Integration.

### Fix 2 — Entry-point clustering

Wrapped `USER_INTAKE` and `USER_CW` in a new subgraph
`ENTRY["User entry points"]` with `direction TB`. Styled with
a subtle dashed grey border and transparent fill so it groups
visually without competing with the layered subgraphs.

Mermaid's LR auto-layout was placing free-floating user nodes
unpredictably; the explicit subgraph forces them to cluster.

### Fix 3 — Legend strategy: keep both

User explicitly chose belt-and-suspenders for this rev:

- The README markdown legend table (added in v2) stays as the
  primary legend.
- `docs/architecture-diagram-legend.mmd` is recreated as a
  standalone Mermaid file. Renders to
  `docs/architecture-diagram-legend.png` (606×1766, vertically
  stacked Node colors / Edge styles / Badge meanings cards).

Why both: the markdown table works inline with text; the PNG
is a self-contained visual companion for anyone consuming the
PNG set directly (slide deck, screenshot embed). The
`classDef` declarations in the legend file are copied verbatim
from the main diagram so colors stay in lockstep — drift-prone,
but the maintenance window is short (May 18 submission).

The v2 failure mode (1184×128 flat strip) was avoided by:
- using three separate inner subgraphs (`NODES`, `EDGES`,
  `BADGES`) with `~~~` chain forcing vertical stacking
- rendering at narrower width (1400px instead of 2400px) so
  Mermaid stacks rather than spreads.

### Fix 4 — Integration column ordering

Source order inside the Integration subgraph stays
`PIPE → WHADAPT → OLADAPT → SYSCLK → PII (storage_adapter,
sync_adapter)`. The user considered moving the PII subgraph
to the middle of the column (between pipeline and adapters)
for storyflow reasons but rejected it: the runtime call graph
is `pipeline → adapters` directly, with storage/sync downstream
of orchestration. Putting PII in the middle would
misrepresent dependency direction. Kept the existing source
order; the `~~~` pinning chain keeps the column tight.

### Fix 5 — Label padding on three nodes

Added a blank line between title and body on `PIPE`, `LBT`,
`FAKES` via doubled `<br/><br/>`. Also added explicit line
breaks inside the `LBT` and `FAKES` body text to control
wrapping rather than letting Mermaid wrap free text
unpredictably.

Specific labels updated:
- `PIPE`: `transcription_pipeline.py<br/><br/>orchestrates
  Whisper → Gemma`
- `LBT`: `tests/test_layer_boundaries.py<br/><br/>AST
  scanner: rejects<br/>Core→Integration, Core→UI,<br/>and
  Integration→UI imports`
- `FAKES`: `tests/fakes/fake_clock.py<br/><br/>FakeClock
  — implements<br/>Clock Protocol`

### Render details

Main diagram: 2384×751 at `-w 2400 -b transparent`. Initial
v3 render at `-w 2000` produced 1984×625 — more compact but
compressed the spacing in ways that partially undid Fix 5.
Re-rendered at 2400px to recover the v2 spaciousness with all
v3 fixes intact.

Legend: 606×1766 at `-w 1400 -b transparent`.

### Files touched in v3

- `docs/architecture-diagram.mmd` (modified — five edits above)
- `docs/architecture-diagram.png` (re-rendered)
- `docs/architecture-diagram-legend.mmd` (created)
- `docs/architecture-diagram-legend.png` (created)
- `README.md` (added legend PNG embed line + dual source link)
- `docs/architecture-diagram-CHANGES.md` (this file, created)

### Out of scope this rev

- Any change to source code, tests, or production architecture.
- A third diagram artifact (runtime-flow vs dependency-graph
  split). Considered briefly during v2; not pursued.
- `git push`. Local commit only.
