from flask import Flask, jsonify, request

from inference import predict_action


app = Flask(__name__)


@app.after_request
def cors(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    response.headers["Access-Control-Allow-Methods"] = "POST,OPTIONS"
    return response


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "cooling-ml-v3"})


@app.route("/predict", methods=["POST", "OPTIONS"])
def predict():
    if request.method == "OPTIONS":
        return ("", 204)
    state = request.get_json(silent=True) or {}
    return jsonify(predict_action(state))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=False)

