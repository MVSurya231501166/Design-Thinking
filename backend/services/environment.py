import math
import random


class DataCenterEnvironment:
    def __init__(self, seed=42):
        self.random = random.Random(seed)
        self.tick = 0
        self.temperature = 24.2
        self.workload = 62.0
        self.cooling = 58.0
        self.racks = self._create_racks()

    def snapshot(self):
        hottest = max(self.racks, key=lambda rack: rack["temperature"])
        avg_temperature = sum(rack["temperature"] for rack in self.racks) / len(self.racks)
        avg_workload = sum(rack["load"] for rack in self.racks) / len(self.racks)
        return {
            "temperature": round(avg_temperature, 2),
            "workload": round(avg_workload, 2),
            "cooling": round(self.cooling, 2),
            "hottest_rack": self._public_rack(hottest),
            "racks": [self._public_rack(rack) for rack in self.racks],
        }

    def set_cooling(self, cooling):
        self.cooling = max(35.0, min(100.0, cooling))

    def apply_action(self, action):
        self.cooling = max(35.0, min(100.0, self.cooling + action))

    def step(self, mode, safety):
        self.tick += 1
        self._update_racks()
        self.workload = sum(rack["load"] for rack in self.racks) / len(self.racks)
        self.temperature = sum(rack["temperature"] for rack in self.racks) / len(self.racks)
        self.cooling = safety.clamp_cooling(self.cooling)

        state = self.snapshot()
        state["mode"] = mode
        state["status"] = safety.status_for_temperature(state["temperature"])
        return state

    def _create_racks(self):
        racks = []
        rows = ["A", "B", "C"]
        for row_index, row in enumerate(rows):
            for position in range(1, 7):
                index = row_index * 6 + position
                load = 48.0 + row_index * 5.0 + position * 2.0 + self.random.uniform(-3.0, 3.0)
                temperature = 23.2 + row_index * 0.35 + position * 0.12 + self.random.uniform(-0.25, 0.25)
                racks.append(
                    {
                        "id": f"{row}{position:02d}",
                        "row": row,
                        "position": position,
                        "load": load,
                        "temperature": temperature,
                        "cooling_share": 0.0,
                    }
                )
        return racks

    def _update_racks(self):
        hotspot_index = int((math.sin(self.tick / 9.0) + 1) * 8.5)
        for index, rack in enumerate(self.racks):
            row_bias = {"A": 0.96, "B": 1.04, "C": 1.1}[rack["row"]]
            cyclic = math.sin((self.tick + rack["position"] * 1.7) / 6.0) * 10.0
            migration = 14.0 if abs(index - hotspot_index) <= 1 else 0.0
            noise = self.random.uniform(-3.2, 3.2)
            target_load = 52.0 * row_bias + cyclic + migration + noise
            rack["load"] = self._approach(rack["load"], target_load, 0.28)
            rack["load"] = max(25.0, min(98.0, rack["load"]))

        total_load = sum(rack["load"] for rack in self.racks)
        for rack in self.racks:
            demand_share = rack["load"] / total_load
            rack["cooling_share"] = max(1.8, self.cooling * demand_share * 1.22)
            heat_gain = rack["load"] * 0.021
            cooling_effect = rack["cooling_share"] * 0.26
            ambient_pull = (23.4 - rack["temperature"]) * 0.055
            crossflow = (self.temperature - rack["temperature"]) * 0.025
            noise = self.random.uniform(-0.04, 0.04)
            rack["temperature"] += heat_gain - cooling_effect + ambient_pull + crossflow + noise
            rack["temperature"] = max(18.0, min(31.8, rack["temperature"]))

    def _public_rack(self, rack):
        return {
            "id": rack["id"],
            "row": rack["row"],
            "position": rack["position"],
            "load": round(rack["load"], 2),
            "temperature": round(rack["temperature"], 2),
            "cooling_share": round(rack["cooling_share"], 2),
            "status": self._rack_status(rack["temperature"]),
        }

    def _rack_status(self, temperature):
        if temperature >= 28.0:
            return "CRITICAL"
        if temperature >= 26.5:
            return "WARNING"
        return "SAFE"

    def _approach(self, current, target, factor):
        return current + (target - current) * factor
