# mcp_prototype_oAuth2.1

Prototipo de un MCP Server en Python con autenticación OAuth 2.1 + PKCE usando Keycloak como servidor de autorización. Al terminar la semana incluirá FastAPI, React y una guía de migración a Azure Entra ID.

---

## ¿Qué es esto?

Un prototipo funcional que demuestra cómo conectar Claude Web a un MCP Server propio con autenticación real. El usuario se loguea con sus credenciales en Keycloak y Claude puede llamar tools que saben quién es el usuario — sin que el usuario tenga que decírselo.

**Arquitectura:**
```
Claude Web → ngrok → FastAPI (MCP Server) → valida JWT con Keycloak
                          ↓
                    Keycloak (OAuth 2.1)
```

---

## Requisitos

- Docker instalado y corriendo
- Git

Nada más. No necesitas Python, Node.js ni ninguna otra dependencia instalada en tu máquina.

---

## Levantar el entorno

```bash
git clone https://github.com/tu-usuario/mcp_prototype_oAuth2.1.git
cd mcp_prototype_oAuth2.1
docker compose up -d
```

Espera ~60 segundos para que Keycloak arranque e inicialice el realm automáticamente.

---

## Verificar que todo funciona

**1. Verificar que el realm existe:**
```bash
curl -s http://localhost:8080/realms/mcp-proto/.well-known/openid-configuration | python3 -m json.tool | head -5
```
Debe devolver JSON con `issuer`, `authorization_endpoint` y `token_endpoint`.

**2. Ver logs del proceso de inicialización:**
```bash
docker compose logs keycloak-init
```
Debe mostrar: `Realm creado exitosamente.`

---

## Servicios y puertos

| Servicio | Puerto | URL | Para qué sirve |
|---|---|---|---|
| Keycloak | 8080 | http://localhost:8080 | Servidor de autenticación OAuth 2.1 |
| FastAPI | 8000 | http://localhost:8000 | MCP Server + API (se agrega miércoles) |
| React | 5173 | http://localhost:5173 | Frontend (se agrega viernes) |

---

## Credenciales de desarrollo

> Estas credenciales son solo para desarrollo local. Nunca usar en producción.

| Componente | Usuario | Contraseña |
|---|---|---|
| Consola admin Keycloak | admin | admin |
| Usuario de prueba OAuth | test | test123 |

**Consola de administración:** http://localhost:8080

---

## Estructura del proyecto

```
mcp_prototype_oAuth2.1/
├── docker-compose.yml          ← orquesta todos los contenedores
├── keycloak/
│   ├── realm-export.json       ← configuración del realm, cliente OAuth y usuario
│   └── init-realm.sh           ← script que crea el realm via API REST al arrancar
├── backend/                    ← FastAPI + MCP Server (se agrega miércoles)
└── frontend/                   ← React + Vite (se agrega viernes)
```

---

## ¿Cómo funciona la inicialización automática?

Keycloak no tiene un mecanismo confiable de importación en la versión 25 cuando el volumen ya tiene datos. Por eso usamos dos contenedores:

1. **keycloak** — arranca el servidor Keycloak en modo desarrollo
2. **keycloak-init** — espera a que Keycloak esté listo y luego crea el realm `mcp-proto` via la API REST de administración

El contenedor `keycloak-init` verifica si el realm ya existe antes de crearlo — si ya existe lo omite. Esto hace que el proceso sea idempotente: puedes hacer `docker compose up` varias veces sin errores.

---

## Comandos útiles

```bash
# Levantar el entorno
docker compose up -d

# Ver logs de Keycloak
docker compose logs keycloak

# Ver logs del proceso de inicialización
docker compose logs keycloak-init

# Bajar el entorno (conserva los datos)
docker compose down

# Bajar el entorno y borrar todos los datos (empezar desde cero)
docker compose down -v

# Ver contenedores corriendo
docker ps
```

---

## ¿Por qué Keycloak tarda ~60 segundos en estar listo?

Keycloak es una aplicación Java. Las aplicaciones Java tardan más en arrancar que otros contenedores porque necesitan inicializar la JVM, cargar todas sus librerías en memoria e inicializar la base de datos interna. En los logs verás: `Keycloak 25.0.0 started in ~15s`. El tiempo adicional es el script de init esperando a que el servidor esté completamente listo.

---

## Configuración del realm OAuth 2.1

El realm `mcp-proto` está configurado con:

- **Cliente:** `mcp-server` — tipo público (sin client secret), Authorization Code Flow habilitado
- **PKCE:** método S256 forzado — obligatorio en OAuth 2.1 y en la especificación MCP
- **Redirect URIs:** `http://localhost:8000/auth/callback` y `https://*.ngrok-free.app/auth/callback`
- **SSL:** deshabilitado — solo para desarrollo local

---

# Backend — MCP Server con FastAPI

Servidor MCP mínimo en Python con FastAPI. Expone un tool `echo` que Claude Web puede llamar directamente.

---

## Requisitos

- Python 3.11 o superior
- ngrok instalado y con cuenta (para exponer el servidor a Claude Web)

---

## Instalación

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

---

## Correr el servidor

```bash
cd backend
source .venv/bin/activate
python main.py
```

El servidor arranca en `http://localhost:8000`.

Verifica que funciona:
```bash
curl http://localhost:8000/
# {"status": "MCP server corriendo"}
```

---

## Exponer con ngrok

En una segunda terminal:

```bash
ngrok http 8000
```

Copia la URL que aparece en `Forwarding`, por ejemplo:
```
https://abc123.ngrok-free.dev
```

Actualiza la variable `base` en la función `oauth_metadata()` de `main.py` con esa URL.

---

## Conectar a Claude Web

1. Ve a **claude.ai → Settings → Connectors → + → Add custom connector**
2. Name: `MCP Proto`
3. Remote MCP server URL: `https://[tu-url-ngrok]/mcp`
4. Haz clic en **Add** y luego **Connect**
5. En el chat escribe: `usa el tool echo con el mensaje hola mundo`

Claude debe responder: `Echo: hola mundo`

---

## Endpoints disponibles

| Endpoint | Método | Para qué sirve |
|---|---|---|
| `/` | GET | Verificación — confirma que el servidor corre |
| `/.well-known/oauth-authorization-server` | GET | Requerido por Claude Web para descubrir OAuth |
| `/register` | POST | Registro dinámico de cliente OAuth |
| `/auth/login` | GET | Inicio del flujo OAuth |
| `/token` | POST | Obtener token de acceso |
| `/mcp` | POST | Endpoint principal MCP — recibe llamadas de Claude |

---

## Tool disponible

| Tool | Descripción | Parámetros |
|---|---|---|
| `echo` | Repite el mensaje que recibe | `message: string` |

---

## Notas importantes

- La URL de ngrok cambia cada vez que reinicias el túnel — actualiza `main.py` y el conector en Claude Web cuando esto ocurra
- El OAuth en este prototipo es mínimo y no verifica credenciales reales — se reemplaza el miércoles con Keycloak
- El `.venv` debe estar dentro de `backend/` — no en la raíz del proyecto



## Migración a producción (Azure Entra ID)

Al terminar el prototipo, el código de FastAPI y React no cambia. Solo se actualizan las variables de entorno:

```bash
# Keycloak (prototipo)
KC_BASE=http://localhost:8080/realms/mcp-proto/protocol/openid-connect
KC_ISSUER=http://localhost:8080/realms/mcp-proto

# Azure Entra ID (producción)
KC_BASE=https://login.microsoftonline.com/TENANT_ID/oauth2/v2.0
KC_ISSUER=https://login.microsoftonline.com/TENANT_ID/v2.0
```

---
