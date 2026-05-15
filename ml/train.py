import argparse
import json
import math
import random
from pathlib import Path

from features import compute_feature_stats, iter_training_samples
from model import (
    COOLING_MAX,
    COOLING_MIN,
    FEATURE_NAMES,
    HARD_LIMIT,
    NextTemperatureModel,
    TARGET_TEMPERATURE,
)


DEFAULT_DATASET = r"I:\SURYA\ai_data_center_cooling_dataset.csv"
DEFAULT_MODEL = "artifacts/cooling_model.json"
DEFAULT_METRICS = "artifacts/metrics.json"


def train(dataset_path, model_path=DEFAULT_MODEL, metrics_path=DEFAULT_METRICS, epochs=4):
    means, stds, target_mean, sample_count = compute_feature_stats(dataset_path)
    model = NextTemperatureModel(
        weights=[0.0 for _ in FEATURE_NAMES],
        bias=target_mean,
        means=means,
        stds=stds,
    )

    model.weights, model.bias = fit_ridge_regression(model, dataset_path, target_mean)

    regression_metrics = evaluate_regression(model, dataset_path)
    policy_metrics = evaluate_policy(model)
    metrics = {
        "dataset_samples": sample_count,
        "regression": regression_metrics,
        "policy_simulation": policy_metrics,
    }

    model.metrics = metrics
    model.save(model_path)
    Path(metrics_path).parent.mkdir(parents=True, exist_ok=True)
    Path(metrics_path).write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    return model, metrics


def fit_ridge_regression(model, dataset_path, target_mean):
    size = len(FEATURE_NAMES) + 1
    matrix = [[0.0 for _ in range(size)] for _ in range(size)]
    vector = [0.0 for _ in range(size)]
    ridge = 0.35
    seen = 0

    for index, (features, target) in enumerate(iter_training_samples(dataset_path)):
        if index % 5 == 0:
            continue

        row = [1.0] + model._scale(features)
        centered_target = target - target_mean
        for i in range(size):
            vector[i] += row[i] * centered_target
            for j in range(size):
                matrix[i][j] += row[i] * row[j]
        seen += 1

    for i in range(1, size):
        matrix[i][i] += ridge

    solution = solve_linear_system(matrix, vector)
    bias = target_mean + solution[0]
    weights = solution[1:]
    print(f"ridge_train_samples={seen}")
    return weights, bias


def solve_linear_system(matrix, vector):
    size = len(vector)
    for pivot in range(size):
        best = max(range(pivot, size), key=lambda row: abs(matrix[row][pivot]))
        if best != pivot:
            matrix[pivot], matrix[best] = matrix[best], matrix[pivot]
            vector[pivot], vector[best] = vector[best], vector[pivot]

        pivot_value = matrix[pivot][pivot]
        if abs(pivot_value) < 1e-9:
            pivot_value = 1e-9

        for col in range(pivot, size):
            matrix[pivot][col] /= pivot_value
        vector[pivot] /= pivot_value

        for row in range(size):
            if row == pivot:
                continue
            factor = matrix[row][pivot]
            if factor == 0:
                continue
            for col in range(pivot, size):
                matrix[row][col] -= factor * matrix[pivot][col]
            vector[row] -= factor * vector[pivot]

    return vector


def evaluate_regression(model, dataset_path):
    count = 0
    abs_error = 0.0
    sq_error = 0.0

    for index, (features, target) in enumerate(iter_training_samples(dataset_path)):
        if index % 5 != 0:
            continue
        prediction = model.bias + sum(weight * value for weight, value in zip(model.weights, model._scale(features)))
        error = prediction - target
        count += 1
        abs_error += abs(error)
        sq_error += error * error

    return {
        "holdout_samples": count,
        "mae_c": round(abs_error / max(count, 1), 4),
        "rmse_c": round(math.sqrt(sq_error / max(count, 1)), 4),
    }


def evaluate_policy(model, episodes=24, steps=180):
    variances = []
    energy = []
    switches = []
    violations = []

    for episode in range(episodes):
        rng = random.Random(9000 + episode)
        temperature = 24.5 + rng.uniform(-0.4, 0.4)
        cooling = 58.0
        previous_action = 0
        history = [temperature, temperature]
        temps = []
        episode_switches = 0
        episode_violations = 0
        cooling_sum = 0.0

        for step in range(steps):
            workload = 58 + math.sin(step / 8.0) * 18 + math.sin(step / 21.0) * 9 + rng.uniform(-4.0, 4.0)
            workload = max(25.0, min(96.0, workload))
            state = {
                "temperature": temperature,
                "hottest_rack_temperature": temperature + max(0.0, workload - 68.0) * 0.018,
                "cooling": cooling,
                "workload": workload,
                "smoothed_temperature": 0.5 * temperature + 0.3 * history[-1] + 0.2 * history[-2],
                "temperature_history": history[-2:],
                "previous_action": previous_action,
                "ambient_temperature": 24.0 + math.sin(step / 60.0) * 2.5,
                "humidity": 50.0,
                "hour_of_day": step % 24,
            }

            action = model.predict_action(state)
            safety_override = temperature >= HARD_LIMIT - 0.8
            if safety_override:
                action = 1
            if action != previous_action:
                episode_switches += 1

            cooling_delta = 2.0 if safety_override else 0.5
            cooling = max(COOLING_MIN, min(COOLING_MAX, cooling + action * cooling_delta))
            heat_gain = workload * 0.018
            cooling_effect = cooling * 0.021
            inertia = (TARGET_TEMPERATURE - temperature) * 0.04
            temperature += heat_gain - cooling_effect + inertia + rng.uniform(-0.04, 0.04)
            temperature = max(18.0, min(31.0, temperature))

            if temperature >= HARD_LIMIT:
                episode_violations += 1
                temperature = HARD_LIMIT - 0.05
                cooling = min(COOLING_MAX, cooling + 4.0)

            previous_action = action
            history.append(temperature)
            history = history[-3:]
            temps.append(temperature)
            cooling_sum += cooling

        mean_temp = sum(temps) / len(temps)
        variances.append(sum((temp - mean_temp) ** 2 for temp in temps) / len(temps))
        energy.append(cooling_sum / steps)
        switches.append(episode_switches)
        violations.append(episode_violations)

    return {
        "temperature_variance_c2": round(sum(variances) / len(variances), 4),
        "average_cooling_level": round(sum(energy) / len(energy), 4),
        "average_control_switches": round(sum(switches) / len(switches), 2),
        "safety_violations": int(sum(violations)),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default=DEFAULT_DATASET)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--metrics", default=DEFAULT_METRICS)
    parser.add_argument("--epochs", type=int, default=4)
    args = parser.parse_args()

    model, metrics = train(args.dataset, args.model, args.metrics, args.epochs)
    print(json.dumps(metrics, indent=2))
    print(f"saved_model={args.model}")


if __name__ == "__main__":
    main()
