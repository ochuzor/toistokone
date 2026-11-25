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
  hint?: string | null
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

export type PracticeSentence = {
  finnish: string
  english_translations: string[]
}

export type Stats = {
  vocabulary: { total: number; mastered: number }
  word_forms: { total: number; mastered: number }
  overall: { total: number; mastered: number; mastery_percent: number }
  activity: {
    today: DailyActivity
    days: DailyActivity[]
    streak_days: number
  }
}

export type DailyActivity = {
  date: string
  attempts: number
  correct: number
  accuracy_percent: number
  unique_cards: number
  score_increases: number
  newly_mastered: number
}

export type Recommendation = {
  word: string
  frequency_rank: number
  frequency_count: number
  related_vocabulary_count: number
  observed_forms: string[]
  chain_words: string[]
  examples: { finnish: string; english_translations: string[] }[]
}

export type VocabularyEntry = {
  finnish: string
  meanings: string[]
  score: number
  last_practiced_at: string | null
  focus_requested_at: string | null
}

export type ContentHealthCategory = 'missing_profiles' | 'base_without_sentences' | 'under_supported_forms' | 'untracked_sentences'

export type ContentHealthSummary = Record<ContentHealthCategory, number>

export type ContentHealthFinding = {
  word?: string | null
  base_word?: string | null
  form?: string | null
  prompt_label?: string | null
  sentence_count?: number | null
  finnish?: string | null
  english_translations?: string[] | null
  priority_reason?: string | null
}

export type ContentHealthResponse = {
  summary: ContentHealthSummary
  category: ContentHealthCategory
  offset: number
  total: number
  findings: ContentHealthFinding[]
}

export type LearningSet = {
  key: string
  title: string
  words: { total: number; mastered: number }
  word_forms: { total: number; mastered: number }
  active: boolean
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

export async function fetchSentenceBreak(): Promise<PracticeSentence[]> {
  const response = await request<{ sentences: PracticeSentence[] }>('/api/practice/sentence-break', { method: 'POST' })
  return response.sentences
}

export function fetchContentVersion(): Promise<{ revision: string }> {
  return request('/api/content-version')
}

export function fetchStats(): Promise<Stats> {
  const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC'
  return request<Stats>(`/api/stats?timezone=${encodeURIComponent(timezone)}`)
}

export async function fetchRecommendations(): Promise<Recommendation[]> {
  const response = await request<{ recommendations: Recommendation[] }>('/api/recommendations')
  return response.recommendations
}

export async function fetchVocabulary(query: string): Promise<VocabularyEntry[]> {
  const response = await request<{ vocabulary: VocabularyEntry[] }>(`/api/vocabulary?query=${encodeURIComponent(query)}`)
  return response.vocabulary
}

export async function fetchFocusWords(): Promise<VocabularyEntry[]> {
  const response = await request<{ vocabulary: VocabularyEntry[] }>('/api/focus-words')
  return response.vocabulary
}

export function fetchContentHealth(category: ContentHealthCategory, offset = 0): Promise<ContentHealthResponse> {
  return request(`/api/content-health?category=${category}&offset=${offset}`)
}

export async function fetchLearningSets(): Promise<LearningSet[]> {
  const response = await request<{ learning_sets: LearningSet[] }>('/api/learning-sets')
  return response.learning_sets
}

export function setActiveLearningSet(setKey: string | null): Promise<void> {
  return request('/api/learning-sets/active', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ set_key: setKey }),
  })
}

export async function addFocusWord(baseWord: string): Promise<void> {
  await request('/api/focus-words', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ base_word: baseWord }),
  })
}

export async function removeFocusWord(baseWord: string): Promise<void> {
  await request(`/api/focus-words/${encodeURIComponent(baseWord)}`, { method: 'DELETE' })
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
