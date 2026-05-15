class SafetyLayer:
    HARD_LIMIT = 28.0
    WARNING_LIMIT = 26.5
    COOLING_MIN = 35.0
    COOLING_MAX = 100.0
    MAX_CHANGE_PER_STEP = 0.5

    def status_for_temperature(self, temperature):
        if temperature >= self.HARD_LIMIT:
            return "CRITICAL"
        if temperature >= self.WARNING_LIMIT:
            return "WARNING"
        return "SAFE"

    def validate(self, action, state, previous_action):
        action = self._clamp_delta(action)

        temperature = state["temperature"]
        workload = state["workload"]
        cooling = state["cooling"]
        hottest_rack = state.get("hottest_rack", {}).get("temperature", temperature)
        projected_cooling = self._bounded_cooling(cooling + action)
        projected_temperature = temperature + workload * 0.018 - projected_cooling * 0.021

        if hottest_rack >= self.HARD_LIMIT - 0.15:
            return self.MAX_CHANGE_PER_STEP

        if temperature >= self.HARD_LIMIT - 0.2:
            return self.MAX_CHANGE_PER_STEP

        if projected_temperature >= self.HARD_LIMIT or hottest_rack >= self.WARNING_LIMIT + 0.8:
            return self.MAX_CHANGE_PER_STEP

        if (temperature >= self.WARNING_LIMIT or hottest_rack >= self.WARNING_LIMIT) and action < 0:
            return 0.0

        if cooling <= self.COOLING_MIN + self.MAX_CHANGE_PER_STEP and action < 0:
            return 0.0

        if cooling >= self.COOLING_MAX - self.MAX_CHANGE_PER_STEP and action > 0:
            return 0.0

        return action

    def clamp_cooling(self, cooling):
        return round(self._bounded_cooling(cooling), 2)

    def _bounded_cooling(self, cooling):
        return max(self.COOLING_MIN, min(self.COOLING_MAX, cooling))

    def _clamp_delta(self, action):
        return max(-self.MAX_CHANGE_PER_STEP, min(self.MAX_CHANGE_PER_STEP, action))
