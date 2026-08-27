import json

import pandas as pd
import streamlit as st

from admin_db import restore_session, sign_in
from config_meta import CONFIG_META
from db import supabase as anon_supabase
from theme import apply_theme

apply_theme()

st.title("Admin")
st.caption("Edycja progów i hiperparametrów pipeline'u (pipeline_config)")

if "admin_mode" not in st.session_state:
    st.session_state.admin_mode = None  # None | "guest" | "auth"
if "admin_session" not in st.session_state:
    st.session_state.admin_session = None

# --- Logowanie ---
if st.session_state.admin_mode is None:
    email = st.text_input("Email")
    password = st.text_input("Hasło", type="password")
    c1, c2 = st.columns(2)
    if c1.button("Zaloguj", width="stretch"):
        tokens = sign_in(email, password)
        if tokens:
            st.session_state.admin_mode = "auth"
            st.session_state.admin_session = tokens
            st.rerun()
        else:
            st.error("Błędny e-mail lub hasło.")
    if c2.button("Zaloguj jako gość", width="stretch"):
        st.session_state.admin_mode = "guest"
        st.rerun()
    st.stop()

is_guest = st.session_state.admin_mode == "guest"
supabase = anon_supabase if is_guest else restore_session(*st.session_state.admin_session)

if is_guest:
    st.info("Tryb podglądu (gość) — wartości są tylko do odczytu, zapis wymaga zalogowania.")
st.button("Wyloguj", on_click=lambda: st.session_state.update(admin_mode=None, admin_session=None))


def _reset_json_value(widget_key: str, default_json: str) -> None:
    # Musi być on_click (nie zwykłe zerowanie po kliknięciu) - Streamlit nie
    # pozwala nadpisać session_state[key] po tym, jak widget o tym kluczu już
    # się w tym przebiegu wyrenderował.
    st.session_state[widget_key] = default_json


def render_value_input(row: dict, disabled: bool):
    value = row["value"]
    widget_key = f"val_{row['id']}"
    if isinstance(value, bool):
        return st.checkbox(
            "Wartość", value=value, key=widget_key, disabled=disabled, label_visibility="collapsed"
        )
    if isinstance(value, (dict, list)):
        default_json = json.dumps(value, ensure_ascii=False, indent=2)
        raw = st.text_area(
            "Wartość (JSON)",
            value=default_json,
            key=widget_key,
            disabled=disabled,
            height=220,
            label_visibility="collapsed",
        )
        if not disabled:
            st.button(
                "Przywróć aktualną wartość", key=f"reset_{widget_key}",
                on_click=_reset_json_value, args=(widget_key, default_json),
            )
        try:
            return json.loads(raw)
        except json.JSONDecodeError as e:
            st.error(f"Niepoprawny JSON w linii {e.lineno}, kolumna {e.colno} — sprawdź przecinki, cudzysłowy i nawiasy.")
            return None
    if isinstance(value, int):
        return st.number_input(
            "Wartość", value=value, step=1, key=widget_key, disabled=disabled, label_visibility="collapsed"
        )
    if isinstance(value, float):
        return st.number_input(
            "Wartość", value=value, step=0.001, format="%.4f",
            key=widget_key, disabled=disabled, label_visibility="collapsed",
        )
    return st.text_input(
        "Wartość", value=str(value), key=widget_key, disabled=disabled, label_visibility="collapsed"
    )


def save_new_value(row: dict, new_value) -> None:
    # Historia zmian: stary wiersz -> active=false, nowa wartość jako nowy aktywny wiersz (patrz load_config())
    supabase.table("pipeline_config").update({"active": False}).eq("id", row["id"]).execute()
    supabase.table("pipeline_config").insert({
        "key": row["key"],
        "value": new_value,
        "description": row["description"],
        "active": True,
    }).execute()


# --- Aktualna konfiguracja ---
st.subheader("Aktualna konfiguracja")

config_resp = (
    supabase.table("pipeline_config")
    .select("id, key, value, description, updated_at")
    .eq("active", True)
    .order("key")
    .execute()
)
config_rows = config_resp.data or []

if not config_rows:
    st.info("Brak jeszcze żadnej konfiguracji.")

for row in config_rows:
    meta = CONFIG_META.get(row["key"])
    validate_fn = meta["validate"] if meta else None

    with st.container(border=True):
        c1, c2 = st.columns([4, 1])
        with c1:
            st.markdown(f"**{row['key']}**")
            if meta:
                st.caption(f"**{meta['category']}** — {meta['effect']}")
            elif row["description"]:
                st.caption(row["description"])
            new_value = render_value_input(row, disabled=is_guest)

            error_msg = None
            if new_value is not None and validate_fn:
                error_msg = validate_fn(new_value)
            if error_msg:
                st.error(error_msg)
        with c2:
            st.write("")
            if is_guest:
                st.caption("Zaloguj się, aby edytować")
            else:
                unchanged = new_value == row["value"]
                if st.button(
                    "Zapisz", key=f"save_{row['id']}", width="stretch",
                    disabled=(new_value is None or error_msg is not None or unchanged),
                ):
                    save_new_value(row, new_value)
                    st.success(f"Zapisano nową wartość dla {row['key']}.")
                    st.rerun()

st.divider()

# --- Historia zmian ---
st.subheader("Historia zmian")

history_resp = (
    supabase.table("pipeline_config")
    .select("key, value, updated_at")
    .eq("active", False)
    .order("updated_at", desc=True)
    .limit(50)
    .execute()
)
history_rows = history_resp.data or []

if not history_rows:
    st.caption("Brak jeszcze żadnych zmian.")
else:
    history_df = pd.DataFrame(history_rows)
    history_df["value"] = history_df["value"].apply(lambda v: json.dumps(v, ensure_ascii=False))
    history_df["updated_at"] = pd.to_datetime(history_df["updated_at"]).dt.strftime("%Y-%m-%d %H:%M")
    st.dataframe(
        history_df.rename(columns={"key": "Klucz", "value": "Poprzednia wartość", "updated_at": "Zmieniono"}),
        hide_index=True,
        width="stretch",
    )
