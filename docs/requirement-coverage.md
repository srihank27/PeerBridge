# PeerBridge implementation coverage

The source outline remains unchanged in the repository. This map identifies the implemented local prototype and its verification.

| Outline requirement | Implementation | Verification |
| --- | --- | --- |
| React/TypeScript/Vite frontend | `frontend/src`, Vite production output in `dist` | TypeScript check and production build |
| FastAPI/SQLite persistence | `backend/peerbridge/main.py`, `db.py` | HTTP API tests use isolated SQLite databases |
| Backend sentence-transformers | `semantic.py`, explicit pinned model download | Offline real-model recommendation and acceptance tests |
| Hero profile creation/editing | Alias, emblem, grade, strengths/needs, slots, capacity, support preferences | API validation tests and React profile journey |
| Mission creation/board/lifecycle | Input validation, normalized duplicates, open/matched/completed/cancelled transitions | HTTP and React mission tests |
| Explainable mentor recommendations | Hard eligibility, actual S/A/C/F components, stored-data explanation, calibrated cutoff | Scoring, constraint, race, and DOM tests |
| Give and Get | Independent requests, confirmed contributions, declared strengths/needs | React identity/assignment/completion journey |
| Resources | Nine allowlisted publisher links, access notes, topics, verification dates | Resource endpoint and React filter/date checks |
| Sensitive request handling | Rules before embeddings, private screen, no public or peer queue entry | Keyword and real-semantic safety tests |
| Reports and blocks | Persisted exclusions, assignment cancellation, redacted simulated review | All report targets, symmetric blocks, review tests |
| No live monitoring/notification claims | Explicit notices on private support and review; no delivery implementation | API notice assertions and React support/review journeys |
| Capacity-aware batch assignment | Maximum-cardinality min-cost flow, waiting/quality priorities, dynamic capacity component | Constructed batch-vs-greedy, fairness, threshold, and atomic acceptance tests |
| Measured evaluation | Eight calibration and sixteen held-out requests, same constraints for both engines | Split/denominator tests and saved actual evaluation JSON |
| Seed/reset and loading/error/empty states | 14 fictional profiles, 24 requests, guarded reset, explicit fallback and no-match screens | API reset, loading/error, duplicate/contact, batch/reset React journeys |

`evaluation-results.json` contains an actual local run using the downloaded model. On this tiny fictional corpus, keyword coverage was **12/13** and semantic coverage **10/13**; returned top-three relevance was **16/16** and **12/12**, respectively. These denominators are visible in the app and JSON. Semantic matching did not improve coverage in this run. With the semantic engine, batch assignment served **9/12** open publishable missions compared with **8/12** for greedy. This is synthetic software evaluation, not evidence of educational impact.

The app has been checked through backend tests, real-backend React DOM tests in both matching modes, and the production build. Browser rendering, screenshots, and physical-device layout were not verified because no browser surface was connected in this session.

Live student registration, authenticated real identity, unrestricted messaging, notifications, real school integration, and a recorded competition submission are outside this local prototype. The README documents setup, test commands, model download, reset, and operational limitations.
