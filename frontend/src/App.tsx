import { NavLink, Route, Routes, useLocation } from 'react-router-dom'

import Home from './pages/Home'
import FocusWords from './pages/FocusWords'
import ContentHealth from './pages/ContentHealth'
import Practice from './pages/Practice'
import Recommendations from './pages/Recommendations'
import LearningSets from './pages/LearningSets'
import LearningSetDetail from './pages/LearningSetDetail'
import LearningPaths from './pages/LearningPaths'
import LearningPathDetail from './pages/LearningPathDetail'

export default function App() {
  const location = useLocation()
  const isPractice = location.pathname === '/practice'

  return (
    <div className={`app-shell${isPractice ? ' is-practice' : ''}`}>
      <header className="site-header">
        <NavLink className="site-brand" to="/">ToistoKone</NavLink>
        <nav aria-label="Main navigation" className="site-nav">
          <NavLink end to="/">Home</NavLink>
          <NavLink to="/practice">Practice</NavLink>
          <NavLink to="/recommendations">Recommendations</NavLink>
          <NavLink to="/focus-words">Focus words</NavLink>
          <NavLink to="/learning-sets">Learning sets</NavLink>
          <NavLink to="/learning-paths">Learning paths</NavLink>
          <NavLink to="/content-health">Content health</NavLink>
        </nav>
      </header>
      <main className="page-content">
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/practice" element={<Practice />} />
          <Route path="/recommendations" element={<Recommendations />} />
          <Route path="/focus-words" element={<FocusWords />} />
          <Route path="/learning-sets" element={<LearningSets />} />
          <Route path="/learning-sets/:setKey" element={<LearningSetDetail />} />
          <Route path="/learning-paths" element={<LearningPaths />} />
          <Route path="/learning-paths/:pathKey" element={<LearningPathDetail />} />
          <Route path="/content-health" element={<ContentHealth />} />
        </Routes>
      </main>
    </div>
  )
}
