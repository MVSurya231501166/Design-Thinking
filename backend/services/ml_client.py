import requests


class MLClient:
    def __init__(self, url="http://localhost:8000/predict", timeout=0.35):
        self.url = url
        self.timeout = timeout

    def predict(self, state):
        payload = {
            "temperature": state["temperature"],
            "workload": state["workload"],
            "cooling": state["cooling"],
            "smoothed_temperature": state.get("smoothed_temperature"),
            "control_phase": state.get("control_phase"),
            "previous_action": state.get("previous_action", 0),
            "hottest_rack_temperature": state.get("hottest_rack", {}).get("temperature"),
            "rack_loads": [
                {"id": rack["id"], "load": rack["load"], "temperature": rack["temperature"]}
                for rack in state.get("racks", [])
            ],
        }

        try:
            response = requests.post(self.url, json=payload, timeout=self.timeout)
            response.raise_for_status()
            action = int(response.json().get("action", 0))
            if action in (-1, 0, 1):
                return action
        except requests.RequestException:
            pass
        except (TypeError, ValueError):
            pass

        return self._mock_predict(state)

    def _mock_predict(self, state):
        temperature = state["temperature"]
        workload = state["workload"]
        cooling = state["cooling"]
        hottest = state.get("hottest_rack", {}).get("temperature", temperature)
        hot_racks = sum(1 for rack in state.get("racks", []) if rack["temperature"] >= 26.4)

        if hottest >= 27.2 or temperature >= 26.8 or hot_racks >= 3:
            return 1
        if temperature <= 23.2 and workload < 58 and cooling > 45:
            return -1
        if hottest >= 26.4 and cooling < 80:
            return 1
        if hottest <= 24.6 and temperature <= 24.0 and cooling > 52:
            return -1
        return 0
