from db import supabase


def get_active_model_type() -> str | None:
    log_resp = supabase.table("system_logs").select("*").order("log_date", desc=True).limit(1).execute()
    if not log_resp.data:
        return None
    return log_resp.data[0]["active_model"]


def get_latest_mape() -> dict:
    log_resp = supabase.table("system_logs").select("mape").order("log_date", desc=True).limit(1).execute()
    if not log_resp.data:
        return {}
    return log_resp.data[0].get("mape") or {}


def get_model_snapshot(model_type: str) -> dict | None:
    """Aktywna wersja danego modelu + jego oczekująca i ostatnia oceniona
    predykcja. Współdzielone przez wszystkie warianty strony 'Dziś'."""
    model_resp = (
        supabase.table("models_logs")
        .select("id, model_version")
        .eq("model_type", model_type)
        .eq("is_active", True)
        .limit(1)
        .execute()
    )
    if not model_resp.data:
        return None

    model_id = model_resp.data[0]["id"]

    pending_resp = (
        supabase.table("model_predictions")
        .select("*")
        .eq("model_id", model_id)
        .eq("status", "pending")
        .order("target_date", desc=True)
        .limit(1)
        .execute()
    )
    evaluated_resp = (
        supabase.table("model_predictions")
        .select("*")
        .eq("model_id", model_id)
        .eq("status", "evaluated")
        .order("target_date", desc=True)
        .limit(1)
        .execute()
    )

    return {
        "model_type": model_type,
        "model_version": model_resp.data[0]["model_version"],
        "pending": pending_resp.data[0] if pending_resp.data else None,
        "evaluated": evaluated_resp.data[0] if evaluated_resp.data else None,
    }


def get_all_snapshots_sorted() -> tuple[str, list[dict]]:
    """Zwraca (active_model_type, [snapshoty wszystkich aktywnych modeli
    posortowane po MAPE, aktywny zawsze pierwszy])."""
    active_model_type = get_active_model_type()
    latest_mape = get_latest_mape()

    all_resp = supabase.table("models_logs").select("model_type").eq("is_active", True).execute()
    snapshots = [get_model_snapshot(row["model_type"]) for row in (all_resp.data or [])]
    snapshots = [s for s in snapshots if s is not None]
    for s in snapshots:
        s["mape"] = latest_mape.get(s["model_type"])

    def sort_key(s):
        if s["model_type"] == active_model_type:
            return (0, 0)
        mape = latest_mape.get(s["model_type"])
        return (1, mape if mape is not None else float("inf"))

    snapshots.sort(key=sort_key)
    return active_model_type, snapshots
