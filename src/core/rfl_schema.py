"""Pydantic v2 models for the audio pipeline and the RFL record.

Two domains, both pure Core data shapes:

  * TranscriptionResult — first-pass adapter output (audio → text +
    English gloss). Used by integration/ollama_adapter.py.
  * RFLRecord + sub-models — the structured intake record built
    incrementally across multi-turn conversations. Day 7+ intake
    logic populates these; Day 9-12 matching consumes them.

Single growing RFLRecord with no versioning per PROJECT_PLAN §6.4
lock — breaking changes break inline.
"""

from typing import Literal

from pydantic import BaseModel


class TranscriptionResult(BaseModel):
    """First-pass adapter output: raw transcription + English gloss.

    Day 5 Session 1A scope. Full RFL record (Name, Age, Relationship,
    LastSeen, Guardian, DistinguishingMarks) lands Days 6-7 per
    PROJECT_PLAN §6.4 once intake conversation flows are designed.
    """

    transcription: str
    english_translation: str


# ─── Intake record domain ────────────────────────────────────────


class Name(BaseModel):
    """Person's name with source-script preservation.

    Field-level usage:
      - canonical: the form Gemma extracted first (or the user typed
        first). Display surface; matching layer prefers source-script
        comparison when available.
      - source_script: which script `canonical` is written in. Used
        by Day 9-12 matching to pick the right comparator (exact
        within-script vs Jaro-Winkler across-script).
      - transliterations: alternate Latin-script forms surfaced
        during intake (e.g. "Mohammed" / "Muhammad" / "Mohamad" for
        the same Arabic name). Empty list when none observed.
        Matching layer iterates these for cross-language linking.
    """

    canonical: str
    """The first-observed form of the name. Required."""

    source_script: Literal["latin", "arabic", "persian", "cyrillic", "other"]
    """Script `canonical` is written in. `other` covers scripts
    KIN doesn't have a dedicated comparator for; matcher falls back
    to transliteration-only compare."""

    transliterations: list[str] = []
    """Alternate Latin-script spellings volunteered during intake.
    Empty list implies no variants surfaced — NOT that none exist."""


class Age(BaseModel):
    """Person's age with confidence flag.

    Refugees frequently provide approximate ages ("about 9", "around
    middle school age"); exact ages typically come from legal
    documents. Matching weights by confidence: exact ages match
    exactly; approximate ages allow ±2 years; unknown ages are
    ignored as a matching signal.
    """

    value: int | None
    """Age in years. None when speaker did not provide an age at all
    (distinct from `confidence='unknown'` which means the speaker
    *attempted* a value but flagged uncertainty)."""

    confidence: Literal["exact", "approximate", "unknown"]
    """How confidently to weight `value` at match-time. Day 7+
    intake logic sets this based on how the age was stated."""


class LastSeen(BaseModel):
    """Where and when the missing person was last seen.

    Both fields are free-text strings — refugees commonly report
    partial dates ('March 2023') or relative timing ('two months
    before the war started'). Day 9-12 matching may attempt
    best-effort parsing of `date_text`; intake just records what
    was said. No validators here.
    """

    location: str | None = None
    """Free-text location as stated. None when not yet captured.
    Display-only at match-time; matching uses corroborating fields
    rather than location-string equality."""

    date_text: str | None = None
    """Free-text time reference as stated ('two weeks ago',
    'before Ramadan 2024'). None when not yet captured. Best-effort
    parsing happens later in the matching layer."""


class Guardian(BaseModel):
    """Guardian information for minors.

    Recorded as flat audit fields. Cross-field enforcement (e.g.,
    minor detection requires Guardian.present and Guardian.consent
    both True before completing intake) lands Day 7-9 with
    safety_rules expansion. This model intentionally does NOT
    validate the relationship between fields — that's a workflow
    concern, not a schema concern.
    """

    present: bool = False
    """Whether a guardian is currently with the speaker / available.
    False when not yet captured OR explicitly absent."""

    consent: bool = False
    """Whether the guardian (if present) has consented to the
    record being created. False when not captured OR refused."""


class FamilyMember(BaseModel):
    """A family member mentioned by the speaker during intake.

    Captures secondary people in the speaker's family network —
    siblings, parents, children — distinct from the primary missing-
    person target. S10 extraction populates these; S11 matching reads
    them for cross-role comparison.

    name mirrors the full_name_source_script discipline: source-script
    preservation. name_transliteration mirrors full_name_transliteration.
    relationship_to_searcher is parallel to RFLRecord.relationship but
    directional: this member's relationship TO the searcher (not to the
    missing-person target).
    """

    name: str
    """Source-script form of the member's name as stated."""

    name_transliteration: str | None = None
    """Latin transliteration when source script is non-Latin (ar/fa)."""

    relationship_to_searcher: str
    """Free-text relationship to the speaker ('son', 'sister', etc.)."""

    status: Literal["missing", "known", "present"] = "missing"
    """Whether this member is also missing, known to be safe, or
    currently present with the searcher."""

    age: int | None = None
    last_seen_location: str | None = None
    distinguishing_marks: str | None = None
    """Free-text identifying feature for this member (scar, mark,
    clothing, hair, tattoo). Source language preserved."""


class RFLRecord(BaseModel):
    """Refugee Family Linking record — the partial intake artifact.

    Single growing model; no versioning (PROJECT_PLAN §6.4 lock).
    All sub-models are optional at the top level: intake conversations
    surface fields incrementally across multi-turn flows, and Day 7+
    logic decides when a record is "complete enough" for matching.

    NOT folded into TranscriptionResult — that's a separate audio-
    pipeline concern. Day 7-9 intake logic bridges them.

    B2-S9 additions: family_roster and searcher_* fields for Option C
    family-network matching. All default-valued; pre-S9 records load
    cleanly with empty roster and null searcher fields.
    """

    name: Name | None = None
    """Subject's name. None until first surfaced during intake."""

    age: Age | None = None
    """Subject's age + confidence. None until surfaced."""

    relationship: str | None = None
    """Speaker's relationship to the subject ('mother', 'older
    brother', 'neighbor'). Free-text in the speaker's words at
    intake time; the matching layer normalizes when scoring
    corroborating fields. Legacy field — preserved alongside
    searcher_relationship_to_target; transcription_pipeline.py reads
    this field; no deprecation in S9."""

    last_seen: LastSeen | None = None
    """When/where the subject was last seen. None until surfaced."""

    guardian: Guardian | None = None
    """Guardian fields, populated when the subject is a minor.
    None implies "not yet asked"; an instance with present=False
    implies "asked, none available"."""

    distinguishing_marks: list[str] = []
    """Free-text identifying details ('scar above left eyebrow',
    'walks with a slight limp'). Empty list when none surfaced.
    Matching layer uses these as corroborating signals."""

    family_roster: list[FamilyMember] = []
    """Additional family members mentioned during intake. Empty list
    when none surfaced (the common case). S10 extraction populates;
    S11 matching reads for cross-role comparison."""

    searcher_name: str | None = None
    """Name of the person speaking (the searcher), in source script.
    None when not captured — many intakes won't state the searcher's
    own name explicitly."""

    searcher_name_transliteration: str | None = None
    """Latin transliteration of searcher_name when non-Latin script."""

    searcher_relationship_to_target: str | None = None
    """Structured parallel of relationship — the searcher's relationship
    to the missing-person target. Both coexist; S10 populates both
    when extraction is updated; this field enables S11 cross-role match."""
