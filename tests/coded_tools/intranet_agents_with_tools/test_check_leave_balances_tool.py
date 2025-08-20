from unittest import TestCase

from coded_tools.intranet_agents_with_tools.check_leave_balances_tool import (
    CheckLeaveBalancesTool,
)


class FakeAbsenceManager:
    app_url = "http://example.com"

    def get_absence_types(self, start_date):
        return {"Absencemodel": ["foo"], "Start_date": start_date}


class TestCheckLeaveBalancesTool(TestCase):
    def test_invoke_uses_absence_manager(self):
        tool = CheckLeaveBalancesTool(absence_manager=FakeAbsenceManager())
        result = tool.invoke({"start_date": "2024-01-01"}, {})
        self.assertEqual("Absence Management", result["app_name"])
        self.assertEqual("http://example.com", result["app_url"])
        self.assertEqual(["foo"], result["Absencemodel"])

