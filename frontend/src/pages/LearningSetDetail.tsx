import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { fetchLearningSet, setActiveLearningSet, type LearningSetDetail } from '../lib/api'

function masteryIcon(score: number): string { return ['○', '◔', '◑', '✓'][score] ?? '○' }
function masteryLabel(score: number): string { return ['Not started', 'One correct answer', 'Two correct answers', 'Mastered'][score] ?? 'Not started' }

export default function LearningSetDetailPage() {
  const { setKey = '' } = useParams()
  const [learningSet, setLearningSet] = useState<LearningSetDetail | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  const refresh = async () => {
    setLoading(true)
    setError(null)
    try {
      setLearningSet(await fetchLearningSet(setKey))
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Unable to load this learning set.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { void refresh() }, [setKey])

  const select = async () => {
    if (!learningSet) return
    try {
      await setActiveLearningSet(learningSet.active ? null : learningSet.key)
      await refresh()
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Unable to update the active learning set.')
    }
  }

  return <section className="card learning-set-detail-card">
    <Link className="back-link" to="/learning-sets">← Learning sets</Link>
    {error && <p className="error" role="alert">{error}</p>}
    {loading ? <p>Loading learning set…</p> : learningSet && <>
      <p className="eyebrow">Learning set</p>
      <div className="learning-set-detail-heading">
        <h1>{learningSet.title}</h1>
        {learningSet.active && <span className="active-set-label">Active</span>}
      </div>
      <p className="notice">Base-card mastery is shown beside each word. Form progress counts only mastered form cards.</p>
      <button className="button small-button" onClick={() => void select()}>{learningSet.active ? 'Clear active set' : 'Make active'}</button>
      <ul className="learning-set-word-list">
        {learningSet.words.map((word) => <li key={word.finnish}>
          <span aria-label={masteryLabel(word.score)} className="learning-set-mastery-icon" title={masteryLabel(word.score)}>{masteryIcon(word.score)}</span>
          <div>
            <strong>{word.finnish}</strong>
            <span>{word.meanings.join(' / ')}</span>
            <small>{word.word_forms.mastered} / {word.word_forms.total} forms mastered</small>
          </div>
        </li>)}
      </ul>
    </>}
  </section>
}
