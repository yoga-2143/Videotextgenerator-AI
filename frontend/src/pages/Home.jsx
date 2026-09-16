import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import logo from '../assets/logo.jpg'

export default function Home() {
  const [url, setUrl] = useState('')
  const [error, setError] = useState('')
  const navigate = useNavigate()

  function handleSubmit(e) {
    if (e && e.preventDefault) e.preventDefault()
    const trimmed = url.trim()
    if (!trimmed || trimmed.includes('...') || trimmed === 'https://www.youtube.com/watch?v=') {
      setError('Please enter a complete YouTube URL (e.g. https://www.youtube.com/watch?v=dQw4w9WgXcQ).')
      return
    }
    setError('')
    navigate('/youtube-url', { state: { url: trimmed, autoSubmit: true } })
  }

  return (
    <main className="mx-auto max-w-4xl px-4 sm:px-6 py-8 sm:py-14 text-center">
      <div className="flex flex-col items-center justify-center">
        {/* Brand Logo */}
        <img
          src={logo}
          alt="VideoTextGenerator AI Logo"
          className="h-24 sm:h-32 w-auto object-contain rounded-2xl sm:rounded-3xl bg-white p-2.5 sm:p-3 shadow-2xl border border-line mb-6 sm:mb-8 transition-transform hover:scale-105"
        />

        {/* Welcome Section */}
        <p className="font-mono text-xs sm:text-base uppercase tracking-[0.2em] sm:tracking-[0.25em] text-wave mb-3 sm:mb-4 font-bold">
          Welcome to
        </p>

        <h1 className="font-display hero-title font-extrabold tracking-tight text-paper max-w-3xl break-words">
          VideoTextGenerator AI
        </h1>

        <p className="mt-4 sm:mt-6 max-w-2xl text-base sm:text-xl text-mute leading-relaxed font-normal px-2 sm:px-0">
          Transform video content into clean, meaningful articles.
          Understand, translate, and listen in your supported languages.
        </p>

        {/* YouTube Input & Process Form Section */}
        <div className="mt-8 sm:mt-10 w-full max-w-2xl text-left bg-panel border border-line rounded-2xl sm:rounded-3xl p-5 sm:p-7 shadow-2xl">
          <form onSubmit={handleSubmit}>
            <label htmlFor="home-yt-input" className="block font-mono text-xs sm:text-sm font-bold uppercase tracking-wider text-wave mb-3">
              YOUTUBE VIDEO URL
            </label>
            <input
              id="home-yt-input"
              type="text"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://www.youtube.com/watch?v=..."
              className="w-full rounded-xl sm:rounded-2xl border border-line bg-ink px-4 sm:px-5 py-3.5 sm:py-4 text-sm sm:text-lg text-paper placeholder:text-mute focus:border-wave focus:outline-none mb-4 font-mono break-all"
            />
            {error && (
              <p className="mb-4 text-xs sm:text-sm font-mono text-rose-400 font-semibold">{error}</p>
            )}
            <button
              type="submit"
              className="w-full inline-flex items-center justify-center rounded-xl sm:rounded-2xl bg-signal py-3.5 sm:py-4 text-base sm:text-lg font-bold text-ink transition-transform hover:scale-[1.01] active:scale-[0.99] shadow-lg cursor-pointer min-h-[48px]"
            >
              Process YouTube URL
            </button>
          </form>
        </div>

        {/* YouTube Video Access Guide Card Directly Below */}
        <div className="mt-6 sm:mt-8 w-full max-w-2xl text-left bg-panel border border-line rounded-2xl sm:rounded-3xl p-5 sm:p-7 shadow-2xl">
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
      </div>
    </main>
  )
}
