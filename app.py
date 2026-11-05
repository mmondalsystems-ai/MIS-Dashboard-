import json
import os
import traceback
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

import logic

app = FastAPI()
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# On Vercel the files in public/ are served by the CDN. This mount makes the same
# URL (/static/shim.js) work when you run the app locally with uvicorn.
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "public", "static")), name="static")

# Every function the page calls through google.script.run.
EXPOSED = [
    "validateLogin", "changePassword", "getLoginUsernames", "getAllEmployees",
    "getAvailableWeeks", "getDepartmentDirectory", "getDepartmentScoreSummary",
    "getChecklistData", "getFmsData", "getEmployeeData", "getMonthlyFmsPeriods",
    "getMonthlyEmployeeData", "getWeeklyScoreSummary", "getHoDepartmentWiseWeeklyScoreSummary",
    "getMonthlyDepartmentWiseScoreSummary", "getDepartmentWiseWeeklyScoreSummary",
    "getMonthlyScoreData", "getMonthlyTeamScoreData", "generateMonthlyTeamScoreSheet",
    "getFollowupScoreData",
]
FUNCS = {name: getattr(logic, name) for name in EXPOSED}


@app.get("/", response_class=HTMLResponse)
def home():
    path = os.path.join(BASE_DIR, "templates", "index.html")
    with open(path, encoding="utf-8") as f:
        return f.read()


@app.post("/api/{fn}")
async def api(fn: str, request: Request):
    body = await request.json()
    args = body.get("args", [])
    func = FUNCS.get(fn)
    if func is None:
        return JSONResponse({"ok": False, "error": "Not ported yet: " + fn})
    try:
        return {"ok": True, "result": func(*args)}
    except Exception as e:
        traceback.print_exc()
        return JSONResponse({"ok": False, "error": str(e)})


@app.on_event("shutdown")
def _close_pool():
    try:
        import db
        if db._pool is not None:
            db._pool.close()
    except Exception:
        pass


@app.get("/health")
def health():
    return {"ok": True}
