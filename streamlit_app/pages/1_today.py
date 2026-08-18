import streamlit as st

from db import supabase
from theme import apply_theme

apply_theme()

st.title("Dziś")
st.caption("Predykcja aktywnego modelu na najbliższy dzień sesyjny")

log_resp = supabase.table("system_logs").select("*").order("log_date", desc=True).limit(1).execute()
if not log_resp.data:
    st.info("Brak jeszcze żadnych danych w system_logs.")
    st.stop()

active_model_type = log_resp.data[0]["active_model"]

model_resp = (
    supabase.table("models_logs")
    .select("id, model_version")
    .eq("model_type", active_model_type)
    .eq("is_active", True)
    .limit(1)
    .execute()
)
if not model_resp.data:
    st.warning(f"Brak aktywnej wersji modelu '{active_model_type}' w models_logs.")
    st.stop()

active_model_id = model_resp.data[0]["id"]
active_model_version = model_resp.data[0]["model_version"]

col_pred, col_last = st.columns([2, 1])

with col_pred:
    st.subheader(f"Aktywny model: {active_model_type} (v{active_model_version})")

    pending_resp = (
        supabase.table("model_predictions")
        .select("*")
        .eq("model_id", active_model_id)
        .eq("status", "pending")
        .order("target_date", desc=True)
        .limit(1)
        .execute()
    )
    if pending_resp.data:
        pred = pending_resp.data[0]
        st.metric(f"Predykcja na {pred['target_date']}", f"{pred['predicted_value']:.2f} USD")
        if pred.get("llm_comment"):
            st.markdown(f"> {pred['llm_comment']}")
    else:
        st.info("Brak oczekującej predykcji dla aktywnego modelu.")

with col_last:
    st.subheader("Ostatnia ocena")

    evaluated_resp = (
        supabase.table("model_predictions")
        .select("*")
        .eq("model_id", active_model_id)
        .eq("status", "evaluated")
        .order("target_date", desc=True)
        .limit(1)
        .execute()
    )
    if evaluated_resp.data:
        last_eval = evaluated_resp.data[0]
        st.caption(f"Wynik na {last_eval['target_date']}")

        sub1, sub2 = st.columns(2)
        sub1.metric("Przewidziano", f"{last_eval['predicted_value']:.2f} USD")
        sub2.metric("Rzeczywiste", f"{last_eval['actual_value']:.2f} USD")
        # Statyczny wynik oceny, nie trend w czasie - bez delta/strzałki,
        # żeby nie sugerować kierunku, którego tu po prostu nie ma.
        st.metric("Błąd", f"{last_eval['error_value']:+.2f} USD")
    else:
        st.info("Brak jeszcze ocenionych predykcji.")

st.divider()
st.subheader("Pozostałe modele")

others_resp = (
    supabase.table("models_logs")
    .select("model_type, model_version")
    .eq("is_active", True)
    .neq("model_type", active_model_type)
    .execute()
)
if others_resp.data:
    for row in others_resp.data:
        st.write(f"**{row['model_type']}** (v{row['model_version']}) — do podłączenia: dzisiejsza predykcja")
else:
    st.info("Brak innych aktywnych modeli.")
