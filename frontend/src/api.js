import { getLocalHistory, deleteLocalHistoryItem, clearLocalHistory } from './utils/localHistory'

const BASE = (import.meta.env.VITE_API_BASE_URL || '/api').replace(/\/+$/, '')


function authHeaders() {
  const token = localStorage.getItem('vetri_token')
  return token ? { Authorization: `Bearer ${token}` } : {}
}

function extractVideoId(url) {
  if (!url || typeof url !== 'string') return url
  const trimmed = url.trim()
  const patterns = [
    /(?:v=|\/v\/|\/embed\/|\/shorts\/|youtu\.be\/)([\w-]{11})/,
    /(?:youtube\.com\/watch\?.*v=)([\w-]{11})/,
    /(?:youtube\.com\/shorts\/)([\w-]{11})/,
    /(?:youtube\.com\/embed\/)([\w-]{11})/,
    /(?:youtu\.be\/)([\w-]{11})/
  ]
  for (const p of patterns) {
    const match = trimmed.match(p)
    if (match && match[1]) return match[1]
  }
  return trimmed
}

async function handle(res) {
  const body = await res.json().catch(() => ({}))
  if (!res.ok || body.success === false) {
    const message = body?.error?.message || body?.message || (res.statusText ? `Server Error (${res.status}: ${res.statusText})` : `HTTP ${res.status} Processing Failed`)
    const err = new Error(message)
    err.status = res.status
    err.code = body?.error?.code || 'API_ERROR'
    throw err
  }
  return body.data
}
async function fetchWithTimeout(resource, options = {}) {
  const { timeout = 90000, ...fetchOptions } = options
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeout)
  try {
    const response = await fetch(resource, {
      ...fetchOptions,
      signal: controller.signal
    })
    return response
  } catch (err) {
    if (err.name === 'AbortError') {
      const timeoutErr = new Error('Processing took longer than expected. Please try again.')
      timeoutErr.code = 'PROCESSING_TIMEOUT'
      throw timeoutErr
    }
    throw err
  } finally {
    clearTimeout(timer)
  }
}

// In-flight deduplication to prevent duplicate concurrent network requests
const IN_FLIGHT_REQUESTS = new Map()

function deduplicateRequest(key, fetcher) {
  if (IN_FLIGHT_REQUESTS.has(key)) {
    return IN_FLIGHT_REQUESTS.get(key)
  }
  const promise = fetcher().finally(() => {
    IN_FLIGHT_REQUESTS.delete(key)
  })
  IN_FLIGHT_REQUESTS.set(key, promise)
  return promise
}

export const api = {
  submitVideoJob: (url, transcript) => {
    return fetch(`${BASE}/jobs/process`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify({ url, transcript }),
    }).then(handle)
  },

  getJobStatus: (jobId) => {
    return fetch(`${BASE}/jobs/${jobId}`).then(handle)
  },

  cancelJob: (jobId) => {
    return fetch(`${BASE}/jobs/${jobId}/cancel`, {
      method: 'POST',
      headers: { ...authHeaders() },
    }).then(handle)
  },

  processVideo: (url, transcript) => {
    const videoId = extractVideoId(url)
    return deduplicateRequest(`process:${videoId}`, () =>
      fetch(`${BASE}/videos/process`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeaders() },
        body: JSON.stringify({ url, transcript }),
      }).then(handle)
    )
  },

  getVideoDetails: (url) => {
    const videoId = extractVideoId(url)
    return deduplicateRequest(`details:${videoId}`, () =>
      fetch(`${BASE}/videos/details`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url }),
      }).then(handle)
    )
  },

  getLanguages: () =>
    fetch(`${BASE}/languages`)
      .then(handle)
      .then(res => (res && res.availableLanguages ? res.availableLanguages : Array.isArray(res) ? res : [])),
  
  translateArticle: (articleId, language) =>
    deduplicateRequest(`translate:${articleId}:${language}`, () =>
      fetch(`${BASE}/articles/${articleId}/translate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeaders() },
        body: JSON.stringify({ language }),
      }).then(handle)
    ),

  generateAudio: (articleId, language) =>
    deduplicateRequest(`audio:${articleId}:${language || 'default'}`, () =>
      fetch(`${BASE}/articles/${articleId}/audio`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeaders() },
        body: JSON.stringify({ language }),
      })
        .then(handle)
        .then(res => {
          if (res && (res.audioUrl || res.audio_url)) {
            const rawUrl = res.audioUrl || res.audio_url
            if (rawUrl && rawUrl.startsWith('/')) {
              let backendOrigin = ''
              if (BASE.startsWith('http')) {
                backendOrigin = new URL(BASE).origin
              } else if (import.meta.env.VITE_API_BASE_URL && import.meta.env.VITE_API_BASE_URL.startsWith('http')) {
                backendOrigin = new URL(import.meta.env.VITE_API_BASE_URL).origin
              } else if (typeof window !== 'undefined' && window.location && window.location.origin) {
                backendOrigin = window.location.origin
              }
              const fullUrl = backendOrigin ? `${backendOrigin}${rawUrl}` : rawUrl
              res.audioUrl = fullUrl
              res.audio_url = fullUrl
            }
          }
          return res
        })
    ),

  getArticle: (id) => fetch(`${BASE}/articles/${id}`, { headers: authHeaders() }).then(handle),
  getHistory: () => Promise.resolve(getLocalHistory()),
  
  deleteHistory: (id) => {
    deleteLocalHistoryItem(id)
    return fetch(`${BASE}/history/${id}`, {
      method: 'DELETE',
      headers: authHeaders(),
    })
      .then(handle)
      .catch(() => ({ success: true }))
  },

  deleteAllHistory: () => {
    clearLocalHistory()
    return fetch(`${BASE}/history/clear_all`, {
      method: 'DELETE',
      headers: authHeaders(),
    })
      .then(handle)
      .catch(() => ({ success: true }))
  },

  search: (query) => fetch(`${BASE}/search?q=${encodeURIComponent(query)}`).then(handle),

  health: () => fetch(`${BASE}/health`).then(handle),

  // Auth Endpoints
  googleLogin: (credential) =>
    fetch(`${BASE}/auth/google`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ credential }),
    }).then(handle),

  emailLogin: (email, password) =>
    fetch(`${BASE}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    }).then(handle),

  signUp: (name, email, password) =>
    fetch(`${BASE}/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, email, password }),
    }).then(handle),

  getMe: () =>
    fetch(`${BASE}/me`, {
      headers: authHeaders(),
    }).then(handle),

  logout: () =>
    fetch(`${BASE}/logout`, {
      method: 'POST',
      headers: authHeaders(),
    }).then(handle),
}
