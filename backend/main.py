import os
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from auth import build_login_url, exchange_code, build_login_url_with_challenge, exchange_code_frontend
import uvicorn
import secrets
from middleware import verify_token, KEYCLOAK_URL
import json
from pathlib import Path
import httpx
from datetime import datetime, timezone
from dotenv import load_dotenv
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

load_dotenv(Path(__file__).parent / ".env")

SERVER_URL = os.environ["SERVER_URL"]
REDIRECT_URI = os.environ["REDIRECT_URI"]

app = FastAPI()

_claude_callbacks: dict[str, str] = {}
@app.get("/")
async def root():
    return {"status": "MCP server corriendo"}

@app.get("/.well-known/oauth-authorization-server")
async def oauth_metadata():
    base = SERVER_URL
    return {
        "issuer": base,
        "authorization_endpoint": f"{base}/auth/login",
        "token_endpoint": f"{base}/token",
        "registration_endpoint": f"{base}/register",
        "response_types_supported": ["code"],
        "code_challenge_methods_supported": ["S256"],
        "jwks_uri": f"{KEYCLOAK_URL}/protocol/openid-connect/certs",
        "grant_types_supported": ["authorization_code"]
    }

@app.post("/register")
async def register_client(request: Request):
    body = await request.json()
    return JSONResponse({
        "client_id": "claude-client",
        "client_secret": "not-needed",
        "redirect_uris": body.get("redirect_uris", []),
        "grant_types": ["authorization_code"],
        "response_types": ["code"],
        "token_endpoint_auth_method": "none"
    })


@app.get("/auth/login")
async def auth_login(
    state: str = "",
    redirect_uri: str = "",
    code_challenge: str = "",
    code_challenge_method: str = "S256",
    response_type: str = "code",
    client_id: str = "",
    scope: str = "",
):
    if not state:
        state = secrets.token_hex(16)

    if redirect_uri:
        _claude_callbacks[state] = redirect_uri

    if code_challenge and redirect_uri:
        # Usar el redirect_uri de Claude directamente en Keycloak
        url = build_login_url_with_challenge(state, code_challenge, redirect_uri, code_challenge_method)
    elif code_challenge:
        url = build_login_url_with_challenge(state, code_challenge, REDIRECT_URI, code_challenge_method)
    else:
        url = build_login_url(state)

    return RedirectResponse(url)

@app.get("/auth/callback")
async def auth_callback(code: str, state: str):
    try:
        claude_redirect = _claude_callbacks.pop(state, None)
        if claude_redirect:
            # No intercambiamos el code — Claude lo hará él mismo via /token
            return RedirectResponse(
                url=f"{claude_redirect}?code={code}&state={state}"
            )

        # Si no hay redirect de Claude, intercambiamos nosotros
        tokens = await exchange_code(code, state)
        return JSONResponse(tokens)
    except ValueError as e:
        return JSONResponse(
            {"error": "invalid_state", "error_description": str(e)},
            status_code=400
        )
    except Exception as e:
        return JSONResponse(
            {"error": "token_exchange_failed", "error_description": str(e)},
            status_code=400
        )
    

@app.get("/auth/frontend-login")
async def frontend_login():
    from auth import generate_verifier, generate_challenge, _pending
    state = secrets.token_hex(16)
    verifier = generate_verifier()
    challenge = generate_challenge(verifier)
    _pending[state] = verifier
    url = build_login_url_with_challenge(
        state, challenge,
        "http://localhost:8000/auth/frontend-callback"
    )
    return RedirectResponse(url)

@app.post("/mcp")
async def mcp_endpoint(request: Request):
    payload = await verify_token(request)

    body = await request.json()
    method = body.get("method")
    req_id = body.get("id")

    if method == "initialize":
        return JSONResponse({
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "mcp-proto", "version": "0.1.0"}
            }
        })

    if method == "tools/list":
        return JSONResponse({
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "tools": [
                    {
                        "name": "echo",
                        "description": "Repite el mensaje que recibe. Tool de prueba.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "message": {"type": "string", "description": "Texto a repetir"}
                            },
                            "required": ["message"]
                        }
                    },
                    {
                        "name": "get_my_profile",
                        "description": "Devuelve el perfil del usuario autenticado desde la base de datos local.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {}
                        }
                    },
                    {
                        "name": "list_my_permissions",
                        "description": "Devuelve la lista de permisos del usuario autenticado.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {}
                        }
                    },
                    {
                        "name": "get_server_info",
                        "description": "Devuelve informacion del servidor MCP y el usuario que esta haciendo la llamada.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {}
                        }
                    }
                ]

            }
        })

    if method == "tools/call":
        params = body.get("params", {})
        name = params.get("name")
        arguments = params.get("arguments", {})

        if name == "echo":
            return JSONResponse({
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": f"Echo: {arguments.get('message', '')}"}]
                }
            })

        if name == "get_my_profile":
            sub = payload.get("sub")
            users_db = json.loads((Path(__file__).parent / "users_db.json").read_text())
            profile = users_db.get(sub)

            if not profile:
                return JSONResponse({
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [{"type": "text", "text": f"No se encontró perfil para sub: {sub}"}]
                    }
                })
            return JSONResponse({
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": json.dumps(profile, ensure_ascii=False, indent=2)}]
                }
            })
        if name == "list_my_permissions":
            sub = payload.get("sub")
            users_db = json.loads((Path(__file__).parent / "users_db.json").read_text())
            profile = users_db.get(sub)

            if not profile:
                return JSONResponse({
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [{"type": "text", "text": f"No se encontró perfil para sub: {sub}"}]
                    }
                })

            permisos = profile.get("permisos", [])
            return JSONResponse({
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": json.dumps(permisos, ensure_ascii=False, indent=2)}]
                }
            })

        if name == "get_server_info":
            now = datetime.now(timezone.utc).isoformat()
            username = payload.get("preferred_username", "desconocido")
            return JSONResponse({
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": json.dumps({
                        "servidor": "mcp-proto",
                        "version": "0.1.0",
                        "timestamp": now,
                        "llamado_por": username
                    }, ensure_ascii=False, indent=2)}]
                }
            })

    return JSONResponse({
        "jsonrpc": "2.0",
        "id": req_id,
        "error": {"code": -32601, "message": f"Método no soportado: {method}"}
    })


@app.post("/token")
async def token_endpoint(request: Request):
    body = await request.form()
    data = dict(body)

    data["client_id"] = "mcp-server"
    data.pop("client_secret", None)

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{KEYCLOAK_URL}/protocol/openid-connect/token",
            data=data
        )
    return JSONResponse(resp.json(), status_code=resp.status_code)



# Sesiones del frontend — se guardan cuando el usuario hace login via /auth/callback
_frontend_sessions: dict[str, dict] = {}

@app.get("/auth/frontend-callback")
async def frontend_callback(code: str, state: str):
    try:
        tokens = await exchange_code_frontend(code, state)
        import base64
        raw = tokens["access_token"].split(".")[1]
        padding = 4 - len(raw) % 4
        payload = json.loads(base64.urlsafe_b64decode(raw + "=" * padding))
        
        session_id = secrets.token_hex(16)
        _frontend_sessions[session_id] = {
            "sub": payload.get("sub"),
            "username": payload.get("preferred_username", ""),
            "email": payload.get("email", ""),
            "access_token": tokens["access_token"],
        }
        return RedirectResponse(url=f"{SERVER_URL}/frontend/?session={session_id}")
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=400)

@app.get("/api/session/{session_id}")
async def get_session(session_id: str):
    s = _frontend_sessions.get(session_id)
    if not s:
        return JSONResponse({"error": "sesion no encontrada"}, status_code=404)
    return {"sub": s["sub"], "username": s["username"], "email": s["email"]}

@app.post("/api/call-tool")
async def call_tool_proxy(request: Request):
    body = await request.json()
    session_id = body.get("session_id")
    tool_name = body.get("tool")
    arguments = body.get("arguments", {})

    s = _frontend_sessions.get(session_id)
    if not s:
        return JSONResponse({"error": "sesion no encontrada o expirada"}, status_code=401)

    # Simular el payload del JWT para reutilizar la logica de los tools
    fake_payload = {"sub": s["sub"], "preferred_username": s["username"]}

    if tool_name == "echo":
        return JSONResponse({"result": f"Echo: {arguments.get('message', '')}"})

    if tool_name == "get_my_profile":
        users_db = json.loads((Path(__file__).parent / "users_db.json").read_text())
        profile = users_db.get(s["sub"])
        if not profile:
            return JSONResponse({"result": f"No se encontro perfil para sub: {s['sub']}"})
        return JSONResponse({"result": json.dumps(profile, ensure_ascii=False, indent=2)})

    if tool_name == "list_my_permissions":
        users_db = json.loads((Path(__file__).parent / "users_db.json").read_text())
        profile = users_db.get(s["sub"])
        if not profile:
            return JSONResponse({"result": f"No se encontro perfil para sub: {s['sub']}"})
        return JSONResponse({"result": json.dumps(profile.get("permisos", []), ensure_ascii=False, indent=2)})

    if tool_name == "get_server_info":
        now = datetime.now(timezone.utc).isoformat()
        return JSONResponse({"result": json.dumps({
            "servidor": "mcp-proto",
            "version": "0.1.0",
            "timestamp": now,
            "llamado_por": s["username"]
        }, ensure_ascii=False, indent=2)})

    return JSONResponse({"error": f"Tool desconocido: {tool_name}"}, status_code=400)



FRONTEND_DIST = Path(__file__).parent.parent / "frontend" / "dist"

if FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

    @app.get("/frontend/")
    async def frontend_index():
        return FileResponse(FRONTEND_DIST / "index.html")

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)