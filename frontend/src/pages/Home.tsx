import { type CSSProperties, useEffect, useState } from 'react'
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
        <section className="activity-section" aria-labelledby="activity-heading">
          <div className="activity-heading"><div><p className="eyebrow">Daily activity</p><h2 id="activity-heading">Today’s practice</h2></div><strong>{stats.activity.streak_days} day{stats.activity.streak_days === 1 ? '' : 's'} in a row</strong></div>
          <div className="activity-grid" aria-label="Today’s activity summary">
            <div className="stat"><span>Answers</span><strong>{stats.activity.today.attempts}</strong></div>
            <div className="stat"><span>Accuracy</span><strong>{stats.activity.today.accuracy_percent}%</strong></div>
            <div className="stat"><span>Unique cards</span><strong>{stats.activity.today.unique_cards}</strong></div>
            <div className="stat"><span>Newly mastered</span><strong>{stats.activity.today.newly_mastered}</strong></div>
          </div>
          <p className="activity-detail">{stats.activity.today.score_increases} score increase{stats.activity.today.score_increases === 1 ? '' : 's'} today.</p>
          <div className="activity-trend" aria-label="Attempts over the last 14 days">
            {stats.activity.days.map((day) => {
              const maximum = Math.max(...stats.activity.days.map((item) => item.attempts), 1)
              const height = day.attempts === 0 ? 0 : Math.max(8, day.attempts / maximum * 100)
              const label = new Date(`${day.date}T00:00:00`).toLocaleDateString(undefined, { weekday: 'narrow' })
              return <div className="activity-day" key={day.date} aria-label={`${day.date}: ${day.attempts} answers, ${day.accuracy_percent}% accuracy`}>
                <div className="activity-bar-track"><div className="activity-bar" style={{ height: `${height}%` } as CSSProperties} /></div>
                <small>{label}</small>
              </div>
            })}
          </div>
        </section>
      </>}
      <div className="home-actions">
        <Link className="button" to="/practice">Start Practicing</Link>
        <Link className="button secondary" to="/recommendations">Word recommendations</Link>
      </div>
    </section>
  )
}
