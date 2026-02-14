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
API_KEY   = os.environ.get("API_KEY")  # set this in Azure App Settings

if not all([DB_SERVER, DB_NAME, DB_USER, DB_PASS]):
    missing = [k for k, v in {
        "DB_SERVER": DB_SERVER,
        "DB_NAME": DB_NAME,
        "DB_USER": DB_USER,
        "DB_PASSWORD": DB_PASS,
    }.items() if not v]
    raise RuntimeError(f"Missing environment variables: {', '.join(missing)}")

if not API_KEY:
    raise RuntimeError("Missing environment variable: API_KEY")

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

@app.before_request
def require_api_key():
    # Allow these without API key
    if request.path in ("/", "/ui", "/health") or request.path.startswith("/static/"):
        return

    provided = request.headers.get("X-API-KEY", "")
    if provided != API_KEY:
        return jsonify({"error": "Unauthorized"}), 401

@app.get("/")
def index():
    return render_template("ui.html")

@app.get("/ui")
def ui():
    return render_template("ui.html")

# 2) Health check endpoint
@app.get("/health")
def health():
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return jsonify({"status": "ok", "db": "ok"}), 200
    except SQLAlchemyError:
        return jsonify({"status": "degraded", "db": "down"}), 500

@app.get("/tickets")
def get_tickets():
    try:
        with engine.connect() as conn:
            rows = conn.execute(text("""
                SELECT id, title, description, status, created_at
                FROM tickets
                ORDER BY created_at DESC
            """)).mappings().all()

        # convert RowMapping -> normal dict
        return jsonify([dict(r) for r in rows]), 200

    except SQLAlchemyError:
        return jsonify({"error": "Database query failed"}), 500

@app.post("/tickets")
def post_ticket():
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

    except SQLAlchemyError:
        return jsonify({"error": "Database insert failed"}), 500

