# FactoryVision Worker Ground-Truth Portal v1

Status: implementation-ready product specification  
Date: 2026-07-25  
Owner: FactoryVision / Pennies & Inches  
Primary surface: `/review`  
Related surfaces: `/ops`, owner count publication  
Design contract: `DESIGN.md` and `docs/design/fv-live-a-approved.png`

Review status: revised after an independent Fable unknown-unknowns pass. See
`worker_ground_truth_portal_v1_fable_review.md`.

## 1. Plain-English Summary

FactoryVision needs a secure work portal where remote reviewers count completed
factory output in 15-minute video chunks.

Each chunk is reviewed independently by three people. Every press of the count
button creates a timestamped placement label. The system compares the three
submissions, resolves straightforward agreement automatically, and sends every
pilot disagreement to an internal adjudicator. Factory owners see only resolved
counts. FactoryVision staff can see queue health, reviewer quality, disputes,
and a blind comparison between the human result and the AI result.

This portal does not control the appliance's live AI counter. It is a delayed
ground-truth, verification, audit, and training system. The edge appliance must
continue counting when the portal, internet, or reviewers are unavailable.

## 2. Why This Exists

The current `/review` experience proves the basic interaction: play a chunk at
high speed, press one large button per completed piece, review timestamps, and
confirm. It is a useful demo, not a production review system.

Current implementation evidence:

- `console/components/review/review-tally-console.tsx:74` hardcodes one
  `live-session` reviewer.
- `console/app/api/review/chunks/next/route.ts:9` accepts reviewer identity from
  a query parameter.
- `console/app/api/review/chunks/[id]/confirm/route.ts:25` accepts reviewer
  identity from the request body.
- `console/lib/reviewStore.ts:45-67` stores work in process memory.
- `console/lib/reviewStore.ts:128-135` marks a chunk processed after one
  submission.
- `console/lib/reviewStore.ts:113-153` uses a global idempotency map that can be
  overwritten by a colliding key from another reviewer.
- The checkpoint-zero amendment removed hidden-golden metadata, peer-count
  projection, global queue depth, and reviewer-throughput fields from current
  worker API responses and UI. Durable domain replacement is still required.
- `console/lib/reviewChunks.ts:50-53` hardcodes demo day and `-07:00` source
  offset instead of factory timezone rules.
- `console/lib/reviewChunks.ts:143-169` assumes rendition time equals source
  time and derives event IDs from array order; padding, undo, and three reviewers
  make both assumptions invalid.
- `console/prisma/schema.prisma` uses a single-factory SQLite demo schema and
  does not model independent assignments, submissions, consensus, or
  adjudication.

The production portal must replace those assumptions without discarding the
speed and clarity of the existing tally interaction.

## 3. Product Doctrine And Authority

### 3.1 Two separate count products

FactoryVision has two related but separate count streams:

1. **Runtime AI count**: produced on the factory appliance from ordered camera
   frames. This remains the live operational count authority defined by the
   numbered repo docs and architecture decision records.
2. **Resolved human ground truth**: produced later by this portal from recorded
   chunks. This is the authoritative verified dataset for audit, evaluation,
   training, and the delayed verified owner count.

The UI and API must name these streams honestly. A human result must not be
presented as real-time. An AI result must not be presented as human verified.

### 3.2 Non-negotiable boundaries

- The portal is never in the live appliance increment path.
- An internet outage never stops the edge appliance from counting or recording.
- Human, AI, and owner-published events remain distinct records with lineage.
- AI results are hidden from reviewers and adjudicators until the human result
  is final during the pilot.
- Raw reviewer submissions are immutable after final submission.
- Owners see only resolved consensus/adjudicated events, never individual
  reviewer identities or unresolved votes.
- No footage leaves the approved local or cloud boundary without explicit
  factory authorization.
- Track B exam-firewall intervals are excluded server-side from review and
  training queues. An exam-firewall interval is a source-hash and source-time
  range registered under `validation/exam/` as held-out evaluation evidence.
  Every training extractor, labeler, and trainer consumes that registry; a
  training manifest without a verified source SHA-256, UTC visible interval,
  and declared complete transitive lineage fails closed. Filenames and caller
  eligibility flags are not firewall evidence.
  Assignment, rendition, and export services must consume both the exam
  firewall and source-set registries directly when those services are
  implemented. Every declared source-set window is blocked from ordinary
  production assignment/export with a provisional 60-second guard band;
  real-footage similarity measurement may widen but never silently shrink it.

This spec does not change count authority, cloud/offline posture, or teacher
roles in the live runtime. Any implementation that changes those boundaries
requires a new architecture decision record.

## 4. Pilot Scope

### 4.1 Included

- One factory.
- Two stations/cameras.
- Three distinct primary reviews per chunk. The eligible reviewer pool is sized
  from measured p95 handle time and absence/fourth-review demand; five qualified
  reviewers is the minimum planning floor, not a pre-measurement staffing claim.
- FactoryVision ops and adjudicator access.
- Spanish-first reviewer UI with English toggle.
- A single daily-work experience that requires no factory, camera, date, or
  video-file selection.
- Automatic arrival of newly ready 15-minute work without a browser refresh.
- Fifteen-minute source chunks.
- Playback at 1x, 2x, and 5x. Shipped 10x and 15x controls remain gated off
  until the real-footage/device safety criteria in section 6.5 pass.
- Three blind primary reviews per chunk.
- Automatic exact agreement and event matching.
- Internal adjudication for every pilot disagreement.
- Post-hoc audited production chunks and explicit qualification clips for
  reviewer quality measurement; no hidden replay with falsified timestamps.
- Blind AI-versus-human comparison after human resolution.
- Delayed publication of resolved counts to the owner console.
- Private cloud media delivery approved for the pilot factory.

### 4.2 Excluded

- Reviewer recruiting, contracts, payroll, and tax handling.
- Native mobile applications.
- Public signup.
- Reviewer-to-reviewer messaging.
- Owner access to worker performance data.
- AI participation in human consensus.
- AI model promotion or self-training.
- Sub-15-minute verified count latency.
- Multi-region active-active infrastructure.
- A configurable adjudication threshold editor.

## 5. Users, Roles, And Permissions

| Role | Authentication | May access |
| --- | --- | --- |
| Reviewer | Invite-only account, magic-link enrollment plus required TOTP MFA before production work | Assigned chunk media, own in-progress work, own daily progress |
| Adjudicator | FactoryVision Google Workspace SSO plus MFA | Disputed chunks, three anonymized submissions, evidence clips; no AI result for any open case |
| Ops | FactoryVision Google Workspace SSO plus MFA | Queue and reviewer-health metadata plus audit logs; no adjudication and no AI event/comparison reads |
| AI analyst | FactoryVision Google Workspace SSO plus MFA | AI comparison only after the human-result embargo clears |
| Factory owner | Existing owner authentication | Resolved counts and evidence permitted by factory policy |
| Service worker | Short-lived workload identity | Ingest, transcode, assign, resolve, publish, retention jobs |

Authorization is server-derived. APIs must ignore or reject a client-supplied
`reviewerId`, `factoryId`, role, or membership claim.

Every domain row carries `factory_id`. Database row-level security and
application authorization both enforce membership. A reviewer can read only:

- the assignment currently leased to that reviewer;
- media access minted for that assignment;
- that reviewer's draft/submission;
- aggregate personal progress that cannot reveal peer answers.

Reference-answer rows live in a private server-only schema or service database
role.
No worker response may include `is_golden`, an expected count, expected event
times, peer counts, AI counts, consensus state, or dispute state.

Adjudicator and AI-analyst permissions are mutually exclusive during the pilot.
An account eligible to adjudicate cannot read AI runs, AI events, or comparison
data for any chunk, including a resolved chunk that an owner dispute could
reopen. The embargo is enforced in the database/API, not only by hiding UI.

Capabilities, rather than page names, are authoritative:

| Capability | Reviewer | Ops | Adjudicator | AI analyst |
| --- | ---: | ---: | ---: | ---: |
| Lease/tally assigned work | yes | no | no | no |
| Read queue and worker-health metadata | no | yes | no | no |
| Read primary submissions for a dispute | no | no | yes | no |
| Resolve/adjudicate a chunk | no | no | yes | no |
| Read AI events/comparisons | no | no | no | only after `human_final_at` |

No account may hold both `adjudicate` and `read_ai_comparison` during the pilot.

## 6. End-To-End Workflow

### 6.0 The reviewer's workday

The reviewer experience must feel like a simple work inbox, not factory
software. A first-time Spanish-speaking worker must reach guided practice within
5 minutes of opening the invite and begin a real assignment within 15 minutes,
including authentication, TOTP enrollment, walkthrough, practice, and
qualification, without live assistance.

Pilot devices have an approved authenticator installed before timed onboarding.
The five-minute target includes linking the preinstalled authenticator and
entering TOTP, not app-store acquisition. A missing or incompatible
authenticator blocks the timing attempt and routes to ops device provisioning;
the worker is not penalized and no five-minute claim is recorded for that
attempt.

The normal day is:

1. Open the invite link and authenticate by magic link.
2. Enroll TOTP MFA on first use and verify one code.
3. Land on `Trabajo de hoy` with one large action:
   `Continuar video` when work is in progress, `Comenzar siguiente video` when
   work is ready, or `No hay videos listos` when the queue is empty.
4. Open the assigned 15-minute chunk. The screen says what to count in one short
   sentence, shows the station alias and source-time range, and presents only
   the video, speed controls, running total, `+1`, undo, and problem action.
5. Reach the end, inspect the reviewer's own timestamps, and confirm.
6. See a brief saved confirmation. The next assignment opens automatically when
   one is ready.
7. Finish the day with completed-today count, time worked, and an honest message
   saying whether more work is currently waiting.

The daily-work header contains only:

- current state: working, work ready, waiting, or done for today;
- completed chunks today;
- whether personal work is ready, without a global queue count, peer timing,
  peer answers, or pre-leased footage details;
- connection and save status;
- Spanish/English control;
- account/help menu.

Workers never browse factories, cameras, storage buckets, dates, files, AI
results, or other reviewers. They never decide which chunk to take next. The
assignment service makes that decision and the UI always presents one obvious
next action.

#### Automatic work arrival

Every camera closes a canonical chunk at each 15-minute boundary. That chunk
does not appear to a reviewer until upload, integrity validation, transcoding,
the configured delay, and assignment checks succeed. When it becomes eligible:

- the assignment service places it into the blind reviewer pool automatically;
- a connected idle worker receives a `work_ready` event and sees
  `Nuevo video listo` within 10 seconds without refreshing;
- a worker already reviewing footage is never interrupted or switched to a new
  video; the new assignment waits behind the current work;
- after confirmation, the next assignment shell and poster may be prefetched and
  it opens within 2 seconds when network conditions permit;
- if no assignment is ready, the waiting screen remains open and updates
  automatically through SSE or a WebSocket, with bounded polling as fallback;
- if the worker is logged out, the work is waiting on the next login;
- an optional sound/browser notification may say only that work is ready and
  must not reveal factory, station, or footage details.

The worker does not need to understand upload, consensus, AI, or the 60-minute
delay. The development locale is neutral Latin American Spanish (`es-419`);
country-specific legal and comprehension approval remains a Tier C launch gate.
The provisional time format is 24-hour: `Este video cubre de 14:00 a 14:15`.

The canonical countable event is:

```text
English: Count one piece on the first frame where the worker has released the
finished piece and it remains in the designated output area.

Spanish (es-419): Cuenta una pieza terminada en el primer cuadro en que el
trabajador la suelta y la pieza queda en el área de salida indicada.
```

Station setup may replace `piece` and `output area` with approved local nouns,
but it may not change the release-and-remains frame anchor. The bilingual event
definition and station-specific nouns live in a versioned translation contract.
Reference annotations use the same frame anchor.

#### First-run training

Before real assignments, a reviewer completes:

- a 60-second Spanish walkthrough with a real example of a countable placement;
- one 90-second curated guided practice clip with visible coaching;
- one 90-second curated uncoached qualification clip;
- a plain explanation of undo, problem reporting, saving, and what happens when
  the connection drops.

The reviewer cannot enter production work until the qualification chunk meets
the approved event-level standard. Failed qualification returns the worker to
practice and alerts ops; it does not expose the correct answer in a reusable
production payload.

### 6.0.1 Reviewer UX rules

- Spanish is selected from the reviewer profile and is the default; English is
  always available.
- Spanish copy uses short, neutral Latin American wording reviewed by native
  speakers from the worker population. Avoid regional slang and technical terms.
- One screen has one primary action. Secondary actions never visually compete
  with `+1`, `Confirmar`, or `Comenzar siguiente video`.
- Instructions describe the physical event to count with a real example, not
  model terminology such as detection, inference, or consensus.
- Large controls, visible focus, keyboard support, icon-plus-text labels, and
  non-color status cues are required.
- The full tally workflow fits a 1366x768 low-cost laptop without hiding the
  video, tally, or confirm action below an unexpected scroll boundary.
- Draft saving is automatic. `Guardado`, `Guardando`, and `Sin conexión` states
  are always understandable; the worker never has to press a save button.
- Loading, no-work, expired-lease, lost-connection, video-failed, and submitted
  states each provide one clear recovery action.
- Session metrics do not create pressure to click faster. Quality and careful
  completion are the worker-facing priority.
- No owner financials, production targets, customer names, peer performance, or
  internal quality score appears in the reviewer UI.

### 6.1 Edge recording and upload

1. The edge recorder writes continuous source segments locally.
2. A chunk manifest closes each 15-minute interval using the factory's local
   timezone and records source-clock boundaries.
3. The edge retains the source until remote upload integrity is confirmed.
4. An opt-in uploader sends encrypted media and metadata to private object
   storage without blocking the runtime counter.
5. The ingest service verifies object size, SHA-256, duration, decodability,
   monotonic timestamps, and station ownership.
6. The transcode service creates review renditions and a poster.
7. A chunk becomes `ready` only after integrity and policy checks pass.

Upload is resumable and idempotent. The same source hash plus station and source
interval may not create duplicate chunks.

### 6.2 Chunk timing

- Nominal chunk length: 15 minutes.
- Boundaries use factory-local quarter hours, stored as UTC instants plus the
  factory timezone.
- Canonical event ownership uses half-open intervals: `[start_at, end_at)`. A
  placement belongs to the chunk containing the frame-anchored release-and-
  remains event defined in section 6.0.
- Each rendition includes 5 seconds of read-only context before and after the
  canonical interval when source footage exists. The UI shades context and
  disables tally input there. An event exactly at `end_at` belongs to the next
  chunk.
- Rendition padding is clipped at exam-firewall and protected-source boundaries.
  Protected-source boundaries include every resolver-calibration,
  AI-evaluation-holdout, practice, and qualification interval declared in the
  source-set registry. Ordinary production assignments and exports maintain a
  provisional 60-second guard band around every protected set. Different source
  sets maintain at least the full context duration between visible intervals
  unless presentation is clipped.
  Assignment eligibility is evaluated against the complete visible rendition
  interval, including context, not only the canonical chunk interval.
  Source registrations and assignments declare the full transitive ancestry
  hash set. A missing or partial-lineage declaration fails closed rather than
  relying on single-hop hash matching.
- Leading context copy is
  `Contexto del video anterior. No cuentes aquí.` Trailing context copy is
  `Contexto del siguiente video. No cuentes aquí.` The count button remains
  visible but disabled, with the reason exposed to assistive technology.
- The resolver performs an adjacent-chunk seam check before publication. Events
  inside 2 seconds of a seam are compared across both chunks and may produce
  exactly one owner-published event. An ambiguous seam enters adjudication.
- DST transitions, camera clock changes, discontinuities, and missing footage
  create explicit gap metadata. They must never silently stretch or compress the
  source timeline.
- A chunk with more than 10 seconds of unexplained timestamp discontinuity,
  undecodable footage, or missing source provenance is quarantined for ops.
- Review eligibility begins 60 minutes after the chunk end by default.
- Target resolved publication: 60-90 minutes after source time when capacity is
  healthy.

The transcode pipeline must preserve a tested rendition-to-source-time mapping.
Burned-timecode fixtures, including variable-frame-rate and discontinuous input,
must demonstrate mapping error below 250 ms before reviewer-tolerance
calibration begins. After the event-alignment tolerance is measured, the
mapping test is rerun against `min(250 ms, 20 percent of the accepted
tolerance)`; failure invalidates the calibration and blocks that rendition.

### 6.3 Assignment

Each eligible chunk creates three primary `review_assignment` rows.

Assignment rules:

- three distinct active reviewers;
- no reviewer receives the same chunk more than once;
- a reviewer does not receive an adjudication task for a chunk they reviewed;
- assignment ordering is oldest eligible first, with station coverage balancing;
- quality sampling is selected after normal production submission so reviewers
  cannot know which current chunk will be audited;
- exam-firewall intervals are never assigned;
- peers cannot infer which worker has or completed the same chunk.

Three is the number of reviews, not the entire eligible roster. The pilot
starts capacity planning at five qualified reviewers, but the final roster is
set only after real-footage p95 handle time, absence coverage, disagreement
rate, and fourth-review demand are measured. The adjudicator is separate. If
fewer than three distinct reviewers are available, the chunk waits and
backlog/verified-through time becomes visible; the system does not silently
publish a two-review result.

Qualification clips are explicit non-publishing exercises with synthetic
session time and no owner-count path. Production quality references are created
only by independent post-hoc audits of real, normally displayed chunks. The
original source time is always shown and retained; no replay is disguised as
current work.

The API returns one active assignment, not a selectable queue. The day view may
show personal completed/pending units but cannot expose station/time identifiers
for work not yet leased when that would enable collusion or answer sharing.

### 6.4 Lease and heartbeat

- Initial lease: 15 minutes.
- Client heartbeat: every 30 seconds while the page is visible and connected.
- Server extends the lease to 15 minutes from the latest accepted heartbeat.
- Two failed heartbeats display a connection warning and persist the draft.
- A hidden/background tab does not lose the lease immediately; the server grants
  a 5-minute recovery window after expiry before reassignment.
- An assignment is never simultaneously active for two reviewers.
- Reassignment uses a new assignment attempt while preserving the abandoned
  attempt and its audit history.
- A prefetched next-assignment shell does not start a lease. The lease starts in
  one server transaction when the reviewer opens the assignment. Prefetch may
  obtain only the poster and metadata; full media authorization requires the
  opened lease.

Closing a browser, losing power, or changing devices must not erase server-saved
draft clicks. The reviewer may resume an unexpired or recoverable assignment.

### 6.5 Reviewer tally experience

The first screen after login is the work surface, not a dashboard.

Header:

- FactoryVision wordmark.
- Station alias and source time range.
- Honest lag behind source time.
- Personal chunks completed today.
- Spanish/English control.
- Connection and draft-save status.

Video:

- Clean 16:9 or source-aspect playback.
- Speed controls: 1x, 2x, and 5x. The 10x and 15x controls are present only for
  a device/rendition class whose Tier B safety gate in section 6.5 has passed.
- Play/pause.
- Back 10 source seconds.
- Timeline with the reviewer's own click markers.
- Visible missing-footage regions.
- No owner names, sensitive job details, AI events, peer events, or reference
  answer state.

Primary controls:

- One large Spanish-first `+1 PIEZA` button (`+1 COUNT` after the worker
  explicitly switches to English). The approved station noun may replace
  `PIEZA`.
- Spacebar performs the same action.
- Undo removes only the latest unsubmitted click.
- `Z` performs undo.
- The summary allows any unsubmitted click to be replayed, moved, or deleted.
  Every draft edit remains in an append-only draft-action log even though only
  the final active events enter the submission.
- A problem menu reports: video will not play, view blocked, timestamp jump,
  wrong station, no usable footage, or other.

Each click immediately writes or upserts a server draft event with:

- stable client-generated click UUID;
- assignment ID;
- source video time in milliseconds;
- source wall-clock time derived server-side;
- current playback rate;
- browser monotonic click time;
- a per-page monotonic epoch UUID so reloads cannot merge unrelated monotonic
  clocks;
- server receipt time;
- client app version;
- media rendition ID.

The server must not trust a client-supplied wall-clock event time.

The browser also writes each draft action to IndexedDB before attempting the
server upsert. Reconnect reconciliation uses the stable action UUID and server
version to suppress duplicates. Clearing browser storage is never the only
recovery path after a server-acknowledged draft.

The client also reports playback health using
`HTMLVideoElement.getVideoPlaybackQuality()` where available: total frames,
dropped frames, current source position, buffered ranges, playback rate, and
stall duration. This telemetry is untrusted operational evidence, not proof of
attention.

The pilot starts with 5x as the maximum production speed. A device/rendition
class may expose 10x or 15x only after a reference-event test on the real worker
hardware and network shows:

- zero missed events in at least 200 representative reference events;
- p95 dropped-frame ratio under 1 percent;
- rendition/source-time error within the bound in section 6.2.

The 200-event gate is a zero-miss safety screen, not evidence of a
0.5-percentage-point non-inferiority claim. Any finer comparison requires a
pre-registered power calculation and the resulting sample size. CI playback
tests are regression evidence only and cannot enable a production speed.

If playback health crosses its validated bound, the player automatically steps
down to the highest validated speed and records the reason.

### 6.6 Coverage and completion

Fast playback is allowed, but traversal telemetry cannot prove that a person
perceived the footage. It is unverified client telemetry used only as a
behavioral guardrail alongside post-hoc audits, playback-health checks, and
cross-account independence controls.

Coverage telemetry records contiguous watched ranges in source time. Seeking may
create gaps. Direct signed-object delivery means the control plane does not see
every byte-range request; the spec makes no server-corroboration claim. The
server enforces only a weak wall-clock sanity floor from lease-open to submit:
usable source duration divided by the maximum speed enabled for that assignment,
minus at most 5 seconds of startup tolerance. That floor is not proof of
attention. Final submission is allowed only when:

- at least 98 percent of usable source time has been traversed;
- every uncovered contiguous range is shorter than the measured minimum
  countable-event duration for that station; until measured, the limit is 250
  ms;
- the video reached the end or all usable ranges were explicitly traversed;
- draft persistence is current;
- the lease is valid or within the recovery transaction.

Ops can override a coverage block only by converting the assignment to a problem
submission. Ops cannot silently mark an incomplete tally as complete.

A client may still fabricate telemetry or screen content. Coverage is never used
as the sole fraud, quality, compensation, or termination signal.

### 6.7 End-of-chunk review and submission

The summary states the reviewer's count and lists each timestamp. Selecting a
timestamp replays a short self-check window. The reviewer may:

- confirm;
- return to edit;
- submit the chunk as a problem.

Final confirmation is an idempotent database transaction that:

1. validates identity, membership, assignment, lease, coverage, and payload;
2. freezes the submission;
3. writes append-only tally events;
4. records the media and app versions;
5. marks the assignment submitted;
6. queues resolution if all three primary submissions exist;
7. returns the next work unit.

No update endpoint edits a final event. A correction creates a superseding
submission or adjudication event with reason and actor.

### 6.8 Consensus

Consensus has two levels:

1. **Count agreement**: all three reviewers report the same total.
2. **Event agreement**: individual timestamped clicks can be aligned across
   submissions.

For the pilot:

- If all three totals match, the resolver aligns events by source time and
  creates one provisional consensus set.
- If any total differs, the whole chunk enters adjudication.
- If totals match but event alignment is ambiguous, the chunk enters
  adjudication.
- If an event group lies inside the seam window, both adjacent chunks must be
  resolved enough to run cross-chunk deduplication before owner publication,
  except for the terminal cases below.
- Any problem submission enters ops triage and does not count as agreement.
- Every owner dispute creates a new adjudication case; it never mutates the
  original resolved record.

Event alignment uses a configurable tolerance measured during pilot calibration,
not an assumed fixed value. The initial test candidate is plus or minus 1.5
source seconds. The tolerance is accepted only after measuring reviewer timing
error at each enabled speed against a resolver-calibration set. That set is
disjoint from AI evaluation holdouts.

Seam terminal rules:

- End of shift/day is an explicit closing seam. Available post-roll context is
  adjudicated if needed; the last chunk never waits for a nonexistent successor.
- If the successor is quarantined or absent beyond 30 minutes after its expected
  readiness time, seam evidence is adjudicated from available padded context and
  receives `seam_adjudicated` or `seam_unverifiable` provenance.
- No chunk remains indefinitely in `resolving` because of a missing seam partner.

The consensus result stores:

- the three source submission IDs;
- resolver version and parameters;
- matched event groups;
- unmatched events;
- confidence/status;
- generated timestamp;
- publication status.

For the first two pilot weeks, 20 percent of otherwise auto-resolved chunks are
selected for independent adjudicator audit, with at least 10 audited chunks per
active factory-day when volume permits. Selection is committed before any AI
reveal and is balanced over time across station, event density, speed, and
reviewer trio; it is not required to fill every cross-product stratum daily.
After at least 200 audited events with no repeated systematic miss, sampling may
fall to 5 percent.

One isolated error opens a quality review. Two errors of the same physical or
workflow class inside a rolling 200 audited-event window pause automatic
publication for the affected station. No percentage-rate threshold is enforced
before the sample floor is met.

`human_final_at` is set only after audit selection is committed and either:

- the chunk was not selected for audit; or
- its selected audit/adjudication is complete.

Owner publication always waits for `human_final_at`. Selected audits therefore
have a separate completion-latency cohort and are excluded from the provisional
90-minute non-audited target until real audit handle time is measured. No count
that can still be changed by a required audit is owner-visible.

Chunks whose publication depends on a successor seam result form a separate
latency cohort. Their structural floor includes the successor's readiness and
resolution time, so they are excluded from the provisional 90-minute
non-audited/non-seam target and reported separately.

Later owner disputes create a new immutable version and do not expose AI output
to the adjudicator.

### 6.9 Adjudication

The adjudicator sees:

- the chunk video;
- three anonymized timestamp tracks;
- event-group disagreements;
- coverage/problem metadata;
- no AI output ever, as required by the section 5 capability matrix.

The API denies AI data for open cases even when the same employee also performs
general ops work. The pilot uses separate adjudicator and AI-analyst accounts;
shared credentials are prohibited.

The adjudicator may add/remove/move events, mark footage unusable, or send the
chunk for a fresh fourth review. Every action requires a reason code. The
adjudicated event set becomes the resolved human result without erasing primary
submissions.

Pilot staffing must include a named daily adjudicator and a backup. Queue
capacity planning must include adjudication time; it is not assumed to be free.

### 6.10 Blind AI comparison

The AI pipeline writes a separate immutable run keyed by:

- chunk ID and source hash;
- model artifact hash;
- code/config version;
- inference parameters;
- event timestamps and confidences;
- run start/end time.

AI output is generated without human labels for that chunk and remains hidden
until `human_final_at` is set. A comparison job then calculates count error,
event precision/recall/F1, timing error, and disagreement classes.

AI output:

- does not break ties;
- does not change consensus;
- does not become gold truth;
- does not automatically enter training data;
- does not promote a model.

Training export is a separate, versioned, approval-gated operation that applies
the repo's gold/silver/bronze and holdout-leakage rules.

### 6.11 Owner publication

Only `resolved_human_count_event` records are published as delayed verified
counts. Owner UI copy must state the actual state, for example:

- `Verified through 2:15 PM`
- `Human verified, 74 minutes behind live`
- `6 resolved placements`

The owner UI must not say `100% HUMAN+AI`, `live verified`, or equivalent unless
both the data and latency actually support that statement.

The runtime AI count and delayed resolved count may be displayed together only
when clearly named, timestamped, and never silently substituted.

`Verified through` is the end of the latest contiguous source interval for which
every prior chunk has a terminal owner-publication status. A quarantined,
unusable, or seam-unverifiable chunk stops that contiguous frontier. The owner
surface must separately show:

- the exact unverified interval;
- unverified minutes;
- that placements in the interval are excluded from the verified total;
- later resolved intervals as `verified after a gap`, never by advancing the
  contiguous frontier across the hole.

## 7. Data Model

Production uses PostgreSQL. The existing SQLite Prisma schema remains a demo
fixture until migrated.

Required entities:

| Entity | Essential purpose |
| --- | --- |
| `factory` | Tenant, timezone, retention/privacy policy |
| `station` | Factory-owned camera/station identity |
| `membership` | User role and factory scope |
| `media_object` | Private object identity, hash, duration, retention state |
| `video_chunk` | Source interval, integrity, gap map, processing state |
| `media_rendition` | Review encoding and source-time mapping |
| `review_assignment` | One reviewer/chunk/round lease and status |
| `review_draft` | Recoverable click and coverage state |
| `review_submission` | Immutable final reviewer result |
| `tally_event` | Immutable source-time placement label |
| `reference_answer` | Server-only qualification/audit truth |
| `consensus_run` | Versioned resolver execution |
| `consensus_event` | Resolved event with submission lineage |
| `adjudication_case` | Disagreement lifecycle |
| `adjudication_action` | Append-only decision history |
| `ai_run` | Blind model execution provenance |
| `ai_event` | AI-only event |
| `resolved_human_count_event` | Owner-publishable human result |
| `audit_log` | Security and high-value domain actions |

Required constraints:

- unique source identity on `(factory_id, station_id, source_start_at,
  source_end_at, source_sha256)`;
- unique primary assignment on `(chunk_id, reviewer_id, review_round)`;
- no reviewer may have two submitted primary assignments for one chunk;
- unique idempotency key per authenticated actor and operation;
- unique tally click UUID per assignment;
- final submissions and tally events are append-only;
- every foreign reference is tenant-consistent;
- soft deletion never destroys audit or label lineage;
- all timestamps use `timestamptz`; factory timezone is stored separately;
- source-time milliseconds are integers, never browser-formatted strings.

`media_rendition` stores a versioned source-time mapping, encoding parameters,
frame-rate mode, frame count, duration, and mapping-validation result.
`video_chunk` stores canonical boundaries separately from padded rendition
boundaries. `consensus_event` stores seam-dedup lineage when adjacent chunks
contribute evidence.

State machines:

```text
video_chunk:
ingesting -> transcoding -> ready -> assigned -> resolving
          -> resolved -> published -> retained/deleted
          -> quarantined

review_assignment:
queued -> leased -> draft -> submitted
       -> expired/reassigned
       -> problem

adjudication_case:
open -> in_review -> resolved
     -> needs_fourth_review
     -> unusable
```

State changes occur through transactions with explicit allowed transitions.

## 8. Proposed Production Architecture

### 8.1 Control plane

- Existing Next.js console for `/review`, `/ops`, and owner publication.
- PostgreSQL as durable system of record.
- Supabase Auth/Postgres is the preferred pilot option because it provides
  invite-based identity, MFA support, and row-level security in one managed
  control plane.
- Background jobs use a durable queue with idempotent workers. A production
  decision must select the queue before implementation; in-process timers are
  prohibited for ingest, assignment, resolution, publication, and deletion.

### 8.2 Media plane

- Edge remains the original recorder and temporary source holder.
- Private Cloudflare R2 is the preferred pilot review-media store, pending
  explicit factory permission and data-processing terms.
- Browser media access uses assignment-scoped, short-lived authorization.
- A server endpoint validates the active assignment, logs the access, and mints
  a signed URL with a maximum 10-minute lifetime.
- The player refreshes authorization before expiry without resetting playback,
  buffers, source time, draft clicks, or coverage telemetry. A refresh failure
  pauses playback and offers retry; delivery-caused gaps are marked
  `media_unavailable` and cannot be charged to reviewer coverage.
- Direct object delivery does not provide synchronous byte-range evidence to the
  control plane and is not represented as proof that the reviewer watched.
- Buckets are never public. Object keys avoid factory/customer names.
- Signed URLs are bearer credentials until expiry and must not be logged.
- Review video carries a moving, low-opacity watermark containing a
  reviewer/session pseudonym and rotating session nonce. Download controls,
  short-lived URLs, and watermarks are deterrence and attribution measures, not
  a guarantee against screen recording.

### 8.3 Network separation

```text
factory camera
  -> offline edge recorder + live AI counter
  -> opt-in resumable upload
  -> private review media + durable control plane
  -> three blind reviewers
  -> consensus/adjudication
  -> delayed owner publication

recorded chunk
  -> blind AI run
  -> comparison only after human resolution
```

The cloud control plane may fail independently. The edge queues uploads locally
and retries with bounded storage alarms. It never waits for remote consensus.

### 8.4 Design-copy precedence

`docs/design/fv-live-a-approved.png` exists in the repo and remains the visual
reference. This spec does not unilaterally supersede the locked `DESIGN.md`
trust line `Every count verified by a person, live` or the `app_spec_v1.md`
phrase `100% HUMAN+AI`. Phase 0 must make an explicit dated amendment to both
contracts, record the amendment commit in this spec, and update
`console/components/chrome/trust-line.tsx` before production implementation.
The dated contract amendment is present in both files. Amendment commit:
`723df77054289be5e0f9992b97b0817f76bf4621`.
The replacement pattern is:

```text
Human verified through 2:15 PM
```

No visual-design token or layout rule is superseded.

## 9. Security, Privacy, And Abuse Controls

### 9.1 Account security

- Invite-only enrollment.
- MFA required before production access.
- Staff access through Google Workspace SSO.
- HttpOnly, Secure, SameSite cookies; no auth token in local storage.
- Session revocation, device/session list, and account disable.
- Rate limits on login, lease, heartbeat, draft, submit, and media minting.
- Reviewer access ends immediately when membership is disabled.

### 9.2 Tenant and media security

- Row-level security on all tenant tables.
- Service roles separated by least privilege.
- Signed-media access requires active assignment and factory membership.
- Media authorization and playback starts are audit logged.
- No secrets, source URLs, signed URLs, or raw footage in application logs,
  analytics, error trackers, or screenshots.
- Production analytics are metadata-only unless separately approved.
- Backups are encrypted and tested for restoration.
- The factory's permission to upload footage does not substitute for the legal
  basis, notice, consent where required, and cross-border transfer analysis for
  employees and contractors visible or audible in the footage.

### 9.3 Reviewer abuse and collusion

- Blind assignments and answers.
- Server identity only.
- No selectable work that enables coordinated chunk targeting.
- Detection for impossible throughput, repeated identical timestamp patterns,
  abnormal seek behavior, low coverage, concurrent sessions, and excessive
  abandoned leases.
- Invite-time identity proofing binds one person to one reviewer account.
- Each reviewer registers a signed device token. The assignment service blocks
  two accounts on the same registered device from receiving the same chunk.
- Shared IP/ASN or network identity for two accounts on one chunk is blocked
  unless ops pre-approves a documented shared-worksite exception. Approved
  exceptions receive stronger timestamp-pattern and session audits.
- Cross-submission similarity checks flag implausibly identical click sequences,
  playback timing, and edit histories before consensus publication.
- Post-hoc audited production work evaluates event accuracy, not only total
  count.
- Suspicious behavior creates an ops flag; it does not automatically accuse or
  terminate a worker.
- Screen recording cannot be technically eliminated in a browser. The factory
  agreement must accept this residual risk after watermarking, least-privilege
  access, reviewer confidentiality terms, and incident procedures are in place.
- Watermark pseudonym-to-reviewer mappings are retained for 180 days so an
  incident discovered after media deletion remains attributable.

### 9.4 Retention

Approved pilot defaults:

- raw and review video: 30 days after source time;
- drafts from abandoned assignments: 7 days;
- operational logs: 90 days;
- timestamped final labels and lineage: retained indefinitely;
- short evidence clips: retained indefinitely.

The last two defaults are a production launch blocker until the factory
agreement, worker privacy notice, deletion obligations, jurisdiction, and data
processing terms explicitly permit them. If they do not, retention becomes
factory-configurable with legal hold and cryptographic deletion support.

Deletion is a job with auditable states: scheduled, object deleted, replicas
expired, database tombstoned, and verified. A database flag alone is not proof
that media was deleted.

Training manifests must retain source-chunk lineage into every model artifact.
The factory agreement must state whether trained weights are retained derived
artifacts or subject to deletion. If a valid deletion request covers a model and
retention is not contractually permitted, that model is quarantined from
deployment until it is retrained without the affected data or a documented
unlearning method is validated. The product must not claim that deleting source
objects removes their influence from an already trained model.

## 10. Reviewer Quality

Quality is event-level, not total-only.

Per reviewer, per station/product where sample size permits:

- audited-reference event precision, recall, and F1;
- total-count absolute error;
- median and p95 timing error;
- peer disagreement rate after excluding bad footage;
- usable-source coverage;
- problem-report rate and validity;
- median active review time;
- abandoned and expired lease rate.

Quality rules:

- Do not show expected answers in worker payloads.
- Qualification is pass/fail against explicit curated clips. Production quality
  scores are informational until the reviewer has at least 50 audited reference
  events across at least 10 chunks; disciplinary use requires at least 200
  audited events plus human review.
- Do not compare raw speed without controlling for station density, footage
  difficulty, device/network failures, and playback speed.
- Do not use peer majority as the only truth for worker discipline.
- Ops sees sample size and confidence intervals with every score.
- Worker status actions require human review and an auditable reason.
- Auto-resolved chunks are randomly audited to measure unanimous-human error.
- Every rate is shown with its numerator, denominator, and Wilson interval. No
  threshold may claim resolution finer than the registered sample can support.
- Evaluation holdouts are isolated before training export; reviewed labels used
  to tune a model or resolver cannot also score that model as blind evaluation.

Pilot reviewers are paid hourly, not per chunk or per click. Speed bonuses are
prohibited during the pilot. Compensation, worker classification, scheduling,
and local labor compliance remain business/legal responsibilities, but the
selected incentive model is an input to fraud and quality controls and must be
recorded before launch.

Review sessions are capped at 90 minutes of continuous tally work followed by a
10-minute break, and at 6 tally hours per reviewer per day. The portal reminds
and then blocks new leases at the cap while allowing the current assignment to
finish. Fatigue, quality, and throughput are reviewed together.

## 11. Capacity And Service Levels

Pilot example:

- two cameras;
- eight recorded hours per camera;
- 64 total 15-minute chunks per day;
- 192 primary assignments per day;
- a hard traversal floor of 3 minutes per assignment at 5x, before review,
  pauses, edits, problems, or confirmation.

No reviewer-hours or roster-size claim is derived from that hard floor. A
real-footage rehearsal must measure median and p95 end-to-end handle time first.
Staffing is then based on p95 demand, breaks, expected absence, measured
adjudication/fourth-review demand, and 25 percent buffer.

Capacity planning must also complete this per-station budget:

```text
daily_source_bytes = source_bitrate_bps / 8 * recorded_seconds
chunk_upload_seconds = chunk_bytes * 8 / measured_sustained_upstream_bps
review_delivery_bps = rendition_bitrate_bps * effective_playback_rate
daily_primary_hours = chunks * 3 * p95_primary_handle_seconds / 3600
daily_adjudication_hours = disputed_chunks * p95_adjudication_seconds / 3600
cost_per_resolved_chunk =
  (storage + upload + transcode + database + delivery + reviewer labor
   + adjudicator labor + support) / resolved_chunks
```

Required pilot headroom:

- upload plus normal factory traffic uses at most 60 percent of measured
  sustained upstream;
- chunk upload plus transcode p95 is at most 30 minutes;
- worker downlink supports the validated speed at no more than 70 percent of
  measured sustained bandwidth;
- primary plus adjudication staffing has 25 percent p95 headroom;
- exact-agreement adjudication rate is measured during rehearsal. Above 20
  percent of chunks or 1.5 adjudicator-hours per factory-day triggers a product
  review before scale-up.

Phase 0 records actual vendor and labor inputs and a maximum acceptable
cost-per-resolved-chunk approved by Thomas. Until those cells are filled, the
60-90 minute target is a design goal, not a proven SLA.

Operational targets:

| Metric | Pilot target |
| --- | --- |
| Eligible chunk to first lease p95 | under 15 minutes |
| Source end to `human_final_at` p95, non-audited chunks | under 90 minutes (design target pending Tier B measurement) |
| Source end to `human_final_at` p95, selected audits | measured and reported separately before a target is approved |
| Source end to `human_final_at` p95, seam-dependent chunks | measured and reported separately with successor wait time |
| Successful draft persistence | 99.9 percent |
| Duplicate final submissions | zero |
| Cross-tenant access | zero |
| Media URL lifetime | at most 10 minutes |
| Unresolved chunk age alert | 120 minutes |
| Reviewer usable coverage | at least 98 percent |

If demand exceeds capacity, the product reports honest backlog and verified
through-time. It does not lower the number of required reviews or publish
unresolved counts silently.

## 12. Ops Surface

`/ops` is operational, dense, and work-focused.

Required views:

- **Queue:** ready, leased, awaiting reviewers, resolving, adjudication,
  quarantined, oldest age, p50/p95 lag.
- **Factories:** camera/upload health, last source time, consent/privacy mode,
  storage age.
- **Reviewers:** online state, active assignment, quality metrics with sample
  size, suspicious-pattern flags.
- **Disagreements:** queue status and age only. Opening primary submissions or
  taking adjudication action requires the separate adjudicator capability.
- **Audit:** account changes, media access, exports, adjudication, retention,
  publication.

The AI comparison surface is a separate `/ai-analysis` route available only to
the AI-analyst capability after `human_final_at`.

The `/ops` route is read-only in v1. Reviewer disablement, lease release,
quarantine, job retry, and label export require separately named capabilities
and a later contract amendment; they must not be inferred from access to
`/ops`. Any future write requires authorization, a reason when applicable, and
an audit row.

## 13. Failure Modes

| Failure | Required behavior |
| --- | --- |
| Edge offline | Live count continues; uploads queue locally |
| Cloud portal unavailable | Review pauses; no runtime impact; backlog visible after recovery |
| Reviewer disconnects | Server draft retained; lease recovery window applies |
| Browser or database disconnects | IndexedDB retains draft actions; stable UUID reconciliation suppresses duplicates |
| Video URL approaches expiry | Player refreshes before expiry without losing playback/source position |
| Video URL refresh fails | Playback pauses; retry is explicit; delivery-caused gaps do not fail reviewer coverage |
| Duplicate upload | Idempotent ingest returns existing chunk |
| Corrupt/transcode-failed media | Chunk quarantined; no assignments |
| Camera clock jumps | Gap/discontinuity visible; chunk quarantined when unsafe |
| Placement crosses chunk seam | Padded context plus adjacent-chunk dedup yields exactly one event or adjudication |
| Last chunk has no seam partner | Explicit closing seam uses available post-roll and reaches a terminal state |
| Seam partner is quarantined | Available context is adjudicated within 30 minutes as seam-adjudicated or seam-unverifiable |
| Reviewer submits twice | Same idempotency key returns original result |
| Resolver runs twice | Same version/input set returns one consensus run |
| One reviewer never submits | Assignment expires and is replaced by a distinct reviewer |
| Database unavailable | No final acknowledgement; client retains draft and retries |
| Object deletion fails | Retention job remains failed/open and pages ops |
| AI run fails | Human workflow and owner publication continue |
| Mid-day chunk is unverified | Contiguous verified-through frontier stops; owner sees the gap and excluded minutes |
| Consensus backlog grows | Verified-through time and alert reflect delay |

## 14. Observability

Structured metrics:

- ingest/transcode success and duration;
- chunk readiness and quarantine reasons;
- queue depth and age by factory/station;
- leases, heartbeats, expiry, reassignment;
- draft-save and final-submit latency/error;
- coverage failures;
- consensus/adjudication rates;
- publication lag;
- media mint/access failures;
- retention/deletion success;
- AI comparison by immutable model version.

Logs use stable IDs, not emails, signed URLs, source URLs, or footage. Traces cross
ingest, assignment, submission, consensus, and publication through correlation
IDs. Security events and data exports generate alerts.

## 15. Implementation Plan

### Evidence tiers

- **Tier A - local/CI proved:** deterministic tests, database/security
  integration, fixture media, build/lint, and browser automation.
- **Tier B - real-footage/hardware proved:** named source hashes, named device
  class, measured network profile, captured screenshots/logs, and human-reviewed
  outcomes. CI cannot satisfy Tier B.
- **Tier C - pilot/legal approved:** factory permission, filmed-worker basis,
  reviewer jurisdiction/lexicon, labor/privacy terms, retention, vendor region,
  cost ceiling, and named human staffing.

Every checkpoint receipt names the highest tier actually proved. `Tier A pass`
must never be shortened to `pilot ready` or `production ready`.

### Phase 0: decisions and fixtures

- Record an architecture decision for the cloud review control/media plane while
  preserving offline runtime authority.
- Obtain pilot factory upload/storage permission and retention terms.
- Select managed Postgres/auth, object storage, and durable job queue.
- Define factory timezone, shift hours, stations, adjudicator rota, and the
  exam-firewall registry contract.
- Use `es-419` only as a development locale. Name the reviewer country and
  approve the checked-in station lexicon before Tier C deployment.
- Build frame-reviewed resolver-calibration, AI-evaluation holdout, practice,
  and qualification sets with disjoint source hashes/windows.
- Measure source bitrate, factory upstream, worker downlink, transcode p95,
  playback frame drops, disagreement rate, adjudication handle time, and full
  cost per resolved chunk.
- Measure real-footage p95 reviewer handle time before sizing the final reviewer
  roster; the minimum planning floor remains five.
- Reconcile the locked trust-line copy in `DESIGN.md`, `app_spec_v1.md`, and the
  current UI through a dated amendment commit, then record its hash here.
- Run independent Fable and Opus checkpoint-zero reviews and close every P0
  contract contradiction before Phase 1 code.

Exit evidence: Tier A spec checks pass; source-set validation proves populated
evaluation intervals cannot overlap another declared set or lineage. The
resolver-calibration, practice, and qualification sets remain empty pending
Tier B footage selection, so their isolation is currently vacuous and must not
be described as populated evidence. The design amendment exists; Fable and Opus
checkpoint receipts show no open P0. Missing Tier B/C items remain explicitly
blocked and do not prevent local implementation.

### Phase 1: identity and durable domain

- Replace client-supplied reviewer identity with authenticated server sessions.
- Add Postgres schema, migrations, row-level security, seed fixtures, and audit.
- Add chunk, rendition, assignment, draft, submission, tally, and reference
  answer models.
- Preserve the approved `/review` visual contract and implement the versioned
  bilingual event/translation contract.

Exit evidence: Tier A auth/RLS tests prove two tenants cannot read each other's
rows; restart does not lose work; expected answers and worker-throughput metrics
are absent from reviewer payloads; Opus checkpoint review has no open P0.

### Phase 2: secure media and robust work loop

- Add verified ingest/transcode manifests.
- Add assignment-scoped signed media.
- Add lease heartbeat, recovery, server drafts, coverage tracking, and
  idempotent final submission.
- Remove peer answers and pre-lease chunk detail from worker views.

Exit evidence: Tier A browser/power/network interruption, IndexedDB
reconciliation, signed-URL refresh, and expired/disabled-user denial tests pass;
Opus checkpoint review has no open P0.

### Phase 3: three-review consensus and adjudication

- Generate three distinct blind assignments.
- Add versioned event alignment and consensus.
- Build adjudication queue and append-only decisions.
- Publish only resolved human events with honest latency.

Exit evidence: Tier A fixture matrix covers 3/3 agreement, count disagreement,
timestamp ambiguity, problem footage, expiry/reassignment, owner dispute,
end-of-shift seam, quarantined seam partner, and verified-through gaps; Opus
checkpoint review has no open P0.

### Phase 4: blind AI comparison and ops

- Import immutable AI runs.
- Enforce human-first reveal.
- Add comparison metrics and drift view.
- Add quality metrics, queue dashboards, alerts, and export gates.

Exit evidence: Tier A capability/RLS tests prove AI cannot influence consensus
or be read by adjudicator-capable accounts; holdout and exam-firewall tests pass;
Opus checkpoint review has no open P0.

### Phase 5: pilot hardening

- Load and concurrency tests.
- Backup restore and object-deletion proof.
- Spanish usability test on actual worker devices and bandwidth.
- Accessibility, keyboard, mobile-width, browser, and visual regression checks.
- Incident runbooks and rollback rehearsal.

Exit evidence: Tier B real-footage/device/network eval packet passes, followed
separately by Tier C factory/legal/staffing approval. Only then may the pilot be
called ready.

## 16. Expected Code Ownership

Likely implementation areas:

- `console/prisma/schema.prisma` and migrations;
- `console/lib/reviewStore.ts` replaced by repository/service modules;
- `console/lib/reviewChunks.ts`: delete `wallClockForClick` and
  `tallyClicksToEvents`; padded-rendition mapping and stable per-assignment event
  IDs replace their zero-offset/array-index assumptions. Retain only compatible
  types and domain helpers.
- `console/components/review/review-tally-console.tsx`: delete the duplicate
  `clickWallClock` zero-offset wall-clock mapping; render canonical source time
  returned by the server.
- `console/app/api/review/**` authenticated assignment APIs;
- new `console/lib/auth/**`, `console/lib/media/**`,
  `console/lib/consensus/**`, and `console/lib/audit/**`;
- `console/components/review/review-tally-console.tsx`;
- `/ops` queue/reviewer-health views, separate adjudication surface, and
  capability-isolated `/ai-analysis` view;
- edge upload/manifest scripts under `scripts/`;
- unit, integration, security, E2E, and failure-recovery tests.

Implementation must use repo patterns and may adjust this map after a fresh code
review. It must not reuse `globalThis` as production persistence.

## 17. Test And Proof Plan

### Unit

- source-time mapping and discontinuities;
- canonical half-open chunk ownership and adjacent-chunk seam dedup;
- assignment eligibility and three-distinct-reviewer invariant;
- lease/heartbeat/recovery transitions;
- coverage union and thresholds;
- idempotency;
- event alignment;
- consensus state matrix;
- reviewer quality calculations;
- retention scheduling.

### Integration

- Auth and row-level-security tenant isolation.
- Reference-answer non-disclosure.
- Open-case AI embargo across adjudicator and ops roles.
- Signed-media authorization, expiry, and disabled-user denial.
- Database restart durability.
- Queue worker retry and exactly-once domain effects.
- Three submissions through resolution/publication.
- Adjudication lineage.
- AI blind-reveal ordering.
- Deletion through object-store verification.

### End to end

- Invite, Spanish-first login on a pre-provisioned pilot device, guided
  practice, qualification, and first real assignment without staff assistance.
- `work_ready` automatically appears on the idle waiting screen without refresh.
- New work never interrupts or replaces an active review.
- Confirming one chunk automatically opens the next ready assignment.
- Reviewer login, resume draft, tally by keyboard, undo, summary, confirm.
- 1x/2x/5x playback on approved low-cost hardware; gated 10x/15x only after the
  named device/rendition class passes the Tier B safety screen.
- Automatic speed downgrade on dropped-frame or bandwidth-health breach.
- Connection loss and URL refresh.
- Spanish UI at desktop and narrow widths.
- Three workers receive the same chunk blindly and cannot see peer answers.
- A separately authorized adjudicator resolves a disagreement.
- Owner sees only the resolved result and verified-through time.
- No browser console errors.

### Load and recovery

- Daily pilot volume plus 5x burst.
- Lease races.
- Database failover during draft and final submit.
- Queue worker crash after external side effect but before acknowledgement.
- Object store latency and transient failures.
- Backlog recovery without duplicate publication.
- One absent reviewer plus expiry/replacement and a requested fourth review.
- Fabricated client coverage proves coverage telemetry cannot independently
  establish quality or attention.
- Two accounts on one registered device cannot receive the same chunk.
- A sub-second reference placement at every candidate playback speed.
- A placement completed immediately before, at, and after a chunk boundary.
- Burned-timecode constant- and variable-frame-rate transcodes.

## 18. Acceptance Criteria

No tier may borrow proof from a higher tier.

### Tier A - local/CI acceptance

- [ ] `make docs-check`, console unit tests, lint, build, and reviewer E2E pass.
- [ ] Fable and Opus checkpoint reviews have no open P0 finding.
- [ ] A newly assigned chunk appears on the idle screen within 10 seconds without
      refresh and never interrupts an active review.
- [ ] Confirming a chunk opens the next assignment shell within 2 seconds under
      the deterministic test network profile.
- [ ] Workers never select factories, cameras, dates, files, or peer-visible
      queues; worker payloads omit expected answers, peer/AI/consensus/dispute
      data, global queue timing, and chunks-per-hour metrics.
- [ ] The complete workflow is usable at 1366x768 and narrow widths without
      overlap or hidden primary controls.
- [ ] Three distinct authenticated identities are assigned to every normal
      chunk, and two accounts on one registered device cannot receive the same
      chunk.
- [ ] Cross-tenant RLS and application authorization prevent access to another
      assignment, answer, or media object.
- [ ] Work survives app/database restart; IndexedDB reconciliation, lease
      recovery, immutable final submission, and idempotency tests pass.
- [ ] Every tally event retains source hash/time, mapping/rendition, assignment,
      reviewer, submission, stable action UUID, and app-version lineage.
- [ ] Coverage is represented as unverified client telemetry; no test or score
      treats it as proof of attention.
- [ ] Count disagreement and ambiguous event alignment enter adjudication.
- [ ] Boundary fixtures produce exactly one event before, at, and after seams,
      including end-of-shift and quarantined-partner terminal cases.
- [ ] A mid-day unverified chunk stops the contiguous verified-through frontier
      and exposes excluded minutes.
- [ ] AI is hidden until `human_final_at`; adjudicator-capable accounts receive
      403 from all AI event/comparison reads.
- [ ] Exam-firewall source intervals cannot be assigned or exported.
- [ ] Signed-media authorization, seamless refresh, refresh failure, and
      disabled/expired-user denial tests pass.
- [ ] No framework overlay or relevant browser console errors remain in desktop
      and narrow-viewport verification.

### Tier B - real-footage/hardware acceptance

- [ ] Every eval names the source video path, SHA-256, source interval, truth
      tier, reviewer identities or simulation boundary, and generated artifacts.
- [ ] The real-footage worker flow runs from ingest through assignment, draft,
      three submissions, resolution/adjudication, and owner publication.
- [ ] Constant- and variable-frame-rate burned-timecode tests prove mapping error
      below 250 ms and below 20 percent of the final alignment tolerance.
- [ ] Each enabled speed passes zero-miss and p95 frame-drop gates on the named
      low-cost worker device/network class. Headless CI is not accepted.
- [ ] Representative first-time workers reach guided practice within 5 minutes
      and real work within 15 minutes, including MFA.
- [ ] The canonical bilingual event definition reaches required two-annotator
      timing agreement before reference labels are used.
- [ ] Real-footage p95 handle time, disagreement rate, audit load, absence, and
      fourth-review demand size the roster with 25 percent headroom.
- [ ] Random audits meet their sample floor and measure unanimous-human error
      without evaluation leakage.
- [ ] Upload, transcode, queue, adjudication, and cost-per-resolved-chunk budgets
      are measured on the actual pilot network/hardware.

### Tier C - pilot/legal acceptance

- [ ] The reviewer country and checked-in Spanish lexicon are approved by
      representative native speakers and comprehension-tested.
- [ ] Factory footage permission, filmed-worker basis/notice/consent where
      required, cross-border transfer, reviewer terms, and retention are signed.
- [ ] Auth/Postgres, object-store region, durable queue, reviewer roster,
      adjudicator coverage, and cost ceiling are approved.
- [ ] Retention deletion is verified against production object storage and model
      lineage/deletion obligations are resolved.
- [ ] Production is deployed, then browsed at the live URL with screenshots,
      interaction proof, and no relevant console errors before any `live` claim.

## 19. Decisions Required Before Production

These are explicit launch gates, not implementation ambiguities:

- Pilot factory's written cloud-upload and reviewer-access approval.
- Jurisdiction, filmed-employee legal basis/notice/consent where required,
  reviewer privacy notice, cross-border transfer analysis, and data-processing
  agreement.
- Final retention for labels and evidence clips.
- Selected auth/Postgres, object-store region, and durable queue.
- Named adjudicator and backup coverage.
- Reviewer roster sized from measured p95 handle time, absence,
  disagreement/adjudication, and fourth-review demand, with five as the minimum
  planning floor.
- Real reviewer hardware, browser, bandwidth, and accessibility profile.
- Measured event-alignment tolerance at each allowed speed.
- Measured reference-event miss rate and frame drops before enabling 10x or 15x.
- Maximum acceptable cost per resolved chunk.
- Screen-recording residual-risk acceptance and reviewer confidentiality terms.
- Whether deletion obligations include trained model weights and the resulting
  retraining/unlearning policy.
- Whether owner-published human counts are a separate audit stream or replace a
  displayed operational count after resolution.

## 20. Definition Of Done

The feature is done when a production-like 15-minute factory chunk is uploaded,
served privately to three authenticated reviewers, independently tallied,
resolved or adjudicated with immutable lineage, compared blindly to an immutable
AI run, and published to the owner as an honestly delayed verified count.

Proof must include:

- automated unit/integration/E2E/security results;
- database rows showing three distinct submissions and one resolved lineage;
- media-access denial evidence;
- restart and retry evidence;
- live production screenshots for reviewer, ops, and owner states;
- production browser console check;
- a retention deletion test;
- an exact-once chunk-seam test;
- real-device playback-quality and reference-event miss results for every
  enabled speed;
- a reviewer absence/replacement/fourth-review simulation;
- an open-adjudication AI-access denial test;
- the filled bandwidth, latency, adjudication, and cost budget;
- an updated current-state document that distinguishes implemented, tested,
  deployed, and pilot-proven claims.
