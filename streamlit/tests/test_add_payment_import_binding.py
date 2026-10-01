import unittest

import app_pages.app_page_add_payment as add_payment_page
import core.database as database
import helpers.classes_payments as class_payments


class AddPaymentImportBindingTests(unittest.TestCase):
    def test_payment_page_uses_database_add_payment_writer(self):
        self.assertIs(add_payment_page.add_payment, database.add_payment)

    def test_payment_page_uses_database_delete_row(self):
        self.assertIs(add_payment_page.delete_row, database.delete_row)
        self.assertIsNot(add_payment_page.delete_row, class_payments.delete_row)


if __name__ == "__main__":
    unittest.main()
