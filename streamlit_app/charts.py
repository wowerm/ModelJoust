import altair as alt
import pandas as pd

# Delikatna siatka na ciemnym tle
GRID_STYLE = {"grid": True, "gridColor": "#2A2F3A", "gridOpacity": 0.5}

# Wspólny styl etykiet nad słupkami i osi kategorii
LABEL_STYLE = {"dy": -10, "fontSize": 15, "fontWeight": "bold"}
CATEGORY_AXIS = alt.Axis(labelAngle=-45, labelFontSize=13)

# Paleta dla modeli, kolejność wg model_order
MODEL_COLORS = ["#3B82F6", "#EF4444", "#22C55E", "#A855F7", "#EAB308"]
# Kolor serii "Zamknięcie" (rzeczywista cena)
ACTUAL_COLOR = "#D4D4D8"
# Paleta dla powodów retreningu
REASON_COLORS = ["#22C55E", "#F97316", "#EC4899", "#6366F1"]


def model_color_scale(domain: list[str], extra: dict[str, str] | None = None) -> alt.Scale:
    # Skala kolorów dla modeli; `extra` dopisuje dodatkowe kategorie (np. Zamknięcie) z własnym kolorem
    full_domain = list(domain)
    colors = list(MODEL_COLORS[: len(domain)])
    for label, color in (extra or {}).items():
        full_domain.append(label)
        colors.append(color)
    return alt.Scale(domain=full_domain, range=colors)


def bar_y_domain(series: pd.Series) -> list[float]:
    # Oś Y od zera z zapasem nad najwyższym słupkiem, żeby etykieta się nie ucinała
    return [0, float(series.max()) * 1.18]


def adaptive_time_axis(min_date: pd.Timestamp, title: str | None = None) -> alt.Axis:
    # Gęstość i format znaczników osi X dopasowane do rozpiętości dat (od min_date do dziś)
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
    # Oś Y dla słupków +/- (np. Bias); zawsze obejmuje zero, inaczej słupki by się nie wyrenderowały
    lo, hi = min(float(series.min()), 0.0), max(float(series.max()), 0.0)
    pad = (hi - lo) * pad_frac or 1.0
    return [lo - pad, hi + pad]


def padded_domain(series: pd.Series, pad_frac: float = 0.08) -> list[float]:
    # Oś Y z buforem wokół min/max zamiast od zera - dla cen/MAPE
    lo, hi = float(series.min()), float(series.max())
    pad = (hi - lo) * pad_frac
    if pad == 0:
        pad = abs(hi) * 0.05 or 1.0
    return [lo - pad, hi + pad]
