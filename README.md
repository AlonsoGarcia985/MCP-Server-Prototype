# MCP Server Prototype — OAuth 2.1 + PKCE + Keycloak

Prototipo de un MCP Server en Python con FastAPI y autenticación OAuth 2.1 completa con PKCE usando Keycloak como servidor de autorización. Incluye middleware de validación JWT y tools que usan la identidad del usuario autenticado.

---

## ¿Qué es esto?

Un prototipo funcional que demuestra cómo conectar Claude Web a un MCP Server propio con autenticación real. El usuario se loguea con sus credenciales en Keycloak, el servidor valida el JWT criptográficamente, y Claude puede llamar tools que saben quién es el usuario — sin que el usuario tenga que decírselo.

**Arquitectura:**
```
Claude Web → ngrok → FastAPI (MCP Server + OAuth) → Keycloak (JWT)
                          ↓
                  valida JWT con JWKS
                          ↓
                  busca perfil por sub
```

---

## Requisitos

- Docker instalado y corriendo
- Python 3.11 o superior
- ngrok instalado y con cuenta gratuita en ngrok.com

---

## 1. Levantar Keycloak

```bash
docker compose up -d
```

Espera ~60 segundos. Keycloak estará listo en `http://localhost:8080`.

Verifica:
```bash
curl -s http://localhost:8080/realms/mcp-proto/.well-known/openid-configuration | python3 -m json.tool | head -5
```

Ver logs del init:
```bash
docker compose logs keycloak-init
# Debe mostrar: Realm creado exitosamente.
```

---

## 2. Obtener el sub del usuario de prueba

Cada vez que Keycloak se reinicia con `docker compose down -v`, el usuario recibe un nuevo `sub`. Actualiza `backend/users_db.json` con el sub correcto:

```bash
TOKEN=$(curl -s -X POST http://localhost:8080/realms/master/protocol/openid-connect/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=admin&grant_type=password&client_id=admin-cli" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

curl -s -H "Authorization: Bearer $TOKEN" \
  http://localhost:8080/admin/realms/mcp-proto/users \
  | python3 -m json.tool | grep -E "username|\"id\""
```

Copia el `id` que aparece y úsalo como clave en `backend/users_db.json`.

---

## 3. Configurar variables de entorno

> ⚠️ Sin este archivo el servidor falla al arrancar con `KeyError: 'KEYCLOAK_BASE_URL'`.

Crea el archivo `backend/.env`:

```env
# URL base de Keycloak incluyendo el realm
KEYCLOAK_BASE_URL=http://localhost:8080/realms/mcp-proto

# URL del callback OAuth — debe coincidir con la URL de ngrok actual
REDIRECT_URI=https://TU-URL-NGROK.ngrok-free.app/auth/callback

# URL pública del servidor — la misma URL de ngrok
SERVER_URL=https://TU-URL-NGROK.ngrok-free.app
```

> Hay un archivo `backend/.env.example` como referencia. El `.env` real nunca se sube al repo.
> Por ahora pon cualquier URL en `REDIRECT_URI` y `SERVER_URL` — las actualizarás en el paso 5 cuando tengas la URL de ngrok.

---

## 4. Levantar el servidor FastAPI

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

Verifica:
```bash
curl http://localhost:8000/
# {"status": "MCP server corriendo"}
```

---

## 5. Exponer con ngrok

```bash
ngrok http 8000
```

Copia la URL de `Forwarding` y actualiza `backend/.env`:
- `REDIRECT_URI=https://[tu-url-ngrok]/auth/callback`
- `SERVER_URL=https://[tu-url-ngrok]`

Reinicia el servidor después de actualizar el `.env`.

> La URL de ngrok cambia cada vez que reinicias el túnel — recuerda actualizar el `.env`.

---

## 6. Conectar a Claude Web

1. Ve a **claude.ai → Settings → Connectors → + → Add custom connector**
2. Name: `MCP Proto`
3. Remote MCP server URL: `https://[tu-url-ngrok]/mcp`
4. Haz clic en **Add** → **Connect** → loguéate con `test / test123`
5. En el chat escribe: `usa el tool get_my_profile`

Claude debe responder con tu perfil completo.

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
│   ├── middleware.py           ← validación JWT con JWKS de Keycloak
│   ├── users_db.json           ← perfiles de usuario indexados por sub
│   ├── .env                    ← variables de entorno (no se sube al repo)
│   ├── .env.example            ← plantilla de variables de entorno
│   ├── requirements.txt        ← dependencias Python
│   └── .venv/                  ← entorno virtual (no se sube al repo)
└── frontend/                   ← React (próximamente)
```

---

## Endpoints disponibles

| Endpoint | Método | Para qué sirve |
|---|---|---|
| `/` | GET | Verificación del servidor |
| `/.well-known/oauth-authorization-server` | GET | Metadatos OAuth — Claude lo consulta al conectarse |
| `/register` | POST | Registro dinámico de cliente OAuth |
| `/auth/login` | GET | Inicia el flujo OAuth con PKCE — redirige a Keycloak |
| `/auth/callback` | GET | Recibe el code de Keycloak y redirige a Claude |
| `/token` | POST | Proxy al endpoint /token de Keycloak |
| `/mcp` | POST | Endpoint MCP protegido — requiere JWT válido |

---

## Tools disponibles

| Tool | Descripción | Autenticación requerida |
|---|---|---|
| `echo` | Repite el mensaje que recibe | ✅ JWT válido |
| `get_my_profile` | Devuelve el perfil del usuario autenticado | ✅ JWT válido + sub en users_db.json |
| `list_my_permissions` | Devuelve la lista de permisos del usuario autenticado | ✅ JWT válido + sub en users_db.json |
| `get_server_info` | Devuelve info del servidor y el usuario que hace la llamada | ✅ JWT válido |

---

## Flujo OAuth 2.1 con PKCE

```
1. Claude llama /.well-known para descubrir los endpoints
2. Claude genera su propio PKCE (code_verifier + code_challenge)
3. Claude redirige al usuario a /auth/login con su code_challenge
4. FastAPI pasa el code_challenge de Claude directamente a Keycloak
5. Usuario se loguea en Keycloak
6. Keycloak redirige a /auth/callback con el code temporal
7. FastAPI redirige a Claude con el code
8. Claude hace POST a /token con el code y su code_verifier
9. FastAPI hace proxy del POST a Keycloak reemplazando client_id
10. Keycloak verifica PKCE y devuelve el JWT
11. Claude manda el JWT en cada llamada al /mcp
12. FastAPI valida la firma JWT con las claves públicas JWKS de Keycloak
```

---

## Validación JWT

El middleware en `middleware.py` valida en cada petición al `/mcp`:

| Validación | Qué verifica |
|---|---|
| Firma RS256 | Que el JWT fue firmado por Keycloak con su clave privada |
| `exp` | Que el token no ha expirado |
| `iss` | Que el token fue emitido por nuestro Keycloak |
| `aud` | Que el token fue emitido para nuestra aplicación |

---

## Credenciales de desarrollo

> ⚠️ Solo para desarrollo local. Nunca usar en producción.

| Componente | Usuario | Contraseña |
|---|---|---|
| Consola admin Keycloak | admin | admin |
| Usuario de prueba OAuth | test | test123 |

---

## Comandos útiles

```bash
# Levantar Keycloak
docker compose up -d

# Ver logs de Keycloak
docker compose logs keycloak

# Bajar Keycloak (conserva datos)
docker compose down

# Bajar Keycloak y borrar todo (el sub del usuario cambiará)
docker compose down -v

# Activar entorno virtual
source backend/.venv/bin/activate

# Correr el servidor
cd backend && python main.py
```

---

## Migración a producción (Azure Entra ID)

Solo cambian 3 cosas. El código Python no se toca.

### Cambio 1 — Keycloak → Azure Entra ID

Pide a IT una App Registration en Azure Portal. Te entregarán 3 valores:

| Variable | Descripción |
|---|---|
| `TENANT_ID` | ID de tu organización en Azure |
| `CLIENT_ID` | ID de la aplicación registrada |
| `CLIENT_SECRET` | Secret generado en Certificates & secrets |

Actualiza el `.env`:
```env
KEYCLOAK_BASE_URL=https://login.microsoftonline.com/TENANT_ID/oauth2/v2.0
CLIENT_ID=tu-client-id
CLIENT_SECRET=tu-client-secret
```

### Cambio 2 — ngrok → URL fija (AWS o Azure)

```env
SERVER_URL=https://mcp.tuempresa.com
REDIRECT_URI=https://mcp.tuempresa.com/auth/callback
```

### Cambio 3 — users_db.json → endpoint del backend

Reemplazar la lectura del JSON por una llamada HTTP al backend real:
```python
resp = await client.get(
    f"{BACKEND_URL}/api/usuario-por-azure-id",
    params={"sub": sub},
    headers={"X-API-Key": BACKEND_API_KEY}
)
profile = resp.json()
```

> El `sub` del JWT de Azure es el mismo `azure_id` que ya existe en la BD de producción.

---

## Troubleshooting

| Error | Causa | Solución |
|---|---|---|
| `No se encontró perfil para sub: XXX` | El sub en `users_db.json` está desactualizado | Obtener el sub correcto con la API de admin y actualizar `users_db.json` |
| Claude no ve los tools nuevos | Claude cachea `tools/list` al conectarse | Desconectar y reconectar el conector en Settings → Connectors |
| `Token inválido: Not enough segments` | El TOKEN en terminal está vacío | Verificar que el comando curl usa `\|` pipe antes del python3 |
| `unauthorized_client` al obtener token | El cliente `mcp-server` no tiene Direct Access Grants | Usar `client_id=admin-cli` para pruebas manuales con curl |
| La URL de ngrok cambió | ngrok gratuito cambia la URL al reiniciar | Actualizar `REDIRECT_URI` y `SERVER_URL` en el `.env` y reiniciar el servidor |
| `KeyError: 'KEYCLOAK_BASE_URL'` al arrancar | El `.env` tiene placeholders en lugar de valores reales | Editar `backend/.env` y reemplazar `your-realm` con `mcp-proto` y `your-public-host` con la URL de ngrok |
| `ERR_NGROK_8012 - connection refused` | ngrok está apuntando al puerto equivocado | Correr `ngrok http 8000` — el servidor FastAPI corre en el puerto 8000 |

---

## Estado del desarrollo

| Día | Actividad | Estado |
|---|---|---|
| Martes | Keycloak con Docker + estructura base | ✅ |
| Martes | Mini-prototipo A — MCP server mínimo con echo tool | ✅ |
| Miércoles | Mini-prototipo B — /auth/login con PKCE completo | ✅ |
| Miércoles | Mini-prototipo C — /auth/callback, POST /token, JWT real | ✅ |
| Miércoles | Middleware JWT con validación JWKS | ✅ |
| Miércoles | Mini-prototipo D — tool get_my_profile con sub del JWT | ✅ |
| Jueves | Tools adicionales con contexto de usuario | ✅ |
| Jueves | Endpoint /.well-known completo con jwks_uri | ✅ |
| Jueves | Test de integración completo desde Claude Web | ✅ |
| Viernes | README completo | ✅ |
| Viernes | Guía de migración a Azure | ✅ |
| Viernes | Frontend React | ⬜ |
