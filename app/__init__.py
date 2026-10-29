from pathlib import Path

from flask import Flask

from .config import Config
from .extensions import db, login_manager


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    Path(app.config["UPLOAD_FOLDER"]).mkdir(parents=True, exist_ok=True)

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Inicie sessao para aceder ao sistema."

    from .routes.auth import auth_bp
    from .routes.dashboard import dashboard_bp
    from .routes.documents import documents_bp
    from .routes.admin import admin_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(documents_bp)
    app.register_blueprint(admin_bp)

    with app.app_context():
        from .models import seed_demo_data

        db.create_all()
        seed_demo_data()

    return app

