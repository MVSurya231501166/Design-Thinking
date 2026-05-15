from pathlib import Path

from model import NextTemperatureModel


DEFAULT_MODEL_PATH = Path(__file__).resolve().parent / "artifacts" / "cooling_model.json"


_MODEL = None


def load_model(model_path=DEFAULT_MODEL_PATH):
    global _MODEL
    _MODEL = NextTemperatureModel.load(model_path)
    return _MODEL


def predict_action(state, model_path=DEFAULT_MODEL_PATH):
    model = _MODEL or load_model(model_path)
    action = model.predict_action(state)
    return {
        "action": int(action),
        "predicted_temperature": round(model.predict_next_temperature(state, action), 3),
        "confidence": model.confidence(state, action),
        "model_version": model.to_dict()["version"],
    }

