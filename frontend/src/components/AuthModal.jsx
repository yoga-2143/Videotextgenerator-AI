import React, { useState } from 'react'
import { GoogleLogin } from '@react-oauth/google'
import { useAuth } from '../AuthContext'

export default function AuthModal({ isOpen, onClose }) {
  const { signIn, signInWithEmail, signUp } = useAuth()
  const [isSignUp, setIsSignUp] = useState(false)
  const [email, setEmail] = useState('')
  const [name, setName] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  if (!isOpen) return null

  const handleGoogleSuccess = async (credentialResponse) => {
    try {
      setLoading(true)
      setError('')
      if (credentialResponse.credential) {
        await signIn(credentialResponse.credential)
        onClose()
      } else {
        throw new Error('Google sign-in credential not received.')
      }
    } catch (err) {
      setError(err.message || 'Google sign-in failed. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  const handleGoogleError = () => {
    setError('Google sign-in popup was cancelled or failed.')
  }

  const handleEmailSubmit = async (e) => {
    e.preventDefault()
    if (!email || !password) {
      setError('Please fill in all required fields.')
      return
    }

    try {
      setLoading(true)
      setError('')
      if (isSignUp) {
        await signUp(name, email, password)
      } else {
        await signInWithEmail(email, password)
      }
      onClose()
    } catch (err) {
      setError(err.message || 'Authentication failed. Please check your details.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="relative w-full max-w-md rounded-3xl border border-line bg-panel p-6 sm:p-8 shadow-2xl">
        {/* Close Button */}
        <button
          type="button"
          onClick={onClose}
          className="absolute right-4 top-4 rounded-xl p-2 text-mute hover:bg-line/50 hover:text-paper transition-colors"
          aria-label="Close modal"
        >
          <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>

        {/* Modal Title */}
        <div className="mb-6 text-center">
          <h2 className="font-display text-2xl font-bold tracking-tight text-paper sm:text-3xl">
            {isSignUp ? 'Create VETRI Account' : 'Sign in to VETRI'}
          </h2>
          <p className="mt-1 text-sm text-mute">
            Access your personalized video summary history on any device.
          </p>
        </div>

        {error && (
          <div className="mb-4 rounded-xl border border-signal/40 bg-signal/10 p-3.5 text-xs text-signal font-mono">
            {error}
          </div>
        )}

        {/* Google Sign In Button */}
        <div className="flex justify-center mb-6">
          <GoogleLogin
            onSuccess={handleGoogleSuccess}
            onError={handleGoogleError}
            useOneTap
            theme="filled_dark"
            shape="pill"
            text={isSignUp ? 'signup_with' : 'signin_with'}
          />
        </div>

        <div className="relative mb-6 flex items-center justify-center">
          <div className="w-full border-t border-line/60"></div>
          <span className="absolute bg-panel px-3 font-mono text-xs font-semibold text-mute uppercase">
            Or with email
          </span>
        </div>

        {/* Form */}
        <form onSubmit={handleEmailSubmit} className="space-y-4">
          {isSignUp && (
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-mute mb-1">
                Name
              </label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Jane Doe"
                className="w-full rounded-xl border border-line bg-ink px-4 py-2.5 text-sm text-paper focus:border-wave focus:outline-none"
              />
            </div>
          )}

          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-mute mb-1">
              Email Address
            </label>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              className="w-full rounded-xl border border-line bg-ink px-4 py-2.5 text-sm text-paper focus:border-wave focus:outline-none"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-mute mb-1">
              Password
            </label>
            <input
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              className="w-full rounded-xl border border-line bg-ink px-4 py-2.5 text-sm text-paper focus:border-wave focus:outline-none"
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full rounded-xl bg-signal py-3 font-mono text-sm font-bold text-ink hover:opacity-90 transition-opacity disabled:opacity-50 cursor-pointer shadow-lg"
          >
            {loading ? 'Processing...' : isSignUp ? 'Create Account' : 'Sign In'}
          </button>
        </form>

        {/* Toggle Mode */}
        <div className="mt-6 text-center text-xs text-mute">
          {isSignUp ? 'Already have an account?' : "Don't have an account yet?"}{' '}
          <button
            type="button"
            onClick={() => {
              setIsSignUp(!isSignUp)
              setError('')
            }}
            className="font-bold text-wave hover:underline cursor-pointer ml-1"
          >
            {isSignUp ? 'Sign In' : 'Create Account'}
          </button>
        </div>
      </div>
    </div>
  )
}
