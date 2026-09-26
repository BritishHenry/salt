import unittest

from payments.attribution import (
    AttributionError,
    authorization_statement,
    normalize_amount,
    normalize_marketplace,
    transfers_status_from_account,
)


class AttributionTests(unittest.TestCase):
    def test_marketplace_slug(self):
        self.assertEqual(normalize_marketplace(" Vinted "), "vinted")
        with self.assertRaises(AttributionError):
            normalize_marketplace("../vinted")

    def test_amount_must_be_positive_int(self):
        self.assertEqual(normalize_amount(1250), 1250)
        with self.assertRaises(AttributionError):
            normalize_amount(12.5)
        with self.assertRaises(AttributionError):
            normalize_amount(0)

    def test_transfers_status(self):
        account = {
            "configuration": {
                "recipient": {
                    "capabilities": {
                        "stripe_balance": {
                            "stripe_transfers": {"status": "active"}
                        }
                    }
                }
            }
        }
        self.assertEqual(transfers_status_from_account(account), "active")
        self.assertEqual(transfers_status_from_account({}), "pending")

    def test_authorization_statement_names_the_sale(self):
        sale = type(
            "Sale",
            (),
            {
                "amount_minor": 2599,
                "currency": "gbp",
                "marketplace": "vinted",
                "external_sale_id": "abc-1",
            },
        )()
        statement = authorization_statement(sale)
        self.assertIn("25.99 GBP", statement)
        self.assertIn("vinted sale abc-1", statement)
        self.assertIn("Salt Stripe balance", statement)


if __name__ == "__main__":
    unittest.main()
