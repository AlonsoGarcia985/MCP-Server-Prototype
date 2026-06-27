import { useState } from 'react'

const TOOLS = [
  { name: 'echo', label: 'Echo', hasInput: true, placeholder: 'Escribe un mensaje...' },
  { name: 'get_my_profile', label: 'Mi perfil', hasInput: false },
  { name: 'list_my_permissions', label: 'Mis permisos', hasInput: false },
  { name: 'get_server_info', label: 'Info del servidor', hasInput: false },
]

export default function ToolsPanel({ session }) {
  const [activeTool, setActiveTool] = useState(TOOLS[0])
  const [input, setInput] = useState('')
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(false)

  async function callTool() {
    setLoading(true)
    setResult(null)
    setError(null)
    try {
      const resp = await fetch('/api/call-tool', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: session.sessionId,
          tool: activeTool.name,
          arguments: activeTool.hasInput ? { message: input } : {}
        })
      })
      const data = await resp.json()
      if (data.error) setError(data.error)
      else setResult(data.result)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{border:'1px solid #ccc', borderRadius:'8px', padding:'1.5rem'}}>
      <h2 style={{marginTop:0}}>🔧 Tools del MCP</h2>

      <div style={{display:'flex', gap:'0.5rem', marginBottom:'1rem', flexWrap:'wrap'}}>
        {TOOLS.map(t => (
          <button key={t.name}
            onClick={() => { setActiveTool(t); setInput(''); setResult(null); setError(null) }}
            style={{
              padding:'0.4rem 1rem', borderRadius:'4px', cursor:'pointer',
              background: activeTool.name === t.name ? '#1a73e8' : '#f0f0f0',
              color: activeTool.name === t.name ? 'white' : '#333',
              border: '1px solid #ccc'
            }}>
            {t.label}
          </button>
        ))}
      </div>

      {activeTool.hasInput && (
        <input
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && callTool()}
          placeholder={activeTool.placeholder}
          style={{width:'100%', padding:'0.5rem', marginBottom:'1rem', borderRadius:'4px', border:'1px solid #ccc', boxSizing:'border-box'}}
        />
      )}

      <button
        onClick={callTool}
        disabled={loading || (activeTool.hasInput && !input.trim())}
        style={{
          padding:'0.5rem 1.5rem', background:'#1a73e8', color:'white',
          border:'none', borderRadius:'4px', cursor:'pointer', marginBottom:'1rem'
        }}>
        {loading ? 'Llamando...' : `Llamar ${activeTool.label}`}
      </button>

      {error && (
        <div style={{background:'#fff0f0', border:'1px solid #f44', borderRadius:'4px', padding:'1rem', color:'#c00'}}>
          <strong>Error:</strong> {error}
        </div>
      )}

      {result && (
        <div style={{background:'#f5f5f5', border:'1px solid #ddd', borderRadius:'4px', padding:'1rem'}}>
          <strong>Respuesta:</strong>
          <pre style={{margin:'0.5rem 0 0', fontFamily:'monospace', fontSize:'0.85rem', whiteSpace:'pre-wrap'}}>{result}</pre>
        </div>
      )}
    </div>
  )
}