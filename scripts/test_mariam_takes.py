"""Mariam intake pipeline evaluation — 2 takes of female Levantine Arabic.

Runs Whisper transcription + Gemma extraction on each take and reports
field-level accuracy against the expected utterance. Matching section
requires a Yusuf record to be pre-loaded in storage.

Usage (from project root):
    .venv/bin/python scripts/test_mariam_takes.py
"""

from __future__ import annotations

import asyncio
import time
from pathlib import Path
from uuid import UUID

import ollama  # sync Client — adapter uses asyncio.to_thread internally
from faster_whisper import WhisperModel

from integration.ollama_adapter import OllamaAdapter
from integration.storage_adapter import StorageAdapter
from integration.system_clock import SYSTEM_CLOCK
from integration.transcription_pipeline import ingest_audio
from integration.whisper_adapter import WhisperAdapter

TAKES = [
    Path("audio_samples/demo_samples/Arabic VO_Mariam_take 1 demo.wav"),
    Path("audio_samples/demo_samples/Arabic VO_Mariam_take 2 demo.wav"),
]

LANG = "ar"
SOURCE_DEVICE = "eval-script"
STORAGE_DIR = Path("storage")

EXPECTED_AR = (
    "أنا مريم العمر، عمري اثنان وثلاثون سنة. أبحث عن أخي يوسف "
    "وابني محمد، عمره ثماني سنوات. فُقدنا قبل ثلاثة أيام عند "
    "البوابة الجنوبية. محمد عنده ندبة فوق حاجبه الأيسر."
)

# Yusuf's record in storage — set to None to skip matching section
YUSUF_RECORD_ID: str | None = "KIN-2026-0042"


def rough_wer(reference: str, hypothesis: str) -> float:
    ref = reference.split()
    hyp = hypothesis.split()
    if not ref:
        return 0.0
    substitutions = sum(1 for r, h in zip(ref, hyp) if r != h)
    deletions = max(0, len(ref) - len(hyp))
    insertions = max(0, len(hyp) - len(ref))
    return round((substitutions + deletions + insertions) / len(ref), 3)


async def evaluate_take(
    take_path: Path,
    whisper_adapter: WhisperAdapter,
    ollama_adapter: OllamaAdapter,
    storage: StorageAdapter,
) -> dict:
    result: dict = {"take": take_path.name, "score": 0, "errors": []}

    print(f"\n{'='*65}")
    print(f"  TAKE: {take_path.name}")
    print(f"{'='*65}")

    if not take_path.exists():
        msg = f"FILE NOT FOUND: {take_path}"
        result["errors"].append(msg)
        print(f"  ERROR: {msg}")
        return result

    # ── 1. WHISPER ───────────────────────────────────────────────────
    print(f"\n[1] WHISPER TRANSCRIPTION")
    t0 = time.monotonic()
    transcription = await whisper_adapter.transcribe(take_path, lang=LANG)
    transcribe_s = round(time.monotonic() - t0, 2)

    wer = rough_wer(EXPECTED_AR, transcription)
    scar_ar = "ندبة" in transcription
    yusuf_ar = "يوسف" in transcription
    mohamad_ar = "محمد" in transcription
    gate_ar = "البوابة" in transcription or "بوابة" in transcription

    print(f"    Transcription : {transcription}")
    print(f"    Rough WER     : {wer:.1%}  (lower is better)")
    print(f"    Key terms:")
    print(f"      يوسف (Yusuf)    : {'✓' if yusuf_ar else '✗ MISSING'}")
    print(f"      محمد (Mohamad)  : {'✓' if mohamad_ar else '✗ MISSING'}")
    print(f"      البوابة (gate)  : {'✓' if gate_ar else '✗ MISSING'}")
    print(f"      ندبة (scar)     : {'✓' if scar_ar else '✗ MISSING'}")
    print(f"    Latency       : {transcribe_s}s")

    result["whisper"] = {
        "transcription": transcription,
        "wer": wer,
        "scar_present": scar_ar,
        "yusuf_present": yusuf_ar,
        "mohamad_present": mohamad_ar,
        "gate_present": gate_ar,
        "transcribe_latency_s": transcribe_s,
    }

    # ── 2. GEMMA EXTRACTION via ingest_audio ─────────────────────────
    print(f"\n[2] GEMMA EXTRACTION (via ingest_audio)")
    t0 = time.monotonic()
    try:
        record, crisis_msg = await ingest_audio(
            take_path,
            lang=LANG,
            source_device_id=SOURCE_DEVICE,
            whisper=whisper_adapter,
            ollama=ollama_adapter,
            storage=storage,
        )
        pipeline_s = round(time.monotonic() - t0, 2)
    except Exception as exc:
        pipeline_s = round(time.monotonic() - t0, 2)
        result["errors"].append(f"ingest_audio raised {type(exc).__name__}: {exc}")
        print(f"    ERROR: {type(exc).__name__}: {exc}")
        result["score"] = 0
        return result

    if crisis_msg:
        print(f"    ⚠️  CRISIS BRANCH triggered — locale message: {crisis_msg!r}")
        print(f"    Extraction skipped. Pipeline latency: {pipeline_s}s")
        result["crisis_triggered"] = True
        result["score"] = 0
        return result

    # IntakeRecord fields: searcher_name, age, last_seen_location,
    # last_seen_date, distinguishing_marks, family_roster (FamilyMember list)
    print(f"\n    SEARCHER")
    searcher_name = record.searcher_name or ""
    searcher_age = record.age
    searcher_name_ok = bool(searcher_name) and (
        "مريم" in searcher_name or "mariam" in searcher_name.lower()
    )
    searcher_age_ok = searcher_age == 32
    print(f"    full_name     : {'OK' if searcher_name_ok else 'MISSING ⚠️'}  → {searcher_name!r}")
    print(f"    age           : {'OK' if searcher_age_ok else f'WRONG ⚠️ (got {searcher_age})'}  → {searcher_age}")

    print(f"\n    FAMILY ROSTER  (expected: Yusuf + Mohamad in family_roster)")
    roster = record.family_roster or []
    print(f"    Count         : {len(roster)}  (expected ≥2)")
    roster_names = [m.name or "" for m in roster]
    yusuf_found = any("يوسف" in n or "yusuf" in n.lower() for n in roster_names)
    mohamad_found = any("محمد" in n or "mohamad" in n.lower() or "mohammad" in n.lower() for n in roster_names)
    print(f"      Yusuf       : {'✓' if yusuf_found else '✗ MISSING'}")
    print(f"      Mohamad     : {'✓' if mohamad_found else '✗ MISSING'}")
    for m in roster:
        print(f"      → {m.name!r}, rel={m.relationship_to_searcher!r}")

    print(f"\n    LAST SEEN")
    ls_loc = record.last_seen_location or ""
    ls_date = record.last_seen_date or ""
    ls_ok = bool(ls_loc) and ("بوابة" in ls_loc or "gate" in ls_loc.lower() or ls_loc)
    print(f"    location      : {'OK' if ls_ok else 'MISSING ⚠️'}  → {ls_loc!r}")
    print(f"    date          : {'OK' if ls_date else 'MISSING ⚠️'}  → {ls_date!r}")

    print(f"\n    DISTINGUISHING MARKS")
    marks = record.distinguishing_marks or ""
    marks_ok = bool(marks)
    scar_in_marks = "scar" in marks.lower() or "ندبة" in marks or "eyebrow" in marks.lower()
    print(f"    marks         : {'OK' if marks_ok else 'MISSING ⚠️'}  → {marks!r}")
    print(f"    scar detail   : {'✓ present' if scar_in_marks else '✗ not extracted'}")

    print(f"\n    Pipeline latency: {pipeline_s}s")

    result["gemma"] = {
        "record_id": str(record.id),
        "searcher_name_ok": searcher_name_ok,
        "searcher_age_ok": searcher_age_ok,
        "roster_count": len(roster),
        "yusuf_found": yusuf_found,
        "mohamad_found": mohamad_found,
        "last_seen_ok": ls_ok,
        "marks_ok": marks_ok,
        "scar_in_marks": scar_in_marks,
        "pipeline_latency_s": pipeline_s,
    }

    # ── 3. AUDIT EVENTS ──────────────────────────────────────────────
    print(f"\n[3] AUDIT EVENTS")
    events = storage.list_audit_events(record_id=record.id)
    event_types = sorted({e.event_type for e in events})
    # Core event types that should fire for a non-crisis intake
    expected_events = {
        "intake_created",
        "field_extracted",
        "match_proposed",
    }
    fired = set(event_types)
    missing_events = expected_events - fired

    print(f"    Total events    : {len(events)}")
    print(f"    Types fired ({len(fired)}): {event_types}")
    field_events = [e for e in events if e.event_type == "field_extracted"]
    print(f"    field_extracted : {len(field_events)} events")
    if missing_events:
        print(f"    Missing ⚠️       : {sorted(missing_events)}")
    else:
        print(f"    All expected event types fired ✓")

    result["audit"] = {
        "total": len(events),
        "fired": sorted(fired),
        "field_extracted_count": len(field_events),
        "missing": sorted(missing_events),
    }

    # ── 4. MATCHING ───────────────────────────────────────────────────
    print(f"\n[4] MATCHING")
    matches = storage.list_match_links(record_id=record.id)
    print(f"    Match links found: {len(matches)}")
    yusuf_match = None
    for m in matches:
        other_id = m.record_b_id if m.record_a_id == record.id else m.record_a_id
        reasoning = m.match_reasoning
        print(f"    → matched with {other_id}")
        print(f"      confidence_score={m.confidence_score:.3f}  band={m.confidence_band}")
        print(f"      reasoning: {reasoning}")
        if YUSUF_RECORD_ID and YUSUF_RECORD_ID in (str(m.record_a_id), str(m.record_b_id)):
            yusuf_match = m

    if not matches:
        print(f"    No matches fired.")
        if YUSUF_RECORD_ID:
            print(f"    (Is {YUSUF_RECORD_ID} loaded in storage/intake_records.jsonl?)")

    result["matching"] = {
        "match_count": len(matches),
        "yusuf_found": yusuf_match is not None,
        "yusuf_score": round(yusuf_match.confidence_score, 3) if yusuf_match else None,
        "yusuf_band": yusuf_match.confidence_band if yusuf_match else None,
    }

    # ── SCORE ─────────────────────────────────────────────────────────
    penalties = 0
    if not searcher_name_ok:  penalties += 2
    if not searcher_age_ok:   penalties += 1
    if len(roster) < 2:       penalties += 2
    if not yusuf_found:       penalties += 1
    if not mohamad_found:     penalties += 1
    if not ls_ok:             penalties += 1
    if not marks_ok:          penalties += 1
    if not scar_in_marks:     penalties += 1

    score = max(1, 10 - penalties)
    result["score"] = score
    print(f"\n[SCORE] {score}/10")

    return result


async def main() -> None:
    print("Loading faster-whisper medium (int8, CPU)...")
    t0 = time.monotonic()
    raw_model = WhisperModel("medium", device="cpu", compute_type="int8")
    print(f"  Model loaded in {time.monotonic() - t0:.1f}s\n")

    whisper_adapter = WhisperAdapter(model=raw_model, clock=SYSTEM_CLOCK)
    ollama_adapter = OllamaAdapter(
        client=ollama.Client(), clock=SYSTEM_CLOCK
    )
    storage = StorageAdapter(storage_dir=STORAGE_DIR, clock=SYSTEM_CLOCK)

    results = []
    for take in TAKES:
        r = await evaluate_take(take, whisper_adapter, ollama_adapter, storage)
        results.append(r)

    # ── SUMMARY ───────────────────────────────────────────────────────
    print(f"\n{'='*65}")
    print("  SUMMARY")
    print(f"{'='*65}")
    header = f"  {'Take':<42} {'Score':>6}  {'WER':>6}  {'Fields'}"
    print(header)
    print(f"  {'-'*62}")
    for r in results:
        w = r.get("whisper", {})
        g = r.get("gemma", {})
        fields_ok = sum([
            g.get("searcher_name_ok", False),
            g.get("searcher_age_ok", False),
            g.get("roster_count", 0) >= 2,
            g.get("last_seen_ok", False),
            g.get("scar_in_marks", False),
        ])
        wer_str = f"{w.get('wer', 0):.0%}" if "whisper" in r else "n/a"
        score = r.get("score", 0)
        print(f"  {r['take']:<42} {score:>5}/10  {wer_str:>6}  {fields_ok}/5 fields")
        for e in r.get("errors", []):
            print(f"    ERROR: {e}")

    scored = [r for r in results if r.get("score", 0) > 0]
    if scored:
        best = max(scored, key=lambda r: (r["score"], -r.get("whisper", {}).get("wer", 1.0)))
        print(f"\n  RECOMMENDED TAKE: {best['take']}  (score={best['score']}/10)")
    else:
        print(f"\n  No takes scored — check errors above.")
    print()


if __name__ == "__main__":
    asyncio.run(main())
