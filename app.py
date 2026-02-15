import os
import urllib.parse
from flask import Flask, request, jsonify, render_template
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

app = Flask(__name__)

DB_SERVER = os.environ.get("DB_SERVER")
DB_NAME   = os.environ.get("DB_NAME")
DB_USER   = os.environ.get("DB_USER")
DB_PASS   = os.environ.get("DB_PASSWORD")

API_KEY = os.environ.get("API_KEY", "")

if not all([DB_SERVER, DB_NAME, DB_USER, DB_PASS]):
    missing = [k for k, v in {
        "DB_SERVER": DB_SERVER, "DB_NAME": DB_NAME, "DB_USER": DB_USER, "DB_PASSWORD": DB_PASS
    }.items() if not v]
    raise RuntimeError(f"Missing environment variables: {', '.join(missing)}")

odbc = (
    "Driver={ODBC Driver 18 for SQL Server};"
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

def require_api_key():
    # If API_KEY env var is empty, auth is disabled
    if not API_KEY:
        return None
    incoming = request.headers.get("X-API-KEY", "")
    if incoming != API_KEY:
        return jsonify({"error": "unauthorized"}), 401
    return None

@app.get("/")
def home():
    return "Helpdesk API is running. Use GET/POST /tickets", 200

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
                SELECT id, title, description, status, created_at
                FROM tickets
                ORDER BY created_at DESC
            """)).mappings().all()

        # RowMapping -> dict
        return jsonify([dict(r) for r in rows]), 200

    except SQLAlchemyError as e:
        return jsonify({"error": "database_error", "details": str(e)}), 500

@app.post("/tickets")
def post_ticket():
    auth = require_api_key()
    if auth:
        return auth

    data = request.get_json(silent=True) or {}
    title = (data.get("title") or "").strip()
    description = (data.get("description") or "").strip()

    if not title or not description:
        return jsonify({"error": "title and description required"}), 400

    try:
        with engine.begin() as conn:
            conn.execute(
                text("INSERT INTO tickets (title, description) VALUES (:t, :d)"),
                {"t": title, "d": description},
            )
        return jsonify({"message": "ticket created"}), 201

    except SQLAlchemyError as e:
        return jsonify({"error": "database_error", "details": str(e)}), 500


# -------------------------
# COMMENTS ENDPOINTS
# -------------------------

@app.get("/tickets/<int:ticket_id>/comments")
def get_comments(ticket_id: int):
    auth = require_api_key()
    if auth:
        return auth

    try:
        with engine.connect() as conn:
            rows = conn.execute(text("""
                SELECT id, ticket_id, author, body, created_at
                FROM ticket_comments
                WHERE ticket_id = :tid
                ORDER BY created_at ASC
            """), {"tid": ticket_id}).mappings().all()

        return jsonify([dict(r) for r in rows]), 200

    except SQLAlchemyError as e:
        return jsonify({"error": "database_error", "details": str(e)}), 500


@app.post("/tickets/<int:ticket_id>/comments")
def add_comment(ticket_id: int):
    auth = require_api_key()
    if auth:
        return auth

    data = request.get_json(silent=True) or {}
    author = (data.get("author") or "").strip()
    body   = (data.get("body") or "").strip()

    if not author or not body:
        return jsonify({"error": "author and body required"}), 400

    try:
        with engine.begin() as conn:
            # ensure ticket exists
            exists = conn.execute(text("SELECT 1 FROM tickets WHERE id = :tid"), {"tid": ticket_id}).scalar()
            if not exists:
                return jsonify({"error": "ticket_not_found"}), 404

            conn.execute(text("""
                INSERT INTO ticket_comments (ticket_id, author, body)
                VALUES (:tid, :a, :b)
            """), {"tid": ticket_id, "a": author, "b": body})

        return jsonify({"message": "comment added"}), 201

    except SQLAlchemyError as e:
        return jsonify({"error": "database_error", "details": str(e)}), 500
