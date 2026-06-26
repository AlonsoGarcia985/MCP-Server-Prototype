from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from auth import build_login_url, exchange_code
import uvicorn
import secrets
from middleware import verify_token
app = FastAPI()

@app.get("/")
async def root():
    return {"status": "MCP server corriendo"}

@app.get("/.well-known/oauth-authorization-server")
async def oauth_metadata():
    base = "https://storeroom-niece-strum.ngrok-free.dev"
    return {
        "issuer": base,
        "authorization_endpoint": f"{base}/auth/login",
        "token_endpoint": "http://localhost:8080/realms/mcp-proto/protocol/openid-connect/token",
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
async def auth_login(state: str = ""):
    if not state:
        state = secrets.token_hex(16)
    url = build_login_url(state)
    return RedirectResponse(url)

@app.get("/auth/callback")
async def auth_callback(code: str, state: str):
    try:
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
    await verify_token(request)

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

    return JSONResponse({
        "jsonrpc": "2.0",
        "id": req_id,
        "error": {"code": -32601, "message": f"Método no soportado: {method}"}
    })

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)