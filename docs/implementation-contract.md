# PeerBridge local prototype contract

The supplied Word outline is the scope. This checkout is local development; do not publish it to Sites. Preserve the original outline and preserve the old dist files until the React production build replaces them.

## Stack and folders

- `frontend/`: React, TypeScript, Vite; build to root `dist/`.
- `backend/peerbridge/`: Python FastAPI, standard-library sqlite3, sentence-transformers. Run `python -m uvicorn backend.peerbridge.main:app --host 127.0.0.1 --port 8000` from the root.
- FastAPI mounts `/api` routes and also the same root routes specified in the outline (`/profiles`, `/missions`, `/matches`, `/reports`, `/metrics`). Vite proxies `/api` to port 8000. FastAPI serves root `dist/` when built.
- SQLite path comes from `PEERBRIDGE_DB`, default `data/peerbridge.sqlite3`. Tests always use temporary databases. Models cache within the workspace via `PEERBRIDGE_MODEL_CACHE`. `PEERBRIDGE_MATCHING=auto|semantic|keyword`; auto loads cached model only and clearly labels keyword fallback. Explicit model-download command opts into downloads.

## Data and API

Use JSON snake_case. Responses below are direct objects/arrays unless specified.

Profile: `id, alias, avatar_id, grade_band, strengths[], needs[], available_slots[], capacity, support_preferences[], active_matches, remaining_capacity`. Avatar IDs `bolt, orbit, comet, shield`; grade bands `middle, high`. Preferences `step_by_step, practice, encouragement`. Slot values `Mon 16:00, Tue 16:00, Wed 16:00, Thu 16:00, Fri 16:00, Sat 10:00`. Strength/need topics are the canonical IDs below. Create returns full profile; PUT updates it. Case-insensitive alias uniqueness. Capacity 0–5 and cannot be reduced below current active matches.

Canonical topics: `algebra, geometry, python, robotics, writing, presentations, science, physics, study_skills, school_transition`.

Mission POST: `{requester_id,text}`. Mission response: `id, requester_id, requester_alias, text, topic, route, status, created_at, analysis`. Analysis: `method, confidence, uncertainty, reason`. Routes `academic, school_transition, clarify, private_support`; statuses `open, matched, completed, cancelled, private`. Mission board GET only returns eligible publishable missions (never private_support or clarify). GET `/profiles/{id}/missions` may return that demo identity's own requests; this is a local simulation, not authenticated registration. PATCH `/missions/{id}` takes `{status}` with transitions validated. Prevent duplicate normalized open/matched text for same requester, return 409. Reject contact details before any public posting; sensitive safety routing takes precedence.

POST `/missions/{id}/recommendations`: `{route, topic, analysis, matching_mode, fallback_reason, threshold, candidates[], resources[], support_message}`. Candidate: `mentor` full profile, `score`, `component_scores:{S,A,C,F}`, `explanation` string, `shared_slots[]`. All scores 0–1. Recompute constraints from database. Private/clarify/completed missions never get peer candidates. Resources are allowlisted records only. Support message explicitly says no adult contacted and no live monitoring. Unknown requests clarify instead of forced matching.

POST `/matches` body `{mission_id,mentor_id}`; returns match with `id,mission_id,mentor_id,requester_id,mentor_alias,requester_alias,topic,component_scores,score,explanation,status,created_at`. Accept transactionally and recheck every constraint, threshold, capacity. GET `/matches` lists confirmed demo assignments. Completion of mission closes active match and releases capacity. Reports/blocks are persistent and invalidate eligibility; block also closes active pair matches and reopens publishable missions.

POST `/reports`: `{reporter_id,target_type,target_id,reason}` where target_type `mission|profile|match`; return report. GET `/reports`: redacted demo review queue, with no raw private mission text. POST `/blocks`: `{blocker_id,blocked_id}`. GET `/blocks?profile_id=...`; DELETE `/blocks/{id}` optional. GET `/resources?topic=...`: directory, resource `{id,title,url,topics[],access_notes,verified_at}`. Do not invent school clubs; school-transition resources fall back to trusted school adult if no verified directory item.

GET `/health`: `{status,matching_mode,model_name,fallback_reason,demo:true}`. POST `/demo/reset` body `{confirm:true}` resets seeded data and results. POST `/assignments/batch` body `{dry_run:true}` previews or `{dry_run:false}` transactionally accepts capacity-aware assignments, with greedy comparison. GET `/metrics` runs actual deterministic synthetic evaluation via evaluation module. Error shape `{error:{code,message,details?}}` including request validation errors.

## Module interface between contributors

- `seed.py` exports `PROFILES` (list of profile dicts with stable ids), `LABELED_REQUESTS` (20–30 dicts: id, requester_id, text, expected_topic, expected_route, relevant_mentor_ids, split='calibration'|'evaluation', optional seed_status), `RESOURCES`, `seed_database(conn)` populating tables defined by db.py. Seeded missions preserve labeled-request IDs, including private/clarify cases only in private tables/state. Use original QuantumSpark, NovaMind, ShieldX, FlashForge among >=12 fictional identities. At least one overloaded mentor and no-eligible example.
- `db.py` exports `connect()` context manager yielding sqlite3 connection with Row factory, `init_database()`, `reset_database()`, and profile/mission serialization helpers as needed. Coordinate exact seed INSERTs directly with seed agent.
- `matching.py` exports eligibility and recommendations functions; coordinate exact evaluation interface directly with evaluation agent. It also exposes capacity-aware batch planning with maximum-cardinality then waiting-time then score priority, and greedy baseline, without forcing low-quality matches.
- `evaluation.py` exports `evaluate()` JSON dict; use the same hard eligibility filters for keyword and semantic modes. Report whether semantic actually ran; never invent semantic metrics. Calibrate threshold on labeled calibration set separately from evaluation. Include denominator/methodology, coverage, top-three relevance, synthetic waiting times and workloads. Persist results only if useful; actual calculations required.

## UX and scope

Blue/purple original hero theme, responsive, keyboard labels, focus states, reduced motion. Dashboard, hero editor, mission composer, board, explained matches, Give and Get, Resource Vault, demo review, evaluation and reset controls. Every public-looking activity is labeled fictional/synthetic. No login, unrestricted chat, district endorsement, or claim of adult notification. Persistent SQLite mutations; localStorage only for selected demo identity. Show pending/error/empty/clarify/no-eligible and private support screens.
