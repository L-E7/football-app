import streamlit as st
import pandas as pd
import json
import random
import os  # <--- NEW: To check for and remove files
from datetime import datetime, timedelta
from streamlit_autorefresh import st_autorefresh

# --- 1. Page Configuration (No changes here) ---
st.set_page_config(
    page_title="Football Tournament Manager",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 2. Improved High-Contrast Theme CSS Block (No changes here) ---
st.markdown("""
<style>
    /* ... CSS remains the same ... */
    .stApp { background-color: #FFFFFF; color: #212529; }
    .stApp h1 { font-size: 3rem; font-weight: bold; color: #198754; text-align: center; padding-bottom: 20px; }
    .stApp h2, .stApp h3 { color: #198754; }
    [data-testid="stSidebar"] { background-color: #F8F9FA; }
    button[kind="primary"] { background-color: #198754; color: white; border: none; }
    button[kind="primary"]:hover { background-color: #157347; color: white; border: none; }
    button[kind="primary"]:disabled { background-color: #a0d1b9; color: #e9e9e9; }
    .st-emotion-cache-1g8sf34 { font-size: 1.1rem; color: #495057; }
</style>
""", unsafe_allow_html=True)

# --- CONSTANTS ---
ACTIVE_TOURNAMENT_FILE = 'active_tournament_state.json'
TOURNAMENT_HISTORY_FILE = 'tournaments.json'


# ---------- Utility Functions (Translated Column Names) ----------
# (No changes in these functions, but we will add new ones)
def load_players_from_excel(file):
    df = pd.read_excel(file, engine='openpyxl')
    return df['Player'].dropna().tolist()

def save_json(data, filename):
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_json(filename):
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return []

# <--- NEW HELPER FUNCTIONS FOR STATE PERSISTENCE --- >
def save_active_tournament():
    """Saves the essential parts of the session state to a file."""
    if 'tournament' in st.session_state and st.session_state.tournament:
        state_to_save = {
            'tournament': st.session_state.tournament,
            'matches': st.session_state.matches,
            'elapsed_time_seconds': st.session_state.elapsed_time.total_seconds(),
            'g1': st.session_state.get('g1', 0),
            'g2': st.session_state.get('g2', 0),
            'goal_events': st.session_state.goal_events,
            'substitutions': st.session_state.substitutions
        }
        save_json(state_to_save, ACTIVE_TOURNAMENT_FILE)

def load_active_tournament():
    """Loads state from the file into the session_state if it exists."""
    if os.path.exists(ACTIVE_TOURNAMENT_FILE):
        try:
            state = load_json(ACTIVE_TOURNAMENT_FILE)
            st.session_state.tournament = state['tournament']
            st.session_state.matches = state['matches']
            st.session_state.elapsed_time = timedelta(seconds=state.get('elapsed_time_seconds', 0))
            st.session_state.g1 = state.get('g1', 0)
            st.session_state.g2 = state.get('g2', 0)
            st.session_state.goal_events = state.get('goal_events', [])
            st.session_state.substitutions = state.get('substitutions', {})
            # We are not resuming a running timer, user must press resume
            st.session_state.timer_running = False 
            st.session_state.timer_start_time = None 
            return True
        except (json.JSONDecodeError, KeyError):
            # If file is corrupted, remove it and start fresh
            os.remove(ACTIVE_TOURNAMENT_FILE)
            return False
    return False

# <--- END OF NEW HELPER FUNCTIONS --- >

def calculate_team_stats(matches, teams):
    # ... (function is unchanged)
    stats = {str(i): {'Played': 0, 'Wins': 0, 'Draws': 0, 'Losses': 0,
                      'Goals For': 0, 'Goals Against': 0} for i in range(1, teams+1)}
    for m in matches:
        t1, t2 = m['teams']
        g1, g2 = m['score']
        stats[t1]['Played'] += 1; stats[t2]['Played'] += 1
        stats[t1]['Goals For'] += g1; stats[t1]['Goals Against'] += g2
        stats[t2]['Goals For'] += g2; stats[t2]['Goals Against'] += g1
        if g1 > g2: stats[t1]['Wins'] += 1; stats[t2]['Losses'] += 1
        elif g2 > g1: stats[t2]['Wins'] += 1; stats[t1]['Losses'] += 1
        else: stats[t1]['Draws'] += 1; stats[t2]['Draws'] += 1
    for s in stats.values():
        s['Goal Diff.'] = s['Goals For'] - s['Goals Against']
        s['Points'] = s['Wins'] * 3 + s['Draws']
    return pd.DataFrame.from_dict(stats, orient='index')

def calculate_player_stats(matches):
    # ... (function is unchanged)
    stats = {}
    for m in matches:
        rosters_for_stats = m.get('original_players', m['players'])
        players_in_match = [p for team_players in rosters_for_stats.values() for p in team_players]
        for p in players_in_match:
            if p not in stats: stats[p] = {'Played': 0, 'Wins': 0, 'Draws': 0, 'Losses': 0, 'Goals': 0, 'Assists': 0}
            stats[p]['Played'] += 1
        winner = None
        if m['score'][0] > m['score'][1]: winner = m['teams'][0]
        elif m['score'][1] > m['score'][0]: winner = m['teams'][1]
        for team_id, players in rosters_for_stats.items():
            for p in players:
                if winner == team_id: stats[p]['Wins'] += 1
                elif winner is None: stats[p]['Draws'] += 1
                else: stats[p]['Losses'] += 1
        for p in m['scorers']:
            if p in stats: stats[p]['Goals'] += 1
        for p in m['assists']:
            if p in stats: stats[p]['Assists'] += 1
    for s in stats.values():
        s['Fantasy Points'] = s['Wins'] + s['Assists'] + s['Goals'] * 2
    return pd.DataFrame.from_dict(stats, orient='index')


# ---------- App State Initialization ----------
# <--- MODIFIED: This section now handles loading the persisted state --- >
if 'initialized' not in st.session_state:
    st.session_state.players = []
    st.session_state.tournament = {}
    st.session_state.matches = []
    st.session_state.history = load_json(TOURNAMENT_HISTORY_FILE)
    st.session_state.menu = "Start a New Tournament"
    st.session_state.timer_running = False
    st.session_state.timer_start_time = None
    st.session_state.elapsed_time = timedelta(0)
    st.session_state.goal_events = []
    st.session_state.substitutions = {}
    
    # Attempt to load an active tournament
    if load_active_tournament():
        st.session_state.menu = "Live Match Management"
        st.toast("Resumed your previous tournament! ⚽")

    st.session_state.initialized = True # Mark as initialized

# ---------- Sidebar Menu (Translated) ----------
st.sidebar.title("Navigation Menu")
# ... (rest of sidebar is unchanged)
menu_options = { "Start a New Tournament": "📅", "Live Match Management": "🎮", "Finish Tournament": "🏆", "Tournament History": "📜"}
menu_selection = st.sidebar.radio("Select a screen:", options=menu_options.keys(), format_func=lambda option: f"{menu_options[option]} {option}", key="menu_selection")
st.session_state.menu = menu_selection

st.title("Football Tournament Manager")

# ---------- App Logic (Translated and Improved) ----------

# ---------- Start Tournament ----------
if st.session_state.menu == "Start a New Tournament":
    # <--- NEW: Prevent starting a new one if an active one exists --- >
    if os.path.exists(ACTIVE_TOURNAMENT_FILE):
        st.warning("An active tournament is already in progress.")
        st.info("Please navigate to 'Live Match Management' to continue or 'Finish Tournament' to end it.")
    else:
        st.header("New Tournament Setup")
        excel_file = st.file_uploader("Import players from an Excel file (Column must be named 'Player')", type=['xlsx'])
        if excel_file: st.session_state.players = load_players_from_excel(excel_file)
        num_teams = st.selectbox("Number of teams", [2, 3, 4], index=1)
        team_players = {}
        assigned_players = set()
        cols = st.columns(num_teams)
        for i in range(1, num_teams + 1):
            with cols[i-1]:
                available_players = [p for p in st.session_state.players if p not in assigned_players]
                selected = st.multiselect(f"Team {i} Players", options=available_players, key=f"team_{i}", max_selections=6)
                if len(selected) > 6: st.warning(f"Team {i} cannot have more than 6 players.")
                team_players[str(i)] = selected
                assigned_players.update(selected)
        st.markdown("---")
        st.subheader("Opening Match")
        col1, col2 = st.columns(2)
        with col1: team1 = st.selectbox("First Team", list(range(1, num_teams+1)), index=0)
        with col2: team2 = st.selectbox("Second Team", list(range(1, num_teams+1)), index=1)
        
        if st.button("Let's start to play ⚽"):
            if team1 == team2: st.error("You must select two different teams for the opening match.")
            else:
                st.session_state.tournament = {'date': str(datetime.today().date()), 'teams': num_teams, 'players': team_players, 'current_match': [str(team1), str(team2)], 'history': [], 'streak': {str(i): 0 for i in range(1, num_teams+1)}}
                st.session_state.matches = []
                st.session_state.menu = "Live Match Management"
                st.session_state.timer_running = False; st.session_state.timer_start_time = None
                st.session_state.elapsed_time = timedelta(0); st.session_state.goal_events = []
                st.session_state.substitutions = {}; st.session_state.g1 = 0; st.session_state.g2 = 0
                
                save_active_tournament() # <--- NEW: Save state on creation
                st.rerun()

# ---------- Live Match ----------
elif st.session_state.menu == "Live Match Management" and st.session_state.tournament:
    # ... (most of this section is the same, but we add saves on action)
    if st.session_state.timer_running: st_autorefresh(interval=1000, key="timer_refresh")
    tm = st.session_state.tournament; t1, t2 = tm['current_match']
    if st.session_state.timer_running: total_elapsed = st.session_state.elapsed_time + (datetime.now() - st.session_state.timer_start_time)
    else: total_elapsed = st.session_state.elapsed_time
    minutes, seconds = divmod(int(total_elapsed.total_seconds()), 60)
    st.header(f"Team {t1} ⚔️ Team {t2}"); st.metric(label="⏱️ Game Time", value=f"{minutes:02d}:{seconds:02d}")
    c1, c2, c3 = st.columns(3)
    if not st.session_state.timer_running and st.session_state.timer_start_time is None:
        if c1.button("▶️ Start Timer"):
            st.session_state.timer_start_time = datetime.now(); st.session_state.timer_running = True
            st.rerun()
    if st.session_state.timer_running:
        if c2.button("⏸️ Pause Timer"):
            st.session_state.elapsed_time += datetime.now() - st.session_state.timer_start_time
            st.session_state.timer_running = False
            save_active_tournament() # <--- NEW: Save state on pause
            st.rerun()
    if not st.session_state.timer_running and st.session_state.timer_start_time is not None:
        if c3.button("▶️ Resume Timer"):
            st.session_state.timer_start_time = datetime.now(); st.session_state.timer_running = True
            st.rerun()
    st.markdown("---"); st.subheader("🥅 Match Score")
    col1, col2 = st.columns(2)
    with col1: g1 = st.number_input(f"Team {t1} Goals", min_value=0, step=1, key='g1', on_change=save_active_tournament) # <--- NEW
    with col2: g2 = st.number_input(f"Team {t2} Goals", min_value=0, step=1, key='g2', on_change=save_active_tournament) # <--- NEW

    with st.expander("🔄 Make Substitutions for the Current Match"):
        all_teams_ids = list(tm['players'].keys()); resting_teams_ids = [t for t in all_teams_ids if t not in [t1, t2]]
        sub_pool = [p for team_id in resting_teams_ids for p in tm['players'][team_id]]
        if not sub_pool: st.info("There are no available players to substitute (all teams are playing).")
        else:
            playing_players = tm['players'][t1] + tm['players'][t2]
            player_to_replace = st.selectbox("Player to replace:", options=playing_players)
            substitute_player = st.selectbox("Substitute player:", options=sub_pool)
            if st.button("Make Substitution"):
                st.session_state.substitutions[player_to_replace] = substitute_player
                save_active_tournament() # <--- NEW: Save state on substitution
                st.success(f"{substitute_player} is now substituting for {player_to_replace}!")
                st.rerun()

    # ... (rest of match logic is the same)
    if st.session_state.substitutions:
        st.write("Active Substitutions:")
        sub_list = [f"**{v}** (In) ↔️ **{k}** (Out)" for k, v in st.session_state.substitutions.items()]
        st.markdown("\n".join(f"- {s}" for s in sub_list))
    original_players_t1 = tm['players'][t1]; original_players_t2 = tm['players'][t2]
    match_players_t1 = [st.session_state.substitutions.get(p, p) for p in original_players_t1]
    match_players_t2 = [st.session_state.substitutions.get(p, p) for p in original_players_t2]
    all_players_in_match = match_players_t1 + match_players_t2
    total_goals = g1 + g2
    while len(st.session_state.goal_events) < total_goals: st.session_state.goal_events.append({'scorer': None, 'assister': None})
    while len(st.session_state.goal_events) > total_goals: st.session_state.goal_events.pop()
    if total_goals > 0:
        st.markdown("---"); st.subheader("⚽ Log Scorers and Assisters")
        for i in range(total_goals):
            col_s, col_a = st.columns(2)
            with col_s: st.session_state.goal_events[i]['scorer'] = st.selectbox(f"Scorer for Goal {i+1}", options=all_players_in_match, key=f"scorer_{i}", on_change=save_active_tournament) # <--- NEW
            with col_a: st.session_state.goal_events[i]['assister'] = st.selectbox(f"Assister for Goal {i+1}", options=["-- No Assist --"] + all_players_in_match, key=f"assister_{i}", on_change=save_active_tournament) # <--- NEW
    
    st.markdown("---")
    if st.session_state.timer_start_time is None: st.info("Start the timer before you can finish the match.")

    if st.button("🏁 Finish & Calculate Match", type="primary", disabled=(st.session_state.timer_start_time is None)):
        scorers = [event['scorer'] for event in st.session_state.goal_events if event['scorer']]
        assists = [event['assister'] for event in st.session_state.goal_events if event['assister'] and event['assister'] != "-- No Assist --"]
        match = {'teams': [t1, t2], 'score': [g1, g2], 'scorers': scorers, 'assists': assists, 'players': {t1: match_players_t1, t2: match_players_t2}, 'original_players': {t1: original_players_t1, t2: original_players_t2}}
        st.session_state.matches.append(match); tm['history'].append(match)
        for t in [t1, t2]: tm['streak'][t] += 1
        winner, loser = (t1, t2) if g1 > g2 else ((t2, t1) if g2 > g1 else (None, None))
        if winner is None:
            if len(st.session_state.matches) == 1: winner = random.choice([t1, t2])
            else:
                prev_match_teams = st.session_state.matches[-2]['teams']
                winner = t2 if t1 in prev_match_teams else t1
            loser = t1 if winner == t2 else t2
        all_teams_ids = list(tm['players'].keys()); next_opponent = next((t for t in all_teams_ids if t not in [t1, t2]), None)
        if tm['streak'].get(winner, 0) >= 3 and next_opponent:
            tm['current_match'] = sorted([next_opponent, loser]); tm['streak'][winner] = 0
        elif next_opponent: tm['current_match'] = sorted([winner, next_opponent])
        else: tm['current_match'] = sorted([winner, loser])
        st.session_state.timer_running = False; st.session_state.timer_start_time = None
        st.session_state.elapsed_time = timedelta(0); st.session_state.goal_events = []
        st.session_state.substitutions = {}; st.session_state.g1 = 0; st.session_state.g2 = 0
        
        save_active_tournament() # <--- NEW: Save state after match calculation
        st.rerun()

# ---------- Finish Tournament & History ----------
elif st.session_state.menu == "Finish Tournament" and st.session_state.tournament:
    st.header("🏁 Final Results")
    tm = st.session_state.tournament
    df_teams = calculate_team_stats(tm['history'], tm['teams'])
    df_players = calculate_player_stats(tm['history'])
    st.subheader("📊 Team Standings"); st.dataframe(df_teams.sort_values(by=['Points', 'Goal Diff.', 'Goals For'], ascending=False), use_container_width=True)
    st.subheader("🏅 Player Leaderboard"); st.dataframe(df_players.sort_values(by=['Fantasy Points', 'Goals', 'Assists'], ascending=False), use_container_width=True)

    if st.button("💾 Save Tournament & Start New"):
        st.session_state.history.append(tm)
        save_json(st.session_state.history, TOURNAMENT_HISTORY_FILE)
        st.success("Tournament saved to history!")
        st.balloons()
        st.session_state.tournament = {}; st.session_state.menu = "Start a New Tournament"
        if os.path.exists(ACTIVE_TOURNAMENT_FILE): # <--- NEW: Clean up the active state file
            os.remove(ACTIVE_TOURNAMENT_FILE)
        st.rerun()

elif st.session_state.menu == "Tournament History":
    # ... (this section is unchanged)
    st.header("📜 Tournament History")
    if not st.session_state.history: st.info("There are no saved tournaments in the history yet.")
    for i, t in enumerate(reversed(st.session_state.history)):
        with st.expander(f"Tournament from Date: {t['date']}"):
            df_teams = calculate_team_stats(t['history'], t['teams'])
            df_players = calculate_player_stats(t['history'])
            st.subheader("📊 Team Standings"); st.dataframe(df_teams.sort_values(by=['Points', 'Goal Diff.', 'Goals For'], ascending=False), use_container_width=True)
            st.subheader("🏅 Player Leaderboard"); st.dataframe(df_players.sort_values(by=['Fantasy Points', 'Goals', 'Assists'], ascending=False), use_container_width=True)
            st.download_button(label="📥 Download Tournament Data (JSON)", data=json.dumps(t, indent=2), file_name=f"tournament_{t['date']}_{i}.json", mime="application/json")