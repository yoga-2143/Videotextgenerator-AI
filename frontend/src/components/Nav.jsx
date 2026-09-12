import React, { useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import logo from '../assets/logo.jpg'
import { useAuth } from '../AuthContext'
import AuthModal from './AuthModal'

export default function Nav() {
  const location = useLocation()
  const { user, signOut } = useAuth()
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const [authModalOpen, setAuthModalOpen] = useState(false)
  const isActive = (path) => location.pathname === path

  return (
    <>
      <header className="sticky top-0 z-30 border-b border-line bg-ink/95 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-3.5 sm:px-6 py-3">
          {/* Brand Link with Logo */}
          <Link
            to="/"
            onClick={() => setMobileMenuOpen(false)}
            className="flex items-center gap-2 sm:gap-3 group font-display text-sm sm:text-xl font-bold tracking-tight text-paper hover:text-wave transition-colors min-w-0 mr-2"
          >
            <img
              src={logo}
              alt="Logo"
              className="h-8 w-auto sm:h-10 object-contain rounded-xl transition-transform group-hover:scale-105 shadow-md border border-line/40 bg-white shrink-0"
            />
            <span className="truncate text-sm sm:text-xl font-bold">VideoTextGenerator AI</span>
          </Link>

          {/* Desktop Navigation items (hidden on mobile <md, visible on md+) */}
          <nav className="hidden md:flex items-center gap-5 lg:gap-7 text-sm lg:text-base font-semibold shrink-0">
            <Link to="/" className={`transition-colors ${isActive('/') ? 'text-wave' : 'text-mute hover:text-paper'}`}>
              Home
            </Link>
            <Link to="/youtube-url" className={`transition-colors ${isActive('/youtube-url') ? 'text-wave' : 'text-mute hover:text-paper'}`}>
              YouTube URL
            </Link>
            <Link to="/history" className={`transition-colors ${isActive('/history') ? 'text-wave' : 'text-mute hover:text-paper'}`}>
              History
            </Link>

            {/* Auth Button / Profile */}
            {user ? (
              <div className="flex items-center gap-3 pl-2 border-l border-line/60">
                {user.picture_url ? (
                  <img
                    src={user.picture_url}
                    alt={user.name || 'User'}
                    className="h-8 w-8 rounded-full border border-wave object-cover"
                  />
                ) : (
                  <div className="flex h-8 w-8 items-center justify-center rounded-full bg-signal text-ink font-bold text-xs">
                    {(user.name || user.email || 'U')[0].toUpperCase()}
                  </div>
                )}
                <span className="text-xs lg:text-sm font-semibold text-paper max-w-[120px] truncate">
                  {user.name || user.email.split('@')[0]}
                </span>
                <button
                  type="button"
                  onClick={signOut}
                  className="rounded-lg border border-line/70 bg-panel px-3 py-1 text-xs font-mono text-mute hover:bg-line/40 hover:text-paper transition-colors cursor-pointer"
                >
                  Sign Out
                </button>
              </div>
            ) : (
              <button
                type="button"
                onClick={() => setAuthModalOpen(true)}
                className="rounded-full bg-signal px-4 py-1.5 font-mono text-xs lg:text-sm font-bold text-ink hover:opacity-90 transition-opacity cursor-pointer shadow-md"
              >
                Sign In
              </button>
            )}
          </nav>

          {/* Mobile Hamburger Toggle Button (visible on mobile <md) */}
          <button
            type="button"
            onClick={() => setMobileMenuOpen(prev => !prev)}
            className="md:hidden flex items-center justify-center p-2 text-paper hover:text-wave focus:outline-none cursor-pointer rounded-lg border border-line/50 bg-panel/50 shrink-0"
            aria-label="Toggle navigation menu"
          >
            {mobileMenuOpen ? (
              <svg className="w-5 h-5 sm:w-6 sm:h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
              </svg>
            ) : (
              <svg className="w-5 h-5 sm:w-6 sm:h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 6h16M4 12h16M4 18h16" />
              </svg>
            )}
          </button>
        </div>

        {/* Mobile Dropdown Menu (visible when mobileMenuOpen is true on mobile <md) */}
        {mobileMenuOpen && (
          <div className="md:hidden border-t border-line/60 bg-panel/95 px-5 py-4 backdrop-blur shadow-xl">
            <nav className="flex flex-col gap-3 font-semibold text-base">
              <Link
                to="/"
                onClick={() => setMobileMenuOpen(false)}
                className={`py-2 transition-colors border-b border-line/30 ${isActive('/') ? 'text-wave font-bold' : 'text-paper hover:text-wave'}`}
              >
                Home
              </Link>
              <Link
                to="/youtube-url"
                onClick={() => setMobileMenuOpen(false)}
                className={`py-2 transition-colors border-b border-line/30 ${isActive('/youtube-url') ? 'text-wave font-bold' : 'text-paper hover:text-wave'}`}
              >
                YouTube URL
              </Link>
              <Link
                to="/history"
                onClick={() => setMobileMenuOpen(false)}
                className={`py-2 transition-colors border-b border-line/30 ${isActive('/history') ? 'text-wave font-bold' : 'text-paper hover:text-wave'}`}
              >
                History
              </Link>

              {user ? (
                <div className="flex items-center justify-between pt-2">
                  <div className="flex items-center gap-2.5">
                    {user.picture_url ? (
                      <img src={user.picture_url} alt="Profile" className="h-7 w-7 rounded-full border border-wave" />
                    ) : (
                      <div className="flex h-7 w-7 items-center justify-center rounded-full bg-signal text-ink font-bold text-xs">
                        {(user.name || user.email || 'U')[0].toUpperCase()}
                      </div>
                    )}
                    <span className="text-sm font-medium text-paper truncate max-w-[160px]">
                      {user.name || user.email}
                    </span>
                  </div>
                  <button
                    type="button"
                    onClick={() => {
                      signOut()
                      setMobileMenuOpen(false)
                    }}
                    className="rounded-lg border border-line/70 bg-ink px-3 py-1 text-xs font-mono text-mute hover:text-paper"
                  >
                    Sign Out
                  </button>
                </div>
              ) : (
                <button
                  type="button"
                  onClick={() => {
                    setMobileMenuOpen(false)
                    setAuthModalOpen(true)
                  }}
                  className="mt-1 w-full rounded-xl bg-signal py-2.5 font-mono text-sm font-bold text-ink text-center hover:opacity-90"
                >
                  Sign In
                </button>
              )}
            </nav>
          </div>
        )}
      </header>

      {/* Auth Modal */}
      <AuthModal isOpen={authModalOpen} onClose={() => setAuthModalOpen(false)} />
    </>
  )
}


