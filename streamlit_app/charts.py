import altair as alt
import pandas as pd


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
        return alt.Axis(
            format="%d-%m-%y", tickCount={"interval": "day", "step": 1}, labelAngle=0, title=title
        )
    elif span_days <= 60:
        return alt.Axis(
            format="%d-%m-%y", tickCount={"interval": "day", "step": 1}, labelAngle=-45, title=title
        )
    elif span_days < 365:
        return alt.Axis(
            format="%m-%y", tickCount={"interval": "month", "step": 1}, labelAngle=0, title=title
        )
    else:
        return alt.Axis(
            format="%m-%y", tickCount={"interval": "month", "step": 1}, labelAngle=-45, title=title
        )


def padded_domain(series: pd.Series, pad_frac: float = 0.08) -> list[float]:
    """Zakres osi Y z buforem wokół min/max, zamiast zaczynania od zera -
    dla cen/MAPE oś od zera marnowałaby większość wykresu."""
    lo, hi = float(series.min()), float(series.max())
    pad = (hi - lo) * pad_frac
    if pad == 0:
        pad = abs(hi) * 0.05 or 1.0
    return [lo - pad, hi + pad]
