import pandas as pd
import streamlit as st

from db import supabase
from theme import apply_theme

apply_theme()

st.title("Porównanie modeli")
st.caption("Wszystkie 5 modeli obok siebie: aktualne MAPE, liczba wersji, cechy")

log_resp = supabase.table("system_logs").select("*").order("log_date", desc=True).limit(1).execute()
versions_resp = supabase.table("models_logs").select("model_type, is_active, selected_features").execute()

if not log_resp.data or not versions_resp.data:
    st.info("Za mało danych jeszcze do porównania.")
    st.stop()

latest_mape = log_resp.data[0].get("mape") or {}
active_model = log_resp.data[0]["active_model"]

versions_df = pd.DataFrame(versions_resp.data)
retrain_counts = versions_df.groupby("model_type").size().to_dict()
active_rows = versions_df[versions_df["is_active"]].set_index("model_type")

rows = []
for model_type in retrain_counts:
    active_row = active_rows.loc[model_type] if model_type in active_rows.index else None
    n_features = len(active_row["selected_features"]) if active_row is not None and active_row["selected_features"] else 0
    rows.append({
        "model": model_type,
        "aktywny teraz": model_type == active_model,
        "MAPE (kroczące)": latest_mape.get(model_type),
        "liczba wersji": retrain_counts[model_type],
        "liczba cech": n_features,
    })

st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)

st.caption(
    "Do zbudowania: ile razy dany model był 'o krok' od przejęcia roli aktywnego "
    "(najdłuższa seria True w system_logs.beats_active, która nie dobiła do progu streak_days)."
)
