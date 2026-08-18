import pandas as pd
import streamlit as st

from db import supabase
from theme import apply_theme

apply_theme()

st.title("Historia predykcji i jakość")
st.caption("Predykcje vs rzeczywiste wartości w czasie, rozkład błędów, kroczące MAPE")

zakres = st.radio("Zakres", ["30 dni", "90 dni", "wszystkie"], horizontal=True)

resp = (
    supabase.table("model_predictions")
    .select("target_date, model_id, predicted_value, actual_value, error_value, status")
    .eq("status", "evaluated")
    .order("target_date", desc=True)
    .limit(500)
    .execute()
)

if not resp.data:
    st.info("Brak jeszcze ocenionych predykcji.")
    st.stop()

df = pd.DataFrame(resp.data)
st.dataframe(df, width="stretch", hide_index=True)

st.caption(
    "Do zbudowania: wykres predykcja vs rzeczywista wartość per model, histogram błędów, "
    "kroczące MAPE z system_logs.mape — z uwzględnieniem przełącznika zakresu powyżej."
)
