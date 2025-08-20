"""Tool to check leave balances."""

from typing import Any, Dict, Union

from neuro_san.interfaces.coded_tool import CodedTool

from coded_tools.intranet_agents_with_tools.absence_manager import AbsenceManager


class CheckLeaveBalancesTool(CodedTool):
    """Check leave balances for an employee."""

    def __init__(self, absence_manager: AbsenceManager | None = None) -> None:
        self.absence_manager = absence_manager or AbsenceManager(None, None, None)

    def invoke(self, args: Dict[str, Any], sly_data: Dict[str, Any]) -> Union[Dict[str, Any], str]:
        start_date: str = args.get("start_date", "need-start-date")
        absence_types = self.absence_manager.get_absence_types(start_date)
        absence_types["app_name"] = "Absence Management"
        absence_types["app_url"] = self.absence_manager.app_url
        return absence_types

    async def async_invoke(self, args: Dict[str, Any], sly_data: Dict[str, Any]) -> Union[Dict[str, Any], str]:
        return self.invoke(args, sly_data)


if __name__ == "__main__":
    check_leave_balances_tool = CheckLeaveBalancesTool()
    START_DATE = "2024-11-22"
    print(check_leave_balances_tool.invoke(args={"start_date": START_DATE}, sly_data={}))

