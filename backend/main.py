import hashlib
import hmac
import logging
import re as _re

import inngest.fast_api
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.core.settings import settings
from backend.routers import auth, chat, dishes, sessions
from backend.services.inngest_client import inngest_client
from pipeline.functions import cooking_pipeline

# Surface the Inngest SDK's internal logger so Cloud Run captures API-level
# failures (e.g. _get_batch / _get_steps auth errors) that would otherwise
# appear only as silent HTTP 500s with no Python traceback.
# INFO is sufficient: the SDK uses logger.error() for failures we care about.
logging.getLogger("inngest").setLevel(logging.INFO)

# ---------------------------------------------------------------------------
# Workaround: inngest SDK 0.5.x bug — _validate_sig uses urllib.parse.parse_qs
# to parse the x-inngest-signature header.  parse_qs only splits on '&', but
# the SDK internally builds the header as "t=TIMESTAMP&s=SIGNATURE" and
# parse_qs returns {"t": ["TIMESTAMP"], "s": ["SIGNATURE"]} — except the SDK
# then calls int(values[0]) expecting a list of ONE item, but the key lookup
# can fail if the actual header format ever differs.  More critically, in some
# SDK versions the header is parsed incorrectly, causing ValueError which
# propagates as an unhandled exception and makes uvicorn return a 500.
#
# Fix: replace _validate_sig with a robust implementation that splits on both
# ',' and '&'.  Remove this patch once the upstream SDK issue is resolved.
# ---------------------------------------------------------------------------
from inngest._internal import errors as _inngest_errors  # noqa: E402
from inngest._internal import net as _inngest_net  # noqa: E402
from inngest._internal import server_lib as _inngest_server_lib  # noqa: E402
from inngest._internal import transforms as _inngest_transforms  # noqa: E402


def _patched_validate_sig(
    body: bytes,
    headers: dict[str, str],
    mode: _inngest_server_lib.ServerKind,
    signing_key: str | None,
) -> str | Exception | None:
    """Replacement for inngest SDK's ``_validate_sig`` (inngest-py <= 0.5.15 bug).

    The SDK uses ``urllib.parse.parse_qs`` to parse the ``x-inngest-signature``
    header (format: ``t=TIMESTAMP&s=SIGNATURE``).  In some SDK versions this
    fails with ValueError, causing uvicorn to return a 500 before user code
    runs.  This replacement parses the header directly with a split on ``[,&]``.
    Remove once the upstream SDK issue is resolved.
    """
    if mode == _inngest_server_lib.ServerKind.DEV_SERVER:
        return None

    sig_header = headers.get(_inngest_server_lib.HeaderKey.SIGNATURE.value)
    if sig_header is None:
        return _inngest_errors.HeaderMissingError(
            f"cannot validate signature in production mode without a "
            f"{_inngest_server_lib.HeaderKey.SIGNATURE.value} header"
        )

    timestamp_str: str | None = None
    signature: str | None = None
    for part in _re.split(r"[,&]", sig_header):
        part = part.strip()
        if "=" in part:
            k, v = part.split("=", 1)
            k = k.strip()
            if k == "t":
                raw = v.strip()
                try:
                    parsed_ts = int(raw)
                except ValueError:
                    return _inngest_errors.SigVerificationFailedError()
                timestamp_str = str(parsed_ts)
            elif k == "s":
                signature = v.strip()

    if signing_key is None:
        return _inngest_errors.SigningKeyMissingError(
            "cannot validate signature in production mode without a signing key"
        )

    if timestamp_str is None or signature is None:
        return _inngest_errors.SigVerificationFailedError()

    key_without_prefix = _inngest_transforms.remove_signing_key_prefix(signing_key)
    mac = hmac.new(
        key_without_prefix.encode("utf-8"),
        body,
        hashlib.sha256,
    )
    mac.update(timestamp_str.encode("utf-8"))
    computed = mac.hexdigest()

    if not hmac.compare_digest(signature, computed):
        return _inngest_errors.SigVerificationFailedError()

    return signing_key


_inngest_net._validate_sig = _patched_validate_sig  # type: ignore[assignment]

app = FastAPI(
    title="Moment Clone API",
    description="AI cooking coaching backend",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(dishes.router)
app.include_router(sessions.router)
app.include_router(chat.router)

# Mount Inngest durable pipeline at /api/inngest
inngest.fast_api.serve(app, inngest_client, [cooking_pipeline])


@app.get("/health")
def health_check() -> dict:
    return {"status": "ok"}
