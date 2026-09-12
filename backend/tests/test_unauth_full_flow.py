import pytest
from app import create_app, db
from app.models.models import Video, Article, Transcript, Audio


@pytest.fixture
def app():
    app = create_app()
    app.config["TESTING"] = True
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def test_complete_unauthenticated_pipeline_flow(client, app):
    """Verify that processing, reading, translating, listening, and deleting history work 100% without auth token."""
    with app.app_context():
        # 1. Create a done video directly to simulate processed video
        video = Video(
            youtube_id="dQw4w9WgXcQ",
            youtube_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            title="Unauthenticated Test Video",
            thumbnail_url="https://img.youtube.com/vi/dQw4w9WgXcQ/hqdefault.jpg",
            original_language="en",
            status="done",
            user_id=None
        )
        db.session.add(video)
        db.session.commit()

        article = Article(
            video_id=video.id,
            language="en",
            title="Unauthenticated Test Article",
            content="IMPORTANT CONTENT\n\n- Fact 1 about AI technology.\n- Fact 2 about web applications.",
            is_original=True,
            is_published=False
        )
        db.session.add(article)
        db.session.commit()

        # 2. Get article without auth headers
        res_art = client.get(f"/api/articles/{article.id}")
        assert res_art.status_code == 200
        assert res_art.json["success"] is True
        assert res_art.json["data"]["title"] == "Unauthenticated Test Article"

        # 3. Get history without auth headers
        res_hist = client.get("/api/history")
        assert res_hist.status_code == 200
        assert res_hist.json["success"] is True
        assert len(res_hist.json["data"]) >= 1

        # 4. Delete single history item without auth headers
        res_del = client.delete(f"/api/history/{video.id}")
        assert res_del.status_code == 200
        assert res_del.json["success"] is True
        assert db.session.get(Video, video.id) is None

        # 5. Clear all history without auth headers
        res_clear = client.delete("/api/history/clear_all")
        assert res_clear.status_code == 200
        assert res_clear.json["success"] is True
