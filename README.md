# PeerBridge The Hero Network

A local, fictional student-support prototype built with **React, TypeScript, Vite, Python FastAPI, SQLite, and sentence-transformers**, following the supplied PeerBridge outline.

Create a pseudonymous hero, ask for academic or school-transition help, see why mentors are recommended, accept an eligible match, and share your own strengths independently. All seeded identities, requests, activity, and evaluation outcomes are synthetic. There is no district endorsement, live registration, private messaging, staff monitoring, or adult notification.

## Run on this Windows computer

The production frontend is built in `dist/`. After setup, run:

```powershell
cd C:\dev\App
powershell -ExecutionPolicy Bypass -File scripts/run.ps1
```

Open **http://127.0.0.1:8000**. Press **Ctrl+C** to stop. FastAPI serves both the React app and its API; `python -m http.server` cannot provide the new backend functionality.

## First-time setup

Requires Python 3.10 or newer. The helper installs dependencies into `.venv`, uses an existing Node.js installation or downloads a checksum-verified portable Node.js runtime into `.tools`, installs the locked frontend packages, builds React, and initializes the demo without overwriting existing changes.

```powershell
cd C:\dev\App
powershell -ExecutionPolicy Bypass -File scripts/setup.ps1 -DownloadModel
powershell -ExecutionPolicy Bypass -File scripts/run.ps1
```

`-DownloadModel` explicitly downloads the pinned public embedding model. Omit it to start with the clearly labeled keyword fallback. Initial setup needs internet access and sufficient space for PyTorch and model dependencies. No API key, paid AI service, or account is required.

Manual setup with Python and Node.js 22.12+ already installed:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
cd frontend
npm ci
npm run build
cd ..
.\.venv\Scripts\python.exe scripts/download_model.py
.\.venv\Scripts\python.exe -m uvicorn backend.peerbridge.main:app --host 127.0.0.1 --port 8000
```

Direct dependencies are pinned in `requirements.txt` and `frontend/package.json`; the tested Python environment and npm dependency tree are recorded in `requirements-lock.txt` and `frontend/package-lock.json`. The Python lock was tested on Windows with Python 3.10.

## Develop

In one terminal:

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.peerbridge.main:app --reload --host 127.0.0.1 --port 8000
```

In another terminal:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/frontend.ps1 dev
```

Open **http://127.0.0.1:5173**. Vite proxies `/api` to FastAPI. Run `scripts/frontend.ps1 build` after frontend changes to refresh `dist/`. The app uses original code-drawn hero artwork and a responsive blue and purple interface, with labeled inputs, keyboard focus handling, and reduced-motion support.

## Try the three journeys

1. **Academic help:** select a middle-school fictional identity, or create one with Tuesday availability. Post “I cannot solve equations with letters, and I am embarrassed to ask in class.” Open the match explanation to see eligible algebra mentors, actual shared slots, score components, and a Khan Academy resource. Accept a match to consume mentor capacity.
2. **Finding belonging:** post “I am new to Sutter Middle School and do not know anyone.” The app uses school-transition support, recommends an eligible peer guide when available, and suggests asking a trusted school adult about welcome activities. No school club or ambassador program is invented.
3. **Giving and receiving:** select QuantumSpark and request presentation help. NovaMind can be recommended when eligibility, availability, and capacity permit. QuantumSpark can independently help with Python or algebra. Giving help is never a repayment condition.

Use the hero selector to simulate different identities. It switches fictional demo context; it is not authentication. Create/edit profiles under Hero Identity; compose and track requests under Mission Board; view contributions and support needs under Give and Get. Resource Vault, evaluation results, batch assignment preview, reports, blocks, and reset controls are available in the UI.

## Matching and routing

The backend applies conservative safety rules **before** topic classification or peer matching. Sensitive requests use a private support screen and cannot enter the public mission board or assignment queue. Unclear requests ask for clarification. Contact details and external links in otherwise public requests are rejected. Rule indicators and similarity scores are not measured safety probabilities; automated routing can miss concerns.

For eligible missions, both the keyword baseline and semantic engine exclude the requester, reported profiles or requests, blocked pairings, incompatible grade bands, undeclared topic competence, unavailable mentors, and full mentors. This prototype requires an exact middle/high grade-band match. Shared availability is a declared opportunity to connect, not a booked calendar appointment.

Eligible recommendations use:

```text
H = 0.40S + 0.25A + 0.20C + 0.15F

S = actual mission embedding similarity to declared strength descriptions
    (explicit topic overlap in keyword mode)
A = shared slots / requester slots
C = Jaccard overlap of declared support preferences
F = remaining mentor capacity / total mentor capacity
```

All components are normalized to 0–1. The displayed explanation uses stored profile data. A threshold is selected from a separate labeled calibration set; requests below it receive resources and an honest no-match state. The weights and thresholds are prototype starting points, not validated evidence of student outcomes.

Acceptance uses SQLite `BEGIN IMMEDIATE` and rechecks the route, quality, availability, blocks, reports, and capacity. Completion/cancellation releases capacity. Blocks cancel active pair assignments; reports remove affected content/pairings from eligibility and create a redacted, explicitly simulated review record. No report contacts an adult.

Batch assignment uses a capacitated bipartite min-cost flow. Its priorities are eligible request coverage, waiting time, then score. Mentor capacity slots account for the declining free-capacity component, so assignments remain above threshold when accepted sequentially. The greedy comparison reranks after each capacity change. Preview does not write assignments; confirmation rechecks and commits the entire batch atomically.

## Semantic model and offline operation

The backend uses [`sentence-transformers/all-MiniLM-L6-v2`](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2), pinned to revision `1110a243fdf4706b3f48f1d95db1a4f5529b4d41`. Download it explicitly:

```powershell
.\.venv\Scripts\python.exe scripts/download_model.py
```

Restart FastAPI after downloading. Runtime model loading uses `local_files_only=True` on CPU. Missing or unloadable model files produce a visible **keyword fallback** with a reason. The app never labels rules as live AI, and evaluation never fabricates unavailable semantic results.

Optional environment variables (the app reads the process environment; `.env.example` is a reference, not automatically loaded):

| Variable | Default | Purpose |
| --- | --- | --- |
| `PEERBRIDGE_DB` | `data/peerbridge.sqlite3` | SQLite demo file |
| `PEERBRIDGE_MATCHING` | `auto` | `auto`, `semantic`, or explicit `keyword` |
| `PEERBRIDGE_MODEL_CACHE` | `.cache/models` | Local embedding model cache |

For example, `$env:PEERBRIDGE_MATCHING = 'keyword'` forces the baseline before starting the server. Selecting `semantic` still reports an honest fallback if the model is unavailable.

## Seed, reset, evaluate, and test

The seed contains **14 fictional profiles, 24 labeled requests, and 9 curated resources**, including ambiguous, sensitive, overloaded, and unmatched cases. Resource records include topics, free-access notes, URLs, and a verification date of October 19, 2026. Verification checks the official destination and relevance; availability and external content can change. There are no fabricated school-directory entries or configured emergency helplines.

```powershell
# Initialize only if needed; preserve existing demo changes.
.\.venv\Scripts\python.exe scripts/demo.py seed

# Replace local demo changes with the original fictional dataset.
.\.venv\Scripts\python.exe scripts/demo.py reset --confirm

# Print freshly calculated evaluation results without changing demo data.
.\.venv\Scripts\python.exe scripts/demo.py evaluate

# Run backend behavior, evaluation, and assignment tests in temporary databases.
.\.venv\Scripts\python.exe -m pytest

# Type-check and build React.
powershell -ExecutionPolicy Bypass -File scripts/frontend.ps1 build

# Run React DOM journeys against an automatically isolated temporary API/database.
.\.venv\Scripts\python.exe scripts/test_frontend.py
```

The evaluation uses **8 calibration requests and 16 held-out requests**. It reports top-three returned relevance, relevant-mentor recall, request coverage, routing accuracy, denominators, and engine availability. Keyword and semantic modes use the same eligibility constraints. Batch and greedy are compared on synthetic coverage, waiting, and workload distribution; equal results are reported as equal. Results are calculated from the labeled corpus, not marketing counters. The evaluation uses isolated in-memory data and never modifies the live SQLite demo.

The React tests use jsdom and the real FastAPI service, not mocked API records. `scripts/test_frontend.py` creates a temporary SQLite file and an owned server on an available loopback port, runs the six UI journeys, then stops that server. Tests require both an explicit `PEERBRIDGE_TEST_URL` and `qa_mode` in the server health response before resetting any data. Do not point tests at a normal demo server. Browser layout/screenshot verification requires a connected browser and is separate from these DOM/API tests.

## API and source layout

Interactive API documentation: **http://127.0.0.1:8000/docs**. The outline's routes are available directly and under `/api` for the frontend.

| Endpoint | Behavior |
| --- | --- |
| `POST /profiles`, `PUT /profiles/{id}`, `GET /profiles` | Create, edit, and list fictional hero profiles |
| `POST /missions`, `GET /missions`, `PATCH /missions/{id}` | Validate/route, list publishable open missions, update lifecycle |
| `GET /profiles/{id}/missions` | That demo identity's request history, including private/unclear state |
| `POST /missions/{id}/recommendations` | Explained candidates, resources, routing, uncertainty |
| `POST /matches`, `GET /matches` | Transactional acceptance and confirmed demo assignments |
| `POST /reports`, `GET /reports` | Persistent reporting and redacted simulated review |
| `POST /blocks`, `GET /blocks`, `DELETE /blocks/{id}` | Persistent pair exclusions |
| `GET /resources`, `GET /metrics`, `GET /health` | Curated resources, measured evaluation, engine state |
| `POST /assignments/batch` | Read-only preview or atomic assignment |
| `POST /demo/reset` | Explicitly confirmed seed reset |

```text
backend/peerbridge/  API, SQLite, rules, semantic model, matching, seeds, evaluation
frontend/src/       React screens, forms, API client, TypeScript types, styling
dist/               Production React build, served by FastAPI
scripts/            Local setup/run/build, explicit model download, seed/reset/evaluate
tests/              API, eligibility, assignment, and measured-evaluation tests
docs/               Implementation contract and requirement traceability
```

## Prototype limitations

This is a **localhost-only demonstration**, not a service for real students. It has no authenticated ownership or staff authorization; profile switching, private-history access, review, metrics, and reset operate within one shared local demo. Pseudonyms hide public-looking identity, but do not provide production privacy or access control. Keep the server bound to `127.0.0.1`; real deployment requires authentication, authorization, moderation, consent/data-retention design, and operational support.

Safety rules are deliberately limited and may miss phrasing, context, or languages. The support screen asks the user to reach a trusted adult and explicitly says nobody has been contacted. Reports are simulated and unmonitored. Neither scores nor synthetic evaluation establish safety or real-world educational impact. Curated academic resources supplement peer suggestions; they are not professional support.

The original static Sites configuration in `.openai/hosting.json` is retained from the earlier mockup. Static-only hosting cannot run the Python API or SQLite backend; this implementation runs through FastAPI as documented above. Live school integrations, notification delivery, unrestricted messaging, real registration, competition rule verification, and a recorded submission demo remain outside the implemented local prototype.
