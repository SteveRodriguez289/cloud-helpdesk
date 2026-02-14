import os
import urllib.parse
from flask import Flask, request, jsonify
from sqlalchemy import create_engine, text

app = Flask(__name__)

DB_SERVER = os.environ.get("DB_SERVER")
DB_NAME = os.environ.get("DB_NAME")
DB_USER = os.environ.get("DB_USER")
DB_PASS = os.environ.get("DB_PASSWORD")

ODBC_DRIVER = os.environ.get("ODBC_DRIVER", "ODBC Driver 18 for SQL Server")

if not all([DB_SERVER, DB_NAME, DB_USER, DB_PASS]):
    raise RuntimeError("Missing required database environment variables")

odbc_str = (
    f"Driver={{{ODBC_DRIVER}}};"
    f"Server=tcp:{DB_SERVER},1433;"
    f"Database={DB_NAME};"
    f"Uid={DB_USER};"
    f"Pwd={DB_PASS};"
    "Encrypt=yes;"
    "TrustServerCertificate=no;"
    "Connection Timeout=30;"
)

connection_url = "mssql+pyodbc:///?odbc_connect=" + urllib.parse.quote_plus(odbc_str)

engine = create_engine(
    connection_url,
    pool_pre_ping=True,
    pool_recycle=1800
)

@app.get("/")
def home():
    return "Helpdesk API is running. Use GET/POST /tickets", 200

@app.get("/tickets")
def get_tickets():
    try:
        with engine.connect() as conn:
            rows = conn.execute(text("""
                SELECT id, title, description, status, created_at
                FROM tickets
                ORDER BY created_at DESC
            """)).mappings().all()
        return jsonify(list(rows)), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.post("/tickets")
def post_ticket():
    try:
        data = request.get_json(silent=True) or {}
        title = (data.get("title") or "").strip()
        description = (data.get("description") or "").strip()

        if not title or not description:
            return jsonify({"error": "title and description required"}), 400

        with engine.begin() as conn:
            conn.execute(
                text("""
                    INSERT INTO tickets (title, description)
                    VALUES (:title, :description)
                """),
                {"title": title, "description": description},
            )

        return jsonify({"message": "ticket created"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500
