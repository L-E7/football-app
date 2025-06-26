import streamlit as st
import pandas as pd
import json
import random
from datetime import datetime, timedelta
from streamlit_autorefresh import st_autorefresh
import io

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
    .card {
        background-color: #2a2a2a; /* Dark background */
        border-radius: 10px;
        padding: 25px;
        margin-bottom: 20px;
        box-shadow: 0 4px 8px 0 rgba(0,0,0,0.2);
        border: 1px solid #444; /* Subtle border */
        color: #f0f2f6; /* Light text */
    }
    .stButton>button {
        border-radius: 20px;
        border: 1px solid #4CAF50;
        background-color: #4CAF50;
        color: white;
        padding: 10px 24px;
        transition: 0.3s;
    }
    .stButton>button:hover {
        background-color: white;
        color: #4CAF50;
    }
    .stTextInput>div>div>input, .stNumberInput>div>div>input {
        background-color: #333;
        color: #f0f2f6;
        border: 1px solid #555;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 24px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        white-space: pre-wrap;
        background-color: #2a2a2a;
        border-radius: 4px 4px 0px 0px;
        gap: 1px;
        padding-top: 10px;
        padding-bottom: 10px;
    }
    .stTabs [aria-selected="true"] {
        background-color: #4CAF50;
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
            df.to_excel(writer, sheet_name=sheet_name, index=False) # Index=False is usually better for export
    processed_data = output.getvalue()
    return processed_data

# --- Stat Calculation Functions ---
def calculate_team_stats(matches, teams):
    if not matches:
        return pd.DataFrame()
    stats = {str(i): {'Played': 0, 'Wins': 0, 'Draws': 0, 'Losses': 0, 'GF': 0, 'GA': 0, 'GD': 0, 'Points': 0} for i in range(1, int(teams)+1)}
    for m in matches:
        t1, t2 = str(m['teams'][0]), str(m['teams'][1])
        g1, g2 = m['score']
        stats[t1]['Played'] += 1; stats[t2]['Played'] += 1
        stats[t1]['GF'] += g1; stats[t1]['GA'] += g2
        stats[t2]['GF'] += g2; stats[t2]['GA'] += g1
        if g1 > g2: stats[t1]['Wins'] += 1; stats[t2]['Losses'] += 1
        elif g2 > g1: stats[t2]['Wins'] += 1; stats[t1]['Losses'] += 1
        else: stats[t1]['Draws'] += 1; stats[t2]['Draws'] += 1
    for s in stats.values():
        s['GD'] = s['GF'] - s['GA']
        s['Points'] = s['Wins'] * 3 + s['Draws']
    df = pd.DataFrame.from_dict(stats, orient='index')
    df.index.name = "Team"
    return df.sort_values(by=['Points', 'GD', 'GF'], ascending=False)

def calculate_player_stats(matches):
    if not matches:
        return pd.DataFrame()
    stats = {}
    for m in matches:
        rosters_for_stats = m.get('original_players', m.get('players', {}))
        players_in_match = []
        for team_id in rosters_for_stats: players_in_match.extend(rosters_for_stats[team_id])
        for p in players_in_match:
            if p not in stats:
                stats[p] = {'Played': 0, 'Wins': 0, 'Draws': 0, 'Losses': 0, 'Goals': 0, 'Assists': 0, 'Rating': 0}
            stats[p]['Played'] += 1
        winner = None; t1, t2 = str(m['teams'][0]), str(m['teams'][1]); g1, g2 = m['score']
        if g1 > g2: winner = t1
        elif g2 > g1: winner = t2
        for team_id in rosters_for_stats:
            for p in rosters_for_stats[team_id]:
                if str(winner) == str(team_id): stats[p]['Wins'] += 1
                elif winner is None: stats[p]['Draws'] += 1
                else: stats[p]['Losses'] += 1
        for p in m.get('scorers', []):
            if p in stats: stats[p]['Goals'] += 1
        for p in m.get('assists', []):
            if p in stats: stats[p]['Assists'] += 1
    for p, s in stats.items(): s['Rating'] = s['Wins'] + s['Assists'] + s['Goals'] * 2
    df = pd.DataFrame.from_dict(stats, orient='index')
    df.index.name = "Player"
    return df.sort_values(by=['Rating', 'Goals', 'Wins'], ascending=False)

# ---------- App State Initialization --- IMPORTANT ---
# This block ensures all necessary keys are initialized once per session, BEFORE they are used.
keys_to_initialize = {
    'players': [], 'tournament': {}, 'timer_running': False, 'timer_start_time': None,
    'elapsed_time': timedelta(0), 'goal_events': [], 'substitutions': {},
    'g1': 0, 'g2': 0 # Initialize score keys here to prevent the API exception
}
for key, default_value in keys_to_initialize.items():
    if key not in st.session_state:
        st.session_state[key] = default_value

# ---------- Main App UI & Logic ----------
st.title("⚽ Football Tournament Manager")

tab1, tab2, tab3 = st.tabs([
    "📅 Start / Manage Tournament", "🏆 Summary & Stats", "ℹ️ Help"
])

# --- Tab 1: Start & Manage Tournament ---
with tab1:
    st.markdown('<div class="card">', unsafe_allow_html=True)

    if not st.session_state.tournament:
        # --- NEW TOURNAMENT SETUP ---
        st.header("New Tournament Setup")
        excel_file = st.file_uploader("Import players from an Excel file (column named 'Player')", type=['xlsx'])
        if excel_file:
            st.session_state.players = load_players_from_excel(excel_file)
            st.success(f"Loaded {len(st.session_state.players)} players.")

        st.session_state.players = st.text_area(
            "Or, enter player names (one per line)",
            value='\n'.join(st.session_state.players),
            height=250
        ).strip().split('\n')
        st.session_state.players = [p.strip() for p in st.session_state.players if p.strip()]

        st.markdown("---")
        col1, col2 = st.columns(2)
        with col1:
            num_teams = st.number_input("Number of Teams", min_value=2, max_value=8, value=2, step=2)
        with col2:
            match_duration_minutes = st.number_input("Match Duration (minutes)", min_value=1, value=10)

        if st.button("🚀 Start Tournament!", type="primary", key="start_tourney_btn"):
            if len(st.session_state.players) < num_teams:
                st.error(f"Not enough players! You need at least {num_teams} players for {num_teams} teams.")
            else:
                players_copy = st.session_state.players.copy()
                random.shuffle(players_copy)
                teams = {str(i + 1): [] for i in range(num_teams)}
                for i, player in enumerate(players_copy):
                    teams[str((i % num_teams) + 1)].append(player)

                st.session_state.tournament = {
                    'players': st.session_state.players,
                    'teams': teams,
                    'num_teams': num_teams,
                    'match_duration_minutes': match_duration_minutes,
                    'history': [],
                    'streaks': {p: 0 for p in st.session_state.players},
                    'next_match': {'teams': [1, 2], 'players': {
                        '1': teams['1'], '2': teams['2']
                    }}
                }
                st.success("Tournament created! The first match is ready.")
                st.rerun()

    else: # --- A TOURNAMENT IS ACTIVE ---
        tourney = st.session_state.tournament
        next_match_info = tourney['next_match']
        t1, t2 = next_match_info['teams']
        team1_players = next_match_info['players'][str(t1)]
        team2_players = next_match_info['players'][str(t2)]

        st.header(f"Match: Team {t1} vs Team {t2}")

        # Timer logic
        if st.session_state.timer_running:
            st_autorefresh(interval=1000, key="timer_refresh")
            st.session_state.elapsed_time = datetime.now() - st.session_state.timer_start_time
        
        duration_td = timedelta(minutes=tourney['match_duration_minutes'])
        time_left = max(duration_td - st.session_state.elapsed_time, timedelta(0))
        st.subheader(f"Time Remaining: {str(time_left).split('.')[0]}")

        col1, col2 = st.columns(2)
        with col1:
            if not st.session_state.timer_running:
                if st.button("▶️ Start Match Timer"):
                    st.session_state.timer_start_time = datetime.now() - st.session_state.elapsed_time
                    st.session_state.timer_running = True
                    st.rerun()
        with col2:
            if st.session_state.timer_running:
                if st.button("⏸️ Pause Match Timer"):
                    st.session_state.timer_running = False
                    st.rerun()

        st.markdown("---")
        st.subheader("🥅 Match Result")
        col1, col2 = st.columns(2)
        # These widgets are now safely created using the pre-initialized session_state keys
        with col1:
            score1 = st.number_input(f"Team {t1} Score", min_value=0, step=1, key='g1')
        with col2:
            score2 = st.number_input(f"Team {t2} Score", min_value=0, step=1, key='g2')

        with st.expander("📝 Log Goals and Assists"):
            st.write("Current Events:")
            for i, event in enumerate(st.session_state.goal_events):
                st.write(f"Goal {i+1}: Scored by **{event['scorer']}** (Team {event['team']}), Assisted by **{event['assister']}**")

            st.markdown("---")
            all_players_in_match = sorted(team1_players + team2_players)
            scorer = st.selectbox("Scorer", options=all_players_in_match, index=None, key=f"scorer_{len(st.session_state.goal_events)}")
            assister = st.selectbox("Assister", options=["-- No Assist --"] + all_players_in_match, index=0, key=f"assister_{len(st.session_state.goal_events)}")

            if st.button("Log Goal"):
                if scorer:
                    team_of_scorer = t1 if scorer in team1_players else t2
                    st.session_state.goal_events.append({'scorer': scorer, 'assister': assister, 'team': team_of_scorer})
                    if team_of_scorer == t1:
                        st.session_state.g1 += 1
                    else:
                        st.session_state.g2 += 1
                    st.rerun()

        st.markdown("---")
        if st.button("🏁 Finish & Calculate Match", type="primary", key="finish_match_btn"):
            # --- THIS IS THE CORRECTED LOGIC FLOW ---
            
            # Step 1: Read values from widgets and create the match record
            scorers = [event['scorer'] for event in st.session_state.goal_events if event['scorer']]
            assists = [event['assister'] for event in st.session_state.goal_events if event['assister'] and event['assister'] != "-- No Assist --"]

            match = {
                'teams': [t1, t2],
                'score': [score1, score2], # Use values from the number_input widgets
                'scorers': scorers,
                'assists': assists,
                'original_players': next_match_info['players'],
                'timestamp': datetime.now().isoformat()
            }

            # Step 2: Update the main tournament object in session state
            st.session_state.tournament['history'].append(match)
            # (Optional) Add more logic here, e.g., finding the next match participants

            # Step 3: RESET the state keys for the NEXT run
            st.session_state.timer_running = False
            st.session_state.timer_start_time = None
            st.session_state.elapsed_time = timedelta(0)
            st.session_state.goal_events = []
            st.session_state.substitutions = {}
            st.session_state.g1 = 0  # This now safely prepares the state for the *next* run
            st.session_state.g2 = 0  # This now safely prepares the state for the *next* run

            # Step 4: Trigger the rerun
            st.success(f"Match between Team {t1} and Team {t2} finished. Result: {score1}-{score2}. Ready for next match.")
            st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)


# --- Tab 2: Summary & Stats ---
with tab2:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.header("Tournament Summary")

    if not st.session_state.tournament:
        st.warning("No tournament is active. Go to the 'Start / Manage Tournament' tab to begin.")
    else:
        tourney = st.session_state.tournament
        history = tourney['history']

        st.subheader("📊 Team Standings")
        team_stats_df = calculate_team_stats(history, tourney['num_teams'])
        if not team_stats_df.empty:
            st.dataframe(team_stats_df, use_container_width=True)
        else:
            st.info("No matches have been played yet.")
        
        st.subheader("⭐ Player Leaderboard")
        player_stats_df = calculate_player_stats(history)
        if not player_stats_df.empty:
            st.dataframe(player_stats_df, use_container_width=True)
        else:
            st.info("No matches have been played yet.")

        st.subheader("📜 Match History")
        if history:
            for i, match in enumerate(reversed(history)):
                t1, t2 = match['teams']
                s1, s2 = match['score']
                st.info(f"Match {len(history)-i}: Team {t1} ({s1}) vs Team {t2} ({s2})")
        else:
            st.info("No matches have been played yet.")
            
        st.markdown("---")
        st.subheader("⬇️ Download Data")
        if not team_stats_df.empty and not player_stats_df.empty:
            excel_bytes = dfs_to_excel_bytes({
                "Team Standings": team_stats_df.reset_index(),
                "Player Leaderboard": player_stats_df.reset_index(),
                "Match History": pd.DataFrame(history)
            })
            st.download_button(
                label="Download All Stats as Excel",
                data=excel_bytes,
                file_name=f"tournament_stats_{datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

    st.markdown('</div>', unsafe_allow_html=True)

# --- Tab 3: Help ---
with tab3:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.header("How to Use This App")
    st.markdown("""
    **This application helps you manage a small-sided football tournament from start to finish.**

    ### 1. Start / Manage Tournament Tab
    - **New Tournament Setup**:
        - **Upload Players**: You can upload an `.xlsx` file. The file must have a column named `Player` with one player name per row.
        - **Manual Entry**: Alternatively, you can type or paste player names directly into the text area, with each name on a new line.
        - **Configure**: Set the number of teams and the duration for each match.
        - **Start Tournament**: Click this button to randomly assign players to teams and create the tournament schedule.
    - **Active Match**:
        - **Timer**: Use the `Start` and `Pause` buttons to control the match clock.
        - **Score Input**: Enter the score for each team directly into the number input fields.
        - **Log Goals**: Expand this section to log individual scorers and assists for each goal. This automatically updates the score.
        - **Finish Match**: When the match is over, click this button. The result will be saved, stats will be calculated, and the app will be ready for the next match.

    ### 2. Summary & Stats Tab
    - **Team Standings**: A league table showing Wins, Draws, Losses, Goals For (GF), Goals Against (GA), Goal Difference (GD), and Points.
    - **Player Leaderboard**: Ranks players based on a `Rating` score (Wins + Assists + Goals*2).
    - **Match History**: A log of all completed matches.
    - **Download**: Export all the data to a single Excel file with multiple sheets.

    ### 3. Resetting a Tournament
    To start a new tournament, simply refresh your browser tab (F5 or Ctrl+R). This will clear all current tournament data.
    """)
    st.markdown('</div>', unsafe_allow_html=True)