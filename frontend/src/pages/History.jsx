import React, { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'

export default function History() {
  const [items, setItems] = useState([])
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [deletingId, setDeletingId] = useState(null)
  const [deleteTargetItem, setDeleteTargetItem] = useState(null)
  const [showClearAllModal, setShowClearAllModal] = useState(false)
  const [clearingAll, setClearingAll] = useState(false)
  const [successMessage, setSuccessMessage] = useState('')

  useEffect(() => {
    fetchHistory()
  }, [])

  function fetchHistory() {
    setLoading(true)
    setError('')
    api.getHistory()
      .then(res => {
        if (Array.isArray(res)) {
          setItems(res)
        } else if (res && Array.isArray(res.data)) {
          setItems(res.data)
        } else {
          setItems([])
        }
      })
      .catch(err => {
        setError(err.message || 'Failed to load history items from backend server.')
        setItems([])
      })
      .finally(() => setLoading(false))
  }

  function confirmDelete(item) {
    setError('')
    setSuccessMessage('')
    setDeleteTargetItem(item)
  }

  function cancelDelete() {
    setDeleteTargetItem(null)
  }

  async function executeDelete() {
    if (!deleteTargetItem) return
    const id = deleteTargetItem.id
    setDeletingId(id)
    try {
      await api.deleteHistory(id)
      setItems(prev => (Array.isArray(prev) ? prev.filter(item => item.id !== id) : []))
      setSuccessMessage('History item deleted successfully.')
      setTimeout(() => setSuccessMessage(''), 4000)
    } catch (err) {
      setError(err.message || 'Failed to delete history item.')
    } finally {
      setDeletingId(null)
      setDeleteTargetItem(null)
    }
  }

  async function executeClearAll() {
    setClearingAll(true)
    setError('')
    try {
      await api.deleteAllHistory()
      setItems([])
      setSuccessMessage('All history items have been deleted successfully.')
      setTimeout(() => setSuccessMessage(''), 4000)
    } catch (err) {
      setError(err.message || 'Failed to clear all history items.')
    } finally {
      setClearingAll(false)
      setShowClearAllModal(false)
    }
  }

  function formatDate(dateStr) {
    if (!dateStr) return 'N/A'
    try {
      const d = new Date(dateStr)
      return isNaN(d.getTime()) ? 'N/A' : d.toLocaleDateString()
    } catch {
      return 'N/A'
    }
  }

  const safeItems = Array.isArray(items) ? items : []

  return (
    <main className="mx-auto max-w-4xl px-6 pb-24 pt-12">
      <div className="flex flex-wrap items-center justify-between gap-4 mb-8 border-b border-line pb-4">
        <h1 className="font-display page-title font-bold text-paper">Processing History</h1>
        <div className="flex items-center gap-4">
          <span className="font-mono text-sm sm:text-base text-wave font-bold uppercase tracking-wider">
            {safeItems.length} Saved Items
          </span>
          {safeItems.length > 0 && (
            <button
              type="button"
              onClick={() => {
                setError('')
                setSuccessMessage('')
                setShowClearAllModal(true)
              }}
              className="inline-flex items-center gap-2 rounded-xl border border-signal/40 bg-signal/10 px-4 py-2 font-mono text-xs sm:text-sm font-bold text-signal hover:bg-signal hover:text-ink transition-all active:scale-95 shadow-sm cursor-pointer"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
              </svg>
              Delete All
            </button>
          )}
        </div>
      </div>

      {successMessage && (
        <div className="mb-6 rounded-2xl border border-emerald-500/30 bg-emerald-500/10 p-5 text-base sm:text-lg text-emerald-400 font-medium">
          {successMessage}
        </div>
      )}

      {error && (
        <div className="mb-6 rounded-2xl border border-signal/30 bg-signal/10 p-5 text-base sm:text-lg text-signal">
          <span className="font-bold block mb-1">History Notice:</span>
          {error}
        </div>
      )}

      {loading && (
        <div className="py-16 text-center">
          <div className="inline-block h-8 w-8 animate-spin rounded-full border-4 border-wave border-t-transparent mb-3" />
          <p className="font-mono text-base text-mute">Loading history records...</p>
        </div>
      )}

      {!loading && safeItems.length === 0 && !error && (
        <div className="rounded-3xl border border-dashed border-line p-12 text-center">
          <p className="text-paper font-semibold text-xl sm:text-2xl">No history yet</p>
          <p className="text-mute text-base mt-2">Process a YouTube video link to generate articles and audio history records.</p>
        </div>
      )}

      {!loading && safeItems.length > 0 && (
        <div className="space-y-4">
          {safeItems.map(item => {
            const targetArticleId = item.articles?.[0]?.id || item.id
            return (
              <div key={item.id} className="flex flex-col sm:flex-row sm:items-center justify-between gap-5 rounded-2xl border border-line bg-panel p-5 transition-all hover:border-line/80 shadow-md">
                <div className="flex items-center gap-5">
                  {item.thumbnail_url && (
                    <img src={item.thumbnail_url} alt="" className="h-20 w-32 rounded-xl object-cover bg-ink border border-line shrink-0" />
                  )}
                  <div>
                    <Link to={`/article/${targetArticleId}`} className="font-bold text-lg sm:text-xl text-paper hover:text-wave transition-colors line-clamp-1">
                      {item.title || 'Untitled video'}
                    </Link>
                    <div className="flex items-center gap-2.5 font-mono text-xs sm:text-sm text-mute mt-2">
                      <span className="uppercase px-2 py-0.5 bg-line/50 rounded text-paper font-bold">{item.original_language || 'EN'}</span>
                      <span>·</span>
                      <span className="capitalize font-semibold">{item.status || 'done'}</span>
                      <span>·</span>
                      <span>{formatDate(item.created_at)}</span>
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-3.5 self-end sm:self-center shrink-0">
                  <Link
                    to={`/article/${targetArticleId}`}
                    className="rounded-full border border-line px-4.5 py-2 text-sm sm:text-base font-semibold text-paper hover:border-wave hover:text-wave transition-colors"
                  >
                    Open Article
                  </Link>
                  <button
                    type="button"
                    onClick={() => confirmDelete(item)}
                    disabled={deletingId === item.id}
                    className="rounded-full border border-signal/30 px-4.5 py-2 text-sm sm:text-base font-semibold text-signal hover:bg-signal/10 transition-colors disabled:opacity-50 cursor-pointer"
                  >
                    {deletingId === item.id ? 'Deleting...' : 'Delete'}
                  </button>
                </div>
              </div>
            )
          })}
        </div>
      )}

      {/* Confirmation Single Item Delete Modal */}
      {deleteTargetItem && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/85 backdrop-blur-sm p-5">
          <div className="w-full max-w-lg rounded-3xl border border-line bg-panel p-8 shadow-2xl">
            <h3 className="font-display text-2xl sm:text-3xl font-bold text-paper">Delete History Item</h3>
            <p className="mt-4 text-base sm:text-lg text-mute leading-relaxed">
              Are you sure you want to delete <span className="font-bold text-paper">"{deleteTargetItem.title || 'this item'}"</span>? This action cannot be undone and will permanently remove associated transcripts, articles, and audio files.
            </p>
            <div className="mt-8 flex justify-end gap-4">
              <button
                type="button"
                onClick={cancelDelete}
                className="rounded-full border border-line px-6 py-2.5 text-sm sm:text-base font-semibold text-paper hover:bg-line/30 transition-colors cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={executeDelete}
                className="rounded-full bg-signal px-6 py-2.5 text-sm sm:text-base font-bold text-ink hover:opacity-90 transition-opacity shadow-lg cursor-pointer"
              >
                Confirm Delete
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Clear All Confirmation Modal */}
      {showClearAllModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/85 backdrop-blur-sm p-5">
          <div className="w-full max-w-lg rounded-3xl border border-line bg-panel p-8 shadow-2xl">
            <div className="flex items-center gap-3 text-signal mb-2">
              <svg className="w-7 h-7" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
              </svg>
              <h3 className="font-display text-2xl sm:text-3xl font-bold text-paper">Delete All History</h3>
            </div>
            <p className="mt-4 text-base sm:text-lg text-mute leading-relaxed">
              Are you sure you want to delete <span className="font-bold text-signal">ALL {safeItems.length} history records</span>? This action cannot be undone and will permanently remove all transcripts, articles, and generated audio files.
            </p>
            <div className="mt-8 flex justify-end gap-4">
              <button
                type="button"
                onClick={() => setShowClearAllModal(false)}
                disabled={clearingAll}
                className="rounded-full border border-line px-6 py-2.5 text-sm sm:text-base font-semibold text-paper hover:bg-line/30 transition-colors disabled:opacity-50 cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={executeClearAll}
                disabled={clearingAll}
                className="rounded-full bg-signal px-6 py-2.5 text-sm sm:text-base font-bold text-ink hover:opacity-90 transition-opacity shadow-lg disabled:opacity-50 cursor-pointer"
              >
                {clearingAll ? 'Clearing All...' : 'Confirm Clear All'}
              </button>
            </div>
          </div>
        </div>
      )}
    </main>
  )
}
