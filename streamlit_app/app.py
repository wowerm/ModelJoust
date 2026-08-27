import streamlit as st

from theme import LOGO_PATH

st.set_page_config(page_title="ModelJoust", page_icon=LOGO_PATH, layout="wide")

pages = {
    "Przegląd": [
        st.Page("pages/1_today.py", title="Dziś", icon=":material/today:"),
    ],
    "Analiza": [
        st.Page("pages/2_model_comparison.py", title="Porównanie modeli", icon=":material/leaderboard:"),
        st.Page("pages/3_retrainings.py", title="Retreningi", icon=":material/fitness_center:"),
        st.Page("pages/4_history_quality.py", title="Historia i jakość", icon=":material/monitoring:"),
        st.Page("pages/5_dynamics.py", title="Dynamika: Champion/Challenger", icon=":material/emoji_events:"),
    ],
    "Administracja": [
        st.Page("pages/6_admin.py", title="Admin", icon=":material/lock:"),
    ],
}

nav = st.navigation(pages)
nav.run()
