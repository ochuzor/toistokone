import { Link } from 'react-router-dom'

export default function Practice() {
  return (
    <section className="card">
      <p className="eyebrow">Practice</p>
      <h1>Your practice queue is coming soon.</h1>
      <p>Phase 0 confirms that routing and local startup are ready.</p>
      <Link className="button secondary" to="/">Back home</Link>
    </section>
  )
}
