import altair as alt
import pandas as pd
import streamlit as st

from charts import CATEGORY_AXIS, GRID_STYLE, LABEL_STYLE, bar_y_domain, model_color_scale
from db import supabase
from theme import apply_theme

apply_theme()

st.title("Dynamika: Champion / Challenger")
st.caption("Jak zachowuje się mechanizm wyboru aktywnego modelu, i czy dynamiczne przełączanie coś daje")

RANGE_OPTIONS = ["30 dni", "90 dni", "180 dni", "365 dni", "wszystkie"]
zakres = st.segmented_control("Zakres (dotyczy całej strony)", RANGE_OPTIONS, default="180 dni")
zakres = zakres or "180 dni"

# --- Dane wspólne, przefiltrowane wybranym zakresem ---
models_resp = supabase.table("models_logs").select("id, model_type, created_at").execute()
models_df = pd.DataFrame(models_resp.data or [])
if models_df.empty:
    st.info("Brak jeszcze żadnych danych.")
    st.stop()

id_to_type = dict(zip(models_df["id"], models_df["model_type"]))
model_order = models_df.groupby("model_type")["created_at"].min().sort_values().index.tolist()

log_resp = supabase.table("system_logs").select("log_date, active_model, mape").order("log_date").execute()
system_df_full = pd.DataFrame(log_resp.data or [])
if system_df_full.empty:
    st.info("Brak jeszcze danych w system_logs.")
    st.stop()
system_df_full["log_date"] = pd.to_datetime(system_df_full["log_date"])

pred_resp = (
    supabase.table("model_predictions")
    .select("target_date, model_id, predicted_value, actual_value, error_value")
    .eq("status", "evaluated")
    .execute()
)
pred_df_full = pd.DataFrame(pred_resp.data or [])
pred_df_full["target_date"] = pd.to_datetime(pred_df_full["target_date"])
pred_df_full["model_type"] = pred_df_full["model_id"].map(id_to_type)

if zakres == "wszystkie":
    system_df = system_df_full
    pred_df = pred_df_full
else:
    days = int(zakres.split(" ")[0])
    cutoff_date = pd.Timestamp.now().normalize() - pd.Timedelta(days=days)
    system_df = system_df_full[system_df_full["log_date"] >= cutoff_date]
    pred_df = pred_df_full[pred_df_full["target_date"] >= cutoff_date]

# =====================================================================
# 1. Dynamiczne przełączanie vs trzymanie się jednego modelu
# =====================================================================
st.subheader("Dynamiczne przełączanie vs jeden stały model")
st.caption(
    "Średnie MAPE w wybranym zakresie — dla każdego modelu, gdyby był aktywny przez cały "
    "okres, zestawione z MAPE wygenerowanym przez predykcje aktywnego danego dnia modelu."
)

SYSTEM_LABEL = "system"

realized_df = system_df.merge(
    pred_df, left_on=["log_date", "active_model"], right_on=["target_date", "model_type"]
)

comparison_rows = []
for model_type in model_order:
    sub = pred_df[pred_df["model_type"] == model_type]
    if sub.empty:
        continue
    static_mape = (sub["error_value"].abs() / sub["actual_value"].abs()).mean() * 100
    comparison_rows.append({"model": f"zawsze {model_type}", "MAPE": static_mape})

if not realized_df.empty:
    realized_mape = (realized_df["error_value"].abs() / realized_df["actual_value"].abs()).mean() * 100
    comparison_rows.append({"model": SYSTEM_LABEL, "MAPE": realized_mape})

if comparison_rows:
    comparison_df = pd.DataFrame(comparison_rows)
    comparison_order = [f"zawsze {m}" for m in model_order] + [SYSTEM_LABEL]

    comp_bars = (
        alt.Chart(comparison_df)
        .mark_bar()
        .encode(
            x=alt.X("model:N", title=None, sort=comparison_order, axis=CATEGORY_AXIS),
            y=alt.Y(
                "MAPE:Q",
                title="Średnie MAPE (%)",
                scale=alt.Scale(domain=bar_y_domain(comparison_df["MAPE"])),
            ),
            color=alt.condition(
                alt.datum.model == SYSTEM_LABEL,
                alt.value("#C9A961"),
                alt.value("#64748b"),
            ),
            tooltip=[
                alt.Tooltip("model:N", title="Model"),
                alt.Tooltip("MAPE:Q", title="MAPE", format=".2f"),
            ],
        )
    )
    comp_labels = comp_bars.mark_text(**LABEL_STYLE).encode(text=alt.Text("MAPE:Q", format=".2f"))
    st.altair_chart((comp_bars + comp_labels).properties(height=320), width="stretch")
else:
    st.info("Brak danych w wybranym zakresie.")

st.divider()

# =====================================================================
# 2. Ile dni każdy model był aktywny
# =====================================================================
st.subheader("Ile dni każdy model był aktywny")

active_days = system_df["active_model"].value_counts().reindex(model_order).fillna(0).astype(int)
active_days_df = active_days.reset_index()
active_days_df.columns = ["model", "dni"]

days_bars = (
    alt.Chart(active_days_df)
    .mark_bar()
    .encode(
        x=alt.X("model:N", title=None, sort=model_order, axis=CATEGORY_AXIS),
        y=alt.Y(
            "dni:Q",
            title="Liczba dni aktywności",
            axis=alt.Axis(tickMinStep=1, format="d"),
            scale=alt.Scale(domain=bar_y_domain(active_days_df["dni"])),
        ),
        color=alt.Color("model:N", scale=model_color_scale(model_order), legend=None),
        tooltip=[
            alt.Tooltip("model:N", title="Model"),
            alt.Tooltip("dni:Q", title="Dni aktywności"),
        ],
    )
)
days_labels = days_bars.mark_text(**LABEL_STYLE).encode(text="dni:Q")
st.altair_chart((days_bars + days_labels).properties(height=280), width="stretch")

st.divider()

# =====================================================================
# 3. Pasek czasowy aktywności
# =====================================================================
st.subheader("Pasek czasowy aktywności")

timeline_strip = (
    alt.Chart(system_df)
    .mark_bar(height=40)
    .encode(
        x=alt.X("log_date:O", title=None, axis=alt.Axis(labels=False, ticks=False, **GRID_STYLE)),
        color=alt.Color(
            "active_model:N",
            title=None,
            scale=model_color_scale(model_order),
            legend=alt.Legend(orient="bottom"),
        ),
        tooltip=[
            alt.Tooltip("log_date:T", title="Data"),
            alt.Tooltip("active_model:N", title="Aktywny model"),
        ],
    )
    .properties(height=90)
)
st.altair_chart(timeline_strip, width="stretch")

st.divider()

# =====================================================================
# 4. Korelacja błędów między modelami
# =====================================================================
st.subheader("Korelacja błędów między modelami")
st.caption("Czy modele mylą się razem, czy niezależnie.")

pivot = pred_df.pivot_table(index="target_date", columns="model_type", values="error_value")
available_models = [m for m in model_order if m in pivot.columns]
if len(available_models) >= 2:
    corr = pivot[available_models].corr()
    corr.index.name = "model_1"
    corr_long = corr.reset_index().melt(id_vars="model_1", var_name="model_2", value_name="corr")

    heatmap = (
        alt.Chart(corr_long)
        .mark_rect()
        .encode(
            x=alt.X("model_1:N", title=None, sort=available_models),
            y=alt.Y("model_2:N", title=None, sort=available_models),
            color=alt.Color(
                "corr:Q", title="Korelacja", scale=alt.Scale(scheme="redblue", domain=[-1, 1], reverse=True)
            ),
            tooltip=[
                alt.Tooltip("model_1:N", title="Model A"),
                alt.Tooltip("model_2:N", title="Model B"),
                alt.Tooltip("corr:Q", title="Korelacja", format=".2f"),
            ],
        )
    )
    heatmap_labels = heatmap.mark_text(fontSize=13, fontWeight="bold").encode(
        text=alt.Text("corr:Q", format=".2f"),
        color=alt.value("black"),
    )
    st.altair_chart((heatmap + heatmap_labels).properties(height=300), width="stretch")
else:
    st.info("Za mało modeli ze wspólnymi ocenionymi predykcjami do policzenia korelacji.")
