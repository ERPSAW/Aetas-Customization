import base64
import io
import mimetypes
import os
import re
import urllib.parse
import frappe
from frappe.model.naming import getseries
from frappe.utils import add_days, cint, flt, formatdate, getdate
from frappe.utils.pdf import get_pdf

WATCH_ITEM_GROUP = "Watch"
CERTIFICATE_PRINT_FORMAT = "Watch Insurance Certificate"
CUSTOM_SETTINGS_DOCTYPE = "Aetas Custom Setting"

# ASSET_RELATIVE_DIR = ("aetas_customization", "public", "images")
# ASSET_FILES = {
#     "logo_src": "logo.png",
#     "signature_src": "signature.png",
#     "banner_src": "footer_banner.jpeg",
# }

# context key used in the print template -> Attach field in Aetas Custom Setting
ASSET_SETTING_FIELDS = {
    "logo_src": "insurance_certificate_logo",
    "signature_src": "insurance_certificate_signature",
    "banner_src": "insurance_certificate_footer_banner",
    "invoice_logo_src": "insurance_invoice_logo",
}

# 1x1 transparent PNG, used as a stand-in when a locally-hosted image
# (Letter Head, Company logo, etc) is referenced but not actually
# present on this site/instance.
_BLANK_IMAGE_DATA_URI = (
    "data:image/png;base64,"
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)

def generate_insurance_certificates(si, attach_to=None, user=None):
    attach_to = attach_to or si

    watch_rows = [row for row in si.items if (row.item_group or "") == WATCH_ITEM_GROUP]
    if not watch_rows:
        return

    naming_series = get_insurance_naming_series(si)  # resolve once per invoice

    contact_mobile, contact_email = _get_contact_details(si)
    insurance_start = getdate(si.posting_date)
    insurance_end = add_days(insurance_start, 365)

    settings = frappe.get_cached_doc(CUSTOM_SETTINGS_DOCTYPE)
    premium_percentage = flt(settings.premium_percentage)

    item_brand_cache = {}
    contexts = []

    for row in watch_rows:
        qty = cint(row.qty) or 1
        per_unit_amount = flt(row.base_amount) / qty if qty else flt(row.rate)
        premium_amount = per_unit_amount * premium_percentage / 100

        if row.item_code not in item_brand_cache:
            item_brand_cache[row.item_code] = frappe.db.get_value("Item", row.item_code, "brand") or ""
        brand = item_brand_cache[row.item_code]

        item_name = row.item_name or row.item_code


        for _unit in range(qty):
            # Create the record FIRST so Frappe's naming_series autoname
            # engine generates the certificate number for us.
            sii_doc = frappe.new_doc("Sales Invoice Insurance")
            sii_doc.naming_series = naming_series
            sii_doc.sales_invoice = si.name
            sii_doc.invoice_date = si.posting_date
            sii_doc.invoice_amount = per_unit_amount          # store as raw number (Currency field), not the formatted string
            sii_doc.premium_amount = premium_amount
            sii_doc.item_name = item_name
            sii_doc.brand = brand
            sii_doc.mobile_no = contact_mobile
            sii_doc.email_id = contact_email
            sii_doc.insurance_start_date = insurance_start
            sii_doc.insurance_end_date = insurance_end
            sii_doc.insert(ignore_permissions=True)

            contexts.append({
                "certificate_no": sii_doc.name,   # <-- the auto-generated number, e.g. CIRAHM-2627-00001
                "invoice_no": si.name,
                "invoice_date": formatdate(si.posting_date),
                "invoice_amount": per_unit_amount,
                # "item_name": item_name,
                "brand": brand,
                "mobile_no": contact_mobile,
                "email_id": contact_email,
                "insurance_start_date": formatdate(insurance_start),
                "insurance_end_date": formatdate(insurance_end),
                "_sii_doc": sii_doc,   # keep reference to attach the PDF to it below
            })

    print_format = _get_print_format_source()
    invoice_pdf_bytes = _render_sales_invoice_pdf(si)
    asset_data_uris = _get_asset_data_uris()

    for context in contexts:
        cert_pdf_bytes = _render_certificate_to_pdf(print_format, context, asset_data_uris)
        combined_pdf_bytes = _merge_pdfs([invoice_pdf_bytes, cert_pdf_bytes])

        sii_doc = context.pop("_sii_doc")
        file_doc = _attach_pdf_to_doc(sii_doc, combined_pdf_bytes, context["certificate_no"], si.name)

        # link the attached PDF back onto the Sales Invoice Insurance record's Attach field
        frappe.db.set_value("Sales Invoice Insurance", sii_doc.name, "insurance_certificate", file_doc.file_url)

        # also attach to the original target (Sales Invoice or Missed Insurance) if you still want that
        if attach_to.doctype != "Sales Invoice Insurance":
            _attach_pdf_to_doc(attach_to, combined_pdf_bytes, context["certificate_no"], si.name)

        send_certificate_email(sii_doc, file_doc, si)

    # frappe.msgprint(
    #     frappe._("{0} Insurance Certificate(s) generated and attached.").format(len(contexts)),
    #     indicator="green",
    # )
    frappe.publish_realtime(
    event="msgprint",
    message=frappe._("{0} Insurance Certificate(s) generated and attached for {1}.").format(len(contexts), si.name),
    user=user,
)


def _get_contact_details(si):
    contact_mobile = si.get("contact_mobile") or ""
    contact_email = si.get("contact_email") or ""
    if not contact_mobile or not contact_email:
        customer_details = frappe.db.get_value(
            "Customer", si.customer, ["mobile_no", "custom_email"], as_dict=True
        ) or {}
        contact_mobile = contact_mobile or customer_details.get("mobile_no") or ""
        contact_email = contact_email or customer_details.get("custom_email") or ""
    return contact_mobile, contact_email


def _render_sales_invoice_pdf(si):
    settings = frappe.get_cached_doc(CUSTOM_SETTINGS_DOCTYPE)
    invoice_print_format = settings.get("insurance_print_format")

    if not invoice_print_format:
        frappe.throw(
            frappe._(
                "Set 'Insurance Print Format' in {0} before generating insurance certificates."
            ).format(CUSTOM_SETTINGS_DOCTYPE)
        )

    html = frappe.get_print(
        si.doctype,
        si.name,
        print_format=invoice_print_format,
        doc=si,
        as_pdf=False,
    )
    invoice_logo_uri = _get_asset_data_uris().get("invoice_logo_src")
    if invoice_logo_uri and invoice_logo_uri != _BLANK_IMAGE_DATA_URI:
        html = _use_invoice_logo_in_letterhead(html, invoice_logo_uri)
        
    html = _inline_local_image_srcs(html)
    html = _inline_local_stylesheet_links(html)

    pdf_bytes = get_pdf(html, options={"orientation": "Portrait"})
    if not pdf_bytes:
        frappe.throw(
            frappe._("Could not render Sales Invoice {0} using print format '{1}'.").format(
                si.name, invoice_print_format
            )
        )
    return pdf_bytes


def _inline_local_image_srcs(html):
    """
    Rewrite any <img src="..."> pointing at this site's own /files/,
    /private/files/, or /assets/ paths (including an absolute URL on
    this same site) into base64 data URIs, reading the bytes directly
    off local disk instead of letting wkhtmltopdf fetch them over
    HTTP. Truly external image URLs are left untouched.
    """
    site_url = frappe.utils.get_url().rstrip("/")
    bench_path = frappe.utils.get_bench_path()
    site_path = frappe.get_site_path()

    def resolve_local_path(src):
        path = src
        if path.startswith(site_url):
            path = path[len(site_url):]
        if not path.startswith("/"):
            return None

        if path.startswith("/private/files/"):
            rel = path[len("/private/files/"):].split("?")[0]
            return os.path.join(site_path, "private", "files", rel)
        if path.startswith("/files/"):
            rel = path[len("/files/"):].split("?")[0]
            return os.path.join(site_path, "public", "files", rel)
        if path.startswith("/assets/"):
            rel = path[len("/assets/"):].split("?")[0]
            return os.path.join(bench_path, "sites", "assets", rel)
        return None

    def replace(match):
        original = match.group(0)
        src = match.group(1)
        local_path = resolve_local_path(src)

        if local_path is None:
            return original

        if not os.path.isfile(local_path):
            return original.replace(src, _BLANK_IMAGE_DATA_URI)

        mime_type, _ = mimetypes.guess_type(local_path)
        mime_type = mime_type or "application/octet-stream"
        with open(local_path, "rb") as f:
            encoded = base64.b64encode(f.read()).decode("ascii")
        data_uri = f"data:{mime_type};base64,{encoded}"
        return original.replace(src, data_uri)

    return re.sub(r'src="([^"]+)"', replace, html)


def _get_print_format_source():
    """
    Pull the "Watch Insurance Certificate" Print Format's stored HTML +
    CSS straight from the database, once per invoice (not once per
    certificate) since it doesn't change between certificates.
    """
    print_format = frappe.get_cached_doc("Print Format", CERTIFICATE_PRINT_FORMAT)

    template_source = print_format.html or ""
    if print_format.css:
        template_source = f"<style>\n{print_format.css}\n</style>\n{template_source}"

    if not template_source.strip():
        frappe.throw(
            frappe._("Print Format '{0}' has no HTML content.").format(CERTIFICATE_PRINT_FORMAT)
        )
    return template_source


def _render_certificate_to_pdf(template_source, context, asset_data_uris):
    context_vars = {"certificates": [context], **asset_data_uris}
    html = frappe.render_template(template_source, context_vars)

    pdf_bytes = get_pdf(html, options={"orientation": "Portrait"})
    if not pdf_bytes:
        frappe.throw(
            frappe._("Insurance certificate PDF generation failed for certificate {0}.").format(
                context["certificate_no"]
            )
        )
    return pdf_bytes

# def _get_asset_data_uris():
#     """
#     Read the logo/signature/banner images from this app's public/images/
#     folder once per invoice and inline them as base64 data URIs, so the
#     certificate HTML is fully self-contained -- no network/URL fetch by
#     wkhtmltopdf required at all.
#     """
#     asset_dir = frappe.get_app_path(*ASSET_RELATIVE_DIR)
#     data_uris = {}
#     for context_key, filename in ASSET_FILES.items():
#         file_path = os.path.join(asset_dir, filename)
#         mime_type, _ = mimetypes.guess_type(file_path)
#         mime_type = mime_type or "image/png"
#         with open(file_path, "rb") as f:
#             encoded = base64.b64encode(f.read()).decode("ascii")
#         data_uris[context_key] = f"data:{mime_type};base64,{encoded}"
#     return data_uris

def _get_asset_data_uris():
    """
    Read the logo/signature/banner images from the Attach fields in
    Aetas Custom Setting once per invoice and inline them as base64
    data URIs, so the certificate HTML is fully self-contained --
    no network/URL fetch by wkhtmltopdf required at all.
    Works for both public (/files/) and private (/private/files/) files.
    """
    settings = frappe.get_cached_doc(CUSTOM_SETTINGS_DOCTYPE)
    data_uris = {}

    for context_key, fieldname in ASSET_SETTING_FIELDS.items():
        file_url = settings.get(fieldname)

        if not file_url:
            frappe.log_error(
                title="Insurance Certificate: image not set",
                message=f"'{fieldname}' is empty in {CUSTOM_SETTINGS_DOCTYPE}.",
            )
            data_uris[context_key] = _BLANK_IMAGE_DATA_URI
            continue

        file_name = frappe.db.get_value("File", {"file_url": file_url}, "name")
        file_path = frappe.get_doc("File", file_name).get_full_path() if file_name else None

        if not file_path or not os.path.isfile(file_path):
            frappe.log_error(
                title="Insurance Certificate: image file missing",
                message=f"File for '{fieldname}' ({file_url}) not found on disk.",
            )
            data_uris[context_key] = _BLANK_IMAGE_DATA_URI
            continue

        mime_type, _ = mimetypes.guess_type(file_path)
        mime_type = mime_type or "image/png"
        with open(file_path, "rb") as f:
            encoded = base64.b64encode(f.read()).decode("ascii")
        data_uris[context_key] = f"data:{mime_type};base64,{encoded}"

    return data_uris


def _merge_pdfs(pdf_byte_list):
    """Concatenate PDFs page-wise, in order: [invoice pages] + [certificate pages]."""
    if len(pdf_byte_list) == 1:
        return pdf_byte_list[0]

    try:
        from pypdf import PdfReader, PdfWriter
    except ImportError:
        from PyPDF2 import PdfReader, PdfWriter

    writer = PdfWriter()
    for pdf_bytes in pdf_byte_list:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        for page in reader.pages:
            writer.add_page(page)

    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()

def _attach_pdf_to_doc(target_doc, pdf_bytes, certificate_no, invoice_name):
    file_doc = frappe.get_doc({
        "doctype": "File",
        "file_name": f"{certificate_no}.pdf",
        "attached_to_doctype": target_doc.doctype,
        "attached_to_name": target_doc.name,
        "content": pdf_bytes,
        "is_private": 1,
    })
    file_doc.save(ignore_permissions=True)
    return file_doc

def get_insurance_naming_series(si):
    """Resolve which naming series to use for a Sales Invoice Insurance
    record: Sales Invoice -> custom_boutique -> Boutique.boutique_warehouse
    -> Aetas Custom Setting.insurance_series_mappings lookup."""

    boutique = si.get("custom_boutique")
    if not boutique:
        frappe.throw(
            frappe._("Sales Invoice {0} has no Boutique set; cannot determine insurance certificate series.")
            .format(si.name)
        )

    boutique_warehouse = frappe.db.get_value("Boutique", boutique, "boutique_warehouse")
    if not boutique_warehouse:
        frappe.throw(
            frappe._("Boutique '{0}' has no Boutique Warehouse configured.").format(boutique)
        )

    settings = frappe.get_cached_doc(CUSTOM_SETTINGS_DOCTYPE)
    series_map = {
        row.boutique_warehouse: row.naming_series
        for row in settings.insurance_naming_series_mappings
    }

    naming_series = series_map.get(boutique_warehouse)
    if not naming_series:
        frappe.throw(
            frappe._(
                "No insurance certificate naming series is configured for warehouse '{0}'. "
                "Please add it in Aetas Custom Setting."
            ).format(boutique_warehouse)
        )

    return naming_series

def enqueue_insurance_certificate_generation(si, attach_to=None):
    """Call this from wherever you currently call generate_insurance_certificates()."""
    attach_to = attach_to or si

    frappe.enqueue(
        method=generate_insurance_certificates_job,   # direct function reference, no string path needed
        queue="long",
        timeout=1500,
        job_id=f"insurance-certificates-{si.name}",
        deduplicate=True,
        enqueue_after_commit=True,
        si_name=si.name,
        attach_to_doctype=attach_to.doctype,
        attach_to_name=attach_to.name,
        user=frappe.session.user,
    )

    frappe.msgprint(
        frappe._("Insurance certificate generation started in the background. You'll be notified when it's done."),
        indicator="blue",
        alert=True,
    )

def generate_insurance_certificates_job(si_name, attach_to_doctype, attach_to_name, user):
    si = frappe.get_doc("Sales Invoice", si_name)
    attach_to = (
        si if attach_to_doctype == si.doctype and attach_to_name == si.name
        else frappe.get_doc(attach_to_doctype, attach_to_name)
    )

    try:
        generate_insurance_certificates(si, attach_to=attach_to, user=user)
    except Exception:
        frappe.log_error(title=f"Insurance certificate generation failed: {si_name}")
        frappe.publish_realtime(
            event="msgprint",
            message=frappe._("Insurance certificate generation failed for {0}. Check Error Log.").format(si_name),
            user=user,
        )
        raise

def _use_invoice_logo_in_letterhead(html, logo_uri):
    """Put the 'Insurance Invoice Logo' from Aetas Custom Setting into the
    letter head area (above TAX INVOICE) of the invoice print."""
    def swap_imgs(block):
        return re.sub(
            r'(<img\b[^>]*?\bsrc=)(["\'])[^"\']*\2',
            lambda m: f'{m.group(1)}"{logo_uri}"',
            block,
            flags=re.I,
        )

    return re.sub(
        r'(<div[^>]*class="[^"]*letter-head[^"]*"[^>]*>)(.*?)(</div>)',
        lambda m: m.group(1) + swap_imgs(m.group(2)) + m.group(3),
        html,
        count=1,
        flags=re.S | re.I,
    )

def _inline_local_stylesheet_links(html):
    site_url = frappe.utils.get_url().rstrip("/")
    bench_path = frappe.utils.get_bench_path()
    site_path = frappe.get_site_path()

    def resolve_local_path(href):
        path = href
        if path.startswith(site_url):
            path = path[len(site_url):]
        if not path.startswith("/"):
            return None

        if path.startswith("/private/files/"):
            rel = path[len("/private/files/"):].split("?")[0]
            return os.path.join(site_path, "private", "files", rel)
        if path.startswith("/files/"):
            rel = path[len("/files/"):].split("?")[0]
            return os.path.join(site_path, "public", "files", rel)
        if path.startswith("/assets/"):
            rel = path[len("/assets/"):].split("?")[0]
            return os.path.join(bench_path, "sites", "assets", rel)
        return None

    def replace_wrapper(match):
        href = match.group(1) or match.group(2)
        local_path = resolve_local_path(href)
        if local_path is None or not os.path.isfile(local_path):
            return match.group(0)
        with open(local_path, "r", encoding="utf-8") as f:
            css_content = f.read()
        return f"<style>\n{css_content}\n</style>"

    pattern = re.compile(
        r'<link[^>]*rel=["\']stylesheet["\'][^>]*href=["\']([^"\']+)["\'][^>]*/?>'
        r'|<link[^>]*href=["\']([^"\']+)["\'][^>]*rel=["\']stylesheet["\'][^>]*/?>'
    )

    return pattern.sub(replace_wrapper, html)

def send_certificate_email(sii_doc, file_doc, si):
    recipient = sii_doc.get("email_id")

    if not recipient:
        frappe.db.set_value(
            "Sales Invoice Insurance", sii_doc.name, "certificate_sent", "Fail"
        )
        frappe.log_error(
            title=f"Insurance certificate email skipped: {sii_doc.name}",
            message=f"No email_id set on Sales Invoice Insurance {sii_doc.name} (Sales Invoice {si.name}).",
        )
        return

    try:
        frappe.sendmail(
            recipients=[recipient],
            subject=frappe._("Your Insurance Certificate - {0}").format(sii_doc.name),
            message=frappe._(
                "Dear Customer,<br><br>"
                "Please find attached your insurance certificate for invoice {0}.<br><br>"
                "Certificate No: {1}<br>"
                "Insurance Period: {2} to {3}<br><br>"
                "Regards,<br>{4}"
            ).format(
                si.name,
                sii_doc.name,
                frappe.utils.formatdate(sii_doc.insurance_start_date),
                frappe.utils.formatdate(sii_doc.insurance_end_date),
                si.company,
            ),
            attachments=[{"fname": file_doc.file_name, "fcontent": file_doc.get_content()}],
            reference_doctype="Sales Invoice Insurance",
            reference_name=sii_doc.name,
            now=True,
        )
        frappe.db.set_value(
            "Sales Invoice Insurance", sii_doc.name, "certificate_sent", "Yes"
        )
    except Exception:
        frappe.db.set_value(
            "Sales Invoice Insurance", sii_doc.name, "certificate_sent", "Fail"
        )
        frappe.log_error(
            title=f"Insurance certificate email failed: {sii_doc.name}",
        )

def _get_certificate_contexts_for_invoice(si_name):
    """Build template contexts from the already-created
    Sales Invoice Insurance records of this invoice."""
    records = frappe.get_all(
        "Sales Invoice Insurance",
        filters={"sales_invoice": si_name},
        fields=[
            "name", "invoice_date", "invoice_amount", "brand", "mobile_no",
            "email_id", "insurance_start_date", "insurance_end_date",
        ],
        order_by="name asc",
    )
    return [
        {
            "certificate_no": r.name,
            "invoice_no": si_name,
            "invoice_date": formatdate(r.invoice_date),
            "invoice_amount": r.invoice_amount,
            "brand": r.brand,
            "mobile_no": r.mobile_no,
            "email_id": r.email_id,
            "insurance_start_date": formatdate(r.insurance_start_date),
            "insurance_end_date": formatdate(r.insurance_end_date),
        }
        for r in records
    ]


def get_insurance_print_data(si_name):
    """Used inside the 'Sales Invoice With Insurance' print format
    (registered as a Jinja method in hooks.py)."""
    return {
        "certificates": _get_certificate_contexts_for_invoice(si_name),
        **_get_asset_data_uris(),   # logo_src, signature_src, banner_src as base64
    }