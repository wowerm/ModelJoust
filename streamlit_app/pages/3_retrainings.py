import altair as alt
import pandas as pd
import streamlit as st

from charts import GRID_STYLE, LABEL_STYLE, REASON_COLORS, adaptive_time_axis, bar_y_domain, model_color_scale
from db import supabase
from theme import apply_theme

apply_theme()

st.title("Retreningi")
st.caption("Historia wersji wszystkich modeli")

REASON_LABELS = {
    "DD": "Data Drift",
    "CD": "Concept Drift",
    "init": "Pierwszy trening",
    "DeadFeature": "Martwa cecha",
}

AXIS_LABEL_STYLE = alt.Axis(labelAngle=-45, labelFontSize=13)

resp = (
    supabase.table("models_logs")
    .select(
        "model_type, model_version, is_active, retrain_trigger, "
        "train_start_date, train_end_date, selected_features, created_at"
    )
    .order("created_at")
    .execute()
)

if not resp.data:
    st.info("Brak jeszcze żadnych wersji modeli.")
    st.stop()

df = pd.DataFrame(resp.data)
df["created_at"] = pd.to_datetime(df["created_at"])
df["train_end_date"] = pd.to_datetime(df["train_end_date"])
df["train_start_date"] = pd.to_datetime(df["train_start_date"])
raw_reason = df["retrain_trigger"].fillna("brak").str.extract(r"^([A-Za-z]+)")[0]
df["powód"] = raw_reason.map(REASON_LABELS).fillna(raw_reason)

# Kolejność modeli = kolejność pierwszego treningu w bazie (odpowiada
# kolejności MODEL_CLASSES w main_pipeline.py), nie alfabetyczna.
model_order = df.groupby("model_type")["created_at"].min().sort_values().index.tolist()
# Wszystkie możliwe powody, nawet te, które jeszcze nigdy nie wystąpiły
all_reasons = sorted(set(REASON_LABELS.values()) | set(df["powód"].unique()))
reason_color_scale = alt.Scale(domain=all_reasons, range=REASON_COLORS[: len(all_reasons)])

# --- Liczba wersji per model ---
st.subheader("Liczba wersji per model")
counts = df["model_type"].value_counts().reindex(model_order)

counts_df = counts.reset_index()
counts_df.columns = ["model", "liczba wersji"]
model_bars = (
    alt.Chart(counts_df)
    .mark_bar()
    .encode(
        x=alt.X("model:N", title=None, sort=model_order, axis=AXIS_LABEL_STYLE),
        y=alt.Y(
            "liczba wersji:Q", title="Liczba wersji",
            axis=alt.Axis(tickMinStep=1, format="d"),
            scale=alt.Scale(domain=bar_y_domain(counts_df["liczba wersji"])),
        ),
        color=alt.Color("model:N", scale=model_color_scale(model_order), legend=None),
    )
)
model_labels = (
    alt.Chart(counts_df)
    .mark_text(dy=-14, fontSize=26, fontWeight="bold", color="#FFFFFF")
    .encode(
        x=alt.X("model:N", sort=model_order),
        y="liczba wersji:Q",
        text="liczba wersji:Q",
    )
)
st.altair_chart((model_bars + model_labels).properties(height=260), width="stretch")

st.divider()

# --- Oś czasu retreningów ---
st.subheader("Oś czasu retreningów")
timeline_df = df.dropna(subset=["train_end_date"])

timeline = (
    alt.Chart(timeline_df)
    .mark_circle(size=160)
    .encode(
        x=alt.X(
            "train_end_date:T",
            title=None,
            axis=adaptive_time_axis(timeline_df["train_end_date"].min()),
            scale=alt.Scale(nice=False),
        ),
        y=alt.Y("model_type:N", title=None, sort=model_order, axis=alt.Axis(**GRID_STYLE)),
        color=alt.Color("powód:N", title=None, scale=reason_color_scale),
        tooltip=[
            alt.Tooltip("model_type:N", title="Model"),
            alt.Tooltip("model_version:Q", title="Wersja"),
            alt.Tooltip("powód:N", title="Powód"),
            alt.Tooltip("train_start_date:T", title="Okno od"),
            alt.Tooltip("train_end_date:T", title="Okno do"),
        ],
    )
    .properties(height=260)
)
st.altair_chart(timeline, width="stretch")

st.divider()

# --- Powody retreningów ---
st.subheader("Powody retreningów")
reason_counts = df["powód"].value_counts().reindex(all_reasons).fillna(0).astype(int).reset_index()
reason_counts.columns = ["powód", "liczba"]

reason_bars = (
    alt.Chart(reason_counts)
    .mark_bar()
    .encode(
        x=alt.X("powód:N", title=None, sort=all_reasons, axis=AXIS_LABEL_STYLE),
        y=alt.Y("liczba:Q", title="Liczba"),
        color=alt.Color("powód:N", title="Powód", scale=reason_color_scale, legend=None),
    )
)
reason_labels = (
    alt.Chart(reason_counts)
    .mark_text(**LABEL_STYLE)
    .encode(
        x=alt.X("powód:N", sort=all_reasons),
        y=alt.Y("liczba:Q"),
        text="liczba:Q",
    )
)
st.altair_chart((reason_bars + reason_labels).properties(height=280), width="stretch")

st.divider()

# --- Aktywne modele ---
st.subheader("Aktywne modele — okno treningowe i cechy")
active_df = df[df["is_active"]]
for _, row in active_df.iterrows():
    features = row["selected_features"] or []
    with st.container(border=True):
        st.markdown(f"**{row['model_type']}** (v{int(row['model_version'])})")
        if pd.notna(row["train_start_date"]) and pd.notna(row["train_end_date"]):
            st.caption(
                f"Okno treningowe: {row['train_start_date'].date()} → {row['train_end_date'].date()}"
            )
        else:
            st.caption("Brak okna treningowego (model bazowy).")
        st.caption(f"Liczba cech: {len(features)}")
        if features:
            chips_html = "".join(
                f"<span style='display:inline-block;background:rgba(148,163,184,0.12);"
                f"color:#CBD5E1;border:1px solid #2A2F3A;border-radius:999px;"
                f"padding:0.2rem 0.7rem;margin:0.15rem 0.25rem 0.15rem 0;font-size:0.8rem;'>"
                f"{feature}</span>"
                for feature in features
            )
            st.markdown(f"<div style='margin-top:0.4rem;'>{chips_html}</div>", unsafe_allow_html=True)

st.divider()

# --- Pełna historia wersji ---
st.subheader("Pełna historia wersji")

history_df = df.sort_values("created_at", ascending=False).copy()
history_df["Liczba cech"] = history_df["selected_features"].apply(lambda f: len(f) if f else 0)
history_df["Trening od"] = history_df["train_start_date"].apply(lambda d: d.strftime("%Y-%m-%d") if pd.notna(d) else "—")
history_df["Trening do"] = history_df["train_end_date"].apply(lambda d: d.strftime("%Y-%m-%d") if pd.notna(d) else "—")
history_df["Utworzono"] = history_df["created_at"].dt.strftime("%Y-%m-%d %H:%M")

history_df = history_df.rename(columns={
    "model_type": "Model",
    "model_version": "Wersja",
    "is_active": "Aktywny",
    "powód": "Powód",
})[["Model", "Wersja", "Aktywny", "Powód", "Trening od", "Trening do", "Liczba cech", "Utworzono"]]


def highlight_active_row(row: pd.Series) -> list[str]:
    if row["Aktywny"]:
        return ["background-color: rgba(34, 197, 94, 0.08)"] * len(row)
    return ["" for _ in row]


st.dataframe(
    history_df.style.apply(highlight_active_row, axis=1),
    width="stretch",
    hide_index=True,
)
