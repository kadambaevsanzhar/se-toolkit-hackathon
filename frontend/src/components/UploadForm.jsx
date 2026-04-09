import { useState, useCallback } from 'react'
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

/**
 * Resize an image to a reasonable size for analysis.
 * Keeps aspect ratio, max 1600px on longest side.
 */
function resizeImage(file, maxDim = 1600) {
  return new Promise((resolve) => {
    const img = new Image()
    img.onload = () => {
      let { width, height } = img
      if (width > maxDim || height > maxDim) {
        if (width > height) {
          height = Math.round((height * maxDim) / width)
          width = maxDim
        } else {
          width = Math.round((width * maxDim) / height)
          height = maxDim
        }
      }
      const canvas = document.createElement('canvas')
      canvas.width = width
      canvas.height = height
      const ctx = canvas.getContext('2d')
      ctx.drawImage(img, 0, 0, width, height)
      canvas.toBlob((blob) => {
        resolve(blob || file)
      }, 'image/jpeg', 0.85)
    }
    img.onerror = () => resolve(file)
    img.src = URL.createObjectURL(file)
  })
}

/** Stages for the frontend progress indicator */
const STAGES = [
  { key: 'uploading', label: '📤 Uploading image...', icon: '📤' },
  { key: 'uploaded', label: '✅ Image uploaded', icon: '✅' },
  { key: 'analyzing', label: '🤖 Analyzing with AI...', icon: '🤖' },
  { key: 'validating', label: '🔍 Validating result...', icon: '🔍' },
  { key: 'completed', label: '✅ Analysis completed', icon: '✅' },
  { key: 'failed', label: '❌ Analysis failed', icon: '❌' },
]

function UploadForm({ onSubmit }) {
  const [file, setFile] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [progressStage, setProgressStage] = useState(null) // null, or stage key from STAGES

  const handleFileChange = useCallback((e) => {
    const selectedFile = e.target.files[0]
    if (selectedFile && selectedFile.type.startsWith('image/')) {
      setFile(selectedFile)
      setError(null)
      setProgressStage(null)
    } else {
      setError('Please select a valid image file (JPEG, PNG, etc.)')
      setFile(null)
      setProgressStage(null)
    }
  }, [])

  const handleSubmit = useCallback(async (e) => {
    e.preventDefault()
    if (!file) {
      setError('Please select a file first')
      return
    }

    setLoading(true)
    setError(null)
    setProgressStage('uploading')

    try {
      // Stage 1: Uploading
      setProgressStage('uploading')
      const processedFile = await resizeImage(file)

      const formData = new FormData()
      const filename = file.name.replace(/\.[^.]+$/, '.jpg')
      formData.append('file', processedFile, filename)

      const sessionId = getSessionId()
      const apiBase = getApiBase()

      console.log(`[Upload] Sending ${processedFile.size} bytes to ${apiBase}/analyze, session=${sessionId}`)

      // Stage 2: Upload complete, analyzing
      setProgressStage('uploaded')
      // Simulate brief pause to show transition, then start analyzing
      setProgressStage('analyzing')

      const response = await axios.post(`${apiBase}/analyze`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
          'X-Session-ID': sessionId,
        },
        timeout: 180000, // 3 minutes max
      })

      console.log('[Upload] Success:', response.data)

      // Stage 3: Backend done, show validating then completed
      const result = response.data.result
      const validatorFailed = (result.validator_flags || []).includes('validator_failed')
      const isPreliminary = validatorFailed || result.is_valid === false

      setProgressStage('validating')
      await new Promise(r => setTimeout(r, 500)) // Brief visual pause
      setProgressStage(isPreliminary ? 'completed' : 'completed')

      onSubmit(response.data)
    } catch (err) {
      const detail = err.response?.data?.detail || 'Analysis failed. Please check your connection and try again.'
      setError(detail)
      setProgressStage('failed')
      console.error('[Upload] Error:', err.response?.data || err.message)
    } finally {
      setLoading(false)
    }
  }, [file, onSubmit])

  return (
    <div className="upload-form">
      <h2>Upload Homework Photo</h2>

      {/* Progress indicator */}
      {progressStage && (
        <div className={`progress-panel stage-${progressStage}`}>
          <div className="progress-bar-container">
            <div className="progress-bar" style={{ width: `${getProgressWidth(progressStage)}%` }}></div>
          </div>
          <div className="progress-stages">
            {STAGES.map((stage) => {
              const isActive = stage.key === progressStage
              const isDone = getStageIndex(progressStage) > getStageIndex(stage.key)
              return (
                <div
                  key={stage.key}
                  className={`progress-stage ${isActive ? 'active' : ''} ${isDone ? 'done' : ''}`}
                >
                  <span className="stage-icon">{stage.icon}</span>
                  <span className="stage-label">{stage.label}</span>
                </div>
              )
            })}
          </div>
        </div>
      )}

      <form onSubmit={handleSubmit}>
        <div className="file-input">
          <input
            type="file"
            accept="image/*"
            onChange={handleFileChange}
            disabled={loading}
            id="file-upload"
          />
          <label htmlFor="file-upload" className="file-label">
            Choose Image
          </label>
        </div>

        {file && <p className="file-name">Selected: {file.name} ({(file.size / 1024).toFixed(0)} KB)</p>}

        <button
          type="submit"
          disabled={!file || loading}
          className="submit-btn"
        >
          {loading ? 'Processing...' : 'Analyze Homework'}
        </button>

        {error && <p className="error">{error}</p>}
      </form>
    </div>
  )
}

/** Calculate progress bar width based on stage */
function getProgressWidth(stage) {
  if (!stage) return 0
  const idx = getStageIndex(stage)
  return Math.min(100, ((idx + 1) / STAGES.length) * 100)
}

function getStageIndex(stage) {
  const idx = STAGES.findIndex(s => s.key === stage)
  return idx >= 0 ? idx : 0
}

export default UploadForm
