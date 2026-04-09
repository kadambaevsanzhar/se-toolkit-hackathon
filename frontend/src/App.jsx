import { useState, useEffect } from 'react'
import './App.css'
import UploadForm from './components/UploadForm'
import ResultDisplay from './components/ResultDisplay'
import History from './components/History'
import { safeUUID } from './utils'

function getSessionId() {
  let sid = localStorage.getItem('ai-grader-session-id')
  if (!sid) {
    sid = 'web-' + safeUUID()
    localStorage.setItem('ai-grader-session-id', sid)
  }
  return sid
}

function App() {
  const [view, setView] = useState('upload')
  const [currentResult, setCurrentResult] = useState(null)
  const [historyKey, setHistoryKey] = useState(0)
  const [appError, setAppError] = useState(null)

  // Defensive: catch any unhandled errors to prevent white screen
  useEffect(() => {
    const handler = (e) => {
      console.error('[App] Unhandled error:', e.error || e.message)
      setAppError('Something went wrong. Please refresh the page.')
    }
    window.addEventListener('error', handler)
    window.addEventListener('unhandledrejection', handler)
    return () => {
      window.removeEventListener('error', handler)
      window.removeEventListener('unhandledrejection', handler)
    }
  }, [])

  const handleUploadSubmit = (result) => {
    setCurrentResult(result)
    setView('result')
    setHistoryKey((k) => k + 1)
  }

  const handleReset = () => {
    setCurrentResult(null)
    setView('upload')
  }

  const sessionId = getSessionId()

  // Always render the shell — never block on async work
  if (appError) {
    return (
      <div className="container">
        <header>
          <h1>AI Homework Feedback Checker</h1>
        </header>
        <div className="error-message" style={{ padding: '40px', textAlign: 'center' }}>
          <h2>⚠️ Application Error</h2>
          <p>{appError}</p>
          <button onClick={() => window.location.reload()}>Refresh Page</button>
        </div>
      </div>
    )
  }

  return (
    <div className="container">
      <header>
        <h1>AI Homework Feedback Checker</h1>
        <p>Upload your homework photo for automatic feedback</p>
      </header>

      <nav className="nav-tabs">
        <button
          className={`nav-btn ${view === 'upload' || view === 'result' ? 'active' : ''}`}
          onClick={handleReset}
        >
          Upload
        </button>
        <button
          className={`nav-btn ${view === 'history' ? 'active' : ''}`}
          onClick={() => {
            setView('history')
            setHistoryKey((k) => k + 1)
          }}
        >
          History
        </button>
      </nav>

      <main>
        {view === 'result' && currentResult ? (
          <ResultDisplay result={currentResult} onReset={handleReset} />
        ) : view === 'upload' ? (
          <UploadForm onSubmit={handleUploadSubmit} />
        ) : (
          <History key={historyKey} sessionId={sessionId} />
        )}
      </main>
    </div>
  )
}

export default App
