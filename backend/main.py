import hashlib
import hmac
import logging

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
# to parse the x-inngest-signature header, but parse_qs splits on '&' while
# Inngest Cloud sends "t=TIMESTAMP,s=SIGNATURE" (comma-separated).  This
# causes parse_qs to return {"t": ["TIMESTAMP,s=SIGNATURE"]} so the subsequent
# int() call raises ValueError, which propagates as an unhandled exception and
# makes uvicorn return a plain-text 500 before any user code runs.
#
# Fix: replace _validate_sig with an implementation that splits on ',' first.
# Remove this patch once the upstream SDK issue is resolved.
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
    header, but Inngest Cloud sends it as ``t=TIMESTAMP,s=SIGNATURE``
    (comma-separated).  ``parse_qs`` only splits on ``&``, so it returns
    ``{"t": ["TIMESTAMP,s=SIG"]}`` and the subsequent ``int()`` call raises
    ``ValueError`` — an unhandled exception that makes uvicorn return a 500.

    This replacement splits on ``,`` instead.  Remove once the upstream SDK
    issue (https://github.com/inngest/inngest-py) is resolved.
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
    for part in sig_header.split(","):
        if "=" in part:
            k, v = part.split("=", 1)
            k = k.strip()
            if k == "t":
                raw = v.strip()
                try:
                    int(raw)  # validate it is a valid integer
                except ValueError:
                    return _inngest_errors.SigVerificationFailedError()
                timestamp_str = raw
            elif k == "s":
                signature = v.strip()

    if signing_key is None:
        return _inngest_errors.SigningKeyMissingError(
            "cannot validate signature in production mode without a signing key"
        )

    if timestamp_str is None or signature is None:
        return _inngest_errors.SigVerificationFailedError()

    mac = hmac.new(
        _inngest_transforms.remove_signing_key_prefix(signing_key).encode("utf-8"),
        body,
        hashlib.sha256,
    )
    mac.update(timestamp_str.encode("utf-8"))

    if not hmac.compare_digest(signature, mac.hexdigest()):
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
