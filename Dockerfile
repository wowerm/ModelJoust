FROM python:3.14-slim

WORKDIR /app

# Zależności kopiowane i instalowane przed resztą kodu - zmiana w
# pipeline'ie nie wymusza ponownej instalacji przy kolejnym budowaniu obrazu.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Tylko moduły potrzebne do codziennego przebiegu main_pipeline.py.
# seed_historical_data.py i simulate_days.py pominięte - to skrypty jednorazowe
# (backfill historii / symulacja), uruchamiane ręcznie poza obrazem.
COPY config.py db_client.py data_download.py prediction_evaluation.py drift_detection.py \
     llm_comment.py model_registry.py main_pipeline.py ./
COPY models/ ./models/

# Sekrety (SUPABASE_URL, SUPABASE_KEY, GROQ_API_KEY) NIE trafiają do obrazu -
# przekazywane dopiero przy "docker run" (lokalnie: --env-file .env,
# na CI: GitHub Secrets wstrzyknięte jako zmienne środowiskowe).
CMD ["python", "main_pipeline.py"]
