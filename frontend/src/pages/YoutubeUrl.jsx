import React, { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api'
import { saveLocalHistoryItem } from '../utils/localHistory'

export default function YoutubeUrl() {
  const [url, setUrl] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [currentJob, setCurrentJob] = useState(null)
  const [jobStageMessage, setJobStageMessage] = useState('')
  const [jobProgress, setJobProgress] = useState(0)
  const [elapsedSeconds, setElapsedSeconds] = useState(0)

  const navigate = useNavigate()
  const pollingRef = useRef(null)
  const timerRef = useRef(null)
  const activeJobIdRef = useRef(null) // Identity guard: only the most recent job may update UI state

  useEffect(() => {
    return () => {
      if (pollingRef.current) clearInterval(pollingRef.current)
      if (timerRef.current) clearInterval(timerRef.current)
    }
  }, [])

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

  function startPolling(jobId) {
    if (pollingRef.current) {
      clearInterval(pollingRef.current)
    }

    pollingRef.current = setInterval(async () => {
      try {
        const jobState = await api.getJobStatus(jobId)
        if (!jobState) return

        // Identity guard: ignore this response if the user has since
        // cancelled or started a different job while this fetch was in flight.
        if (activeJobIdRef.current !== jobId) return
        // Belt-and-suspenders: also ignore if the server ever returns a
        // job_id that doesn't match what we asked for.
        if (jobState.job_id && jobState.job_id !== jobId) return

        setCurrentJob(jobState)
        setJobStageMessage(jobState.message || 'Processing video...')
        setJobProgress(jobState.progress || 10)

        if (jobState.status === 'completed' && jobState.result) {
          clearInterval(pollingRef.current)
          pollingRef.current = null
          stopTimer()
          setLoading(false)

          const data = jobState.result
          saveLocalHistoryItem(data)
          const targetId = data?.article?.id || data?.video_id
          if (targetId) {
            navigate(`/article/${targetId}`, { state: { video: data } })
          } else {
            setError('Video processed, but article ID was not returned. Please check History.')
          }
        } else if (jobState.status === 'failed') {
          clearInterval(pollingRef.current)
          pollingRef.current = null
          stopTimer()
          setLoading(false)
          setError(jobState.error?.message || jobState.message || 'Video processing failed.')
        }
      } catch (err) {
        // Silent retry on single polling network error
      }
    }, 1500)
  }

  async function fetchClientCaptions(urlStr) {
    try {
      const videoId = extractVideoId(urlStr)
      if (!videoId) return null
      
      const timedtextUrl = `https://www.youtube.com/api/timedtext?v=${videoId}&lang=en`
      const proxyUrls = [
        `https://api.allorigins.win/raw?url=${encodeURIComponent(timedtextUrl)}`,
        `https://corsproxy.io/?${encodeURIComponent(timedtextUrl)}`,
        timedtextUrl
      ]

      for (const targetUrl of proxyUrls) {
        try {
          const res = await fetch(targetUrl, { signal: AbortSignal.timeout(4000) }).catch(() => null)
          if (res && res.ok) {
            const xml = await res.text().catch(() => '')
            if (xml && xml.includes('<text')) {
              const matches = [...xml.matchAll(/<text[^>]*>(.*?)<\/text>/gs)]
              const text = matches
                .map(m => m[1].replace(/<[^>]+>/g, '').replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '"').replace(/&#39;/g, "'").trim())
                .filter(Boolean)
                .join(' ')
              if (text && text.length > 10) {
                return text
              }
            }
          }
        } catch (err) {}
      }
    } catch (e) {}
    return null
  }

  async function handleSubmit(e) {
    if (e && e.preventDefault) e.preventDefault()
    if (loading) return
    setError('')
    setJobStageMessage('Initializing video processing...')
    setJobProgress(5)

    const trimmed = url.trim()
    if (!trimmed || trimmed.includes('...') || trimmed === 'https://www.youtube.com/watch?v=') {
      setError('Please enter a complete YouTube URL (e.g. https://www.youtube.com/watch?v=dQw4w9WgXcQ).')
      return
    }

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
      // Client-assisted caption extraction
      const clientTranscript = await fetchClientCaptions(trimmed)

      // 1. Submit async processing job
      const res = await api.submitVideoJob(trimmed, clientTranscript)
      if (res && res.job_id) {
        activeJobIdRef.current = res.job_id
        setCurrentJob({ job_id: res.job_id, status: 'queued', progress: 5 })
        startPolling(res.job_id)
      } else if (res && res.article) {
        // Direct cached resolve
        stopTimer()
        saveLocalHistoryItem(res)
        const targetId = res.article?.id || res.video_id || res.id
        navigate(`/article/${targetId}`, { state: { video: res } })
      } else {
        stopTimer()
        setError('Failed to initiate processing job.')
        setLoading(false)
      }
    } catch (err) {
      // Fallback to legacy processVideo if submitVideoJob returns error
      try {
        const data = await api.processVideo(trimmed)
        stopTimer()
        saveLocalHistoryItem(data)
        const targetId = data?.article?.id || data?.video_id || data?.id
        if (targetId) {
          navigate(`/article/${targetId}`, { state: { video: data } })
        } else {
          setError(err.message || 'Failed to process YouTube URL')
          setLoading(false)
        }
      } catch (err2) {
        stopTimer()
        setError(err2.message || err.message || 'Failed to process YouTube URL')
        setLoading(false)
      }
    }
  }

  async function handleCancel() {
    if (pollingRef.current) {
      clearInterval(pollingRef.current)
      pollingRef.current = null
    }
    stopTimer()
    const jobToCancel = currentJob?.job_id
    // Clear the identity guard first so any response already in flight for
    // this job is ignored the moment it resolves, even before the cancel
    // request round-trips to the server.
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
  }

  return (
    <main className="mx-auto max-w-4xl px-6 py-16">
      <div className="text-center mb-12">
        <span className="font-mono text-sm sm:text-base font-bold uppercase tracking-[0.2em] text-wave">
          YouTube Processor
        </span>
        <h1 className="mt-3 font-display page-title font-bold text-paper">
          Enter YouTube Video URL
        </h1>
        <p className="mt-4 text-base sm:text-lg text-mute max-w-xl mx-auto leading-relaxed">
          Paste any public YouTube link to extract clean transcript data, rank important facts, and display important content immediately.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="rounded-3xl border border-line bg-panel p-8 shadow-2xl mb-8">
        <label htmlFor="yt-input" className="block text-sm font-mono font-bold uppercase tracking-wider text-paper mb-3">
          YouTube Video Link
        </label>
        <input
          id="yt-input"
          type="text"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="https://www.youtube.com/watch?v=..."
          disabled={loading}
          className="w-full rounded-2xl border border-line bg-ink px-5 py-4 text-lg sm:text-xl text-paper placeholder:text-mute focus:border-wave focus:outline-none mb-6 font-medium disabled:opacity-60"
        />

        {/* Live Progress Stage Feedback Box */}
        {loading && (
          <div className="mb-6 rounded-2xl border border-wave/40 bg-wave/10 p-5">
            <div className="flex items-center justify-between gap-4 mb-2">
              <div className="flex items-center gap-2 font-mono text-sm font-bold uppercase text-wave">
                <div className="h-4 w-4 animate-spin rounded-full border-2 border-wave border-t-transparent shrink-0" />
                <span>{jobStageMessage || 'Processing Video...'}</span>
              </div>
              <span className="font-mono text-sm font-bold text-wave">{jobProgress}%</span>
            </div>

            {/* Progress Bar Container */}
            <div className="w-full h-2.5 bg-ink rounded-full overflow-hidden border border-line mb-3">
              <div
                className="h-full bg-wave transition-all duration-300 ease-out"
                style={{ width: `${Math.min(Math.max(jobProgress, 5), 100)}%` }}
              />
            </div>

            <div className="flex items-center justify-between text-xs font-mono text-mute">
              <span>Stage-based processing active ({elapsedSeconds}s)</span>
              <button
                type="button"
                onClick={handleCancel}
                className="text-signal hover:underline font-bold cursor-pointer"
              >
                Cancel Request
              </button>
            </div>
          </div>
        )}

        {/* User-Friendly Error Display & Retry */}
        {error && !loading && (
          <div className="mb-6 rounded-2xl border border-rose-500/30 bg-rose-500/10 p-5 text-paper">
            <div className="flex items-center gap-2 mb-1.5 font-bold text-rose-400 font-mono text-sm uppercase tracking-wider">
              <svg className="w-5 h-5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              Processing Notice
            </div>
            <p className="text-base leading-relaxed text-paper/90 font-medium mb-3">{error}</p>
            <button
              type="button"
              onClick={handleSubmit}
              disabled={loading}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-rose-500 text-white font-bold text-sm hover:bg-rose-600 transition-colors cursor-pointer disabled:opacity-60"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
              Retry
            </button>
          </div>
        )}

        <button
          type="submit"
          disabled={loading}
          className="w-full inline-flex items-center justify-center gap-3 rounded-2xl bg-signal py-4 text-base sm:text-lg font-bold text-ink transition-transform hover:scale-[1.01] active:scale-[0.99] disabled:opacity-60 shadow-lg cursor-pointer"
        >
          {loading ? 'Processing Video URL...' : 'Process Video URL'}
        </button>
      </form>
    </main>
  )
}
