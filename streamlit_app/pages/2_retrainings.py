import pandas as pd
import streamlit as st

from db import supabase
from theme import apply_theme

apply_theme()

st.title("Retreningi")
st.caption("Historia wersji wszystkich modeli — kiedy, dlaczego, na jakim oknie danych")

resp = (
    supabase.table("models_logs")
    .select("model_type, model_version, is_active, retrain_trigger, train_start_date, train_end_date, created_at")
    .order("created_at", desc=True)
    .execute()
)

if not resp.data:
    st.info("Brak jeszcze żadnych wersji modeli.")
    st.stop()

df = pd.DataFrame(resp.data)
st.dataframe(df, width="stretch", hide_index=True)

st.caption("Oś czasu retreningów per model — do zbudowania.")
