import csv
import math

from model import FEATURE_NAMES


def iter_training_samples(dataset_path):
    histories = {}
    pending = {}

    with open(dataset_path, "r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            rack_id = row["rack_id"]
            current_temperature = to_float(row["rack_temperature_c"])

            if rack_id in pending:
                yield pending[rack_id], current_temperature

            history = histories.get(rack_id, [])
            features = row_to_features(row, history)
            pending[rack_id] = features

            history.append(current_temperature)
            if len(history) > 4:
                history.pop(0)
            histories[rack_id] = history


def row_to_features(row, history):
    temperature = to_float(row["rack_temperature_c"])
    temp_lag_1 = history[-1] if len(history) >= 1 else temperature
    temp_lag_2 = history[-2] if len(history) >= 2 else temp_lag_1
    temp_ema = 0.5 * temperature + 0.3 * temp_lag_1 + 0.2 * temp_lag_2
    cooling_level = cooling_level_from_row(row)
    workload_level = workload_level_from_row(row)
    hour = int(to_float(row["hour_of_day"]))

    return {
        "temperature": temperature,
        "temp_lag_1": temp_lag_1,
        "temp_lag_2": temp_lag_2,
        "temp_ema": temp_ema,
        "cooling_level": cooling_level,
        "workload_level": workload_level,
        "ambient_temperature": to_float(row["ambient_temperature_c"]),
        "humidity": to_float(row["humidity_pct"]),
        "hour_sin": math.sin(2.0 * math.pi * hour / 24.0),
        "hour_cos": math.cos(2.0 * math.pi * hour / 24.0),
        "hotspot_flag": to_float(row["hotspot_flag"]),
    }


def cooling_level_from_row(row):
    valve = to_float(row["cooling_valve_position"]) * 100.0
    chiller = to_float(row["chiller_load_pct"])
    fan = to_float(row["fan_speed_rpm"]) / 2500.0 * 100.0
    airflow = to_float(row["airflow_cfm"]) / 1300.0 * 100.0
    cooling_power = to_float(row["cooling_power_kw"]) / 4.0 * 100.0
    return bounded((valve + chiller + fan + airflow + cooling_power) / 5.0, 0.0, 100.0)


def workload_level_from_row(row):
    cpu = to_float(row["cpu_utilization_pct"])
    gpu = to_float(row["gpu_utilization_pct"])
    memory = to_float(row["memory_usage_pct"])
    queue = min(100.0, to_float(row["task_queue_length"]) * 10.0)
    it_power = min(100.0, to_float(row["it_power_kw"]) / 8.0 * 100.0)
    return bounded(0.28 * cpu + 0.28 * gpu + 0.18 * memory + 0.12 * queue + 0.14 * it_power, 0.0, 100.0)


def compute_feature_stats(dataset_path):
    count = 0
    sums = {name: 0.0 for name in FEATURE_NAMES}
    sums_sq = {name: 0.0 for name in FEATURE_NAMES}
    target_sum = 0.0

    for features, target in iter_training_samples(dataset_path):
        count += 1
        target_sum += target
        for name in FEATURE_NAMES:
            value = features[name]
            sums[name] += value
            sums_sq[name] += value * value

    means = {name: sums[name] / count for name in FEATURE_NAMES}
    stds = {}
    for name in FEATURE_NAMES:
        variance = max(1e-6, sums_sq[name] / count - means[name] * means[name])
        stds[name] = math.sqrt(variance)

    return means, stds, target_sum / count, count


def to_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def bounded(value, minimum, maximum):
    return max(minimum, min(maximum, value))

