import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import { fetchLearningPaths, type LearningPath } from '../lib/api'

export default function LearningPaths() {
  const [paths, setPaths] = useState<LearningPath[]>([])
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    void fetchLearningPaths()
      .then(setPaths)
      .catch((caught) => setError(caught instanceof Error ? caught.message : 'Unable to load learning paths.'))
      .finally(() => setLoading(false))
  }, [])

  return <section className="card learning-paths-card">
    <p className="eyebrow">Learning paths</p>
    <h1>Follow your learning journey</h1>
    <p className="notice">Paths connect learning sets in sequence. Complete 70% of base cards and 40% of form cards at score 2 or above to open the next set.</p>
    {error && <p className="error" role="alert">{error}</p>}
    {loading ? <p>Loading learning paths…</p> : paths.length === 0 ? <p className="notice">No learning paths imported yet. Add a Markdown file under <code>learning-paths/</code> and rerun the pipeline.</p> : <ul className="learning-path-list">
      {paths.map((path) => <li key={path.key}>
        <Link className="learning-path-link" to={`/learning-paths/${encodeURIComponent(path.key)}`}>{path.title}</Link>
        <small>{path.sets.mastered} / {path.sets.total} sets completed</small>
        {path.completed && <span className="active-set-label">Complete</span>}
      </li>)}
    </ul>}
  </section>
}
