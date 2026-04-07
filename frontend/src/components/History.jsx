import { useState, useEffect } from 'react'
import axios from 'axios'

function History() {
  const [history, setHistory] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    const fetchHistory = async () => {
      setLoading(true)
      setError(null)
      try {
        const apiBase = import.meta.env.VITE_API_URL || ''
        const response = await axios.get(`${apiBase}/history`)
        setHistory(response.data)
      } catch (err) {
        setError(err.response?.data?.detail || 'Failed to load history')
      } finally {
        setLoading(false)
      }
    }

    fetchHistory()
  }, [])

  const formatDate = (dateString) => {
    const date = new Date(dateString)
    return date.toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    })
  }

  const formatFilename = (filename) => {
    if (!filename) return 'Untitled'
    const name = filename.split('/').pop()
    return name.length > 50 ? name.slice(0, 47) + '...' : name
  }

  const formatFeedback = (feedback) => {
    if (!feedback) return '(No feedback)'
    return feedback.length > 100 ? feedback.slice(0, 97) + '...' : feedback
  }

  if (loading) {
    return (
      <div className="history-container">
        <h2>Previous Submissions</h2>
        <div className="loading">Loading history...</div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="history-container">
        <h2>Previous Submissions</h2>
        <div className="error-message">{error}</div>
      </div>
    )
  }

  if (history.length === 0) {
    return (
      <div className="history-container">
        <h2>Previous Submissions</h2>
        <div className="empty-state">No submissions yet. Start by uploading your first homework photo.</div>
      </div>
    )
  }

  return (
    <div className="history-container">
      <h2>Previous Submissions</h2>
      <div className="history-list">
        {history.map((item) => (
          <div key={item.id} className="history-item">
            <div className="history-header">
              <span className="history-date">{formatDate(item.created_at)}</span>
              <span className="history-score">
                {item.suggested_score !== null ? `${item.suggested_score}/10` : '—'}
              </span>
            </div>
            <div className="history-filename">{formatFilename(item.filename)}</div>
            <div className="history-feedback">{formatFeedback(item.short_feedback)}</div>
          </div>
        ))}
      </div>
    </div>
  )
}

export default History
