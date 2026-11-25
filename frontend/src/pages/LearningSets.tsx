import { useEffect, useState } from 'react'

import { fetchLearningSets, setActiveLearningSet, type LearningSet } from '../lib/api'

export default function LearningSets() {
  const [learningSets, setLearningSets] = useState<LearningSet[]>([])
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  const refresh = async () => {
    setLoading(true)
    setError(null)
    try {
      setLearningSets(await fetchLearningSets())
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Unable to load learning sets.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { void refresh() }, [])

  const select = async (setKey: string | null) => {
    try {
      await setActiveLearningSet(setKey)
      await refresh()
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Unable to update the active learning set.')
    }
  }

  return <section className="card learning-sets-card">
    <p className="eyebrow">Learning sets</p>
    <h1>Give your practice a direction</h1>
    <p className="notice">Learning sets come from Markdown files in <code>learning-sets/</code>. An active set gets preference for new cards and contextual reading breaks; normal review remains unchanged.</p>
    {error && <p className="error" role="alert">{error}</p>}
    {loading ? <p>Loading learning sets…</p> : learningSets.length === 0 ? <p className="notice">No learning sets imported yet. Add a Markdown file and rerun the pipeline.</p> : <>
      {learningSets.some((learningSet) => learningSet.active) && <button className="text-button" onClick={() => void select(null)}>Clear active set</button>}
      <ul className="learning-set-list">
        {learningSets.map((learningSet) => <li key={learningSet.key} className={learningSet.active ? 'active' : ''}>
          <div>
            <strong>{learningSet.title}</strong>
            <small>{learningSet.words.mastered} / {learningSet.words.total} words mastered · {learningSet.word_forms.mastered} / {learningSet.word_forms.total} forms mastered</small>
          </div>
          {learningSet.active ? <span className="active-set-label">Active</span> : <button className="button small-button" onClick={() => void select(learningSet.key)}>Make active</button>}
        </li>)}
      </ul>
    </>}
  </section>
}
