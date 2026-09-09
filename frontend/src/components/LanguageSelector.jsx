import React, { useState, useRef, useEffect } from 'react'

export default function LanguageSelector({ languages, selectedLang, onChange, disabled }) {
  const [isOpen, setIsOpen] = useState(false)
  const [search, setSearch] = useState('')
  const dropdownRef = useRef(null)

  const COMMON_LANG_NAMES = {
    en: 'English', ta: 'Tamil', hi: 'Hindi', te: 'Telugu', ml: 'Malayalam',
    kn: 'Kannada', bn: 'Bengali', mr: 'Marathi', gu: 'Gujarati', ur: 'Urdu',
    es: 'Spanish', fr: 'French', de: 'German', it: 'Italian', pt: 'Portuguese',
    ja: 'Japanese', ko: 'Korean', zh: 'Chinese', ru: 'Russian', ar: 'Arabic'
  }

  const selectedObj = languages.find(l => (l.code === selectedLang || l.id === selectedLang || l.language_id === selectedLang)) || {
    code: selectedLang,
    language_id: selectedLang,
    name: COMMON_LANG_NAMES[selectedLang] || (selectedLang ? selectedLang.toUpperCase() : 'English'),
    supports_tts: true
  }

  useEffect(() => {
    function handleClickOutside(e) {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target)) {
        setIsOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const filteredLangs = languages.filter(l =>
    (l.name || l.display_name || '').toLowerCase().includes(search.toLowerCase()) ||
    (l.code || l.id || l.language_id || '').toLowerCase().includes(search.toLowerCase())
  )

  return (
    <div className="relative inline-block text-left" ref={dropdownRef}>
      <button
        type="button"
        disabled={disabled}
        onClick={() => setIsOpen(prev => !prev)}
        className="inline-flex items-center justify-between gap-3 rounded-2xl border border-line bg-panel px-4 py-2.5 text-sm sm:text-base font-semibold text-paper hover:border-wave transition-all min-w-[220px] cursor-pointer disabled:opacity-50"
      >
        <span className="truncate">{selectedObj.name || selectedObj.display_name}</span>
        <div className="flex items-center gap-1.5 shrink-0">
          {selectedObj.supports_tts !== false ? (
            <span className="font-mono text-[10px] uppercase font-bold text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded-full border border-emerald-500/30">
              Text + Voice
            </span>
          ) : (
            <span className="font-mono text-[10px] uppercase font-bold text-amber-400 bg-amber-500/10 px-2 py-0.5 rounded-full border border-amber-500/30">
              Text Only
            </span>
          )}
          <svg className={`w-4 h-4 text-mute transition-transform ${isOpen ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 9l-7 7-7-7" />
          </svg>
        </div>
      </button>

      {isOpen && (
        <div className="absolute left-0 z-50 mt-2 w-72 rounded-2xl border border-line bg-panel p-3 shadow-2xl backdrop-blur-xl">
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search language..."
            autoFocus
            className="w-full rounded-xl border border-line bg-ink px-3 py-2 text-sm text-paper placeholder:text-mute focus:border-wave focus:outline-none mb-2 font-medium"
          />
          <div className="max-h-60 overflow-y-auto space-y-1 pr-1 custom-scrollbar">
            {filteredLangs.length === 0 ? (
              <div className="py-3 text-center text-xs font-mono text-mute">No languages found</div>
            ) : (
              filteredLangs.map((l) => {
                const codeVal = l.code || l.id || l.language_id
                return (
                  <button
                    key={codeVal}
                    type="button"
                    onClick={() => {
                      onChange(codeVal)
                      setIsOpen(false)
                      setSearch('')
                    }}
                    className={`w-full flex items-center justify-between rounded-xl px-3 py-2 text-sm font-medium transition-colors text-left ${
                      codeVal === selectedLang ? 'bg-wave/15 text-wave font-bold' : 'text-paper hover:bg-line/40'
                    }`}
                  >
                    <span>{l.name || l.display_name}</span>
                    {l.supports_tts !== false ? (
                      <span className="font-mono text-[9px] uppercase font-bold text-emerald-400">Audio+Text</span>
                    ) : (
                      <span className="font-mono text-[9px] uppercase font-bold text-amber-400">Text Only</span>
                    )}
                  </button>
                )
              })
            )}
          </div>
        </div>
      )}
    </div>
  )
}
