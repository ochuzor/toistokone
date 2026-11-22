import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'

import { fetchBatch, type QuizQuestion, resetMastery, submitAnswer } from '../lib/api'
import { cardKey, clearPracticeState, loadPracticeState, savePracticeState, type SavedAnswer } from '../lib/queue'

function masteryIcon(score: number): string { return ['○', '◔', '◑', '✓'][score] ?? '○' }
function masteryLabel(score: number): string { return ['Not started', 'One correct answer', 'Two correct answers', 'Mastered'][score] ?? 'Not started' }

export default function Practice() {
  const saved = loadPracticeState()
  const [queue, setQueue] = useState<QuizQuestion[]>(() => saved?.queue ?? [])
  const [capacity, setCapacity] = useState(() => saved?.capacity ?? 0)
  const [answer, setAnswer] = useState<SavedAnswer | null>(() => saved?.currentAnswer ?? null)
  const [loading, setLoading] = useState(!saved?.queue.length)
  const [error, setError] = useState<string | null>(null)
  const [refillError, setRefillError] = useState<string | null>(null)
  const refillInFlight = useRef(false)
  const initialLoadInFlight = useRef(false)
  const requestedQueues = useRef(new Set<string>())
  const current = queue[0]
  const result = answer?.result
  const score = result?.score_after ?? current?.score ?? 0

  useEffect(() => {
    if (queue.length) savePracticeState({ schemaVersion: 1, queue, capacity: Math.max(capacity, queue.length), ...(answer ? { currentAnswer: answer } : {}) })
    else if (!loading) clearPracticeState()
  }, [answer, capacity, loading, queue])

  const loadInitialBatch = async () => {
    if (initialLoadInFlight.current) return
    initialLoadInFlight.current = true
    setLoading(true)
    setError(null)
    try {
      const batch = await fetchBatch()
      setQueue(batch)
      setCapacity(batch.length)
      setAnswer(null)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Unable to load practice cards.')
    } finally {
      initialLoadInFlight.current = false
      setLoading(false)
    }
  }

  useEffect(() => { if (!queue.length && loading) void loadInitialBatch() }, [])

  const submitPendingAnswer = async (question: QuizQuestion, pending: SavedAnswer) => {
    setError(null)
    try {
      const response = await submitAnswer(question.card, pending.selectedOptionId, question.correct_option_id, pending.attemptId)
      setAnswer({ ...pending, submitted: true, result: response })
    } catch (caught) { setError(caught instanceof Error ? caught.message : 'Unable to save your answer. Retry to keep this card.') }
  }

  useEffect(() => {
    if (current && answer && answer.questionId === current.question_id && !answer.submitted) void submitPendingAnswer(current, answer)
  }, [])

  useEffect(() => {
    if (!queue.length || queue.length > 3 || refillInFlight.current) return
    const signature = queue.map(cardKey).sort().join('|')
    if (requestedQueues.current.has(signature)) return
    requestedQueues.current.add(signature)
    refillInFlight.current = true
    void fetchBatch().then((batch) => {
      setQueue((remaining) => {
        const existing = new Set(remaining.map(cardKey))
        const additions = batch.filter((question) => !existing.has(cardKey(question)))
        if (additions.length) {
          setCapacity(remaining.length + additions.length)
          setRefillError(null)
          return [...remaining, ...additions]
        }
        setRefillError('No additional cards are available right now.')
        return remaining
      })
    }).catch((caught) => setRefillError(caught instanceof Error ? caught.message : 'Unable to load more cards.')).finally(() => { refillInFlight.current = false })
  }, [queue])

  const chooseOption = (optionId: string) => {
    if (!current || answer) return
    const pending: SavedAnswer = { questionId: current.question_id, selectedOptionId: optionId, attemptId: crypto.randomUUID(), submitted: false }
    setAnswer(pending)
    savePracticeState({ schemaVersion: 1, queue, capacity, currentAnswer: pending })
    void submitPendingAnswer(current, pending)
  }

  const reset = async () => {
    if (!current || !result) return
    try {
      const response = await resetMastery(current.card)
      setAnswer((previous) => previous?.result ? { ...previous, result: { ...previous.result, score_after: response.score, mastered: false } } : previous)
    } catch (caught) { setError(caught instanceof Error ? caught.message : 'Unable to reset mastery.') }
  }

  const next = () => {
    if (!answer?.submitted) return
    setQueue((remaining) => remaining.slice(1))
    setAnswer(null)
    setError(null)
  }

  if (loading) return <section className="card"><p>Loading practice cards…</p></section>
  if (error && !current) return <section className="card"><h1>Practice is unavailable</h1><p role="alert">{error}</p><button className="button" onClick={() => void loadInitialBatch()}>Retry</button></section>
  if (!current) return <section className="card"><h1>No cards available yet</h1><p>Import content or answer vocabulary cards to unlock word forms.</p><button className="button" onClick={() => void loadInitialBatch()}>Retry</button><Link className="button secondary" to="/">Back home</Link></section>

  return <section className={`card practice-card${answer?.submitted ? ' feedback-visible' : ''}`}>
    <div className="practice-header"><div><p className="eyebrow">Practice</p><p className="queue-progress">{queue.length} card{queue.length === 1 ? '' : 's'} remaining</p></div><span aria-label={masteryLabel(score)} className="mastery-icon" title={masteryLabel(score)}>{masteryIcon(score)}</span></div>
    <div className="progress-track" aria-label="Queue progress"><div className="progress-fill" style={{ width: `${capacity ? queue.length / capacity * 100 : 0}%` }} /></div>
    <p className="prompt">{current.prompt}</p>
    {current.english_translations.length > 0 && <p className="translations">{current.english_translations.join(' / ')}</p>}
    {error && <p className="error" role="alert">{error}</p>}
    {refillError && <p className="notice">{refillError}</p>}
    <div className="options" aria-label="Answer choices">{current.options.map((option) => {
      const isCorrect = result && option.id === current.correct_option_id
      const isSelected = option.id === answer?.selectedOptionId
      const feedbackClass = result ? (isCorrect ? ' correct' : isSelected ? ' incorrect' : ' faded') : ''
      return <button className={`option${feedbackClass}`} disabled={!!answer} key={option.id} onClick={() => chooseOption(option.id)}>{option.text}</button>
    })}</div>
    {answer && <div className="feedback" role="status">{result ? <><p>{result.correct ? 'Correct!' : 'Not quite — the correct answer is highlighted.'}</p><button className="text-button" onClick={() => void reset()}>Reset mastery</button><button aria-label="Next" className="button next-button" onClick={next}><span className="next-label">Next</span><span aria-hidden="true" className="next-arrow">→</span></button></> : <><p>Saving your answer…</p>{error && <button className="button" onClick={() => void submitPendingAnswer(current, answer)}>Retry submission</button>}</>}</div>}
    <Link className="back-link" to="/">Back home</Link>
  </section>
}
