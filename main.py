import os
import json
import logging
import calendar
from datetime import datetime
from collections import defaultdict

from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
import gspread
from google.oauth2.service_account import Credentials

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

SCOPES    = ["https://www.googleapis.com/auth/spreadsheets"]
WHO_ME    = os.environ.get("WHO_ME", "Me")
WHO_HER   = os.environ.get("WHO_HER", "Her")

MONTH_NAMES = [
    "January","February","March","April","May","June",
    "July","August","September","October","November","December"
]


def get_spreadsheet():
    creds_json = os.environ.get("GOOGLE_CREDENTIALS_JSON")
    if creds_json:
        creds = Credentials.from_service_account_info(json.loads(creds_json), scopes=SCOPES)
    else:
        creds = Credentials.from_service_account_file("credentials.json", scopes=SCOPES)
    gc = gspread.authorize(creds)
    return gc.open_by_key(os.environ["GOOGLE_SHEET_ID"])


def get_or_create_sheet(spreadsheet, month_name: str):
    try:
        return spreadsheet.worksheet(month_name)
    except gspread.WorksheetNotFound:
        ws = spreadsheet.add_worksheet(title=month_name, rows=1000, cols=6)
        ws.append_row(["Date", "Time", "Amount (PLN)", "Category", "Who", "Note"])
        ws.format("A1:F1", {"textFormat": {"bold": True}})
        return ws


def parse_records(records: list) -> list:
    """Return list of dicts with amount as float, skip header/bad rows."""
    out = []
    for r in records:
        try:
            amount = float(str(r.get("Amount (PLN)", 0)).replace(",", "."))
            if amount <= 0:
                continue
            out.append({
                "amount":   amount,
                "category": str(r.get("Category", "other")).strip().lower() or "other",
                "who":      str(r.get("Who", "")).strip(),
                "date":     str(r.get("Date", "")),
            })
        except (ValueError, TypeError):
            continue
    return out


# ── Routes ──────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def index():
    with open("static/index.html") as f:
        html = f.read()
    html = html.replace("%%WHO_ME%%", WHO_ME).replace("%%WHO_HER%%", WHO_HER)
    return HTMLResponse(content=html)


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard():
    with open("static/dashboard.html") as f:
        return HTMLResponse(content=f.read())


class Expense(BaseModel):
    amount:   float
    category: str
    note:     str = ""
    who:      str = ""


@app.post("/log")
async def log_expense(expense: Expense):
    if expense.amount <= 0:
        raise HTTPException(status_code=400, detail="Amount must be positive")

    now = datetime.now()
    month_name = now.strftime("%B %Y")
    row = [
        now.strftime("%Y-%m-%d"),
        now.strftime("%H:%M"),
        round(expense.amount, 2),
        expense.category,
        expense.who or WHO_ME,
        expense.note,
    ]

    try:
        ss = get_spreadsheet()
        ws = get_or_create_sheet(ss, month_name)
        ws.append_row(row)
        logger.info(f"Logged: {row}")
        return JSONResponse({"ok": True})
    except Exception as e:
        logger.error(f"Sheet write error: {e}")
        raise HTTPException(status_code=500, detail="Could not write to sheet")


@app.get("/api/dashboard")
async def api_dashboard(
    month: str = Query(..., description="Sheet tab name e.g. 'June 2026'"),
    year:  int = Query(...),
):
    try:
        ss = get_spreadsheet()
        all_sheets = {ws.title: ws for ws in ss.worksheets()}
    except Exception as e:
        logger.error(f"Spreadsheet access error: {e}")
        raise HTTPException(status_code=500, detail="Cannot access spreadsheet")

    # ── Current month data ──
    current_records = []
    if month in all_sheets:
        try:
            current_records = parse_records(all_sheets[month].get_all_records())
        except Exception as e:
            logger.error(f"Error reading sheet {month}: {e}")

    total = sum(r["amount"] for r in current_records)

    # Category breakdown, sorted by total desc
    cat_totals: dict[str, float] = defaultdict(float)
    for r in current_records:
        cat_totals[r["category"]] += r["amount"]
    categories = sorted(
        [{"name": k, "total": round(v, 2)} for k, v in cat_totals.items()],
        key=lambda x: -x["total"]
    )

    # Who split
    who_totals: dict[str, float] = defaultdict(float)
    for r in current_records:
        who_totals[r["who"]] += r["amount"]
    who_split = sorted(
        [{"who": k, "total": round(v, 2)} for k, v in who_totals.items()],
        key=lambda x: -x["total"]
    )

    # ── Month-over-month: collect up to 6 months ending at current ──
    month_idx = MONTH_NAMES.index(month.split(" ")[0]) if month.split(" ")[0] in MONTH_NAMES else -1
    monthly_totals = []

    if month_idx >= 0:
        for delta in range(5, -1, -1):   # 5 months ago → current
            m_idx = month_idx - delta
            m_year = year
            if m_idx < 0:
                m_idx += 12
                m_year -= 1
            tab = f"{MONTH_NAMES[m_idx]} {m_year}"
            if tab not in all_sheets:
                continue
            try:
                records = parse_records(all_sheets[tab].get_all_records())
            except Exception:
                continue
            if not records:
                continue
            ct: dict[str, float] = defaultdict(float)
            for r in records:
                ct[r["category"]] += r["amount"]
            monthly_totals.append({
                "month": tab,
                "total": round(sum(ct.values()), 2),
                "categories": [{"name": k, "total": round(v, 2)} for k, v in ct.items()],
            })

    # Days in month
    try:
        m_name, m_year_str = month.rsplit(" ", 1)
        m_num = MONTH_NAMES.index(m_name) + 1
        days_in_month = calendar.monthrange(int(m_year_str), m_num)[1]
    except Exception:
        days_in_month = 30

    return JSONResponse({
        "total":          round(total, 2),
        "days_in_month":  days_in_month,
        "categories":     categories,
        "who_split":      who_split,
        "monthly_totals": monthly_totals,
    })


app.mount("/static", StaticFiles(directory="static"), name="static")
