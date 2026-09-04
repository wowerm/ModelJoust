"""
Analiza wrażliwości parametrów: dla każdej kombinacji z PARAM_GRID ustawia
te parametry w pipeline_config, czyści wyniki poprzedniej kombinacji,
odtwarza 200-dniową symulację main_pipeline.main() od zera, liczy
podsumowanie (metryki per model + "system", retreningi, kolejność zmian
aktywnego modelu) i zapisuje je jako jeden wiersz w sensitivity_sweep_results
(schema.sql - trzeba założyć ręcznie raz przed pierwszym uruchomieniem).

Samodzielny skrypt - celowo NIE importuje first_setup/simulate_days.py ani
niczego z streamlit_app/, żeby nie ruszać istniejącego kodu pipeline'u/apki.

Bezpieczny do przerwania i wznowienia w dowolnym momencie: każda kombinacja
zapisuje wynik dopiero po pełnym zakończeniu, a już zapisane kombinacje są
pomijane przy kolejnym uruchomieniu (sprawdzane po polu `params`).
"""
import itertools
import sys
import time
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import DEFAULT_CONFIG
from db_client import supabase, STORAGE_BUCKET
from main_pipeline import main as run_single_day

SIM_DAYS = 200

# Zatrzymaj się przed startem NOWEJ kombinacji po tylu godzinach od startu
# tego uruchomienia - zostawia ok. 1h bufora do twardego limitu 6h na
# hostowanym runnerze GitHub Actions, na wypadek trafienia na wolniejszą
# kombinację (więcej retreningów niż bazowa konfiguracja).
TIME_BUDGET_HOURS = 5

MODEL_TYPES = ["naive", "OLS", "lasso", "random_forest", "xgboost"]
MODEL_CODES = {"naive": "n", "OLS": "o", "lasso": "l", "random_forest": "r", "xgboost": "x"}

# Klucze muszą być identyczne z kluczami w pipeline_config / DEFAULT_CONFIG.
# active_model_streak_days celowo tylko 2 wartości (bez bazowej "3") - margin
# i streak sterują tym samym mechanizmem (próg zmiany aktywnego modelu), więc
# pełne 3x3 dla obu naraz byłoby w dużej mierze nadmiarowe. Jeśli 2 i 5 wyjdą
# wyraźnie różne, osobny, pojedynczy test z wartością 3 dołoży się tanio.
PARAM_GRID = {
    "data_drift_z_threshold": [2.0, 3.0, 4.0],
    "active_model_margin": [0.005, 0.01, 0.02],
    "active_model_streak_days": [2, 5],
    "training_window_years": [3, 5],
}


# --- Konfiguracja i reset stanu między kombinacjami ---

def set_config(params: dict) -> None:
    """Nadpisuje podane klucze pipeline_config, tym samym wzorcem co panel
    admina (dezaktywacja starego aktywnego wiersza + insert nowego -
    historia zmian zostaje w tabeli). Pozostałe klucze configu (spoza
    PARAM_GRID) zostają nietknięte, na swoich aktualnych wartościach."""
    for key, value in params.items():
        supabase.table("pipeline_config").update({"active": False}).eq("key", key).eq("active", True).execute()
        description = DEFAULT_CONFIG[key][1]
        supabase.table("pipeline_config").insert(
            {"key": key, "value": value, "description": description, "active": True}
        ).execute()


def reset_state() -> None:
    """Czyści wyniki poprzedniej kombinacji: model_predictions (musi być
    pierwsze - ma FK do models_logs, inaczej baza odrzuci kasowanie),
    models_logs, system_logs, oraz bucket Storage z zapisanymi modelami
    (inaczej numeracja wersji zaczynająca się od v1 przy każdej kombinacji
    zaczęłaby nadpisywać/osierocać pliki poprzednich kombinacji). NIE rusza
    raw_data ani reszty pipeline_config."""
    supabase.table("model_predictions").delete().gte("prediction_id", 0).execute()
    supabase.table("models_logs").delete().gte("id", 0).execute()
    supabase.table("system_logs").delete().gte("log_date", "1900-01-01").execute()

    files = supabase.storage.from_(STORAGE_BUCKET).list()
    paths = [f["name"] for f in files]
    if paths:
        supabase.storage.from_(STORAGE_BUCKET).remove(paths)


def run_simulation_days(days: int) -> None:
    end_date = pd.Timestamp.now(tz="America/New_York").normalize().tz_localize(None)
    sim_dates = pd.bdate_range(end=end_date, periods=days)
    for i, date in enumerate(sim_dates, start=1):
        print(f"  dzień {i}/{len(sim_dates)}: {date.date()}")
        try:
            run_single_day(as_of_date=date)
        except Exception as e:
            print(f"  BŁĄD w dniu {date.date()}: {e}")


# --- Podsumowanie kombinacji ---

def fetch_evaluated_predictions() -> pd.DataFrame:
    rows = []
    start, page = 0, 1000
    while True:
        resp = (
            supabase.table("model_predictions")
            .select("target_date, model_id, predicted_value, actual_value")
            .eq("status", "evaluated")
            .order("target_date")
            .range(start, start + page - 1)
            .execute()
        )
        batch = resp.data or []
        rows.extend(batch)
        if len(batch) < page:
            break
        start += page
    return pd.DataFrame(rows)


def error_metrics(df: pd.DataFrame) -> dict:
    """MAPE/MAE/RMSE liczone tak samo jak w prediction_evaluation.py
    (error = predicted - actual). Trafność kierunku: czy model poprawnie
    przewidział kierunek zmiany względem OSTATNIEJ znanej ceny - dokładnie
    to, co model faktycznie prognozuje (predicted_price = last_actual_y_level
    * (1 + predicted_return)), nie względem poprzedniej predykcji."""
    if df.empty:
        return {"mape": None, "mae": None, "rmse": None, "direction_accuracy": None}

    df = df.sort_values("target_date").reset_index(drop=True)
    error = df["predicted_value"] - df["actual_value"]
    mape = float((error.abs() / df["actual_value"].abs()).mean() * 100)
    mae = float(error.abs().mean())
    rmse = float((error ** 2).mean() ** 0.5)

    prev_actual = df["actual_value"].shift(1)
    valid = prev_actual.notna()
    direction_accuracy = None
    if valid.any():
        actual_up = (df["actual_value"] - prev_actual) > 0
        predicted_up = (df["predicted_value"] - prev_actual) > 0
        direction_accuracy = float((actual_up[valid] == predicted_up[valid]).mean() * 100)

    return {"mape": mape, "mae": mae, "rmse": rmse, "direction_accuracy": direction_accuracy}


def compute_summary(sim_days: int) -> dict:
    id_to_type = {
        row["id"]: row["model_type"]
        for row in (supabase.table("models_logs").select("id, model_type").execute().data or [])
    }
    pred_df = fetch_evaluated_predictions()
    if not pred_df.empty:
        pred_df["model_type"] = pred_df["model_id"].map(id_to_type)

    metrics = {}
    for model_type in MODEL_TYPES:
        model_df = pred_df[pred_df["model_type"] == model_type] if not pred_df.empty else pd.DataFrame()
        metrics[model_type] = error_metrics(model_df)

    logs_rows = (
        supabase.table("system_logs").select("log_date, active_model").order("log_date").execute().data or []
    )
    active_model_sequence = [MODEL_CODES.get(row["active_model"], "?") for row in logs_rows]

    if not pred_df.empty and logs_rows:
        active_by_date = {row["log_date"]: row["active_model"] for row in logs_rows}
        pred_df["active_model_that_day"] = pred_df["target_date"].map(active_by_date)
        system_df = pred_df[pred_df["model_type"] == pred_df["active_model_that_day"]]
    else:
        system_df = pd.DataFrame()
    metrics["system"] = error_metrics(system_df)

    retrain_rows = supabase.table("models_logs").select("model_type, retrain_trigger").execute().data or []
    retrainings = {}
    for model_type in MODEL_TYPES:
        reasons = [row["retrain_trigger"] for row in retrain_rows if row["model_type"] == model_type]
        reason_counts = {}
        for reason in reasons:
            reason_counts[reason] = reason_counts.get(reason, 0) + 1
        retrainings[model_type] = {"count": len(reasons), "reasons": reason_counts}

    return {
        "metrics": metrics,
        "retrainings": retrainings,
        "active_model_sequence": active_model_sequence,
        "sim_days": sim_days,
    }


# --- Pętla po siatce parametrów ---

def combo_already_done(params: dict) -> bool:
    resp = supabase.table("sensitivity_sweep_results").select("id").eq("params", params).limit(1).execute()
    return bool(resp.data)


def save_result(params: dict, summary: dict) -> None:
    payload = {"params": params, **summary}
    supabase.table("sensitivity_sweep_results").insert(payload).execute()


def run_sweep() -> None:
    keys = list(PARAM_GRID.keys())
    combos = [dict(zip(keys, values)) for values in itertools.product(*PARAM_GRID.values())]
    print(f"Siatka: {len(combos)} kombinacji x {SIM_DAYS} dni symulacji każda.")

    start_time = time.time()
    budget_seconds = TIME_BUDGET_HOURS * 3600

    for i, params in enumerate(combos, start=1):
        if combo_already_done(params):
            print(f"[{i}/{len(combos)}] {params} - już zrobione, pomijam.")
            continue

        if time.time() - start_time > budget_seconds:
            print(f"\nZbliżam się do limitu {TIME_BUDGET_HOURS}h dla tego uruchomienia - kończę. "
                  f"Kolejne zaplanowane uruchomienie podejmie dalsze kombinacje.")
            return

        print(f"\n{'=' * 80}\n[{i}/{len(combos)}] {params}\n{'=' * 80}")
        t0 = time.time()

        set_config(params)
        reset_state()
        run_simulation_days(SIM_DAYS)
        summary = compute_summary(SIM_DAYS)
        save_result(params, summary)

        print(f"[{i}/{len(combos)}] gotowe w {(time.time() - t0) / 60:.1f} min.")

    print("\nWszystkie kombinacje zrobione.")


if __name__ == "__main__":
    run_sweep()
