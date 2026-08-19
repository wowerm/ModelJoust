import altair as alt
import pandas as pd
import streamlit as st

from charts import adaptive_time_axis
from db import supabase
from theme import apply_theme

apply_theme()

st.title("Retreningi")
st.caption("Historia wersji wszystkich modeli — kiedy, dlaczego, na jakim oknie danych")

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
# retrain_trigger bywa np. "DD(X_VIX,X_Copper)" - wyciągamy sam prefiks
# (init/DD/CD/DeadFeature) i tłumaczymy na czytelną nazwę.
raw_reason = df["retrain_trigger"].fillna("brak").str.extract(r"^([A-Za-z]+)")[0]
df["powód"] = raw_reason.map(REASON_LABELS).fillna(raw_reason)

# Kolejność modeli = kolejność pierwszego treningu w bazie (odpowiada
# kolejności MODEL_CLASSES w main_pipeline.py), nie alfabetyczna.
model_order = df.groupby("model_type")["created_at"].min().sort_values().index.tolist()

st.subheader("Liczba wersji per model")
counts = df["model_type"].value_counts().reindex(model_order)
cols = st.columns(len(counts))
for col, (model_type, count) in zip(cols, counts.items()):
    col.metric(model_type, int(count))

counts_df = counts.reset_index()
counts_df.columns = ["model", "liczba wersji"]
model_bars = (
    alt.Chart(counts_df)
    .mark_bar(color="#C9A961")
    .encode(
        x=alt.X("model:N", title=None, sort=model_order, axis=AXIS_LABEL_STYLE),
        y=alt.Y("liczba wersji:Q", title="Liczba wersji", axis=alt.Axis(tickMinStep=1, format="d")),
    )
)
model_labels = (
    alt.Chart(counts_df)
    .mark_text(dy=-8)
    .encode(
        x=alt.X("model:N", sort=model_order),
        y=alt.Y("liczba wersji:Q"),
        text="liczba wersji:Q",
    )
)
st.altair_chart((model_bars + model_labels).properties(height=220), width="stretch")

st.divider()

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
        y=alt.Y("model_type:N", title=None, sort=model_order),
        color=alt.Color("powód:N", title=None, scale=alt.Scale(scheme="dark2")),
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

st.subheader("Powody retreningów")
# Wszystkie możliwe powody, nawet te, które jeszcze nigdy nie wystąpiły (0).
all_reasons = sorted(set(REASON_LABELS.values()) | set(df["powód"].unique()))
reason_counts = df["powód"].value_counts().reindex(all_reasons).fillna(0).astype(int).reset_index()
reason_counts.columns = ["powód", "liczba"]

reason_bars = (
    alt.Chart(reason_counts)
    .mark_bar()
    .encode(
        x=alt.X("powód:N", title=None, sort=all_reasons, axis=AXIS_LABEL_STYLE),
        y=alt.Y("liczba:Q", title="Liczba"),
        color=alt.Color("powód:N", title="Powód", scale=alt.Scale(scheme="dark2"), legend=None),
    )
)
reason_labels = (
    alt.Chart(reason_counts)
    .mark_text(dy=-8)
    .encode(
        x=alt.X("powód:N", sort=all_reasons),
        y=alt.Y("liczba:Q"),
        text="liczba:Q",
    )
)
st.altair_chart((reason_bars + reason_labels).properties(height=280), width="stretch")

st.divider()

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
            st.write(", ".join(features))

st.divider()

st.subheader("Pełna historia wersji")
st.dataframe(
    df.sort_values("created_at", ascending=False).drop(columns=["powód"]),
    width="stretch",
    hide_index=True,
)
