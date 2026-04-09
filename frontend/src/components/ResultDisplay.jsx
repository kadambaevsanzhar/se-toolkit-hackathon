function ResultDisplay({ result, onReset }) {
  if (!result) return null
  const r = result.result

  // Handle non-academic rejection
  if (r.is_academic_submission === false) {
    return (
      <div className="result-container">
        <h2>Submission Review</h2>
        <div className="rejection-card">
          <div className="rejection-icon">📷</div>
          <h3>Not an Academic Submission</h3>
          <p>{r.short_feedback || "The image does not appear to contain readable academic content."}</p>
          {r.supported_action && <p>{r.supported_action}</p>}
          <div className="rejection-suggestion">
            <strong>What you can submit:</strong>
            <ul>
              <li>Photos of homework assignments</li>
              <li>Written solutions or answers</li>
              <li>Worksheets or notebook pages</li>
              <li>Any school/university assignment</li>
            </ul>
          </div>
        </div>
        <button onClick={onReset} className="reset-btn">
          Try Again
        </button>
      </div>
    )
  }

  // Determine analysis status using explicit backend field
  const analysisStatus = r.analysis_status || 'success'
  const isAnalyzerFailed = analysisStatus === 'analyzer_failed'
  const isPreliminary = analysisStatus === 'validator_failed' || r.is_preliminary === true
  const isValidated = analysisStatus === 'success' && r.validation_status === 'validated' && !isPreliminary

  if (isAnalyzerFailed) {
    return (
      <div className="result-container">
        <h2>Analysis Failed</h2>
        <div className="validation-status preliminary">
          ❌ Analysis could not be completed. {r.validator_reason || r.short_feedback || 'Please try again later.'}
        </div>
        <button onClick={onReset} className="reset-btn">
          Try Again
        </button>
      </div>
    )
  }

  return (
    <div className="result-container">
      {isPreliminary ? (
        <>
          <h2>Preliminary Analysis</h2>
          <div className="validation-status preliminary">
            ⚠️ Preliminary analysis — Final validation was unavailable. Please review the result carefully.
          </div>
        </>
      ) : (
        <>
          <h2>Analysis Result</h2>
          {isValidated && (
            <div className="validation-status validated">
              ✅ Validated by secondary AI reviewer
            </div>
          )}
        </>
      )}

      {/* Student name + Topic labels */}
      <div className="metadata-line">
        {r.student_name && <span className="topic-badge student">👤 {r.student_name}</span>}
        {r.subject && <span className="topic-badge subject">{r.subject}</span>}
        {r.topic && <span className="topic-badge topic">{r.topic}</span>}
        {r.task_title && <span className="topic-badge task">{r.task_title}</span>}
      </div>

        <div className="result-card">
        {/* Score */}
        {r.suggested_score !== null && r.max_score !== null && (
          <div className="score-section">
            <h3>{isPreliminary ? 'Preliminary Score' : 'Score'}: {r.suggested_score}/{r.max_score}</h3>
          </div>
        )}

        {/* Summary */}
        <div className="feedback-section">
          <h4>Summary</h4>
          <p>{r.short_feedback}</p>
        </div>

        {/* Strengths */}
        {r.strengths && r.strengths.length > 0 && (
          <div className="strengths-section">
            <h4>✅ Strengths</h4>
            <ul>
              {r.strengths.map((s, i) => (
                <li key={i}>{s}</li>
              ))}
            </ul>
          </div>
        )}

        {/* Mistakes (summary list) */}
        {r.mistakes && r.mistakes.length > 0 && (
          <div className="mistakes-section">
            <h4>⚠️ Areas to Improve</h4>
            <ul>
              {r.mistakes.map((m, i) => (
                <li key={i}>{m}</li>
              ))}
            </ul>
          </div>
        )}

        {/* Detailed Mistakes — only if entries are complete */}
        {hasCompleteDetailedMistakes(r.detailed_mistakes) && (
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
        {/* Show message if detailed mistakes unavailable */}
        {r.detailed_mistakes && r.detailed_mistakes.length > 0 && !hasCompleteDetailedMistakes(r.detailed_mistakes) && (
          <div className="detailed-mistakes-section">
            <h4>📝 Detailed Mistake Analysis</h4>
            <p className="unavailable-msg">Detailed validation unavailable — insufficient data for full breakdown.</p>
          </div>
        )}

        {/* Improvement Suggestion */}
        {r.improvement_suggestions && r.improvement_suggestions.length > 0 && (
          <div className="suggestion-section">
            <h4>💡 How to Improve</h4>
            <ul>
              {r.improvement_suggestions.map((suggestion, i) => (
                <li key={i}>{suggestion}</li>
              ))}
            </ul>
          </div>
        )}

        {/* Next Steps */}
        {r.next_steps && r.next_steps.length > 0 && (
          <div className="next-steps-section">
            <h4>📚 What to Practice Next</h4>
            <ul>
              {r.next_steps.map((step, i) => (
                <li key={i}>{step}</li>
              ))}
            </ul>
          </div>
        )}

        {/* Validation Flags (dev info) */}
        {r.validator_flags && r.validator_flags.length > 0 && (
          <div className="validator-flags-section">
            <h4>Validation Info</h4>
            <div className="flags-list">
              {r.validator_flags.map((flag, i) => (
                <span key={i} className={`flag-badge flag-${flag}`}>{flag}</span>
              ))}
            </div>
            {r.validator_reason && (
              <p className="validator-reason">Reason: {r.validator_reason}</p>
            )}
          </div>
        )}
      </div>

      <button onClick={onReset} className="reset-btn">
        Analyze Another Homework
      </button>
    </div>
  )
}

/**
 * Check if detailed_mistakes has at least one entry with all required fields non-empty.
 * Supports both old field names (what_is_wrong, why_it_is_wrong, etc.) and new (what, why, how_to_fix).
 */
function hasCompleteDetailedMistakes(mistakes) {
  if (!mistakes || !Array.isArray(mistakes) || mistakes.length === 0) return false
  return mistakes.some(dm => {
    if (!dm || typeof dm !== 'object') return false
    const what = dm.what || dm.what_is_wrong || ''
    const why = dm.why || dm.why_it_is_wrong || ''
    const how = dm.how_to_fix || dm.how_to_avoid_next_time || ''
    const type = dm.type || ''
    return type.trim() && what.trim() && why.trim() && how.trim()
  })
}

export default ResultDisplay
