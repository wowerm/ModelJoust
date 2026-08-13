import pandas as pd


class NaiveModel:
    """
    Model bazowy, pierwszy kompletny szkielet end-to-end pipeline'u.
    Predykcja na jutro = ostatnia znana cena złota. Brak parametrów i
    treningu - shap_values zawsze None (nie ma cech objaśniających, bo
    nie ma czego tłumaczyć).
    """

    def __init__(self, storage_path: str | None = None, baseline_stats: dict | None = None,
                 config: dict | None = None):
        """storage_path, baseline_stats i config przyjmowane wyłącznie dla
        spójności interfejsu z pozostałymi blackboxami (jednolite wywołanie
        z main_pipeline.py) - model naiwny nie ma obiektu do zapisania/
        wczytania, cech objaśniających ani progów/hiperparametrów, więc
        żaden z nich tu nie jest używany."""
        self.storage_path = storage_path
        self.data: dict | None = None

    def load_data(self, today_data: dict) -> None:
        """today_data = {"returns": {...}, "last_actual_y_level": float} -
        model naiwny korzysta wyłącznie z ostatniej znanej ceny, nie ze
        stóp zwrotu."""
        self.data = today_data

    def retrain_if_needed(self, retrain_required: bool, as_of_date: pd.Timestamp) -> None:
        """as_of_date przyjmowane wyłącznie dla spójności interfejsu z
        pozostałymi blackboxami - model naiwny niczego nie trenuje."""
        if retrain_required:
            print("NaiveModel: retrening zażądany, ale model bazowy nie ma "
                  "parametrów do wytrenowania - brak akcji.")

    def predict(self) -> dict:
        """Predykcja na jutro = ostatnia znana cena złota."""
        if self.data is None:
            raise ValueError("Brak danych - wywołaj load_data() przed predict().")

        last_known_price = self.data.get("last_actual_y_level")
        if last_known_price is None or pd.isna(last_known_price):
            raise ValueError("Brak jakiejkolwiek znanej wartości actual_y w oknie danych.")

        return {
            "predicted_value": float(last_known_price),
            "shap_values": None,
            "selected_features": [],
            "baseline_stats": None,
            "storage_path": None,
            # Model naiwny ma tylko jedną, sensowną wersję (logika się nigdy
            # nie zmienia) - zawsze v1, żeby models_logs miało co zapisać
            # przy pierwszym uruchomieniu (retrain_trigger='init').
            "model_version": 1,
            "train_start_date": None,
            "train_end_date": None,
        }
