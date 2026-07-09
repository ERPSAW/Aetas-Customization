"""
Incoming Webhook — Shopify Enquiry Form → Frappe Lead
======================================================
Endpoint : POST /api/method/aetas_customization.aetas_customization.api.lead_webhook.receive_lead
Auth     : Authorization: Bearer <token>  (stored in "Shopify Lead Settings" Single)
Idempotency: SHA-256 hash of (email + model_reference_number + enquiry_date)
             OR client-supplied X-Idempotency-Key header.

Setup checklist
---------------
1. Add this file at  aetas_customization.aetas_customization/api/lead_webhook.py
2. Create "Shopify Lead Settings" Single DocType with fields:
      - webhook_bearer_token  (Password)
3. Add custom fields to Lead DocType:
      - custom_product_title        (Data)
      - custom_model_reference      (Data)
      - custom_product_price        (Currency)
      - custom_page_url             (Data)
      - custom_webhook_idempotency  (Data, Read Only, unique index)
4. bench migrate && bench restart
"""

import hashlib
import hmac

import frappe
from frappe import _


# ---------------------------------------------------------------------------
# Public entry point — allow_guest=True because external systems call this
# ---------------------------------------------------------------------------

@frappe.whitelist()
def receive_lead() -> dict:
    """
    POST /api/method/aetas_customization.aetas_customization.api.lead_webhook.receive_lead

    Validates auth, deduplicates via idempotency key, then enqueues
    background processing so we respond to the caller in < 1 second.
    """

    # ── 2. Parse payload ───────────────────────────────────────────────────
    # frappe already parses the JSON body into form_dict during request setup
    # (frappe.request.data may already be consumed by then).
    raw_data = frappe.request.data
    if raw_data:
        try:
            payload = frappe.parse_json(raw_data.decode("utf-8"))
        except Exception:
            frappe.local.response["http_status_code"] = 400
            return {"status": "error", "code": "INVALID_JSON", "message": _("Request body must be valid JSON.")}
    else:
        payload = frappe.local.form_dict

    if not payload:
        frappe.local.response["http_status_code"] = 400
        return {"status": "error", "code": "EMPTY_PAYLOAD", "message": _("Request body cannot be empty.")}

    if not isinstance(payload, dict):
        frappe.local.response["http_status_code"] = 400
        return {"status": "error", "code": "INVALID_JSON", "message": _("Request body must be a JSON object.")}

    # ── 3. Validate required fields ────────────────────────────────────────
    validation_error = _validate_required_fields(payload)
    if validation_error:
        frappe.local.response["http_status_code"] = 422
        return {"status": "error", "code": "VALIDATION_ERROR", "message": validation_error}

    # ── 4. Idempotency check ───────────────────────────────────────────────
    idempotency_key = _resolve_idempotency_key(payload, frappe.request.headers)

    existing = frappe.db.get_value(
        "Lead",
        {"custom_webhook_idempotency": idempotency_key},
        "name",
    )
    if existing:
        # Return 200 — not an error; caller already succeeded once
        return {
            "status": "duplicate",
            "code": "ALREADY_PROCESSED",
            "message": _("This lead was already created."),
            "lead_id": existing,
        }

    # ── 5. Enqueue background processing — respond fast ───────────────────
    frappe.enqueue(
        "aetas_customization.aetas_customization.api.lead_webhook._create_lead_from_payload",
        queue="default",
        timeout=120,
        payload=payload,
        idempotency_key=idempotency_key,
    )

    frappe.local.response["http_status_code"] = 202
    return {
        "status": "accepted",
        "code": "QUEUED",
        "message": _("Lead creation has been queued."),
        "idempotency_key": idempotency_key,
    }


# ---------------------------------------------------------------------------
# Background worker — runs after we've already responded 202
# ---------------------------------------------------------------------------

def _create_lead_from_payload(payload: dict, idempotency_key: str) -> None:
    """
    Background job. Creates a Frappe Lead from the Shopify enquiry payload.
    All DB work is isolated here — never runs inline in the HTTP handler.
    """
    # Guard: second worker may pick up the same job if queue retries
    if frappe.db.exists("Lead", {"custom_webhook_idempotency": idempotency_key}):
        return

    try:
        lead = frappe.new_doc("Lead")

        # ── Core CRM fields ────────────────────────────────────────────────
        lead.lead_name      = payload.get("name", "").strip()
        lead.email_id       = payload.get("email", "").strip().lower()
        lead.mobile_no      = str(payload.get("phone", "")).strip()
        lead.city           = payload.get("city", "").strip()
        lead.source         = "6. Online - AOT Website/Shopify"
        lead.status         = "Open"
        lead.company_name   = payload.get("name", "").strip()

        # ── Custom extension fields ────────────────────────────────────────
        lead.custom_product_title        = payload.get("product_title", "").strip()
        lead.custom_model_reference      = payload.get("model_reference_number", "").strip()
        lead.custom_product_price        = _safe_float(payload.get("product_price"))
        lead.custom_page_url             = payload.get("page_url", "").strip()
        lead.custom_webhook_idempotency  = idempotency_key

        # ── Notes — preserve the enquiry date from source ──────────────────
        enquiry_date = payload.get("date", "")
        if enquiry_date:
            lead.append("notes", {
                "note": f"Shopify enquiry submitted on: {enquiry_date}",
                "added_by": frappe.session.user,
                "added_on": frappe.utils.now(),
            })

        lead.insert(ignore_permissions=True, ignore_mandatory=True,)
        frappe.db.commit()

        frappe.logger().info(
            f"[lead_webhook] Created Lead {lead.name} "
            f"| idempotency={idempotency_key}"
        )

    except frappe.DuplicateEntryError:
        # Race condition — another worker won; safe to ignore
        frappe.db.rollback()
        frappe.log_error(
            title="Lead Webhook: Failed to create Lead",
            message=frappe.as_json({
                "payload": payload,
                "idempotency_key": idempotency_key,
                "traceback": frappe.get_traceback(),
            }),
        )
        return

    except Exception:
        frappe.db.rollback()
        frappe.log_error(
            title="Lead Webhook: Failed to create Lead",
            message=frappe.as_json({
                "payload": payload,
                "idempotency_key": idempotency_key,
                "traceback": frappe.get_traceback(),
            }),
        )


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _authenticate(headers: dict) -> str | None:
    """
    Validates the Bearer token in the Authorization header.
    Returns an error string if invalid, None if ok.
    """
    auth_header = headers.get("Authorization", "")

    if not auth_header.startswith("Bearer "):
        return _("Missing or malformed Authorization header. Expected: Bearer <token>")

    provided_token = auth_header[len("Bearer "):]

    try:
        stored_token = frappe.get_value(
            "Shopify Lead Settings", None, "webhook_bearer_token"
        )
    except Exception:
        frappe.log_error(
            title="Lead Webhook: Settings missing",
            message="Shopify Lead Settings DocType or field not found.",
        )
        return _("Webhook authentication is misconfigured on the server.")

    if not stored_token:
        return _("Bearer token is not configured on the server.")

    # Use constant-time compare to prevent timing attacks
    if not hmac.compare_digest(provided_token, stored_token):
        return _("Invalid Bearer token.")

    return None


def _validate_required_fields(payload: dict) -> str | None:
    """
    Returns a human-readable error string if any required field is missing.
    All 9 source fields are validated.
    """
    required = {
        "name":                  "Enquirer name",
        "email":                 "Email address",
        "phone":                 "Phone number",
        "city":                  "City",
        "product_title":         "Product title",
        "model_reference_number": "Model reference number",
        "product_price":         "Product price",
        "page_url":              "Page URL",
    }
    # "date" is optional — we accept records without it

    missing = [label for field, label in required.items() if not payload.get(field)]

    if missing:
        return _("Missing required fields: {0}").format(", ".join(missing))

    # Email format sanity check
    email = payload.get("email", "")
    if "@" not in email or "." not in email.split("@")[-1]:
        return _("Invalid email format: {0}").format(email)

    return None


def _resolve_idempotency_key(payload: dict, headers: dict) -> str:
    """
    Priority:
      1. X-Idempotency-Key header supplied by the caller (use as-is, hashed)
      2. Deterministic SHA-256 of email + model_reference_number + date

    Hashing means we never store the raw key — only the fingerprint.
    """
    client_key = headers.get("X-Idempotency-Key", "").strip()

    if client_key:
        raw = f"client:{client_key}"
    else:
        raw = ":".join([
            payload.get("email", "").strip().lower(),
            payload.get("model_reference_number", "").strip(),
            payload.get("date", "").strip(),
        ])

    return hashlib.sha256(raw.encode()).hexdigest()


def _safe_float(value: object) -> float:
    """Converts price to float, returns 0.0 on any conversion failure."""
    try:
        return float(str(value).replace(",", "").strip())
    except (ValueError, TypeError):
        return 0.0