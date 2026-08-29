"""Panel UI -- connections list/connect form + CloudHub applications list.

SIDEBAR CONTENT -- NO CARDS ANYWHERE, per ~/UI_INTERFACE_STANDARD.md's
"left sidebar, no decorated cards" rule (same convention as Power Automate
Connector's / n8n Connector's panels.py).

Every section (connections, connect form, applications) is a plain
ui.Stack, content stacked vertically and left-aligned, sections separated
by ui.Divider() -- no Card border/background/shadow anywhere in this slot.
Disconnect lives only in the "App settings" screen (panels_settings.py).
The one secondary "App settings" button is always the LAST element at the
bottom of the sidebar.

WHY A FULL FORM, NOT A TOKEN LIKE n8n/Make.com/Slack.

Anypoint Platform's Connected App auth needs client_id + client_secret +
org_id + a default environment_id -- see app.py's module docstring for the
full reasoning (Connected Apps overview, multi-environment orgs). The form
therefore asks for all four required fields plus an optional label, with a
help dialog explaining where to find each one -- the same shape as Power
Automate Connector's 5-field form.
"""
from __future__ import annotations

from imperal_sdk import ui

import mulesoft_client as mc
from app import ext
import handlers as h


def _settings_button() -> ui.UINode:
    """The one required secondary entry point into the settings screen --
    always the last element at the bottom of the sidebar."""
    return ui.Button(
        "App settings", variant="secondary", size="sm", full_width=True,
        icon="settings", on_click=ui.Call("__panel__mulesoft_settings"),
    )


def _connection_row(c: dict) -> ui.UINode:
    label = c.get("label") or c.get("org_id", "")
    return ui.Stack(direction="v", gap=1, children=[
        ui.Text(label, variant="body"),
        ui.Text(f"org {c.get('org_id', '')} · env {c.get('environment_id', '')}", variant="caption"),
    ])


def _connections_section(connections: list[dict]) -> ui.UINode:
    if not connections:
        return ui.Text("No organizations connected yet.", variant="caption")
    children: list[ui.UINode] = []
    for i, c in enumerate(connections):
        if i > 0:
            children.append(ui.Divider())
        children.append(_connection_row(c))
    return ui.Stack(direction="v", gap=2, children=children)


def _app_row(a) -> ui.UINode:
    """One CloudHub application row -- plain content, no Card wrapper, no
    padding/border, per Vlad's standing sidebar rule."""
    subtitle = a.status.capitalize() + (f" · {a.workers} worker(s)" if a.workers else "")
    return ui.Stack(direction="v", gap=1, children=[
        ui.Text(a.domain, variant="body"),
        ui.Text(subtitle, variant="caption"),
    ])


def _applications_section(apps: list) -> ui.UINode:
    if not apps:
        return ui.Text("No CloudHub applications yet.", variant="caption")
    children: list[ui.UINode] = []
    for i, a in enumerate(apps):
        if i > 0:
            children.append(ui.Divider())
        children.append(_app_row(a))
    return ui.Stack(direction="v", gap=2, children=children)


def _connect_section() -> ui.UINode:
    """Plain content, no Card wrapper. Stretched full-width per
    UI_INTERFACE_STANDARD.md (2026-08-20). No intro heading/description
    text here -- the Connected App walkthrough lives ONLY in
    mulesoft_connect_help's modal (button below opens it); repeating it
    here would duplicate that instruction."""
    return ui.Stack(direction="v", gap=3, align="stretch", children=[
        ui.Button("How do I set this up?", variant="ghost", size="sm",
                  icon="HelpCircle",
                  on_click=ui.Call("__panel__mulesoft_connect_help")),
        ui.Form(
            action="connect_mulesoft",
            submit_label="Verify and connect",
            children=[
                ui.Stack(direction="v", gap=1, children=[
                    ui.Text("Connected App client ID", variant="caption"),
                    ui.Input(param_name="client_id", placeholder="Connected App client ID"),
                ]),
                ui.Stack(direction="v", gap=1, children=[
                    ui.Text("Connected App client secret", variant="caption"),
                    ui.Password(param_name="client_secret",
                                 placeholder="Connected App client secret"),
                ]),
                ui.Stack(direction="v", gap=1, children=[
                    ui.Text("Organization ID", variant="caption"),
                    ui.Input(param_name="org_id", placeholder="Anypoint organization ID (GUID)"),
                ]),
                ui.Stack(direction="v", gap=1, children=[
                    ui.Text("Environment ID", variant="caption"),
                    ui.Input(param_name="environment_id", placeholder="Environment ID (GUID)"),
                ]),
                ui.Stack(direction="v", gap=1, children=[
                    ui.Text("Label (optional)", variant="caption"),
                    ui.Input(param_name="label", placeholder="e.g. Production"),
                ]),
            ],
        ),
    ])


@ext.panel("mulesoft_connect", slot="left", title="MuleSoft", icon="🔗",
           default_width=320, min_width=260, max_width=420)
async def mulesoft_connect_panel(ctx, **kwargs) -> object:
    connections = await h._load_connections(ctx)
    connected = bool(connections)

    header = ui.Header(text="MuleSoft", level=2,
                        subtitle="Manage your Anypoint Platform CloudHub applications from Imperal")

    if not connected:
        return ui.Stack(direction="v", gap=4, align="stretch", children=[
            header,
            _connect_section(),
            ui.Divider(),
            _settings_button(),
        ])

    apps: list = []
    first = connections[0]
    try:
        tok = await mc.get_access_token(ctx, first["client_id"], first["client_secret"])
        if tok.get("ok"):
            raw = await mc.list_applications(ctx, tok["access_token"], first["org_id"], first["environment_id"])
            apps = [h._app_to_entity(a) for a in raw]
    except mc.ClientFail:
        apps = []

    return ui.Stack(direction="v", gap=4, align="stretch", children=[
        header,
        ui.Text("Connected organizations", variant="subtitle"),
        _connections_section(connections),
        ui.Divider(),
        _connect_section(),
        ui.Divider(),
        ui.Text(f"CloudHub applications -- {first.get('label') or first.get('org_id', '')}", variant="subtitle"),
        _applications_section(apps),
        ui.Divider(),
        ui.Button("View environment dashboard", variant="primary", size="sm", full_width=True,
                  icon="LayoutDashboard", on_click=ui.Call("__panel__mulesoft_center")),
        ui.Divider(),
        _settings_button(),
    ])


@ext.panel("mulesoft_connect_help", slot="center",
           title="How to connect MuleSoft", center_overlay=True)
async def mulesoft_connect_help(ctx, **kwargs) -> object:
    content = ui.Stack(direction="v", gap=3, children=[
        ui.Text("1. In Anypoint Platform, open Access Management > Connected Apps > Create app."),
        ui.Text("2. Choose \"App as Owner\" (machine-to-machine, no user login involved)."),
        ui.Text("3. Grant the scopes/permissions you want to use (e.g. \"Manage Applications\" for CloudHub, \"View Environment\" for API Manager)."),
        ui.Text("4. Copy the Client ID and Client Secret from the Connected App's details page."),
        ui.Text("5. Copy your organization ID from Access Management > organization details, and your environment ID from Access Management > Environments."),
        ui.Divider(),
        ui.Alert(
            title="CloudHub and API Manager only",
            message=(
                "This manages CloudHub Mule applications and API Manager "
                "instances. Design Center API specs and Access Management "
                "users/roles are out of scope here."
            ),
            type="warning",
        ),
        ui.Divider(),
        ui.Link(
            label="Open MuleSoft's official Connected Apps guide",
            href="https://docs.mulesoft.com/access-management/connected-apps-overview",
        ),
    ])
    return ui.Dialog(
        title="How to connect MuleSoft",
        content=content,
        confirm_label="",
        cancel_label="Close",
    )


def _audit_row(a) -> dict:
    return {
        "domain": a.domain, "status": a.status,
        "workers": str(a.workers),
        "mule_version": a.mule_version or "—",
        "stale": "Yes" if a.is_stale else "No",
        "domain_id": a.domain,
    }


@ext.panel("mulesoft_center", slot="center", title="MuleSoft", icon="🔗", center_overlay=True)
async def mulesoft_center_panel(ctx, domain_id: str = "", **kwargs) -> object:
    """Post-connect main screen: CloudHub environment health dashboard, or
    an application detail when `domain_id` is passed (master-detail via
    the same panel_id, per UI_COMPONENT_VOCABULARY.md §3)."""
    connections = await h._load_connections(ctx)
    if not connections:
        return ui.Empty(
            message="Connect an Anypoint Platform organization from the sidebar to see it here.",
            icon="🔗",
        )
    if domain_id:
        return await _application_detail(ctx, domain_id)
    return await _environment_dashboard(ctx)


async def _environment_dashboard(ctx) -> ui.UINode:
    from schemas import AuditCloudhubEnvironmentParams
    audit_result = await h.audit_cloudhub_environment(ctx, AuditCloudhubEnvironmentParams())
    stats: list[ui.UINode] = []
    rows: list[dict] = []
    if audit_result.success and audit_result.data:
        r = audit_result.data
        stats = [
            ui.Stat(label="Total applications", value=str(r.total)),
            ui.Stat(label="Stale (outdated Mule)", value=str(r.stale_count)),
            ui.Stat(label="Stopped", value=str(r.stopped_count)),
        ]
        rows = [_audit_row(item) for item in r.items]

    body: list[ui.UINode] = []
    if stats:
        body.append(ui.Stats(stats=stats))
    body.append(ui.Divider())
    body.append(ui.Text("CloudHub applications", variant="subtitle"))
    if rows:
        columns = [
            ui.DataColumn("domain", "Domain", sortable=True),
            ui.DataColumn("status", "Status", sortable=True),
            ui.DataColumn("workers", "Workers", sortable=False),
            ui.DataColumn("mule_version", "Mule version", sortable=False),
            ui.DataColumn("stale", "Stale?", sortable=True),
        ]
        body.append(ui.DataTable(
            columns=columns, rows=rows,
            on_row_click=ui.Call("__panel__mulesoft_center", domain_id=""),
        ))
    else:
        body.append(ui.Empty(message="No CloudHub applications on this environment yet.", icon="🔗"))
    return ui.Stack(direction="v", gap=3, align="stretch", children=body)


async def _application_detail(ctx, domain_id: str) -> ui.UINode:
    from schemas import GetCloudhubApplicationParams
    result = await h.get_cloudhub_application(ctx, GetCloudhubApplicationParams(domain=domain_id))
    if not result.success or not result.data:
        return ui.Alert(title="Application not found", message=result.error or "Could not load this application.", type="error")
    a = result.data
    return ui.Stack(direction="v", gap=3, align="stretch", children=[
        ui.Button("← Back to environment", variant="ghost", size="sm",
                  on_click=ui.Call("__panel__mulesoft_center")),
        ui.KeyValue(columns=2, items=[
            {"key": "Domain", "value": a.domain},
            {"key": "Status", "value": a.status},
            {"key": "Workers", "value": str(a.workers)},
            {"key": "Worker type", "value": a.worker_type or "—"},
            {"key": "Mule version", "value": a.mule_version or "—"},
            {"key": "Latest Mule version", "value": a.latest_mule_version or "—"},
            {"key": "Region", "value": a.region or "—"},
            {"key": "Last update", "value": a.last_update_time or "—"},
        ]),
        ui.Divider(),
        ui.Stack(direction="h", gap=2, children=[
            ui.Button("Restart", variant="secondary", size="sm",
                      on_click=ui.Call("restart_cloudhub_application", {"domain": a.domain})),
            ui.Button("Stop", variant="destructive", size="sm",
                      on_click=ui.Call("stop_cloudhub_application", {"domain": a.domain})),
        ]),
    ])
