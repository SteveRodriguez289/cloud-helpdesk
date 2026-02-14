import os
import urllib.parse
from flask import Flask, request, jsonify
from sqlalchemy import create_engine, text

app = Flask(__name__)

DB_SERVER = os.environ.get("DB_SERVER")
DB_NAME   = os.environ.get("DB_NAME")
DB_USER   = os.environ.get("DB_USER")
DB_PASS   = os.environ.get("DB_PASSWORD")

if not all([DB_SERVER, DB_NAME, DB_USER, DB_PASS]):
    missing = [k for k,v in {
        "DB_SERVER": DB_SERVER, "DB_NAME": DB_NAME, "DB_USER": DB_USER, "DB_PASSWORD": DB_PASS
    }.items() if not v]
    raise RuntimeError(f"Missing environment variables: {', '.join(missing)}")

odbc = (
    f"Driver={{ODBC Driver 17 for SQL Server}};"
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
print("DB_SERVER =", DB_SERVER)
print("DB_NAME   =", DB_NAME)
print("DB_USER   =", DB_USER)


@app.get("/")
def home():
    return "Helpdesk API is running. Use GET/POST /tickets", 200

@app.get("/tickets")
def get_tickets():
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT id, title, description, status, created_at
            FROM tickets
            ORDER BY created_at DESC
        """)).mappings().all()
    return jsonify(list(rows)), 200

@app.post("/tickets")
def post_ticket():
    data = request.get_json(silent=True) or {}
    title = (data.get("title") or "").strip()
    description = (data.get("description") or "").strip()
    if not title or not description:
        return jsonify({"error": "title and description required"}), 400

    with engine.begin() as conn:
        conn.execute(
            text("INSERT INTO tickets (title, description) VALUES (:t, :d)"),
            {"t": title, "d": description},
        )
    return jsonify({"message": "ticket created"}), 201
