# Worker Ground-Truth Portal Actual-Footage Rehearsal Receipt

Date: 2026-07-25

Status: **REHEARSAL EVIDENCE ONLY - NOT TIER B TRUTH**

## Source

Local-only source root:
`/Users/thomas/FactoryVisionArtifacts/worker_days/20260709/gate-line/segments`

The selected sequence is 15 consecutive MKV segments from 12:08 through 12:22
on 2026-07-09. `ffprobe` measured 900.134 seconds in total. Raw footage was not
copied into Git.

| Segment | Seconds | SHA-256 |
| --- | ---: | --- |
| `20260709T120800_gate-line_20260709.mkv` | 60.001 | `cac1b9796d394be78c54553d9d1c520aa984f6d03c354d04d62b703b0ed4376c` |
| `20260709T120858_gate-line_20260709.mkv` | 59.984 | `65faea5f8f45a45ed8830db68a0eec687e2ae283119597231395d160d76e7203` |
| `20260709T120958_gate-line_20260709.mkv` | 59.983 | `2189cb63c02ddf7c356423b85c5b77683d57880d188dd47b4ab70fbfbcb9eabb` |
| `20260709T121058_gate-line_20260709.mkv` | 59.967 | `cf909deda41eb4e8a9f8a81cc7c1962122d356280aed290ccc5eb46a70804bc1` |
| `20260709T121158_gate-line_20260709.mkv` | 60.035 | `390c7e2c925d6e4b9d9799ca72494e593106aed7fff0ae1ea34f25d64fee94e9` |
| `20260709T121258_gate-line_20260709.mkv` | 60.033 | `1c042834a7ef9ada5013624b9123c4575863c6a9af4481db27149c17ba43b0dd` |
| `20260709T121358_gate-line_20260709.mkv` | 60.034 | `f39d1f779a29bd9ff84ce93065ec8a90813a947fd5988f0f83c417ef4610b559` |
| `20260709T121458_gate-line_20260709.mkv` | 60.082 | `0ea83dfc88d45cc9a73df731401e9696953ad8d05a3122dc88f07450f382db6a` |
| `20260709T121559_gate-line_20260709.mkv` | 59.965 | `722557092b28e9093aa48a82dafdd10a5b958e026c97392d3b4c56ba96264b16` |
| `20260709T121658_gate-line_20260709.mkv` | 59.998 | `5343401207f4be63bc32326e0c159baded332ad1fe3e6db193214c75c5b61844` |
| `20260709T121758_gate-line_20260709.mkv` | 59.997 | `75b1c1c2d45c7f39863f4d75d6e4ba3d2f5de1d219d362c3238419fbc9b4de72` |
| `20260709T121859_gate-line_20260709.mkv` | 60.008 | `5bca5476fd0409368a45bfd7a73d57deecfebaad8091d0186b5ef282067d3e8e` |
| `20260709T121959_gate-line_20260709.mkv` | 60.000 | `c196dff89d2acbc220cc9864fba285a4b88a6a7517c90fa48229c844ab9854f1` |
| `20260709T122059_gate-line_20260709.mkv` | 60.028 | `8a6027c35179abc9a5ede6a35a29cc4e9e7a0af859269f23e0c4a2aa65ca16f9` |
| `20260709T122159_gate-line_20260709.mkv` | 60.019 | `c37e5d9c0e982ab6f9efe3ad7a601331eabc5873cda643aaf5828b0119e3a249` |

## What Was Verified

- The production-built `/review` surface loaded real factory footage on desktop
  and at 390x844.
- The mobile video reached browser `readyState=4`; the Spanish `+1 PIEZA`
  control rendered; document width remained below viewport width; and browser
  warning/error logs were empty.
- Representative frames from the July sequence showed the same fixed gate-line
  station and appeared suitable for a low-activity or zero-output rehearsal.

## What Was Not Verified

- Factory permission to use this sequence for reviewer work.
- Filmed-worker notice, consent, legal basis, or cross-border transfer terms.
- Three independent human labels, adjudication, or reconciled truth.
- Event timestamps, zero-output truth, worker comprehension, handle time,
  frame-drop rate, or AI accuracy.

This sequence must not enter practice, qualification, calibration, training,
or evaluation registries until permission and source-set role are explicitly
approved. Visual inspection is not a label and is not Tier B evidence.
