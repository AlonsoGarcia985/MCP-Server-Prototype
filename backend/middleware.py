import os
from pathlib import Path
import httpx
from jose import jwt, JWTError
from fastapi import Request, HTTPException
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

KEYCLOAK_URL = os.environ["KEYCLOAK_BASE_URL"]
JWKS_URI = f"{KEYCLOAK_URL}/protocol/openid-connect/certs"

# Cache de las claves públicas — se descarga una vez y se reutiliza
_jwks_cache: dict | None = None

async def get_jwks() -> dict:
    global _jwks_cache
    if not _jwks_cache:
        async with httpx.AsyncClient() as client:
            resp = await client.get(JWKS_URI)
            _jwks_cache = resp.json()
    return _jwks_cache

async def verify_token(request: Request) -> dict:
    auth = request.headers.get("Authorization", "")

    if not auth.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            headers={"WWW-Authenticate": 'Bearer realm="mcp", error="unauthorized"'},
            detail="Token requerido"
        )

    token = auth[7:]

    try:
        jwks = await get_jwks()
        payload = jwt.decode(
            token,
            jwks,
            algorithms=["RS256"],
            audience="account",
            issuer=KEYCLOAK_URL,
        )
        return payload

    except JWTError as e:
        global _jwks_cache
        _jwks_cache = None  # limpiar cache por si Keycloak rotó las claves
        raise HTTPException(
            status_code=401,
            detail=f"Token inválido: {e}"
        )