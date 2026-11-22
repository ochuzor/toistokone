export type CardReference = {
  type: 'vocabulary' | 'word_form'
  base_word: string
  target_form: string
}

export type QuizQuestion = {
  question_id: string
  card: CardReference
  score: number
  prompt: string
  english_translations: string[]
  options: { id: string; text: string }[]
  correct_option_id: string
}

export type AnswerResult = {
  correct: boolean
  score_before: number
  score_after: number
  mastered: boolean
}

export type Stats = {
  vocabulary: { total: number; mastered: number }
  word_forms: { total: number; mastered: number }
  overall: { total: number; mastered: number; mastery_percent: number }
}

export type Recommendation = {
  word: string
  frequency_rank: number
  frequency_count: number
  related_vocabulary_count: number
  observed_forms: string[]
  examples: { finnish: string; english_translations: string[] }[]
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(path, options)
  if (!response.ok) {
    const body = await response.json().catch(() => ({})) as { detail?: string }
    throw new Error(body.detail ?? 'Something went wrong. Please try again.')
  }
  return response.json() as Promise<T>
}

export async function fetchBatch(): Promise<QuizQuestion[]> {
  const response = await request<{ questions: QuizQuestion[] }>('/api/quiz/batch', { method: 'POST' })
  return response.questions
}

export function fetchStats(): Promise<Stats> {
  return request<Stats>('/api/stats')
}

export async function fetchRecommendations(): Promise<Recommendation[]> {
  const response = await request<{ recommendations: Recommendation[] }>('/api/recommendations')
  return response.recommendations
}

export function submitAnswer(card: CardReference, selectedOptionId: string, correctOptionId: string, attemptId: string): Promise<AnswerResult> {
  return request<AnswerResult>('/api/answers', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      attempt_id: attemptId,
      card,
      selected_option_id: selectedOptionId,
      correct_option_id: correctOptionId,
    }),
  })
}

export function resetMastery(card: CardReference): Promise<{ score: number }> {
  return request<{ score: number }>('/api/cards/reset', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ card }),
  })
}
