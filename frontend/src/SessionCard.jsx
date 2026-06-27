export default function SessionCard({ session }) {
    if (!session) return (
      <div style={{border:'1px solid #ccc', borderRadius:'8px', padding:'1.5rem', marginBottom:'1.5rem'}}>
        <p>No hay sesión activa.</p>
        <a href="/auth/frontend-login" style={{
          display:'inline-block', marginTop:'1rem', padding:'0.5rem 1.5rem',
          background:'#1a73e8', color:'white', borderRadius:'4px', textDecoration:'none'
        }}>
          Iniciar sesión con Keycloak
        </a>
      </div>
    )
  
    return (
      <div style={{border:'1px solid #4caf50', borderRadius:'8px', padding:'1.5rem', marginBottom:'1.5rem', background:'#f9fff9'}}>
        <h2 style={{marginTop:0}}>✅ Sesión activa</h2>
        <table style={{borderCollapse:'collapse', width:'100%'}}>
          <tbody>
            <tr>
              <td style={{padding:'0.4rem 1rem 0.4rem 0', fontWeight:'bold', color:'#555'}}>Usuario</td>
              <td style={{padding:'0.4rem 0'}}>{session.username}</td>
            </tr>
            <tr>
              <td style={{padding:'0.4rem 1rem 0.4rem 0', fontWeight:'bold', color:'#555'}}>Email</td>
              <td style={{padding:'0.4rem 0'}}>{session.email}</td>
            </tr>
            <tr>
              <td style={{padding:'0.4rem 1rem 0.4rem 0', fontWeight:'bold', color:'#555'}}>Sub (JWT)</td>
              <td style={{padding:'0.4rem 0', fontFamily:'monospace', fontSize:'0.85rem', color:'#333'}}>{session.sub}</td>
            </tr>
            <tr>
              <td style={{padding:'0.4rem 1rem 0.4rem 0', fontWeight:'bold', color:'#555'}}>Session ID</td>
              <td style={{padding:'0.4rem 0', fontFamily:'monospace', fontSize:'0.85rem', color:'#333'}}>{session.sessionId}</td>
            </tr>
          </tbody>
        </table>
      </div>
    )
  }