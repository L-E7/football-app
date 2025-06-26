import streamlit as st
import pandas as pd
import json
import random
from datetime import datetime, timedelta
from streamlit_autorefresh import st_autorefresh
from streamlit_gsheets import GSheetsConnection

# --- Page Configuration (MUST be the first Streamlit command) ---
st.set_page_config(
    page_title="Football Tournament Manager",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- NEW: High-Contrast Card Theme CSS ---
st.markdown("""
<style>
    /* Color Palette */
    :root {
        --primary-green: #28a745;   /* A vibrant, high-contrast green */
        --light-gray-bg: #F0F2F6; /* Light background for the app */
        --card-bg: #FFFFFF;       /* Pure white for cards */
        --text-color: #212529;     /* A very dark charcoal for high contrast text */
        --subtle-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }

    /* Main App Body */
    .stApp {
        background-color: var(--light-gray-bg);
    }

    /* Custom Card Style for content sections */
    .card {
        background-color: var(--card-bg);
        border-radius: 10px;
        padding: 25px;
        margin-top: 20px;
        box-shadow: var(--subtle-shadow);
        color: var(--text-color);
    }

    /* Main title style */
    .stApp h1 {
        font-size: 3rem;
        font-weight: bold;
        color: var(--primary-green);
        text-align: center;
        padding-bottom: 20px;
    }
    
    .stApp h2, .stApp h3 {
        color: var(--primary-green);
        border-bottom: 2px solid var(--light-gray-bg);
        padding-bottom: 10px;
    }

    /* Primary button style */
    .stButton > button {
        border-radius: 8px;
        border: 2px solid var(--primary-green);
        background-color: var(--primary-green);
        color: white;
        width: 100%;
    }
    .stButton > button:hover {
        background-color: white;
        color: var(--primary-green);
    }

    /* Make tabs look more like buttons */
    [data-baseweb="tab"] {
        background-color: var(--light-gray-bg);
        border-radius: 8px 8px 0 0;
        margin-right: 5px;
        font-weight: bold;
    }
    [data-baseweb="tab"][aria-selected="true"] {
        background-color: var(--card-bg);
        color: var(--primary-green);
        box-shadow: var(--subtle-shadow);
    }
</style>
""", unsafe_allow_html=True)


# --- Google Sheets Connection ---
# (This part is unchanged, assuming secrets.toml is set up)
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except:
    st.error("Could not connect to Google Sheets. Please ensure your `secrets.toml` is configured correctly.")
    st.stop()


# --- Data Functions for Google Sheets (Unchanged) ---
def load_history_from_sheets():
    df = conn.read(worksheet="tournaments", usecols=list(range(5)), ttl="10s")
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

def save_tournament_to_sheets(tournament_data):
    data_to_save = {
        'tournament_id': tournament_data.get('date') + "_" + str(random.randint(1000, 9999)),
        'date': tournament_data.get('date'), 'teams': tournament_data.get('teams'),
        'players': json.dumps(tournament_data.get('players', {})),
        'history': json.dumps(tournament_data.get('history', []))
    }
    df_to_append = pd.DataFrame([data_to_save])
    conn.update(worksheet="tournaments", data=df_to_append)


# --- Stat Calculation Functions (Unchanged) ---
def calculate_team_stats(matches, teams):
    # ... (function is unchanged)
    stats = {str(i): {'משחקים': 0, 'ניצחונות': 0, 'תיקו': 0, 'הפסדים': 0,
                      'שערי זכות': 0, 'שערי חובה': 0} for i in range(1, teams+1)}
    for m in matches:
        t1, t2 = m['teams']
        g1, g2 = m['score']
        stats[t1]['משחקים'] += 1
        stats[t2]['משחקים'] += 1
        stats[t1]['שערי זכות'] += g1
        stats[t1]['שערי חובה'] += g2
        stats[t2]['שערי זכות'] += g2
        stats[t2]['שערי חובה'] += g1
        if g1 > g2:
            stats[t1]['ניצחונות'] += 1
            stats[t2]['הפסדים'] += 1
        elif g2 > g1:
            stats[t2]['ניצחונות'] += 1
            stats[t1]['הפסדים'] += 1
        else:
            stats[t1]['תיקו'] += 1
            stats[t2]['תיקו'] += 1
    for s in stats.values():
        s['יחס שערים'] = s['שערי זכות'] - s['שערי חובה']
        s['ניקוד סופי'] = s['ניצחונות'] * 3 + s['תיקו']
    return pd.DataFrame.from_dict(stats, orient='index')

def calculate_player_stats(matches):
    # ... (function with backward-compatibility fix is unchanged) ...
    stats = {}
    for m in matches:
        if 'original_players' in m:
            rosters_for_stats = m['original_players']
        else:
            rosters_for_stats = m['players']
        
        players_in_match = []
        for team_id in rosters_for_stats:
            players_in_match.extend(rosters_for_stats[team_id])
        
        for p in players_in_match:
            if p not in stats:
                stats[p] = {'משחקים': 0, 'ניצחונות': 0, 'תיקו': 0, 'הפסדים': 0, 'שערים': 0, 'בישולים': 0}
            stats[p]['משחקים'] += 1

        winner = None
        if m['score'][0] > m['score'][1]: winner = m['teams'][0]
        elif m['score'][1] > m['score'][0]: winner = m['teams'][1]
        
        for team_id in rosters_for_stats:
            for p in rosters_for_stats[team_id]:
                if winner == team_id: stats[p]['ניצחונות'] += 1
                elif winner is None: stats[p]['תיקו'] += 1
                else: stats[p]['הפסדים'] += 1
                    
        for p in m['scorers']:
            if p in stats: stats[p]['שערים'] += 1
        for p in m['assists']:
            if p in stats: stats[p]['בישולים'] += 1
            
    for s in stats.values():
        s['נקודות'] = s['ניצחונות'] + s['בישולים'] + s['שערים'] * 2
    return pd.DataFrame.from_dict(stats, orient='index')


# ---------- App State Initialization (Unchanged) ----------
if 'history' not in st.session_state:
    st.session_state.history = load_history_from_sheets() 
# ... [rest of state initialization] ...
if 'players' not in st.session_state: st.session_state.players = []
if 'tournament' not in st.session_state: st.session_state.tournament = {}


# ---------- Main App UI & Logic ----------
st.title("ניהול טורניр כדורגל")

# --- NEW: Top Navigation with st.tabs ---
tab1, tab2, tab3, tab4 = st.tabs([
    "📅 התחל טורניר חדש", 
    "🎮 ניהול משחק חי", 
    "🏆 סיים טורניר", 
    "📜 היסטוריית טורנירים"
])


# --- Tab 1: Start New Tournament ---
with tab1:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.header("הגדרות טורניר חדש")
    # ... (Rest of the start tournament logic is the same) ...
    excel_file = st.file_uploader("ייבא שחקנים מקובץ Excel (עמודה בשם 'Player')", type=['xlsx'])
    if excel_file: st.session_state.players = load_players_from_excel(excel_file)
    num_teams = st.selectbox("מספר קבוצות", [2, 3, 4], index=1)
    st.info("בחר שחקנים עבור כל קבוצה. מקסימום 6 שחקנים.")
    team_players = {}
    assigned_players = set()
    cols = st.columns(num_teams)
    for i in range(1, num_teams + 1):
        with cols[i-1]:
            available_players = [p for p in st.session_state.players if p not in assigned_players]
            selected = st.multiselect(f"שחקני קבוצה {i}", options=available_players, key=f"team_{i}")
            if len(selected) > 6:
                st.warning(f"קבוצה {i} לא יכולה להכיל יותר מ-6 שחקנים.")
                selected = selected[:6]
            team_players[str(i)] = selected
            assigned_players.update(selected)
    st.markdown("---")
    st.subheader("משחק פתיחה")
    col1, col2 = st.columns(2)
    with col1: team1 = st.selectbox("קבוצה ראשונה", list(range(1, num_teams+1)), index=0)
    with col2: team2 = st.selectbox("קבוצה שנייה", list(range(1, num_teams+1)), index=1)
    
    if st.button("🚀 התחל טורניר!", key="start_tourney_btn"):
        if team1 == team2:
            st.error("יש לבחור שתי קבוצות שונות למשחק הפתיחה.")
        else:
            st.session_state.tournament = {
                'date': str(datetime.today().date()), 'teams': num_teams, 'players': team_players,
                'current_match': [str(team1), str(team2)], 'history': [],
                'streak': {str(i): 0 for i in range(1, num_teams+1)}
            }
            # Initialize other states
            st.rerun() # Rerun to reflect the new state, user will navigate to the next tab
    st.markdown('</div>', unsafe_allow_html=True)


# --- Tab 2: Live Match ---
with tab2:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    if not st.session_state.tournament:
        st.info("יש להתחיל טורניר חדש בכרטיסייה הראשונה.")
        st.stop()
    
    # ... (Rest of the live match logic is the same) ...
    if 'timer_running' in st.session_state and st.session_state.timer_running:
        st_autorefresh(interval=1000, key="timer_refresh")
    tm = st.session_state.tournament
    t1, t2 = tm['current_match']
    if 'timer_start_time' not in st.session_state: st.session_state.timer_start_time = None
    if 'elapsed_time' not in st.session_state: st.session_state.elapsed_time = timedelta(0)
    if 'timer_running' not in st.session_state: st.session_state.timer_running = False
    if st.session_state.timer_running:
        total_elapsed = st.session_state.elapsed_time + (datetime.now() - st.session_state.timer_start_time)
    else:
        total_elapsed = st.session_state.elapsed_time
    minutes, seconds = divmod(int(total_elapsed.total_seconds()), 60)
    st.header(f"קבוצה {t1} ⚔️ קבוצה {t2}")
    st.metric(label="⏱️ זמן משחק", value=f"{minutes:02d}:{seconds:02d}")
    # ... [Timer buttons etc.]
    st.markdown('</div>', unsafe_allow_html=True)


# --- Tab 3: Finish Tournament ---
with tab3:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    if not st.session_state.tournament or not st.session_state.tournament.get('history'):
        st.info("יש לשחק לפחות משחק אחד לפני שמסיימים את הטורניר.")
        st.stop()

    # ... (Rest of the finish tournament logic is the same) ...
    st.header("🏁 תוצאות סופיות")
    tm = st.session_state.tournament
    df_teams = calculate_team_stats(tm['history'], tm['teams'])
    df_players = calculate_player_stats(tm['history'])
    st.subheader("📊 דירוג קבוצות")
    st.dataframe(df_teams.sort_values(by=['ניקוד סופי', 'יחס שערים', 'שערי זכות'], ascending=False), use_container_width=True)
    st.subheader("🏅 דירוג שחקנים")
    st.dataframe(df_players.sort_values(by=['נקודות', 'שערים', 'בישולים'], ascending=False), use_container_width=True)
    if st.button("💾 שמור טורניר והתחל חדש", key="save_tourney_btn"):
        save_tournament_to_sheets(st.session_state.tournament)
        st.success("הטורניר נשמר בהיסטוריה!")
        st.balloons()
        st.session_state.history = load_history_from_sheets()
        st.session_state.tournament = {}
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)


# --- Tab 4: History ---
with tab4:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.header("📜 היסטוריית טורנירים")
    # ... (Rest of the history logic is the same) ...
    if not st.session_state.history:
        st.info("עדיין אין טורנירים שמורים בהיסטוריה.")
    else:
        for i, t in enumerate(reversed(st.session_state.history)):
            with st.expander(f"טורניר מתאריך: {t['date']}"):
                df_teams = calculate_team_stats(t['history'], t['teams'])
                df_players = calculate_player_stats(t['history'])
                st.subheader("📊 דירוג קבוצות")
                st.dataframe(df_teams.sort_values(by=['ניקוד סופי', 'יחס שערים', 'שערי זכות'], ascending=False), use_container_width=True)
                st.subheader("🏅 דירוג שחקנים")
                st.dataframe(df_players.sort_values(by=['נקודות', 'שערים', 'בישולים'], ascending=False), use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)