-- Jednorazowa, ręczna konfiguracja tabeli na potrzeby analizy wrażliwości
-- parametrów (sensitivity_analysis/run_sweep.py). Osobno od database/database_setup.sql
-- - ta tabela jest tymczasowa, do usunięcia (DROP TABLE) po zakończonej analizie.
--
-- Jeden wiersz = jedna przetestowana kombinacja parametrów, z pełnym
-- podsumowaniem 200-dniowej symulacji dla tej kombinacji.

CREATE TABLE sensitivity_sweep_results (
    id                     BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    params                 JSONB NOT NULL,   -- testowane wartości parametrów, np. {"training_window_years": 3, ...}
    metrics                JSONB NOT NULL,   -- {"naive": {...}, "OLS": {...}, ..., "system": {...}}, każdy z mape/mae/rmse/direction_accuracy
    retrainings            JSONB NOT NULL,   -- {"OLS": {"count": 3, "reasons": {"data_drift": 2, "init": 1}}, ...}
    active_model_sequence  JSONB NOT NULL,   -- ["n","n","x","x","o",...] - jeden kod na dzień symulacji, w kolejności chronologicznej
    sim_days               INTEGER NOT NULL,
    created_at             TIMESTAMPTZ DEFAULT now()
);

GRANT SELECT, INSERT ON sensitivity_sweep_results TO service_role;
ALTER TABLE sensitivity_sweep_results ENABLE ROW LEVEL SECURITY;
-- Brak polityk dla anon/authenticated - ta tabela nie jest czytana przez
-- apkę Streamlit, tylko przez run_sweep.py (service_role) i ręczną analizę.

-- database_setup.sql nigdy nie nadawał service_role prawa DELETE na tych
-- tabelach (main_pipeline.py tylko wstawia/aktualizuje, nigdy nie kasuje) -
-- run_sweep.py potrzebuje tego, żeby czyścić wyniki między kombinacjami.
GRANT DELETE ON model_predictions TO service_role;
GRANT DELETE ON models_logs TO service_role;
GRANT DELETE ON system_logs TO service_role;
