import React, { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'

export default function Search() {
  const [results, setResults] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    async function loadArticles() {
      try {
        const data = await api.search('')
        setResults(data || [])
      } catch (err) {
        setError(err.message || 'Failed to load articles.')
      } finally {
        setLoading(false)
      }
    }
    loadArticles()
  }, [])

  return (
    <main className="mx-auto max-w-4xl px-5 py-10">
      {error && (
        <div className="mb-6 p-4 rounded-xl border border-signal/30 bg-signal/10 text-signal text-sm">
          {error}
        </div>
      )}

      {loading && (
        <div className="py-12 text-center text-mute font-mono text-sm">
          Loading published articles...
        </div>
      )}

      {!loading && results.length === 0 && !error && (
        <div className="text-center py-16 border border-dashed border-line rounded-2xl">
          <p className="text-paper font-semibold text-lg">No articles available yet</p>
          <p className="text-mute text-sm mt-1">Process a YouTube video link to generate and publish your first article.</p>
        </div>
      )}

      <div className="grid gap-4 sm:grid-cols-2">
        {results.map((item) => (
          <Link
            key={item.id}
            to={`/article/${item.id}`}
            className="block rounded-xl border border-line bg-panel p-5 transition-all hover:border-wave group"
          >
            <div className="flex items-center justify-between text-xs font-mono text-mute mb-2">
              <span className="uppercase px-2 py-0.5 bg-line/50 rounded text-paper font-semibold">{item.language}</span>
              <span>{new Date(item.created_at).toLocaleDateString()}</span>
            </div>
            <h3 className="font-display text-lg font-semibold text-paper group-hover:text-wave transition-colors line-clamp-2">
              {item.title}
            </h3>
            {item.snippet && (
              <p className="text-sm text-mute mt-2 line-clamp-3 leading-relaxed">
                {item.snippet}
              </p>
            )}
          </Link>
        ))}
      </div>
    </main>
  )
}
