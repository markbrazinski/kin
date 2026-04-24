# Three Hypothesis Tests — 20260423_082052

Model: `gemma4:e2b`  Temperature: `0.1`  Runs per case: `3`  Wall-clock cap: `45s`

## Test 1 — English-output translation hypothesis

Prompt asked for English-only output and person-extraction. 'Respected English only' column: mechanical check — does the model output contain non-ASCII characters from the source script (Cyrillic / Bengali / diacritic-heavy French)?

| Language | Run | Latency (s) | Outcome | English translation | Respected English only? | My read |
|---|---|---|---|---|---|---|
| french | 1 | 11.26 | ok | NO_PERSON_MENTIONED | yes |  |
| french | 2 | 6.33 | ok | NO_PERSON_MENTIONED | yes |  |
| french | 3 | 9.40 | ok | [empty] | yes |  |
| ukrainian | 1 | 7.16 | ok | 1. refused to search 2. NO_PERSON_MENTIONED | yes |  |
| ukrainian | 2 | 7.81 | ok | 1. they refused to search 2. NO_PERSON_MENTIONED | yes |  |
| ukrainian | 3 | 6.32 | ok | 1. they refused to search 2. NO_PERSON_MENTIONED | yes |  |
| bengali | 1 | 7.50 | ok | NO_PERSON_MENTIONED | yes |  |
| bengali | 2 | 8.54 | ok | NO_PERSON_MENTIONED | yes |  |
| bengali | 3 | 6.66 | ok | NO_PERSON_MENTIONED | yes |  |
| portuguese | 1 | 11.10 | ok | [empty] | yes |  |
| portuguese | 2 | 9.87 | ok | [empty] | yes |  |
| portuguese | 3 | 8.54 | ok | 1. the structures 2. NO_PERSON_MENTIONED | yes |  |

## Test 2 — Ukrainian conversational retest

Standard transcription+translation prompt, on ukrainian_01.wav (Common Voice conversational clip).

| Clip | Run | Latency (s) | Outcome | Output | My read |
|---|---|---|---|---|---|
| ukrainian_01.wav | 1 | 9.59 | ok | ```json {   "transcription": "відповідно до згодом стали великоросами які згудом стали дали великоросами",   "english_translation": "according to later became large-headed ones which coincidentally gave large-headed ones" } ``` |  |
| ukrainian_01.wav | 2 | 8.08 | ok | ```json {   "transcription": "відповідно до згодом стали великоросами які згудом стали дали великоросами",   "english_translation": "according to later became large-headed ones which coincidentally gave large-headed ones" } ``` |  |
| ukrainian_01.wav | 3 | 8.09 | ok | ```json {   "transcription": "згудом стали великоросами. які згудом стали великоросами.",   "english_translation": "they became large ones. which became large ones." } ``` |  |

## Test 3 — Farsi and Amharic baseline

Standard prompt, FLEURS clips (fa_ir, am_et).

| Language | Run | Latency (s) | Outcome | Output | My read |
|---|---|---|---|---|---|
| farsi | 1 | 10.30 | ok | ```json {   "transcription": "دستورهای حکومتی |  |
| farsi | 2 | 8.34 | ok | ```json {   "transcription": "در ماه اکتبر آغاز شد. درخواست گذاشت بود.",   "english_translation": "It started in the month of October. He had placed a request." } ``` |  |
| farsi | 3 | 9.80 | ok | ```json {   "transcription": "در ماه اکتبر آغاز شود. درخواست کرده بود. اظهارات گسترده حکومتی بود. |  |
| amharic | 1 | 10.03 | ok | [empty] |  |
| amharic | 2 | 9.45 | ok | ```json {   "transcription": "༄༅།།བཀའ་འགོད་བྱ་བ་འདི་ལྟར་ |  |
| amharic | 3 | 9.90 | ok | ```json {   "transcription": "༄༅།།བཀའ་འགོད་བསྒྲུབ་པའི་སྐབས་སུ་བསམ་བློ་གཏོང་བ་དང་། འདི་ནི་བསམ་བློ་གཏོང་བ་དང་། འདི་ནི་བསམ་བློ་གཏོང་བ་དང་། འདི་ནི་བསམ་བློ་གཏོང་བ་དང་ |  |

## Key findings (mechanical only)

- Total probes attempted: 21
- Wall-clock timeouts: 0
- Exceptions: 0
- Empty responses: 4
- Missing clips (skipped): 0
- Latency range: min=6.32s  max=11.26s  median=8.54s
- Test 1 "respected English only" check: 12/12 outputs were pure-ASCII

