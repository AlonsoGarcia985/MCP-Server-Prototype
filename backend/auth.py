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

def build_login_url(state: str) -> str:
    verifier = generate_verifier()
    challenge = generate_challenge(verifier)

    _pending[state] = verifier

    params = urlencode({
        "response_type":         "code",
        "client_id":             "mcp-server",
        "redirect_uri":          "http://localhost:8000/auth/callback",
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
                "redirect_uri":  "http://localhost:8000/auth/callback",
                "code":          code,
                "code_verifier": verifier,
            }
        )
    resp.raise_for_status()
    return resp.json()