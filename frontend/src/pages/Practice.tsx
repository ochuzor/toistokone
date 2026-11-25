import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'

import { fetchBatch, fetchContentVersion, fetchSentenceBreak, type PracticeSentence, type QuizQuestion, resetMastery, submitAnswer } from '../lib/api'
import { cardKey, clearPracticeState, loadPracticeState, randomSentenceBreakInterval, savePracticeState, type SavedAnswer } from '../lib/queue'

function masteryIcon(score: number): string { return ['○', '◔', '◑', '✓'][score] ?? '○' }
function masteryLabel(score: number): string { return ['Not started', 'One correct answer', 'Two correct answers', 'Mastered'][score] ?? 'Not started' }

function splitNominalPrompt(prompt: string): { formName: string; questionCue: string | null } {
  const match = /^(.*?)\s*\(([^()]+)\)$/.exec(prompt)
  return match ? { formName: match[1], questionCue: match[2] } : { formName: prompt, questionCue: null }
}

export default function Practice() {
  const [queue, setQueue] = useState<QuizQuestion[]>([])
  const [capacity, setCapacity] = useState(0)
  const [answer, setAnswer] = useState<SavedAnswer | null>(null)
  const [contentRevision, setContentRevision] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [refillError, setRefillError] = useState<string | null>(null)
  const [queueNotice, setQueueNotice] = useState<string | null>(null)
  const [quizzesSinceSentenceBreak, setQuizzesSinceSentenceBreak] = useState(0)
  const [nextSentenceBreakAt, setNextSentenceBreakAt] = useState(randomSentenceBreakInterval)
  const [sentenceBreak, setSentenceBreak] = useState<PracticeSentence[] | null>(null)
  const [loadingSentenceBreak, setLoadingSentenceBreak] = useState(false)
  const refillInFlight = useRef(false)
  const initialLoadInFlight = useRef(false)
  const initializationInFlight = useRef(false)
  const resumePendingAnswer = useRef(false)
  const requestedQueues = useRef(new Set<string>())
  const current = queue[0]
  const result = answer?.result
  const score = result?.score_after ?? current?.score ?? 0
  const isNominalPrompt = current?.card.type === 'word_form' && (current.card.target_form.startsWith('nominal:') || current.card.target_form.startsWith('nominal-plural:')) && !!current.hint
  const nominalPrompt = isNominalPrompt && current ? splitNominalPrompt(current.prompt) : null

  useEffect(() => {
    if (contentRevision && (queue.length || sentenceBreak)) savePracticeState({ schemaVersion: 4, contentRevision, queue, capacity: Math.max(capacity, queue.length), quizzesSinceSentenceBreak, nextSentenceBreakAt, ...(answer ? { currentAnswer: answer } : {}), ...(sentenceBreak ? { sentenceBreak } : {}) })
    else if (!loading) clearPracticeState()
  }, [answer, capacity, contentRevision, loading, nextSentenceBreakAt, queue, quizzesSinceSentenceBreak, sentenceBreak])

  const loadInitialBatch = async (refreshed = false) => {
    if (initialLoadInFlight.current) return
    initialLoadInFlight.current = true
    setLoading(true)
    setError(null)
    try {
      const batch = await fetchBatch()
      setQueue(batch)
      setCapacity(batch.length)
      setAnswer(null)
      setQuizzesSinceSentenceBreak(0)
      setNextSentenceBreakAt(randomSentenceBreakInterval())
      setSentenceBreak(null)
      setQueueNotice(refreshed ? 'Practice content was updated, so a fresh queue was loaded.' : null)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Unable to load practice cards.')
    } finally {
      initialLoadInFlight.current = false
      setLoading(false)
    }
  }

  const initializePractice = async () => {
    if (initializationInFlight.current) return
    initializationInFlight.current = true
    setLoading(true)
    setError(null)
    try {
      const { revision } = await fetchContentVersion()
      setContentRevision(revision)
      const saved = loadPracticeState()
      if (saved && saved.contentRevision === revision && (saved.queue.length || saved.sentenceBreak?.length)) {
        setQueue(saved.queue)
        setCapacity(saved.capacity)
        setAnswer(saved.currentAnswer ?? null)
        setQuizzesSinceSentenceBreak(saved.quizzesSinceSentenceBreak)
        setNextSentenceBreakAt(saved.nextSentenceBreakAt)
        setSentenceBreak(saved.sentenceBreak ?? null)
        resumePendingAnswer.current = !!saved.currentAnswer && !saved.currentAnswer.submitted
        setQueueNotice(null)
        setLoading(false)
      } else {
        const hadSavedQueue = localStorage.getItem('toistokone.practice-queue.v1') !== null
        clearPracticeState()
        await loadInitialBatch(hadSavedQueue)
      }
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Unable to verify practice content.')
      setLoading(false)
    } finally {
      initializationInFlight.current = false
    }
  }

  useEffect(() => { void initializePractice() }, [])

  const submitPendingAnswer = async (question: QuizQuestion, pending: SavedAnswer) => {
    setError(null)
    try {
      const response = await submitAnswer(question.card, pending.selectedOptionId, question.correct_option_id, pending.attemptId)
      setAnswer({ ...pending, submitted: true, result: response })
    } catch (caught) { setError(caught instanceof Error ? caught.message : 'Unable to save your answer. Retry to keep this card.') }
  }

  useEffect(() => {
    if (resumePendingAnswer.current && current && answer && answer.questionId === current.question_id && !answer.submitted) {
      resumePendingAnswer.current = false
      void submitPendingAnswer(current, answer)
    }
  }, [answer, current])

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
    if (contentRevision) savePracticeState({ schemaVersion: 4, contentRevision, queue, capacity, quizzesSinceSentenceBreak, nextSentenceBreakAt, currentAnswer: pending, ...(sentenceBreak ? { sentenceBreak } : {}) })
    void submitPendingAnswer(current, pending)
  }

  const reset = async () => {
    if (!current || !result) return
    if (!window.confirm('Reset mastery for this card? Its score will return to 0.')) return
    try {
      const response = await resetMastery(current.card)
      setAnswer((previous) => previous?.result ? { ...previous, result: { ...previous.result, score_after: response.score, mastered: false } } : previous)
    } catch (caught) { setError(caught instanceof Error ? caught.message : 'Unable to reset mastery.') }
  }

  const next = async () => {
    if (sentenceBreak) {
      setSentenceBreak(null)
      setQuizzesSinceSentenceBreak(0)
      setNextSentenceBreakAt(randomSentenceBreakInterval())
      return
    }
    if (!answer?.submitted || loadingSentenceBreak) return
    setQueue((remaining) => remaining.slice(1))
    setAnswer(null)
    setError(null)
    const completed = quizzesSinceSentenceBreak + 1
    if (completed < nextSentenceBreakAt) {
      setQuizzesSinceSentenceBreak(completed)
      return
    }
    setQuizzesSinceSentenceBreak(0)
    setLoadingSentenceBreak(true)
    try {
      const sentences = await fetchSentenceBreak()
      if (sentences.length) setSentenceBreak(sentences)
      else setNextSentenceBreakAt(randomSentenceBreakInterval())
    } catch {
      setNextSentenceBreakAt(randomSentenceBreakInterval())
      setQueueNotice('A reading break could not be loaded; practice will continue normally.')
    } finally {
      setLoadingSentenceBreak(false)
    }
  }

  if (loading) return <section className="card"><p>Loading practice cards…</p></section>
  if (error && !current) return <section className="card"><h1>Practice is unavailable</h1><p role="alert">{error}</p><button className="button" onClick={() => void initializePractice()}>Retry</button></section>
  if (loadingSentenceBreak) return <section className="card practice-card"><p className="eyebrow">Reading break</p><p>Preparing sentences…</p></section>
  if (sentenceBreak) return <section className="card practice-card sentence-break">
    <p className="eyebrow">Reading break</p>
    <h1>Read these sentences</h1>
    <div className="sentence-list">{sentenceBreak.map((sentence) => <article className="practice-sentence" key={sentence.finnish}><p>{sentence.finnish}</p>{sentence.english_translations.map((translation) => <small key={translation}>{translation}</small>)}</article>)}</div>
    <button className="button next-button" onClick={() => void next()}>Next</button>
  </section>
  if (!current) return <section className="card"><h1>No cards available yet</h1><p>Import content or answer vocabulary cards to unlock word forms.</p><button className="button" onClick={() => void initializePractice()}>Retry</button><Link className="button secondary" to="/">Back home</Link></section>

  return <section className={`card practice-card${answer?.submitted ? ' feedback-visible' : ''}`}>
    <div className="practice-header"><div><p className="eyebrow">Practice</p><p className="queue-progress">{queue.length} card{queue.length === 1 ? '' : 's'} remaining</p></div><span aria-label={masteryLabel(score)} className="mastery-icon" title={masteryLabel(score)}>{masteryIcon(score)}</span></div>
    <div className="progress-track" aria-label="Queue progress"><div className="progress-fill" style={{ width: `${capacity ? queue.length / capacity * 100 : 0}%` }} /></div>
    {queueNotice && <p className="notice" role="status">{queueNotice}</p>}
    {nominalPrompt ? <div className="nominal-prompt">
      <p className="nominal-base">{current.hint}</p>
      <p className="nominal-instruction">Choose the <strong>{nominalPrompt.formName}</strong>{nominalPrompt.questionCue && <span>{nominalPrompt.questionCue}</span>}</p>
    </div> : <div className={current.hint ? 'form-prompt' : undefined}>
      {current.hint && <p className="prompt-hint"><span>Base form</span>{current.hint}</p>}
      <p className="prompt">{current.prompt}</p>
    </div>}
    {current.english_translations.length > 0 && <p className="translations">{current.english_translations.join(' / ')}</p>}
    {error && <p className="error" role="alert">{error}</p>}
    {refillError && <p className="notice">{refillError}</p>}
    <div className="options" aria-label="Answer choices">{current.options.map((option) => {
      const isCorrect = result && option.id === current.correct_option_id
      const isSelected = option.id === answer?.selectedOptionId
      const feedbackClass = result ? (isCorrect ? ' correct' : isSelected ? ' incorrect' : ' faded') : ''
      return <button className={`option${feedbackClass}`} disabled={!!answer} key={option.id} onClick={() => chooseOption(option.id)}>{option.text}</button>
    })}</div>
    {answer && <div className="feedback" role="status">{result ? <><p>{result.correct ? 'Correct!' : 'Not quite — the correct answer is highlighted.'}</p><button className="text-button" onClick={() => void reset()}>Reset mastery</button><button className="button next-button" onClick={() => void next()}>Next</button></> : <><p>Saving your answer…</p>{error && <button className="button" onClick={() => void submitPendingAnswer(current, answer)}>Retry submission</button>}</>}</div>}
  </section>
}
