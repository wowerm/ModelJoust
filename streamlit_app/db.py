import os

from dotenv import load_dotenv
from supabase import Client, create_client

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")

if not SUPABASE_URL or not SUPABASE_ANON_KEY:
    raise ValueError(
        "Brak SUPABASE_URL / SUPABASE_ANON_KEY w pliku .env! "
        "To osobny klucz (anon, publiczny) od tego używanego przez pipeline "
        "(service_role) - patrz Project Settings -> API w Supabase."
    )

# Klucz anon, ograniczony przez RLS do samego odczytu - apka nigdy nie pisze
# do bazy tym klientem. Zapis (panel admina) dostaje osobnego klienta na
# service_role, tworzonego dopiero po weryfikacji hasła.
supabase: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)


def last_n_evaluated_cutoff(n: int) -> tuple[str | None, int]:
    # "N dni" w całej apce = N dni z FAKTYCZNIE ewaluowaną predykcją, nie N
    # ostatnich wierszy system_logs - dzień bez notowania giełdowego (status
    # 'unused') albo dzień, w którym pipeline w ogóle się nie uruchomił, nie
    # powinien "zjadać" miejsca w oknie kosztem realnych danych. Limit wiersza
    # to n*5+20 (max 5 modeli/dzień + zapas), żeby jednym zapytaniem złapać
    # z pewnością co najmniej n różnych dat. Zwraca (cutoff, ile dat realnie
    # znaleziono) - drugi element pozwala wywołującemu wykryć sytuację "mamy
    # mniej historii niż żądane N".
    resp = (
        supabase.table("model_predictions")
        .select("target_date")
        .eq("status", "evaluated")
        .order("target_date", desc=True)
        .limit(n * 5 + 20)
        .execute()
    )
    dates = sorted({row["target_date"] for row in (resp.data or [])}, reverse=True)
    if not dates:
        return None, 0
    window = dates[:n]
    return window[-1], len(window)
