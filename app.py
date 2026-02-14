import os
import urllib.parse
from datetime import datetime, timezone
from flask import Flask, request, jsonify, render_template
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

app = Flask(__name__)

DB_SERVER = os.environ.get("DB_SERVER")
DB_NAME   = os.environ.get("DB_NAME")
DB_USER   = os.environ.get("DB_USER")
DB_PASS   = os.environ.get("DB_PASSWORD")

API_KEY = os.environ.get("API_KEY", "").strip()

if not all([DB_SERVER, DB_NAME, DB_USER, DB_PASS]):
    missing = [k for k, v in {
        "DB_SERVER": DB_SERVER,
        "DB_NAME": DB_NAME,
        "DB_USER": DB_USER,
        "DB_PASSWORD": DB_PASS
    }.items() if not v]
    raise RuntimeError(f"Missing environment variables: {', '.join(missing)}")

odbc = (
    f"Driver={{ODBC Driver 18 for SQL Server}};"
    f"Server=tcp:{DB_SERVER},1433;"
    f"Database={DB_NAME};"
    f"Uid={DB_USER};"
    f"Pwd={DB_PASS};"
    "Encrypt=yes;"
    "TrustServerCertificate=no;"
    "Connection Timeout=30;"
)
conn_str = "mssql+pyodbc:///?odbc_connect=" + urllib.parse.quote_plus(odbc)
engine = create_engine(conn_str, pool_pre_ping=True)

ALLOWED_STATUS = {"Open", "Pending", "Closed"}
ALLOWED_PRIORITY = {"Low", "Medium", "High"}


def require_api_key():
    # If API_KEY env var is not set, allow requests (optional mode)
    if not API_KEY:
        return None

    provided = request.headers.get("X-API-KEY", "").strip()
    if not provided or provided != API_KEY:
        return jsonify({"error": "unauthorized"}), 401
    return None


def serialize_ticket(row):
    # RowMapping -> dict with ISO time string
    d = dict(row)
    created_at = d.get("created_at")
    if isinstance(created_at, datetime):
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        d["created_at"] = created_at.isoformat()
    return d


@app.get("/")
def home():
    return "Helpdesk API is running. Use /ui, /docs, and /tickets", 200


@app.get("/ui")
def ui():
    return render_template("ui.html")


@app.get("/tickets")
def get_tickets():
    auth = require_api_key()
    if auth:
        return auth

    try:
        with engine.connect() as conn:
            rows = conn.execute(text("""
                SELECT id, title, description, status, priority, assigned_to, created_at
                FROM tickets
                ORDER BY created_at DESC
            """)).mappings().all()

        return jsonify([serialize_ticket(r) for r in rows]), 200

    except SQLAlchemyError as e:
        return jsonify({"error": "database error", "detail": str(e)}), 500


@app.post("/tickets")
def post_ticket():
    auth = require_api_key()
    if auth:
        return auth

    data = request.get_json(silent=True) or {}

    title = (data.get("title") or "").strip()
    description = (data.get("description") or "").strip()

    status = (data.get("status") or "Open").strip()
    priority = (data.get("priority") or "Medium").strip()
    assigned_to = (data.get("assigned_to") or "").strip() or None

    if not title or not description:
        return jsonify({"error": "title and description required"}), 400

    if status not in ALLOWED_STATUS:
        return jsonify({"error": f"invalid status. allowed: {sorted(ALLOWED_STATUS)}"}), 400

    if priority not in ALLOWED_PRIORITY:
        return jsonify({"error": f"invalid priority. allowed: {sorted(ALLOWED_PRIORITY)}"}), 400

    try:
        with engine.begin() as conn:
            conn.execute(
                text("""
                    INSERT INTO tickets (title, description, status, priority, assigned_to)
                    VALUES (:t, :d, :s, :p, :a)
                """),
                {"t": title, "d": description, "s": status, "p": priority, "a": assigned_to},
            )

        return jsonify({"message": "ticket created"}), 201

    except SQLAlchemyError as e:
        return jsonify({"error": "database error", "detail": str(e)}), 500


@app.patch("/tickets/<int:ticket_id>")
def update_ticket(ticket_id: int):
    auth = require_api_key()
    if auth:
        return auth

    data = request.get_json(silent=True) or {}

    status = data.get("status")
    priority = data.get("priority")
    assigned_to = data.get("assigned_to")

    updates = {}
    if status is not None:
        status = (status or "").strip()
        if status not in ALLOWED_STATUS:
            return jsonify({"error": f"invalid status. allowed: {sorted(ALLOWED_STATUS)}"}), 400
        updates["status"] = status

    if priority is not None:
        priority = (priority or "").strip()
        if priority not in ALLOWED_PRIORITY:
            return jsonify({"error": f"invalid priority. allowed: {sorted(ALLOWED_PRIORITY)}"}), 400
        updates["priority"] = priority

    if assigned_to is not None:
        assigned_to = (assigned_to or "").strip()
        updates["assigned_to"] = assigned_to if assigned_to else None

    if not updates:
        return jsonify({"error": "no fields to update"}), 400

    set_clause = ", ".join([f"{k} = :{k}" for k in updates.keys()])
    updates["id"] = ticket_id

    try:
        with engine.begin() as conn:
            result = conn.execute(
                text(f"UPDATE tickets SET {set_clause} WHERE id = :id"),
                updates
            )
            if result.rowcount == 0:
                return jsonify({"error": "ticket not found"}), 404

        return jsonify({"message": "ticket updated"}), 200

    except SQLAlchemyError as e:
        return jsonify({"error": "database error", "detail": str(e)}), 500


@app.get("/tickets/<int:ticket_id>")
def get_ticket(ticket_id: int):
    auth = require_api_key()
    if auth:
        return auth

    try:
        with engine.connect() as conn:
            row = conn.execute(text("""
                SELECT id, title, description, status, priority, assigned_to, created_at
                FROM tickets
                WHERE id = :id
            """), {"id": ticket_id}).mappings().first()

        if not row:
            return jsonify({"error": "ticket not found"}), 404

        return jsonify(serialize_ticket(row)), 200

    except SQLAlchemyError as e:
        return jsonify({"error": "database error", "detail": str(e)}), 500


@app.delete("/tickets/<int:ticket_id>")
def delete_ticket(ticket_id: int):
    auth = require_api_key()
    if auth:
        return auth

    try:
        with engine.begin() as conn:
            result = conn.execute(
                text("DELETE FROM tickets WHERE id = :id"),
                {"id": ticket_id}
            )
            if result.rowcount == 0:
                return jsonify({"error": "ticket not found"}), 404

        return jsonify({"message": "ticket deleted"}), 200

    except SQLAlchemyError as e:
        return jsonify({"error": "database error", "detail": str(e)}), 500


