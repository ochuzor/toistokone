import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import { fetchBatch, type AnswerResult, type QuizQuestion, resetMastery, submitAnswer } from '../lib/api'

export type PracticeSession = {
  questions: QuizQuestion[]
  selectedOptionId: string | null
  result: AnswerResult | null
}

type PracticeProps = {
  session: PracticeSession | null
  setSession: (session: PracticeSession | null) => void
}

function masteryIcon(score: number): string {
  return ['○', '◔', '◑', '✓'][score] ?? '○'
}

function masteryLabel(score: number): string {
  return ['Not started', 'One correct answer', 'Two correct answers', 'Mastered'][score] ?? 'Not started'
}

export default function Practice({ session, setSession }: PracticeProps) {
  const [questions, setQuestions] = useState<QuizQuestion[]>(() => session?.questions ?? [])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedOptionId, setSelectedOptionId] = useState<string | null>(() => session?.selectedOptionId ?? null)
  const [result, setResult] = useState<AnswerResult | null>(() => session?.result ?? null)
  const [submitting, setSubmitting] = useState(false)
  const [capacity, setCapacity] = useState(() => session?.questions.length ?? 0)

  const loadBatch = async () => {
    setLoading(true)
    setError(null)
    setSelectedOptionId(null)
    setResult(null)
    try {
      const batch = await fetchBatch()
      setQuestions(batch)
      setCapacity(batch.length)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Unable to load practice cards.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (session) {
      setLoading(false)
    } else {
      void loadBatch()
    }
  }, [])

  useEffect(() => {
    setSession(questions.length ? { questions, selectedOptionId, result } : null)
  }, [questions, result, selectedOptionId, setSession])

  const current = questions[0]
  const score = result?.score_after ?? current?.score ?? 0

  const chooseOption = async (optionId: string) => {
    if (!current || selectedOptionId || submitting) return
    setSelectedOptionId(optionId)
    setSubmitting(true)
    try {
      setResult(await submitAnswer(current.card, optionId, current.correct_option_id))
    } catch (caught) {
      setSelectedOptionId(null)
      setError(caught instanceof Error ? caught.message : 'Unable to save your answer.')
    } finally {
      setSubmitting(false)
    }
  }

  const reset = async () => {
    if (!current) return
    try {
      const response = await resetMastery(current.card)
      setResult((previous) => previous ? { ...previous, score_after: response.score, mastered: false } : previous)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Unable to reset mastery.')
    }
  }

  const next = () => {
    setQuestions((remaining) => remaining.slice(1))
    setSelectedOptionId(null)
    setResult(null)
    setError(null)
  }

  if (loading) {
    return <section className="card"><p>Loading practice cards…</p></section>
  }

  if (error && !current) {
    return <section className="card"><h1>Practice is unavailable</h1><p role="alert">{error}</p><button className="button" onClick={() => void loadBatch()}>Retry</button></section>
  }

  if (!current) {
    return <section className="card"><h1>No cards available yet</h1><p>Import content or answer vocabulary cards to unlock word forms.</p><button className="button" onClick={() => void loadBatch()}>Retry</button><Link className="button secondary" to="/">Back home</Link></section>
  }

  return (
    <section className="card practice-card">
      <div className="practice-header">
        <div>
          <p className="eyebrow">Practice</p>
          <p className="queue-progress">{questions.length} card{questions.length === 1 ? '' : 's'} remaining</p>
        </div>
        <span aria-label={masteryLabel(score)} className="mastery-icon" title={masteryLabel(score)}>{masteryIcon(score)}</span>
      </div>
      <div className="progress-track" aria-label="Queue progress"><div className="progress-fill" style={{ width: `${capacity ? questions.length / capacity * 100 : 0}%` }} /></div>
      <p className="prompt">{current.prompt}</p>
      {current.english_translations.length > 0 && <p className="translations">{current.english_translations.join(' / ')}</p>}
      {error && <p className="error" role="alert">{error}</p>}
      <div className="options" aria-label="Answer choices">
        {current.options.map((option) => {
          const isCorrect = result && option.id === current.correct_option_id
          const isSelected = option.id === selectedOptionId
          const feedbackClass = result ? (isCorrect ? ' correct' : isSelected ? ' incorrect' : '') : ''
          return <button className={`option${feedbackClass}`} disabled={selectedOptionId !== null || submitting} key={option.id} onClick={() => void chooseOption(option.id)}>{option.text}</button>
        })}
      </div>
      {result && <div className="feedback" role="status"><p>{result.correct ? 'Correct!' : 'Not quite — the correct answer is highlighted.'}</p><button className="text-button" onClick={() => void reset()}>Reset mastery</button><button className="button" onClick={next}>Next</button></div>}
      <Link className="back-link" to="/">Back home</Link>
    </section>
  )
}
