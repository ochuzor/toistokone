import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { fetchLearningPath, type LearningPathDetail } from '../lib/api'

function progressText(label: string, progress: { qualified: number; total: number; percent: number }) {
  return `${label}: ${progress.qualified} / ${progress.total} at score 2+ (${progress.percent}%)`
}

export default function LearningPathDetailPage() {
  const { pathKey = '' } = useParams()
  const [path, setPath] = useState<LearningPathDetail | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    setError(null)
    void fetchLearningPath(pathKey)
      .then(setPath)
      .catch((caught) => setError(caught instanceof Error ? caught.message : 'Unable to load this learning path.'))
      .finally(() => setLoading(false))
  }, [pathKey])

  return <section className="card learning-path-detail-card">
    <Link className="back-link" to="/learning-paths">← Learning paths</Link>
    {error && <p className="error" role="alert">{error}</p>}
    {loading ? <p>Loading learning path…</p> : path && <>
      <p className="eyebrow">Learning path</p>
      <div className="learning-set-detail-heading">
        <h1>{path.title}</h1>
        {path.completed && <span className="active-set-label">Complete</span>}
      </div>
      <p className="notice">Each step needs 70% of base cards and 40% of forms at score 2 or above. You can still make any set active from its own page.</p>
      <ol className="learning-path-step-list">
        {path.steps.map((step) => <li className={`learning-path-step ${step.state}`} key={step.key}>
          <div className="learning-path-step-heading">
            <span className="learning-path-step-state">{step.state === 'completed' ? '✓' : step.state === 'available' ? '→' : '·'}</span>
            <div>
              <Link to={`/learning-sets/${encodeURIComponent(step.key)}`}>{step.title}</Link>
              <small>{step.state === 'completed' ? 'Completed' : step.state === 'available' ? 'Ready to focus on' : 'Upcoming'}</small>
            </div>
          </div>
          <p>{progressText('Base cards', step.vocabulary)}</p>
          <p>{progressText('Form cards', step.word_forms)}</p>
        </li>)}
      </ol>
    </>}
  </section>
}
