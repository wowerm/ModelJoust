import streamlit as st

from data import get_all_snapshots_sorted
from formatting import error_with_pct
from theme import apply_theme

apply_theme()

st.title("Dziś")
st.caption("Prognoza ceny zamknięcia złota (GC=F, COMEX) na najbliższy dzień sesyjny")

active_model_type, snapshots = get_all_snapshots_sorted()
if not snapshots:
    st.info("Brak jeszcze żadnych danych.")
    st.stop()

active = snapshots[0]
pending = active["pending"]
evaluated = active["evaluated"]

# --- Aktywny model ---
if pending:
    st.markdown(
        f"""
        <div style='text-align:center;padding:1.5rem 0;'>
            <div style='color:#94a3b8;font-size:0.85rem;letter-spacing:0.12em;text-transform:uppercase;'>
                {active['model_type']} (v{active['model_version']}) — aktywny model
            </div>
            <div style='font-size:4rem;font-weight:700;color:#C9A961;line-height:1.15;'>
                ${pending['predicted_value']:.2f}
            </div>
            <div style='color:#94a3b8;'>prognoza na {pending['target_date']}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if pending.get("llm_comment"):
        st.markdown(f"> {pending['llm_comment']}")
else:
    st.info("Brak oczekującej predykcji.")

if evaluated:
    st.divider()
    # --- Metryki ---
    c1, c2, c3 = st.columns(3)
    c1.metric("Przewidziano", f"${evaluated['predicted_value']:.2f}")
    c2.metric("Rzeczywiste", f"${evaluated['actual_value']:.2f}")
    c3.metric("Błąd", error_with_pct(evaluated["error_value"], evaluated["actual_value"]))

st.divider()
# --- Pozostałe modele ---
st.caption("Pozostałe modele — od najlepszego do najgorszego wg kroczącego MAPE")

others = snapshots[1:]
if others:
    cols = st.columns(len(others))
    for rank, (col, snapshot) in enumerate(zip(cols, others), start=2):
        with col, st.container(border=True):
            st.markdown(
                f"<div style='color:#64748b;font-size:0.75rem;letter-spacing:0.08em;"
                f"text-transform:uppercase;'>#{rank}</div>"
                f"<div style='font-weight:600;'>{snapshot['model_type']} "
                f"<span style='color:#64748b;font-weight:400;'>v{snapshot['model_version']}</span></div>",
                unsafe_allow_html=True,
            )
            if snapshot["mape"] is not None:
                st.markdown(
                    f"<div style='color:#94a3b8;font-size:0.8rem;'>MAPE: {snapshot['mape']:.2f}%</div>",
                    unsafe_allow_html=True,
                )

            if snapshot["pending"]:
                st.markdown(
                    f"<div style='font-size:1.3rem;font-weight:600;margin-top:0.4rem;'>"
                    f"${snapshot['pending']['predicted_value']:.2f}</div>",
                    unsafe_allow_html=True,
                )
            else:
                st.caption("brak prognozy")

            if snapshot["evaluated"]:
                ev = snapshot["evaluated"]
                st.caption(f"ostatni błąd: {error_with_pct(ev['error_value'], ev['actual_value'])}")
