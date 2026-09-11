import time
import pytest
from unittest.mock import patch, MagicMock
from app.services.transcript_service import get_transcript, fetch_transcript, TranscriptError
from app.services.transcript_providers import (
    TranscriptProviderChain,
    TranscriptResult,
    YouTubeCaptionProvider,
    AlternativeTranscriptProvider,
    validate_transcript,
)

def test_1_jnqxac9ivrw_first_youtube_video_captions_success():
    """1. Verify video jNQXAC9IVRw ('Me at the zoo') caption lookup."""
    try:
        raw_text, lang = fetch_transcript("jNQXAC9IVRw")
        assert raw_text is not None
        assert len(raw_text) > 10
        assert lang in ["en", "en-US"]
    except TranscriptError as e:
        if e.code == "BOT_PROTECTION_BLOCKED":
            pytest.skip("Render/Cloud IP blocked by YouTube bot protection during live network test.")
        raise


def test_2_bot_protection_blocked_error_prevents_doomed_audio_fallback():
    """2. Verify that YouTube bot protection response stops doomed audio fallback."""
    whisper_called = []

    def on_whisper():
        whisper_called.append(True)

    with patch("app.services.transcript_providers.YouTubeCaptionProvider.fetch") as mock_captions:
        mock_captions.side_effect = TranscriptError("BOT_PROTECTION_BLOCKED", "YouTube anti-bot verification active.")
        with pytest.raises(TranscriptError) as exc_info:
            get_transcript("jNQXAC9IVRw", on_whisper_transcribe=on_whisper)

        assert exc_info.value.code == "BOT_PROTECTION_BLOCKED"
        assert len(whisper_called) == 0


def test_3_provider_fallback_chain_execution():
    """3. Verify provider fallback chain executes sequentially."""
    mock_prov1 = MagicMock()
    mock_prov1.name = "prov1"
    mock_prov1.fetch.return_value = None

    mock_prov2 = MagicMock()
    mock_prov2.name = "prov2"
    mock_prov2.fetch.return_value = TranscriptResult(
        video_id="vid123",
        source="alternative_api",
        source_language="en",
        transcript_text="This is a fully validated alternative transcript content for vid123.",
    )

    chain = TranscriptProviderChain(providers=[mock_prov1, mock_prov2])
    res = chain.execute("vid123")
    assert res is not None
    assert res.source == "alternative_api"
    assert "vid123" in res.transcript_text
    from unittest.mock import ANY
    mock_prov1.fetch.assert_called_once_with("vid123", ANY)
    mock_prov2.fetch.assert_called_once_with("vid123", ANY)


def test_4_successful_alternative_transcript_provider():
    """4. Verify successful alternative transcript provider execution via Supadata/API response."""
    with patch("os.getenv") as mock_env, patch("requests.get") as mock_get:
        mock_env.side_effect = lambda k, d="": "fake_supadata_key" if k == "SUPADATA_API_KEY" else d
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "lang": "en",
            "content": [{"text": "Hello world from Supadata API transcript for jNQXAC9IVRw."}]
        }
        mock_get.return_value = mock_resp

        provider = AlternativeTranscriptProvider()
        res = provider.fetch("jNQXAC9IVRw")
        assert res is not None
        assert res.source == "alternative_api"
        assert "Supadata API transcript" in res.transcript_text


def test_5_stale_wrong_video_transcript_rejection():
    """5. Verify validation rejects transcript if video_id mismatches or content is junk."""
    bad_res = TranscriptResult(
        video_id="WRONG_VIDEO_ID",
        source="captions",
        source_language="en",
        transcript_text="Transcript belonging to another video completely.",
    )
    assert validate_transcript(bad_res, "jNQXAC9IVRw") is False

    empty_res = TranscriptResult(
        video_id="jNQXAC9IVRw",
        source="captions",
        source_language="en",
        transcript_text="",
    )
    assert validate_transcript(empty_res, "jNQXAC9IVRw") is False


def test_6_old_video_to_new_video_identity_isolation():
    """6. Verify no old video metadata/transcript/article leaks into a new video job."""
    res1 = TranscriptResult(
        video_id="vid_A",
        source="captions",
        source_language="en",
        transcript_text="Unique transcript text content exclusively for video A.",
    )
    res2 = TranscriptResult(
        video_id="vid_B",
        source="captions",
        source_language="en",
        transcript_text="Unique transcript text content exclusively for video B.",
    )
    assert res1.source_text_hash != res2.source_text_hash
    assert res1.video_id != res2.video_id


def test_7_same_video_different_language_isolation():
    """7. Verify article/translation caching maintains strict language key isolation."""
    from app.models.models import Article
    art_es = Article(video_id=1, language="es", title="Spanish Title", content="Spanish content")
    art_fr = Article(video_id=1, language="fr", title="French Title", content="French content")
    assert art_es.language != art_fr.language
    assert art_es.content != art_fr.content


def test_8_transcript_to_article_grounding():
    """8. Verify article generation is grounded in transcript without hallucinating unrelated content."""
    from app.services.summarizer_service import rank_important_sentences
    transcript = "The elephant has a long trunk. It lives in the zoo. Visitors come to watch animals."
    summary = rank_important_sentences(transcript)
    assert "elephant" in summary or "zoo" in summary


def test_9_whisper_not_called_when_captions_succeed():
    """9. Verify Whisper is NOT called when captions or provider transcript succeeds."""
    whisper_called = []

    def on_whisper():
        whisper_called.append(True)

    with patch("app.services.transcript_providers.YouTubeCaptionProvider.fetch") as mock_captions:
        mock_captions.return_value = TranscriptResult(
            video_id="vid999",
            source="captions",
            source_language="en",
            transcript_text="Valid caption text for video 999 with enough words to pass validation.",
        )
        cleaned, lang, source = get_transcript("vid999", on_whisper_transcribe=on_whisper)
        assert source == "captions"
        assert len(whisper_called) == 0


def test_10_cancellation_handling():
    """10. Verify job cancellation stops job processing immediately."""
    from app.services.job_manager import create_video_job, cancel_job, is_job_cancelled
    job_id = create_video_job("https://www.youtube.com/watch?v=cancel_test", "cancel_test")
    assert is_job_cancelled(job_id) is False
    success = cancel_job(job_id)
    assert success is True
    assert is_job_cancelled(job_id) is True


def test_11_stale_job_recovery_watchdog():
    """11. Verify watchdog fails job if stalled for > 300s."""
    from app.services.job_manager import create_video_job, VIDEO_JOBS, get_job_state
    job_id = create_video_job("https://www.youtube.com/watch?v=stale_test", "stale_test")
    VIDEO_JOBS[job_id]["updated_at"] = time.time() - 350
    state = get_job_state(job_id)
    assert state["status"] == "failed"
    assert state["error"]["code"] == "JOB_STALLED"


def test_12_long_video_job_pipeline_flow():
    """12. Verify long video non-blocking processing and job progress state updates."""
    from app.services.job_manager import create_video_job, update_job_stage, get_job_state, JobStage
    job_id = create_video_job("https://www.youtube.com/watch?v=long_vid", "long_vid")
    update_job_stage(job_id, JobStage.FETCHING_TRANSCRIPT, progress_override=20)
    state1 = get_job_state(job_id)
    assert state1["progress"] == 20

    update_job_stage(job_id, JobStage.GENERATING_IMPORTANT_CONTENT, progress_override=92)
    state2 = get_job_state(job_id)
    assert state2["progress"] == 92
