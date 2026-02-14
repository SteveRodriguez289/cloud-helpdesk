import os
import urllib.parse
from flask import Flask, request, jsonify, render_template, make_response
from sqlalchemy import create_engine, text

app = Flask(__name__)

# -------------------------
# Config (Azure App Settings)
# -------------------------
DB_SERVER = os.environ.get("DB_SERVER")
DB_NAME   = os.environ.get("DB_NAME")
DB_USER   = os.environ.get("DB_USER")
DB_PASS   = os.environ.get("DB_PASSWORD")

API_KEY = os.environ.get("API_KEY", "").strip()  # set this in Azure App Settings

if not all([DB_SERVER, DB_NAME, DB_USER, DB_PASS]):
    missing = [k for k, v in {
        "DB_SERVER": DB_SERVER,
        "DB_NAME": DB_NAME,
        "DB_USER": DB_USER,
        "DB_PASSWORD": DB_PASS
    }.items() if not v]
    raise RuntimeError(f"Missing environment variables: {', '.join(missing)}")

# ODBC Driver 18 is recommended on Azure
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

# -------------------------
# DB init (auto-create table)
# -------------------------
def init_db():
    with engine.begin() as conn:
        conn.execute(text("""
        IF OBJECT_ID('dbo.tickets', 'U') IS NULL
        BEGIN
            CREATE TABLE dbo.tickets (
                id INT IDENTITY(1,1) PRIMARY KEY,
                title NVARCHAR(255) NOT NULL,
                description NVARCHAR(MAX) NOT NULL,
                status NVARCHAR(50) NOT NULL DEFAULT 'Open',
                created_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
            );
        END
        """))

init_db()

# -------------------------
# Auth helper (Header or Cookie)
# -------------------------
PUBLIC_PATHS = {"/", "/ui", "/login", "/health", "/openapi.json", "/docs"}

@app.before_request
def require_key():
    if not API_KEY:
        return  # if API_KEY not set, no auth required

    if request.path in PUBLIC_PATHS or request.path.startswith("/static/"):
        return

    key = request.headers.get("X-API-KEY") or request.cookies.get("api_key")
    if key != API_KEY:
        return jsonify({"error": "unauthorized"}), 401

# -------------------------
# Pages
# -------------------------
@app.get("/")
def home():
    return "Helpdesk API is running. Visit /ui", 200

@app.get("/health")
def health():
    return jsonify({"ok": True}), 200

@app.get("/ui")
def ui():
    return render_template("ui.html"), 200

@app.post("/login")
def login():
    data = request.get_json(silent=True) or {}
    key = (data.get("api_key") or "").strip()

    if not API_KEY:
        return jsonify({"message": "API_KEY not set on server; login not required"}), 200

    if key != API_KEY:
        return jsonify({"error": "invalid key"}), 401

    resp = make_response(jsonify({"message": "logged in"}), 200)
    resp.set_cookie("api_key", key, httponly=True, samesite="Lax", secure=True)
    return resp

# -------------------------
# API
# -------------------------
@app.get("/tickets")
def get_tickets():
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT id, title, description, status, created_at
            FROM dbo.tickets
            ORDER BY created_at DESC
        """)).mappings().all()

    # convert RowMapping -> dict
    return jsonify([dict(r) for r in rows]), 200

@app.get("/tickets/<int:ticket_id>")
def get_ticket(ticket_id: int):
    with engine.connect() as conn:
        row = conn.execute(
            text("""
                SELECT id, title, description, status, created_at
                FROM dbo.tickets
                WHERE id = :id
            """),
            {"id": ticket_id},
        ).mappings().first()

    if not row:
        return jsonify({"error": "not found"}), 404
    return jsonify(dict(row)), 200

@app.post("/tickets")
def post_ticket():
    data = request.get_json(silent=True) or {}
    title = (data.get("title") or "").strip()
    description = (data.get("description") or "").strip()

    if not title or not description:
        return jsonify({"error": "title and description required"}), 400

    with engine.begin() as conn:
        conn.execute(
            text("INSERT INTO dbo.tickets (title, description) VALUES (:t, :d)"),
            {"t": title, "d": description},
        )

    return jsonify({"message": "ticket created"}), 201

@app.patch("/tickets/<int:ticket_id>")
def update_ticket(ticket_id: int):
    data = request.get_json(silent=True) or {}
    status = (data.get("status") or "").strip()

    if status not in {"Open", "In Progress", "Closed"}:
        return jsonify({"error": "status must be Open, In Progress, or Closed"}), 400

    with engine.begin() as conn:
        res = conn.execute(
            text("UPDATE dbo.tickets SET status = :s WHERE id = :id"),
            {"s": status, "id": ticket_id},
        )
        if res.rowcount == 0:
            return jsonify({"error": "not found"}), 404

    return jsonify({"message": "ticket updated"}), 200

@app.delete("/tickets/<int:ticket_id>")
def delete_ticket(ticket_id: int):
    with engine.begin() as conn:
        res = conn.execute(
            text("DELETE FROM dbo.tickets WHERE id = :id"),
            {"id": ticket_id},
        )
        if res.rowcount == 0:
            return jsonify({"error": "not found"}), 404

    return jsonify({"message": "ticket deleted"}), 200

# -------------------------
# OpenAPI + Docs (no extra packages)
# -------------------------
@app.get("/openapi.json")
def openapi():
    spec = {
        "openapi": "3.0.0",
        "info": {"title": "Helpdesk API", "version": "1.0.0"},
        "servers": [{"url": request.host_url.rstrip("/")}],
        "paths": {
            "/tickets": {
                "get": {
                    "summary": "List tickets",
                    "responses": {"200": {"description": "OK"}}
                },
                "post": {
                    "summary": "Create ticket",
                    "requestBody": {"required": True},
                    "responses": {"201": {"description": "Created"}}
                }
            },
            "/tickets/{id}": {
                "get": {
                    "summary": "Get one ticket",
                    "parameters": [{"name": "id", "in": "path", "required": True, "schema": {"type": "integer"}}],
                    "responses": {"200": {"description": "OK"}, "404": {"description": "Not found"}}
                },
                "patch": {
                    "summary": "Update ticket status",
                    "parameters": [{"name": "id", "in": "path", "required": True, "schema": {"type": "integer"}}],
                    "requestBody": {"required": True},
                    "responses": {"200": {"description": "OK"}, "400": {"description": "Bad Request"}, "404": {"description": "Not found"}}
                },
                "delete": {
                    "summary": "Delete ticket",
                    "parameters": [{"name": "id", "in": "path", "required": True, "schema": {"type": "integer"}}],
                    "responses": {"200": {"description": "OK"}, "404": {"description": "Not found"}}
                }
            }
        }
    }
    return jsonify(spec), 200

@app.get("/docs")
def docs():
    # Swagger UI via CDN (free)
    html = f"""
<!doctype html>
<html>
  <head>
    <meta charset="utf-8" />
    <title>Helpdesk API Docs</title>
    <link rel="stylesheet" href="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css" />
  </head>
  <body>
    <div id="swagger"></div>
    <script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
    <script>
      window.ui = SwaggerUIBundle({{
        url: "/openapi.json",
        dom_id: "#swagger"
      }});
    </script>
  </body>
</html>
"""
    return html, 200
