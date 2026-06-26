from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from auth import build_login_url, exchange_code, build_login_url_with_challenge
import uvicorn
import secrets
from middleware import verify_token
import json
from pathlib import Path
import httpx
app = FastAPI()

_claude_callbacks: dict[str, str] = {}
@app.get("/")
async def root():
    return {"status": "MCP server corriendo"}

@app.get("/.well-known/oauth-authorization-server")
async def oauth_metadata():
    base = "https://storeroom-niece-strum.ngrok-free.dev"
    return {
        "issuer": base,
        "authorization_endpoint": f"{base}/auth/login",
        "token_endpoint": f"{base}/token",
        "registration_endpoint": f"{base}/register",
        "response_types_supported": ["code"],
        "code_challenge_methods_supported": ["S256"],
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
        url = build_login_url_with_challenge(state, code_challenge, "https://storeroom-niece-strum.ngrok-free.dev/auth/callback", code_challenge_method)
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

    return JSONResponse({
        "jsonrpc": "2.0",
        "id": req_id,
        "error": {"code": -32601, "message": f"Método no soportado: {method}"}
    })


@app.post("/token")
async def token_endpoint(request: Request):
    body = await request.form()
    data = dict(body)

    # Log temporal para ver qué manda Claude
    print("=== /token recibido ===")
    print(data)

    data["client_id"] = "mcp-server"
    data.pop("client_secret", None)

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "http://localhost:8080/realms/mcp-proto/protocol/openid-connect/token",
            data=data
        )

    print("=== respuesta Keycloak ===")
    print(resp.status_code, resp.text)

    return JSONResponse(resp.json(), status_code=resp.status_code)

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)