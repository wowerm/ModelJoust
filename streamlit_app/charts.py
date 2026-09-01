import altair as alt
import pandas as pd

# Delikatna siatka na ciemnym tle
GRID_STYLE = {"grid": True, "gridColor": "#2A2F3A", "gridOpacity": 0.5}

# Wspólny styl etykiet nad słupkami i osi kategorii - kolor jawnie biały,
# bo domyślny (czarny) ginie na ciemnym tle apki
LABEL_STYLE = {"dy": -10, "fontSize": 15, "fontWeight": "bold", "color": "#FFFFFF"}
CATEGORY_AXIS = alt.Axis(labelAngle=-45, labelFontSize=13)

# Stonowana paleta dla modeli, kolejność wg model_order - celowo omija czystą
# zieleń/czerwień (te są zarezerwowane w apce pod znaczenie "lepszy"/"gorszy",
# np. podświetlenie tabeli w module 4) i złoto (ACCENT_COLOR, znaczenie
# "wyróżniony/zwycięzca"), żeby nie kolidować z tamtymi sygnałami.
MODEL_COLORS = ["#5494D4", "#9E75D7", "#30A69A", "#DD804B", "#D3699E"]
# Kolor serii "Zamknięcie" (rzeczywista cena)
ACTUAL_COLOR = "#D4D4D8"
# Paleta dla powodów retreningu
REASON_COLORS = ["#22C55E", "#F97316", "#EC4899", "#6366F1"]
# Złoty akcent apki (patrz theme.py/logo) - używany też jako uniwersalny
# sygnał "to jest wyróżnione/zwycięskie" (np. obramowanie najlepszego słupka).
ACCENT_COLOR = "#C9A961"


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


# Nazwa kolumny modelu w tabelach metryk - highlight_best_worst ją pomija
# (nie ma sensu podświetlać "najlepszej"/"najgorszej" nazwy modelu).
MODEL_COLUMN = "Model"


def highlight_best_worst(col: pd.Series) -> list[str]:
    # Zielony = najlepszy, czerwony = najgorszy w kolumnie (pd.Styler.apply,
    # axis=0 - wołane raz na kolumnę). Bias liczony inaczej niż reszta -
    # "najlepszy" to najbliżej zera, nie min/max, bo to błąd ze znakiem
    # (dodatni i ujemny są tak samo złe).
    if col.name == MODEL_COLUMN:
        return ["" for _ in col]
    valid = col.dropna()
    if valid.empty:
        return ["" for _ in col]

    if col.name == "Bias ($)":
        best_idx = valid.abs().idxmin()
        worst_idx = valid.abs().idxmax()
    elif col.name == "Trafność kierunku (%)":
        best_idx = valid.idxmax()
        worst_idx = valid.idxmin()
    else:  # MAPE, MAE, RMSE - im mniej, tym lepiej
        best_idx = valid.idxmin()
        worst_idx = valid.idxmax()

    if best_idx == worst_idx:
        return ["" for _ in col]

    styles = []
    for idx in col.index:
        if idx == best_idx:
            styles.append("background-color: rgba(34, 197, 94, 0.18); color: #22C55E; font-weight: 600;")
        elif idx == worst_idx:
            styles.append("background-color: rgba(239, 68, 68, 0.18); color: #EF4444; font-weight: 600;")
        else:
            styles.append("")
    return styles
