import { Route, Routes } from 'react-router-dom'

import Home from './pages/Home'
import Practice from './pages/Practice'
import Recommendations from './pages/Recommendations'

export default function App() {
  return (
    <main className="app-shell">
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/practice" element={<Practice />} />
        <Route path="/recommendations" element={<Recommendations />} />
      </Routes>
    </main>
  )
}
