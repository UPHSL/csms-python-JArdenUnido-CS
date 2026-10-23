"""Configuration settings for the CSMS Flask application."""

import os
import tempfile


class BaseConfig:
    """Settings shared by all application environments."""

    APP_NAME = "Community Services Management System"
    APP_VERSION = "0.1.0"
    CURRENT_SPRINT = "Sprint 0 - Developer Onboarding"

    SECRET_KEY = os.environ.get(
        "CSMS_SECRET_KEY",
        "development-only-secret-key",
    )

    # Path to the SQLite database file used by the persistence layer (T03).
    # Sub-classes may override this with a different path or ":memory:".
    DATABASE_PATH: str = os.environ.get(
        "CSMS_DATABASE_PATH",
        os.path.join(os.path.dirname(__file__), "..", "..", "csms.db"),
    )


class DevelopmentConfig(BaseConfig):
    """Local development configuration."""

    DEBUG = True


class TestingConfig(BaseConfig):
    """Automated testing configuration.

    Each test session writes to its own temporary file so that:

    * Tests are isolated from the development database.
    * Two :class:`~csms.repositories.resident_repository.ResidentRepository`
      instances created in the same test **share** the same on-disk file,
      which is required by Test 7 (persistence across repository instances).
      An in-memory ``:memory:`` database would not satisfy this because each
      ``sqlite3.connect(":memory:")`` call opens a *separate* in-process
      database invisible to other connections.
    """

    TESTING = True
    DEBUG = False
    SECRET_KEY = "testing-secret-key"

    # Use a real temporary file so multiple repository instances can share it.
    # The file is created once when this class attribute is evaluated at import
    # time, which gives every test in the same session the same path.
    _tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    _tmp.close()
    DATABASE_PATH: str = _tmp.name
