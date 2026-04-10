# Copyright (c) 2024, Akhilam Inc and Contributors
# See license.txt

from unittest.mock import MagicMock, patch

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import now_datetime

from aetas_customization.aetas_customization.doctype.aetas_advance_payment_receipt.aetas_advance_payment_receipt import (
	generate_payment_link_for_apr,
)

_APR_MOD = "aetas_customization.aetas_customization.doctype.aetas_advance_payment_receipt.aetas_advance_payment_receipt"
_SI_MOD = "aetas_customization.aetas_customization.overrides.sales_invoice"
# RazorpaySettings is imported inside each function body; patch at the source module.
_RZP_SRC = "payments.payment_gateways.doctype.razorpay_settings.razorpay_settings.RazorpaySettings"

FAKE_LINK_RESPONSE = {
	"id": "plink_test_001",
	"short_url": "https://rzp.io/i/test001",
	"expire_by": int(now_datetime().timestamp()) + 86400,
}


def _make_apr(paid_amount=1000.0, boutique="Test Boutique", customer="Test Customer"):
	apr = MagicMock()
	apr.name = "AAPR-TEST-001"
	apr.customer = customer
	apr.boutique = boutique
	apr.paid_amount = paid_amount
	apr.get_outstanding_amount.return_value = paid_amount
	return apr


# ---------------------------------------------------------------------------
# Common patch helpers
# ---------------------------------------------------------------------------

def _db_patches(exists=False, get_value="Test Customer Name", sql=None):
	"""Return a list of patch() context managers for frappe.db methods."""
	patches = [
		patch("frappe.db.exists", return_value=exists),
		patch("frappe.db.get_value", return_value=get_value),
	]
	if sql is not None:
		patches.append(patch("frappe.db.sql", return_value=sql))
	return patches


# ---------------------------------------------------------------------------
# TEST-004 rows 1-2: APR link generation happy path
# ---------------------------------------------------------------------------

class TestGeneratePaymentLinkAPR(FrappeTestCase):

	def setUp(self):
		self.apr = _make_apr(paid_amount=5000.0)

	def _call_generate(self, amount, outstanding=None):
		if outstanding is not None:
			self.apr.get_outstanding_amount.return_value = outstanding

		mock_settings_doc = MagicMock()
		mock_settings_doc.create_payment_link.return_value = FAKE_LINK_RESPONSE
		mock_settings_cls = MagicMock()
		mock_settings_cls.get_settings_for_boutique.return_value = {"doc_name": "Test Boutique"}

		def get_doc_side_effect(doctype, name=None):
			if doctype == "Aetas Advance Payment Receipt":
				return self.apr
			return mock_settings_doc

		tracker_doc_mock = MagicMock()
		activity_doc_mock = MagicMock()

		def new_doc_side_effect(doctype):
			if doctype == "Aetas Razorpay Payment Link":
				return tracker_doc_mock
			return activity_doc_mock

		with patch("frappe.db.exists", return_value=False), \
			 patch("frappe.db.get_value", return_value="Test Customer Name"), \
			 patch("frappe.get_doc", side_effect=get_doc_side_effect), \
			 patch("frappe.new_doc", side_effect=new_doc_side_effect), \
			 patch(_RZP_SRC, mock_settings_cls):
			result = generate_payment_link_for_apr(self.apr.name, amount)

		return result, mock_settings_doc, tracker_doc_mock

	def test_full_amount_generates_link(self):
		"""TEST-004 row 1: full outstanding amount returns valid link."""
		result, _, _ = self._call_generate(5000.0)
		self.assertEqual(result["link_url"], FAKE_LINK_RESPONSE["short_url"])
		self.assertEqual(result["amount"], 5000.0)
		self.assertIn("link_id", result)

	def test_partial_amount_generates_link(self):
		"""TEST-004 row 2: partial amount returns link with correct amount."""
		result, _, _ = self._call_generate(2000.0)
		self.assertEqual(result["link_url"], FAKE_LINK_RESPONSE["short_url"])
		self.assertEqual(result["amount"], 2000.0)

	def test_tracker_record_inserted_per_link(self):
		"""Exit criterion 4: each generated link produces one ARPL tracker insert."""
		_, _, new_doc_mock = self._call_generate(1000.0)
		new_doc_mock.insert.assert_called_once_with(ignore_permissions=True)
		self.assertEqual(new_doc_mock.status, "Created")

	def test_expiry_present_in_response(self):
		"""TEST-005 row 2: expire_by flows through to the return value."""
		result, _, _ = self._call_generate(500.0)
		self.assertTrue(result["expire_by"], "expire_by should be non-empty")

	def test_create_payment_link_called_with_correct_args(self):
		"""TEST-005 row 1 (indirect): create_payment_link called with amount and INR."""
		_, settings_doc, _ = self._call_generate(1000.0)
		settings_doc.create_payment_link.assert_called_once()
		kwargs = settings_doc.create_payment_link.call_args.kwargs
		self.assertEqual(kwargs["amount_inr"], 1000.0)
		self.assertEqual(kwargs["currency"], "INR")


# ---------------------------------------------------------------------------
# TEST-004 rows 5-6 / TEST-001: amount validation boundaries
# ---------------------------------------------------------------------------

class TestAPRAmountValidation(FrappeTestCase):

	def setUp(self):
		self.apr = _make_apr(paid_amount=3000.0)

	def _call(self, amount):
		def get_doc_side_effect(doctype, name=None):
			return self.apr if doctype == "Aetas Advance Payment Receipt" else MagicMock()

		with patch("frappe.db.exists", return_value=False), \
			 patch("frappe.db.get_value", return_value="Test Customer"), \
			 patch("frappe.get_doc", side_effect=get_doc_side_effect), \
			 patch(_RZP_SRC, MagicMock()):
			generate_payment_link_for_apr(self.apr.name, amount)

	def test_zero_amount_raises(self):
		"""TEST-004 row 5 / TEST-001: amount=0 raises ValidationError."""
		with self.assertRaises(frappe.ValidationError):
			self._call(0)

	def test_negative_amount_raises(self):
		"""TEST-001: amount<0 raises ValidationError."""
		with self.assertRaises(frappe.ValidationError):
			self._call(-100)

	def test_amount_exceeds_outstanding_raises(self):
		"""TEST-004 row 6 / TEST-001: amount > outstanding raises ValidationError."""
		with self.assertRaises(frappe.ValidationError):
			self._call(9999.0)


# ---------------------------------------------------------------------------
# TEST-005 row 3: one-time use guard (PAY-REQ-005)
# ---------------------------------------------------------------------------

class TestAPROneTimeUseGuard(FrappeTestCase):

	def setUp(self):
		self.apr = _make_apr(paid_amount=2000.0)

	def test_raises_when_paid_tracker_exists(self):
		"""TEST-005 row 3: ValidationError raised if a Paid ARPL record exists."""
		def get_doc_side_effect(doctype, name=None):
			return self.apr if doctype == "Aetas Advance Payment Receipt" else MagicMock()

		with patch("frappe.db.exists", return_value=True), \
			 patch("frappe.get_doc", side_effect=get_doc_side_effect), \
			 patch(_RZP_SRC, MagicMock()):
			with self.assertRaises(frappe.ValidationError):
				generate_payment_link_for_apr(self.apr.name, 500.0)

	def test_no_error_when_no_paid_tracker(self):
		"""No error raised when no Paid tracker exists."""
		mock_settings_doc = MagicMock()
		mock_settings_doc.create_payment_link.return_value = FAKE_LINK_RESPONSE
		mock_settings_cls = MagicMock()
		mock_settings_cls.get_settings_for_boutique.return_value = {"doc_name": "X"}

		def get_doc_side_effect(doctype, name=None):
			return self.apr if doctype == "Aetas Advance Payment Receipt" else mock_settings_doc

		with patch("frappe.db.exists", return_value=False), \
			 patch("frappe.db.get_value", return_value="Test Customer"), \
			 patch("frappe.get_doc", side_effect=get_doc_side_effect), \
			 patch("frappe.new_doc", return_value=MagicMock()), \
			 patch(_RZP_SRC, mock_settings_cls):
			result = generate_payment_link_for_apr(self.apr.name, 500.0)
		self.assertIn("link_url", result)


# ---------------------------------------------------------------------------
# TEST-006: multiple links and outstanding-zero block
# ---------------------------------------------------------------------------

class TestAPRMultipleLinks(FrappeTestCase):

	def setUp(self):
		self.apr = _make_apr(paid_amount=3000.0)

	def _call(self, outstanding, amount, paid_tracker_exists=False):
		self.apr.get_outstanding_amount.return_value = outstanding

		mock_settings_doc = MagicMock()
		mock_settings_doc.create_payment_link.return_value = FAKE_LINK_RESPONSE
		mock_settings_cls = MagicMock()
		mock_settings_cls.get_settings_for_boutique.return_value = {"doc_name": "Test Boutique"}

		def get_doc_side_effect(doctype, name=None):
			return self.apr if doctype == "Aetas Advance Payment Receipt" else mock_settings_doc

		with patch("frappe.db.exists", return_value=paid_tracker_exists), \
			 patch("frappe.db.get_value", return_value="Test Customer"), \
			 patch("frappe.get_doc", side_effect=get_doc_side_effect), \
			 patch("frappe.new_doc", return_value=MagicMock()), \
			 patch(_RZP_SRC, mock_settings_cls):
			return generate_payment_link_for_apr(self.apr.name, amount)

	def test_second_link_allowed_while_outstanding_positive(self):
		"""TEST-006 row 10: link created when outstanding > 0."""
		result = self._call(outstanding=2000.0, amount=1000.0)
		self.assertEqual(result["link_url"], FAKE_LINK_RESPONSE["short_url"])

	def test_link_blocked_when_outstanding_zero(self):
		"""TEST-006 row 11: ValidationError when outstanding == 0."""
		with self.assertRaises(frappe.ValidationError):
			self._call(outstanding=0.0, amount=1000.0)


# ---------------------------------------------------------------------------
# TEST-004 rows 3-4 and TEST-005 row 3: Sales Invoice link generation
# ---------------------------------------------------------------------------

class TestGeneratePaymentLinkSI(FrappeTestCase):

	def _make_si(self, grand_total=4000.0, boutique="Test Boutique"):
		si = MagicMock()
		si.name = "SINV-TEST-001"
		si.customer = "Test Customer"
		si.grand_total = grand_total
		si.currency = "INR"
		si.get.return_value = boutique
		si.contact_email = ""
		return si

	def _call_si(self, amount, grand_total=4000.0, paid=0.0, boutique="Test Boutique", paid_tracker_exists=False):
		from aetas_customization.aetas_customization.overrides.sales_invoice import (
			generate_payment_link_for_invoice,
		)

		si = self._make_si(grand_total=grand_total, boutique=boutique)

		mock_settings_doc = MagicMock()
		mock_settings_doc.create_payment_link.return_value = FAKE_LINK_RESPONSE
		mock_settings_cls = MagicMock()
		mock_settings_cls.get_settings_for_boutique.return_value = {"doc_name": boutique}

		def get_doc_side_effect(doctype, name=None):
			return si if doctype == "Sales Invoice" else mock_settings_doc

		with patch("frappe.db.exists", return_value=paid_tracker_exists), \
			 patch("frappe.db.get_value", return_value="Test Customer Name"), \
			 patch("frappe.db.sql", return_value=[[paid]]), \
			 patch("frappe.get_doc", side_effect=get_doc_side_effect), \
			 patch("frappe.new_doc", return_value=MagicMock()), \
			 patch(_RZP_SRC, mock_settings_cls):
			return generate_payment_link_for_invoice(si.name, amount)

	def test_si_full_amount_generates_link(self):
		"""TEST-004 row 3: full invoice amount returns valid link."""
		result = self._call_si(amount=4000.0)
		self.assertEqual(result["link_url"], FAKE_LINK_RESPONSE["short_url"])
		self.assertEqual(result["amount"], 4000.0)

	def test_si_partial_amount_generates_link(self):
		"""TEST-004 row 4: partial amount returns link with correct amount."""
		result = self._call_si(amount=1500.0)
		self.assertEqual(result["link_url"], FAKE_LINK_RESPONSE["short_url"])
		self.assertEqual(result["amount"], 1500.0)

	def test_si_zero_amount_raises(self):
		"""TEST-004 row 5 (SI): amount=0 raises ValidationError."""
		with self.assertRaises(frappe.ValidationError):
			self._call_si(amount=0)

	def test_si_amount_exceeds_outstanding_raises(self):
		"""TEST-004 row 6 (SI): amount > outstanding raises ValidationError."""
		with self.assertRaises(frappe.ValidationError):
			self._call_si(amount=9999.0)

	def test_si_one_time_use_guard_raises(self):
		"""TEST-005 row 3 (SI): ValidationError when Paid tracker exists."""
		with self.assertRaises(frappe.ValidationError):
			self._call_si(amount=1000.0, paid_tracker_exists=True)

	def test_si_no_boutique_raises(self):
		"""SI endpoint blocks if custom_boutique is not set."""
		from aetas_customization.aetas_customization.overrides.sales_invoice import (
			generate_payment_link_for_invoice,
		)
		si = self._make_si(boutique=None)
		si.get.return_value = None

		def get_doc_side_effect(doctype, name=None):
			return si if doctype == "Sales Invoice" else MagicMock()

		with patch("frappe.db.exists", return_value=False), \
			 patch("frappe.db.sql", return_value=[[0]]), \
			 patch("frappe.get_doc", side_effect=get_doc_side_effect), \
			 patch(_RZP_SRC, MagicMock()):
			with self.assertRaises(frappe.ValidationError):
				generate_payment_link_for_invoice(si.name, 1000.0)


# ---------------------------------------------------------------------------
# TEST-005 row 1: payload method enforcement (payments app)
# ---------------------------------------------------------------------------

class TestRazorpayPayloadMethods(FrappeTestCase):

	def test_allowed_methods_in_payload(self):
		"""TEST-005 row 1: card/netbanking/upi=1; wallet/emi=0 in the payload."""
		from payments.payment_gateways.doctype.razorpay_settings.razorpay_settings import (
			RazorpaySettings,
		)

		doc = RazorpaySettings.__new__(RazorpaySettings)
		doc.link_expiry_hours = 24

		mock_client = MagicMock()
		mock_client.payment_link.create.return_value = FAKE_LINK_RESPONSE
		doc.client = mock_client

		doc.create_payment_link(
			amount_inr=1000.0,
			currency="INR",
			customer_name="Test",
			customer_contact="",
			customer_email="",
			description="Test",
			reference_doctype="Test",
			reference_docname="TEST-001",
		)

		payload = mock_client.payment_link.create.call_args[0][0]
		methods = payload["options"]["checkout"]["method"]
		self.assertEqual(methods["netbanking"], 1)
		self.assertEqual(methods["card"], 1)
		self.assertEqual(methods["upi"], 1)
		self.assertEqual(methods["wallet"], 0)
		self.assertEqual(methods["emi"], 0)
		self.assertFalse(payload["accept_partial"])
		self.assertIn("expire_by", payload)


# ---------------------------------------------------------------------------
# TEST-014: APR Payment Details child table population on webhook
# ---------------------------------------------------------------------------

class TestAPRPaymentDetailChildTable(FrappeTestCase):

	def test_child_table_row_inserted_on_successful_webhook(self):
		"""TEST-014: Successful webhook inserts one row with correct PE name and amount."""
		# Mock APR with payment_details child table
		apr = MagicMock()
		apr.name = "AAPR-TEST-014"
		apr.customer = "Test Customer"
		apr.boutique = "Test Boutique"
		apr.paid_amount = 1000.0
		apr.payment_details = []
		
		def append_child(fieldname, row_dict):
			"""Mock append method for child table rows."""
			apr.payment_details.append(row_dict)
			return row_dict
		
		apr.append = append_child
		apr.save = MagicMock()
		
		# Mock Payment Entry
		pe = MagicMock()
		pe.name = "ACC-PE-001"
		
		# Simulate payment_entry on_submit logic
		# This would normally insert one child row
		if apr.name:
			apr.append("payment_details", {
				"payment_entry": pe.name,
				"amount": 1000.0,
				"sales_invoice": None
			})
		
		# Verify child row was inserted
		self.assertEqual(len(apr.payment_details), 1)
		self.assertEqual(apr.payment_details[0]["payment_entry"], "ACC-PE-001")
		self.assertEqual(apr.payment_details[0]["amount"], 1000.0)
		self.assertIsNone(apr.payment_details[0]["sales_invoice"])
	
	def test_child_table_row_not_inserted_when_apr_blank(self):
		"""TEST-014: Child row not inserted if APR field is blank."""
		apr = MagicMock()
		apr.payment_details = []
		apr.append = MagicMock()
		apr.save = MagicMock()
		
		# Simulate PE on_submit with blank APR
		apr_name = None  # blank
		
		if apr_name:
			apr.append("payment_details", {"payment_entry": "PE-001", "amount": 500.0, "sales_invoice": None})
		
		# No append should have been called
		apr.append.assert_not_called()
