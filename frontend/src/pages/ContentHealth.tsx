import { useEffect, useState } from 'react'

import { fetchContentHealth, type ContentHealthCategory, type ContentHealthFinding, type ContentHealthSummary } from '../lib/api'

const categories: { key: ContentHealthCategory; label: string; empty: string }[] = [
  { key: 'missing_profiles', label: 'No grammar profile', empty: 'Every dictionary entry has generated grammar forms.' },
  { key: 'base_without_sentences', label: 'Base words without sentences', empty: 'Every base word has sentence support.' },
  { key: 'under_supported_forms', label: 'Forms with fewer than two sentences', empty: 'Every generated form has at least two supporting sentences.' },
  { key: 'untracked_sentences', label: 'Untracked sentences', empty: 'Every imported sentence contains tracked vocabulary or a generated form.' },
]

function renderFormGroups(findings: ContentHealthFinding[]) {
  const groups = new Map<string, ContentHealthFinding[]>()
  for (const finding of findings) {
    const baseWord = finding.base_word ?? ''
    groups.set(baseWord, [...(groups.get(baseWord) ?? []), finding])
  }
  return [...groups].map(([baseWord, forms]) => <li key={baseWord} className="health-form-group">
    <strong>{baseWord}</strong>
    <ul>
      {forms.map((finding, index) => <li key={`${finding.form}-${finding.prompt_label}-${index}`}>
        <strong>{finding.form}</strong>
        <small>{finding.prompt_label} · {finding.sentence_count} supporting sentence{finding.sentence_count === 1 ? '' : 's'}</small>
        <small>{finding.priority_reason}</small>
      </li>)}
    </ul>
  </li>)
}

function renderFinding(category: ContentHealthCategory, finding: ContentHealthFinding) {
  if (category === 'untracked_sentences') return <><strong>{finding.finnish}</strong>{finding.english_translations?.map((translation) => <small key={translation}>{translation}</small>)}<small>{finding.priority_reason}</small></>
  return <><strong>{finding.word}</strong><small>{finding.priority_reason}</small></>
}

export default function ContentHealth() {
  const [category, setCategory] = useState<ContentHealthCategory>('missing_profiles')
  const [summary, setSummary] = useState<ContentHealthSummary | null>(null)
  const [findings, setFindings] = useState<ContentHealthFinding[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = async (nextCategory: ContentHealthCategory, offset = 0) => {
    setLoading(true)
    setError(null)
    try {
      const response = await fetchContentHealth(nextCategory, offset)
      setSummary(response.summary)
      setTotal(response.total)
      setFindings((previous) => offset ? [...previous, ...response.findings] : response.findings)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Unable to load content health.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { void load(category) }, [category])
  const selected = categories.find((item) => item.key === category)!

  return <section className="card health-card">
    <p className="eyebrow">Content health</p>
    <h1>Review your learning content</h1>
    <p className="notice">Findings are shown in priority order: focus words, recent practice, frequency, and sentence simplicity.</p>
    {error ? <p className="error" role="alert">{error}</p> : <>
      <div className="health-summary" aria-label="Content health summary">{categories.map((item) => <button className={`health-summary-item${category === item.key ? ' active' : ''}`} key={item.key} onClick={() => setCategory(item.key)}><strong>{summary?.[item.key] ?? '–'}</strong><span>{item.label}</span></button>)}</div>
      <section aria-live="polite" aria-label={selected.label}>
        <p className="notice">{loading ? 'Loading findings…' : `${total} finding${total === 1 ? '' : 's'}`}</p>
        {!loading && findings.length === 0 ? <p>{selected.empty}</p> : <ul className="health-list">{category === 'under_supported_forms' ? renderFormGroups(findings) : findings.map((finding, index) => <li key={`${category}-${index}`}>{renderFinding(category, finding)}</li>)}</ul>}
        {!loading && findings.length < total && <button className="button" onClick={() => void load(category, findings.length)}>Show more</button>}
      </section>
    </>}
  </section>
}
