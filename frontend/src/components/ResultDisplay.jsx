function ResultDisplay({ result, onReset }) {
  if (!result) return null

  return (
    <div className="result-container">
      <h2>Analysis Result</h2>

      <div className="result-card">
        <div className="score-section">
          <h3>Score: {result.result.suggested_score}/{result.result.max_score}</h3>
        </div>

        <div className="feedback-section">
          <h4>Feedback</h4>
          <p>{result.result.short_feedback}</p>
        </div>

        {result.result.strengths && result.result.strengths.length > 0 && (
          <div className="strengths-section">
            <h4>Strengths</h4>
            <ul>
              {result.result.strengths.map((strength, i) => (
                <li key={i}>{strength}</li>
              ))}
            </ul>
          </div>
        )}

        {result.result.mistakes && result.result.mistakes.length > 0 && (
          <div className="mistakes-section">
            <h4>Areas for Improvement</h4>
            <ul>
              {result.result.mistakes.map((mistake, i) => (
                <li key={i}>{mistake}</li>
              ))}
            </ul>
          </div>
        )}

        {result.result.improvement_suggestion && (
          <div className="suggestion-section">
            <h4>Suggestion</h4>
            <p>{result.result.improvement_suggestion}</p>
          </div>
        )}
      </div>

      <button onClick={onReset} className="reset-btn">
        Analyze Another Homework
      </button>
    </div>
  )
}

export default ResultDisplay
