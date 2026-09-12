const LOCAL_HISTORY_KEY = 'vetri_local_history_v1'

export function getLocalHistory() {
  try {
    const raw = localStorage.getItem(LOCAL_HISTORY_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) ? parsed : []
  } catch (e) {
    console.warn('Failed to read local history from localStorage:', e)
    return []
  }
}

export function saveLocalHistoryItem(videoResult) {
  if (!videoResult) return getLocalHistory()

  try {
    const existing = getLocalHistory()
    
    // Extract primary identifiers and metadata
    const videoId = videoResult.video_id || videoResult.id
    const youtubeId = videoResult.youtube_id || ''
    const articleObj = videoResult.article || (Array.isArray(videoResult.articles) ? videoResult.articles[0] : null)
    const targetId = articleObj?.id || videoResult.article_id || videoId

    const title = videoResult.title || articleObj?.title || 'Untitled video'
    const thumbnailUrl = videoResult.thumbnail_url || (youtubeId ? `https://img.youtube.com/vi/${youtubeId}/hqdefault.jpg` : '')
    const originalLanguage = videoResult.original_language || articleObj?.language || 'en'
    const status = videoResult.status || 'done'
    const createdAt = videoResult.created_at || new Date().toISOString()
    const articles = articleObj ? [{ id: articleObj.id, language: articleObj.language || originalLanguage }] : (videoResult.articles || [])

    const newItem = {
      id: targetId,
      video_id: videoId,
      youtube_id: youtubeId,
      title,
      thumbnail_url: thumbnailUrl,
      original_language: originalLanguage,
      status,
      created_at: createdAt,
      articles,
    }

    // Deduplicate: filter out existing entry with same youtube_id, video_id, or item id
    const filtered = existing.filter(item => {
      if (youtubeId && item.youtube_id === youtubeId) return false
      if (videoId && item.video_id === videoId) return false
      if (targetId && item.id === targetId) return false
      return true
    })

    // Prepend new item to the top
    const updated = [newItem, ...filtered]
    localStorage.setItem(LOCAL_HISTORY_KEY, JSON.stringify(updated))
    return updated
  } catch (e) {
    console.warn('Failed to save item to local history:', e)
    return getLocalHistory()
  }
}

export function deleteLocalHistoryItem(id) {
  try {
    const existing = getLocalHistory()
    const updated = existing.filter(item => {
      if (item.id === id || item.video_id === id || String(item.id) === String(id) || String(item.video_id) === String(id)) {
        return false
      }
      if (item.articles && item.articles.some(a => a.id === id || String(a.id) === String(id))) {
        return false
      }
      return true
    })
    localStorage.setItem(LOCAL_HISTORY_KEY, JSON.stringify(updated))
    return updated
  } catch (e) {
    console.warn('Failed to delete item from local history:', e)
    return getLocalHistory()
  }
}

export function clearLocalHistory() {
  try {
    localStorage.setItem(LOCAL_HISTORY_KEY, JSON.stringify([]))
  } catch (e) {
    console.warn('Failed to clear local history:', e)
  }
  return []
}
