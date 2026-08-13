import os

from dotenv import load_dotenv
from groq import Groq

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    raise ValueError(
        "Brak skonfigurowanego GROQ_API_KEY w pliku .env!"
    )

client = Groq(api_key=GROQ_API_KEY)

MODEL_NAME = "llama-3.1-8b-instant"

NAIVE_STATIC_COMMENT = "Model bazowy: prognoza równa ostatniej znanej cenie złota."


def build_llm_comment(model_type: str, shap_values: dict | None, predicted_value: float) -> str:
    """
    Zwraca komentarz w języku naturalnym opisujący dzisiejszą predykcję.
    Dla modelu naiwnego (shap_values=None) - stały tekst, bez wywołania LLM
    (nie ma cech do wytłumaczenia).
    """
    if not shap_values:
        return NAIVE_STATIC_COMMENT

    sorted_contributions = sorted(shap_values.items(), key=lambda kv: abs(kv[1]), reverse=True)
    contributions_text = "\n".join(
        f"- {feature}: {value:+.6f}" for feature, value in sorted_contributions
    )

    prompt = (
        f"Jesteś asystentem opisującym w prosty, zrozumiały sposób predykcję modelu "
        f"typu '{model_type}', przewidującego jutrzejszą cenę złota (w USD). Model "
        f"przewidział cenę {predicted_value:.2f} USD. Poniżej wkład (SHAP) poszczególnych "
        f"cech w tę predykcję (dodatnia wartość = pchała cenę w górę, ujemna = w dół; "
        f"cechy to dzienne stopy zwrotu instrumentów finansowych, 'actual_y' to wczorajsza "
        f"stopa zwrotu samego złota):\n\n"
        f"{contributions_text}\n\n"
        f"Napisz 2-3 zdania po polsku, prostym językiem (bez żargonu technicznego), "
        f"wyjaśniające, co najbardziej wpłynęło na tę predykcję i w którą stronę."
    )

    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=600,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Błąd wywołania Groq API: {e}")
        return "Nie udało się wygenerować opisu predykcji (błąd API)."
