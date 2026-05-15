from flask import Blueprint, jsonify, request

from controller.control_loop import cooling_controller

api = Blueprint("api", __name__)


@api.route("/state", methods=["GET"])
def get_state():
    return jsonify(cooling_controller.get_state())


@api.route("/step", methods=["POST", "OPTIONS"])
def step():
    if request.method == "OPTIONS":
        return ("", 204)

    result = cooling_controller.step()
    return jsonify(result)


@api.route("/mode", methods=["POST", "OPTIONS"])
def set_mode():
    if request.method == "OPTIONS":
        return ("", 204)

    payload = request.get_json(silent=True) or {}
    mode = payload.get("mode")

    if mode not in ("AI", "BASELINE"):
        return jsonify({"error": "mode must be AI or BASELINE"}), 400

    state = cooling_controller.set_mode(mode)
    return jsonify(state)

