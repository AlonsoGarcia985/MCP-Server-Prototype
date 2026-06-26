import secrets
import base64
import hashlib
from urllib.parse import urlencode
import httpx

# Temporary storage: state → code_verifier
# In production this goes in Redis with TTL of 5 minutes
_pending: dict[str, str] = {}

def generate_verifier() -> str:
    return base64.urlsafe_b64encode(secrets.token_bytes(64)).rstrip(b"=").decode()

def generate_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode()).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()

REDIRECT_URI = "https://storeroom-niece-strum.ngrok-free.dev/auth/callback"

def build_login_url(state: str) -> str:
    verifier = generate_verifier()
    challenge = generate_challenge(verifier)

    _pending[state] = verifier

    params = urlencode({
        "response_type":         "code",
        "client_id":             "mcp-server",
        "redirect_uri":          REDIRECT_URI,
        "scope":                 "openid profile email",
        "state":                 state,
        "code_challenge":        challenge,
        "code_challenge_method": "S256",
    })

    return f"http://localhost:8080/realms/mcp-proto/protocol/openid-connect/auth?{params}"

async def exchange_code(code: str, state: str) -> dict:
    verifier = _pending.pop(state, None)
    if not verifier:
        raise ValueError("Invalid or expired state — possible CSRF attack")

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "http://localhost:8080/realms/mcp-proto/protocol/openid-connect/token",
            data={
                "grant_type":    "authorization_code",
                "client_id":     "mcp-server",
                "redirect_uri":  REDIRECT_URI,
                "code":          code,
                "code_verifier": verifier,
            }
        )
    resp.raise_for_status()
    return resp.json()

def build_login_url_with_challenge(state: str, code_challenge: str, redirect_uri: str, code_challenge_method: str = "S256") -> str:
    params = urlencode({
        "response_type":         "code",
        "client_id":             "mcp-server",
        "redirect_uri":          redirect_uri,
        "scope":                 "openid profile email",
        "state":                 state,
        "code_challenge":        code_challenge,
        "code_challenge_method": code_challenge_method,
    })
    return f"http://localhost:8080/realms/mcp-proto/protocol/openid-connect/auth?{params}"