import pytest
from unittest.mock import patch, MagicMock
from app import create_app, db
from app.services.transcript_service import get_transcript, fetch_transcript, extract_video_id, TranscriptError
from app.services.whisper_service import WhisperError


@pytest.fixture
def client():
    app = create_app()
    app.config["TESTING"] = True
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    with app.test_client() as client:
        with app.app_context():
            db.create_all()
            yield client
            db.session.remove()
            db.drop_all()


def test_1_public_video_transcript_success():
    """1. Public video transcript success."""
    with patch("app.services.transcript_service.fetch_transcript") as mock_fetch:
        mock_fetch.return_value = ("This is a clean public video transcript for testing.", "en")
        cleaned, lang, source = get_transcript("dQw4w9WgXcQ")
        assert source == "captions"
        assert lang == "en"
        assert "public video transcript" in cleaned


def test_2_transcript_unavailable_whisper_fallback_succeeds():
    """2. Transcript unavailable -> Whisper fallback succeeds."""
    with patch("app.services.transcript_service.fetch_transcript") as mock_fetch, \
         patch("app.services.whisper_service.transcribe_with_whisper") as mock_whisper:
        mock_fetch.side_effect = TranscriptError("TRANSCRIPT_UNAVAILABLE", "No transcript was available.")
        mock_whisper.return_value = ("Speech to text transcribed via Whisper model.", "en")

        cleaned, lang, source = get_transcript("dQw4w9WgXcQ")
        assert source == "whisper"
        assert lang == "en"
        assert "Whisper model" in cleaned


def test_3_generic_exception_not_falsely_labeled_video_private():
    """3. Transcript API throws a generic exception -> verify it is NOT falsely labeled VIDEO_PRIVATE."""
    with patch("app.services.transcript_service.YouTubeTranscriptApi") as mock_ytt, \
         patch("app.services.whisper_service.transcribe_with_whisper") as mock_whisper:
        mock_ytt.list_transcripts.side_effect = Exception("Generic unexpected HTTP connection reset")
        mock_whisper.side_effect = WhisperError("WHISPER_TRANSCRIPTION_FAILED", "Audio was obtained, but speech transcription failed.")

        with pytest.raises(TranscriptError) as exc_info:
            get_transcript("dQw4w9WgXcQ")

        assert exc_info.value.code != "VIDEO_PRIVATE"
        assert exc_info.value.code != "VIDEO_PRIVATE_OR_RESTRICTED"
        assert exc_info.value.code in ["TRANSCRIPT_UNAVAILABLE", "WHISPER_TRANSCRIPTION_FAILED"]


def test_4_private_video_correct_error():
    """4. Private video -> correct VIDEO_PRIVATE error."""
    with patch("app.services.transcript_service.fetch_transcript") as mock_fetch, \
         patch("app.services.whisper_service.transcribe_with_whisper") as mock_whisper:
        mock_fetch.side_effect = TranscriptError("VIDEO_PRIVATE", "This video is private and cannot be processed.")

        with pytest.raises(TranscriptError) as exc_info:
            get_transcript("private_id_123")

        assert exc_info.value.code == "VIDEO_PRIVATE"
        assert exc_info.value.message == "This video is private and cannot be processed."
        # Verify fallback was NOT called for private video
        mock_whisper.assert_not_called()


def test_5_audio_extraction_fails_error():
    """5. Audio extraction fails -> user-safe clean TRANSCRIPT_UNAVAILABLE error."""
    with patch("app.services.transcript_service.fetch_transcript") as mock_fetch, \
         patch("app.services.whisper_service.transcribe_with_whisper") as mock_whisper:
        mock_fetch.side_effect = TranscriptError("TRANSCRIPT_UNAVAILABLE", "No transcript was available.")
        mock_whisper.side_effect = WhisperError("AUDIO_EXTRACTION_FAILED", "The video's audio could not be extracted.")

        with pytest.raises(TranscriptError) as exc_info:
            get_transcript("dQw4w9WgXcQ")

        assert exc_info.value.code in ["TRANSCRIPT_UNAVAILABLE", "AUDIO_EXTRACTION_FAILED"]
        assert "Unable to retrieve a transcript" in exc_info.value.message or "audio" in exc_info.value.message


def test_6_whisper_fails_error():
    """6. Whisper fails -> user-safe clean TRANSCRIPT_UNAVAILABLE error."""
    with patch("app.services.transcript_service.fetch_transcript") as mock_fetch, \
         patch("app.services.whisper_service.transcribe_with_whisper") as mock_whisper:
        mock_fetch.side_effect = TranscriptError("TRANSCRIPT_UNAVAILABLE", "No transcript was available.")
        mock_whisper.side_effect = WhisperError("WHISPER_TRANSCRIPTION_FAILED", "Audio was obtained, but speech transcription failed.")

        with pytest.raises(TranscriptError) as exc_info:
            get_transcript("dQw4w9WgXcQ")

        assert exc_info.value.code in ["TRANSCRIPT_UNAVAILABLE", "WHISPER_TRANSCRIPTION_FAILED"]
        assert "Unable to retrieve a transcript" in exc_info.value.message or "speech" in exc_info.value.message


def test_7_verify_fallback_is_called_after_transcript_failure():
    """7. Verify fallback is actually called after transcript failure."""
    fallback_called = []
    whisper_called = []

    def on_audio():
        fallback_called.append(True)

    def on_whisper():
        whisper_called.append(True)

    with patch("app.services.transcript_service.fetch_transcript") as mock_fetch, \
         patch("app.services.whisper_service.transcribe_with_whisper") as mock_whisper:
        mock_fetch.side_effect = TranscriptError("TRANSCRIPT_UNAVAILABLE", "No transcript available.")
        mock_whisper.return_value = ("Fallback text successfully transcribed.", "en")

        cleaned, lang, source = get_transcript(
            "dQw4w9WgXcQ",
            on_audio_fallback=on_audio,
            on_whisper_transcribe=on_whisper
        )

        assert len(fallback_called) == 1
        assert len(whisper_called) == 1
        assert source == "whisper"


def test_8_backend_returns_real_error_code_and_message(client):
    def inline_submit(func, app, job_id, url, video_id, user_id):
        func(app, job_id, url, video_id, user_id)

    with patch("app.routes.youtube.extract_video_id") as mock_extract, \
         patch("app.routes.youtube.get_transcript") as mock_get_trans, \
         patch("app.routes.youtube.submit_video_processing_task", side_effect=inline_submit):
        mock_extract.return_value = "fresh_err_vid_8"
        mock_get_trans.side_effect = TranscriptError("AUDIO_EXTRACTION_FAILED", "The video's audio could not be extracted.")

        # Call process_video synchronous endpoint
        res = client.post("/api/videos/process", json={"url": "https://www.youtube.com/watch?v=fresh_err_vid_8"})
        data = res.get_json()

        assert res.status_code == 422
        assert data["success"] is False
        assert data["error"]["code"] == "AUDIO_EXTRACTION_FAILED"
        assert data["error"]["message"] == "The video's audio could not be extracted."


def test_9_retry_fresh_request_behavior(client):
    """9. Verify Retry capability and status responses."""
    def inline_submit(func, app, job_id, url, video_id, user_id):
        func(app, job_id, url, video_id, user_id)

    with patch("app.routes.youtube.extract_video_id") as mock_extract, \
         patch("app.routes.youtube.get_transcript") as mock_get_trans, \
         patch("app.routes.youtube.submit_video_processing_task", side_effect=inline_submit):
        mock_extract.return_value = "fresh_err_vid_9"
        mock_get_trans.side_effect = TranscriptError("AUDIO_EXTRACTION_FAILED", "The video's audio could not be extracted.")

        res1 = client.post("/api/videos/process", json={"url": "https://www.youtube.com/watch?v=fresh_err_vid_9"})
        data1 = res1.get_json()
        assert data1["error"]["retryable"] is True

        # Now mock success for retry attempt
        mock_get_trans.side_effect = None
        mock_get_trans.return_value = ("Clean transcript content on retry.", "en", "captions")

        with patch("app.services.summarizer_service.rank_important_sentences", return_value="Clean transcript content on retry."), \
             patch("app.routes.youtube.get_llm_provider") as mock_llm:
            mock_provider = MagicMock()
            mock_provider.generate_article.return_value = {"title": "Test Title", "important_content": ["Fact 1"]}
            mock_llm.return_value = mock_provider

            res2 = client.post("/api/videos/process", json={"url": "https://www.youtube.com/watch?v=fresh_err_vid_9"})
            data2 = res2.get_json()
            assert data2["success"] is True
            assert "data" in data2


def test_10_whisper_timeout_error_response(client):
    """10. Verify WHISPER_TIMEOUT error code and message format via background job polling."""
    def inline_submit(func, app, job_id, url, video_id, user_id):
        func(app, job_id, url, video_id, user_id)

    with patch("app.routes.youtube.extract_video_id") as mock_extract, \
         patch("app.routes.youtube.get_transcript") as mock_get_trans, \
         patch("app.routes.youtube.submit_video_processing_task", side_effect=inline_submit):
        mock_extract.return_value = "dQw4w9WgXcQ"
        mock_get_trans.side_effect = TranscriptError("WHISPER_TIMEOUT", "Speech-to-text processing took too long. Please try again.")

        # Submit async job
        res = client.post("/api/jobs/process", json={"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"})
        data = res.get_json()
        assert res.status_code == 200
        assert data["success"] is True
        job_id = data["data"]["job_id"]

        # Check job status via polling
        res_status = client.get(f"/api/jobs/{job_id}")
        status_data = res_status.get_json()
        assert res_status.status_code == 200
        assert status_data["data"]["status"] == "failed"
        assert status_data["data"]["error"]["code"] == "WHISPER_TIMEOUT"
        assert "took too long" in status_data["data"]["error"]["message"]


def test_11_granular_progress_callbacks():
    """11. Verify progress callback fires with smooth progress percentages."""
    progress_records = []

    def on_progress(p, msg):
        progress_records.append((p, msg))

    with patch("app.services.transcript_service.fetch_transcript") as mock_fetch, \
         patch("app.services.whisper_service.transcribe_with_whisper") as mock_whisper:
        mock_fetch.side_effect = TranscriptError("TRANSCRIPT_UNAVAILABLE", "No transcript available.")
        mock_whisper.side_effect = lambda vid, *args, **kwargs: (
            kwargs.get("on_progress")(50, "Whisper model loading") if kwargs.get("on_progress") else None,
            kwargs.get("on_progress")(60, "Transcription started") if kwargs.get("on_progress") else None,
            kwargs.get("on_progress")(85, "Transcript completed") if kwargs.get("on_progress") else None,
            ("Transcribed text", "en")
        )[-1]

        cleaned, lang, source = get_transcript("dQw4w9WgXcQ", on_progress=on_progress)
        assert source == "whisper"
        assert len(progress_records) >= 3
        percentages = [p[0] for p in progress_records]
        assert 50 in percentages
        assert 60 in percentages
        assert 85 in percentages
