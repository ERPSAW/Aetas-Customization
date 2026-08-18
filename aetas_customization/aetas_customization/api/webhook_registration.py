# Copyright (c) 2026, Akhilam Inc and Contributors
# See license.txt
"""
Automatic Razorpay webhook registration / deregistration.

Wired to the `Razorpay Settings` doctype via a doc_events `on_update` hook
(see hooks.py). When a boutique's settings are enabled we register a webhook
with Razorpay (v1 Webhooks API) pointing at the inbound handler
`aetas_customization.aetas_customization.api.webhook.handle_razorpay_webhook`,
and store the resulting webhook id + a generated secret on the document.
When disabled we deregister it.

Design notes:
- The razorpay SDK's `webhook.create/all/edit/fetch` hit the v1 API with
  standard merchant keys, but `webhook.delete` requires an `account_id`
  (v2 partner API). So deregistration attempts a direct v1 DELETE and, if
  that is rejected, falls back to editing the webhook to inactive.
- Razorpay API failures never block the save: they are logged, surfaced as a
  msgprint warning, and recorded in `webhook_status` / `webhook_last_error`.
"""

import frappe
from frappe import _
from frappe.utils import get_url, now_datetime

from aetas_customization.aetas_customization.api.razorpay_activity_log import (
    create_activity_log,
)

# Events the inbound handler dispatches on (see webhook.py). Razorpay v1
# expects `events` as an object of {event_name: 1}.
WEBHOOK_EVENTS = [
    "payment_link.paid",
    "payment_link.cancelled",
    "payment.failed",
]

WEBHOOK_METHOD_PATH = (
    "/api/method/aetas_customization.aetas_customization.api.webhook."
    "handle_razorpay_webhook"
)


def get_webhook_url():
    """
    Public callback URL for this site's inbound Razorpay handler.

    Prefer `site_url` from site config: behind the Arbok tunnel `get_url()`
    resolves to the internal host IP (e.g. 10.100.0.4), which Razorpay rejects
    as a private IP. `site_url` holds the real public domain.
    """
    base = frappe.conf.get("site_url") or get_url()
    return base.rstrip("/") + WEBHOOK_METHOD_PATH


def _events_dict():
    return {event: 1 for event in WEBHOOK_EVENTS}


def _alert_email():
    """Best-effort contact email for the Razorpay webhook alert."""
    user = frappe.session.user
    if user and user not in ("Guest", "Administrator") and "@" in user:
        return user
    return frappe.db.get_value("User", user, "email") or None


# ── doc_events entry point ─────────────────────────────────────────────────────

def on_update(doc, method=None):
    """
    React to enable/disable (and credential change) transitions on
    `Razorpay Settings`. Registration state is persisted via db_set, so this
    does not recurse.
    """
    before = doc.get_doc_before_save()
    was_enabled = bool(before.enabled) if before else False
    is_enabled = bool(doc.enabled)

    creds_changed = bool(
        before
        and (before.api_key != doc.api_key or before.api_secret != doc.api_secret)
    )

    if is_enabled and not was_enabled:
        # Freshly enabled (or newly created enabled).
        register_webhook(doc)
    elif not is_enabled and was_enabled:
        # Freshly disabled.
        deregister_webhook(doc)
    elif is_enabled and creds_changed and doc.webhook_id:
        # Still enabled but pointed at a different Razorpay account: move the
        # webhook to the new account.
        deregister_webhook(doc)
        register_webhook(doc)
    elif is_enabled and not doc.webhook_id:
        # Enabled but never successfully registered (e.g. a prior failure or a
        # manually cleared id) — try again.
        register_webhook(doc)


# ── Registration ───────────────────────────────────────────────────────────────

def register_webhook(doc):
    """Create (or adopt) a Razorpay webhook and persist its details on doc."""
    try:
        doc.init_client()
        if not getattr(doc, "client", None):
            _record_error(
                doc,
                "webhook.register",
                _("API Key is required before a webhook can be registered."),
            )
            return

        url = get_webhook_url()
        secret = frappe.generate_hash(length=32)
        events = _events_dict()

        existing = _find_existing_webhook(doc, url)
        if existing:
            # Refresh the existing webhook (events + secret) rather than
            # creating a duplicate for the same URL.
            resp = doc.client.webhook.edit(
                existing.get("id"),
                None,
                {"url": url, "secret": secret, "events": events},
            )
        else:
            payload = {"url": url, "secret": secret, "events": events}
            alert = _alert_email()
            if alert:
                payload["alert_email"] = alert
            resp = doc.client.webhook.create(payload)

        webhook_id = (resp or {}).get("id") or (existing or {}).get("id")

        doc.db_set("webhook_id", webhook_id, update_modified=False)
        doc.db_set("webhook_url", url, update_modified=False)
        doc.db_set("webhook_secret", secret, update_modified=False)
        doc.db_set("webhook_status", "Active", update_modified=False)
        doc.db_set("webhook_registered_on", now_datetime(), update_modified=False)
        doc.db_set("webhook_last_error", None, update_modified=False)

        create_activity_log(
            direction="Outbound",
            activity_type="webhook.register",
            processing_status="Processed",
            reference_doctype="Razorpay Settings",
            reference_docname=doc.name,
            response_payload=resp,
        )
        frappe.msgprint(
            _("Razorpay webhook registered ({0}).").format(webhook_id),
            indicator="green",
            alert=True,
        )
    except Exception as e:
        _record_error(doc, "webhook.register", e)


def _find_existing_webhook(doc, url):
    """Return a webhook item already registered for `url`, if any."""
    try:
        listing = doc.client.webhook.all() or {}
    except Exception:
        return None
    for item in listing.get("items", []) or []:
        if item.get("url") == url:
            return item
    return None


# ── Deregistration ──────────────────────────────────────────────────────────────

def deregister_webhook(doc):
    """
    Remove the webhook from Razorpay. Tries a hard v1 DELETE first; if that is
    unavailable for the account, deactivates the webhook via edit instead.
    Local webhook fields are always cleared / updated.
    """
    webhook_id = doc.webhook_id
    if not webhook_id:
        doc.db_set("webhook_status", "Not Registered", update_modified=False)
        return

    try:
        doc.init_client()
        if not getattr(doc, "client", None):
            # No credentials to talk to Razorpay — clear locally so we don't
            # keep a dangling reference.
            _clear_local_webhook(doc, status="Not Registered")
            return

        deleted = _try_hard_delete(doc, webhook_id)
        if deleted:
            _clear_local_webhook(doc, status="Not Registered")
            final_status = "Not Registered"
            action = "deleted"
        else:
            # Fallback: deactivate the webhook but keep the id on record.
            doc.client.webhook.edit(
                webhook_id,
                None,
                {"url": doc.webhook_url or get_webhook_url(),
                 "events": _events_dict(),
                 "active": False},
            )
            doc.db_set("webhook_status", "Inactive", update_modified=False)
            doc.db_set("webhook_last_error", None, update_modified=False)
            final_status = "Inactive"
            action = "deactivated"

        create_activity_log(
            direction="Outbound",
            activity_type="webhook.deregister",
            processing_status="Processed",
            reference_doctype="Razorpay Settings",
            reference_docname=doc.name,
            response_payload={"webhook_id": webhook_id,
                              "action": action,
                              "status": final_status},
        )
        frappe.msgprint(
            _("Razorpay webhook {0} ({1}).").format(action, webhook_id),
            indicator="orange",
            alert=True,
        )
    except Exception as e:
        _record_error(doc, "webhook.deregister", e)


def _try_hard_delete(doc, webhook_id):
    """Attempt a direct v1 DELETE /v1/webhooks/{id}. Returns True on success."""
    try:
        doc.client.webhook.delete_url("/v1/webhooks/{0}".format(webhook_id), {})
        return True
    except Exception:
        # Endpoint may not be enabled for standard keys — signal fallback.
        return False


def _clear_local_webhook(doc, status="Not Registered"):
    doc.db_set("webhook_id", None, update_modified=False)
    doc.db_set("webhook_status", status, update_modified=False)
    doc.db_set("webhook_registered_on", None, update_modified=False)
    doc.db_set("webhook_last_error", None, update_modified=False)


# ── Shared error handling ────────────────────────────────────────────────────────

def _record_error(doc, activity_type, err):
    """Log, flag status, and warn — never block the save."""
    message = str(err)
    frappe.log_error(frappe.get_traceback(), "Razorpay Webhook {0}".format(activity_type))
    try:
        create_activity_log(
            direction="Outbound",
            activity_type=activity_type,
            processing_status="Failed",
            reference_doctype="Razorpay Settings",
            reference_docname=doc.name,
            error_message=message,
        )
    except Exception:
        pass
    doc.db_set("webhook_status", "Error", update_modified=False)
    doc.db_set("webhook_last_error", message, update_modified=False)
    frappe.msgprint(
        _("Razorpay webhook operation failed: {0}").format(message),
        indicator="red",
        alert=True,
    )
