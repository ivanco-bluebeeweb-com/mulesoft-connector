"""Chat functions for MuleSoft Connector: connection management, CloudHub
applications (list/get/start/stop/restart/update/delete/logs), alerts,
schedules, API Manager instances, and bulk operations + environment audit
(Ярус 3 value-add). Built on mulesoft_client.py / schemas.py, following
the same shape as Power Automate Connector's handlers.py.
"""
from __future__ import annotations

import json
import uuid

from imperal_sdk import ActionResult

import mulesoft_client as mc
from app import ext, chat
from schemas import (
    NoParams,
    ConnectMulesoftParams, ProviderConnection, ProviderConnectionList,
    DisconnectMulesoftParams, DeleteResult,
    ListCloudhubApplicationsParams, CloudhubApplication, CloudhubApplicationList,
    GetCloudhubApplicationParams,
    StartStopRestartParams, CloudhubActionResult,
    DeleteCloudhubApplicationParams,
    UpdateCloudhubApplicationParams,
    GetCloudhubApplicationLogsParams, CloudhubLogEntry, CloudhubLogList,
    ListCloudhubAlertsParams, CloudhubAlert, CloudhubAlertList,
    CreateCloudhubAlertParams, DeleteCloudhubAlertParams,
    ListCloudhubSchedulesParams, CloudhubSchedule, CloudhubScheduleList,
    SetCloudhubScheduleEnabledParams, RunCloudhubScheduleParams,
    ListApiInstancesParams, ApiInstance, ApiInstanceList,
    GetApiInstanceParams,
    BulkAppResultItem, BulkAppResult, BulkDomainsParams,
    AuditCloudhubEnvironmentParams, CloudhubAuditRow, CloudhubAuditReport,
    GetStaleApplicationsParams,
)

_SECRET_NAME = "mulesoft_connections"


# ──────────────────────────────────────────────────────────────────────────
# Connection storage helpers -- one secret holding a JSON array of
# connection records, same precedent as Power Automate Connector / n8n
# Connector / Make.com Connector (ctx.secrets has no "one secret per id"
# primitive).
# ──────────────────────────────────────────────────────────────────────────


async def _load_connections(ctx) -> list[dict]:
    raw = await ctx.secrets.get(_SECRET_NAME)
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        return []
    return data if isinstance(data, list) else []


async def _save_connections(ctx, connections: list[dict]) -> None:
    await ctx.secrets.set(_SECRET_NAME, json.dumps(connections))


async def _resolve_connection(ctx, connection_id: str = "") -> dict | None:
    connections = await _load_connections(ctx)
    if not connections:
        return None
    if connection_id:
        for c in connections:
            if c.get("id") == connection_id:
                return c
        return None
    return connections[0]


def _connection_to_entity(c: dict) -> ProviderConnection:
    return ProviderConnection(
        id=c.get("id", ""),
        title=c.get("label") or c.get("org_id", ""),
        connected=True,
        detail=f"org {c.get('org_id', '')} / env {c.get('environment_id', '')}",
        org_id=c.get("org_id", ""),
        environment_id=c.get("environment_id", ""),
    )


async def _get_token(ctx, conn: dict) -> dict:
    """Fetch a fresh access token for a stored connection. MuleSoft client-
    credentials tokens are short-lived (default 3600s per Anypoint's own
    OAuth2 token endpoint) -- no refresh-token dance needed, just request a
    new one per call, same simplicity tradeoff as Power Automate Connector.
    """
    return await mc.get_access_token(ctx, conn.get("client_id", ""), conn.get("client_secret", ""))


# ──────────────────────────────────────────────────────────────────────────
# Connection management
# ──────────────────────────────────────────────────────────────────────────


@chat.function(
    "connect_mulesoft",
    "Connect your Anypoint Platform organization by saving your Connected App's "
    "client_id/client_secret plus your organization ID and a default environment "
    "ID, after checking they actually work together. You'll need: a Connected App "
    "(Anypoint Platform > Access Management > Connected Apps > create one as "
    "\"App as Owner\" for machine-to-machine access) granted the permissions you "
    "want to use (e.g. \"Manage Applications\" for CloudHub). Note: this manages "
    "CloudHub Mule applications and API Manager instances -- Design Center specs "
    "and Access Management users/roles are out of scope here.",
    action_type="write",
    chain_callable=True,
    data_model=ProviderConnection,
    event="mulesoft-connector.connect_mulesoft",
    effects=["mulesoft.provider.connected"],
)
async def connect_mulesoft(ctx, params: ConnectMulesoftParams) -> ActionResult:
    """Connect an Anypoint Platform organization via OAuth2 client credentials."""
    client_id = params.client_id.strip()
    client_secret = params.client_secret.strip()
    org_id = params.org_id.strip()
    environment_id = params.environment_id.strip()
    missing = [
        n for n, v in [
            ("client_id", client_id), ("client_secret", client_secret),
            ("org_id", org_id), ("environment_id", environment_id),
        ] if not v
    ]
    if missing:
        return ActionResult.error(
            f"Please provide: {', '.join(missing)}.",
            code="MULESOFT_MISSING_FIELD",
        )
    check = await mc.check_connection(ctx, client_id, client_secret, org_id, environment_id)
    if not check.get("ok"):
        return ActionResult.error(check.get("error", "Could not verify these credentials."), code=check.get("error_code", "MULESOFT_CONNECT_FAILED"))

    connections = await _load_connections(ctx)
    # De-duplicate by (org_id, environment_id) -- reconnecting the same
    # organization/environment updates the existing record in place instead
    # of creating a duplicate, same convention fixed in Power Automate
    # Connector's connect handler.
    existing = next((c for c in connections if c.get("org_id") == org_id and c.get("environment_id") == environment_id), None)
    if existing:
        existing.update({
            "client_id": client_id, "client_secret": client_secret,
            "label": params.label.strip() or existing.get("label", ""),
        })
        record = existing
    else:
        record = {
            "id": str(uuid.uuid4()),
            "client_id": client_id, "client_secret": client_secret,
            "org_id": org_id, "environment_id": environment_id,
            "label": params.label.strip(),
        }
        connections.append(record)
    await _save_connections(ctx, connections)
    return ActionResult.ok(_connection_to_entity(record))


@chat.function(
    "disconnect_mulesoft",
    "Disconnect one Anypoint Platform organization/environment. Nothing in "
    "Anypoint Platform is changed; the saved Connected App credentials are "
    "deleted here.",
    action_type="write",
    chain_callable=True,
    data_model=DeleteResult,
    event="mulesoft-connector.disconnect_mulesoft",
    effects=["mulesoft.provider.disconnected"],
)
async def disconnect_mulesoft(ctx, params: DisconnectMulesoftParams) -> ActionResult:
    connections = await _load_connections(ctx)
    remaining = [c for c in connections if c.get("id") != params.connection_id]
    if len(remaining) == len(connections):
        return ActionResult.error("No such connection.", code="MULESOFT_NOT_FOUND")
    await _save_connections(ctx, remaining)
    return ActionResult.ok(DeleteResult(id=params.connection_id, title="disconnected", ok=True))


@chat.function(
    "list_connections",
    "List the connected Anypoint Platform organizations/environments.",
    action_type="read",
    chain_callable=True,
    data_model=ProviderConnectionList,
    event="mulesoft-connector.list_connections",
)
async def list_connections(ctx, params: NoParams) -> ActionResult:
    connections = await _load_connections(ctx)
    return ActionResult.ok(ProviderConnectionList(
        title="MuleSoft connections",
        items=[_connection_to_entity(c) for c in connections],
    ))


async def _resolve_or_error(ctx, connection_id: str = ""):
    """Shared guard: resolve a connection or return the standard 'not
    connected' ActionResult.error; also mints a token. Returns
    (conn, token, error_or_None)."""
    conn = await _resolve_connection(ctx, connection_id)
    if conn is None:
        return None, None, ActionResult.error(
            "No MuleSoft organization is connected yet. Use connect_mulesoft first.",
            code="MULESOFT_ACCOUNT_MISSING",
        )
    tok = await _get_token(ctx, conn)
    if not tok.get("ok"):
        return None, None, ActionResult.error(tok.get("error", "Could not authenticate."), code=tok.get("error_code", "MULESOFT_TOKEN_REJECTED"))
    return conn, tok["access_token"], None


# ──────────────────────────────────────────────────────────────────────────
# CloudHub applications
# ──────────────────────────────────────────────────────────────────────────


def _app_to_entity(a: dict) -> CloudhubApplication:
    domain = a.get("domain", "")
    mv = a.get("muleVersion") or {}
    return CloudhubApplication(
        id=domain,
        title=domain,
        domain=domain,
        status=a.get("status", ""),
        workers=(a.get("workers") or {}).get("amount", a.get("workers", 0)) if isinstance(a.get("workers"), dict) else (a.get("workers") or 0),
        worker_type=((a.get("workers") or {}).get("type", {}) or {}).get("name", "") if isinstance(a.get("workers"), dict) else "",
        mule_version=mv.get("version", "") if isinstance(mv, dict) else str(mv or ""),
        latest_mule_version=(a.get("muleVersionUpgrade") or {}).get("recommendedVersion", "") if isinstance(a.get("muleVersionUpgrade"), dict) else "",
        region=a.get("region", ""),
        last_update_time=str(a.get("lastUpdateTime", "")),
    )


@chat.function(
    "list_cloudhub_applications",
    "List CloudHub Mule applications in the connected organization/environment, with their status (STARTED/UNDEPLOYED/etc.).",
    action_type="read",
    chain_callable=True,
    data_model=CloudhubApplicationList,
    event="mulesoft-connector.list_cloudhub_applications",
)
async def list_cloudhub_applications(ctx, params: ListCloudhubApplicationsParams) -> ActionResult:
    conn, token, err = await _resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    try:
        apps = await mc.list_applications(ctx, token, conn["org_id"], conn["environment_id"])
    except mc.ClientFail as e:
        return ActionResult.error(e.payload.get("error"), code=e.payload.get("error_code"))
    if params.search:
        needle = params.search.lower()
        apps = [a for a in apps if needle in (a.get("domain", "").lower())]
    return ActionResult.ok(CloudhubApplicationList(
        title=f"{len(apps)} application(s)",
        items=[_app_to_entity(a) for a in apps],
    ))


@chat.function(
    "get_cloudhub_application",
    "Read one CloudHub Mule application in full -- status, workers, Mule runtime version, region.",
    action_type="read",
    chain_callable=True,
    data_model=CloudhubApplication,
    event="mulesoft-connector.get_cloudhub_application",
)
async def get_cloudhub_application(ctx, params: GetCloudhubApplicationParams) -> ActionResult:
    conn, token, err = await _resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    try:
        app = await mc.get_application(ctx, token, conn["org_id"], conn["environment_id"], params.domain)
    except mc.ClientFail as e:
        return ActionResult.error(e.payload.get("error"), code=e.payload.get("error_code"))
    return ActionResult.ok(_app_to_entity(app))


@chat.function(
    "start_cloudhub_application",
    "Start a stopped CloudHub Mule application.",
    action_type="write",
    chain_callable=True,
    data_model=CloudhubActionResult,
    event="mulesoft-connector.start_cloudhub_application",
    effects=["mulesoft.application.started"],
)
async def start_cloudhub_application(ctx, params: StartStopRestartParams) -> ActionResult:
    conn, token, err = await _resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    try:
        await mc.start_application(ctx, token, conn["org_id"], conn["environment_id"], params.domain)
    except mc.ClientFail as e:
        return ActionResult.error(e.payload.get("error"), code=e.payload.get("error_code"))
    return ActionResult.ok(CloudhubActionResult(id=params.domain, title=params.domain, ok=True, detail="started"))


@chat.function(
    "stop_cloudhub_application",
    "Stop a running CloudHub Mule application.",
    action_type="write",
    chain_callable=True,
    data_model=CloudhubActionResult,
    event="mulesoft-connector.stop_cloudhub_application",
    effects=["mulesoft.application.stopped"],
)
async def stop_cloudhub_application(ctx, params: StartStopRestartParams) -> ActionResult:
    conn, token, err = await _resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    try:
        await mc.stop_application(ctx, token, conn["org_id"], conn["environment_id"], params.domain)
    except mc.ClientFail as e:
        return ActionResult.error(e.payload.get("error"), code=e.payload.get("error_code"))
    return ActionResult.ok(CloudhubActionResult(id=params.domain, title=params.domain, ok=True, detail="stopped"))


@chat.function(
    "restart_cloudhub_application",
    "Restart a CloudHub Mule application.",
    action_type="write",
    chain_callable=True,
    data_model=CloudhubActionResult,
    event="mulesoft-connector.restart_cloudhub_application",
    effects=["mulesoft.application.restarted"],
)
async def restart_cloudhub_application(ctx, params: StartStopRestartParams) -> ActionResult:
    conn, token, err = await _resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    try:
        await mc.restart_application(ctx, token, conn["org_id"], conn["environment_id"], params.domain)
    except mc.ClientFail as e:
        return ActionResult.error(e.payload.get("error"), code=e.payload.get("error_code"))
    return ActionResult.ok(CloudhubActionResult(id=params.domain, title=params.domain, ok=True, detail="restarted"))


@chat.function(
    "update_cloudhub_application",
    "Update a CloudHub Mule application's workers, worker size, or application properties.",
    action_type="write",
    chain_callable=True,
    data_model=CloudhubActionResult,
    event="mulesoft-connector.update_cloudhub_application",
    effects=["mulesoft.application.updated"],
)
async def update_cloudhub_application(ctx, params: UpdateCloudhubApplicationParams) -> ActionResult:
    conn, token, err = await _resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    try:
        await mc.update_application(
            ctx, token, conn["org_id"], conn["environment_id"], params.domain,
            workers=params.workers, properties=params.properties,
        )
    except mc.ClientFail as e:
        return ActionResult.error(e.payload.get("error"), code=e.payload.get("error_code"))
    return ActionResult.ok(CloudhubActionResult(id=params.domain, title=params.domain, ok=True, detail="updated"))


@chat.function(
    "delete_cloudhub_application",
    "Permanently delete (undeploy) a CloudHub Mule application. Cannot be undone.",
    action_type="destructive",
    chain_callable=True,
    data_model=DeleteResult,
    event="mulesoft-connector.delete_cloudhub_application",
    effects=["mulesoft.application.deleted"],
)
async def delete_cloudhub_application(ctx, params: DeleteCloudhubApplicationParams) -> ActionResult:
    conn, token, err = await _resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    try:
        await mc.delete_application(ctx, token, conn["org_id"], conn["environment_id"], params.domain)
    except mc.ClientFail as e:
        return ActionResult.error(e.payload.get("error"), code=e.payload.get("error_code"))
    return ActionResult.ok(DeleteResult(id=params.domain, title=params.domain, ok=True))


@chat.function(
    "get_cloudhub_application_logs",
    "Read recent log lines for a CloudHub Mule application.",
    action_type="read",
    chain_callable=True,
    data_model=CloudhubLogList,
    event="mulesoft-connector.get_cloudhub_application_logs",
)
async def get_cloudhub_application_logs(ctx, params: GetCloudhubApplicationLogsParams) -> ActionResult:
    conn, token, err = await _resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    try:
        logs = await mc.get_application_logs(ctx, token, conn["org_id"], conn["environment_id"], params.domain, limit=params.limit)
    except mc.ClientFail as e:
        return ActionResult.error(e.payload.get("error"), code=e.payload.get("error_code"))
    items = [
        CloudhubLogEntry(
            id=str(i), title=str(l.get("priority", "")),
            timestamp=str(l.get("timestamp", "")), priority=str(l.get("priority", "")),
            message=str(l.get("message", "")),
        )
        for i, l in enumerate(logs)
    ]
    return ActionResult.ok(CloudhubLogList(title=f"{len(items)} log line(s)", items=items))


# ──────────────────────────────────────────────────────────────────────────
# CloudHub alerts
# ──────────────────────────────────────────────────────────────────────────


@chat.function(
    "list_cloudhub_alerts",
    "List alerts configured on a CloudHub Mule application.",
    action_type="read",
    chain_callable=True,
    data_model=CloudhubAlertList,
    event="mulesoft-connector.list_cloudhub_alerts",
)
async def list_cloudhub_alerts(ctx, params: ListCloudhubAlertsParams) -> ActionResult:
    conn, token, err = await _resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    try:
        alerts = await mc.list_alerts(ctx, token, conn["org_id"], conn["environment_id"], params.domain)
    except mc.ClientFail as e:
        return ActionResult.error(e.payload.get("error"), code=e.payload.get("error_code"))
    items = [
        CloudhubAlert(
            id=str(a.get("id", "")), title=str(a.get("name", "")), domain=params.domain,
            enabled=bool(a.get("enabled", True)), watch=str(a.get("watch", "")),
            condition=json.dumps(a.get("condition", {})) if isinstance(a.get("condition"), dict) else str(a.get("condition", "")),
        )
        for a in alerts
    ]
    return ActionResult.ok(CloudhubAlertList(title=f"{len(items)} alert(s)", items=items))


@chat.function(
    "create_cloudhub_alert",
    "Create a new alert watching a CloudHub Mule application (e.g. notify on application status changes or restarts).",
    action_type="write",
    chain_callable=True,
    data_model=CloudhubAlert,
    event="mulesoft-connector.create_cloudhub_alert",
    effects=["mulesoft.alert.created"],
)
async def create_cloudhub_alert(ctx, params: CreateCloudhubAlertParams) -> ActionResult:
    conn, token, err = await _resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    try:
        alert = await mc.create_alert(
            ctx, token, conn["org_id"], conn["environment_id"], params.domain,
            name=params.name, condition={"watch": params.watch}, enabled=params.enabled,
        )
    except mc.ClientFail as e:
        return ActionResult.error(e.payload.get("error"), code=e.payload.get("error_code"))
    return ActionResult.ok(CloudhubAlert(
        id=str(alert.get("id", "")), title=params.name, domain=params.domain,
        enabled=params.enabled, watch=params.watch, condition="",
    ))


@chat.function(
    "delete_cloudhub_alert",
    "Permanently delete a CloudHub application alert. Cannot be undone.",
    action_type="destructive",
    chain_callable=True,
    data_model=DeleteResult,
    event="mulesoft-connector.delete_cloudhub_alert",
    effects=["mulesoft.alert.deleted"],
)
async def delete_cloudhub_alert(ctx, params: DeleteCloudhubAlertParams) -> ActionResult:
    conn, token, err = await _resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    domain = params.alert_id.split(":", 1)[0] if ":" in params.alert_id else ""
    alert_id = params.alert_id.split(":", 1)[1] if ":" in params.alert_id else params.alert_id
    if not domain:
        return ActionResult.error(
            "alert_id must be in 'domain:alertId' form, as returned by list_cloudhub_alerts.",
            code="MULESOFT_VALIDATION_FAILED",
        )
    try:
        await mc.delete_alert(ctx, token, conn["org_id"], conn["environment_id"], domain, alert_id)
    except mc.ClientFail as e:
        return ActionResult.error(e.payload.get("error"), code=e.payload.get("error_code"))
    return ActionResult.ok(DeleteResult(id=params.alert_id, title="deleted", ok=True))


# ──────────────────────────────────────────────────────────────────────────
# CloudHub schedules
# ──────────────────────────────────────────────────────────────────────────


@chat.function(
    "list_cloudhub_schedules",
    "List scheduled flow triggers configured on a CloudHub Mule application.",
    action_type="read",
    chain_callable=True,
    data_model=CloudhubScheduleList,
    event="mulesoft-connector.list_cloudhub_schedules",
)
async def list_cloudhub_schedules(ctx, params: ListCloudhubSchedulesParams) -> ActionResult:
    conn, token, err = await _resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    try:
        schedules = await mc.list_schedules(ctx, token, conn["org_id"], conn["environment_id"], params.domain)
    except mc.ClientFail as e:
        return ActionResult.error(e.payload.get("error"), code=e.payload.get("error_code"))
    items = [
        CloudhubSchedule(
            id=str(s.get("name", "")), title=str(s.get("name", "")), domain=params.domain,
            enabled=bool(s.get("enabled", True)), flow_name=str(s.get("flowName", "")),
        )
        for s in schedules
    ]
    return ActionResult.ok(CloudhubScheduleList(title=f"{len(items)} schedule(s)", items=items))


@chat.function(
    "set_cloudhub_schedule_enabled",
    "Enable or disable a scheduled flow trigger on a CloudHub Mule application.",
    action_type="write",
    chain_callable=True,
    data_model=CloudhubActionResult,
    event="mulesoft-connector.set_cloudhub_schedule_enabled",
    effects=["mulesoft.schedule.updated"],
)
async def set_cloudhub_schedule_enabled(ctx, params: SetCloudhubScheduleEnabledParams) -> ActionResult:
    conn, token, err = await _resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    try:
        await mc.set_schedule_enabled(ctx, token, conn["org_id"], conn["environment_id"], params.domain, params.schedule_id, params.enabled)
    except mc.ClientFail as e:
        return ActionResult.error(e.payload.get("error"), code=e.payload.get("error_code"))
    return ActionResult.ok(CloudhubActionResult(id=params.schedule_id, title=params.schedule_id, ok=True, detail="enabled" if params.enabled else "disabled"))


@chat.function(
    "run_cloudhub_schedule",
    "Run a CloudHub application's scheduled flow trigger immediately, regardless of its schedule.",
    action_type="write",
    chain_callable=True,
    data_model=CloudhubActionResult,
    event="mulesoft-connector.run_cloudhub_schedule",
    effects=["mulesoft.schedule.run"],
)
async def run_cloudhub_schedule(ctx, params: RunCloudhubScheduleParams) -> ActionResult:
    conn, token, err = await _resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    try:
        await mc.run_schedule(ctx, token, conn["org_id"], conn["environment_id"], params.domain, params.schedule_id)
    except mc.ClientFail as e:
        return ActionResult.error(e.payload.get("error"), code=e.payload.get("error_code"))
    return ActionResult.ok(CloudhubActionResult(id=params.schedule_id, title=params.schedule_id, ok=True, detail="ran"))


# ──────────────────────────────────────────────────────────────────────────
# API Manager instances
# ──────────────────────────────────────────────────────────────────────────


@chat.function(
    "list_api_instances",
    "List API instances registered in API Manager for the connected organization/environment.",
    action_type="read",
    chain_callable=True,
    data_model=ApiInstanceList,
    event="mulesoft-connector.list_api_instances",
)
async def list_api_instances(ctx, params: ListApiInstancesParams) -> ActionResult:
    conn, token, err = await _resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    try:
        apis = await mc.list_api_instances(ctx, token, conn["org_id"], conn["environment_id"])
    except mc.ClientFail as e:
        return ActionResult.error(e.payload.get("error"), code=e.payload.get("error_code"))
    if params.search:
        needle = params.search.lower()
        apis = [a for a in apis if needle in str(a.get("assetId", "")).lower()]
    items = [
        ApiInstance(
            id=str(a.get("id", "")), title=str(a.get("assetId", "")),
            asset_id=str(a.get("assetId", "")), asset_version=str(a.get("assetVersion", "")),
            environment_id=conn["environment_id"], tracking_status=str(a.get("lastActiveDate") and "active" or "unregistered"),
            endpoint_uri=str((a.get("endpoint") or {}).get("uri", "")) if isinstance(a.get("endpoint"), dict) else "",
        )
        for a in apis
    ]
    return ActionResult.ok(ApiInstanceList(title=f"{len(items)} API instance(s)", items=items))


@chat.function(
    "get_api_instance",
    "Read one API Manager instance in full.",
    action_type="read",
    chain_callable=True,
    data_model=ApiInstance,
    event="mulesoft-connector.get_api_instance",
)
async def get_api_instance(ctx, params: GetApiInstanceParams) -> ActionResult:
    conn, token, err = await _resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    try:
        a = await mc.get_api_instance(ctx, token, conn["org_id"], conn["environment_id"], params.api_id)
    except mc.ClientFail as e:
        return ActionResult.error(e.payload.get("error"), code=e.payload.get("error_code"))
    return ActionResult.ok(ApiInstance(
        id=str(a.get("id", "")), title=str(a.get("assetId", "")),
        asset_id=str(a.get("assetId", "")), asset_version=str(a.get("assetVersion", "")),
        environment_id=conn["environment_id"], tracking_status=str(a.get("lastActiveDate") and "active" or "unregistered"),
        endpoint_uri=str((a.get("endpoint") or {}).get("uri", "")) if isinstance(a.get("endpoint"), dict) else "",
    ))


# ──────────────────────────────────────────────────────────────────────────
# Bulk operations + environment audit (Ярус 3 value-add)
# ──────────────────────────────────────────────────────────────────────────


def _bulk_to_result(raw: list[dict], title: str) -> BulkAppResult:
    items = [
        BulkAppResultItem(id=r["domain"], title=r["domain"], domain=r["domain"], ok=r["ok"], error=r.get("error", ""))
        for r in raw
    ]
    succeeded = sum(1 for r in raw if r["ok"])
    return BulkAppResult(title=title, items=items, succeeded=succeeded, failed=len(raw) - succeeded)


@chat.function(
    "bulk_start_cloudhub_applications",
    "Start SEVERAL CloudHub Mule applications in one call, by explicit domains. Continues past individual failures and reports per-domain results.",
    action_type="write",
    chain_callable=True,
    data_model=BulkAppResult,
    event="mulesoft-connector.bulk_start_cloudhub_applications",
    effects=["mulesoft.application.started"],
)
async def bulk_start_cloudhub_applications(ctx, params: BulkDomainsParams) -> ActionResult:
    conn, token, err = await _resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    raw = await mc.bulk_set_application_status(ctx, token, conn["org_id"], conn["environment_id"], params.domains, "START")
    return ActionResult.ok(_bulk_to_result(raw, "Bulk start"))


@chat.function(
    "bulk_stop_cloudhub_applications",
    "Stop SEVERAL CloudHub Mule applications in one call, by explicit domains. Continues past individual failures and reports per-domain results.",
    action_type="write",
    chain_callable=True,
    data_model=BulkAppResult,
    event="mulesoft-connector.bulk_stop_cloudhub_applications",
    effects=["mulesoft.application.stopped"],
)
async def bulk_stop_cloudhub_applications(ctx, params: BulkDomainsParams) -> ActionResult:
    conn, token, err = await _resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    raw = await mc.bulk_set_application_status(ctx, token, conn["org_id"], conn["environment_id"], params.domains, "STOP")
    return ActionResult.ok(_bulk_to_result(raw, "Bulk stop"))


@chat.function(
    "bulk_restart_cloudhub_applications",
    "Restart SEVERAL CloudHub Mule applications in one call, by explicit domains. Continues past individual failures and reports per-domain results.",
    action_type="write",
    chain_callable=True,
    data_model=BulkAppResult,
    event="mulesoft-connector.bulk_restart_cloudhub_applications",
    effects=["mulesoft.application.restarted"],
)
async def bulk_restart_cloudhub_applications(ctx, params: BulkDomainsParams) -> ActionResult:
    conn, token, err = await _resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    raw = await mc.bulk_set_application_status(ctx, token, conn["org_id"], conn["environment_id"], params.domains, "RESTART")
    return ActionResult.ok(_bulk_to_result(raw, "Bulk restart"))


@chat.function(
    "bulk_delete_cloudhub_applications",
    "Permanently delete SEVERAL CloudHub Mule applications in one call, by explicit domains. Cannot be undone. Continues past individual failures and reports per-domain results.",
    action_type="destructive",
    chain_callable=True,
    data_model=BulkAppResult,
    event="mulesoft-connector.bulk_delete_cloudhub_applications",
    effects=["mulesoft.application.deleted"],
)
async def bulk_delete_cloudhub_applications(ctx, params: BulkDomainsParams) -> ActionResult:
    conn, token, err = await _resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    raw = await mc.bulk_delete_applications(ctx, token, conn["org_id"], conn["environment_id"], params.domains)
    return ActionResult.ok(_bulk_to_result(raw, "Bulk delete"))


@chat.function(
    "audit_cloudhub_environment",
    "Build one aggregated health report across every CloudHub Mule application in the connected environment -- status, worker count, current vs. latest recommended Mule runtime version, and staleness -- in a single call instead of paging through list_cloudhub_applications by hand. This is a connector-native convenience, not a native Anypoint Platform report.",
    action_type="read",
    chain_callable=True,
    data_model=CloudhubAuditReport,
    event="mulesoft-connector.audit_cloudhub_environment",
)
async def audit_cloudhub_environment(ctx, params: AuditCloudhubEnvironmentParams) -> ActionResult:
    conn, token, err = await _resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    try:
        apps = await mc.list_applications(ctx, token, conn["org_id"], conn["environment_id"])
    except mc.ClientFail as e:
        return ActionResult.error(e.payload.get("error"), code=e.payload.get("error_code"))
    rows = []
    stale_count = 0
    stopped_count = 0
    for a in apps:
        domain = a.get("domain", "")
        status = a.get("status", "")
        mv = a.get("muleVersion") or {}
        current_v = mv.get("version", "") if isinstance(mv, dict) else str(mv or "")
        upgrade = a.get("muleVersionUpgrade") or {}
        latest_v = upgrade.get("recommendedVersion", "") if isinstance(upgrade, dict) else ""
        is_stale = bool(latest_v) and latest_v != current_v
        if is_stale:
            stale_count += 1
        if status not in ("STARTED",):
            stopped_count += 1
        workers = (a.get("workers") or {}).get("amount", a.get("workers", 0)) if isinstance(a.get("workers"), dict) else (a.get("workers") or 0)
        rows.append(CloudhubAuditRow(
            id=domain, title=domain, domain=domain, status=status, workers=workers,
            mule_version=current_v, latest_mule_version=latest_v, is_stale=is_stale,
            last_update_time=str(a.get("lastUpdateTime", "")),
        ))
    return ActionResult.ok(CloudhubAuditReport(
        title=f"CloudHub environment audit -- {len(rows)} application(s)",
        items=rows, total=len(rows), stale_count=stale_count, stopped_count=stopped_count,
    ))


@chat.function(
    "get_stale_applications",
    "List only the CloudHub Mule applications running on an outdated Mule runtime version compared to Anypoint's own recommended upgrade -- a filtered view of audit_cloudhub_environment for teams that just want the upgrade backlog.",
    action_type="read",
    chain_callable=True,
    data_model=CloudhubAuditReport,
    event="mulesoft-connector.get_stale_applications",
)
async def get_stale_applications(ctx, params: GetStaleApplicationsParams) -> ActionResult:
    conn, token, err = await _resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    try:
        apps = await mc.list_applications(ctx, token, conn["org_id"], conn["environment_id"])
    except mc.ClientFail as e:
        return ActionResult.error(e.payload.get("error"), code=e.payload.get("error_code"))
    rows = []
    for a in apps:
        mv = a.get("muleVersion") or {}
        current_v = mv.get("version", "") if isinstance(mv, dict) else str(mv or "")
        upgrade = a.get("muleVersionUpgrade") or {}
        latest_v = upgrade.get("recommendedVersion", "") if isinstance(upgrade, dict) else ""
        if latest_v and latest_v != current_v:
            domain = a.get("domain", "")
            workers = (a.get("workers") or {}).get("amount", a.get("workers", 0)) if isinstance(a.get("workers"), dict) else (a.get("workers") or 0)
            rows.append(CloudhubAuditRow(
                id=domain, title=domain, domain=domain, status=a.get("status", ""), workers=workers,
                mule_version=current_v, latest_mule_version=latest_v, is_stale=True,
                last_update_time=str(a.get("lastUpdateTime", "")),
            ))
    return ActionResult.ok(CloudhubAuditReport(
        title=f"{len(rows)} stale application(s)",
        items=rows, total=len(rows), stale_count=len(rows), stopped_count=0,
    ))
