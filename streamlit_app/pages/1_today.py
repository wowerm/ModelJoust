import streamlit as st

from data import get_all_snapshots_sorted
from formatting import error_with_pct, format_price, signed_dollar
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
    active_mape_text = f"{active['mape']:.2f}%" if active["mape"] is not None else "—"

    delta_html = ""
    if evaluated:
        delta = pending["predicted_value"] - evaluated["actual_value"]
        delta_pct = (delta / evaluated["actual_value"]) * 100 if evaluated["actual_value"] else 0.0
        arrow = "▲" if delta >= 0 else "▼"
        delta_color = "#22C55E" if delta >= 0 else "#EF4444"
        delta_html = (
            f"<div style='color:{delta_color};font-size:1.15rem;font-weight:600;margin-top:0.3rem;'>"
            f"{arrow} {signed_dollar(delta)} ({delta_pct:+.2f}%) względem ostatniego znanego zamknięcia</div>"
        )

    st.markdown(
        f"""
        <div style='text-align:center;padding:1.5rem 0;'>
            <div style='color:#94a3b8;font-size:0.85rem;letter-spacing:0.12em;text-transform:uppercase;'>
                {active['model_type']} (v{active['model_version']}) — aktywny model · MAPE kroczące: {active_mape_text}
            </div>
            <div style='font-size:4rem;font-weight:700;color:#C9A961;line-height:1.15;'>
                {format_price(pending['predicted_value'])}
            </div>
            {delta_html}
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
    c1.metric("Przewidziano", format_price(evaluated["predicted_value"]))
    c2.metric("Rzeczywista cena", format_price(evaluated["actual_value"]))
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
                    f"{format_price(snapshot['pending']['predicted_value'])}</div>",
                    unsafe_allow_html=True,
                )
            else:
                st.caption("brak prognozy")

            if snapshot["evaluated"]:
                ev = snapshot["evaluated"]
                st.caption(f"ostatni błąd: {error_with_pct(ev['error_value'], ev['actual_value'])}")
