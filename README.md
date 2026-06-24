# MCP Server Prototype — OAuth 2.1 + PKCE + Keycloak

Prototipo de un MCP Server en Python con FastAPI y autenticación OAuth 2.1 completa con PKCE usando Keycloak como servidor de autorización. Al terminar la semana incluirá middleware JWT, validación de tokens y frontend React.

---

## ¿Qué es esto?

Un prototipo funcional que demuestra cómo conectar Claude Web a un MCP Server propio con autenticación real. El usuario se loguea con sus credenciales en Keycloak, el servidor obtiene un JWT real, y Claude puede llamar tools que saben quién es el usuario — sin que el usuario tenga que decírselo.

**Arquitectura:**
```
Claude Web → ngrok → FastAPI (MCP Server + OAuth) → Keycloak (JWT)
                          ↓
                    Keycloak (OAuth 2.1)
```

---

## Requisitos

- Docker instalado y corriendo
- Python 3.11 o superior
- ngrok instalado y con cuenta gratuita en ngrok.com
- Git

---

## 1. Levantar Keycloak

```bash
docker compose up -d
```

Espera ~60 segundos. Keycloak estará listo en `http://localhost:8080` con el realm `mcp-proto`, el cliente `mcp-server` y el usuario de prueba `test / test123` configurados automáticamente.

Verifica que funciona:
```bash
curl -s http://localhost:8080/realms/mcp-proto/.well-known/openid-configuration | python3 -m json.tool | head -5
```

Ver logs del proceso de inicialización:
```bash
docker compose logs keycloak-init
# Debe mostrar: Realm creado exitosamente.
```

---

## 2. Levantar el servidor FastAPI

Si es la primera vez:
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

Las siguientes veces:
```bash
cd backend
source .venv/bin/activate
python main.py
```

El servidor arranca en `http://localhost:8000`.

Verifica:
```bash
curl http://localhost:8000/
# {"status": "MCP server corriendo"}
```

---

## 3. Exponer con ngrok

En una segunda terminal:
```bash
ngrok http 8000
```

Copia la URL de `Forwarding`, por ejemplo:
```
https://abc123.ngrok-free.dev
```

Actualiza la variable `base` en `oauth_metadata()` dentro de `main.py` con esa URL.

> La URL de ngrok cambia cada vez que reinicias el túnel. Cuando cambie, actualiza `main.py` y el conector en Claude Web.

---

## 4. Probar el flujo OAuth completo

Abre en el browser:
```
http://localhost:8000/auth/login
```

Debe redirigir a la pantalla de login de Keycloak. Loguéate con `test / test123`. El servidor devolverá el JWT con el `sub`, `email` y `preferred_username` del usuario.

Para inspeccionar el JWT:
```bash
echo "PEGA_TU_ACCESS_TOKEN" | cut -d. -f2 | base64 -d 2>/dev/null | python3 -m json.tool
```

---

## 5. Conectar a Claude Web

1. Ve a **claude.ai → Settings → Connectors → + → Add custom connector**
2. Name: `MCP Proto`
3. Remote MCP server URL: `https://[tu-url-ngrok]/mcp`
4. Haz clic en **Add** y luego **Connect**
5. En el chat escribe: `usa el tool echo con el mensaje hola mundo`

Claude debe responder: `Echo: hola mundo`

---

## Estructura del proyecto

```
mcp_prototype_oAuth2.1/
├── docker-compose.yml          ← levanta Keycloak automáticamente
├── keycloak/
│   ├── realm-export.json       ← configuración del realm, cliente y usuario
│   └── init-realm.sh           ← script que crea el realm via API REST
├── backend/
│   ├── main.py                 ← servidor FastAPI + endpoints OAuth + MCP
│   ├── auth.py                 ← lógica PKCE: verifier, challenge, exchange
│   ├── requirements.txt        ← dependencias Python
│   └── .venv/                  ← entorno virtual (no se sube al repo)
└── frontend/                   ← React (se agrega viernes)
```

---

## Servicios y puertos

| Servicio | Puerto | URL | Para qué sirve |
|---|---|---|---|
| Keycloak | 8080 | http://localhost:8080 | Servidor de autenticación OAuth 2.1 |
| FastAPI | 8000 | http://localhost:8000 | MCP Server + OAuth |
| React | 5173 | http://localhost:5173 | Frontend (se agrega viernes) |

---

## Endpoints disponibles

| Endpoint | Método | Para qué sirve |
|---|---|---|
| `/` | GET | Verificación del servidor |
| `/.well-known/oauth-authorization-server` | GET | Metadatos OAuth — Claude lo consulta al conectarse |
| `/register` | POST | Registro dinámico de cliente OAuth |
| `/auth/login` | GET | Inicia el flujo OAuth con PKCE — redirige a Keycloak |
| `/auth/callback` | GET | Recibe el code de Keycloak e intercambia por JWT |
| `/mcp` | POST | Endpoint MCP — recibe llamadas de Claude |

---

## Flujo OAuth 2.1 con PKCE

```
1. Usuario abre /auth/login
2. FastAPI genera code_verifier (secreto) y code_challenge = SHA256(verifier)
3. FastAPI redirige a Keycloak con el code_challenge
4. Usuario se loguea en Keycloak
5. Keycloak redirige a /auth/callback con un code temporal
6. FastAPI intercambia el code + code_verifier por el JWT
7. JWT contiene sub, email y preferred_username del usuario
```

---

## Credenciales de desarrollo

> ⚠️ Solo para desarrollo local. Nunca usar en producción.

| Componente | Usuario | Contraseña |
|---|---|---|
| Consola admin Keycloak | admin | admin |
| Usuario de prueba OAuth | test | test123 |

---

## ¿Cómo funciona la inicialización automática de Keycloak?

Keycloak 25 no tiene un mecanismo confiable de importación cuando el volumen ya tiene datos. Por eso usamos dos contenedores:

- **keycloak** — arranca el servidor en modo desarrollo
- **keycloak-init** — espera a que Keycloak esté listo y crea el realm `mcp-proto` via API REST

El proceso es idempotente — si el realm ya existe lo omite. Puedes hacer `docker compose up` varias veces sin errores.

---

## Comandos útiles

```bash
# Levantar Keycloak
docker compose up -d

# Ver logs de Keycloak
docker compose logs keycloak

# Ver logs del init
docker compose logs keycloak-init

# Bajar Keycloak (conserva datos)
docker compose down

# Bajar Keycloak y borrar todo (empezar desde cero)
docker compose down -v

# Ver contenedores corriendo
docker ps

# Activar entorno virtual
source backend/.venv/bin/activate

# Correr el servidor
cd backend && python main.py
```

---

## Migración a producción (Azure Entra ID)

El código de FastAPI no cambia. Solo se actualizan las URLs en `auth.py`:

```python
# Keycloak (prototipo)
KEYCLOAK_URL = "http://localhost:8080/realms/mcp-proto/protocol/openid-connect"

# Azure Entra ID (producción)
KEYCLOAK_URL = "https://login.microsoftonline.com/TENANT_ID/oauth2/v2.0"
```

---

## Estado del desarrollo

| Día | Actividad | Estado |
|---|---|---|
| Martes | Keycloak con Docker + estructura base | ✅ |
| Martes | Mini-prototipo A — MCP server mínimo con echo tool | ✅ |
| Miércoles | Mini-prototipo B — /auth/login con PKCE completo | ✅ |
| Miércoles | Flujo OAuth 2.1 completo con callback y JWT real | 🔄 En progreso |
| Jueves | Middleware JWT + tools con contexto de usuario | ⬜ |
| Viernes | Frontend React + manual de migración a Azure | ⬜ |
