import pytest
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

os.environ["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"

from app import create_app, db



@pytest.fixture()
def app(tmp_path):
    db_file = tmp_path / "test_vetri.db"
    application = create_app()
    application.config.update({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": f"sqlite:///{db_file}",
    })
    with application.app_context():
        db.create_all()
        yield application
        db.session.remove()


@pytest.fixture()
def client(app):
    return app.test_client()
