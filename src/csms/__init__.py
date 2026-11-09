"""Community Services Management System Flask application."""

from flask import Flask

from csms.config import DevelopmentConfig


def create_app(test_config: dict[str, object] | None = None) -> Flask:
    """Create and configure the CSMS Flask application.

    Args:
        test_config: Optional configuration overrides used during testing.

    Returns:
        A configured Flask application.
    """
    app = Flask(__name__)

    app.config.from_object(DevelopmentConfig)

    if test_config is not None:
        app.config.update(test_config)

    from csms.ui.routes import main_blueprint
    app.register_blueprint(main_blueprint)

    from csms.ui.resident_routes import residents_bp
    app.register_blueprint(residents_bp)

    return app