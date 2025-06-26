import streamlit as st
import pandas as pd
import json
import random
from datetime import datetime, timedelta
from streamlit_autorefresh import st_autorefresh
import io  # For in-memory file handling

# --- Page Configuration ---
st.set_page_config(
    page_title="Football Tournament Manager",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- High-Contrast Card Theme CSS ---
st.markdown("""
<style>
    /* Color Palette */
    :root {
        --primary-green: #28a745;
        --light-gray-bg: #F0F2F6;
        --card-bg: #FFFFFF;
        --text-color: #212529;
        --subtle-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    .stApp { background-color: var(--light-gray-bg); }
    .card {
        background-color: var(--card-bg);
        border-radius: 10px;
        padding: 25px;
        margin-top: 20px;
        box-shadow: var(--subtle-shadow);
        color: var(--text-color);
    }
    .stApp h1 {
        font-size: 3rem; font-weight: bold; color: var(--primary-green);
        text-align: center; padding-bottom: 20px;
    }
    .stApp h2, .stApp h3 {
        color: var(--primary-green); border-bottom: 2px solid var(--light-gray-bg);
        padding-bottom: 10px;
    }
    .stButton > button {
        border-radius: 8px; border: 2px solid var(--primary-green);
        background-color: var(--primary-green); color: white; width: 100%;
    }
    .stButton > button:hover { background-color: white; color: var(--primary-green); }
    [data-baseweb="tab"] {
        background-color: var(--light-gray-bg); border-radius: 8px 8px 0 0;
        margin-right: 5px; font-weight: bold;
    }
    [data-baseweb="tab"][aria-selected="true"] {
        background-color: var(--card-bg); color: var(--primary-green);
        box-shadow: var(--subtle-shadow);
    }
</style>
""", unsafe_allow_html=True)


# --- Utility Functions ---
def load_players_from_excel(file):
    df = pd.read_excel(file, engine='openpyxl')
    return df['Player'].dropna().tolist()

def dfs_to_excel_bytes(dfs_dict):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        for sheet_name, df in dfs_dict.items():
            df.to_excel(writer, sheet_name=sheet_name, index=True)
    processed_data = output.getvalue()
    return processed_data

# --- Stat Calculation Functions ---
def calculate_team_stats(matches, teams):
    stats = {str(i): {'משחקים': 0, 'ניצחונות': 0, 'תיקו': 0, 'הפסדים': 0,
                      'שערי זכות': 0, 'שערי חובה': 0} for i in range(1, int(teams)+1)}
    for m in matches:
        t1, t2 = str(m['teams'][0]), str(m['teams'][1])
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
    stats = {}
    for m in matches:
        rosters_for_stats = m.get('original_players', m.get('players', {}))
        
        players_in_match = []
        for team_id in rosters_for_stats:
            players_in_match.extend(rosters_for_stats[team_id])
        
        for p in players_in_match:
            if p not in stats:
                stats[p] = {'משחקים': 0, 'ניצחונות': 0, 'תיקו': 0, 'הפסדים': 0, 'שערים': 0, 'בישולים': 0}
            stats[p]['משחקים'] += 1

        winner = None
        t1, t2 = str(m['teams'][0]), str(m['teams'][1])
        g1, g2 = m['score']
        if g1 > g2: winner = t1
        elif g2 > g1: winner = t2
        
        for team_id in rosters_for_stats:
            for p in rosters_for_stats[team_id]:
                if str(winner) == str(team_id): stats[p]['ניצחונות'] += 1
                elif winner is None: stats[p]['תיקו'] += 1
                else: stats[p]['הפסדים'] += 1
                    
        for p in m.get('scorers', []):
            if p in stats: stats[p]['שערים'] += 1
        for p in m.get('assists', []):
            if p in stats: stats[p]['בישולים'] += 1
            
    for s in stats.values():
        s['נקודות'] = s['ניצחונות'] + s['בישולים'] + s['שערים'] * 2
    return pd.DataFrame.from_dict(stats, orient='index')

# ---------- App State Initialization ----------
if 'players' not in st.session_state: st.session_state.players = []
if 'tournament' not in st.session_state: st.session_state.tournament = {}
if 'matches' not in st.session_state: st.session_state.matches = []
if 'timer_running' not in st.session_state: st.session_state.timer_running = False
if 'timer_start_time' not in st.session_state: st.session_state.timer_start_time = None
if 'elapsed_time' not in st.session_state: st.session_state.elapsed_time = timedelta(0)
if 'goal_events' not in st.session_state: st.session_state.goal_events = []
if 'substitutions' not in st.session_state: st.session_state.substitutions = {}


# ---------- Main App UI & Logic ----------
st.title("ניהול טורניר כדורגל")

tab1, tab2, tab3 = st.tabs([
    "📅 התחל / נהל טורניר", 
    "🏆 סיכום וסטטיסטיקות", 
    "ℹ️ עזרה"
])

# --- Tab 1: Start & Manage Tournament ---
with tab1:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    
    if not st.session_state.tournament:
        st.header("הגדרות טורניр חדש")
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
        
        if st.button("🚀 התחל טורניр!", key="start_tourney_btn"):
            if team1 == team2:
                st.error("יש לבחור שתי קבוצות שונות למשחק הפתיחה.")
            else:
                st.session_state.tournament = {
                    'date': str(datetime.today().date()), 'teams': num_teams, 'players': team_players,
                    'current_match': [str(team1), str(team2)], 'history': [],
                    'streak': {str(i): 0 for i in range(1, num_teams+1)}
                }
                st.session_state.g1 = 0
                st.session_state.g2 = 0
                st.rerun()

    else:
        if st.session_state.timer_running: st_autorefresh(interval=1000, key="timer_refresh")
        tm = st.session_state.tournament
        t1, t2 = tm['current_match']
        
        if st.session_state.timer_running and st.session_state.timer_start_time:
            total_elapsed = st.session_state.elapsed_time + (datetime.now() - st.session_state.timer_start_time)
        else:
            total_elapsed = st.session_state.elapsed_time
        minutes, seconds = divmod(int(total_elapsed.total_seconds()), 60)
        st.header(f"קבוצה {t1} ⚔️ קבוצה {t2}")
        st.metric(label="⏱️ זמן משחק", value=f"{minutes:02d}:{seconds:02d}")
        c1, c2, c3 = st.columns(3)
        if not st.session_state.timer_running and st.session_state.timer_start_time is None:
            if c1.button("▶️ התחל שעון"):
                st.session_state.timer_start_time = datetime.now()
                st.session_state.timer_running = True
                st.rerun()
        if st.session_state.timer_running:
            if c2.button("⏸️ עצור שעון"):
                st.session_state.elapsed_time += datetime.now() - st.session_state.timer_start_time
                st.session_state.timer_running = False
                st.rerun()
        if not st.session_state.timer_running and st.session_state.timer_start_time is not None:
            if c3.button("▶️ המשך שעון"):
                st.session_state.timer_start_time = datetime.now()
                st.session_state.timer_running = True
                st.rerun()
        st.markdown("---")
        st.subheader("🥅 תוצאת המשחק")
        col1, col2 = st.columns(2)
        with col1: g1 = st.number_input(f"שערים קבוצה {t1}", min_value=0, step=1, key='g1')
        with col2: g2 = st.number_input(f"שערים קבוצה {t2}", min_value=0, step=1, key='g2')
        with st.expander("🔄 בצע חילופים למשחק הנוכחי"):
            all_teams_ids = list(tm['players'].keys())
            resting_teams_ids = [t for t in all_teams_ids if t not in [t1, t2]]
            sub_pool = []
            if resting_teams_ids:
                for team_id in resting_teams_ids: sub_pool.extend(tm['players'][team_id])
            if not sub_pool:
                st.info("אין שחקנים פנויים לחילוף.")
            else:
                playing_players = tm['players'][t1] + tm['players'][t2]
                player_to_replace = st.selectbox("שחקן להחלפה:", options=playing_players)
                substitute_player = st.selectbox("שחקן מחליף:", options=sub_pool)
                if st.button("בצע חילוף"):
                    st.session_state.substitutions[player_to_replace] = substitute_player
                    st.success(f"{substitute_player} מחליף את {player_to_replace}!")
        if st.session_state.substitutions:
            st.write("חילופים פעילים:")
            sub_list = [f"**{v}** (נכנס) ↔️ **{k}** (יוצא)" for k,v in st.session_state.substitutions.items()]
            st.markdown("\n".join(f"- {s}" for s in sub_list))
        original_players_t1 = tm['players'][t1]
        original_players_t2 = tm['players'][t2]
        match_players_t1 = [st.session_state.substitutions.get(p, p) for p in original_players_t1]
        match_players_t2 = [st.session_state.substitutions.get(p, p) for p in original_players_t2]
        all_players_in_match = match_players_t1 + match_players_t2
        total_goals = g1 + g2
        while len(st.session_state.goal_events) < total_goals:
            st.session_state.goal_events.append({'scorer': None, 'assister': None})
        while len(st.session_state.goal_events) > total_goals:
            st.session_state.goal_events.pop()
        if total_goals > 0:
            st.markdown("---")
            st.subheader("⚽ הזנת כובשים ומבשלים")
            for i in range(total_goals):
                col_s, col_a = st.columns(2)
                with col_s: st.session_state.goal_events[i]['scorer'] = st.selectbox(f"כובש שער {i+1}", options=all_players_in_match, key=f"scorer_{i}")
                with col_a:
                    assist_options = ["-- ללא בישול --"] + all_players_in_match
                    st.session_state.goal_events[i]['assister'] = st.selectbox(f"מבשל שער {i+1}", options=assist_options, key=f"assister_{i}")
        st.markdown("---")
        if st.button("🏁 סיים וחשב משחק", type="primary", key="finish_match_btn"):
            st.session_state.g1 = 0
            st.session_state.g2 = 0
            scorers = [event['scorer'] for event in st.session_state.goal_events if event['scorer']]
            assists = [event['assister'] for event in st.session_state.goal_events if event['assister'] and event['assister'] != "-- ללא בישול --"]
            match = {
                'teams': [t1, t2], 'score': [g1, g2], 'scorers': scorers, 'assists': assists,
                'players': {t1: match_players_t1, t2: match_players_t2},
                'original_players': {t1: original_players_t1, t2: original_players_t2}
            }
            tm['history'].append(match)
            for team_id in [t1, t2]: tm['streak'][team_id] += 1
            winner = None
            if g1 > g2: winner = t1
            elif g2 > g1: winner = t2
            else:
                if len(tm['history']) == 1: winner = random.choice([t1, t2])
                else:
                    prev_match_teams = tm['history'][-2]['teams']
                    winner = t2 if str(t1) in prev_match_teams else t1
            all_teams_ids = list(tm['players'].keys())
            if tm['streak'].get(winner, 0) >= 3:
                rest_team, loser = winner, t2 if winner == t1 else t1
                next_opponent = next((t for t in all_teams_ids if t not in [t1, t2]), None)
                if next_opponent: tm['current_match'] = sorted([next_opponent, loser])
                else: tm['current_match'] = sorted([t1, t2])
                tm['streak'][rest_team] = 0
            else:
                loser = t2 if winner == t1 else t1
                next_opponent = next((t for t in all_teams_ids if t not in [t1, t2]), None)
                if next_opponent: tm['current_match'] = sorted([winner, next_opponent])
                else: tm['current_match'] = sorted([winner, loser])
            st.session_state.timer_running = False
            st.session_state.timer_start_time = None
            st.session_state.elapsed_time = timedelta(0)
            st.session_state.goal_events = []
            st.session_state.substitutions = {}
            st.rerun()
            
    st.markdown('</div>', unsafe_allow_html=True)


# --- Tab 2: Summary & Stats ---
with tab2:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    if not st.session_state.tournament or not st.session_state.tournament.get('history'):
        st.info("יש לשחק לפחות משחק אחד לפני שמציגים סיכום.")
        st.stop()
    st.header("🏁 תוצאות סופיות")
    tm = st.session_state.tournament
    df_teams = calculate_team_stats(tm['history'], tm['teams'])
    df_players = calculate_player_stats(tm['history'])
    
    df_teams_sorted = df_teams.sort_values(by=['ניקוד סופי', 'יחס שערים', 'שערי זכות'], ascending=False)
    df_players_sorted = df_players.sort_values(by=['נקודות', 'שערים', 'בישולים'], ascending=False)

    st.subheader("📊 דירוג קבוצות")
    st.dataframe(df_teams_sorted, use_container_width=True)
    st.subheader("🏅 דירוג שחקנים")
    st.dataframe(df_players_sorted, use_container_width=True)
    
    st.markdown("---")
    st.subheader("⬇️ הורדת נתונים")
    
    excel_data_bytes = dfs_to_excel_bytes({
        "Team_Stats": df_teams_sorted,
        "Player_Stats": df_players_sorted
    })
    
    today_date = datetime.now().strftime("%Y-%m-%d")
    file_name = f"tournament_results_{today_date}.xlsx"
    
    st.download_button(
        label="הורד תוצאות כקובץ Excel",
        data=excel_data_bytes,
        file_name=file_name,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True
    )
    
    st.markdown("---")
    if st.button("🗑️ התחל טורניר חדש (הנתונים הנוכחיים ימחקו)", key="reset_btn"):
        st.session_state.tournament = {}
        st.rerun()
        
    st.markdown('</div>', unsafe_allow_html=True)

# --- Tab 3: Help ---
with tab3:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.header("ℹ️ עזרה והוראות")
    st.markdown("""
    **ברוכים הבאים למנהל הטורנירים!**

    - **שלב 1: התחל טורניр חדש**
        - בכרטיסייה הראשונה, **"התחל / נהל טורניר"**, הגדר את הטורניр.
        - תוכל לייבא רשימת שחקנים מקובץ אקסל.
        - בחר את מספר הקבוצות והקצה שחקנים לכל קבוצה.
        - בחר את שתי הקבוצות למשחק הפתיחה ולחץ על **"התחל טורניר!"**.

    - **שלב 2: ניהול משחק חי**
        - לאחר התחלת הטורניר, הכרטיסייה הראשונה הופכת למסך ניהול המשחק.
        - השתמש בכפתורי השעון כדי לנהל את זמן המשחק.
        - בסיום המשחק, הזן את התוצאה הסופית.
        - הזן את הכובשים והמבשלים עבור כל שער.
        - במידת הצורך, השתמש באזור החילופים כדי להכניס שחקנים מקבוצות נחות.
        - לחץ על **"סיים וחשב משחק"** כדי לקבוע את המשחק הבא אוטומטית.

    - **שלב 3: סיום וסטטיסטיקות**
        - בכל שלב, תוכל לעבור לכרטיסייה **"סיכום וסטטיסטיקות"** כדי לראות את טבלאות הדירוג המעודכנות.
        - בסיום הטורניר, תוכל להוריד את התוצאות כקובץ אקסל.
        - לחיצה על **"התחל טורניр חדש"** בכרטיסייה זו תאפס את כל הנתונים ותאפשר לך להתחיל מההתחלה.
    """)
    st.markdown('</div>', unsafe_allow_html=True)