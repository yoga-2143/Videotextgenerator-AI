import pytest
from app import create_app, db
from app.models.models import Video, Article, Transcript
from app.services.job_manager import create_video_job, set_job_result, get_job_state, JobStage


@pytest.fixture
def client():
    app = create_app()
    app.config["TESTING"] = True
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    with app.test_client() as client:
        with app.app_context():
            db.create_all()
            yield client
            db.drop_all()


def test_missing_article_returns_404(client):
    """Guarantees invalid or missing article IDs return 404 NOT_FOUND instead of leaking previous video articles."""
    # Create an existing video/article in DB
    v1 = Video(
        youtube_id="dQw4w9WgXcQ",
        youtube_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        title="Video 1",
        status="done",
        original_language="en"
    )
    db.session.add(v1)
    db.session.commit()
    a1 = Article(video_id=v1.id, language="en", title="Video 1 Article", content="IMPORTANT CONTENT\n\nContent 1", is_original=True)
    db.session.add(a1)
    db.session.commit()

    # Requesting an invalid non-existent ID must return 404, NOT Video 1's article!
    response = client.get("/api/articles/99999")
    assert response.status_code == 404
    data = response.get_json()
    assert data["success"] is False
    assert data["error"]["code"] == "NOT_FOUND"


def test_job_isolation_between_requests(client):
    """Guarantees Job A and Job B generate unique job_ids and distinct results."""
    job_a = create_video_job("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ")
    job_b = create_video_job("https://www.youtube.com/watch?v=L_LUpnjgPso", "L_LUpnjgPso")

    assert job_a != job_b

    set_job_result(job_a, {"video_id": 1, "youtube_id": "dQw4w9WgXcQ", "title": "Video A"})
    set_job_result(job_b, {"video_id": 2, "youtube_id": "L_LUpnjgPso", "title": "Video B"})

    state_a = get_job_state(job_a)
    state_b = get_job_state(job_b)

    assert state_a["result"]["youtube_id"] == "dQw4w9WgXcQ"
    assert state_b["result"]["youtube_id"] == "L_LUpnjgPso"


def test_rapid_a_b_c_job_creation(client):
    """Guarantees process(A), process(B), process(C) generate 3 distinct job_ids."""
    job_a = create_video_job("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ")
    job_b = create_video_job("https://www.youtube.com/watch?v=L_LUpnjgPso", "L_LUpnjgPso")
    job_c = create_video_job("https://www.youtube.com/watch?v=3JZ_D3ELwOQ", "3JZ_D3ELwOQ")

    assert len({job_a, job_b, job_c}) == 3

    # Resolve B after C
    set_job_result(job_c, {"video_id": 3, "youtube_id": "3JZ_D3ELwOQ", "title": "Video C"})
    set_job_result(job_b, {"video_id": 2, "youtube_id": "L_LUpnjgPso", "title": "Video B"})

    # State for job C must remain Video C
    state_c = get_job_state(job_c)
    assert state_c["result"]["title"] == "Video C"


def test_translate_non_existent_article_returns_404(client):
    """Guarantees translating a missing article ID returns 404 and does NOT leak previous video articles."""
    v1 = Video(youtube_id="dQw4w9WgXcQ", youtube_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ", title="Video 1", status="done", original_language="en")
    db.session.add(v1)
    db.session.commit()
    a1 = Article(video_id=v1.id, language="en", title="Video 1 Article", content="IMPORTANT CONTENT\n\nContent 1", is_original=True)
    db.session.add(a1)
    db.session.commit()

    response = client.post("/api/articles/99999/translate", json={"language": "ta"})
    assert response.status_code == 404
    data = response.get_json()
    assert data["success"] is False
    assert data["error"]["code"] == "NOT_FOUND"


def test_audio_non_existent_article_returns_404(client):
    """Guarantees requesting audio for a missing article ID returns 404."""
    v1 = Video(youtube_id="dQw4w9WgXcQ", youtube_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ", title="Video 1", status="done", original_language="en")
    db.session.add(v1)
    db.session.commit()

    response = client.post("/api/articles/99999/audio", json={"language": "ta"})
    assert response.status_code == 404
    data = response.get_json()
    assert data["success"] is False
    assert data["error"]["code"] == "NOT_FOUND"

