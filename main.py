import os
import json
import logging
from datetime import datetime

from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
import gspread
from google.oauth2.service_account import Credentials

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

WHO_ME  = os.environ.get("WHO_ME", "Me")
WHO_HER = os.environ.get("WHO_HER", "Her")


def get_sheet():
    creds_json = os.environ.get("GOOGLE_CREDENTIALS_JSON")
    if creds_json:
        creds_dict = json.loads(creds_json)
        creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    else:
        creds = Credentials.from_service_account_file("credentials.json", scopes=SCOPES)

    gc = gspread.authorize(creds)
    sheet_id = os.environ["GOOGLE_SHEET_ID"]
    spreadsheet = gc.open_by_key(sheet_id)

    month = datetime.now().strftime("%B %Y")
    try:
        worksheet = spreadsheet.worksheet(month)
    except gspread.WorksheetNotFound:
        worksheet = spreadsheet.add_worksheet(title=month, rows=1000, cols=6)
        worksheet.append_row(["Date", "Time", "Amount (PLN)", "Category", "Who", "Note"])
        worksheet.format("A1:F1", {"textFormat": {"bold": True}})

    return worksheet


class Expense(BaseModel):
    amount: float
    category: str
    note: str = ""
    who: str = ""


@app.get("/", response_class=HTMLResponse)
async def index():
    with open("static/index.html", "r") as f:
        html = f.read()
    html = html.replace("%%WHO_ME%%", WHO_ME).replace("%%WHO_HER%%", WHO_HER)
    return HTMLResponse(content=html)


@app.post("/log")
async def log_expense(expense: Expense):
    if expense.amount <= 0:
        raise HTTPException(status_code=400, detail="Amount must be positive")

    now = datetime.now()
    row = [
        now.strftime("%Y-%m-%d"),
        now.strftime("%H:%M"),
        round(expense.amount, 2),
        expense.category,
        expense.who or WHO_ME,
        expense.note,
    ]

    try:
        sheet = get_sheet()
        sheet.append_row(row)
        logger.info(f"Logged: {row}")
        return JSONResponse({"ok": True})
    except Exception as e:
        logger.error(f"Sheet write error: {e}")
        raise HTTPException(status_code=500, detail="Could not write to sheet")


app.mount("/static", StaticFiles(directory="static"), name="static")
