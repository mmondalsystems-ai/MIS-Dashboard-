OSWAL Employee Score Dashboard - Python version (all features)

What this is
- FastAPI server that reads Supabase Postgres directly and serves your Index.html.
- All 20 dashboard calls are ported from Code.gs with identical score logic
  (checked against the original Apps Script code on the same data: 0 differences).
- Index.html is unchanged except for one added line (<script src="/static/shim.js">)
  that routes google.script.run to this server.

One-time setup
1. Supabase SQL Editor: run login_users.sql
2. Spreadsheet Apps Script: add login_sync.gs, run LoginSync_pushUsers once
   (re-run it when you add a new user to the Users sheet; passwords changed
   in the dashboard live in Supabase only).
3. Copy .env.example to .env and put your Supabase "Session pooler" connection string
   in DATABASE_URL (Supabase > Project Settings > Database).

Run in VS Code
   pip install -r requirements.txt
   uvicorn app:app --reload
   open http://127.0.0.1:8000

If you change Index.html later:
   python make_index.py path/to/Index.html     (rebuilds templates/index.html)

Host on Render.com
   Build command : pip install -r requirements.txt
   Start command : uvicorn app:app --host 0.0.0.0 --port $PORT
   Environment   : DATABASE_URL

Known difference
- "Generate monthly score" no longer writes the "Monthly Score" tab in the Google
  Sheet (the server has no sheet access). The dashboard still shows all the data.
