from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
import secrets
import uvicorn

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

@app.post("/mcp")
async def mcp_endpoint(request: Request):
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

@app.get("/auth/login")
async def auth_login(
    response_type: str,
    client_id: str,
    redirect_uri: str,
    code_challenge: str,
    code_challenge_method: str,
    state: str = ""
):
    fake_code = secrets.token_hex(16)
    return RedirectResponse(
        url=f"{redirect_uri}?code={fake_code}&state={state}"
    )

@app.post("/token")
async def token(request: Request):
    return JSONResponse({
        "access_token": "fake-token-proto",
        "token_type": "Bearer",
        "expires_in": 3600
    })

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)