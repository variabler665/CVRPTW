import os
from flask import Flask
from flask_cors import CORS
from .database import engine, Base
from .routes import api_bp, pages_bp


def create_app():
    app = Flask(__name__)
    CORS(app)
    app.config["JSON_AS_ASCII"] = False
    Base.metadata.create_all(bind=engine)
    app.register_blueprint(api_bp, url_prefix="/api")
    app.register_blueprint(pages_bp)
    return app


app = create_app()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
