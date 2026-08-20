"""Pydantic params models + SDL entity contracts for MuleSoft Connector.

All params models are module-scope (V17 federal invariant, same rule as
Power Automate Connector / Make.com Connector / n8n Connector's schemas.py).
"""
from __future__ import annotations

from pydantic import BaseModel, Field
from imperal_sdk import sdl


class NoParams(BaseModel):
    """Explicit empty params model -- V17 disallows untyped handlers."""
    pass


# ──────────────────────────────────────────────────────────────────────────
# Connection
# ──────────────────────────────────────────────────────────────────────────


class ConnectMulesoftParams(BaseModel):
    client_id: str = Field(
        "",
        description="Client ID of the Anypoint Platform Connected App created for this connection.",
    )
    client_secret: str = Field(
        "",
        description="Client secret of the Anypoint Platform Connected App.",
    )
    org_id: str = Field(
        "",
        description="Your Anypoint Platform organization ID (a GUID), found in Access Management > organization details.",
    )
    environment_id: str = Field(
        "",
        description="Default Anypoint environment ID (a GUID) to operate in, e.g. your Production or Sandbox environment. Found in Access Management > Environments.",
    )
    label: str = Field("", description="Optional friendly name for this organization/environment connection.")


class ProviderConnection(sdl.Entity):
    id: str = ""
    title: str = ""
    connected: bool = False
    detail: str = ""
    org_id: str = ""
    environment_id: str = ""


class ProviderConnectionList(sdl.Entity):
    id: str = "provider_connection_list"
    title: str = ""
    items: list[ProviderConnection] = Field(default_factory=list)


class DisconnectMulesoftParams(BaseModel):
    connection_id: str = Field(..., description="Connection id to disconnect, from list_connections.")


class DeleteResult(sdl.Entity):
    id: str = ""
    title: str = ""
    ok: bool = True


# ──────────────────────────────────────────────────────────────────────────
# CloudHub applications
# ──────────────────────────────────────────────────────────────────────────


class ListCloudhubApplicationsParams(BaseModel):
    connection_id: str = Field("", description="Which connected organization to use. Omit if only one is connected.")
    search: str | None = Field(None, description="Optional domain/name substring filter.")


class CloudhubApplication(sdl.Entity):
    id: str = ""
    title: str = ""
    domain: str = ""
    status: str = ""
    workers: int = 0
    worker_type: str = ""
    mule_version: str = ""
    latest_mule_version: str = ""
    region: str = ""
    last_update_time: str = ""


class CloudhubApplicationList(sdl.Entity):
    id: str = "cloudhub_application_list"
    title: str = ""
    items: list[CloudhubApplication] = Field(default_factory=list)


class GetCloudhubApplicationParams(BaseModel):
    connection_id: str = Field("", description="Which connected organization to use. Omit if only one is connected.")
    domain: str = Field(..., description="CloudHub application domain (its unique identifier).")


class StartStopRestartParams(BaseModel):
    connection_id: str = Field("", description="Which connected organization to use. Omit if only one is connected.")
    domain: str = Field(..., description="CloudHub application domain to act on.")


class CloudhubActionResult(sdl.Entity):
    id: str = ""
    title: str = ""
    ok: bool = True
    detail: str = ""


class DeleteCloudhubApplicationParams(BaseModel):
    connection_id: str = Field("", description="Which connected organization to use. Omit if only one is connected.")
    domain: str = Field(..., description="CloudHub application domain to permanently delete.")


class UpdateCloudhubApplicationParams(BaseModel):
    connection_id: str = Field("", description="Which connected organization to use. Omit if only one is connected.")
    domain: str = Field(..., description="CloudHub application domain to update.")
    workers: int | None = Field(None, ge=1, le=8, description="New number of workers.")
    worker_type: str | None = Field(None, description="New worker size, e.g. 'MICRO', 'SMALL', 'MEDIUM', 'LARGE'.")
    properties: dict[str, str] | None = Field(None, description="New/replaced application (system) properties as key/value pairs.")


class GetCloudhubApplicationLogsParams(BaseModel):
    connection_id: str = Field("", description="Which connected organization to use. Omit if only one is connected.")
    domain: str = Field(..., description="CloudHub application domain whose logs to read.")
    limit: int = Field(100, ge=1, le=1000, description="Max log lines to return.")


class CloudhubLogEntry(sdl.Entity):
    id: str = ""
    title: str = ""
    timestamp: str = ""
    priority: str = ""
    message: str = ""


class CloudhubLogList(sdl.Entity):
    id: str = "cloudhub_log_list"
    title: str = ""
    items: list[CloudhubLogEntry] = Field(default_factory=list)


# ──────────────────────────────────────────────────────────────────────────
# CloudHub alerts
# ──────────────────────────────────────────────────────────────────────────


class ListCloudhubAlertsParams(BaseModel):
    connection_id: str = Field("", description="Which connected organization to use. Omit if only one is connected.")
    domain: str = Field(..., description="CloudHub application domain whose alerts to list.")


class CloudhubAlert(sdl.Entity):
    id: str = ""
    title: str = ""
    domain: str = ""
    enabled: bool = True
    watch: str = ""
    condition: str = ""


class CloudhubAlertList(sdl.Entity):
    id: str = "cloudhub_alert_list"
    title: str = ""
    items: list[CloudhubAlert] = Field(default_factory=list)


class CreateCloudhubAlertParams(BaseModel):
    connection_id: str = Field("", description="Which connected organization to use. Omit if only one is connected.")
    domain: str = Field(..., description="CloudHub application domain this alert watches.")
    name: str = Field(..., description="Display name for the alert.")
    watch: str = Field(..., description="What to watch, e.g. 'APPLICATION_STATUS', 'APPLICATION_RESTART'.")
    enabled: bool = Field(True, description="Whether the alert is active immediately.")


class DeleteCloudhubAlertParams(BaseModel):
    connection_id: str = Field("", description="Which connected organization to use. Omit if only one is connected.")
    alert_id: str = Field(..., description="Alert id to permanently delete, from list_cloudhub_alerts.")


# ──────────────────────────────────────────────────────────────────────────
# CloudHub schedules
# ──────────────────────────────────────────────────────────────────────────


class ListCloudhubSchedulesParams(BaseModel):
    connection_id: str = Field("", description="Which connected organization to use. Omit if only one is connected.")
    domain: str = Field(..., description="CloudHub application domain whose schedules to list.")


class CloudhubSchedule(sdl.Entity):
    id: str = ""
    title: str = ""
    domain: str = ""
    enabled: bool = True
    flow_name: str = ""


class CloudhubScheduleList(sdl.Entity):
    id: str = "cloudhub_schedule_list"
    title: str = ""
    items: list[CloudhubSchedule] = Field(default_factory=list)


class SetCloudhubScheduleEnabledParams(BaseModel):
    connection_id: str = Field("", description="Which connected organization to use. Omit if only one is connected.")
    domain: str = Field(..., description="CloudHub application domain the schedule belongs to.")
    schedule_id: str = Field(..., description="Schedule id, from list_cloudhub_schedules.")
    enabled: bool = Field(..., description="True to enable, False to disable.")


class RunCloudhubScheduleParams(BaseModel):
    connection_id: str = Field("", description="Which connected organization to use. Omit if only one is connected.")
    domain: str = Field(..., description="CloudHub application domain the schedule belongs to.")
    schedule_id: str = Field(..., description="Schedule id to run immediately, from list_cloudhub_schedules.")


# ──────────────────────────────────────────────────────────────────────────
# API Manager instances
# ──────────────────────────────────────────────────────────────────────────


class ListApiInstancesParams(BaseModel):
    connection_id: str = Field("", description="Which connected organization to use. Omit if only one is connected.")
    search: str | None = Field(None, description="Optional API name substring filter.")


class ApiInstance(sdl.Entity):
    id: str = ""
    title: str = ""
    asset_id: str = ""
    asset_version: str = ""
    environment_id: str = ""
    tracking_status: str = ""
    endpoint_uri: str = ""


class ApiInstanceList(sdl.Entity):
    id: str = "api_instance_list"
    title: str = ""
    items: list[ApiInstance] = Field(default_factory=list)


class GetApiInstanceParams(BaseModel):
    connection_id: str = Field("", description="Which connected organization to use. Omit if only one is connected.")
    api_id: str = Field(..., description="API instance id, from list_api_instances.")


# ──────────────────────────────────────────────────────────────────────────
# Bulk operations + environment audit (Ярус 3 value-add -- not native to
# either Anypoint API)
# ──────────────────────────────────────────────────────────────────────────


class BulkAppResultItem(sdl.Entity):
    id: str = ""
    title: str = ""
    domain: str = ""
    ok: bool = True
    error: str = ""


class BulkAppResult(sdl.Entity):
    id: str = "bulk_app_result"
    title: str = ""
    items: list[BulkAppResultItem] = Field(default_factory=list)
    succeeded: int = 0
    failed: int = 0


class BulkDomainsParams(BaseModel):
    connection_id: str = Field("", description="Which connected organization to use. Omit if only one is connected.")
    domains: list[str] = Field(
        ..., min_length=1, max_length=100,
        description="Explicit CloudHub application domains; 1-100, never inferred.",
    )


class AuditCloudhubEnvironmentParams(BaseModel):
    connection_id: str = Field("", description="Which connected organization to use. Omit if only one is connected.")


class CloudhubAuditRow(sdl.Entity):
    id: str = ""
    title: str = ""
    domain: str = ""
    status: str = ""
    workers: int = 0
    mule_version: str = ""
    latest_mule_version: str = ""
    is_stale: bool = False
    last_update_time: str = ""


class CloudhubAuditReport(sdl.Entity):
    id: str = "cloudhub_audit_report"
    title: str = ""
    items: list[CloudhubAuditRow] = Field(default_factory=list)
    total: int = 0
    stale_count: int = 0
    stopped_count: int = 0


class GetStaleApplicationsParams(BaseModel):
    connection_id: str = Field("", description="Which connected organization to use. Omit if only one is connected.")
