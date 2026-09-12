import React from 'react'
import { Link } from 'react-router-dom'
import logo from '../assets/logo.jpg'

export default function Home() {
  return (
    <main className="mx-auto max-w-5xl px-4 sm:px-6 py-8 sm:py-20 text-center">
      <div className="flex flex-col items-center justify-center">
        {/* Brand Logo */}
        <img
          src={logo}
          alt="VideoTextGenerator AI Logo"
          className="h-24 sm:h-36 w-auto object-contain rounded-2xl sm:rounded-3xl bg-white p-2.5 sm:p-3 shadow-2xl border border-line mb-6 sm:mb-8 transition-transform hover:scale-105"
        />

        {/* Welcome Section */}
        <p className="font-mono text-xs sm:text-base uppercase tracking-[0.2em] sm:tracking-[0.25em] text-wave mb-3 sm:mb-4 font-bold">
          Welcome to
        </p>

        <h1 className="font-display hero-title font-extrabold tracking-tight text-paper max-w-4xl break-words">
          VideoTextGenerator AI
        </h1>

        <p className="mt-4 sm:mt-8 max-w-2xl text-base sm:text-xl md:text-2xl text-mute leading-relaxed font-normal px-2 sm:px-0">
          Transform video content into clean, meaningful articles.
          Understand, translate, and listen in your supported languages.
        </p>

        <div className="mt-6 sm:mt-10 flex flex-wrap items-center justify-center gap-2.5 sm:gap-4 font-mono text-xs sm:text-base font-bold uppercase tracking-[0.1em] sm:tracking-[0.2em] text-wave bg-panel border border-line rounded-2xl sm:rounded-full px-4 sm:px-8 py-2.5 sm:py-3 shadow-md max-w-full min-w-0">
          <span>Understand</span>
          <span className="text-mute">•</span>
          <span>Translate</span>
          <span className="text-mute">•</span>
          <span>Listen</span>
        </div>

        {/* Quick Action Button */}
        <div className="mt-8 sm:mt-12">
          <Link
            to="/youtube-url"
            className="min-h-[48px] inline-flex items-center justify-center rounded-full bg-signal px-8 sm:px-9 py-3.5 sm:py-4 text-base sm:text-lg font-bold text-ink transition-transform hover:scale-105 shadow-xl min-w-0 max-w-full"
          >
            Process YouTube URL
          </Link>
        </div>
      </div>
    </main>
  )
}
