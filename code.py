import streamlit as st
import pandas as pd
import json
import random
from datetime import datetime, timedelta
from streamlit_autorefresh import st_autorefresh
import io  # New import for in-memory file handling

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

# --- NEW: Function to convert dataframes to an Excel file in memory ---
def dfs_to_excel_bytes(dfs_dict):
    """
    Takes a dictionary of {sheet_name: dataframe} and returns the bytes
    of an Excel file with each dataframe on its own sheet.
    """
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
                elif winner is None
        st.markdown("---")
        if st.button("🏁 סיים וחשב משחק", type="primary", key="finish_match_btn"):
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
            st.session_state.g1 = 0
            st.session_state.g2 = 0
            st.rerun()
            
    st.markdown('</div>', unsafe_allow_html=True)


# --- Tab 2: Finish Tournament ---
with tab2:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    if not st.session_state.tournament or not st.session_state.tournament.get('history'):
        st.info("יש לשחק לפחות משחק אחד לפני שמציגים סיכום.")
        st.stop()
    st.header("🏁 תוצאות סופיות")
    tm = st.session_state.tournament
    df_teams = calculate_team_stats(tm['history'], tm['teams'])
    df_players = calculate_player_stats(tm['history'])
    
    # Sort the dataframes for display
    df_teams_sorted = df_teams.sort_values(by=['ניקוד סופי', 'יחס שערים', 'שערי זכות'], ascending=False)
    df_players_sorted = df_players.sort_values(by=['נקודות', 'שערים', 'בישולים'], ascending1, t2]: tm['streak'][team_id] += 1
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
    st.subheader("📊 דירוג קבוצות")
    st.dataframe(df_teams.sort_values(by=['ניקוד סופי', 'יחס שערים', 'שערי זכות'], ascending=False), use_container_width=True)
    st.subheader("🏅 דירוג שחקנים")
    st.dataframe(df_players.sort_values(by=['נקודות', 'שערים', 'בישולים'], ascending=False), use_container_width=True)
    
    st.markdown("---")

    # --- NEW: Excel Download Section ---
    st.subheader("⬇️ הורדת נתונים")
    
    # Prepare data for download
    excel_data = to_excel(
        df_teams.sort_values(by=['ניקוד סופי', 'יחס שערים', 'שערי זכות'], ascending=False),
        df_players.sort_values(by=['נקודות', 'שערים', 'בישולים'], ascending=False)
    )
    
    # Create file name with current date
    today_date = datetime.now().strftime("%Y-%m-%d")
    file_name = f"tournament_results_{today_date}.xlsx"
    
    st.download_button(
        label="הורד תוצאות כקובץ Excel",
        data=excel_data,
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
    # ... [Help text is unchanged] ...
    st.markdown("""
    **ברוכים הבאים למנהל הטורנירים!**

    - **שלב 1: התחל טורניר חדש**
        - בכרטיסייה הראשונה, **"התחל / נהל טורניר"**, הגדר את הטורניר.
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
        - בסיום הטורניр, תוכל להוריד את התוצאות כקובץ אקסל.
        - לחיצה על **"התחל טורניр חדש"** בכרטיסייה זו תאפס את כל הנתונים ותאפשר לך להתחיל מההתחלה.
    """)
    st.markdown('</div>', unsafe_allow_html=True)