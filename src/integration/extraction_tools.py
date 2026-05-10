"""Module-level constants for the extract_intake_fields tool.

EXTRACT_INTAKE_FIELDS_TOOL is the JSON Schema dict passed to
OllamaAdapter.tool_call(); lifted verbatim from the Apr 28 GREEN
hello-world (scripts/gemma_extraction_helloworld.py) and validated
across EN/AR/FA in the Apr 29 multilang sweep
(scripts/gemma_extraction_multilang_sweep.py).

ExtractIntakeFieldsArgs is the Pydantic model S4 uses to validate the
arguments dict returned by tool_call(). tool_call() itself does NOT
validate against this model — keeps the adapter reusable for future
tools.

B2-S10: FamilyMemberArg DTO and four new tool parameters (searcher_name,
searcher_name_transliteration, searcher_relationship_to_target,
family_members). Probe confirmed gemma4:e2b cleanly separates primary
target from secondary family members with the extended schema; no
conflation or hallucination observed across 5 probe utterances
(EN/ES, single- and multi-entity, named and unnamed).
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, model_validator


class FamilyMemberArg(BaseModel):
    """Extraction-layer DTO for a single family member returned by the tool.

    Intentionally decoupled from core.rfl_schema.FamilyMember — the
    extraction schema must not couple to Core model changes. status is
    str (not Literal) so an invalid model response doesn't crash
    validation; _map_family_members() in transcription_pipeline.py
    guards the Literal constraint.
    """

    model_config = ConfigDict(extra="ignore")

    name: str
    name_transliteration: str | None = None
    relationship_to_searcher: str
    status: str = "missing"
    age: int | None = None
    last_seen_location: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _coerce_full_name_to_name(cls, data: Any) -> Any:
        """Gemma sometimes emits 'full_name' instead of 'name' in nested
        family_members objects, mirroring the outer schema's field name.
        Remap before validation so both keys are accepted.
        """
        if isinstance(data, dict) and "name" not in data and "full_name" in data:
            data = {**data, "name": data["full_name"]}
        return data


EXTRACT_INTAKE_FIELDS_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "extract_intake_fields",
        "description": (
            "Extract intake fields from the speaker's statement about one or "
            "more missing persons. The speaker is always the searcher — never "
            "a missing person. full_name is the primary missing-person target "
            "(whoever the speaker names first or emphasizes most). "
            "family_members must list EVERY missing person the speaker names, "
            "including whoever is in full_name. Each turn may carry only some "
            "fields; emit null (not an empty string, not a guess) for any "
            "field not explicitly stated in this utterance."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "full_name": {
                    "type": ["string", "null"],
                    "description": (
                        "Full name of the missing person; null if not stated "
                        "in this utterance."
                    ),
                },
                "relationship": {
                    "type": ["string", "null"],
                    "description": (
                        "Speaker's relationship to the missing person "
                        "(e.g., 'son', 'daughter', 'hijo', 'hija', "
                        "'ابن', 'پسر'); null if not stated."
                    ),
                },
                "age": {
                    "type": ["integer", "null"],
                    "description": (
                        "Age of the SEARCHER (the person speaking), not the age "
                        "of any family member they mention. Null if the searcher "
                        "did not state their own age."
                    ),
                },
                "last_seen_location": {
                    "type": ["string", "null"],
                    "description": (
                        "Where the speaker last saw the missing person "
                        "(e.g., 'Tapachula bus terminal', 'border with "
                        "Colombia', 'el cruce de la frontera', "
                        "'البوابة الجنوبية', 'مخيم الزعتري'); null if not "
                        "stated. Preserve the speaker's source language."
                    ),
                },
                "last_seen_date": {
                    "type": ["string", "null"],
                    "description": (
                        "When the speaker last saw the missing person, as "
                        "stated (e.g., 'two weeks ago', 'hace dos semanas', "
                        "'last Tuesday'); null if not stated. Preserve the "
                        "speaker's phrasing — do not normalize to a date."
                    ),
                },
                "distinguishing_features": {
                    "type": ["string", "null"],
                    "description": (
                        "Any distinguishing physical features the speaker "
                        "mentions (scars, marks, what they were wearing, "
                        "approximate height, hair color, etc.); null if not "
                        "stated. Preserve the speaker's source language."
                    ),
                },
                "searcher_name": {
                    "type": ["string", "null"],
                    "description": (
                        "Name of the person speaking (the searcher), in the "
                        "source script as stated. Null if the speaker did not "
                        "state their own name in this utterance."
                    ),
                },
                "searcher_name_transliteration": {
                    "type": ["string", "null"],
                    "description": (
                        "Latin-script transliteration of searcher_name when "
                        "the source language uses a non-Latin script (Arabic, "
                        "Farsi). Null for Latin-script languages and when not "
                        "stated."
                    ),
                },
                "searcher_relationship_to_target": {
                    "type": ["string", "null"],
                    "description": (
                        "The searcher's relationship to the missing person "
                        "(e.g., 'mother', 'uncle', 'أم', 'مادر'). Null if "
                        "not stated."
                    ),
                },
                "family_members": {
                    "type": ["array", "null"],
                    "description": (
                        "ALL missing persons the speaker names, including "
                        "whoever is in full_name. Example: if the speaker "
                        "says 'I am looking for my brother Yusuf and my son "
                        "Mohamad (age 8)', then full_name='يوسف' AND "
                        "family_members must contain both يوسف (brother, "
                        "missing) AND محمد (son, missing, age 8). Emit null "
                        "(not an empty array) only when the speaker names "
                        "zero missing persons by name."
                    ),
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {
                                "type": "string",
                                "description": "Name in source script.",
                            },
                            "name_transliteration": {
                                "type": "string",
                                "description": (
                                    "Latin transliteration for non-Latin "
                                    "source scripts."
                                ),
                            },
                            "relationship_to_searcher": {
                                "type": "string",
                                "description": (
                                    "This member's relationship to the "
                                    "speaker ('daughter', 'brother', etc.)."
                                ),
                            },
                            "status": {
                                "type": "string",
                                "enum": ["missing", "known", "present"],
                                "description": (
                                    "Whether this member is missing, known "
                                    "to be safe, or present with the "
                                    "searcher. Detect from context: "
                                    "'is with me' / 'معي' / 'still with me' "
                                    "/ 'هو معي' / 'is here with us' / "
                                    "'are still safe' → 'present'. "
                                    "'is missing' / 'مفقود' / "
                                    "'I am looking for' → 'missing'. "
                                    "Default if unstated: 'missing'."
                                ),
                            },
                            "age": {
                                "type": ["integer", "null"],
                                "description": (
                                    "Age of THIS family member as stated by the "
                                    "searcher. Extract from phrases like 'عمره 8 "
                                    "سنوات' (he is 8 years old) or 'age 8' when "
                                    "the searcher states a family member's age. "
                                    "Null if not stated for this member."
                                ),
                            },
                            "last_seen_location": {
                                "type": "string",
                                "description": (
                                    "Where last seen, in source language."
                                ),
                            },
                        },
                        "required": ["name", "relationship_to_searcher"],
                    },
                },
            },
            # Nothing required: progressive extend turns may carry only a
            # subset of fields. Storage's no-op detection handles unchanged
            # values; the pipeline's empty-filter on extend drops None /
            # empty so existing data isn't clobbered.
            "required": [],
        },
    },
}


class ExtractIntakeFieldsArgs(BaseModel):
    """Validates raw arguments dict from extract_intake_fields tool calls.

    Used by S4 ingest_audio() to validate ToolCallResult.arguments
    before mapping to IntakeRecord fields per the discrepancy #3
    rule: full_name → full_name_source_script (always) and
    full_name_transliteration (only for Latin-script source langs).

    extra='ignore' so future tool-schema additions don't break
    consumers that still validate against the older shape.
    """

    model_config = ConfigDict(extra="ignore")

    full_name: str | None = None
    relationship: str | None = None
    age: int | None = None
    last_seen_location: str | None = None
    last_seen_date: str | None = None
    distinguishing_features: str | None = None
    searcher_name: str | None = None
    searcher_name_transliteration: str | None = None
    searcher_relationship_to_target: str | None = None
    family_members: list[FamilyMemberArg] | None = None
