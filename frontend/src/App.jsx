import { useState, useEffect } from 'react'
import SessionCard from './SessionCard'
import ToolsPanel from './ToolsPanel'

export default function App() {
  const [session, setSession] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const sessionId = params.get('session')

    if (!sessionId) {
      setLoading(false)
      return
    }

    fetch(`/api/session/${sessionId}`)
      .then(r => r.json())
      .then(data => {
        if (!data.error) setSession({ ...data, sessionId })
      })
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <div style={{padding:'2rem'}}>Verificando sesión...</div>

  return (
    <div style={{maxWidth:'800px', margin:'0 auto', padding:'2rem', fontFamily:'sans-serif'}}>
      <h1 style={{marginBottom:'2rem'}}>MCP Server Prototype</h1>
      <SessionCard session={session} />
      {session && <ToolsPanel session={session} />}
    </div>
  )
}