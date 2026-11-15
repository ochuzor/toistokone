import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import { fetchStats, type Stats } from '../lib/api'

export default function Home() {
  const [stats, setStats] = useState<Stats | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let ignore = false
    void fetchStats().then((response) => {
      if (!ignore) setStats(response)
    }).catch((caught) => {
      if (!ignore) setError(caught instanceof Error ? caught.message : 'Unable to load progress.')
    })
    return () => { ignore = true }
  }, [])

  return (
    <section className="card">
      <p className="eyebrow">ToistoKone</p>
      <h1>Practice Finnish, one repetition at a time.</h1>
      {error ? <p className="error" role="alert">{error}</p> : !stats ? <p>Loading your progress…</p> : <>
        <div className="stats-grid" aria-label="Mastery summary">
          <div className="stat"><span>Vocabulary</span><strong>{stats.vocabulary.mastered} / {stats.vocabulary.total}</strong><small>mastered</small></div>
          <div className="stat"><span>Word forms</span><strong>{stats.word_forms.mastered} / {stats.word_forms.total}</strong><small>mastered</small></div>
          <div className="stat overall"><span>Overall mastery</span><strong>{stats.overall.mastery_percent}%</strong><small>{stats.overall.mastered} / {stats.overall.total} cards</small></div>
        </div>
      </>}
      <Link className="button" to="/practice">Start Practicing</Link>
    </section>
  )
}
