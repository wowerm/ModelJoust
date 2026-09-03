import sys
from pathlib import Path

import pandas as pd
import yfinance as yf


sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from data_download import tickers, normalize_market_data
from db_client import supabase


def seed_historical_data():
    """
    Jednorazowe zapełnienie raw_data historią 5 lat wstecz dla wszystkich
    śledzonych instrumentów - używane przy pierwszym uruchomieniu systemu
    albo dodaniu nowego instrumentu do tickers. Zapisuje surowe dane z API
    (bez ffill), jeden wiersz per dzień roboczy.
    """
    print("Pobieranie historycznych danych rynkowych...")
    df_raw = yf.download(
        list(tickers.values()), period="5y", interval="1d", progress=False
    )["Close"]
    df_raw = normalize_market_data(df_raw)

    print(f"Przygotowano {len(df_raw)} dni roboczych do zapisu (bez ffill - surowe dane z API).")

    payloads = []
    for date_index, row in df_raw.iterrows():
        date_str = pd.to_datetime(date_index).strftime("%Y-%m-%d")

        # BEZ ffill - zapisujemy dokładnie to, co zwróciło API. Braki
        # zostają jako null (czysty status rynku danego dnia).
        row_dict = {k: (None if pd.isna(v) else float(v)) for k, v in row.to_dict().items()}

        actual_gold_value = row_dict.pop("Y_Gold", None)

        payloads.append({
            "target_date": date_str,
            "features": row_dict,
            "actual_y": actual_gold_value,
        })

    print(f"Wysyłanie {len(payloads)} rekordów do Supabase...")

    try:
        supabase.table("raw_data").upsert(payloads, on_conflict="target_date").execute()
        print(f"Sukces: Zapisano {len(payloads)} rekordów.")
    except Exception as e:
        print(f"Błąd podczas zapisu do bazy: {e}")


if __name__ == "__main__":
    seed_historical_data()