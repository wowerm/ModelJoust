# ModelJoust

MLOps-owy system prognozujący cenę złota na kolejny dzień sesyjny — pięć konkurujących ze sobą modeli, automatyczne wykrywanie dryftu i retrening, oraz mechanizm champion/challenger, który na bieżąco wybiera, który model jest w danym momencie "aktywny". Całość działa raz dziennie, w pełni automatycznie, z podglądem wyników w aplikacji webowej.

**Żywa aplikacja:** [modeljoust.streamlit.app](https://modeljoust.streamlit.app/)

> Aplikacja stoi na darmowym planie Streamlit Community Cloud — po dłuższej nieaktywności "usypia" i przy pierwszym wejściu może pokazać ekran z prośbą o obudzenie (jedno kliknięcie, kilkanaście sekund).

## Czym to jest

Codziennie, po zamknięciu sesji, system:

1. pobiera najświeższe dane rynkowe (złoto + kilkadziesiąt powiązanych instrumentów: indeksy, surowce, waluty, obligacje, kryptowaluty),
2. ocenia wczorajsze predykcje względem rzeczywistej ceny,
3. sprawdza dla każdego modelu, czy nie doszło do Data Driftu (zmiana rozkładu cech) albo Concept Driftu (zmiana relacji cecha→cena) i w razie potrzeby retrenuje go od nowa (oraz kilka pomniejszych zabezpieczeń, np. wykrywanie instrumentów, które przestały być raportowane),
4. generuje dzisiejszą predykcję dla każdego z 5 modeli, wraz z wyjaśnieniem (SHAP) i krótkim opisem w języku naturalnym (LLM),
5. sprawdza, czy któryś model nie powinien zastąpić aktualnie aktywnego (champion/challenger).

Wynik tego procesu — predykcje, historia wersji modeli, metryki jakości — trafia do Supabase i jest widoczny na żywo w aplikacji Streamlit.

## Modele

| Model | Charakterystyka |
|---|---|
| **Naive** | model bazowy — jutrzejsza cena = dzisiejsza (punkt odniesienia dla reszty) |
| **OLS** | regresja liniowa na dziennych stopach zwrotu, dobór cech eliminacją wsteczną + filtr VIF |
| **Lasso** | regresja z regularyzacją L1, siła regularyzacji dobierana przez chronologiczny CV |
| **Random Forest** | las losowy, cechy ograniczone do skumulowanej ważności |
| **XGBoost** | gradient boosting, analogiczny dobór cech co Random Forest |

Każdy model (poza naive) trenuje się niezależnie, ma własną historię wersji i własny zestaw wybranych cech — mogą się od siebie znacząco różnić.

## Champion / Challenger

W danym momencie tylko **jeden** model jest "aktywny" — to jego predykcja liczy się jako oficjalny wynik systemu. Pozostałe cztery działają równolegle w tle. Model-pretendent przejmuje rolę aktywnego dopiero, gdy pokonuje obecnego lidera pod względem kroczącego MAPE przez określoną liczbę dni z rzędu (nie jednorazowo) — dzięki temu system nie przełącza się przypadkowo przy pojedynczym dobrym dniu słabszego modelu.

Progi tego mechanizmu (jak duża musi być przewaga, ile dni z rzędu, jak szeroko liczony jest dryft, z ilu lat historii korzysta trening) nie zostały dobrane na wyczucie — przed uruchomieniem aktualnej wersji systemu przeprowadzona została analiza wrażliwości: dziesiątki kombinacji parametrów przetestowano na identycznym, historycznym oknie czasowym, porównując MAPE, MAE, RMSE i trafność kierunku systemu względem każdego pojedynczego modelu z osobna. Aktualna konfiguracja w `config.py` to wynik tej analizy — kombinacja, przy której dynamiczne przełączanie faktycznie biło wszystkie pojedyncze modele, nie tylko średnio.

## Architektura

```
GitHub Actions (codziennie, po sesji)
        │
        ▼
   Docker (main_pipeline.py)
        │
        ├─ dane rynkowe ──── yfinance
        ├─ opis predykcji ── Groq (LLM)
        │
        ▼
     Supabase
   (Postgres + Storage + Auth)
        │
        ▼
  Aplikacja Streamlit
   (podgląd na żywo)
```

Supabase jest jedynym źródłem prawdy — pipeline i aplikacja nigdy nie komunikują się ze sobą bezpośrednio, tylko przez bazę. Modele (wytrenowane obiekty) trzymane są w Supabase Storage, dane i metryki w Postgresie.

## Struktura repozytorium

```
main_pipeline.py          # punkt wejścia - codzienny przebieg
config.py                 # progi i hiperparametry (pipeline_config w bazie)
data_download.py          # pobieranie danych rynkowych
drift_detection.py        # Data Drift / Concept Drift
prediction_evaluation.py  # ewaluacja predykcji, wybór aktywnego modelu
model_registry.py         # zapis/odczyt wersji modeli (Storage + models_logs)
llm_comment.py            # opis predykcji w języku naturalnym
models/                   # pięć blackboxów (naive/OLS/lasso/RF/XGBoost)

database/
  database_setup.sql      # pełny schemat bazy (tabele, RLS, polityki)

first_setup/
  seed_historical_data.py # jednorazowy backfill kilku lat historii rynkowej
  simulate_days.py        # odtworzenie pipeline'u dzień po dniu na historii
                           # (do zbudowania baseline'u albo testów end-to-end)

streamlit_app/             # aplikacja webowa (6 modułów, patrz niżej)

.github/workflows/
  daily_pipeline.yml       # harmonogram: build obrazu + codzienne uruchomienie
```

`first_setup/` to narzędzia jednorazowe/pomocnicze, nie część codziennego działania systemu — służą do zbudowania historii od zera (np. po resecie bazy) albo do przetestowania całego pipeline'u na wielu dniach naraz, zanim system zacznie działać na żywo.

## Aplikacja (modeljoust.streamlit.app)

| Moduł | Zawartość |
|---|---|
| **Dziś** | bieżąca predykcja aktywnego modelu, kierunek zmiany, opis w języku naturalnym, karty pozostałych modeli |
| **Porównanie modeli** | MAPE/MAE/RMSE/trafność kierunku wszystkich 5 modeli obok siebie |
| **Retreningi** | historia wersji każdego modelu - kiedy, dlaczego, jakie cechy |
| **Historia i jakość** | szczegółowa analiza błędów w wybranym oknie czasowym, wykresy |
| **Dynamika (Champion/Challenger)** | czy dynamiczne przełączanie faktycznie się opłaca względem trzymania jednego modelu |
| **Admin** | edycja progów/parametrów pipeline'u, historia zmian konfiguracji |

Odczyt danych jest publiczny; zapis (zmiana parametrów) wymaga zalogowania.

## Technologie

Python · pandas · scikit-learn · statsmodels · XGBoost · SHAP · Supabase (Postgres, Storage, Auth) · Streamlit · Docker · GitHub Actions · Groq (LLM)
