import React from 'react'
import { Link, useLocation } from 'react-router-dom'
import logo from '../assets/logo.jpg'

export default function Nav() {
  const location = useLocation()
  const isActive = (path) => location.pathname === path

  return (
    <header className="sticky top-0 z-20 border-b border-line bg-ink/95 backdrop-blur">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-3.5">
        {/* Brand Link with Logo */}
        <Link to="/" className="flex items-center gap-3 group font-display text-xl font-bold tracking-tight text-paper hover:text-wave transition-colors">
          <img
            src={logo}
            alt="Logo"
            className="h-10 w-auto object-contain rounded-xl transition-transform group-hover:scale-105 shadow-md border border-line/40 bg-white"
          />
          <span>VideoTextGenerator AI</span>
        </Link>

        {/* Navigation items: ONLY Home, YouTube URL, History */}
        <nav className="flex items-center gap-7 text-base font-semibold">
          <Link to="/" className={`transition-colors ${isActive('/') ? 'text-wave' : 'text-mute hover:text-paper'}`}>
            Home
          </Link>
          <Link to="/youtube-url" className={`transition-colors ${isActive('/youtube-url') ? 'text-wave' : 'text-mute hover:text-paper'}`}>
            YouTube URL
          </Link>
          <Link to="/history" className={`transition-colors ${isActive('/history') ? 'text-wave' : 'text-mute hover:text-paper'}`}>
            History
          </Link>
        </nav>
      </div>
    </header>
  )
}
