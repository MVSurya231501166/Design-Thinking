from flask import Flask

from routes.api import api


def create_app():
    app = Flask(__name__)
    app.register_blueprint(api)

    @app.after_request
    def add_cors_headers(response):
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type"
        response.headers["Access-Control-Allow-Methods"] = "GET,POST,OPTIONS"
        return response

    return app


if __name__ == "__main__":
    create_app().run(host="0.0.0.0", port=5002, debug=True)
