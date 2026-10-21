"""FastAPI API and built React app for the explicitly fictional local demo."""

from contextlib import asynccontextmanager
import json
import os
from pathlib import Path
import sqlite3
import uuid

from fastapi import APIRouter, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from . import db, matching, semantic
from .analysis import analyze_text, contains_contact, normalized_text
from .schemas import BatchInput, BlockInput, MatchInput, MissionInput, MissionUpdate, ProfileInput, ReportInput, ResetInput, TOPICS


@asynccontextmanager
async def lifespan(app):
    db.init_database()
    yield


app = FastAPI(title="PeerBridge fictional local demo", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:8000", "http://127.0.0.1:8000"], allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"], allow_headers=["Content-Type"])
router = APIRouter()


def fail(status, code, message, details=None):
    error = {"code": code, "message": message}
    if details is not None:
        error["details"] = details
    raise HTTPException(status_code=status, detail=error)


@app.exception_handler(StarletteHTTPException)
async def http_error(request, exc):
    detail = exc.detail if isinstance(exc.detail, dict) else {"code": "http_error", "message": str(exc.detail)}
    return JSONResponse(status_code=exc.status_code, content={"error": detail})


@app.exception_handler(RequestValidationError)
async def validation_error(request, exc):
    details = [{"field": ".".join(str(v) for v in e["loc"]), "message": e["msg"]} for e in exc.errors()]
    return JSONResponse(status_code=422, content={"error": {"code": "validation_error", "message": "Please check the highlighted request fields.", "details": details}})


@app.exception_handler(sqlite3.IntegrityError)
async def integrity_error(request, exc):
    return JSONResponse(status_code=409, content={"error": {"code": "conflict", "message": "This change conflicts with existing demo data. Refresh and try again."}})


def required(conn, table, identifier):
    # Table names are internal constants, never supplied by a request.
    row = conn.execute(f"SELECT * FROM {table} WHERE id=?", (identifier,)).fetchone()
    if row is None:
        fail(404, "not_found", f"The requested {table.rstrip('s')} was not found.")
    return row


def _close_matches(conn, rows, status="cancelled"):
    for row in rows:
        conn.execute("UPDATE matches SET status=? WHERE id=?", (status, row["id"]))
        mission = conn.execute("SELECT * FROM missions WHERE id=?", (row["mission_id"],)).fetchone()
        if mission and mission["status"] == "matched":
            conn.execute("UPDATE missions SET status=? WHERE id=?", ("completed" if status == "completed" else "open", row["mission_id"]))


@router.get("/health")
def health():
    return {"status": "ok", **semantic.status(), "demo": True, "qa_mode": os.environ.get("PEERBRIDGE_TEST_MODE") == "1"}


@router.get("/profiles")
def profiles():
    with db.connect() as conn:
        return [db.profile_dict(conn, row) for row in conn.execute("SELECT * FROM profiles ORDER BY alias COLLATE NOCASE")]


@router.get("/profiles/{profile_id}")
def profile(profile_id: str):
    with db.connect() as conn:
        return db.profile_dict(conn, required(conn, "profiles", profile_id))


@router.post("/profiles", status_code=201)
def create_profile(body: ProfileInput):
    with db.connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        if conn.execute("SELECT 1 FROM profiles WHERE alias=? COLLATE NOCASE", (body.alias,)).fetchone():
            fail(409, "alias_taken", "That fictional hero alias is already in use.")
        identifier = "hero-" + uuid.uuid4().hex
        conn.execute("INSERT INTO profiles VALUES(?,?,?,?,?,?,?,?,?,?)", (identifier, body.alias, body.avatar_id, body.grade_band, json.dumps(body.strengths), json.dumps(body.needs), json.dumps(body.available_slots), body.capacity, json.dumps(body.support_preferences), db.utcnow()))
        return db.profile_dict(conn, required(conn, "profiles", identifier))


@router.put("/profiles/{profile_id}")
def update_profile(profile_id: str, body: ProfileInput):
    with db.connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        old = db.profile_dict(conn, required(conn, "profiles", profile_id))
        if body.capacity < old["active_matches"]:
            fail(409, "capacity_in_use", "Complete or cancel active mentor assignments before reducing capacity below the current workload.")
        if conn.execute("SELECT 1 FROM profiles WHERE alias=? COLLATE NOCASE AND id!=?", (body.alias, profile_id)).fetchone():
            fail(409, "alias_taken", "That fictional hero alias is already in use.")
        # Changing availability or grade must not silently invalidate an active
        # agreement. Complete/cancel it first, or retain the shared slot/band.
        involved = conn.execute("SELECT x.*,m.requester_id FROM matches x JOIN missions m ON x.mission_id=m.id WHERE x.status='active' AND (x.mentor_id=? OR x.requester_id=?)", (profile_id, profile_id)).fetchall()
        for match in involved:
            other_id = match["requester_id"] if match["mentor_id"] == profile_id else match["mentor_id"]
            other = required(conn, "profiles", other_id)
            if body.grade_band != other["grade_band"] or not (set(body.available_slots) & set(db.decode(other["available_slots"], []))):
                fail(409, "active_agreement", "Keep a compatible grade band and shared time for active assignments, or complete/cancel those missions first.")
            if match["mentor_id"] == profile_id and match["topic"] not in body.strengths:
                fail(409, "active_agreement", "Retain the declared strength used by an active mentor assignment, or complete/cancel that mission first.")
        conn.execute("UPDATE profiles SET alias=?,avatar_id=?,grade_band=?,strengths=?,needs=?,available_slots=?,capacity=?,support_preferences=? WHERE id=?", (body.alias, body.avatar_id, body.grade_band, json.dumps(body.strengths), json.dumps(body.needs), json.dumps(body.available_slots), body.capacity, json.dumps(body.support_preferences), profile_id))
        return db.profile_dict(conn, required(conn, "profiles", profile_id))


@router.get("/profiles/{profile_id}/missions")
def own_missions(profile_id: str):
    with db.connect() as conn:
        required(conn, "profiles", profile_id)
        return [db.mission_dict(conn, row) for row in conn.execute("SELECT * FROM missions WHERE requester_id=? ORDER BY created_at DESC,id", (profile_id,))]


@router.post("/missions", status_code=201)
def create_mission(body: MissionInput):
    analyzed = analyze_text(body.text)
    # Sensitive routing takes precedence even if private text contains contact
    # information. No such text can ever appear on the public board.
    if analyzed["route"] != "private_support" and contains_contact(body.text):
        fail(422, "contact_details", "Remove contact details, links, handles, and addresses before posting. Use a fictional hero alias only.")
    normalized = normalized_text(body.text)
    if len(normalized) < 5:
        fail(422, "mission_too_short", "Describe the subject and the help you need.")
    with db.connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        required(conn, "profiles", body.requester_id)
        if conn.execute("SELECT 1 FROM missions WHERE requester_id=? AND normalized_text=? AND status IN ('open','matched')", (body.requester_id, normalized)).fetchone():
            fail(409, "duplicate_mission", "You already have this mission open or matched. Check your existing requests.")
        identifier = "mission-" + uuid.uuid4().hex
        status = "private" if analyzed["route"] == "private_support" else "open"
        conn.execute("INSERT INTO missions VALUES(?,?,?,?,?,?,?,?,?)", (identifier, body.requester_id, body.text, normalized, analyzed["topic"], analyzed["route"], status, json.dumps(analyzed["analysis"]), db.utcnow()))
        return db.mission_dict(conn, required(conn, "missions", identifier))


@router.get("/missions")
def missions():
    with db.connect() as conn:
        return [db.mission_dict(conn, row) for row in conn.execute("SELECT * FROM missions WHERE status='open' ORDER BY created_at,id") if matching.publishable(conn, row)]


@router.patch("/missions/{mission_id}")
def update_mission(mission_id: str, body: MissionUpdate):
    with db.connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        old = required(conn, "missions", mission_id)
        transitions = {"open": {"completed", "cancelled"}, "matched": {"completed", "cancelled"}, "completed": {"open"}, "cancelled": {"open"}, "private": {"cancelled"}}
        if body.status not in transitions.get(old["status"], set()):
            fail(409, "invalid_transition", f"Cannot change a {old['status']} mission to {body.status}.")
        if body.status == "open" and old["route"] not in ("academic", "school_transition"):
            fail(409, "private_route", "Private or unclear requests cannot be reopened to the mission board. Submit a new, clear academic or school-related request.")
        if body.status == "open" and conn.execute("SELECT 1 FROM missions WHERE requester_id=? AND normalized_text=? AND status IN ('open','matched') AND id!=?", (old["requester_id"], old["normalized_text"], mission_id)).fetchone():
            fail(409, "duplicate_mission", "An identical mission is already active.")
        matches = conn.execute("SELECT * FROM matches WHERE mission_id=? AND status='active'", (mission_id,)).fetchall()
        _close_matches(conn, matches, "completed" if body.status == "completed" else "cancelled")
        conn.execute("UPDATE missions SET status=? WHERE id=?", (body.status, mission_id))
        return db.mission_dict(conn, required(conn, "missions", mission_id))


@router.post("/missions/{mission_id}/recommendations")
def recommendations(mission_id: str):
    with db.connect() as conn:
        return matching.recommend(conn, required(conn, "missions", mission_id))


@router.get("/matches")
def matches():
    with db.connect() as conn:
        return [db.match_dict(conn, row) for row in conn.execute("SELECT * FROM matches ORDER BY created_at DESC,id")]


@router.post("/matches", status_code=201)
def create_match(body: MatchInput):
    with db.connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        required(conn, "missions", body.mission_id)
        required(conn, "profiles", body.mentor_id)
        try:
            return matching.accept_match(conn, body.mission_id, body.mentor_id)
        except matching.MatchConflict as exc:
            fail(409, "match_ineligible", str(exc))


@router.get("/resources")
def resources(topic: str | None = None):
    if topic is not None and topic not in (*TOPICS, "private_support"):
        fail(422, "unknown_topic", "Choose a topic from the resource directory.")
    with db.connect() as conn:
        rows = [db.resource_dict(row) for row in conn.execute("SELECT * FROM resources ORDER BY title")]
        return [row for row in rows if topic is None or topic in row["topics"]]


@router.post("/reports", status_code=201)
def create_report(body: ReportInput):
    with db.connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        required(conn, "profiles", body.reporter_id)
        table = {"mission": "missions", "profile": "profiles", "match": "matches"}[body.target_type]
        target = required(conn, table, body.target_id)
        identifier = "report-" + uuid.uuid4().hex
        conn.execute("INSERT INTO reports VALUES(?,?,?,?,?,?)", (identifier, body.reporter_id, body.target_type, body.target_id, body.reason, db.utcnow()))
        if body.target_type == "mission":
            affected = conn.execute("SELECT * FROM matches WHERE mission_id=? AND status='active'", (body.target_id,)).fetchall()
        elif body.target_type == "profile":
            affected = conn.execute("SELECT * FROM matches WHERE (mentor_id=? OR requester_id=?) AND status='active'", (body.target_id, body.target_id)).fetchall()
        else:
            affected = conn.execute("SELECT * FROM matches WHERE status='active' AND ((requester_id=? AND mentor_id=?) OR (requester_id=? AND mentor_id=?))", (target["requester_id"], target["mentor_id"], target["mentor_id"], target["requester_id"])).fetchall()
        _close_matches(conn, affected)
        result = dict(required(conn, "reports", identifier))
        result.update(review_status="simulated_pending", demo=True, notice="No adult has been contacted. There is no live monitoring.")
        return result


@router.get("/reports")
def reports():
    with db.connect() as conn:
        result = []
        for row in conn.execute("SELECT r.*,p.alias reporter_alias FROM reports r JOIN profiles p ON p.id=r.reporter_id ORDER BY r.created_at DESC,r.id"):
            item = dict(row)
            # The review queue never reproduces mission text or free-form report
            # text, which may itself quote a student's private request.
            item["reason"] = "Report details are private in this simulated review queue."
            item["target_summary"] = {"profile": "Reported fictional hero profile", "mission": "Reported mission (content hidden)", "match": "Reported demo assignment"}[item["target_type"]]
            item.update(review_status="simulated_pending", demo=True, notice="No adult has been contacted. There is no live monitoring.")
            result.append(item)
        return result


@router.post("/blocks", status_code=201)
def create_block(body: BlockInput):
    if body.blocker_id == body.blocked_id:
        fail(422, "self_block", "Choose a different fictional hero to block.")
    with db.connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        required(conn, "profiles", body.blocker_id)
        required(conn, "profiles", body.blocked_id)
        existing = conn.execute("SELECT * FROM blocks WHERE blocker_id=? AND blocked_id=?", (body.blocker_id, body.blocked_id)).fetchone()
        if existing:
            return dict(existing)
        identifier = "block-" + uuid.uuid4().hex
        conn.execute("INSERT INTO blocks VALUES(?,?,?,?)", (identifier, body.blocker_id, body.blocked_id, db.utcnow()))
        affected = conn.execute("SELECT * FROM matches WHERE status='active' AND ((mentor_id=? AND requester_id=?) OR (mentor_id=? AND requester_id=?))", (body.blocker_id, body.blocked_id, body.blocked_id, body.blocker_id)).fetchall()
        _close_matches(conn, affected)
        return dict(required(conn, "blocks", identifier))


@router.get("/blocks")
def blocks(profile_id: str | None = None):
    with db.connect() as conn:
        if profile_id:
            required(conn, "profiles", profile_id)
        rows = conn.execute("SELECT b.*,p.alias blocker_alias,q.alias blocked_alias FROM blocks b JOIN profiles p ON p.id=b.blocker_id JOIN profiles q ON q.id=b.blocked_id ORDER BY b.created_at,b.id")
        return [dict(r) for r in rows if profile_id is None or profile_id in (r["blocker_id"], r["blocked_id"])]


@router.delete("/blocks/{block_id}")
def delete_block(block_id: str):
    with db.connect() as conn:
        required(conn, "blocks", block_id)
        conn.execute("DELETE FROM blocks WHERE id=?", (block_id,))
    return {"deleted": block_id}


@router.post("/assignments/batch")
def batch(body: BatchInput):
    with db.connect() as conn:
        if not body.dry_run:
            conn.execute("BEGIN IMMEDIATE")
        plan = matching.plan_batch(conn)
        plan["dry_run"] = body.dry_run
        if not body.dry_run:
            try:
                plan["matches"] = [matching.accept_match(conn, item["mission_id"], item["mentor_id"], threshold=plan["threshold"]) for item in plan["assignments"]]
            except matching.MatchConflict as exc:
                fail(409, "batch_conflict", str(exc))
        return plan


@router.get("/metrics")
def metrics():
    from .evaluation import evaluate
    return evaluate()


@router.post("/demo/reset")
def reset(body: ResetInput):
    db.reset_database()
    return {"status": "reset", "demo": True, "message": "The fictional profiles, labeled missions, and seeded assignments have been restored."}


app.include_router(router, prefix="/api")
app.include_router(router)

DIST = Path(__file__).resolve().parents[2] / "dist"
if (DIST / "assets").is_dir():
    app.mount("/assets", StaticFiles(directory=str(DIST / "assets")), name="assets")


@app.api_route("/", methods=["GET", "HEAD"], include_in_schema=False)
def frontend_index():
    if (DIST / "index.html").is_file():
        return FileResponse(DIST / "index.html")
    return JSONResponse({"message": "PeerBridge API is running. Start the Vite frontend or run its production build.", "api": "/api/health"})


@app.get("/{path:path}", include_in_schema=False)
def frontend_path(path: str):
    if path.startswith("api/") or path == "api":
        fail(404, "not_found", "No such API endpoint.")
    resolved = (DIST / path).resolve()
    if resolved.is_relative_to(DIST.resolve()) and resolved.is_file():
        return FileResponse(resolved)
    if path and "." not in path and (DIST / "index.html").is_file():
        return FileResponse(DIST / "index.html")
    fail(404, "not_found", "No such page or asset.")
