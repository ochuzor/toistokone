import { useState } from 'react'
import { Route, Routes } from 'react-router-dom'

import Home from './pages/Home'
import Practice, { type PracticeSession } from './pages/Practice'

export default function App() {
  const [practiceSession, setPracticeSession] = useState<PracticeSession | null>(null)

  return (
    <main className="app-shell">
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/practice" element={<Practice session={practiceSession} setSession={setPracticeSession} />} />
      </Routes>
    </main>
  )
}
