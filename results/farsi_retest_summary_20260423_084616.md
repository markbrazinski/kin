# Farsi Retest — 20260423_084616

Model: `gemma4:e2b`  Temperature: `0.1`  num_predict: **1500** (prior Test 3 cap was 400)  Wall-clock cap: `30s`  Audio: `farsi_01.wav`

## Retest runs (num_predict=1500)

| Run | Latency (s) | Completed? | Transcription (Persian) | English translation | My read |
|---|---|---|---|---|---|
| 1 | 17.22 | natural EOS | در ماه اکتبر آغاز شد. درخواست گزارش شده بود. | It started in the month of October. The request had been reported. |  |
| 2 | 8.46 | natural EOS | دستورات حکومتی ارائه شده بود. این خواسته‌گذاری بلند مدت بود. | Government instructions were provided. This was a long-term demand. |  |
| 3 | 11.24 | natural EOS | اقتراح شده بود. درخواست کرده بود. این درخواست بوده است. در ماه اکتبر آغاز شود. | It was suggested. He/she had requested. This was the request. Let it begin in October. |  |

## Original Test 3 Farsi runs (num_predict=400) — for continuity

| File | Latency (s) | Outcome | done_reason | Raw content |
|---|---|---|---|---|
| test3_farsi_run1_20260423_081954.json | 10.30 | ok | length | ```json {   "transcription": "دستورهای حکومتی |
| test3_farsi_run2_20260423_082005.json | 8.34 | ok | stop | ```json {   "transcription": "در ماه اکتبر آغاز شد. درخواست گذاشت بود.",   "english_translation": "It started in the month of October. He had placed a request." } ``` |
| test3_farsi_run3_20260423_082013.json | 9.80 | ok | length | ```json {   "transcription": "در ماه اکتبر آغاز شود. درخواست کرده بود. اظهارات گسترده حکومتی بود. |

## Mechanical observations

- Total retest runs: 3
- Completed = "natural EOS": 3/3
- Wall-clock timeouts (30s): 0/3
- Latency range: min=8.46s  max=17.22s
- Distinct transcriptions across 3 non-empty runs: 3
