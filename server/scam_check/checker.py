"""CareCircle scam check: combines the ML model with red-flag rules into one verdict."""

from pathlib import Path

import joblib

from redflags import MIN_CAREFUL, find_flags, safe_signs

MODEL_PATH = Path(__file__).resolve().parent.parent / "models" / "scam_model.joblib"

STRENGTH_POINTS = {"strong": 0.25, "medium": 0.10, "weak": 0.04}
SAFE_POINTS = 0.20

VERDICTS = {
    "scam": {
        "icon": "🛑",
        "title": {"en": "Likely a scam", "es": "Probablemente es una estafa"},
        "advice": {
            "en": "Don't reply, tap any links, or call numbers in this message. Delete it. "
                  "If you're worried, call the company or person using a number you already trust.",
            "es": "No responda, no toque enlaces ni llame a los numeros del mensaje. Borrelo. "
                  "Si le preocupa, llame a la empresa o persona a un numero de confianza.",
        },
    },
    "careful": {
        "icon": "⚠️",
        "title": {"en": "Be careful", "es": "Tenga cuidado"},
        "advice": {
            "en": "Something about this message seems off. Don't share personal information or money. "
                  "Check with a family member or call the company directly before doing anything.",
            "es": "Algo de este mensaje no parece normal. No comparta datos personales ni dinero. "
                  "Consulte con un familiar o llame directamente a la empresa antes de actuar.",
        },
    },
    "safe": {
        "icon": "✅",
        "title": {"en": "Looks safe", "es": "Parece seguro"},
        "advice": {
            "en": "We didn't find warning signs. Still, never share passwords or codes with anyone.",
            "es": "No encontramos senales de alerta. Aun asi, nunca comparta contrasenas ni codigos.",
        },
    },
}


class ScamChecker:
    def __init__(self, model_path=MODEL_PATH):
        self.model = joblib.load(model_path)

    def model_probability(self, text):
        return float(self.model.predict_proba([text])[0][1])

    def check(self, text, lang="en"):
        lang = lang if lang in ("en", "es") else "en"
        prob = self.model_probability(text)
        flags = find_flags(text, lang)
        safe = safe_signs(text)

        strong = sum(f["strength"] == "strong" for f in flags)
        risk = prob + sum(STRENGTH_POINTS[f["strength"]] for f in flags) - SAFE_POINTS * len(safe)
        risk = max(0.0, min(1.0, risk))

        if risk >= 0.65 or strong >= 2:
            verdict = "scam"
        elif risk >= 0.35 or strong >= 1 or any(f["id"] in MIN_CAREFUL for f in flags):
            verdict = "careful"
        else:
            verdict = "safe"

        # Strongest reasons first, at most 3 so it's easy to read.
        order = {"strong": 0, "medium": 1, "weak": 2}
        reasons = [f["why"] for f in sorted(flags, key=lambda f: order[f["strength"]])][:3]

        # A plain-words confidence label, so the app never sounds more certain than it is.
        if verdict == "scam":
            confidence = "Very sure" if (risk >= 0.9 or strong >= 2) else "Fairly sure"
        elif verdict == "careful":
            confidence = "Not sure"
        else:
            confidence = "Fairly sure" if risk < 0.2 else "Somewhat sure"

        v = VERDICTS[verdict]
        return {
            "verdict": verdict,
            "icon": v["icon"],
            "title": v["title"][lang],
            "confidence": confidence,
            "warning_signs": len(flags),
            "reasons": reasons,
            "advice": v["advice"][lang],
            "risk_score": round(risk, 3),
            "model_probability": round(prob, 3),
            "flags": [{k: f[k] for k in ("id", "strength", "evidence")} for f in flags],
            "safe_signs": safe,
        }
