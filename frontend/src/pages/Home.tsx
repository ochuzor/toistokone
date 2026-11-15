import { Link } from 'react-router-dom'

export default function Home() {
  return (
    <section className="card">
      <p className="eyebrow">ToistoKone</p>
      <h1>Practice Finnish, one repetition at a time.</h1>
      <p>Vocabulary and word-form practice will appear here as the next phases are completed.</p>
      <Link className="button" to="/practice">Start Practicing</Link>
    </section>
  )
}
