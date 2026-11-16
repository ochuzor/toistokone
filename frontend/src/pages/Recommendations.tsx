import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import { fetchRecommendations, type Recommendation } from '../lib/api'

export default function Recommendations() {
  const [recommendations, setRecommendations] = useState<Recommendation[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let ignore = false
    void fetchRecommendations().then((response) => {
      if (!ignore) setRecommendations(response)
    }).catch((caught) => {
      if (!ignore) setError(caught instanceof Error ? caught.message : 'Unable to load recommendations.')
    })
    return () => { ignore = true }
  }, [])

  return <section className="card recommendations-card">
    <p className="eyebrow">Recommendations</p>
    <h1>Words to consider next</h1>
    <p className="notice">These are common words found beside your existing vocabulary. Review a word and add it manually to <code>dictionary.txt</code>, then run the import pipeline.</p>
    {error ? <p className="error" role="alert">{error}</p> : recommendations === null ? <p>Finding recommendations…</p> : recommendations.length === 0 ? <p>No contextual recommendations are available yet. Add more sentence content or vocabulary, then run the import pipeline.</p> : <ol className="recommendation-list">{recommendations.map((recommendation) => <li className="recommendation" key={recommendation.word}>
      <div className="recommendation-heading"><strong>{recommendation.word}</strong><span>Frequency rank #{recommendation.frequency_rank}</span></div>
      <small>Found beside {recommendation.related_vocabulary_count} of your vocabulary word{recommendation.related_vocabulary_count === 1 ? '' : 's'}.</small>
      <div className="recommendation-examples">{recommendation.examples.map((example) => <div className="recommendation-example" key={example.finnish}>
        <p>{example.finnish}</p><small>{example.english_translations.join(' / ')}</small>
      </div>)}</div>
    </li>)}</ol>}
    <Link className="back-link" to="/">Back home</Link>
  </section>
}
