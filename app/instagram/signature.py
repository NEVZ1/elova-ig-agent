from __future__ import annotations

import hmac
import hashlib


def verify_x_hub_signature_256(app_secret: str, raw_body: bytes, signature_header: str | None) -> bool:
    if not app_secret or not signature_header:
        return False
    if not signature_header.startswith("sha256="):
        return False
    expected = hmac.new(app_secret.encode("utf-8"), msg=raw_body, digestmod=hashlib.sha256).hexdigest()
    provided = signature_header.split("=", 1)[1]
    return hmac.compare_digest(expected, provided)

