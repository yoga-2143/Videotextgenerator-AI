import React, { useState, useEffect, useRef } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { api } from '../api'
import { saveLocalHistoryItem } from '../utils/localHistory'

export default function YoutubeUrl() {
  const navigate = useNavigate()
  const location = useLocation()

  const initialUrl = location.state?.url || ''
  const initialAutoSubmit = !!(location.state?.autoSubmit && initialUrl)
  const initialJobId = location.state?.jobId || null
  const initialJobState = location.state?.initialJobState

  // State
  const [url, setUrl] = useState(initialUrl)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(() => initialAutoSubmit || !!initialJobId)
  const [currentJob, setCurrentJob] = useState(initialJobState || (initialJobId ? { job_id: initialJobId, status: 'queued', progress: 5 } : null))
  const [jobStageMessage, setJobStageMessage] = useState(initialJobState?.message || 'Checking transcript...')
  const [jobProgress, setJobProgress] = useState(initialJobState?.progress || 5)
  const [elapsedSeconds, setElapsedSeconds] = useState(0)
  const [transcriptText, setTranscriptText] = useState('')
  const [videoTitle, setVideoTitle] = useState('')

  const pollingRef = useRef(null)
  const timerRef = useRef(null)
  const activeJobIdRef = useRef(initialJobId)
  const currentJobUrlRef = useRef(initialUrl)
  const hasAutoSubmittedRef = useRef(false)

  function startTimer() {
    setElapsedSeconds(0)
    if (timerRef.current) clearInterval(timerRef.current)
    timerRef.current = setInterval(() => {
      setElapsedSeconds((prev) => prev + 1)
    }, 1000)
  }

  function stopTimer() {
    if (timerRef.current) {
      clearInterval(timerRef.current)
      timerRef.current = null
    }
  }

  function startPolling(jobId, jobUrl) {
    if (pollingRef.current) clearInterval(pollingRef.current)

    const boundUrl = jobUrl || currentJobUrlRef.current || url

    pollingRef.current = setInterval(async () => {
      try {
        const jobState = await api.getJobStatus(jobId)
        if (!jobState) return

        // Identity guard: ignore response if active job has changed
        if (activeJobIdRef.current !== jobId) return
        if (jobState.job_id && jobState.job_id !== jobId) return

        setCurrentJob(jobState)
        setJobStageMessage(jobState.message || 'Processing video...')
        setJobProgress(jobState.progress || 10)

        // Capture video title if available
        const title = jobState.video_title || jobState.title || jobState.extra_data?.video_title
        if (title) setVideoTitle(title)

        // Capture transcript text preview
        const transcriptObj = jobState.transcript || jobState.extra_data?.transcript
        if (transcriptObj && transcriptObj.text) {
          setTranscriptText(transcriptObj.text)
        }

        if (jobState.status === 'completed' && jobState.result) {
          clearInterval(pollingRef.current)
          pollingRef.current = null
          stopTimer()
          setLoading(false)

          const data = jobState.result
          saveLocalHistoryItem(data)
          const targetId = data?.article?.id || data?.video_id
          if (targetId) {
            navigate(`/article/${targetId}`, { state: { video: data, url: boundUrl } })
          } else {
            setError('Video processed, but article ID was not returned. Please check History.')
          }
        } else if (jobState.status === 'failed') {
          clearInterval(pollingRef.current)
          pollingRef.current = null
          stopTimer()
          setLoading(false)
          setError(jobState.error?.message || jobState.message || 'Unable to retrieve a transcript for this video right now. Please try again later.')
        }
      } catch (err) {
        // Silent retry on polling error
      }
    }, 1500)
  }

  async function startJobSubmission(targetUrl) {
    const trimmed = (targetUrl || url).trim()
    if (!trimmed || trimmed.includes('...') || trimmed === 'https://www.youtube.com/watch?v=') {
      setError('Please enter a complete YouTube URL (e.g. https://www.youtube.com/watch?v=dQw4w9WgXcQ).')
      setLoading(false)
      return
    }

    setError('')
    setUrl(trimmed)
    currentJobUrlRef.current = trimmed
    setTranscriptText('')
    setVideoTitle('')
    setJobStageMessage('Checking transcript...')
    setJobProgress(5)
    setLoading(true)
    startTimer()

    // Invalidate any previous job immediately
    if (pollingRef.current) {
      clearInterval(pollingRef.current)
      pollingRef.current = null
    }
    activeJobIdRef.current = null
    setCurrentJob(null)

    try {
      const res = await api.submitVideoJob(trimmed)
      if (res && res.job_id) {
        activeJobIdRef.current = res.job_id
        setCurrentJob({ job_id: res.job_id, status: 'queued', progress: 5 })
        startPolling(res.job_id, trimmed)
      } else if (res && (res.article || res.video_id)) {
        stopTimer()
        saveLocalHistoryItem(res)
        const targetId = res.article?.id || res.video_id || res.id
        navigate(`/article/${targetId}`, { state: { video: res, url: trimmed } })
      } else {
        stopTimer()
        setError('Failed to initiate processing job.')
        setLoading(false)
      }
    } catch (err) {
      stopTimer()
      setError(err.message || 'Unable to retrieve a transcript for this video right now. Please try again later.')
      setLoading(false)
    }
  }

  // Mounting effect to handle autoSubmit or initialJobId
  useEffect(() => {
    if (initialJobId) {
      activeJobIdRef.current = initialJobId
      startTimer()
      startPolling(initialJobId, initialUrl)
    } else if (initialAutoSubmit && !hasAutoSubmittedRef.current) {
      hasAutoSubmittedRef.current = true
      startJobSubmission(initialUrl)
    }

    return () => {
      if (pollingRef.current) clearInterval(pollingRef.current)
      if (timerRef.current) clearInterval(timerRef.current)
    }
  }, [initialJobId, initialAutoSubmit, initialUrl])

  function handleSubmit(e) {
    if (e && e.preventDefault) e.preventDefault()
    startJobSubmission(url)
  }

  async function handleCancel() {
    if (pollingRef.current) {
      clearInterval(pollingRef.current)
      pollingRef.current = null
    }
    stopTimer()
    const jobToCancel = currentJob?.job_id
    activeJobIdRef.current = null
    if (jobToCancel) {
      try {
        await api.cancelJob(jobToCancel)
      } catch (err) {}
    }
    setLoading(false)
    setCurrentJob(null)
    setJobStageMessage('')
    setJobProgress(0)
    setTranscriptText('')
  }

  return (
    <main className="mx-auto max-w-4xl px-4 sm:px-6 py-8 sm:py-16">
      <div className="text-center mb-8 sm:mb-12">
        <span className="font-mono text-xs sm:text-base font-bold uppercase tracking-[0.15em] sm:tracking-[0.2em] text-wave">
          YouTube Processor
        </span>
        <h1 className="mt-2 sm:mt-3 font-display page-title font-bold text-paper">
          {loading ? 'Processing Video...' : 'Enter YouTube Video URL'}
        </h1>
        <p className="mt-3 sm:mt-4 text-sm sm:text-lg text-mute max-w-xl mx-auto leading-relaxed">
          {loading
            ? 'Extracting transcript and generating article content in the background.'
            : 'Paste any public YouTube link to extract clean transcript data, rank important facts, and generate articles automatically.'}
        </p>
      </div>

      <div className="rounded-2xl sm:rounded-3xl border border-line bg-panel p-5 sm:p-8 shadow-2xl mb-8">
        {/* Dedicated Processing Screen UI */}
        {loading && (
          <div>
            {/* YOUTUBE VIDEO URL Header Banner */}
            <div className="mb-6 rounded-2xl border border-line bg-ink p-4 sm:p-5 text-left shadow-md">
              <span className="font-mono text-xs font-bold uppercase tracking-wider text-wave block mb-1">
                YOUTUBE VIDEO URL
              </span>
              <a
                href={url || currentJobUrlRef.current}
                target="_blank"
                rel="noopener noreferrer"
                className="font-mono text-sm sm:text-base font-semibold text-paper hover:text-wave underline break-all break-words max-w-full inline-block"
              >
                {url || currentJobUrlRef.current}
              </a>
            </div>

            {videoTitle && (
              <h2 className="text-lg sm:text-xl font-bold text-paper mb-4 text-left break-words">
                {videoTitle}
              </h2>
            )}

            {/* Stage & Progress Indicator */}
            <div className="mb-6 rounded-2xl border border-wave/40 bg-wave/10 p-5 sm:p-6 text-left">
              <div className="flex items-center justify-between gap-3 mb-3">
                <div className="flex items-center gap-3 font-mono text-sm sm:text-base font-bold uppercase text-wave min-w-0">
                  <div className="h-5 w-5 animate-spin rounded-full border-2 border-wave border-t-transparent shrink-0" />
                  <span className="truncate">{jobStageMessage || 'Checking transcript...'}</span>
                </div>
                <span className="font-mono text-base sm:text-lg font-extrabold text-wave shrink-0">
                  {jobProgress}%
                </span>
              </div>

              {/* Progress Bar */}
              <div className="w-full h-3 bg-ink rounded-full overflow-hidden border border-line mb-4">
                <div
                  className="h-full bg-wave transition-all duration-300 ease-out"
                  style={{ width: `${Math.min(Math.max(jobProgress, 5), 100)}%` }}
                />
              </div>

              <div className="flex flex-wrap items-center justify-between gap-2 text-xs font-mono text-mute">
                <span>Processing active ({elapsedSeconds}s)</span>
                <button
                  type="button"
                  onClick={handleCancel}
                  className="text-signal hover:underline font-bold cursor-pointer min-h-[36px] flex items-center"
                >
                  Cancel Request
                </button>
              </div>
            </div>

            {/* Transcript-First Display */}
            {transcriptText && (
              <div className="mb-6 rounded-2xl border border-line bg-ink p-5 text-left">
                <div className="flex items-center justify-between mb-3 border-b border-line pb-2">
                  <span className="font-mono text-xs font-bold uppercase text-wave tracking-wider flex items-center gap-2">
                    <svg className="w-4 h-4 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7" />
                    </svg>
                    Transcript Ready (Generating Article...)
                  </span>
                  <span className="font-mono text-xs text-mute">{transcriptText.split(' ').length} words</span>
                </div>
                <p className="text-xs sm:text-sm text-paper/80 leading-relaxed max-h-48 overflow-y-auto pr-2 font-mono">
                  {transcriptText}
                </p>
              </div>
            )}

            {/* YouTube Access Guide Card on Processing Screen */}
            <div className="text-left bg-black/30 border border-line/60 rounded-2xl p-4 sm:p-5">
              <h3 className="font-mono text-xs font-bold uppercase tracking-wider text-wave mb-3 flex items-center gap-2">
                <svg className="w-4 h-4 text-wave shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                YOUTUBE VIDEO ACCESS GUIDE
              </h3>
              <ul className="space-y-2.5 font-medium text-xs sm:text-sm text-paper/95 leading-relaxed">
                <li className="flex items-start gap-2.5 min-w-0">
                  <span className="shrink-0 text-base select-none">🔴</span>
                  <span className="min-w-0 break-words">
                    <strong className="text-paper font-semibold">Private:</strong> We cannot process it because permission is required.
                  </span>
                </li>
                <li className="flex items-start gap-2.5 min-w-0">
                  <span className="shrink-0 text-base select-none">🟡</span>
                  <span className="min-w-0 break-words">
                    <strong className="text-paper font-semibold">Unlisted:</strong> We can process it using the link if captions/transcript are available.
                  </span>
                </li>
                <li className="flex items-start gap-2.5 min-w-0">
                  <span className="shrink-0 text-base select-none">🟢</span>
                  <span className="min-w-0 break-words">
                    <strong className="text-paper font-semibold">Public:</strong> We can normally process it.
                  </span>
                </li>
                <li className="flex items-start gap-2.5 min-w-0">
                  <span className="shrink-0 text-base select-none">⚠️</span>
                  <span className="min-w-0 break-words">
                    <strong className="text-paper font-semibold">Age-restricted / Region-restricted / Members-only:</strong> It may not work because of access restrictions.
                  </span>
                </li>
              </ul>
            </div>
          </div>
        )}

        {/* Error Display on Processing Screen (Requirement 9) */}
        {error && !loading && (
          <div className="rounded-2xl border border-rose-500/30 bg-rose-500/10 p-5 text-left text-paper">
            <div className="flex items-center gap-2 mb-2 font-bold text-rose-400 font-mono text-xs sm:text-sm uppercase tracking-wider">
              <svg className="w-5 h-5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              Processing Notice
            </div>
            <p className="text-sm sm:text-base leading-relaxed text-paper/90 font-medium mb-4">{error}</p>
            <div className="flex flex-wrap items-center gap-3">
              <button
                type="button"
                onClick={() => startJobSubmission(url || currentJobUrlRef.current)}
                className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-rose-500 text-white font-bold text-xs sm:text-sm hover:bg-rose-600 transition-colors cursor-pointer min-h-[44px]"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                </svg>
                Try Again
              </button>
              <button
                type="button"
                onClick={() => {
                  setError('')
                  setLoading(false)
                }}
                className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl border border-line bg-panel text-paper font-bold text-xs sm:text-sm hover:bg-line/40 transition-colors cursor-pointer min-h-[44px]"
              >
                Enter Different URL
              </button>
            </div>
          </div>
        )}

        {/* URL Input Form (Visible when not processing and no error) */}
        {!loading && !error && (
          <form onSubmit={handleSubmit}>
            <label htmlFor="yt-input" className="block text-xs sm:text-sm font-mono font-bold uppercase tracking-wider text-paper mb-2.5 sm:mb-3">
              YOUTUBE VIDEO URL
            </label>
            <input
              id="yt-input"
              type="text"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://www.youtube.com/watch?v=..."
              disabled={loading}
              className="w-full rounded-xl sm:rounded-2xl border border-line bg-ink px-4 sm:px-5 py-3.5 sm:py-4 text-base sm:text-xl text-paper placeholder:text-mute focus:border-wave focus:outline-none mb-5 sm:mb-6 font-mono break-all disabled:opacity-60"
            />
            <button
              type="submit"
              disabled={loading}
              className="w-full inline-flex items-center justify-center gap-3 rounded-xl sm:rounded-2xl bg-signal py-3.5 sm:py-4 text-base sm:text-lg font-bold text-ink transition-transform hover:scale-[1.01] active:scale-[0.99] disabled:opacity-60 shadow-lg cursor-pointer min-h-[48px]"
            >
              Process YouTube URL
            </button>
          </form>
        )}
      </div>

      {/* Access Guide below input form when idle */}
      {!loading && !error && (
        <div className="w-full text-left bg-panel border border-line rounded-2xl sm:rounded-3xl p-5 sm:p-7 shadow-2xl">
          <h3 className="font-mono text-xs sm:text-sm font-bold uppercase tracking-wider text-wave mb-3 flex items-center gap-2">
            <svg className="w-4 h-4 text-wave shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            YOUTUBE VIDEO ACCESS GUIDE
          </h3>
          <p className="text-xs sm:text-sm font-semibold text-paper/80 mb-4 leading-relaxed">
            YouTube video access depends on the video type:
          </p>
          <ul className="space-y-3.5 font-medium text-xs sm:text-sm text-paper/95 leading-relaxed">
            <li className="flex items-start gap-3 min-w-0">
              <span className="shrink-0 text-base sm:text-lg select-none">🔴</span>
              <span className="min-w-0 break-words">
                <strong className="text-paper font-semibold">Private:</strong> We cannot process it because permission is required.
              </span>
            </li>
            <li className="flex items-start gap-3 min-w-0">
              <span className="shrink-0 text-base sm:text-lg select-none">🟡</span>
              <span className="min-w-0 break-words">
                <strong className="text-paper font-semibold">Unlisted:</strong> We can process it using the link if captions/transcript are available.
              </span>
            </li>
            <li className="flex items-start gap-3 min-w-0">
              <span className="shrink-0 text-base sm:text-lg select-none">🟢</span>
              <span className="min-w-0 break-words">
                <strong className="text-paper font-semibold">Public:</strong> We can normally process it.
              </span>
            </li>
            <li className="flex items-start gap-3 min-w-0">
              <span className="shrink-0 text-base sm:text-lg select-none">⚠️</span>
              <span className="min-w-0 break-words">
                <strong className="text-paper font-semibold">Age-restricted / Region-restricted / Members-only:</strong> It may not work because of access restrictions.
              </span>
            </li>
          </ul>
        </div>
      )}
    </main>
  )
}
