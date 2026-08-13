import io

import joblib

from db_client import supabase, STORAGE_BUCKET


def get_next_model_version(model_type: str) -> int:
    """Zwraca kolejny numer wersji dla danego model_type w models_logs
    (1, jeśli żadna wersja jeszcze nie istnieje). Współdzielone przez
    wszystkie blackboxy."""
    response = (
        supabase.table("models_logs")
        .select("model_version")
        .eq("model_type", model_type)
        .not_.is_("model_version", "null")
        .order("model_version", desc=True)
        .limit(1)
        .execute()
    )
    if not response.data:
        return 1
    return response.data[0]["model_version"] + 1


def save_model_to_storage(model, selected_features: list, filename_prefix: str, model_version: int) -> str:
    """Serializuje (model + selected_features) i wrzuca do Supabase Storage
    jako {filename_prefix}_v{wersja}.joblib. baseline_stats NIE trafia tutaj
    - jedyne źródło prawdy to models_logs. filename_prefix to osobna
    konwencja nazewnicza per blackbox (np. "OLS", "RandomForest"), inna niż
    wartość model_type używana w zapytaniach do bazy (np. "OLS", "random_forest")."""
    bundle = {"model": model, "selected_features": selected_features}
    buffer = io.BytesIO()
    joblib.dump(bundle, buffer)
    buffer.seek(0)

    path = f"{filename_prefix}_v{model_version}.joblib"
    supabase.storage.from_(STORAGE_BUCKET).upload(
        path,
        buffer.read(),
        {"content-type": "application/octet-stream", "upsert": "true"},
    )
    return path


def load_model_from_storage(storage_path: str) -> dict:
    """Wczytuje bundle {"model", "selected_features"} zapisany przez
    save_model_to_storage()."""
    try:
        file_bytes = supabase.storage.from_(STORAGE_BUCKET).download(storage_path)
    except Exception as e:
        raise ValueError(f"Nie udało się wczytać modelu z '{storage_path}': {e}")

    return joblib.load(io.BytesIO(file_bytes))


def save_model_version_if_needed(model_type: str, result: dict, model_info: dict | None,
                                   retrain_trigger: str) -> int:
    """
    Po retreningu zapisuje nową wersję do models_logs (dezaktywując
    poprzednią, jeśli istniała) i zwraca id do użycia w model_predictions.

    Wyjątek dla "naive": model bazowy nigdy nie zyskuje realnie innej wersji
    (jego logika się nie zmienia) - nowy wiersz powstaje TYLKO gdy jeszcze
    żaden nie istniał (retrain_trigger='init'), żeby model_predictions miało
    do czego przypiąć model_id. Przy kolejnych "retreningach" (np. z Concept
    Driftu) zapis jest pomijany, istniejący wiersz zostaje aktywny.
    """
    if model_type == "naive" and model_info is not None:
        print(f"NaiveModel: pomijam zapis nowej wersji do models_logs "
              f"(retrain_trigger='{retrain_trigger}') - logika modelu bazowego się "
              f"nie zmienia, istniejący wiersz (id={model_info['id']}) zostaje aktywny.")
        return model_info["id"]

    if model_info is not None:
        try:
            supabase.table("models_logs").update(
                {"is_active": False}
            ).eq("id", model_info["id"]).execute()
        except Exception as e:
            print(f"Błąd dezaktywacji poprzedniej wersji modelu '{model_type}': {e}")

    payload = {
        "model_type": model_type,
        "model_version": result["model_version"],
        "is_active": True,
        "retrain_trigger": retrain_trigger,
        "train_start_date": result.get("train_start_date"),
        "train_end_date": result.get("train_end_date"),
        "baseline_stats": result["baseline_stats"],
        "selected_features": result["selected_features"],
        "storage_path": result["storage_path"],
        # nowa wersja startuje z czystym detektorem Page-Hinkleya
        "concept_drift_stats": None,
    }

    response = supabase.table("models_logs").insert(payload).execute()
    new_id = response.data[0]["id"]
    print(f"Zapisano nową wersję modelu '{model_type}' (v{result['model_version']}, id={new_id}, "
          f"retrain_trigger='{retrain_trigger}').")
    return new_id


def update_concept_drift_stats(model_type: str, model_id: int, new_cd_stats: dict) -> None:
    """Aktualizuje stan detektora Page-Hinkley (concept_drift_stats) dla
    wskazanej wersji modelu w models_logs."""
    try:
        supabase.table("models_logs").update(
            {"concept_drift_stats": new_cd_stats}
        ).eq("id", model_id).execute()
    except Exception as e:
        print(f"Błąd zapisu concept_drift_stats dla modelu '{model_type}': {e}")


def save_prediction(model_id: int, target_date: str, result: dict, llm_comment: str) -> None:
    """Zapisuje predykcję modelu na target_date do model_predictions ze
    statusem 'pending' - czeka na ewaluację, gdy pojawi się rzeczywista
    cena złota dla tej daty."""
    payload = {
        "target_date": target_date,
        "model_id": model_id,
        "predicted_value": result["predicted_value"],
        "shap_values": result["shap_values"],
        "llm_comment": llm_comment,
        "status": "pending",
    }
    try:
        supabase.table("model_predictions").insert(payload).execute()
        print(f"Zapisano predykcję (model_id={model_id}, target_date={target_date}): "
              f"{result['predicted_value']:.2f}")
    except Exception as e:
        print(f"Błąd zapisu predykcji dla model_id={model_id}: {e}")
