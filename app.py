"""Extension declaration, secrets, lifecycle hooks.

WHY BYOK (bring-your-own-key), same reasoning as Power Automate Connector /
Make.com Connector / n8n Connector. Anypoint Platform lives inside the
USER'S OWN Salesforce/MuleSoft organization -- Imperal cannot and should
not broker access to someone else's Anypoint org centrally.

WHY CONNECTED APP (client_id + client_secret) + ORG_ID/ENV_ID, NOT A
GENERIC PLATFORM OAUTH ENTRY.

Anypoint Platform's own Connected Apps feature supports OAuth 2.0 client
credentials grant for exactly this kind of server-to-server integration
(docs.mulesoft.com/access-management/connected-apps-overview, confirmed
during Discovery 2026-08-20, CONNECTOR_DISCOVERY.md). Unlike Zapier
(which requires external marketplace review before any real API access
exists at all), a MuleSoft Connected App can be created immediately by
any org admin -- no chicken-and-egg. The connector therefore asks for the
Connected App's own client_id/client_secret plus the organization's
org_id and a default environment_id (Dev/Test/Prod -- Anypoint orgs are
explicitly multi-environment, same shape as Power Automate's
Dev/Test/UAT/Prod business groups).

WHY `write_mode="both"`, SAME REASONING AS n8n/Make.com/Power Automate
CONNECTOR.

Declaring `write_mode="user"` would mean only the platform's generic
Secrets screen could write these -- leaving a first-time user with no
in-app screen explaining what a Connected App even is or how to create
one. `"both"` keeps the generic Secrets screen as a fallback while
letting `connect_mulesoft` be the friendly guided path.

WHY SCOPE IS PER-ACCOUNT, NOT APP-LEVEL, SAME AS n8n/Make.com/Power
Automate CONNECTOR.

Each user connects their OWN Anypoint organization -- these are not
developer-owned app credentials, so the connections secret is declared
per-account (default scope), not `scope="app"`.

WHY ONE SECRET HOLDING A JSON ARRAY, NOT FLAT SECRETS FOR "the"
ORGANIZATION (multi-environment support).

Anypoint orgs are explicitly multi-environment by design (Dev/Test/Sandbox/
Production is the normal setup, not an edge case) -- same structural
problem Power Automate Connector already solved for Dataverse
environments and Slack Connector solved for multiple workspaces.
`ctx.secrets` only supports a fixed, manifest-declared set of NAMES --
there is no "one secret per connection_id" primitive. This connector
follows the same precedent: `mulesoft_connections` holds a JSON array of
`{id, label, client_id, client_secret, org_id, environment_id}` objects.
`schemas.py`'s `connection_id` parameter on every tool call addresses one
specific entry in that array -- see handlers.py's
`_load_connections`/`_save_connections` helpers.
"""
from __future__ import annotations

from imperal_sdk import ChatExtension, Extension

ext = Extension(
    "mulesoft-connector",
    version="0.1.0",
    display_name="MuleSoft",
    description=(
        "Connect your own MuleSoft Anypoint Platform organization to see "
        "and manage your CloudHub Mule applications from Imperal -- list "
        "applications with their status, start/stop/restart/delete them, "
        "update their worker/runtime configuration, read their logs, "
        "manage alerts and schedules, browse your API Manager registry, "
        "and run bulk operations and environment audits across many "
        "applications at once. Uses your own Anypoint Connected App "
        "(OAuth2 client credentials) -- nothing is hosted or proxied by "
        "Imperal beyond the request itself. Note: this manages CloudHub "
        "applications and API Manager instances only; Design Center API "
        "specification projects and deep network infrastructure (VPC/VPN/ "
        "load balancers) are out of scope."
    ),
    icon="icon.svg",
    capabilities=[
        "mulesoft:read",
        "mulesoft:write",
    ],
    actions_explicit=True,
    system=False,
)

chat = ChatExtension(
    ext,
    tool_name="mulesoft",
    description=(
        "MuleSoft Connector -- connect your Anypoint Platform organization "
        "via your own Connected App, then list/get/start/stop/restart/"
        "delete CloudHub applications, read their logs, manage alerts and "
        "schedules, browse API Manager instances, and run bulk operations "
        "and environment audits across many applications at once."
    ),
)

ext.secret(
    "mulesoft_connections",
    (
        "Your connected Anypoint Platform organizations -- stored as a "
        "JSON array, one entry per organization/environment pair, each "
        "with its own Connected App (client_id, client_secret) and "
        "org_id/environment_id. Managed through connect_mulesoft / "
        "disconnect_mulesoft -- you should not need to edit this directly."
    ),
    required=True,
    write_mode="both",
    max_bytes=65536,
    rotation_hint_days=180,
)(lambda: None)


@ext.health_check
async def health_check(ctx) -> dict:
    """Fast configuration health; no third-party call -- just confirms at
    least one organization connection is stored, same shape as Power
    Automate Connector's health_check."""
    import json as _json
    raw = await ctx.secrets.get("mulesoft_connections")
    try:
        count = len(_json.loads(raw)) if raw else 0
    except Exception:
        count = 0
    return {
        "healthy": True,
        "detail": (
            f"{count} Anypoint Platform organization(s) connected." if count
            else "Not connected yet -- run connect_mulesoft."
        ),
    }
