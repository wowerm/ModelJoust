from pathlib import Path

import streamlit as st

LOGO_PATH = str(Path(__file__).parent / "assets" / "logo.svg")

_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600;700&display=swap');

h1, h2, h3 {
    font-family: 'Space Grotesk', sans-serif !important;
    letter-spacing: 0.01em;
}

h1 {
    border-bottom: 2px solid #C9A961;
    padding-bottom: 0.4rem;
}
</style>
"""


def apply_theme() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)
    st.logo(LOGO_PATH, icon_image=LOGO_PATH, size="large")
