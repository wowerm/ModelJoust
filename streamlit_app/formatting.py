def polish_plural(n: int, singular: str, few: str, many: str) -> str:
    """Poprawna polska odmiana liczebnikowa: 1 wersja, 2-4 wersje, 5+/0 wersji
    (z wyjątkiem 12-14, które zawsze biorą formę 'wersji', nie 'wersje')."""
    if n == 1:
        form = singular
    elif n % 10 in (2, 3, 4) and n % 100 not in (12, 13, 14):
        form = few
    else:
        form = many
    return f"{n} {form}"


def signed_dollar(value: float) -> str:
    """Standardowy finansowy zapis: znak przed symbolem waluty (+$98.31,
    -$45.20), nie po nim ($+98.31) - tak zwyczajowo pokazuje się zyski/straty."""
    sign = "+" if value >= 0 else "-"
    return f"{sign}${abs(value):.2f}"


def error_with_pct(error_value: float, actual_value: float) -> str:
    """Błąd w dolarach + w nawiasie odpowiadający mu błąd procentowy
    względem rzeczywistej wartości."""
    pct = (error_value / actual_value) * 100 if actual_value else 0.0
    sign = "+" if pct >= 0 else "-"
    return f"{signed_dollar(error_value)} ({sign}{abs(pct):.2f}%)"
