import streamlit as st

from theme import apply_theme

apply_theme()

st.title("Symulacja: co by było, gdyby trzymać się jednego modelu")
st.caption(
    "Dla każdego z 5 modeli: jak wyglądałoby jego skumulowane MAPE, gdyby był używany "
    "przez cały okres, zestawione z rzeczywistym wyborem systemu (dynamiczne przełączanie)."
)

st.caption(
    "Do zbudowania. Liczy się w całości z model_predictions (predykcje WSZYSTKICH modeli "
    "są tam zapisane na każdy dzień, nie tylko aktywnego) — bez zmian w main_pipeline.py."
)
