from services.environment import DataCenterEnvironment
from services.ml_client import MLClient
from services.safety import SafetyLayer
from controller.stability import StabilizedControlPolicy


class CoolingController:
    def __init__(self):
        self.environment = DataCenterEnvironment()
        self.ml_client = MLClient()
        self.safety = SafetyLayer()
        self.stability = StabilizedControlPolicy()
        self.mode = "AI"
        self.last_safe_action = 0
        self.baseline_cooling = 58.0

    def get_state(self):
        state = self.environment.snapshot()
        state["mode"] = self.mode
        state["status"] = self.safety.status_for_temperature(state["temperature"])
        state["rack_status"] = self.safety.status_for_temperature(state["hottest_rack"]["temperature"])
        state.update(self.stability.metadata())
        state["previous_action"] = self.last_safe_action
        return state

    def set_mode(self, mode):
        self.mode = mode
        if mode == "BASELINE":
            self.environment.set_cooling(self.baseline_cooling)
            self.last_safe_action = 0
            self.stability.reset_hold()
        return self.get_state()

    def step(self):
        state_before = self.get_state()

        if self.mode == "AI":
            ml_direction = self.ml_client.predict(state_before)
        else:
            ml_direction = 0

        action = self.stability.choose_action(
            state=state_before,
            ml_direction=ml_direction,
            mode=self.mode,
        )

        # If oscillation was detected, snap cooling to the computed average
        if self.stability.steady_cooling is not None:
            self.environment.set_cooling(self.stability.steady_cooling)
            self.stability.steady_cooling = None
            safe_action = 0.0
        elif self.mode == "BASELINE":
            safe_action = self.safety.validate(
                action=0.0,
                state=state_before,
                previous_action=self.last_safe_action,
            )
        else:
            safe_action = self.safety.validate(
                action=action,
                state=state_before,
                previous_action=self.last_safe_action,
            )

        if safe_action != action:
            self.stability.control_phase = "Correcting"
            if safe_action != 0:
                self.stability.last_action_step = self.stability.current_step

        self.last_safe_action = safe_action
        self.environment.apply_action(safe_action)
        state_after = self.environment.step(mode=self.mode, safety=self.safety)
        state_after["rack_status"] = self.safety.status_for_temperature(
            state_after["hottest_rack"]["temperature"]
        )
        state_after.update(self.stability.metadata())

        return {
            "state": state_after,
            "action": action,
            "safe_action": safe_action,
            "decision": self._decision_summary(state_before, action, safe_action),
        }

    def _decision_summary(self, state, action, safe_action):
        hottest = state["hottest_rack"]
        if action != safe_action:
            return f"Safety adjusted command for {hottest['id']} at {hottest['temperature']:.2f} C"
        if safe_action > 0:
            return f"Correcting: cooling increased by {safe_action:.1f}; {hottest['id']} is {hottest['temperature']:.2f} C"
        if safe_action < 0:
            return f"Stabilizing: cooling reduced by {abs(safe_action):.1f}; smoothed temperature is within control range"
        if self.stability.control_phase == "Steady":
            return f"Steady: cooling locked at {state['cooling']:.1f}% (oscillation averaged)"
        return f"Holding: deadband active around {self.stability.TARGET_TEMPERATURE:.1f} C"


cooling_controller = CoolingController()
