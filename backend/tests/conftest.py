import pytest
from app import create_app
from app.extensions import db as _db

TEST_CONFIG = {
    "TESTING": True,
    "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
    "CACHE_TTL_SECONDS": 30,
}


@pytest.fixture(scope="session")
def app():
    """Create a test Flask app with an in-memory SQLite database."""
    test_app = create_app(test_config=TEST_CONFIG)
    with test_app.app_context():
        _db.create_all()
        yield test_app
        _db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture(autouse=True)
def clean_db(app):
    """Truncate all tables before each test for full isolation."""
    with app.app_context():
        yield
        # Delete all rows from every table after each test
        for table in reversed(_db.metadata.sorted_tables):
            _db.session.execute(table.delete())
        _db.session.commit()
