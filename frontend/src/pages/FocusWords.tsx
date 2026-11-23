import { FormEvent, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import { addFocusWord, fetchFocusWords, fetchVocabulary, removeFocusWord, type VocabularyEntry } from '../lib/api'

function isNew(entry: VocabularyEntry): boolean {
  return entry.score === 0 && entry.last_practiced_at === null
}

export default function FocusWords() {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<VocabularyEntry[]>([])
  const [focused, setFocused] = useState<VocabularyEntry[]>([])
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const refresh = async (searchQuery: string) => {
    setLoading(true)
    setError(null)
    try {
      const [vocabulary, queued] = await Promise.all([fetchVocabulary(searchQuery), fetchFocusWords()])
      setResults(vocabulary)
      setFocused(queued)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Unable to load vocabulary.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { void refresh('') }, [])

  const submitSearch = (event: FormEvent) => {
    event.preventDefault()
    void refresh(query)
  }

  const focus = async (entry: VocabularyEntry) => {
    try {
      await addFocusWord(entry.finnish)
      await refresh(query)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Unable to add the focus word.')
    }
  }

  const remove = async (entry: VocabularyEntry) => {
    try {
      await removeFocusWord(entry.finnish)
      await refresh(query)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Unable to remove the focus word.')
    }
  }

  return <section className="card focus-card">
    <p className="eyebrow">Focus words</p>
    <h1>Bring class vocabulary in next</h1>
    <p className="notice">Choose a new dictionary word to use the next available new-vocabulary slot. The request clears once it enters a generated batch.</p>
    <form className="focus-search" onSubmit={submitSearch}>
      <label htmlFor="word-search">Search Finnish or English</label>
      <div><input id="word-search" value={query} onChange={(event) => setQuery(event.target.value)} /><button className="button" type="submit">Search</button></div>
    </form>
    {error && <p className="error" role="alert">{error}</p>}
    <section aria-labelledby="focused-heading">
      <h2 id="focused-heading">Queued for next available batch</h2>
      {focused.length === 0 ? <p className="notice">No focus words selected.</p> : <ul className="focus-list">{focused.map((entry) => <li key={entry.finnish}><div><strong>{entry.finnish}</strong><small>{entry.meanings.join(' / ')}</small></div><button className="text-button" onClick={() => void remove(entry)}>Remove</button></li>)}</ul>}
    </section>
    <section aria-labelledby="search-results-heading">
      <h2 id="search-results-heading">{loading ? 'Searching…' : 'Dictionary words'}</h2>
      {!loading && <ul className="focus-list">{results.map((entry) => <li key={entry.finnish}><div><strong>{entry.finnish}</strong><small>{entry.meanings.join(' / ')}</small></div>{entry.focus_requested_at ? <span className="notice">Queued</span> : isNew(entry) ? <button className="button small-button" onClick={() => void focus(entry)}>Add next</button> : <span className="notice">Already practised</span>}</li>)}</ul>}
    </section>
    <Link className="back-link" to="/">Back home</Link>
  </section>
}
