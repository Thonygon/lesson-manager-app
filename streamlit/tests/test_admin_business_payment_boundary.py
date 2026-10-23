import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ADMIN_SOURCE = (ROOT / "streamlit/app_pages/admin.py").read_text(encoding="utf-8")
EXPO_SOURCE = (ROOT / "expo/src/components/admin-workspace-screen.tsx").read_text(encoding="utf-8")
ADMIN_API_SOURCE = (ROOT / "expo/src/app/api/admin-workspace+api.ts").read_text(encoding="utf-8")


def plan_access_predicate():
    module = ast.parse(ADMIN_SOURCE)
    function = next(node for node in module.body if isinstance(node, ast.FunctionDef) and node.name == "_has_commercial_plan_access")
    function.returns = None
    for argument in function.args.args:
        argument.annotation = None
    isolated = ast.Module(body=[function], type_ignores=[])
    namespace = {}
    exec(compile(isolated, "admin_plan_access", "exec"), namespace)
    return namespace["_has_commercial_plan_access"]


class AdminBusinessPaymentBoundaryTests(unittest.TestCase):
    def test_manual_override_and_trial_are_access_not_revenue(self):
        has_access = plan_access_predicate()
        self.assertTrue(has_access({"current_plan": "pro", "subscription_status": "active", "manual_override": True}))
        self.assertTrue(has_access({"current_plan": "pro", "subscription_status": "trialing"}))
        self.assertFalse(has_access({"current_plan": "free", "subscription_status": "active"}))
        self.assertFalse(has_access({"current_plan": "pro", "subscription_status": "canceled"}))

    def test_admin_does_not_present_plan_access_as_paying_customers(self):
        self.assertNotIn('"paid_users"', ADMIN_SOURCE)
        self.assertNotIn("admin.paidUsers", EXPO_SOURCE)
        self.assertIn("admin.planAccessNotRevenue", EXPO_SOURCE)
        self.assertIn("admin_plan_access_not_revenue", ADMIN_SOURCE)

    def test_expo_business_api_never_reads_private_teacher_payments(self):
        self.assertNotIn("from('payments')", ADMIN_API_SOURCE)
        self.assertIn("rows(server, 'payment_events'", ADMIN_API_SOURCE)


if __name__ == "__main__":
    unittest.main()
