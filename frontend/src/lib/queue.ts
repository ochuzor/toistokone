import type { AnswerResult, PracticeSentence, QuizQuestion } from './api'

const STORAGE_KEY = 'toistokone.practice-queue.v1'

export type SavedAnswer = {
  questionId: string
  selectedOptionId: string
  attemptId: string
  submitted: boolean
  result?: AnswerResult
}

export type SavedPracticeState = {
  schemaVersion: 5
  contentRevision: string
  queue: QuizQuestion[]
  capacity: number
  currentAnswer?: SavedAnswer
  quizzesSinceSentenceBreak: number
  nextSentenceBreakAt: number
  sentenceBreak?: PracticeSentence[]
}

type RawSavedPracticeState = Omit<Partial<SavedPracticeState>, 'schemaVersion'> & { schemaVersion?: number }

export function randomSentenceBreakInterval(): number {
  return Math.floor(Math.random() * 8) + 3
}

export function cardKey(question: QuizQuestion): string {
  return `${question.card.type}\u0000${question.card.base_word}\u0000${question.card.target_form}`
}

function isQuestion(value: unknown): value is QuizQuestion {
  if (!value || typeof value !== 'object') return false
  const question = value as Partial<QuizQuestion>
  return typeof question.question_id === 'string' && typeof question.prompt === 'string' && Array.isArray(question.options) && Array.isArray(question.english_translations) && !!question.card
}

function isSentence(value: unknown): value is PracticeSentence {
  if (!value || typeof value !== 'object') return false
  const sentence = value as Partial<PracticeSentence>
  return typeof sentence.finnish === 'string' && Array.isArray(sentence.english_translations) && sentence.english_translations.every((translation) => typeof translation === 'string')
}

export function loadPracticeState(): SavedPracticeState | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return null
    const saved = JSON.parse(raw) as RawSavedPracticeState
    if (saved.schemaVersion !== 5 || typeof saved.contentRevision !== 'string' || !Array.isArray(saved.queue) || !saved.queue.every(isQuestion) || typeof saved.capacity !== 'number' || saved.capacity < saved.queue.length) return null
    if (saved.currentAnswer && (typeof saved.currentAnswer.questionId !== 'string' || typeof saved.currentAnswer.selectedOptionId !== 'string' || typeof saved.currentAnswer.attemptId !== 'string' || typeof saved.currentAnswer.submitted !== 'boolean' || saved.queue[0]?.question_id !== saved.currentAnswer.questionId)) return null
    if (typeof saved.quizzesSinceSentenceBreak !== 'number' || saved.quizzesSinceSentenceBreak < 0 || !Number.isInteger(saved.quizzesSinceSentenceBreak) || typeof saved.nextSentenceBreakAt !== 'number' || saved.nextSentenceBreakAt < 3 || saved.nextSentenceBreakAt > 10 || !Number.isInteger(saved.nextSentenceBreakAt) || (saved.sentenceBreak !== undefined && (!Array.isArray(saved.sentenceBreak) || !saved.sentenceBreak.length || !saved.sentenceBreak.every(isSentence)))) return null
    return saved as SavedPracticeState
  } catch {
    return null
  }
}

export function savePracticeState(state: SavedPracticeState): void {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(state))
}

export function clearPracticeState(): void {
  localStorage.removeItem(STORAGE_KEY)
}
