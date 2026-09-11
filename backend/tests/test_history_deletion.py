import pytest
from app import db
from app.models.models import Video, Article, Audio, TranslationCache


def test_delete_article_with_translation_cache_rows(client):
    """Test deleting a video/article that has dependent TranslationCache rows."""
    v = Video(youtube_id="vid_test_01", youtube_url="https://youtube.com/watch?v=vid_test_01", title="Video 1", status="done")
    db.session.add(v)
    db.session.commit()

    art = Article(video_id=v.id, language="en", title="Article 1", content="Content 1", is_original=True)
    db.session.add(art)
    db.session.commit()

    # Add translation cache entries referencing art.id
    t1 = TranslationCache(article_id=art.id, target_language="ar", title="محتوى", content="مضمون 1")
    t2 = TranslationCache(article_id=art.id, target_language="ta", title="தலைப்பு", content="உள்ளடக்கம் 1")
    aud = Audio(article_id=art.id, language="ta", file_path="fake_audio_1.mp3")
    db.session.add_all([t1, t2, aud])
    db.session.commit()

    assert TranslationCache.query.filter_by(article_id=art.id).count() == 2
    assert Audio.query.filter_by(article_id=art.id).count() == 1

    # Delete History Item (DELETE /history/<video_id>)
    res = client.delete(f"/api/history/{v.id}")
    assert res.status_code == 200
    assert res.json["success"] is True

    # Verify dependent TranslationCache, Audio, Article, and Video records are deleted cleanly without FK error
    assert db.session.get(Video, v.id) is None
    assert db.session.get(Article, art.id) is None
    assert TranslationCache.query.filter_by(article_id=art.id).count() == 0
    assert Audio.query.filter_by(article_id=art.id).count() == 0


def test_delete_article_without_translation_cache_rows(client):
    """Test deleting a video/article with no dependent translation cache rows."""
    v = Video(youtube_id="vid_test_02", youtube_url="https://youtube.com/watch?v=vid_test_02", title="Video 2", status="done")
    db.session.add(v)
    db.session.commit()

    art = Article(video_id=v.id, language="en", title="Article 2", content="Content 2", is_original=True)
    db.session.add(art)
    db.session.commit()

    res = client.delete(f"/api/history/{v.id}")
    assert res.status_code == 200
    assert res.json["success"] is True
    assert db.session.get(Video, v.id) is None


def test_delete_multiple_history_items_and_isolation(client):
    """Test deleting one item does not affect other videos/articles, translation caches, or audio."""
    # Video A
    v_a = Video(youtube_id="vid_a", youtube_url="https://youtube.com/watch?v=vid_a", title="Video A", status="done")
    db.session.add(v_a)
    db.session.commit()
    art_a = Article(video_id=v_a.id, language="en", title="Article A", content="Content A", is_original=True)
    db.session.add(art_a)
    db.session.commit()
    t_a = TranslationCache(article_id=art_a.id, target_language="es", title="Titulo A", content="Contenido A")
    aud_a = Audio(article_id=art_a.id, language="es", file_path="audio_a.mp3")
    db.session.add_all([t_a, aud_a])

    # Video B
    v_b = Video(youtube_id="vid_b", youtube_url="https://youtube.com/watch?v=vid_b", title="Video B", status="done")
    db.session.add(v_b)
    db.session.commit()
    art_b = Article(video_id=v_b.id, language="en", title="Article B", content="Content B", is_original=True)
    db.session.add(art_b)
    db.session.commit()
    t_b = TranslationCache(article_id=art_b.id, target_language="fr", title="Titre B", content="Contenu B")
    aud_b = Audio(article_id=art_b.id, language="fr", file_path="audio_b.mp3")
    db.session.add_all([t_b, aud_b])
    db.session.commit()

    # Delete Video A only
    res = client.delete(f"/api/history/{v_a.id}")
    assert res.status_code == 200

    # Video A records gone
    assert db.session.get(Video, v_a.id) is None
    assert TranslationCache.query.filter_by(article_id=art_a.id).count() == 0
    assert Audio.query.filter_by(article_id=art_a.id).count() == 0

    # Video B records completely intact
    assert db.session.get(Video, v_b.id) is not None
    assert db.session.get(Article, art_b.id) is not None
    assert TranslationCache.query.filter_by(article_id=art_b.id).count() == 1
    assert Audio.query.filter_by(article_id=art_b.id).count() == 1


def test_clear_all_history_safely(client):
    """Test Clear All history functionality cleans all items safely."""
    for i in range(3):
        v = Video(youtube_id=f"vid_{i}", youtube_url=f"https://youtube.com/watch?v=vid_{i}", title=f"Video {i}", status="done")
        db.session.add(v)
        db.session.commit()
        art = Article(video_id=v.id, language="en", title=f"Article {i}", content=f"Content {i}")
        db.session.add(art)
        db.session.commit()
        tc = TranslationCache(article_id=art.id, target_language="de", title=f"Titel {i}", content=f"Inhalt {i}")
        aud = Audio(article_id=art.id, language="de", file_path=f"audio_{i}.mp3")
        db.session.add_all([tc, aud])
        db.session.commit()

    assert Video.query.count() == 3
    assert Article.query.count() == 3
    assert TranslationCache.query.count() == 3
    assert Audio.query.count() == 3

    res = client.delete("/api/history/clear_all")
    assert res.status_code == 200
    assert res.json["success"] is True

    assert Video.query.count() == 0
    assert Article.query.count() == 0
    assert TranslationCache.query.count() == 0
    assert Audio.query.count() == 0
