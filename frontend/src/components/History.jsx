import { useState, useEffect } from 'react'
import axios from 'axios'
import { safeUUID } from '../utils'

function getSessionId() {
  let sid = localStorage.getItem('ai-grader-session-id')
  if (!sid) {
    sid = 'web-' + safeUUID()
    localStorage.setItem('ai-grader-session-id', sid)
  }
  return sid
}

function getApiBase() {
  const buildTimeBase = import.meta.env.VITE_API_URL
  if (!buildTimeBase || buildTimeBase.includes('backend') || buildTimeBase.includes('host.docker')) {
    return `${window.location.protocol}//${window.location.hostname}:8000`
  }
  return buildTimeBase
}

function formatLocalTime(isoString) {
  if (!isoString) return '—'
  const date = new Date(isoString)
  return date.toLocaleString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function History({ sessionId }) {
  const [history, setHistory] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [selectedItem, setSelectedItem] = useState(null)

  useEffect(() => {
    const sid = sessionId || getSessionId()
    let cancelled = false
    const fetchHistory = async () => {
      if (!cancelled) {
        setLoading(true)
        setError(null)
        setSelectedItem(null)
      }
      try {
        const apiBase = getApiBase()
        const response = await axios.get(`${apiBase}/history`, {
          headers: { 'X-Session-ID': sid },
        })
        if (!cancelled) {
          setHistory(response.data)
          console.log('[History] Fetched', response.data.length, 'items for session', sid)
        }
      } catch (err) {
        if (!cancelled) {
          setError(err.response?.data?.detail || 'Failed to load history')
          console.error('[History] Error:', err.response?.data || err.message)
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    fetchHistory()
    return () => { cancelled = true }
  }, [sessionId])

  const handleItemClick = async (item) => {
    try {
      const apiBase = getApiBase()
      const response = await axios.get(`${apiBase}/result/${item.id}`, {
        headers: { 'X-Session-ID': sessionId || getSessionId() },
      })
      setSelectedItem(response.data)
    } catch (err) {
      console.error('[History] Failed to fetch details:', err)
    }
  }

  const handleBack = () => setSelectedItem(null)

  const formatFilename = (filename) => {
    if (!filename) return 'Untitled'
    return filename.split('/').pop()
  }

  const formatFeedback = (feedback) => {
    if (!feedback) return '(No feedback)'
    return feedback.length > 100 ? feedback.slice(0, 97) + '...' : feedback
  }

  // Full detail view
  if (selectedItem && selectedItem.result) {
    const r = selectedItem.result
    const showScore = r.suggested_score !== null && r.max_score !== null
    return (
      <div className="history-container">
        <button className="back-btn" onClick={handleBack}>← Back to History</button>
        <h2>Submission #{selectedItem.id} — {formatFilename(selectedItem.filename)}</h2>
        <p className="history-date">{formatLocalTime(selectedItem.created_at)}</p>

        {r.student_name || r.subject || r.topic || r.task_title ? (
          <div className="topic-labels">
            {r.student_name && <span className="topic-badge student">👤 {r.student_name}</span>}
            {r.subject && <span className="topic-badge subject">{r.subject}</span>}
            {r.topic && <span className="topic-badge topic">{r.topic}</span>}
            {r.task_title && <span className="topic-badge task">{r.task_title}</span>}
          </div>
        ) : null}

        <div className="result-card">
          {showScore && <div className="score-section"><h3>Score: {r.suggested_score}/{r.max_score}</h3></div>}

          <div className="feedback-section">
            <h4>Summary</h4>
            <p>{r.short_feedback}</p>
          </div>

          {r.strengths && r.strengths.length > 0 && (
            <div className="strengths-section">
              <h4>✅ Strengths</h4>
              <ul>{r.strengths.map((s, i) => <li key={i}>{s}</li>)}</ul>
            </div>
          )}

          {r.mistakes && r.mistakes.length > 0 && (
            <div className="mistakes-section">
              <h4>⚠️ Areas to Improve</h4>
              <ul>{r.mistakes.map((m, i) => <li key={i}>{m}</li>)}</ul>
            </div>
          )}

          {r.detailed_mistakes && r.detailed_mistakes.length > 0 && (
            <div className="detailed-mistakes-section">
              <h4>📝 Detailed Mistake Analysis</h4>
              {r.detailed_mistakes.map((dm, i) => (
                <div key={i} className="mistake-card">
                  <div className="mistake-header">
                    <span className={`mistake-type-badge ${dm.type}`}>{dm.type?.replace('_', ' ')}</span>
                    {dm.location && <span className="mistake-location">{dm.location}</span>}
                  </div>
                  <p><strong>What&apos;s wrong:</strong> {dm.what}</p>
                  <p><strong>Why:</strong> {dm.why}</p>
                  {dm.how_to_fix && <p><strong>How to fix:</strong> {dm.how_to_fix}</p>}
                </div>
              ))}
            </div>
          )}

          {r.improvement_suggestions && r.improvement_suggestions.length > 0 && (
            <div className="suggestion-section">
              <h4>💡 How to Improve</h4>
              <ul>{r.improvement_suggestions.map((item, i) => <li key={i}>{item}</li>)}</ul>
            </div>
          )}

          {r.next_steps && r.next_steps.length > 0 && (
            <div className="next-steps-section">
              <h4>📚 What to Practice Next</h4>
              <ul>{r.next_steps.map((step, i) => <li key={i}>{step}</li>)}</ul>
            </div>
          )}
        </div>
      </div>
    )
  }

  // List view
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
          <div key={item.id} className="history-item" onClick={() => handleItemClick(item)}>
            <div className="history-header">
              <span className="history-date">{formatLocalTime(item.created_at)}</span>
              <span className="history-score">
                {item.suggested_score !== null ? `${item.suggested_score}/10` : '—'}
              </span>
            </div>
            <div className="history-filename">{formatFilename(item.filename)}</div>
            {(item.student_name || item.subject || item.topic || item.task_title) && (
              <div className="history-topics">
                {item.student_name && <span className="mini-badge student-badge">👤 {item.student_name}</span>}
                {item.subject && <span className="mini-badge">{item.subject}</span>}
                {item.topic && <span className="mini-badge">{item.topic}</span>}
                {item.task_title && <span className="mini-badge">{item.task_title}</span>}
              </div>
            )}
            <div className="history-feedback">{formatFeedback(item.short_feedback)}</div>
          </div>
        ))}
      </div>
    </div>
  )
}

export default History
