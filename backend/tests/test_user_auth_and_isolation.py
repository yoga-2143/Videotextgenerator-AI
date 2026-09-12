import os
import pytest
from app import create_app, db
from app.models.models import User, Video, Article, Transcript, Audio, TranslationCache
from app.utils.auth_utils import issue_token


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


def test_user_authentication_and_history_isolation(client, app):
    with app.app_context():
        # Create User A & User B
        user_a = User(email="user_a@example.com", name="User A", google_id="google_sub_a")
        user_b = User(email="user_b@example.com", name="User B", google_id="google_sub_b")
        db.session.add_all([user_a, user_b])
        db.session.commit()

        token_a = issue_token(user_a)
        token_b = issue_token(user_b)

        headers_a = {"Authorization": f"Bearer {token_a}"}
        headers_b = {"Authorization": f"Bearer {token_b}"}

        # 1. Create Video A for User A
        video_a = Video(
            youtube_id="vid_a_12345",
            youtube_url="https://www.youtube.com/watch?v=vid_a_12345",
            title="User A Video",
            status="done",
            user_id=user_a.id
        )
        db.session.add(video_a)
        db.session.commit()

        article_a = Article(
            video_id=video_a.id,
            language="en",
            title="User A Article",
            content="IMPORTANT CONTENT\n\nContent for User A.",
            is_original=True,
            is_published=False
        )
        db.session.add(article_a)

        # 2. Create Video B for User B
        video_b = Video(
            youtube_id="vid_b_67890",
            youtube_url="https://www.youtube.com/watch?v=vid_b_67890",
            title="User B Video",
            status="done",
            user_id=user_b.id
        )
        db.session.add(video_b)
        db.session.commit()

        article_b = Article(
            video_id=video_b.id,
            language="en",
            title="User B Article",
            content="IMPORTANT CONTENT\n\nContent for User B.",
            is_original=True,
            is_published=False
        )
        db.session.add(article_b)

        # 3. Create Legacy Video (user_id IS NULL)
        video_legacy = Video(
            youtube_id="vid_legacy_00",
            youtube_url="https://www.youtube.com/watch?v=vid_legacy_00",
            title="Legacy Video",
            status="done",
            user_id=None
        )
        db.session.add(video_legacy)
        db.session.commit()

        # ==========================================
        # VERIFICATION 1: GET HISTORY ISOLATION
        # ==========================================
        res_a = client.get("/api/history", headers=headers_a)
        assert res_a.status_code == 200
        data_a = res_a.json["data"]
        titles_a = [item["title"] for item in data_a]
        assert "User A Video" in titles_a
        assert "User B Video" not in titles_a
        assert "Legacy Video" not in titles_a

        res_b = client.get("/api/history", headers=headers_b)
        assert res_b.status_code == 200
        data_b = res_b.json["data"]
        titles_b = [item["title"] for item in data_b]
        assert "User B Video" in titles_b
        assert "User A Video" not in titles_b
        assert "Legacy Video" not in titles_b

        # Unauthenticated request to /api/history must return 401
        res_unauth = client.get("/api/history")
        assert res_unauth.status_code == 401

        # ==========================================
        # VERIFICATION 2: ARTICLE ACCESS CONTROL
        # ==========================================
        # User A can view User A article
        res_art_a = client.get(f"/api/articles/{article_a.id}", headers=headers_a)
        assert res_art_a.status_code == 200
        assert res_art_a.json["data"]["title"] == "User A Article"

        # User B CANNOT view User A article -> 403 Forbidden
        res_art_b_on_a = client.get(f"/api/articles/{article_a.id}", headers=headers_b)
        assert res_art_b_on_a.status_code == 403

        # Unauthenticated user CANNOT view User A article -> 403 Forbidden
        res_art_unauth_on_a = client.get(f"/api/articles/{article_a.id}")
        assert res_art_unauth_on_a.status_code == 403

        # ==========================================
        # VERIFICATION 3: DELETE ONE SECURITY
        # ==========================================
        # User B tries to delete User A video -> 404 Not Found
        res_del_b_on_a = client.delete(f"/api/history/{video_a.id}", headers=headers_b)
        assert res_del_b_on_a.status_code == 404

        # User A deletes User A video -> 200 OK
        res_del_a = client.delete(f"/api/history/{video_a.id}", headers=headers_a)
        assert res_del_a.status_code == 200

        # Video A is gone
        assert db.session.get(Video, video_a.id) is None
        # Video B remains intact
        assert db.session.get(Video, video_b.id) is not None

        # ==========================================
        # VERIFICATION 4: DELETE ALL SECURITY
        # ==========================================
        # User B calls clear_all -> deletes ONLY User B videos
        res_clear_b = client.delete("/api/history/clear_all", headers=headers_b)
        assert res_clear_b.status_code == 200

        # Video B is gone
        assert db.session.get(Video, video_b.id) is None
        # Legacy Video remains intact
        assert db.session.get(Video, video_legacy.id) is not None

        # ==========================================
        # VERIFICATION 5: CROSS-DEVICE SAME ACCOUNT
        # ==========================================
        # Simulate device 2 issuing another token for User A
        token_a_device2 = issue_token(user_a)
        headers_a_device2 = {"Authorization": f"Bearer {token_a_device2}"}

        # Create new Video A2 via device 1
        video_a2 = Video(
            youtube_id="vid_a2_99999",
            youtube_url="https://www.youtube.com/watch?v=vid_a2_99999",
            title="User A Device 1 Video",
            status="done",
            user_id=user_a.id
        )
        db.session.add(video_a2)
        db.session.commit()

        # Query history on device 2
        res_a_dev2 = client.get("/api/history", headers=headers_a_device2)
        assert res_a_dev2.status_code == 200
        titles_a_dev2 = [item["title"] for item in res_a_dev2.json["data"]]
        assert "User A Device 1 Video" in titles_a_dev2
