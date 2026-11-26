import { Fragment, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { fetchGrammarGuide, type GrammarGuideDetail } from '../lib/api'

function inlineMarkdown(text: string) {
  return text.split(/(\*\*[^*]+\*\*|\*[^*]+\*)/).filter(Boolean).map((part, index) => {
    if (part.startsWith('**')) return <strong key={index}>{part.slice(2, -2)}</strong>
    if (part.startsWith('*')) return <em key={index}>{part.slice(1, -1)}</em>
    return <Fragment key={index}>{part}</Fragment>
  })
}

function guideBody(markdown: string) {
  return markdown.split('\n\n').filter(Boolean).map((block, index) => {
    if (block.startsWith('## ')) return <h2 key={index}>{block.slice(3)}</h2>
    return <p key={index}>{inlineMarkdown(block)}</p>
  })
}

export default function GrammarGuideDetail() {
  const { guideKey = '' } = useParams()
  const [guide, setGuide] = useState<GrammarGuideDetail | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => { void fetchGrammarGuide(guideKey).then(setGuide).catch((caught) => setError(caught instanceof Error ? caught.message : 'Unable to load this grammar guide.')) }, [guideKey])
  if (error) return <section className="card"><Link className="back-link" to="/practice">Back to practice</Link><p className="error" role="alert">{error}</p></section>
  if (!guide) return <section className="card"><p>Loading grammar guide…</p></section>
  return <section className="card grammar-guide-detail-card"><Link className="back-link" to="/practice">Back to practice</Link><p className="eyebrow">Grammar guide</p><h1>{guide.title}</h1><p className="grammar-guide-summary">{guide.summary}</p><div className="grammar-guide-examples">{guide.examples.map((example) => <p key={example.finnish}><strong>{example.finnish}</strong><span>{example.english}</span></p>)}</div><div className="grammar-guide-body">{guideBody(guide.details_markdown)}</div></section>
}
