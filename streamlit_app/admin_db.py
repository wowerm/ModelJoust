import os

from dotenv import load_dotenv
from supabase import Client, create_client

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")


def sign_in(email: str, password: str) -> tuple[str, str] | None:
    # Logowanie przez Supabase Auth (auth.users) - konto zakłada się ręcznie w
    # Dashboardzie, hasło nigdy nie trafia do kodu/.env. Zwraca tokeny sesji do
    # zapamiętania w st.session_state (Streamlit tworzy nowy klient co rerun).
    client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
    try:
        auth_resp = client.auth.sign_in_with_password({"email": email, "password": password})
    except Exception:
        return None
    if not auth_resp.session:
        return None
    return auth_resp.session.access_token, auth_resp.session.refresh_token


def restore_session(access_token: str, refresh_token: str) -> Client:
    # Odtwarza zalogowaną sesję na świeżym kliencie - dalsze zapytania idą jako
    # authenticated (nie anon), więc RLS wpuszcza zapis do pipeline_config.
    client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
    client.auth.set_session(access_token, refresh_token)
    return client
