import altair as alt
import pandas as pd
import streamlit as st

from charts import adaptive_time_axis, padded_domain
from db import supabase
from theme import apply_theme

apply_theme()

st.title("Historia predykcji i jakość")
st.caption("Predykcje vs rzeczywiste wartości w czasie, rozkład błędów, kroczące MAPE")

RANGE_OPTIONS = ["10 dni", "30 dni", "90 dni", "180 dni", "365 dni", "wszystkie"]
zakres = st.segmented_control("Zakres", RANGE_OPTIONS, default="30 dni")
zakres = zakres or "30 dni"

today = pd.Timestamp.now().normalize()
if zakres == "wszystkie":
    cutoff = None
else:
    days = int(zakres.split(" ")[0])
    cutoff = (today - pd.Timedelta(days=days)).strftime("%Y-%m-%d")

# Kolejność modeli spójna z resztą apki (Retreningi) - wg pierwszego treningu.
models_resp = supabase.table("models_logs").select("id, model_type, created_at").execute()
models_df = pd.DataFrame(models_resp.data or [])
if models_df.empty:
    st.info("Brak jeszcze żadnych danych.")
    st.stop()

id_to_type = dict(zip(models_df["id"], models_df["model_type"]))
model_order = (
    models_df.groupby("model_type")["created_at"].min().sort_values().index.tolist()
)

pred_query = (
    supabase.table("model_predictions")
    .select("target_date, model_id, predicted_value, actual_value, error_value")
    .eq("status", "evaluated")
)
if cutoff:
    pred_query = pred_query.gte("target_date", cutoff)
pred_resp = pred_query.order("target_date").execute()

if not pred_resp.data:
    st.info("Brak jeszcze ocenionych predykcji w wybranym zakresie.")
    st.stop()

df = pd.DataFrame(pred_resp.data)
df["target_date"] = pd.to_datetime(df["target_date"])
df["model_type"] = df["model_id"].map(id_to_type)

# Widoczność kropek na liniach zależy od FAKTYCZNEGO rozstrzału dat w
# przefiltrowanych danych, nie od wybranej etykiety zakresu - dzięki temu
# "wszystkie" też dostanie kropki, dopóki historia jest krótka, i straci
# je automatycznie, gdy urośnie ponad 90 dni, bez specjalnego przypadku.
actual_span_days = (df["target_date"].max() - df["target_date"].min()).days
show_points = actual_span_days < 90

# Oś X pokazuje CAŁE wybrane okno (cutoff -> dziś), nie tylko ciasno
# dopasowany zakres danych - jeśli historia jest krótsza niż wybrany
# zakres, początek osi zostaje pusty, a linie zaczynają się tam, gdzie
# faktycznie zaczynają się dane. Przy "wszystkie" nie ma z góry ustalonego
# okna, więc oś i tak ciasno trzyma się danych.
axis_start = pd.Timestamp(cutoff) if cutoff else df["target_date"].min()
if zakres == "10 dni":
    # Tylko wizualne przycięcie osi o 1 dzień z lewej - dane (cutoff w
    # zapytaniach do bazy) zostają bez zmian, tnie się wyłącznie oś.
    axis_start = axis_start + pd.Timedelta(days=1)
axis_domain = [axis_start, today]

# --- Predykcja vs rzeczywista wartość w czasie ---
st.subheader("Predykcja vs rzeczywista wartość")

pred_lines = df[["target_date", "model_type", "predicted_value"]].rename(
    columns={"model_type": "seria", "predicted_value": "wartość"}
)
actual_lines = (
    df.drop_duplicates("target_date")[["target_date", "actual_value"]]
    .rename(columns={"actual_value": "wartość"})
)
actual_lines["seria"] = "Zamknięcie"
line_df = pd.concat([pred_lines, actual_lines[["target_date", "seria", "wartość"]]], ignore_index=True)
line_df["is_actual"] = line_df["seria"] == "Zamknięcie"

price_chart = (
    alt.Chart(line_df)
    .mark_line(point=show_points)
    .encode(
        x=alt.X(
            "target_date:T",
            axis=adaptive_time_axis(axis_start),
            scale=alt.Scale(domain=axis_domain, nice=False),
        ),
        y=alt.Y("wartość:Q", title="Cena ($)", scale=alt.Scale(domain=padded_domain(line_df["wartość"]))),
        color=alt.Color(
            "seria:N", title=None, scale=alt.Scale(domain=model_order + ["Zamknięcie"], scheme="dark2")
        ),
        # strokeWidth, nie size - "size" jest współdzielone z rozmiarem
        # punktów markera (point=True), więc dawało niemal niewidoczne kropki
        # dla modeli (range 1.5-3 to sensowna grubość linii w px, ale
        # mikroskopijny rozmiar punktu).
        strokeWidth=alt.StrokeWidth(
            "is_actual:N", scale=alt.Scale(domain=[True, False], range=[3, 1.5]), legend=None
        ),
        tooltip=[
            alt.Tooltip("target_date:T", title="Data"),
            alt.Tooltip("seria:N", title="Seria"),
            alt.Tooltip("wartość:Q", title="Wartość", format="$.2f"),
        ],
    )
    .properties(height=340)
)
st.altair_chart(price_chart, width="stretch")

st.divider()

# --- Rozkład błędów per model ---
st.subheader("Rozkład błędów")

n_bins = 15
df["bin"] = pd.cut(df["error_value"], bins=n_bins)
df["bin_center"] = df["bin"].apply(lambda b: (b.left + b.right) / 2)
df["bin_label"] = df["bin"].apply(lambda b: f"${b.left:.2f} → ${b.right:.2f}")

hist_df = (
    df.groupby(["model_type", "bin_center", "bin_label"], observed=True)
    .size()
    .reset_index(name="liczba")
)

hist = (
    alt.Chart(hist_df)
    .mark_bar()
    .encode(
        x=alt.X("bin_center:Q", title="Błąd ($)"),
        y=alt.Y("liczba:Q", title="Liczba"),
        color=alt.Color("model_type:N", scale=alt.Scale(domain=model_order, scheme="dark2"), legend=None),
        tooltip=[
            alt.Tooltip("bin_label:N", title="Zakres"),
            alt.Tooltip("liczba:Q", title="Liczba"),
        ],
    )
    .properties(width=150, height=160)
    .facet(column=alt.Column("model_type:N", title=None, sort=model_order))
)
st.altair_chart(hist)

st.divider()

# --- Kroczące MAPE ---
st.subheader("Kroczące MAPE")
mape_query = supabase.table("system_logs").select("log_date, mape")
if cutoff:
    mape_query = mape_query.gte("log_date", cutoff)
mape_resp = mape_query.order("log_date").execute()

mape_rows = []
for row in mape_resp.data or []:
    for model_type, value in (row.get("mape") or {}).items():
        if value is not None:
            mape_rows.append({"log_date": row["log_date"], "model_type": model_type, "MAPE": value})

if mape_rows:
    mape_df = pd.DataFrame(mape_rows)
    mape_df["log_date"] = pd.to_datetime(mape_df["log_date"])
    mape_chart = (
        alt.Chart(mape_df)
        .mark_line(point=show_points)
        .encode(
            x=alt.X(
                "log_date:T",
                axis=adaptive_time_axis(axis_start),
                scale=alt.Scale(domain=axis_domain, nice=False),
            ),
            y=alt.Y("MAPE:Q", title="MAPE (%)", scale=alt.Scale(domain=padded_domain(mape_df["MAPE"]))),
            color=alt.Color("model_type:N", title=None, scale=alt.Scale(domain=model_order, scheme="dark2")),
            tooltip=[
                alt.Tooltip("log_date:T", title="Data"),
                alt.Tooltip("model_type:N", title="Model"),
                alt.Tooltip("MAPE:Q", title="MAPE", format=".2f"),
            ],
        )
        .properties(height=300)
    )
    st.altair_chart(mape_chart, width="stretch")
else:
    st.info("Brak danych MAPE w wybranym zakresie.")
