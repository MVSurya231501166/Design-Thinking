from inference import predict_action


sample = {
    "temperature": 25.8,
    "hottest_rack_temperature": 26.4,
    "cooling": 58.0,
    "workload": 74.0,
    "smoothed_temperature": 26.1,
    "temperature_history": [25.4, 25.7, 25.8],
    "previous_action": 0,
}


if __name__ == "__main__":
    print(predict_action(sample))

