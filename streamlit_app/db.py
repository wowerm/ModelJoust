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
