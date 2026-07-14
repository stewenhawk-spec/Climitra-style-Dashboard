import gspread
from google.oauth2.service_account import Credentials
import pandas as pd

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

def get_client(creds_path="credentials/service_account.json"):
    creds = Credentials.from_service_account_file(creds_path, scopes=SCOPES)
    return gspread.authorize(creds)

def read_worksheet(sheet_id, worksheet_name, creds_path="credentials/service_account.json"):
    client = get_client(creds_path)
    sheet = client.open_by_key(sheet_id)
    ws = sheet.worksheet(worksheet_name)
    return pd.DataFrame(ws.get_all_records())

def write_worksheet(sheet_id, worksheet_name, df, creds_path="credentials/service_account.json"):
    client = get_client(creds_path)
    sheet = client.open_by_key(sheet_id)
    ws = sheet.worksheet(worksheet_name)
    ws.clear()
    ws.update([df.columns.values.tolist()] + df.values.tolist())