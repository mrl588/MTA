from flask import Flask
from flask_cors import CORS
from .extensions import db
from .firebase import init_firebase


def create_app(test_config: dict = None):
    app = Flask(__name__)
    app.config.from_object("app.config.Config")

    if test_config:
        app.config.update(test_config)

    CORS(app)
    db.init_app(app)

    with app.app_context():
        # Import models so SQLAlchemy metadata is populated before create_all
        from . import models  # noqa: F401
        db.create_all()

    init_firebase()

    from .routes import status, vehicles, stations, accessibility, favorites, trip
    app.register_blueprint(status.bp)
    app.register_blueprint(vehicles.bp)
    app.register_blueprint(stations.bp)
    app.register_blueprint(accessibility.bp)
    app.register_blueprint(favorites.bp)
    app.register_blueprint(trip.bp)

    return app
