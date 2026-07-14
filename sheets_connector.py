import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import streamlit as st

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


def get_client(creds_path="credentials/service_account.json"):
    """
    Authenticates with Google Sheets.

    - If running on Streamlit Community Cloud, credentials come from
      st.secrets["gcp_service_account"] (set in the app's Secrets panel).
    - If running locally, credentials come from the local JSON key file.
    """
    if "gcp_service_account" in st.secrets:
        creds_dict = dict(st.secrets["gcp_service_account"])
        creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    else:
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
