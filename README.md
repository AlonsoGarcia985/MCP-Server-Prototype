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
  | grep -o '"access_token":"[^"]*"' | cut -d'"' -f4)

curl -s -H "Authorization: Bearer $TOKEN" \
  http://localhost:8080/admin/realms/mcp-proto/users \
  | python3 -m json.tool | grep -E "username|\"id\""
```

Copia el `id` que aparece y úsalo como clave en `backend/users_db.json`.

---

## 3. Levantar el servidor FastAPI

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

## 4. Exponer con ngrok

```bash
ngrok http 8000
```

Copia la URL de `Forwarding` y actualiza en `main.py`:
- La variable `base` en `oauth_metadata()`
- La variable `REDIRECT_URI` en `auth.py`

> La URL de ngrok cambia cada vez que reinicias el túnel.

---

## 5. Conectar a Claude Web

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
│   ├── requirements.txt        ← dependencias Python
│   └── .venv/                  ← entorno virtual (no se sube al repo)
└── frontend/                   ← React (se agrega viernes)
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

Solo cambian las URLs en `auth.py` y `middleware.py`:

```python
# Keycloak (prototipo)
KEYCLOAK_URL = "http://localhost:8080/realms/mcp-proto"

# Azure Entra ID (producción)
KEYCLOAK_URL = "https://login.microsoftonline.com/TENANT_ID/v2.0"
```

El campo `sub` del JWT de Azure es el mismo `azure_id` que ya existe en la base de datos de producción — el código no cambia.

---

## Troubleshooting

| Error | Causa | Solución |
|---|---|---|
| `No se encontró perfil para sub: XXX` | El sub en `users_db.json` está desactualizado | Obtener el sub correcto con la API de admin y actualizar `users_db.json` |
| Claude no ve los tools nuevos | Claude cachea `tools/list` al conectarse | Desconectar y reconectar el conector en Settings → Connectors |
| `Token inválido: Not enough segments` | El TOKEN en terminal está vacío | Verificar que el comando curl devuelve `access_token` antes del pipe |
| `unauthorized_client` al obtener token | El cliente `mcp-server` no tiene Direct Access Grants | Usar `client_id=admin-cli` para pruebas manuales con curl |
| La URL de ngrok cambió | ngrok gratuito cambia la URL al reiniciar | Actualizar `base` en `oauth_metadata()` y `REDIRECT_URI` en `auth.py` |

## Estado del desarrollo

| Día | Actividad | Estado |
|---|---|---|
| Martes | Keycloak con Docker + estructura base | ✅ |
| Martes | Mini-prototipo A — MCP server mínimo con echo tool | ✅ |
| Miércoles | Mini-prototipo B — /auth/login con PKCE completo | ✅ |
| Miércoles | Mini-prototipo C — /auth/callback, POST /token, JWT real | ✅ |
| Miércoles | Middleware JWT con validación JWKS | ✅ |
| Miércoles | Mini-prototipo D — tool get_my_profile con sub del JWT | ✅ |
| Jueves | Tools adicionales con contexto de usuario | ⬜ |
| Viernes | Frontend React + manual de migración a Azure | ⬜ |
