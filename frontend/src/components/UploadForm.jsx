import { useState } from 'react'
import axios from 'axios'

function UploadForm({ onSubmit }) {
  const [file, setFile] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const handleFileChange = (e) => {
    const selectedFile = e.target.files[0]
    if (selectedFile && selectedFile.type.startsWith('image/')) {
      setFile(selectedFile)
      setError(null)
    } else {
      setError('Please select a valid image file')
      setFile(null)
    }
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!file) {
      setError('Please select a file')
      return
    }

    setLoading(true)
    setError(null)

    const formData = new FormData()
    formData.append('file', file)

    try {
      const apiBase = import.meta.env.VITE_API_URL || '';
      const response = await axios.post(`${apiBase}/analyze`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      })
      onSubmit(response.data)
    } catch (err) {
      setError(err.response?.data?.detail || 'Analysis failed. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="upload-form">
      <h2>Upload Homework Photo</h2>
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

        {file && <p className="file-name">Selected: {file.name}</p>}

        <button
          type="submit"
          disabled={!file || loading}
          className="submit-btn"
        >
          {loading ? 'Analyzing...' : 'Analyze Homework'}
        </button>

        {error && <p className="error">{error}</p>}
      </form>
    </div>
  )
}

export default UploadForm
