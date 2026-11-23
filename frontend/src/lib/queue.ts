import type { AnswerResult, QuizQuestion } from './api'

const STORAGE_KEY = 'toistokone.practice-queue.v1'

export type SavedAnswer = {
  questionId: string
  selectedOptionId: string
  attemptId: string
  submitted: boolean
  result?: AnswerResult
}

export type SavedPracticeState = {
  schemaVersion: 2
  contentRevision: string
  queue: QuizQuestion[]
  capacity: number
  currentAnswer?: SavedAnswer
}

export function cardKey(question: QuizQuestion): string {
  return `${question.card.type}\u0000${question.card.base_word}\u0000${question.card.target_form}`
}

function isQuestion(value: unknown): value is QuizQuestion {
  if (!value || typeof value !== 'object') return false
  const question = value as Partial<QuizQuestion>
  return typeof question.question_id === 'string' && typeof question.prompt === 'string' && Array.isArray(question.options) && Array.isArray(question.english_translations) && !!question.card
}

export function loadPracticeState(): SavedPracticeState | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return null
    const saved = JSON.parse(raw) as Partial<SavedPracticeState>
    if (saved.schemaVersion !== 2 || typeof saved.contentRevision !== 'string' || !Array.isArray(saved.queue) || !saved.queue.every(isQuestion) || typeof saved.capacity !== 'number' || saved.capacity < saved.queue.length) return null
    if (saved.currentAnswer && (typeof saved.currentAnswer.questionId !== 'string' || typeof saved.currentAnswer.selectedOptionId !== 'string' || typeof saved.currentAnswer.attemptId !== 'string' || typeof saved.currentAnswer.submitted !== 'boolean' || saved.queue[0]?.question_id !== saved.currentAnswer.questionId)) return null
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
