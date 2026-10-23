import unittest
from src.market_bot.core.parser import (
    classify_khqr_stage,
    extract_sender_info,
    normalize_business,
    normalize_phone,
    normalize_status,
    parse_competitor_banks,
    parse_location,
    parse_merchant_form,
)


class TestParser(unittest.TestCase):
    def test_standard_14_field_form(self):
        text = (
            "Name: chhunly Phone shop\n"
            "Tel: TG\n"
            "Business: phone Shop\n"
            "Purpose: CMCB Products\n"
            "Bank: AC/ ABA/ KB\n"
            "Amount: N/A\n"
            "Interest: N/A\n"
            "Loan Type: N/A\n"
            "Tenure: N/A\n"
            "Maturity: N/A\n"
            "Status: OP\n"
            "Potential H/M/L: L\n"
            "Potential Product: KHQR\n"
            "Remark: NID expires not yet renew"
        )
        parsed = parse_merchant_form(text)
        self.assertTrue(parsed.is_valid)
        self.assertEqual(parsed.name, "chhunly Phone shop")
        self.assertEqual(parsed.tel_clean, "TELEGRAM")
        self.assertEqual(parsed.business_clean, "Phone Shop")
        self.assertEqual(parsed.has_aba, 1)
        self.assertEqual(parsed.has_acleda, 1)
        self.assertEqual(parsed.has_other_bank, 1)
        self.assertEqual(parsed.has_cmcb, 0)
        self.assertEqual(parsed.status_clean, "OP")

    def test_khmer_unicode_form(self):
        text = (
            "Name: ភូមិគ្រឹះគាវ\n"
            "Tel: 0717775999\n"
            "Business: Food\n"
            "Purpose: CMCB Products\n"
            "Bank: ABA KHQR\n"
            "Amount: N/A\n"
            "Interest: N/A\n"
            "Loan Type: N/A\n"
            "Tenure: N/A\n"
            "Maturity: N/A\n"
            "Status: OP\n"
            "Potential H/M/L: L\n"
            "Potential Product: KHQR\n"
            "Remark: New visit and get contact owner"
        )
        parsed = parse_merchant_form(text)
        self.assertTrue(parsed.is_valid)
        self.assertEqual(parsed.name, "ភូមិគ្រឹះគាវ")
        self.assertEqual(parsed.tel_clean, "0717775999")
        self.assertEqual(parsed.business_clean, "Restaurant / Food")
        self.assertEqual(parsed.has_aba, 1)
        self.assertEqual(parsed.has_cmcb, 0)

    def test_phone_normalization(self):
        self.assertEqual(normalize_phone("061 992 166"), "061992166")
        self.assertEqual(normalize_phone("010-269-292"), "010269292")
        self.assertEqual(normalize_phone("TG"), "TELEGRAM")
        self.assertEqual(normalize_phone("Telegram"), "TELEGRAM")
        self.assertEqual(normalize_phone("N/A"), "N/A")
        self.assertEqual(normalize_phone(""), "N/A")

    def test_status_normalization(self):
        self.assertEqual(normalize_status("Exsiting"), "Existing")
        self.assertEqual(normalize_status("Existing customer"), "Existing")
        self.assertEqual(normalize_status("New Visit"), "New Visit")
        self.assertEqual(normalize_status("New"), "New Visit")
        self.assertEqual(normalize_status("Follow Up"), "Follow Up")

    def test_competitor_flags(self):
        aba, ac, cmcb, other = parse_competitor_banks("CMCB(KHQR), ABA(POS)")
        self.assertEqual(aba, 1)
        self.assertEqual(cmcb, 1)
        self.assertEqual(ac, 0)
        self.assertEqual(other, 0)

    def test_stage_classification(self):
        self.assertEqual(
            classify_khqr_stage("Existing", "Return POS machine", "CMCB (POS)"),
            "CONVERTED",
        )
        self.assertEqual(
            classify_khqr_stage("OP", "Signed Acount opening KHQR.", "ABA (KHQR)"),
            "CONVERTED",
        )
        self.assertEqual(
            classify_khqr_stage("Follow up", "Follow up POS", "ABA (KHQR)"),
            "PIPELINE",
        )
        self.assertEqual(
            classify_khqr_stage("New Visit", "New visited", "AC(KHQR)"),
            "TARGET",
        )

    def test_location_parser(self):
        msg = {
            "message_id": 101,
            "date": 1725350000,
            "location": {"latitude": 11.5911, "longitude": 104.8749},
        }
        loc = parse_location(msg)
        self.assertIsNotNone(loc)
        self.assertAlmostEqual(loc.latitude, 11.5911)
        self.assertAlmostEqual(loc.longitude, 104.8749)

    def test_invalid_chatter_rejection(self):
        text = "Hello team, please remember to visit Toul Kork today!"
        parsed = parse_merchant_form(text)
        self.assertFalse(parsed.is_valid)


if __name__ == "__main__":
    unittest.main()
