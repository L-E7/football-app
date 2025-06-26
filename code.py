import streamlit as st
import pandas as pd
import json
import random
from datetime import datetime, timedelta
from streamlit_autorefresh import st_autorefresh
# --- NEW IMPORTS ---
import gspread
from gspread_dataframe import get_as_dataframe, set_with_dataframe

# --- Page Configuration and CSS (No changes) ---
st.set_page_config(...)
st.markdown("""<style>...</style>""", unsafe_allow_html=True)


# --- NEW: gspread Connection Logic ---
# This uses the secrets from your .streamlit/secrets.toml file
try:
    gc = gspread.service_account_from_dict(st.secrets["gcp_service_account"])
    # Open the Google Sheet by its name
    SHEET_NAME = "FootballAppDatabase" # Make sure this matches your Google Sheet file name
    sh = gc.open(SHEET_NAME)
    worksheet = sh.worksheet("tournaments") # Get the specific tab
except Exception as e:
    st.error(f"Could not connect to Google Sheets. Please ensure your `secrets.toml` is configured correctly. Error: {e}")
    st.stop()


# --- NEW: Function to load history using gspread ---
def load_history_from_sheets():
    df = get_as_dataframe(worksheet, evaluate_formulas=True).dropna(how='all')
    history_list = []
    for index, row in df.iterrows():
        try:
            tournament = {
                'tournament_id': row['tournament_id'], 'date': row['date'], 'teams': int(row['teams']),
                'players': json.loads(row['players'].replace("'", '"')), 
                'history': json.loads(row['history'].replace("'", '"'))
            }
            history_list.append(tournament)
        except (json.JSONDecodeError, TypeError, KeyError) as e:
            st.warning(f"Could not parse a row from history: {e}")
            continue
    return history_list

# --- NEW: Function to save a tournament using gspread ---
def save_tournament_to_sheets(tournament_data):
    # Get the existing data from the sheet
    existing_df = get_as_dataframe(worksheet, evaluate_formulas=True).dropna(how='all')
    
    # Prepare the new tournament data
    new_data = {
        'tournament_id': tournament_data.get('date') + "_" + str(random.randint(1000, 9999)),
        'date': tournament_data.get('date'), 'teams': tournament_data.get('teams'),
        'players': json.dumps(tournament_data.get('players', {})),
        'history': json.dumps(tournament_data.get('history', []))
    }
    new_df = pd.DataFrame([new_data])
    
    # Append the new data to the existing data
    updated_df = pd.concat([existing_df, new_df], ignore_index=True)
    
    # Write the entire updated DataFrame back to the sheet
    set_with_dataframe(worksheet, updated_df)


# ---------- [The rest of your code remains exactly the same] ----------
# For brevity, I'll omit the rest of the code as it doesn't need to change.
# Just make sure the three parts above (requirements, secrets, and the connection/load/save functions in code.py)
# are updated.
#
# The parts that need updating are:
# 1. The imports at the top of the file.
# 2. The connection logic.
# 3. The load_history_from_sheets function.
# 4. The save_tournament_to_sheets function.
#
# The rest of your app (state management, UI tabs, etc.) can stay as it is.