import altair as alt
import pandas as pd

# Delikatna siatka - subtelna na ciemnym tle, nie odciąga uwagi od danych.
GRID_STYLE = {"grid": True, "gridColor": "#2A2F3A", "gridOpacity": 0.5}

# Wspólny styl etykiet z wartościami nad słupkami i osi kategorii - używane
# na wszystkich wykresach słupkowych w apce.
LABEL_STYLE = {"dy": -10, "fontSize": 15, "fontWeight": "bold"}
CATEGORY_AXIS = alt.Axis(labelAngle=-45, labelFontSize=13)

# Jedna, żywa paleta dla modeli - używana wszędzie, gdzie kolor koduje
# model. Kolejność odpowiada model_order (kolejność pierwszego treningu).
MODEL_COLORS = ["#3B82F6", "#EF4444", "#22C55E", "#A855F7", "#EAB308"]
# Neutralny, jasny kolor dla serii "Zamknięcie" (rzeczywista cena) - ma się
# wyróżniać na tle kolorów modeli, nie ginąć wśród nich.
ACTUAL_COLOR = "#D4D4D8"
# Osobna paleta dla powodów retreningu (inna kategoria niż modele, więc nie
# musi współdzielić MODEL_COLORS).
REASON_COLORS = ["#22C55E", "#F97316", "#EC4899", "#6366F1"]


def model_color_scale(domain: list[str], extra: dict[str, str] | None = None) -> alt.Scale:
    """Spójna skala kolorów dla modeli. `extra` dopisuje dodatkowe
    kategorie spoza modeli (np. {'Zamknięcie': ACTUAL_COLOR}) z własnym
    kolorem."""
    full_domain = list(domain)
    colors = list(MODEL_COLORS[: len(domain)])
    for label, color in (extra or {}).items():
        full_domain.append(label)
        colors.append(color)
    return alt.Scale(domain=full_domain, range=colors)


def bar_y_domain(series: pd.Series) -> list[float]:
    """Zakres osi Y od zera z zapasem nad najwyższym słupkiem, żeby
    etykieta z wartością nad słupkiem się nie ucinała."""
    return [0, float(series.max()) * 1.18]


def adaptive_time_axis(min_date: pd.Timestamp, title: str | None = None) -> alt.Axis:
    """Oś X, która dostosowuje gęstość i format znaczników do rozpiętości
    danych (od min_date do dziś) - współdzielone przez wszystkie wykresy
    czasowe w apce:
      - do 20 dni: znacznik co dzień, poziomo
      - 20-60 dni: znacznik co dzień, pod kątem (za gęsto na poziomo)
      - 60-365 dni: znacznik co miesiąc, poziomo
      - od 365 dni: znacznik co miesiąc, pod kątem (za dużo miesięcy na poziomo)
    """
    span_days = (pd.Timestamp.now() - min_date).days
    if span_days <= 20:
        tick, angle = {"interval": "day", "step": 1}, 0
        fmt = "%d-%m-%y"
    elif span_days <= 60:
        tick, angle = {"interval": "day", "step": 1}, -45
        fmt = "%d-%m-%y"
    elif span_days < 365:
        tick, angle = {"interval": "month", "step": 1}, 0
        fmt = "%m-%y"
    else:
        tick, angle = {"interval": "month", "step": 1}, -45
        fmt = "%m-%y"
    return alt.Axis(format=fmt, tickCount=tick, labelAngle=angle, title=title, **GRID_STYLE)


def signed_bar_domain(series: pd.Series, pad_frac: float = 0.15) -> list[float]:
    """Zakres osi Y dla słupków, które mogą być dodatnie i ujemne (np. Bias).
    W przeciwieństwie do bar_y_domain/padded_domain ZAWSZE zawiera zero -
    Vega-Lite rysuje słupki od zera, więc jeśli domena go nie obejmuje
    (np. same wartości ujemne), słupki w ogóle się nie renderują."""
    lo, hi = min(float(series.min()), 0.0), max(float(series.max()), 0.0)
    pad = (hi - lo) * pad_frac or 1.0
    return [lo - pad, hi + pad]


def padded_domain(series: pd.Series, pad_frac: float = 0.08) -> list[float]:
    """Zakres osi Y z buforem wokół min/max, zamiast zaczynania od zera -
    dla cen/MAPE oś od zera marnowałaby większość wykresu."""
    lo, hi = float(series.min()), float(series.max())
    pad = (hi - lo) * pad_frac
    if pad == 0:
        pad = abs(hi) * 0.05 or 1.0
    return [lo - pad, hi + pad]
