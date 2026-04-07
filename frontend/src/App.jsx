import { useState } from 'react'
import './App.css'
import UploadForm from './components/UploadForm'
import ResultDisplay from './components/ResultDisplay'
import History from './components/History'

function App() {
  const [view, setView] = useState('upload') // 'upload', 'history', or 'result'
  const [currentResult, setCurrentResult] = useState(null)

  const handleUploadSubmit = (result) => {
    setCurrentResult(result)
    setView('result')
  }

  const handleReset = () => {
    setCurrentResult(null)
    setView('upload')
  }

  return (
    <div className="container">
      <header>
        <h1>AI Homework Feedback Checker</h1>
        <p>Upload your homework photo for automatic feedback</p>
      </header>

      <nav className="nav-tabs">
        <button
          className={`nav-btn ${view === 'upload' || (view === 'result' && currentResult) ? 'active' : ''}`}
          onClick={() => {
            setView('upload')
            setCurrentResult(null)
          }}
        >
          Upload
        </button>
        <button
          className={`nav-btn ${view === 'history' ? 'active' : ''}`}
          onClick={() => setView('history')}
        >
          History
        </button>
      </nav>

      <main>
        {view === 'upload' && currentResult ? (
          <ResultDisplay result={currentResult} onReset={handleReset} />
        ) : view === 'upload' ? (
          <UploadForm onSubmit={handleUploadSubmit} />
        ) : view === 'history' ? (
          <History />
        ) : (
          <UploadForm onSubmit={handleUploadSubmit} />
        )}
      </main>
    </div>
  )
}

export default App
