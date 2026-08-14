CREATE TABLE raw_data (
    target_date DATE PRIMARY KEY,
    features    JSONB NOT NULL,
    actual_y    DOUBLE PRECISION,
    created_at  TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE models_logs (
    id                   BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    model_type           VARCHAR(50) NOT NULL,
    model_version        INTEGER,
    is_active            BOOLEAN NOT NULL DEFAULT false,
    retrain_trigger      VARCHAR(255),
    train_start_date     DATE,
    train_end_date       DATE,
    selected_features    JSONB,
    baseline_stats       JSONB,
    storage_path         TEXT,
    concept_drift_stats  JSONB,
    created_at           TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE model_predictions (
    prediction_id   BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    target_date     DATE NOT NULL,
    model_id        BIGINT NOT NULL REFERENCES models_logs(id),
    predicted_value DOUBLE PRECISION NOT NULL,
    actual_value    DOUBLE PRECISION,
    error_value     DOUBLE PRECISION,
    shap_values     JSONB,
    llm_comment     TEXT,
    status          VARCHAR(20) NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending', 'evaluated', 'unused')),
    created_at      TIMESTAMPTZ DEFAULT now(),
    CONSTRAINT unique_model_prediction_per_day UNIQUE (target_date, model_id)
);

CREATE TABLE system_logs (
    log_date       DATE PRIMARY KEY,
    active_model   VARCHAR(50) NOT NULL,
    mape           JSONB,
    beats_active   JSONB,
    created_at     TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE pipeline_config (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    key         TEXT NOT NULL,
    value       JSONB NOT NULL,
    description TEXT,
    active      BOOLEAN NOT NULL DEFAULT true,
    updated_at  TIMESTAMPTZ DEFAULT now()
);

CREATE UNIQUE INDEX pipeline_config_active_key_idx
    ON pipeline_config (key) WHERE active = true;

CREATE INDEX idx_predictions_target_date ON model_predictions(target_date DESC);
CREATE INDEX idx_predictions_model_id ON model_predictions(model_id);
CREATE INDEX idx_raw_data_features ON raw_data USING GIN (features);
CREATE INDEX idx_predictions_shap ON model_predictions USING GIN (shap_values);

GRANT SELECT, INSERT, UPDATE ON raw_data          TO service_role;
GRANT SELECT, INSERT, UPDATE ON models_logs       TO service_role;
GRANT SELECT, INSERT, UPDATE ON model_predictions TO service_role;
GRANT SELECT, INSERT, UPDATE ON system_logs       TO service_role;
GRANT SELECT, INSERT, UPDATE ON pipeline_config   TO service_role;

INSERT INTO storage.buckets (id, name, public)
VALUES ('models', 'models', false);