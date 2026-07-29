# Copyright (c) 2026, Akhilam Inc and contributors
# For license information, please see license.txt

from frappe.model.document import Document


class BrandSalesPerson(Document):
    """Child row on Brand — one enabled Sales Person in the round-robin pool."""

    pass
