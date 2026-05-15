import json
import math
from pathlib import Path


MODEL_VERSION = "v3_next_temperature_ridge_sgd"
TARGET_TEMPERATURE = 25.0
DEADBAND = 1.0
HARD_LIMIT = 28.0
WARNING_LIMIT = 26.5
COOLING_MIN = 35.0
COOLING_MAX = 100.0
ACTION_COOLING_EFFECT = 2.0

FEATURE_NAMES = [
    "temperature",
    "temp_lag_1",
    "temp_lag_2",
    "temp_ema",
    "cooling_level",
    "workload_level",
    "ambient_temperature",
    "humidity",
    "hour_sin",
    "hour_cos",
    "hotspot_flag",
]


class NextTemperatureModel:
    def __init__(self, weights=None, bias=0.0, means=None, stds=None, metrics=None):
        self.weights = weights or [0.0 for _ in FEATURE_NAMES]
        self.bias = bias
        self.means = means or {name: 0.0 for name in FEATURE_NAMES}
        self.stds = stds or {name: 1.0 for name in FEATURE_NAMES}
        self.metrics = metrics or {}

    def predict_next_temperature(self, state, action=0):
        features = build_runtime_features(state, action)
        scaled = self._scale(features)
        return self.bias + sum(weight * value for weight, value in zip(self.weights, scaled))

    def predict_action(self, state):
        previous_action = int(state.get("previous_action", 0) or 0)
        raw_temperature = control_temperature(state)
        smoothed_temperature = float(state.get("smoothed_temperature") or raw_temperature)

        if raw_temperature >= HARD_LIMIT - 0.2:
            return 1

        if raw_temperature >= WARNING_LIMIT or smoothed_temperature >= TARGET_TEMPERATURE + DEADBAND:
            return 1

        if TARGET_TEMPERATURE - DEADBAND <= smoothed_temperature <= TARGET_TEMPERATURE + DEADBAND:
            return 0

        if raw_temperature >= TARGET_TEMPERATURE + 0.6:
            return 1

        candidates = [-1, 0, 1]
        scored_actions = []
        for action in candidates:
            if raw_temperature >= WARNING_LIMIT and action < 0:
                continue

            predicted = self.predict_next_temperature(state, action)
            projected_cooling = bounded_cooling(float(state.get("cooling", 58.0)) + action * ACTION_COOLING_EFFECT)
            score = self._control_cost(
                predicted_temperature=predicted,
                projected_cooling=projected_cooling,
                action=action,
                previous_action=previous_action,
            )
            scored_actions.append((score, action, predicted))

        if not scored_actions:
            return 1

        scored_actions.sort(key=lambda item: item[0])
        return int(scored_actions[0][1])

    def confidence(self, state, action):
        predicted = self.predict_next_temperature(state, action)
        distance = abs(predicted - TARGET_TEMPERATURE)
        return round(max(0.35, min(0.95, 1.0 - distance / 10.0)), 3)

    def to_dict(self):
        return {
            "version": MODEL_VERSION,
            "feature_names": FEATURE_NAMES,
            "weights": self.weights,
            "bias": self.bias,
            "means": self.means,
            "stds": self.stds,
            "metrics": self.metrics,
        }

    @classmethod
    def from_dict(cls, payload):
        return cls(
            weights=payload["weights"],
            bias=payload["bias"],
            means=payload["means"],
            stds=payload["stds"],
            metrics=payload.get("metrics", {}),
        )

    def save(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path):
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls.from_dict(payload)

    def _scale(self, features):
        return [
            (features[name] - self.means[name]) / max(self.stds[name], 1e-6)
            for name in FEATURE_NAMES
        ]

    def _control_cost(self, predicted_temperature, projected_cooling, action, previous_action):
        deviation = predicted_temperature - TARGET_TEMPERATURE
        temp_cost = deviation * deviation
        high_temp_penalty = max(0.0, predicted_temperature - WARNING_LIMIT) ** 2 * 8.0
        hard_limit_penalty = max(0.0, predicted_temperature - HARD_LIMIT) ** 2 * 80.0
        energy_cost = (projected_cooling / COOLING_MAX) * 0.12
        switching_cost = 0.2 if action != previous_action else 0.0
        neutral_bias = 0.05 if action != 0 else 0.0
        return temp_cost + high_temp_penalty + hard_limit_penalty + energy_cost + switching_cost + neutral_bias


def build_runtime_features(state, action=0):
    temperature = control_temperature(state)
    history = state.get("temperature_history") or []
    temp_lag_1 = float(history[-1]) if len(history) >= 1 else temperature
    temp_lag_2 = float(history[-2]) if len(history) >= 2 else temp_lag_1
    smoothed = float(state.get("smoothed_temperature") or (0.5 * temperature + 0.3 * temp_lag_1 + 0.2 * temp_lag_2))
    hour = int(state.get("hour_of_day", 12) or 12)
    cooling = bounded_cooling(float(state.get("cooling", 58.0)) + action * ACTION_COOLING_EFFECT)
    workload = float(state.get("workload", 60.0))
    ambient = float(state.get("ambient_temperature", 24.0))
    humidity = float(state.get("humidity", 50.0))
    hotspot = 1.0 if temperature >= WARNING_LIMIT or int(state.get("hotspot_flag", 0) or 0) else 0.0

    return {
        "temperature": temperature,
        "temp_lag_1": temp_lag_1,
        "temp_lag_2": temp_lag_2,
        "temp_ema": smoothed,
        "cooling_level": cooling,
        "workload_level": workload,
        "ambient_temperature": ambient,
        "humidity": humidity,
        "hour_sin": math.sin(2.0 * math.pi * hour / 24.0),
        "hour_cos": math.cos(2.0 * math.pi * hour / 24.0),
        "hotspot_flag": hotspot,
    }


def control_temperature(state):
    hottest = state.get("hottest_rack_temperature")
    if hottest is None and isinstance(state.get("hottest_rack"), dict):
        hottest = state["hottest_rack"].get("temperature")
    return max(float(state.get("temperature", 25.0)), float(hottest or state.get("temperature", 25.0)))


def bounded_cooling(cooling):
    return max(COOLING_MIN, min(COOLING_MAX, cooling))
