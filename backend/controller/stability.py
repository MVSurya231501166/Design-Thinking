class StabilizedControlPolicy:
    TARGET_TEMPERATURE = 25.0
    DEADBAND = 1.0
    EMA_ALPHA = 0.25
    MAX_CHANGE_PER_STEP = 0.5
    MIN_HOLD_STEPS = 5
    OSCILLATION_WINDOW = 6
    STEADY_HOLD_DURATION = 15

    def __init__(self):
        self.smoothed_temperature = None
        self.last_action_step = -self.MIN_HOLD_STEPS
        self.current_step = 0
        self.control_phase = "Holding"
        self.action_history = []
        self.cooling_history = []
        self.steady_until_step = 0
        self.steady_cooling = None

    def reset_hold(self):
        self.last_action_step = self.current_step
        self.control_phase = "Holding"
        self.action_history.clear()
        self.cooling_history.clear()
        self.steady_until_step = 0
        self.steady_cooling = None

    def choose_action(self, state, ml_direction, mode):
        self.current_step += 1
        raw_temperature = self._control_temperature(state)
        self.smoothed_temperature = self._smooth(raw_temperature)

        # If in steady hold from oscillation detection, keep holding
        if self.current_step < self.steady_until_step:
            self.control_phase = "Steady"
            return 0.0

        lower_bound = self.TARGET_TEMPERATURE - self.DEADBAND
        upper_bound = self.TARGET_TEMPERATURE + self.DEADBAND

        if mode == "BASELINE":
            self.control_phase = "Holding"
            return 0.0

        if self.smoothed_temperature > upper_bound:
            direction = 1
            self.control_phase = "Correcting"
        elif self.smoothed_temperature < lower_bound:
            direction = -1
            self.control_phase = "Stabilizing"
        else:
            self.control_phase = "Holding"
            return 0.0

        if not self._hold_elapsed():
            self.control_phase = "Holding"
            return 0.0

        if ml_direction == 0:
            action = direction
        elif direction > 0:
            action = max(ml_direction, direction)
        else:
            action = min(ml_direction, direction)

        delta = self._rate_limited_delta(action)
        if delta != 0:
            self.last_action_step = self.current_step

            # Track action direction and cooling value for oscillation detection
            self.action_history.append(1 if delta > 0 else -1)
            self.cooling_history.append(state["cooling"])
            if len(self.action_history) > self.OSCILLATION_WINDOW * 2:
                self.action_history = self.action_history[-self.OSCILLATION_WINDOW:]
                self.cooling_history = self.cooling_history[-self.OSCILLATION_WINDOW:]

            # Check for oscillation pattern (alternating +/-)
            if self._is_oscillating():
                self.steady_cooling = sum(self.cooling_history) / len(self.cooling_history)
                self.steady_until_step = self.current_step + self.STEADY_HOLD_DURATION
                self.action_history.clear()
                self.cooling_history.clear()
                self.control_phase = "Steady"
                return 0.0

        return delta

    def force_adjustment(self, direction):
        delta = self._rate_limited_delta(direction)
        if delta != 0:
            self.last_action_step = self.current_step
        self.control_phase = "Correcting"
        return delta

    def metadata(self):
        return {
            "target_temperature": self.TARGET_TEMPERATURE,
            "deadband": self.DEADBAND,
            "smoothed_temperature": round(self.smoothed_temperature, 2)
            if self.smoothed_temperature is not None
            else None,
            "control_phase": self.control_phase,
            "current_step": self.current_step,
            "last_action_step": self.last_action_step,
            "hold_steps_remaining": max(
                0, self.MIN_HOLD_STEPS - (self.current_step - self.last_action_step)
            ),
            "steady_steps_remaining": max(0, self.steady_until_step - self.current_step),
        }

    def _smooth(self, raw_temperature):
        if self.smoothed_temperature is None:
            return raw_temperature
        return (
            self.EMA_ALPHA * raw_temperature
            + (1 - self.EMA_ALPHA) * self.smoothed_temperature
        )

    def _control_temperature(self, state):
        rack_temperature = state.get("hottest_rack", {}).get("temperature", state["temperature"])
        return max(state["temperature"], rack_temperature)

    def _hold_elapsed(self):
        return self.current_step - self.last_action_step >= self.MIN_HOLD_STEPS

    def _rate_limited_delta(self, action):
        if action > 0:
            return self.MAX_CHANGE_PER_STEP
        if action < 0:
            return -self.MAX_CHANGE_PER_STEP
        return 0.0

    def _is_oscillating(self):
        """Detect alternating +/- pattern in recent actions."""
        if len(self.action_history) < self.OSCILLATION_WINDOW:
            return False
        recent = self.action_history[-self.OSCILLATION_WINDOW:]
        for i in range(1, len(recent)):
            if recent[i] == recent[i - 1]:
                return False
        return True
