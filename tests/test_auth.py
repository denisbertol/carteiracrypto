import time
import unittest
from types import SimpleNamespace
from uuid import uuid4

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa

from app.auth import AuthError, TokenVerifier
from app.config import get_settings


class FixedJwksClient:
    """Test-only JWKS adapter; JWT signature verification remains real."""

    def __init__(self, public_key):
        self.public_key = public_key

    def get_signing_key_from_jwt(self, token):
        return SimpleNamespace(key=self.public_key)


class TestAuth(unittest.TestCase):
    def setUp(self):
        self.settings = get_settings()
        self.private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.other_private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.verifier = TokenVerifier(
            jwks_client=FixedJwksClient(self.private_key.public_key())
        )

    def token(self, *, subject=None, issuer=None, key=None, algorithm="RS256", expires=None):
        now = int(time.time())
        payload = {
            "sub": str(subject or self.settings.owner_user_id),
            "aud": "authenticated",
            "iss": issuer or f"{self.settings.supabase_url.rstrip('/')}/auth/v1",
            "iat": now,
            "exp": expires if expires is not None else now + 3600,
        }
        signing_key = key or self.private_key
        return jwt.encode(payload, signing_key, algorithm=algorithm, headers={"kid": "test-key"})

    def assert_unauthorized(self, token):
        with self.assertRaises(AuthError) as error:
            self.verifier.verify_token(token)
        self.assertEqual(error.exception.status_code, 401)

    def test_missing_and_test_tokens_are_rejected(self):
        self.assert_unauthorized("")
        self.assert_unauthorized(f"test-token-{self.settings.owner_user_id}")
        self.assert_unauthorized(f"test-token-{uuid4()}")

    def test_owner_with_valid_signature_issuer_audience_and_expiry_is_accepted(self):
        token = self.token()
        self.assertEqual(self.verifier.verify_token(token), self.settings.owner_user_id)

    def test_invalid_signature_is_rejected(self):
        token = self.token(key=self.other_private_key)
        self.assert_unauthorized(token)

    def test_wrong_issuer_and_expired_tokens_are_rejected(self):
        self.assert_unauthorized(self.token(issuer="https://attacker.invalid/auth/v1"))
        self.assert_unauthorized(self.token(expires=int(time.time()) - 1))

    def test_publishable_key_is_not_accepted_as_hs256_secret(self):
        token = self.token(
            key=self.settings.supabase_publishable_key,
            algorithm="HS256",
        )
        self.assert_unauthorized(token)

    def test_valid_token_for_another_user_is_forbidden(self):
        token = self.token(subject=uuid4())
        with self.assertRaises(AuthError) as error:
            self.verifier.verify_token(token)
        self.assertEqual(error.exception.status_code, 403)


if __name__ == "__main__":
    unittest.main()
