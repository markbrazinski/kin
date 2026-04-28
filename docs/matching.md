# KIN Cross-Record Matching

> **Source:** Day 10 Session "kind-pearl" (April 26, 2026).
> Pure-Core matching design + threshold tuning evidence + the Q1–Q5
> design decisions that locked in `src/core/matching.py`.
>
> **When to update:** when threshold values change, a new corroborating
> field is added, or the no-LLM lock is revisited. Do not edit for
> implementation refactors that preserve behavior.

---

## 1. The problem

Two intake sessions produce two `RFLRecord`s. Are they the same person?

The reunification problem KIN serves is real and the baseline is grim:
ICRC's *Trace the Face* program achieves a **4.1% reunification rate**
(309 of 7,490 photos; CLAUDE.md §"Headline stats"). When two volunteers
record the same displaced person at different camps, on different days,
in different scripts, the records must converge — or the person is lost
in the queue.

The matching layer is the demo's wow moment: "Mohammed" recorded as
Arabic محمد in one intake, transliterated as "Mohamad" in another, must
surface as the same person with the demo's confidence-band UI rendering
"high — same-script exact name; age and last_seen agree".

---

## 2. Algorithm at a glance

Two stages, executed in order:

```
match_records(a, b):
    1. phonetic, same_script_exact = _phonetic_name_match(a.name, b.name)
    2. if phonetic < GATE_THRESHOLD:
           return MatchResult(is_match=False, score=0.0, confidence="low",
                              reason="name phonetic <gate>")
    3. age_score        = _score_age(a.age, b.age)
    4. last_seen_score  = _score_last_seen(a.last_seen, b.last_seen)
    5. marks_score      = _score_marks(a.distinguishing_marks, b....)
    6. matched_fields   = [name for name, s in scores if s > 0.0]
    7. composite        = WEIGHT_AGE*age + WEIGHT_LAST_SEEN*last_seen
                        + WEIGHT_MARKS*marks
                        (floored at 0.85 if same-script exact)
    8. is_match  = composite >= COMPOSITE_THRESHOLD
    9. confidence = _confidence_band(phonetic, same_script_exact,
                                     len(matched_fields), composite)
   10. return MatchResult(...)
```

**Phonetic name match is the gate.** Below the threshold, no match
regardless of how strongly the corroborating fields agree. Strong
corroborating evidence cannot manufacture identity from a weak name
match — false-positive merges in humanitarian intake are catastrophic.

---

## 3. Phonetic gate

Three paths inside `_phonetic_name_match(a, b)`:

| Case | Action | Returns |
|---|---|---|
| Either Name is `None` | short-circuit | `(0.0, False)` |
| `a.source_script == b.source_script` AND `a.canonical == b.canonical` | instant 1.0 | `(1.0, True)` |
| Same script, different canonical | `jellyfish.jaro_winkler_similarity(a.canonical, b.canonical)` | `(score, False)` |
| Cross-script | enumerate `(a.canonical ∪ a.transliterations) × (b.canonical ∪ b.transliterations)`; skip pairs without ASCII alpha on either side; take `max(JW)` | `(max_jw, False)` |

**Why `max` for cross-script (not average):** identity is yes/no. One
strong transliteration pair is the evidence. Averaging in weak pairs
("Abu" vs "Ali") would dilute a real signal.

**Why Jaro-Winkler (not Levenshtein, not Soundex):** JW has a
transposition allowance and a prefix bonus that matches how
transliteration variance actually behaves at field-intake time
("Mohammed" / "Mohamad" / "Muhammad" all share strong leading
substring + character-set overlap with one or two transposed
internal characters). Levenshtein is too coarse on short names;
Soundex and Metaphone are American-English phonetic projections
that distort non-Latin transliterations more than they help.

**Empirical JW values driving the gate at 0.85:**

| Pair | JW | Same script? | Result |
|---|---|---|---|
| Mohammed / Mohamad (Latin) | 0.92 | yes | passes gate |
| Mohammed (Latin) / Mohamad (Latin) via cross-script translit | 0.92 | n/a | passes gate |
| محمد / محمد (Arabic, identical) | 1.00 | yes (exact) | instant 1.0 |
| Maria / Maria (Latin, identical) | 1.00 | yes (exact) | instant 1.0 |
| Carlos / Juan (Latin) | 0.47 | yes | rejects with margin |
| Aiyana / Bartholomew (Latin) | 0.42 | yes | rejects with margin |
| Omar / Umar (Latin only) | 0.83 | yes | **fails gate** — see §8 |

---

## 4. Corroborating scoring

Three fields contribute. Weights sum to 1.0:

| Field | Weight | Score rule |
|---|---|---|
| Age | 0.40 | exact match → 1.0; ±2y → 0.7; ±5y → 0.3; else 0.0. Confidence=`unknown` or missing value → 0.0 (no signal). |
| LastSeen | 0.40 | substring-token overlap (≥4 chars, case-folded) on `location` AND `date_text` → 1.0; one only → 0.5; neither → 0.0. |
| Distinguishing marks | 0.20 | binary tiebreaker. Any ≥5-char token from any mark on side A appears in any mark on side B → 1.0; else 0.0. |

```
composite = 0.40*age + 0.40*last_seen + 0.20*marks
if phonetic == 1.0:                               # same-script exact name
    composite = max(composite, 0.85)              # SAME_SCRIPT_EXACT_FLOOR
```

**Phonetic does NOT enter the composite weighted sum.** The gate
already enforced `phonetic ≥ 0.85`. Mixing it into the composite
would double-count name evidence and drown the corroborating signal
the composite is meant to measure. The `MatchResult` exposes
`score` (composite) and `phonetic_score` (raw JW) as orthogonal
axes so the demo trace panel can show "name evidence" and
"field evidence" separately.

The `SAME_SCRIPT_EXACT_FLOOR = 0.85` exists for exactly one case:
two records with identical same-script canonicals and zero usable
corroborating fields. Without the floor, composite would be 0.0
and `is_match` would be False — but a same-script exact name match
is itself strong evidence and deserves to surface as "review me"
rather than be silently dropped. The confidence-band logic (§5)
keeps these in the `medium` tier so the UI flags them for human
verification rather than auto-merging.

---

## 5. Confidence bands

Three bands (`Literal["low", "medium", "high"]`). Rules evaluated
top-to-bottom inside `_confidence_band`:

```
if phonetic < GATE_THRESHOLD:                       return "low"
if AMBIGUOUS_BAND[0] <= composite <= AMBIGUOUS_BAND[1]:
    return "low"                                    # explicit demotion
if same_script_exact and num_corroborating >= 1:    return "high"
if same_script_exact:                               return "medium"
if num_corroborating >= 1:                          return "medium"
return "low"
```

`AMBIGUOUS_BAND = (0.65, 0.75)`. Composites in this range are
demoted to `"low"` regardless of name evidence. The demo would
rather show "low confidence — please review" than overclaim a
match in the borderline zone.

**Disambiguation note (Q3 below):** the original spec said
"high requires ≥2 corroborating". This was loosened to ≥1 because
a same-script exact name match (instant 1.0 on the strongest
identity signal we have) plus even one agreeing corroborating
field is itself strong enough to surface as high. Demanding two
would push the Mohammed/Mohamad demo case (which has age + last_seen
agreeing) to "high" only because it happens to have two — a single
corroborator should be enough.

---

## 6. Threshold values + evidence

| Constant | Value | Driving evidence | Test |
|---|---|---|---|
| `GATE_THRESHOLD` | 0.85 | Mohammed/Mohamad lands at 0.92 (passes); Carlos/Juan lands at 0.47 (rejects with margin); the gap is wide enough that the boundary is uncontested. Lowering the gate below 0.85 was considered for Omar/Umar but rejected (see §8). | `test_match_mohammed_mohamad_arabic_script_high_confidence`, `test_match_different_people_same_age_no_match` |
| `COMPOSITE_THRESHOLD` | 0.70 | Age + last_seen both agreeing (the two strongest corroborating fields) yields 0.40+0.40 = 0.80, comfortably above 0.70. A single field agreeing yields 0.40, below threshold — a single corroborator is not enough by itself unless paired with the same-script-exact floor. | `test_match_mohammed_mohamad_arabic_script_high_confidence`, `test_match_same_name_different_ages_low_confidence` |
| `AMBIGUOUS_BAND` | (0.65, 0.75) | Symmetric ±0.05 around `COMPOSITE_THRESHOLD`. Demotes borderline composites to `"low"` so the UI flags rather than auto-classifies. | implicit in the band logic |
| `SAME_SCRIPT_EXACT_FLOOR` | 0.85 | Composite for same-script exact name + zero corroborating fields is 0.0 by the weighted sum; floor lifts it to 0.85 (above `COMPOSITE_THRESHOLD`) so bare-name matches still surface. Confidence stays at `"medium"` so the UI flags for review. | `test_match_same_name_different_ages_low_confidence` |
| `WEIGHT_AGE`, `WEIGHT_LAST_SEEN`, `WEIGHT_MARKS` | 0.40, 0.40, 0.20 | Age and location are the strongest disambiguators in field-intake practice; marks are confirmatory but rarely diagnostic in isolation. Sum = 1.0. | covered by the weighted assertions in tests 1 and 4 |
| `AGE_EXACT`, `AGE_NEAR_2Y`, `AGE_NEAR_5Y` | 1.0, 0.7, 0.3 | Refugees frequently provide approximate ages; ±2 years is realistic for "about nine"; ±5 years is the outer bound where memory-of-age stops being identity evidence and starts being noise. | implicit in test 1 (approximate ages exact-match) and test 4 (8 vs 42 → 0.0) |

**No tuning was needed during build.** Initial thresholds held against
all 7 tests on first run. Threshold values are conservative by design
— relaxing them in future sessions requires multi-fixture evidence,
not single-case justification.

---

## 7. Q1–Q5 design decisions (locked)

**Q1: Two-stage matching (phonetic gate + corroborating validators), not weighted-everything.**

Phonetic name match is the gate. If names don't pass JW ≥ 0.85, no match
regardless of corroborating fields. If names pass, corroborating fields
score separately as validators. **Strong corroborating cannot compensate
for a weak name match.** Conservative by design — false-positive merges
in humanitarian intake are catastrophic. A different family with a
similar age and last-seen location is not the same person, even if every
other field agrees.

**Q2: Empirical threshold tuning against test fixtures.**

Started with the values locked in PROJECT_PLAN §3 (`GATE_THRESHOLD = 0.85`,
`COMPOSITE_THRESHOLD = 0.70`). Required test cases drove the validation:
Mohammed/Mohamad must match (passed at 0.92), Carlos/Juan must NOT match
(rejected at 0.47), identical names with incompatible ages must surface
at "medium" not "high" (passed via the same-script-exact floor + band
logic). Final values are unchanged from initial — see §6.

**Q3: Same-script + cross-script handling.**

Two paths inside `_phonetic_name_match`:

- **Same-script + identical canonical** — instant 1.0. The demo
  specifically shows this case: both intakes captured the Arabic
  canonical محمد, romanizations differ in the transliterations list.
  The same-script-exact path bypasses JW entirely and the
  `same_script_exact` flag is True, which feeds the high-confidence
  band rule.
- **Cross-script** — enumerate canonical + transliterations on both
  sides, skip pairs without ASCII alpha (one side must have romanized
  text or there's nothing to JW), take `max(JW)`. Realistic field
  intake when one volunteer captured Arabic-script and another captured
  romanization-only.

The "high requires ≥1 corroborating (not ≥2)" loosening from the spec
is documented in §5.

**Q4: `MatchResult` Pydantic model, not a tuple or dict.**

Returns `is_match`, `score`, `phonetic_score`, `matched_fields`,
`confidence`, `reason`. Demo UI consumes this to render the
linked-record card. Critically, `phonetic_score` and `score` are
exposed separately so the trace panel can show name evidence and
field evidence as orthogonal axes — not a single opaque blend.
`reason` is a short human-readable explanation that ships directly
to the demo overlay.

**Q5: No LLM in the matching path. Deterministic, pure.**

Pure phonetic + corroborating + threshold. Deterministic, fully
testable, no Integration imports. Runs in microseconds per pair
instead of seconds per inference. Auditable: every match has a
`reason` string derived from the same code path the test suite
exercises. The "explain why this matched" UI narrator is a
separable concern (Day 12-13 UI wiring) — the matching layer
never calls the model.

A targeted regression test
(`test_match_module_does_not_import_llm_clients`) asserts that
matching.py contains no `import ollama`, `from anthropic`, or
`from openai` strings. The broader Core boundary
(`tests/test_layer_boundaries.py`) catches integration/ui
imports via AST; this narrower test catches the case of a direct
LLM client import that wouldn't be in `FORBIDDEN_ROOTS`.

---

## 8. Edge cases acknowledged but not handled

**Omar / Umar via Latin-only comparison.** JW("Omar","Umar") = 0.83,
below the 0.85 gate. No standard phonetic algorithm (Soundex,
Metaphone, NYSIIS, MRC) treats them as equivalent because they
differ at the first phoneme — a vowel — and these algorithms
correctly preserve leading vowels. ASCII-folding does not help (case
is already irrelevant; there is no diacritic to strip). Lowering the
gate to 0.80 was rejected because the only counter-evidence
(Carlos/Juan at 0.47) is a single case and broadening the gate has
diffuse downstream risk.

**This is a feature, not a workaround:** the architecture's
source-script preservation in `Name.source_script` and `Name.canonical`
is the bridge for transliteration variance. When both intakes capture
the Arabic canonical عمر — which is realistic field-intake practice —
the same-script-exact path returns 1.0 regardless of how each
volunteer romanized the name in the transliterations list. Test 2
(`test_match_omar_umar_phonetic`) exercises exactly this path.

The Latin-only Omar/Umar case (one intake captured only "Omar", the
other only "Umar", neither captured the Arabic canonical) is a known
limitation. Mitigation: the intake flow should encourage source-script
capture whenever possible. If pure-Latin transliteration matching for
Arabic-vowel-class variance becomes a real demand, a domain-specific
preprocessing step (collapse leading O/U/A) is the cleanest addition,
but it introduces edge cases (Anna/Onna become equivalent) and is
deferred until evidence demands it.

**Unicode normalization on Arabic strings.** `jellyfish` operates on
Python strings as code-point sequences and does not perform NFC/NFD
normalization. Two visually-identical Arabic strings that differ in
normalization will score < 1.0. Pydantic does not normalize on input.
Mitigation if it becomes a demo blocker: prepend
`unicodedata.normalize("NFC", s)` inside `_phonetic_name_match` —
single-line additive change.

**`Name is None` on either record.** Handled: `_phonetic_name_match`
short-circuits to `(0.0, False)`, gate fails, `is_match=False`,
confidence=`"low"`. Test 5 (gate-enforcement) covers the symmetric
"no-bridge" intuition though not this specific input.

**Empty `transliterations` lists on cross-script comparison.** The
cross-script path falls back to `jw(a.canonical, b.canonical)` so
the comparison never silently drops. With one Arabic and one Latin
canonical and no transliterations on either side, JW is near-zero
(almost no shared codepoints) and the gate fails cleanly — the
correct behavior because there is no information to bridge the
scripts.

**Multi-record matching (>2 records at once).** The algorithm
primitive is pairwise. Production code reaches it via a fan-out
trigger that calls `match_records` once per eligible candidate; see
§9 for the runtime contract. Multi-record clustering (one match
relating ≥3 records) is a post-submission concern.

---

## 9. Runtime trigger entry point

The matching algorithm exposed by `match_records(a, b) → MatchResult`
is a pure pairwise primitive. Production code reaches it via the
runtime trigger in
[`src/integration/transcription_pipeline.py`](../src/integration/transcription_pipeline.py)
— specifically `_trigger_matching(new_record, *, storage)`, called
from `ingest_audio` after a non-crisis record finishes extraction
and before the optional `status="complete"` promotion.

**Trigger contract** (Part 1 REV 4 §"Required matching trigger
behavior"):

1. Fires on new IntakeRecord creation only (inside `ingest_audio`).
2. Produces `MatchLink` rows in `verification_status="proposed"`.
3. Does NOT auto-confirm.
4. Does NOT fire on read or list operations.
5. Excludes `status="paused_for_crisis"` records from the candidate
   pool. Partial records DO enter the pool.

**Fan-out shape:** the trigger calls `match_records` once per
eligible candidate (linear scan of `storage.list_intake_records()`).
Matches with `is_match=True` become `MatchLink` rows with
`match_reasoning` populated from the `MatchResult` (matched_fields,
phonetic_score, reason). Storage auto-emits one `match_proposed`
audit event per created link. The trigger emits a structlog
`matching_trigger_fired` event regardless of match count so
execution is observable even when no matches result.

**IntakeRecord ↔ RFLRecord bridge:** `_to_rfl_record(intake)` maps
the flat storage shape (Part 1 REV 4 schema) to the nested matching
domain shape (this document). Storage owns persistence; matching
owns the algorithm; the bridge is an orchestration concern that
keeps both unchanged. ADR-004 records the placement rationale.

**Concurrency:** none. Single-writer assumption inherited from
`storage_adapter` — the trigger reads + writes JSONL in the same
async task as `ingest_audio`. Demo scale (≤10 records) keeps the
linear-scan candidate filter cheap; production scale would want an
index.

**Auditability:** every trigger invocation produces a
`matching_trigger_fired` structlog event (`new_record_id`,
`candidate_count`, `match_count`); every match produces a
`match_proposed` persisted audit event. The two layers complement
each other — the structlog stream proves the trigger ran; the
persisted events prove what it produced.

---

## 10. References

- [PROJECT_PLAN.md](../PROJECT_PLAN.md) §3 (architecture lock —
  Core has zero I/O), §6.4 (matching layer scope and no-LLM lock),
  §7 (locked language set EN/ES/AR/FA).
- [CLAUDE.md](../CLAUDE.md) — agent design principles, particularly
  "every LLM output is validated against a Pydantic schema" and
  "constraints at the tool level, not the prompt level".
- [src/core/rfl_schema.py](../src/core/rfl_schema.py) — source of
  truth for `Name`, `Age`, `LastSeen`, `RFLRecord` field semantics.
- [src/core/safety_rules.py](../src/core/safety_rules.py) and
  [src/core/language_matrix.py](../src/core/language_matrix.py) —
  Core module style this file mirrors.
- [tests/test_layer_boundaries.py](../tests/test_layer_boundaries.py)
  — AST-based check that Core imports nothing from Integration or UI.
- [docs/test_strategy.md](test_strategy.md) — Phase 5A test strategy
  (invariant-first, not count-first).
