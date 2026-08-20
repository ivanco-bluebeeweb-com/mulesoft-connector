"""Panel UI -- connections list/connect form + CloudHub applications list.

SIDEBAR CONTENT -- follows ~/UI_INTERFACE_STANDARD.md in full (as last
updated 2026-08-20, including the CTA-stretch, no-Card, no-duplicated-
instructions, and no-redundant-"not connected"-banner rules):

- No ui.Card anywhere in this slot -- every section is a plain ui.Stack,
  content stacked vertically, left-aligned, sections separated by
  ui.Divider().
- The connect form's container and every child use align="stretch" with
  no break in the chain, so the submit CTA visually fills the sidebar
  width (ui.Form has no dedicated submit-button-width parameter in the
  installed SDK -- see Task #2158 for the platform gap).
- No "Connect MuleSoft" heading/intro paragraph above the form, and no
  "Not connected yet" banner -- an empty connect form already makes the
  disconnected state obvious. The one help affordance is a small
  secondary button that opens a modal with the Connected App walkthrough,
  so that content lives in exactly one place, not duplicated in the
  sidebar too.
- Disconnect lives only in the "App settings" screen (panels_settings.py).
  The one secondary "App settings" button is always the LAST element at
  the bottom of the sidebar, secondary style.
"""
from __future__ import annotations

from imperal_sdk import ui

import mulesoft_client as mc
from app import ext
import handlers as h


def _settings_button() -> ui.UINode:
    return ui.Button(
        "App settings", variant="secondary", size="sm",
        on_click=ui.OpenPanel("mulesoft_settings"),
    )


def _help_dialog() -> ui.UINode:
    body = ui.Stack(direction="v", gap=2, align="stretch", children=[
        ui.Text("How do I get a Connected App?", variant="heading"),
        ui.Text(
            "In Anypoint Platform, go to Access Management > Connected Apps > "
            "Create app. Choose \"App as Owner\" (machine-to-machine, client "
            "credentials) and grant it the Anypoint scopes you want to use here "
            "-- e.g. \"Manage Applications\" (Runtime Manager) for CloudHub, or "
            "\"View Environment\" for read-only access. Copy the Client ID and "
            "Client Secret it generates.",
            variant="body",
        ),
        ui.Text(
            "Your organization ID and environment ID are both GUIDs, found "
            "under Access Management > organization details, and Access "
            "Management > Environments respectively.",
            variant="body",
        ),
    ])
    return ui.Dialog(
        id="mulesoft_help_dialog", title="Connect MuleSoft",
        trigger=ui.Button("How do I get a Connected App?", variant="secondary", size="sm"),
        children=[body],
    )


def _connect_form() -> ui.UINode:
    return ui.Form(
        id="mulesoft_connect_form",
        on_submit=ui.Call("connect_mulesoft", {}),
        align="stretch",
        children=[
            ui.Stack(direction="v", gap=1, align="stretch", children=[
                ui.Text("Client ID", variant="label"),
                ui.Input(name="client_id", placeholder="8f3e1c2a-...", required=True),
            ]),
            ui.Stack(direction="v", gap=1, align="stretch", children=[
                ui.Text("Client secret", variant="label"),
                ui.Password(name="client_secret", placeholder="Connected App client secret", required=True),
            ]),
            ui.Stack(direction="v", gap=1, align="stretch", children=[
                ui.Text("Organization ID", variant="label"),
                ui.Input(name="org_id", placeholder="a1b2c3d4-...", required=True),
            ]),
            ui.Stack(direction="v", gap=1, align="stretch", children=[
                ui.Text("Environment ID", variant="label"),
                ui.Input(name="environment_id", placeholder="e5f6a7b8-... (e.g. Production)", required=True),
            ]),
            ui.Stack(direction="v", gap=1, align="stretch", children=[
                ui.Text("Label (optional)", variant="label"),
                ui.Input(name="label", placeholder="e.g. Acme Corp -- Production"),
            ]),
            ui.Button("Connect", type="submit", variant="primary", full_width=True),
        ],
    )


def _connection_row(c: dict) -> ui.UINode:
    label = c.get("title") or c.get("detail", "")
    return ui.Stack(direction="v", gap=1, align="stretch", children=[
        ui.Text(label, variant="body"),
        ui.Text(c.get("detail", ""), variant="caption"),
    ])


def _connections_section(connections: list[dict]) -> ui.UINode:
    if not connections:
        return _connect_form()
    children: list[ui.UINode] = []
    for i, c in enumerate(connections):
        if i > 0:
            children.append(ui.Divider())
        children.append(_connection_row(c))
    return ui.Stack(direction="v", gap=2, align="stretch", children=children)


@ext.panel("mulesoft_sidebar", slot="sidebar")
async def mulesoft_sidebar_panel(ctx) -> ui.UINode:
    connections = await h._load_connections(ctx)
    children: list[ui.UINode] = [_connections_section(connections)]
    children.append(ui.Divider())
    children.append(_help_dialog())
    children.append(ui.Divider())
    children.append(_settings_button())
    return ui.Stack(direction="v", gap=2, align="stretch", children=children)


@ext.panel("mulesoft_center", slot="center", center_overlay=True)
async def mulesoft_center_panel(ctx) -> ui.UINode:
    """Base (non-overlay) center content -- per ~/UI_INTERFACE_STANDARD.md
    (2026-08-20 addition): when an app has no dedicated center content of
    its own (everything lives in the sidebar / settings overlay), the
    center slot must not be silently empty. NOTE: `center_overlay=True` is
    REQUIRED for the platform to actually mount this panel on page load --
    omitting it registers the panel but the session-init batch never
    surfaces it (confirmed live 2026-08-20, same bug hit and fixed on
    n8n/Make.com/Power Automate Connector).
    """
    return ui.Stack(direction="v", align="center", children=[
        ui.Text("Nothing to show here -- this app is managed entirely from the sidebar.", variant="caption"),
    ])
