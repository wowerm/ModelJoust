import pandas as pd
import yfinance as yf

from db_client import supabase

tickers = {
    # cel - zmiana przewidywanej zmiennej (np. na Bitcoin zamiast złota, bo
    # złoto jest zbyt stabilne/mało zmienne - do przemyślenia z promotorką)
    # sprowadza się GŁÓWNIE do zmiany tego jednego wpisu "Y_..." - seed_historical_data.py
    # importuje ten słownik stąd, nie ma go gdzie indziej duplikować. Cała
    # reszta pipeline'u (raw_data, build_today_return_row, blackboxy) operuje
    # na kluczu "actual_y", nie na nazwie instrumentu wprost, więc nie wymaga zmian.
    "Y_Gold": "GC=F",

    # metale/surowce
    "X_Silver": "SI=F",
    "X_Platinum": "PL=F",
    "X_Palladium": "PA=F",
    "X_Copper": "HG=F",
    "X_CrudeOil_WTI": "CL=F",
    "X_Brent": "BZ=F",
    "X_NaturalGas": "NG=F",

    # soft commodities
    "X_Wheat": "ZW=F",
    "X_Coffee": "KC=F",
    "X_Cocoa": "CC=F",
    "X_Sugar": "SB=F",

    # obligacje / stopy realne
    "X_30Y_Treasury": "ZB=F",
    "X_10Y_Treasury": "ZN=F",
    "X_5Y_Treasury": "ZF=F",
    "X_TIPS": "TIP",
    "X_ShortTermTreasury": "SHY",
    "X_LongTermTreasury": "TLT",

    # indeksy
    "X_SP500": "^GSPC",
    "X_Nasdaq": "^IXIC",
    "X_DowJones": "^DJI",
    "X_Russell2000": "^RUT",
    "X_EuroStoxx": "^STOXX50E",
    "X_DAX": "^GDAXI",
    "X_FTSE100": "^FTSE",
    "X_Nikkei": "^N225",
    "X_EmergingMarkets": "EEM",
    "X_Semiconductors": "SMH",

    # waluty
    "X_USD_Index": "DX-Y.NYB",
    "X_EURUSD": "EURUSD=X",
    "X_AUDUSD": "AUDUSD=X",
    "X_GBPUSD": "GBPUSD=X",
    "X_USDJPY": "USDJPY=X",
    "X_USDCHF": "USDCHF=X",
    "X_USDINR": "USDINR=X",

    # zmienność i sentyment ryzyka
    "X_VIX": "^VIX",
    "X_GoldVIX": "^GVZ",
    "X_HighYieldBonds": "HYG",
    "X_InvestGradeBonds": "LQD",

    # akcje spółek wydobywczych
    "X_GoldMiners": "GDX",
    "X_JuniorGoldMiners": "GDXJ",

    # krypto
    "X_Bitcoin": "BTC-USD",
    "X_Ethereum": "ETH-USD",
}


def normalize_market_data(df_raw: pd.DataFrame) -> pd.DataFrame:
    """Spłaszcza MultiIndex kolumn (jeśli pobierano wiele tickerów naraz),
    tłumaczy symbole yfinance na własne klucze (Y_..., X_...), i odrzuca
    ewentualne artefakty sobotnio/niedzielne w samych danych (np. błędnie
    zaetykietowana pierwsza świeca poniedziałkowej sesji FX). Współdzielone
    przez save_latest_market_data() i seed_historical_data.py."""
    if isinstance(df_raw.columns, pd.MultiIndex):
        df_raw.columns = df_raw.columns.get_level_values(0)

    inv_tickers = {v: k for k, v in tickers.items()}
    df_raw = df_raw.rename(columns=inv_tickers)

    return df_raw[df_raw.index.dayofweek < 5]


def save_latest_market_data(as_of_date: pd.Timestamp):
    """
    Pobiera z yfinance ceny zamknięcia wszystkich śledzonych instrumentów za
    as_of_date (wg czasu US/Eastern) i zapisuje jeden wiersz do raw_data
    (features + actual_y). Pomija weekendy oraz dni, dla których dane nie są
    jeszcze opublikowane - w obu przypadkach nie zapisuje żadnego wiersza.
    """
    date_str = as_of_date.strftime('%Y-%m-%d')

    # Dodatkowe zabezpieczenie: jeśli dzisiaj wg czasu rynku złota to sobota
    # lub niedziela, nie ma sensu nawet odpytywać API - to nie jest dzień,
    # dla którego powinniśmy tworzyć rekord.
    if as_of_date.dayofweek >= 5:
        print(f"{date_str} to weekend (wg czasu US/Eastern) - pomijam zapis.")
        return

    # period liczone jest przez yfinance wstecz od DZISIAJ, nie od as_of_date -
    # przy codziennym, "żywym" uruchomieniu (as_of_date == dziś) 2 dni w zupełności
    # wystarczą. Przy uzupełnianiu zaległej/historycznej daty trzeba sięgnąć
    # wystarczająco daleko wstecz, żeby as_of_date w ogóle znalazło się w oknie -
    # to warunek konieczny, żeby historyczne uzupełnianie bazy działało poprawnie.
    real_today = pd.Timestamp.now(tz="America/New_York").normalize().tz_localize(None)
    days_diff = (real_today - as_of_date).days
    period = "2d" if days_diff <= 0 else f"{days_diff + 1}d"

    print(f"Pobieranie danych rynkowych (as_of wg US/Eastern: {date_str}, period={period})...")
    df_raw = yf.download(list(tickers.values()), period=period, interval="1d", progress=False)['Close']
    df_raw = normalize_market_data(df_raw)

    # Nie szukamy "ostatniego dostępnego dnia" - interesuje nas WYŁĄCZNIE
    # dzisiejsza data (wg czasu rynku złota). Jeśli jej nie ma w indeksie,
    # nie zapisujemy niczego - to nie jest "dzisiejszy" rekord.
    if as_of_date not in df_raw.index:
        print(f"Brak jakichkolwiek danych dla {date_str} (dane jeszcze nieopublikowane).")
        return

    # BEZ ffill - zapisujemy dokładnie to, co zwróciło API dla TEJ konkretnej
    # daty. Braki zostają jako null (czysty status rynku danego dnia).
    row_dict = df_raw.loc[as_of_date].to_dict()
    row_dict = {k: (None if pd.isna(v) else float(v)) for k, v in row_dict.items()}

    actual_gold_value = row_dict.pop("Y_Gold", None)

    payload = {
        "target_date": date_str,
        "features": row_dict,
        "actual_y": actual_gold_value,
    }

    print(f"Zapis do Supabase dla daty: {date_str} (actual_y={actual_gold_value})")

    try:
        supabase.table("raw_data").upsert(payload, on_conflict="target_date").execute()
        print("Sukces: Zapisano dane w bazie.")
    except Exception as e:
        print(f"Błąd podczas zapisu do bazy: {e}")


if __name__ == "__main__":
    _as_of_date = pd.Timestamp.now(tz="America/New_York").normalize().tz_localize(None)
    save_latest_market_data(_as_of_date)