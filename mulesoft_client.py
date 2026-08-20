"""MuleSoft Anypoint Platform HTTP client -- OAuth2 client-credentials auth
against a user's own Connected App, thin wrappers around the CloudHub API
(Mule application lifecycle) and API Manager API (managed API registry).

WHY CLIENT CREDENTIALS (Connected App), NOT DELEGATED USER OAUTH -- see
app.py module docstring for the full architectural reasoning. Token is
requested against `https://anypoint.mulesoft.com/accounts/api/v2/oauth2/
token` with `grant_type=client_credentials`.

WHY CLOUDHUB API AS THE PRIMARY SURFACE.

CloudHub API (`anypoint.mulesoft.com/cloudhub/api/*`) is the officially
documented, fully-CRUD surface for managing Mule applications: create,
deploy, start, stop, restart, delete, update metadata (workers, Mule
runtime version), and read logs/alerts/schedules
(docs.mulesoft.com/cloudhub/cloudhub-api, confirmed 2026-08-20). Every
call requires the organization id and environment id as headers
(`X-ANYPNT-ORG-ID`, `X-ANYPNT-ENV-ID`) alongside the bearer token --
Anypoint orgs are explicitly multi-environment (Dev/Test/Sandbox/
Production), so these are not optional path components but required
per-request context, same shape as Power Automate's environment_url.

WHY 401 vs 403 ARE HANDLED DIFFERENTLY, SAME PRINCIPLE AS n8n/Make.com/
Power Automate CONNECTOR's clients.

A 401 means the Connected App's credentials are not accepted at all
(wrong client_id/client_secret, or the token request itself failed). A
403 means the token was issued fine, but the Connected App lacks the
Anypoint permission (e.g. "Manage Applications") for this specific
organization/environment/operation -- a materially different, more
specific and more fixable cause (the fix is granting a permission in
Access Management, not re-entering credentials) that must not be
reported as "wrong credentials".
"""
from __future__ import annotations

ANYPOINT_BASE = "https://anypoint.mulesoft.com"
TOKEN_URL = f"{ANYPOINT_BASE}/accounts/api/v2/oauth2/token"
CLOUDHUB_BASE = f"{ANYPOINT_BASE}/cloudhub/api"
APIMANAGER_BASE = f"{ANYPOINT_BASE}/apimanager/api/v1"

ACCOUNT_MISSING = "MULESOFT_ACCOUNT_MISSING"
TOKEN_REJECTED = "MULESOFT_TOKEN_REJECTED"
PERMISSION_DENIED = "MULESOFT_PERMISSION_DENIED"
NOT_FOUND = "MULESOFT_NOT_FOUND"
VALIDATION_FAILED = "MULESOFT_VALIDATION_FAILED"
RESPONSE_UNEXPECTED = "MULESOFT_RESPONSE_UNEXPECTED"
UNREACHABLE = "MULESOFT_UNREACHABLE"
RATE_LIMITED = "MULESOFT_RATE_LIMITED"
BACKEND_5XX = "MULESOFT_BACKEND_5XX"
BACKEND_TIMEOUT = "MULESOFT_BACKEND_TIMEOUT"

_MESSAGES = {
    ACCOUNT_MISSING: "No MuleSoft organization is connected yet.",
    TOKEN_REJECTED: "Anypoint Platform rejected these credentials. Check the client ID and client secret, then reconnect.",
    PERMISSION_DENIED: "Anypoint Platform accepted the credentials, but this Connected App lacks the permission for this operation (e.g. \"Manage Applications\"). Grant it the required permission in Access Management for this organization/environment.",
    NOT_FOUND: "Anypoint Platform has no such application/instance, or this organization cannot access it.",
    VALIDATION_FAILED: "Anypoint Platform rejected the request as invalid.",
    RESPONSE_UNEXPECTED: "Anypoint Platform returned a response the connector could not safely interpret.",
    UNREACHABLE: "Could not reach Anypoint Platform.",
    RATE_LIMITED: "Anypoint Platform is rate-limiting requests; try again shortly.",
    BACKEND_5XX: "Anypoint Platform returned a server error; try again shortly.",
    BACKEND_TIMEOUT: "Anypoint Platform took too long to respond; try again shortly.",
}
_RETRYABLE = {RATE_LIMITED, BACKEND_5XX, BACKEND_TIMEOUT}


def fail(code: str, detail: str = "") -> dict:
    message = _MESSAGES.get(code, code)
    if detail:
        message = f"{message} ({detail})"
    return {"ok": False, "error_code": code, "error": message, "retryable": code in _RETRYABLE}


class ClientFail(Exception):
    def __init__(self, payload: dict):
        super().__init__(payload.get("error", "MuleSoft request failed"))
        self.payload = payload


async def get_access_token(ctx, client_id: str, client_secret: str) -> dict:
    """Client-credentials token request against Anypoint Platform's own
    OAuth2 token endpoint. Returns {"ok": True, "access_token": ...} or a
    fail() dict."""
    resp = await ctx.http.post(
        TOKEN_URL,
        json={
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
        },
        headers={"Content-Type": "application/json"},
    )
    if resp.status_code in (400, 401):
        return fail(TOKEN_REJECTED)
    if resp.status_code >= 500:
        return fail(BACKEND_5XX)
    if resp.status_code != 200:
        return fail(RESPONSE_UNEXPECTED, f"token endpoint returned {resp.status_code}")
    body = resp.body if isinstance(resp.body, dict) else {}
    token = body.get("access_token")
    if not token:
        return fail(RESPONSE_UNEXPECTED, "token response had no access_token")
    return {"ok": True, "access_token": token, "expires_in": body.get("expires_in", 3600)}


def _headers(access_token: str, org_id: str, environment_id: str) -> dict:
    return {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
        "Content-Type": "application/json",
        "X-ANYPNT-ORG-ID": org_id,
        "X-ANYPNT-ENV-ID": environment_id,
    }


def _check_status(resp, action: str) -> dict | list:
    if resp.status_code in (200, 201, 202, 204):
        if resp.status_code == 204:
            return {}
        return resp.body if isinstance(resp.body, (dict, list)) else {}
    if resp.status_code == 401:
        raise ClientFail(fail(TOKEN_REJECTED, action))
    if resp.status_code == 403:
        raise ClientFail(fail(PERMISSION_DENIED, action))
    if resp.status_code == 404:
        raise ClientFail(fail(NOT_FOUND, action))
    if resp.status_code == 429:
        raise ClientFail(fail(RATE_LIMITED, action))
    if resp.status_code >= 500:
        raise ClientFail(fail(BACKEND_5XX, action))
    if resp.status_code == 400:
        raise ClientFail(fail(VALIDATION_FAILED, action))
    raise ClientFail(fail(RESPONSE_UNEXPECTED, f"{action}: HTTP {resp.status_code}"))


async def check_connection(ctx, client_id: str, client_secret: str, org_id: str, environment_id: str) -> dict:
    """Get a token, then a cheap GET /applications to prove the Connected
    App actually has a working permission -- a valid token alone does not
    guarantee CloudHub access (see PERMISSION_DENIED docstring above)."""
    tok = await get_access_token(ctx, client_id, client_secret)
    if not tok.get("ok"):
        return tok
    resp = await ctx.http.get(
        f"{CLOUDHUB_BASE}/applications",
        headers=_headers(tok["access_token"], org_id, environment_id),
    )
    try:
        _check_status(resp, "verify connection")
    except ClientFail as e:
        return e.payload
    return {"ok": True}


# ──────────────────────────────────────────────────────────────────────────
# CloudHub applications
# ──────────────────────────────────────────────────────────────────────────


async def list_applications(ctx, access_token: str, org_id: str, environment_id: str) -> list[dict]:
    resp = await ctx.http.get(
        f"{CLOUDHUB_BASE}/applications",
        headers=_headers(access_token, org_id, environment_id),
    )
    body = _check_status(resp, "list applications")
    return body if isinstance(body, list) else body.get("data") or []


async def get_application(ctx, access_token: str, org_id: str, environment_id: str, domain: str) -> dict:
    resp = await ctx.http.get(
        f"{CLOUDHUB_BASE}/applications/{domain}",
        headers=_headers(access_token, org_id, environment_id),
    )
    return _check_status(resp, "get application")


async def set_application_status(
    ctx, access_token: str, org_id: str, environment_id: str, domain: str, status: str,
) -> dict:
    """status: 'START', 'STOP', or 'RESTART' -- CloudHub's own tri-state
    lifecycle action endpoint (POST /applications/{domain}/status)."""
    resp = await ctx.http.post(
        f"{CLOUDHUB_BASE}/applications/{domain}/status",
        headers=_headers(access_token, org_id, environment_id),
        json={"status": status},
    )
    return _check_status(resp, f"set application status ({status})")


async def start_application(ctx, access_token: str, org_id: str, environment_id: str, domain: str) -> dict:
    return await set_application_status(ctx, access_token, org_id, environment_id, domain, "START")


async def stop_application(ctx, access_token: str, org_id: str, environment_id: str, domain: str) -> dict:
    return await set_application_status(ctx, access_token, org_id, environment_id, domain, "STOP")


async def restart_application(ctx, access_token: str, org_id: str, environment_id: str, domain: str) -> dict:
    return await set_application_status(ctx, access_token, org_id, environment_id, domain, "RESTART")


async def update_application(
    ctx, access_token: str, org_id: str, environment_id: str, domain: str, *,
    workers: int | None = None, mule_version: str | None = None,
    properties: dict | None = None,
) -> dict:
    payload: dict = {}
    if workers is not None:
        payload["workers"] = workers
    if mule_version is not None:
        payload["muleVersion"] = {"version": mule_version}
    if properties is not None:
        payload["properties"] = properties
    resp = await ctx.http.put(
        f"{CLOUDHUB_BASE}/applications/{domain}",
        headers=_headers(access_token, org_id, environment_id),
        json=payload,
    )
    return _check_status(resp, "update application")


async def delete_application(ctx, access_token: str, org_id: str, environment_id: str, domain: str) -> dict:
    resp = await ctx.http.delete(
        f"{CLOUDHUB_BASE}/applications/{domain}",
        headers=_headers(access_token, org_id, environment_id),
    )
    return _check_status(resp, "delete application")


async def get_application_logs(
    ctx, access_token: str, org_id: str, environment_id: str, domain: str, *, limit: int = 100,
) -> list[dict]:
    resp = await ctx.http.get(
        f"{CLOUDHUB_BASE}/applications/{domain}/logs",
        headers=_headers(access_token, org_id, environment_id),
        params={"limit": limit},
    )
    body = _check_status(resp, "get application logs")
    return body if isinstance(body, list) else body.get("data") or []


# ──────────────────────────────────────────────────────────────────────────
# CloudHub alerts
# ──────────────────────────────────────────────────────────────────────────


async def list_alerts(ctx, access_token: str, org_id: str, environment_id: str, domain: str) -> list[dict]:
    resp = await ctx.http.get(
        f"{CLOUDHUB_BASE}/applications/{domain}/alerts",
        headers=_headers(access_token, org_id, environment_id),
    )
    body = _check_status(resp, "list alerts")
    return body if isinstance(body, list) else body.get("data") or []


async def create_alert(
    ctx, access_token: str, org_id: str, environment_id: str, domain: str, *,
    name: str, condition: dict, enabled: bool = True,
) -> dict:
    payload = {"name": name, "enabled": enabled, **condition}
    resp = await ctx.http.post(
        f"{CLOUDHUB_BASE}/applications/{domain}/alerts",
        headers=_headers(access_token, org_id, environment_id),
        json=payload,
    )
    return _check_status(resp, "create alert")


async def delete_alert(ctx, access_token: str, org_id: str, environment_id: str, domain: str, alert_id: str) -> dict:
    resp = await ctx.http.delete(
        f"{CLOUDHUB_BASE}/applications/{domain}/alerts/{alert_id}",
        headers=_headers(access_token, org_id, environment_id),
    )
    return _check_status(resp, "delete alert")


# ──────────────────────────────────────────────────────────────────────────
# CloudHub schedules
# ──────────────────────────────────────────────────────────────────────────


async def list_schedules(ctx, access_token: str, org_id: str, environment_id: str, domain: str) -> list[dict]:
    resp = await ctx.http.get(
        f"{CLOUDHUB_BASE}/applications/{domain}/schedules",
        headers=_headers(access_token, org_id, environment_id),
    )
    body = _check_status(resp, "list schedules")
    return body if isinstance(body, list) else body.get("data") or []


async def set_schedule_enabled(
    ctx, access_token: str, org_id: str, environment_id: str, domain: str, schedule_name: str, enabled: bool,
) -> dict:
    resp = await ctx.http.put(
        f"{CLOUDHUB_BASE}/applications/{domain}/schedules/{schedule_name}",
        headers=_headers(access_token, org_id, environment_id),
        json={"enabled": enabled},
    )
    return _check_status(resp, "set schedule enabled")


async def run_schedule(ctx, access_token: str, org_id: str, environment_id: str, domain: str, schedule_name: str) -> dict:
    resp = await ctx.http.post(
        f"{CLOUDHUB_BASE}/applications/{domain}/schedules/{schedule_name}/run",
        headers=_headers(access_token, org_id, environment_id),
        json={},
    )
    return _check_status(resp, "run schedule")


# ──────────────────────────────────────────────────────────────────────────
# API Manager -- managed API instance registry (read-focused this release)
# ──────────────────────────────────────────────────────────────────────────


async def list_api_instances(ctx, access_token: str, org_id: str, environment_id: str, *, limit: int = 50) -> list[dict]:
    resp = await ctx.http.get(
        f"{APIMANAGER_BASE}/organizations/{org_id}/environments/{environment_id}/apis",
        headers=_headers(access_token, org_id, environment_id),
        params={"limit": limit},
    )
    body = _check_status(resp, "list API instances")
    return body.get("assets") or body.get("data") or [] if isinstance(body, dict) else (body or [])


async def get_api_instance(ctx, access_token: str, org_id: str, environment_id: str, api_id: str) -> dict:
    resp = await ctx.http.get(
        f"{APIMANAGER_BASE}/organizations/{org_id}/environments/{environment_id}/apis/{api_id}",
        headers=_headers(access_token, org_id, environment_id),
    )
    return _check_status(resp, "get API instance")


# ──────────────────────────────────────────────────────────────────────────
# Bulk operations + environment audit (Ярус 3 value-add -- NOT native to
# either Anypoint API; this connector's own convenience layer, looping the
# single-item calls above with per-item error isolation so one bad domain
# doesn't abort the rest, same principle as Power Automate Connector's
# bulk_set_flow_state/bulk_delete_flows).
# ──────────────────────────────────────────────────────────────────────────


async def bulk_set_application_status(
    ctx, access_token: str, org_id: str, environment_id: str, domains: list[str], status: str,
) -> list[dict]:
    results = []
    for domain in domains:
        try:
            await set_application_status(ctx, access_token, org_id, environment_id, domain, status)
            results.append({"domain": domain, "ok": True})
        except ClientFail as e:
            results.append({"domain": domain, "ok": False, "error": e.payload.get("error")})
    return results


async def bulk_delete_applications(ctx, access_token: str, org_id: str, environment_id: str, domains: list[str]) -> list[dict]:
    results = []
    for domain in domains:
        try:
            await delete_application(ctx, access_token, org_id, environment_id, domain)
            results.append({"domain": domain, "ok": True})
        except ClientFail as e:
            results.append({"domain": domain, "ok": False, "error": e.payload.get("error")})
    return results
