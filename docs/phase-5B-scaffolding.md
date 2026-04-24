# Phase 5B — Directory Scaffolding Spec

**Status:** Ready to execute on Day 1 (April 24)
**Prerequisite:** CLAUDE.md test patch applied, prototype copied into place
**Time budget:** 3-4 hours

This spec defines the production directory layout for KIN. Every path here
is load-bearing — tests, imports, and the Clock port design depend on this
structure. Do not improvise it during build.

---

## Full tree

```
kin/
├── CLAUDE.md                          # locked + test patch applied
├── decisions.md                       # append-only ADR log
├── README.md                          # public-facing (judges will read)
├── pyproject.toml                     # ruff + mypy strict + pytest config
├── .env.example
├── .gitignore
├── .pre-commit-config.yaml            # tiered (fast on commit, full on push)
├── Makefile                           # make dev / test / test-full / e2e / fixtures
├── docs/
│   ├── architecture.md
│   ├── safety.md                      # Dr. Megan Jones Bell pre-emption
│   ├── test_strategy.md               # FULL Opus Phase 5A doc, verbatim
│   ├── demo_script.md                 # Phase 5.7 output
│   └── ADR/                           # every ADR as its own file
│       ├── 001-web-ui-primary-demo-surface.md
│       └── 002-test-strategy-invariant-based.md
├── audio_samples/                     # gitignored raw WAVs
├── src/
│   ├── core/                          # pure, no I/O (Python)
│   │   ├── __init__.py
│   │   ├── clock.py                   # Protocol interface
│   │   ├── rfl_schema.py              # Pydantic v2 RFL models
│   │   ├── safety_rules.py            # 4-language crisis detection
│   │   ├── scoring.py                 # tool-call confidence
│   │   └── language_matrix.py         # supported-language gates
│   ├── integration/                   # adapters only, no decisions
│   │   ├── __init__.py
│   │   ├── ollama_adapter.py          # wraps Ollama SDK; padding + timeout + logging
│   │   ├── system_clock.py            # real Clock adapter
│   │   ├── storage_adapter.py         # JSONL queue
│   │   ├── sync_adapter.py            # RFL-compliant JSON emit; no network
│   │   └── ffmpeg_helpers.py          # padding pipeline
│   └── ui/
│       ├── __init__.py
│       ├── terminal_demo.py           # dev surface
│       ├── caseworker_review.py       # Claude Code handoff helper
│       ├── server.py                  # FastAPI, 127.0.0.1 only
│       ├── sse.py                     # SSE event generator
│       └── web/                       # React + Vite + TypeScript
│           ├── package.json
│           ├── tsconfig.json
│           ├── vite.config.ts
│           ├── tailwind.config.js
│           ├── postcss.config.js
│           ├── index.html
│           ├── vitest.config.ts
│           ├── playwright.config.ts
│           ├── public/
│           └── src/
│               ├── main.tsx           # Vite entry
│               ├── App.tsx            # shell (replaces prototype app.jsx)
│               ├── index.css          # Tailwind directives + kin-populate, waveform, link-draw animations
│               ├── components/
│               │   ├── icons.tsx      # barrel re-exports from lucide-react
│               │   ├── primitives/
│               │   │   ├── Button.tsx
│               │   │   ├── Chip.tsx
│               │   │   ├── SectionHeader.tsx
│               │   │   ├── Field.tsx
│               │   │   ├── CompletenessMeter.tsx
│               │   │   ├── Waveform.tsx
│               │   │   └── Divider.tsx
│               │   ├── RecordCard.tsx
│               │   ├── MinorStrip.tsx
│               │   ├── Crisis.tsx          # CrisisReferralCard
│               │   ├── Transliteration.tsx # split/linking/merged view
│               │   ├── DevTrace.tsx
│               │   ├── VoicePanel.tsx
│               │   ├── IntakeTimer.tsx
│               │   ├── TopBar.tsx
│               │   ├── ShortcutHint.tsx
│               │   └── DemoDock.tsx
│               ├── hooks/
│               │   ├── useSSE.ts           # connects to FastAPI /intake/stream
│               │   ├── useKeyboardShortcuts.ts  # ⌘D, ⌘.
│               │   └── useIntakeState.ts   # reducer for record + phase
│               └── lib/
│                   ├── sse.ts              # low-level SSE client
│                   ├── types.ts            # MUST track src/core/rfl_schema.py
│                   ├── i18n.ts             # CRISIS_COPY + localized strings
│                   └── classnames.ts       # tiny cn() helper
├── tests/
│   ├── conftest.py                    # socket monkeypatch, fixture loader,
│   │                                  #   staleness check, gemma4:e2b assertion
│   ├── fakes/
│   │   ├── __init__.py
│   │   ├── fake_clock.py              # heapq-based async FakeClock
│   │   ├── stub_ollama.py             # captures calls, replays fixtures
│   │   └── wav_helpers.py             # make_wav_with_head_silence() etc.
│   ├── core/
│   │   ├── test_clock.py              # port contract tests
│   │   ├── test_rfl_schema.py
│   │   ├── test_safety_rules.py       # 4-lang crisis parametrization
│   │   ├── test_scoring.py
│   │   └── test_language_matrix.py
│   ├── integration/
│   │   ├── test_ollama_adapter_padding.py
│   │   ├── test_ollama_adapter_timeout.py
│   │   ├── test_ollama_adapter_errors.py   # GGML retry, malformed JSON, etc.
│   │   ├── test_storage_adapter.py
│   │   └── test_sync_adapter.py            # includes no-network assertion
│   ├── ui/
│   │   ├── test_server_routes.py           # FastAPI TestClient
│   │   ├── test_sse_events.py              # SSE event type ordering
│   │   └── web/
│   │       ├── components/
│   │       │   ├── RecordCard.test.tsx
│   │       │   ├── Crisis.test.tsx
│   │       │   ├── Transliteration.test.tsx
│   │       │   ├── MinorStrip.test.tsx
│   │       │   ├── IntakeTimer.test.tsx
│   │       │   └── DevTrace.test.tsx
│   │       ├── hooks/
│   │       │   └── useSSE.test.ts
│   │       └── lib/
│   │           └── sse.test.ts
│   ├── redteam/                            # 10 adversarial cases, -m redteam
│   │   ├── test_fatal_assertion_refusal.py
│   │   ├── test_prompt_injection.py
│   │   ├── test_unaccompanied_minor.py
│   │   ├── test_semantic_crisis_paraphrase.py
│   │   └── test_language_mismatch.py
│   ├── e2e/
│   │   └── spanish_fill.spec.ts            # ONE Playwright test
│   └── fixtures/
│       └── gemma/
│           ├── manifest.json               # content-addressed index
│           ├── prompts/
│           │   ├── intake_v3.txt
│           │   ├── intake_v3.sha256
│           │   └── crisis_classifier_v1.txt
│           ├── inputs/
│           │   ├── audio/                  # test WAVs per language
│           │   └── text/
│           └── responses/
│               └── intake_v3/              # captured Day 5-7
├── scripts/
│   ├── capture_fixture.py                  # writes to fixtures/gemma/responses
│   ├── verify_fixtures.py                  # staleness check, run manually
│   ├── evening_push.sh                     # after-hours GitHub sync
│   ├── probe_audio.py                      # ad-hoc Phase 2.5 carryover
│   ├── test_audio_smoke.py                 # smoke check new audio sample
│   └── fetch_*.py                          # carryover from recon
└── results/                                # gitignored raw probe JSONs
    └── phase_2_5_final/                    # archived
```

---

## Layer boundaries (enforced)

The import rules must be programmatically enforceable so a future Claude
Code session can't silently violate them.

### Core → NOTHING
```python
# src/core/safety_rules.py
# VALID:
from src.core.rfl_schema import RFLRecord
# INVALID (caught by test):
from src.integration.ollama_adapter import OllamaAdapter  # NO
from fastapi import ...                                    # NO
import requests                                            # NO
```

### Integration → Core only
```python
# src/integration/ollama_adapter.py
# VALID:
from src.core.clock import Clock
from src.core.rfl_schema import RFLRecord
# INVALID:
from src.ui.server import ...  # NO — wrong direction
```

### UI → Integration + Core
```python
# src/ui/server.py
# VALID:
from src.core.rfl_schema import RFLRecord
from src.integration.ollama_adapter import OllamaAdapter
# Decisions still come from Core; UI just orchestrates.
```

### Test to enforce these rules

```python
# tests/test_layer_boundaries.py
"""Import graph analysis. If a Core module imports from Integration
or UI, this test fails loudly. Prevents silent layer violations."""
import ast
import pathlib
import pytest

CORE_DIR = pathlib.Path("src/core")
INTEGRATION_DIR = pathlib.Path("src/integration")

def _imports_in(path: pathlib.Path) -> set[str]:
    tree = ast.parse(path.read_text())
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name)
    return imports

@pytest.mark.parametrize("path", list(CORE_DIR.rglob("*.py")))
def test_core_has_no_integration_or_ui_imports(path):
    forbidden = ("src.integration", "src.ui", "fastapi", "requests",
                 "httpx", "ollama")
    imports = _imports_in(path)
    violations = [i for i in imports if any(i.startswith(f) for f in forbidden)]
    assert not violations, f"{path} violates Core purity: {violations}"

@pytest.mark.parametrize("path", list(INTEGRATION_DIR.rglob("*.py")))
def test_integration_has_no_ui_imports(path):
    imports = _imports_in(path)
    violations = [i for i in imports if i.startswith("src.ui")]
    assert not violations, f"{path} imports UI (wrong direction): {violations}"
```

This test lives at `tests/test_layer_boundaries.py` (top-level, not under
a layer folder). Two tests, parametrized over every file in Core and
Integration. Catches architectural drift immediately.

---

## Types kept in sync

The single biggest risk of the React + Python split is that the SSE event
schema on the server side drifts from the TypeScript type definitions on
the client side. Without a sync mechanism, you'll discover mismatches at
demo time.

### Option chosen: manual sync with a contract test

Generating TypeScript from Pydantic is tempting but adds ~4 hours of
tooling (`datamodel-code-generator` or similar) and one more thing to
break. For a solo build with ~6 SSE event types, manual maintenance is
fine if backed by a test.

```python
# tests/ui/test_sse_contract.py
"""Ensures that every SSE event type the server can emit has a matching
TypeScript type in src/ui/web/src/lib/types.ts. Failing this test means
the contract drifted — update one side or the other."""
import re
import pathlib
import pytest

from src.ui.sse import ALL_EVENT_TYPES  # defined as a tuple in sse.py

TYPES_FILE = pathlib.Path("src/ui/web/src/lib/types.ts")

def test_every_server_event_has_a_client_type():
    ts_source = TYPES_FILE.read_text()
    # Look for type KinSSEEvent = ... | { type: "foo" } | ...
    declared = set(re.findall(r'type:\s*"([^"]+)"', ts_source))
    missing = set(ALL_EVENT_TYPES) - declared
    assert not missing, f"TypeScript missing event types: {missing}"
```

Any new event type requires updating both sides in the same commit. The
test fails loudly if you forget.

---

## Configuration files to create

### `pyproject.toml` (additions)

```toml
[project]
name = "kin"
version = "0.1.0"
requires-python = ">=3.11"

[tool.pytest.ini_options]
asyncio_mode = "auto"
markers = ["redteam: adversarial cases", "slow: fixture-capture only"]
addopts = "--strict-markers -ra"
testpaths = ["tests"]

[tool.coverage.run]
branch = true
source = ["src/core", "src/integration"]
omit = ["**/__init__.py"]

[tool.coverage.report]
fail_under = 90
exclude_lines = ["pragma: no cover", "raise NotImplementedError", "if TYPE_CHECKING:"]

[tool.ruff]
target-version = "py311"
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "I", "N", "UP", "B", "A", "C4", "RET", "SIM"]

[tool.mypy]
python_version = "3.11"
strict = true
warn_unreachable = true
files = ["src/core", "src/integration"]
# UI layer (server.py) runs strict on its own file but FastAPI decorators
# are untyped in many spots; we don't want to pollute Integration type
# strictness with that.
```

### `.pre-commit-config.yaml` (tiered)

From Opus Phase 5A §6, verbatim — already in the test strategy document.
Commit it as `.pre-commit-config.yaml` and run `pre-commit install` once.

### `Makefile`

```makefile
.PHONY: dev test test-full e2e fixtures verify-fixtures

dev:
	@uvicorn src.ui.server:app --host 127.0.0.1 --port 8000 --reload

test:
	@pytest tests/core tests/integration tests/ui -q -n auto \
		--cov=src/core --cov=src/integration \
		--cov-report=term-missing --cov-fail-under=90

test-full:
	@pytest -q

e2e:
	@cd src/ui/web && pnpm exec playwright test --project=chromium

fixtures:
	@python scripts/capture_fixture.py

verify-fixtures:
	@python scripts/verify_fixtures.py
```

### `src/ui/web/vite.config.ts`

```typescript
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    host: '127.0.0.1',          // match the server.py binding
    proxy: {
      '/api': 'http://127.0.0.1:8000',
      '/intake': 'http://127.0.0.1:8000',
    },
  },
});
```

### `src/ui/web/vitest.config.ts`

```typescript
import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test-setup.ts'],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'html'],
    },
  },
});
```

### `src/ui/web/src/test-setup.ts`

```typescript
import '@testing-library/jest-dom/vitest';
import { cleanup } from '@testing-library/react';
import { afterEach } from 'vitest';

afterEach(() => cleanup());
```

---

## Prototype migration checklist

Day 1 morning, run this in order:

1. **Create directory tree.** Every directory from the spec above, empty.
2. **Copy prototype files into place** under `src/ui/web/src/`. They come
   in as `.jsx` — rename to `.tsx` but don't add types yet. Get it
   rendering first.
3. **Add Vite + Tailwind + TypeScript config.** Get the dev server
   running against the prototype unchanged. Prove the build works.
4. **Convert to TypeScript, one file at a time,** in this order:
   - `icons.tsx` (trivial — just prop types)
   - `primitives/` (one file at a time)
   - `RecordCard.tsx`, `MinorStrip.tsx` (small)
   - `Crisis.tsx`, `Transliteration.tsx` (split the prototype's
     combined file)
   - `DevTrace.tsx`
   - `App.tsx` last (largest, most interconnected)
5. **Apply the three prototype audit fixes** (from yesterday):
   - Match-view narrative rewrite in `Transliteration.tsx`
   - Crisis disabled state: border-shift + "Paused" overlay, drop
     opacity-50 in `RecordCard.tsx`
   - Darken `muted` color token in `tailwind.config.js`
6. **Replace demo sequencer with SSE client.** Hardcoded `DEMO_STEPS`
   setTimeout loop becomes `useSSE('/intake/stream')`. Server emits
   the same event sequence (mocked in tests, live from adapter in
   production). This is the single biggest code change from prototype
   to production.
7. **Write the 3 Day-1 tests** (Opus §8): crisis, minor, timeout.
8. **Write the layer-boundary test.** Earns its 20 lines forever.

Estimated time for steps 1-8: 6-8 hours. That's Day 1 + half of Day 2.

---

## Gitignore

```gitignore
# Python
__pycache__/
*.py[cod]
.pytest_cache/
.coverage
htmlcov/
.mypy_cache/
.ruff_cache/

# Node
node_modules/
dist/
.vite/

# Project
audio_samples/
results/
tests/fixtures/gemma/captures/
.env

# OS
.DS_Store
```

`audio_samples/` is gitignored because WAVs are large. Test fixtures go
under `tests/fixtures/gemma/` (tracked) except the raw capture session
output under `captures/` (gitignored — only vetted fixtures get
committed).

---

## What this spec does NOT cover

These are intentionally out of Phase 5B scope:

- **Docker / containerization.** Not needed for a local demo. Add later
  if judges ask for reproducibility beyond "clone and run".
- **CI/CD (GitHub Actions).** Not needed pre-submission. Local pre-commit
  tier suffices. The evening-push workflow is the sync mechanism.
- **Dependency pinning details.** `pyproject.toml` + `package.json` with
  sensible ranges; no lock-file discipline needed for a 25-day hackathon.
- **Accessibility tooling.** `axe-core` scanning is ideal but adds test
  time. Field-UX principles are baked into the design; formal a11y
  tooling is a post-submission concern.
- **Internationalization library choice.** The `i18n.ts` module holds
  strings as a flat object. If it grows past 50 keys, migrate to
  `react-intl` or similar. Premature for 4 languages × ~15 strings.
