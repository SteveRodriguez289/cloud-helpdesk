import os
import urllib.parse
import logging
from datetime import datetime

from flask import Flask, request, jsonify, render_template
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

app = Flask(__name__)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("helpdesk")

DB_SERVER = os.environ.get("DB_SERVER")
DB_NAME   = os.environ.get("DB_NAME")
DB_USER   = os.environ.get("DB_USER")
DB_PASS   = os.environ.get("DB_PASSWORD")
API_KEY   = os.environ.get("API_KEY")

if not all([DB_SERVER, DB_NAME, DB_USER, DB_PASS]):
    missing = [k for k, v in {
        "DB_SERVER": DB_SERVER,
        "DB_NAME": DB_NAME,
        "DB_USER": DB_USER,
        "DB_PASSWORD": DB_PASS
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
    if not API_KEY:
        return None
    if request.headers.get("X-API-KEY") != API_KEY:
        return jsonify({"error": "Unauthorized"}), 401
    return None

def row_to_dict(row):
    d = dict(row)
    if "created_at" in d and isinstance(d["created_at"], datetime):
        d["created_at"] = d["created_at"].isoformat()
    return d

@app.get("/")
def home():
    return "Helpdesk API is running. Use GET/POST /tickets and PUT /tickets/<id>", 200

@app.get("/ui")
def ui():
    return render_template("index.html")

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
        return jsonify([row_to_dict(r) for r in rows]), 200
    except SQLAlchemyError as e:
        logger.exception("DB error in GET /tickets")
        return jsonify({"error": str(e)}), 500

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
                text("""
                    INSERT INTO tickets (title, description, status, created_at)
                    VALUES (:t, :d, 'Open', SYSUTCDATETIME())
                """),
                {"t": title, "d": description}
            )
        return jsonify({"message": "ticket created"}), 201
    except SQLAlchemyError as e:
        logger.exception("DB error in POST /tickets")
        return jsonify({"error": str(e)}), 500

@app.put("/tickets/<int:ticket_id>")
def update_ticket(ticket_id: int):
    auth = require_api_key()
    if auth:
        return auth
    data = request.get_json(silent=True) or {}
    status = (data.get("status") or "").strip()
    allowed = {"Open", "In Progress", "Closed"}
    if status not in allowed:
        return jsonify({"error": "invalid status"}), 400
    try:
        with engine.begin() as conn:
            result = conn.execute(
                text("UPDATE tickets SET status = :s WHERE id = :id"),
                {"s": status, "id": ticket_id}
            )
        if result.rowcount == 0:
            return jsonify({"error": "ticket not found"}), 404
        return jsonify({"message": "ticket updated"}), 200
    except SQLAlchemyError as e:
        logger.exception("DB error in PUT /tickets/<id>")
        return jsonify({"error": str(e)}), 500
