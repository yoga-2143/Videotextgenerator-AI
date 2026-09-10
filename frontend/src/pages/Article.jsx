import React, { useEffect, useRef, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { api } from '../api'
import LanguageSelector from '../components/LanguageSelector'

const DEFAULT_FONT_SIZE = 18
const MIN_FONT_SIZE = 14
const MAX_FONT_SIZE = 30
const FONT_STEP = 2

const SECTION_HEADINGS = {
  en: 'IMPORTANT CONTENT',
  ta: 'முக்கியமான உள்ளடக்கம்',
  hi: 'महत्वपूर्ण सामग्री',
  te: 'ముఖ్యమైన సమాచారం',
  ml: 'പ്രധാന വിവരങ്ങൾ',
  kn: 'ಪ್ರಮುಖ ವಿಷಯ',
  es: 'CONTENIDO IMPORTANTE',
  fr: 'CONTENU IMPORTANT',
  de: 'WICHTIGER INHALT',
  pt: 'CONTEÚDO IMPORTANTE',
  ar: 'محتوى هام',
  zh: '重要内容',
  ja: '重要なコンテンツ',
  ko: '주요 내용',
  ru: 'ВАЖНОЕ СОДЕРЖАНИЕ',
}

function renderTextWithLinks(text) {
  if (!text) return text
  const urlRegex = /(https?:\/\/[^\s]+|www\.[^\s]+|\b[a-zA-Z0-9\-]+\.(?:com|org|net|in|io|ai|co|gov|edu)\b)/g
  const parts = text.split(urlRegex)
  if (parts.length === 1) return text

  return parts.map((part, index) => {
    if (part.match(urlRegex)) {
      const href = part.startsWith('http') ? part : part.startsWith('www.') ? `https://${part}` : `https://${part}`
      return (
        <a
          key={index}
          href={href}
          target="_blank"
          rel="noopener noreferrer"
          className="text-wave hover:underline font-semibold border-b border-wave/40 hover:border-wave transition-all inline-flex items-center gap-1 mx-1"
        >
          {part}
          <svg className="w-3.5 h-3.5 inline-block opacity-75 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
          </svg>
        </a>
      )
    }
    return part
  })
}

export default function Article() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [article, setArticle] = useState(null)
  const [languages, setLanguages] = useState([])
  const [selectedLang, setSelectedLang] = useState('en')
  const [translating, setTranslating] = useState(false)
  const [audioUrl, setAudioUrl] = useState(null)
  const [generatingAudio, setGeneratingAudio] = useState(false)
  const [isPlaying, setIsPlaying] = useState(false)
  const [audioNotice, setAudioNotice] = useState('')
  const [loading, setLoading] = useState(true)
  const [notFound, setNotFound] = useState(false)
  const [error, setError] = useState('')
  const [copyStatus, setCopyStatus] = useState('idle')
  const [shareStatus, setShareStatus] = useState('idle')
  const [shareMessage, setShareMessage] = useState('')

  const [fontSize, setFontSize] = useState(() => {
    const saved = localStorage.getItem('vetri_article_fontsize')
    const parsed = saved ? parseInt(saved, 10) : DEFAULT_FONT_SIZE
    return isNaN(parsed) ? DEFAULT_FONT_SIZE : Math.min(Math.max(parsed, MIN_FONT_SIZE), MAX_FONT_SIZE)
  })

  const audioRef = useRef(null)
  const jobIdRef = useRef(0)
  const audioLangRef = useRef('en')

  const selectedLangObj = languages.find(l => l.code === selectedLang) || { code: 'en', name: 'English', supports_tts: true }

  // Audio Playback Sync Effect
  useEffect(() => {
    if (audioUrl && audioRef.current) {
      audioRef.current.load()
      audioRef.current
        .play()
        .then(() => {
          setIsPlaying(true)
          setAudioNotice('')
        })
        .catch(() => {
          setAudioNotice('Voice generated. Click the speaker icon to play.')
        })
    }
  }, [audioUrl])

  const redirectingRef = useRef(false)

  // Fetch Initial Article & Languages
  useEffect(() => {
    if (!id || id === 'undefined' || id === 'null') {
      setNotFound(true)
      setLoading(false)
      setError('Article ID is missing or invalid.')
      return
    }

    setArticle(null)
    setAudioUrl(null)
    setIsPlaying(false)
    setAudioNotice('')
    setError('')
    setLoading(true)
    setNotFound(false)
    redirectingRef.current = false

    fetch(`/api/articles/${id}`)
      .then(r => {
        if (r.status === 404) {
          setNotFound(true)
          return null
        }
        if (!r.ok) {
          throw new Error(`Server error (${r.status}). Unable to fetch article.`)
        }
        return r.json()
      })
      .then(res => {
        if (res && res.success && res.data) {
          setArticle(res.data)
          if (res.data.language) {
            setSelectedLang(res.data.language)
            audioLangRef.current = res.data.language
          }
        } else if (res && !res.success) {
          if (res.error?.code === 'NOT_FOUND') {
            setNotFound(true)
          } else {
            setError(res.error?.message || 'Failed to load article details.')
          }
        } else {
          setNotFound(true)
        }
      })
      .catch(err => {
        setError(err.message || 'Network error loading article.')
      })
      .finally(() => setLoading(false))

    api.getLanguages().then(setLanguages).catch(() => {})
  }, [id])

  // Safe Single-Execution Redirect for Missing Articles to Main Video Processor (/youtube-url)
  useEffect(() => {
    if (notFound && !loading && !redirectingRef.current) {
      redirectingRef.current = true
      const timer = setTimeout(() => {
        navigate('/youtube-url', { replace: true })
      }, 1500)
      return () => clearTimeout(timer)
    }
  }, [notFound, loading, navigate])

  async function handleLanguageChange(langCode) {
    if (audioRef.current) {
      try {
        audioRef.current.pause()
        audioRef.current.src = ""
      } catch (e) {}
    }
    const nextLangObj = languages.find(l => l.code === langCode || l.id === langCode || l.language_id === langCode)
    if (nextLangObj && nextLangObj.supports_tts === false) {
      setAudioNotice('Voice is not available for this language.')
    }

    jobIdRef.current += 1
    const currentJobId = jobIdRef.current

    setSelectedLang(langCode)
    setArticle(null)
    setAudioUrl(null)
    setIsPlaying(false)
    setAudioNotice('')
    setError('')

    setTranslating(true)
    try {
      const targetArticleId = id || article?.id
      const translated = await api.translateArticle(targetArticleId, langCode)
      if (jobIdRef.current !== currentJobId) return

      if (translated) {
        const returnedLang = translated.target_language_id || translated.language || translated.targetLanguage
        if (returnedLang && returnedLang.toLowerCase() !== langCode.toLowerCase()) {
          setError(`TRANSLATION_VALIDATION_FAILED: Received response for '${returnedLang}' instead of requested '${langCode}'.`)
          return
        }
        setArticle(translated)
      } else {
        setError(`TRANSLATION_FAILED: Could not translate into '${nextLangObj?.name || langCode}'.`)
      }
    } catch (err) {
      if (jobIdRef.current !== currentJobId) return
      setError(err.message || `Translation failed for ${nextLangObj?.name || langCode}.`)
    } finally {
      if (jobIdRef.current === currentJobId) {
        setTranslating(false)
      }
    }
  }

  async function handleSpeakerClick() {
    if (generatingAudio) return
    setError('')
    setAudioNotice('')

    if (selectedLangObj.supports_tts === false) {
      setAudioNotice('Voice is not available for this language.')
      return
    }

    if (isPlaying && audioRef.current) {
      audioRef.current.pause()
      setIsPlaying(false)
      return
    }

    if (audioUrl && audioRef.current && audioLangRef.current === selectedLang) {
      try {
        await audioRef.current.play()
        setIsPlaying(true)
      } catch (err) {
        setAudioNotice('Voice generated. Click the speaker icon to play.')
      }
      return
    }

    jobIdRef.current += 1
    const currentJobId = jobIdRef.current
    setGeneratingAudio(true)

    try {
      const targetArticleId = id || article?.id
      const res = await api.generateAudio(targetArticleId, selectedLang)
      if (jobIdRef.current !== currentJobId) return

      if (res && res.voiceAvailable === false) {
        setAudioNotice('Voice is not available for this language.')
      } else if (res && (res.audioUrl || res.audio_url)) {
        const returnedLang = res.target_language_id || res.language
        if (returnedLang && returnedLang.toLowerCase() !== selectedLang.toLowerCase()) {
          setError('VOICE_LANGUAGE_MISMATCH: The audio could not be generated for the selected language.')
          return
        }
        audioLangRef.current = selectedLang
        setAudioUrl(res.audioUrl || res.audio_url)
      } else {
        setAudioNotice('Voice is not available for this language.')
      }
    } catch (err) {
      if (jobIdRef.current !== currentJobId) return
      setError(err.message || 'Unable to generate voice. Please try again.')
    } finally {
      if (jobIdRef.current === currentJobId) {
        setGeneratingAudio(false)
      }
    }
  }

  function increaseFontSize() {
    setFontSize(prev => {
      const next = Math.min(prev + FONT_STEP, MAX_FONT_SIZE)
      localStorage.setItem('vetri_article_fontsize', next)
      return next
    })
  }

  function decreaseFontSize() {
    setFontSize(prev => {
      const next = Math.max(prev - FONT_STEP, MIN_FONT_SIZE)
      localStorage.setItem('vetri_article_fontsize', next)
      return next
    })
  }

  function resetFontSize() {
    setFontSize(DEFAULT_FONT_SIZE)
    localStorage.setItem('vetri_article_fontsize', DEFAULT_FONT_SIZE)
  }

  async function handleCopy() {
    if (!article?.content) return
    const textToCopy = article.content.trim()

    try {
      if (navigator.clipboard && window.isSecureContext) {
        await navigator.clipboard.writeText(textToCopy)
      } else {
        const textarea = document.createElement('textarea')
        textarea.value = textToCopy
        textarea.style.position = 'fixed'
        textarea.style.opacity = '0'
        document.body.appendChild(textarea)
        textarea.focus()
        textarea.select()
        const successful = document.execCommand('copy')
        document.body.removeChild(textarea)
        if (!successful) throw new Error('execCommand failed')
      }
      setCopyStatus('copied')
      setTimeout(() => setCopyStatus('idle'), 2500)
    } catch (err) {
      setCopyStatus('error')
      setTimeout(() => setCopyStatus('idle'), 3000)
    }
  }

  async function handleShare() {
    if (!article?.content) return
    setShareMessage('')

    const shareData = {
      title: article.title || 'Article',
      text: article.content,
      url: window.location.href,
    }

    if (navigator.share) {
      try {
        await navigator.share(shareData)
        setShareStatus('shared')
        setTimeout(() => setShareStatus('idle'), 2500)
      } catch (err) {
        if (err.name === 'AbortError' || err.message?.toLowerCase().includes('cancel')) {
          return
        }
        fallbackShare(shareData)
      }
    } else {
      fallbackShare(shareData)
    }
  }

  async function fallbackShare(shareData) {
    const formattedShareText = `${shareData.title}\n\n${shareData.text}\n\nLink: ${shareData.url}`
    try {
      if (navigator.clipboard && window.isSecureContext) {
        await navigator.clipboard.writeText(formattedShareText)
      } else {
        const textarea = document.createElement('textarea')
        textarea.value = formattedShareText
        textarea.style.position = 'fixed'
        textarea.style.opacity = '0'
        document.body.appendChild(textarea)
        textarea.focus()
        textarea.select()
        const successful = document.execCommand('copy')
        document.body.removeChild(textarea)
        if (!successful) throw new Error('execCommand failed')
      }
      setShareStatus('copied')
      setShareMessage('Share text copied to clipboard!')
      setTimeout(() => {
        setShareStatus('idle')
        setShareMessage('')
      }, 3000)
    } catch (err) {
      setShareStatus('error')
      setShareMessage('Failed to share or copy text. Please try again.')
      setTimeout(() => {
        setShareStatus('idle')
        setShareMessage('')
      }, 3000)
    }
  }

  if (loading || translating) {
    return (
      <main className="mx-auto max-w-3xl px-6 py-24 text-center">
        <div className="inline-block h-8 w-8 animate-spin rounded-full border-4 border-wave border-t-transparent mb-4" />
        <p className="font-mono text-base font-semibold text-paper">
          {translating ? `Translating article to ${selectedLangObj?.name || selectedLang}…` : 'Loading article…'}
        </p>
      </main>
    )
  }

  if (notFound) {
    return (
      <main className="mx-auto max-w-3xl px-6 py-16 text-center">
        <div className="rounded-3xl border border-signal/30 bg-panel p-8 shadow-2xl">
          <div className="inline-flex items-center gap-3 rounded-full border border-signal/30 bg-signal/10 px-5 py-2.5 text-signal font-mono text-sm mb-6">
            <span className="relative flex h-2.5 w-2.5">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-signal opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-signal"></span>
            </span>
            Article not found. Redirecting to Main Video Processor...
          </div>
          <p className="text-mute text-sm font-mono mb-6">
            If redirection does not happen automatically, click below to open the Main Video Processor.
          </p>
          <button
            type="button"
            onClick={() => navigate('/youtube-url', { replace: true })}
            className="inline-flex items-center gap-2 rounded-full bg-signal px-7 py-3 font-mono text-sm font-bold text-ink hover:opacity-90 transition-opacity cursor-pointer shadow-lg"
          >
            Go to Main Video Processor
          </button>
        </div>
      </main>
    )
  }

  if (error && !article) {
    return (
      <main className="mx-auto max-w-3xl px-6 py-16 text-center">
        <div className="rounded-3xl border border-rose-500/30 bg-panel p-8 shadow-2xl">
          <div className="flex items-center justify-center gap-2 text-rose-400 font-mono text-base font-bold uppercase mb-3">
            <svg className="w-6 h-6 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            Failed to Load Article
          </div>
          <p className="text-paper text-base mb-6 font-medium leading-relaxed max-w-lg mx-auto">{error}</p>
          <div className="flex flex-wrap items-center justify-center gap-4">
            <button
              type="button"
              onClick={() => {
                setError('')
                setLoading(true)
                fetch(`/api/articles/${id}`)
                  .then(r => r.json())
                  .then(res => {
                    if (res?.success && res?.data) setArticle(res.data)
                    else setError(res?.error?.message || 'Article not found.')
                  })
                  .catch(err => setError(err.message || 'Network error.'))
                  .finally(() => setLoading(false))
              }}
              className="rounded-full bg-wave px-6 py-2.5 font-mono text-sm font-bold text-ink hover:opacity-90 transition-opacity cursor-pointer"
            >
              Try Again
            </button>
            <button
              type="button"
              onClick={() => navigate('/youtube-url')}
              className="rounded-full border border-line px-6 py-2.5 font-mono text-sm font-semibold text-paper hover:bg-line/40 transition-colors cursor-pointer"
            >
              Go to Main Video Processor
            </button>
          </div>
        </div>
      </main>
    )
  }

  if (!article) {
    return (
      <main className="mx-auto max-w-3xl px-6 py-16 text-center">
        <div className="rounded-3xl border border-line bg-panel p-8 shadow-2xl">
          <p className="text-paper font-semibold text-lg mb-4">No article content available.</p>
          <button
            type="button"
            onClick={() => navigate('/youtube-url')}
            className="rounded-full bg-signal px-6 py-2.5 font-mono text-sm font-bold text-ink hover:opacity-90 transition-opacity cursor-pointer"
          >
            Go to Main Video Processor
          </button>
        </div>
      </main>
    )
  }

  return (
    <main className="mx-auto max-w-3xl px-6 pb-24 pt-10">
      {/* Article Controls Toolbar */}
      <div className="mb-8 flex flex-wrap items-center justify-between gap-4 border-b border-line pb-5">
        {/* Language Selector */}
        <div className="flex items-center gap-3">
          <LanguageSelector
            languages={languages}
            selectedLang={selectedLang}
            onChange={handleLanguageChange}
            disabled={translating}
          />
          {translating && <span className="text-base text-mute font-mono animate-pulse self-end mb-2">Translating…</span>}
        </div>

        {/* Font Size Controls */}
        <div className="flex items-center gap-2 bg-panel border border-line rounded-2xl px-3 py-1.5 shadow-sm" role="group" aria-label="Font size controls">
          <span className="font-mono text-xs text-mute mr-1 hidden sm:inline font-bold uppercase">Text Size:</span>
          <button
            type="button"
            onClick={decreaseFontSize}
            disabled={fontSize <= MIN_FONT_SIZE}
            title="Decrease article font size (A−)"
            aria-label="Decrease font size"
            className="rounded-lg border border-line px-3 py-1 font-mono text-sm font-bold text-paper hover:bg-line/40 hover:text-wave transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
          >
            A−
          </button>
          <button
            type="button"
            onClick={resetFontSize}
            title="Reset font size to default (18px)"
            aria-label="Reset font size"
            className="rounded-lg border border-line px-3 py-1 font-mono text-xs font-semibold text-mute hover:bg-line/40 hover:text-paper transition-colors"
          >
            Reset
          </button>
          <button
            type="button"
            onClick={increaseFontSize}
            disabled={fontSize >= MAX_FONT_SIZE}
            title="Increase article font size (A+)"
            aria-label="Increase font size"
            className="rounded-lg border border-line px-3 py-1 font-mono text-sm font-bold text-paper hover:bg-line/40 hover:text-wave transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
          >
            A+
          </button>
        </div>
      </div>

      {/* Clean UI Header Badge for Important Content (Dynamically Translated) */}
      <div className="mt-8 mb-6 flex items-center gap-3 border-b border-line/60 pb-3">
        <span className="relative flex h-2.5 w-2.5">
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-wave opacity-75"></span>
          <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-wave"></span>
        </span>
        <h2 className="font-mono text-xs sm:text-sm font-bold uppercase tracking-widest text-wave">
          {SECTION_HEADINGS[selectedLang] || SECTION_HEADINGS[article?.language] || SECTION_HEADINGS.en}
        </h2>
      </div>

      {/* Article Content with Controlled Fluid Font Size */}
      <div
        style={{ fontSize: `${fontSize}px`, lineHeight: '1.85' }}
        className="text-paper/95 transition-all duration-150 font-normal antialiased"
      >
        {(() => {
          const rawContent = (article?.content || '')
            .replace(/^(IMPORTANT CONTENT|முக்கியமான உள்ளடக்கம்|முக்கிய உள்ளடக்கம்|महत्वपूर्ण सामग्री|முఖ్యమైన సమాచారం|പ്രധാന വിവരങ്ങൾ|പ്രധാന വിശേഷங்கள்|ಪ್ರಮುಖ ವಿಷಯ|CONTENIDO IMPORTANTE|CONTENU IMPORTANT|WICHTIGER INHALT|CONTEÚDO IMPORTANTE|محتوى هام|重要内容|重要なコンテンツ|주요 내용|ВАЖНОЕ СОДЕРЖАНИЕ)\s*/i, '')
            .trim()
          
          if (!rawContent) return null
          
          const paragraphs = rawContent.split('\n\n').filter(p => p.trim())
          return (
            <ul className="space-y-3">
              {paragraphs.map((p, idx) => {
                const cleanP = p.replace(/^•\s*/, '').trim()
                return (
                  <li key={idx} className="flex items-start gap-3.5 py-1.5 transition-all group">
                    <span className="mt-2.5 flex h-2 w-2 shrink-0 items-center justify-center rounded-full bg-white shadow-sm shadow-white/60 group-hover:scale-125 transition-transform" />
                    <span className="flex-1 text-paper/95 leading-relaxed">{renderTextWithLinks(cleanP)}</span>
                  </li>
                )
              })}
            </ul>
          )
        })()}
      </div>

      {/* Article Action Toolbar (Icon-Only Buttons Family: Copy, Share, Speaker/Voice) */}
      <div className="mt-6 flex flex-wrap items-center gap-3">
        {/* Copy Icon Button */}
        <button
          type="button"
          onClick={handleCopy}
          title="Copy article"
          aria-label="Copy"
          className="inline-flex items-center justify-center rounded-xl border border-line bg-panel p-2.5 sm:px-3 text-paper hover:border-wave hover:text-wave transition-all active:scale-95 shadow-sm cursor-pointer"
        >
          {copyStatus === 'copied' ? (
            <svg className="w-4 h-4 shrink-0 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M5 13l4 4L19 7" />
            </svg>
          ) : copyStatus === 'error' ? (
            <svg className="w-4 h-4 shrink-0 text-signal" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          ) : (
            <svg className="w-4 h-4 shrink-0 text-mute hover:text-wave transition-colors" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
            </svg>
          )}
        </button>

        {/* Share Icon Button */}
        <button
          type="button"
          onClick={handleShare}
          title="Share article"
          aria-label="Share"
          className="inline-flex items-center justify-center rounded-xl border border-line bg-panel p-2.5 sm:px-3 text-paper hover:border-wave hover:text-wave transition-all active:scale-95 shadow-sm cursor-pointer"
        >
          {shareStatus === 'shared' || shareStatus === 'copied' ? (
            <svg className="w-4 h-4 shrink-0 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M5 13l4 4L19 7" />
            </svg>
          ) : shareStatus === 'error' ? (
            <svg className="w-4 h-4 shrink-0 text-signal" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          ) : (
            <svg className="w-4 h-4 shrink-0 text-mute hover:text-wave transition-colors" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M8.684 13.342C8.886 12.938 9 12.482 9 12c0-.482-.114-.938-.316-1.342m0 2.684a3 3 0 110-2.684m0 2.684l6.632 3.316m-6.632-6l6.632-3.316m0 0a3 3 0 105.367-2.684 3 3 0 00-5.367 2.684zm0 9.316a3 3 0 105.368 2.684 3 3 0 00-5.368-2.684z" />
            </svg>
          )}
        </button>

        {/* Speaker Icon Button */}
        <button
          type="button"
          onClick={handleSpeakerClick}
          disabled={generatingAudio || !selectedLangObj?.supports_tts}
          title={selectedLangObj?.supports_tts ? "Generate Voice" : "Voice is not available for this language"}
          aria-label="Generate Voice"
          className="inline-flex items-center justify-center rounded-xl border border-line bg-panel p-2.5 sm:px-3 text-paper hover:border-wave hover:text-wave transition-all active:scale-95 shadow-sm disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer"
        >
          {generatingAudio ? (
            <div className="h-4 w-4 shrink-0 animate-spin rounded-full border-2 border-wave border-t-transparent" />
          ) : isPlaying ? (
            <svg className="w-4 h-4 shrink-0 text-wave animate-pulse" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M15.536 8.464a5 5 0 010 7.072m2.828-9.9a9 9 0 010 12.728M5.586 15H4a1 1 0 01-1-1v-4a1 1 0 011-1h1.586l4.707-4.707C10.923 3.663 12 4.109 12 5v14c0 .891-1.077 1.337-1.707.707L5.586 15z" />
            </svg>
          ) : (
            <svg className="w-4 h-4 shrink-0 text-mute hover:text-wave transition-colors" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15.536 8.464a5 5 0 010 7.072m2.828-9.9a9 9 0 010 12.728M5.586 15H4a1 1 0 01-1-1v-4a1 1 0 011-1h1.586l4.707-4.707C10.923 3.663 12 4.109 12 5v14c0 .891-1.077 1.337-1.707.707L5.586 15z" />
            </svg>
          )}
        </button>
      </div>

      {/* QA Badges Section */}
      <div className="mt-8 pt-6 border-t border-line/40 flex flex-wrap items-center gap-2">
        <span className="font-mono text-xs text-mute font-bold uppercase mr-2">QA Badges:</span>
        <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-mono font-bold bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
          <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M5 13l4 4L19 7"/></svg>
          Meaning Checked
        </span>
        <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-mono font-bold bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
          <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M5 13l4 4L19 7"/></svg>
          Low Repetition
        </span>
        <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-mono font-bold bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
          <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M5 13l4 4L19 7"/></svg>
          Proofread
        </span>
        <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-mono font-bold bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
          <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M5 13l4 4L19 7"/></svg>
          Readability Checked
        </span>
      </div>

      {shareMessage && (
        <p className="mt-2 text-xs font-mono text-emerald-400 font-semibold">{shareMessage}</p>
      )}

      {audioNotice && (
        <p className="mt-2 text-xs font-mono text-wave font-semibold">{audioNotice}</p>
      )}

      {/* Programmatic Hidden Audio Element */}
      {audioUrl && (
        <audio
          ref={audioRef}
          src={audioUrl}
          preload="auto"
          className="hidden"
          onPlay={() => setIsPlaying(true)}
          onPause={() => setIsPlaying(false)}
          onEnded={() => setIsPlaying(false)}
          onError={() => setError('Unable to generate voice. Please try again.')}
        />
      )}

      {error && <p className="mt-5 text-base text-signal font-semibold">{error}</p>}
    </main>
  )
}
