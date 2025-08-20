# Copyright (C) 2023-2025 Cognizant Digital Business, Evolutionary AI.
# All Rights Reserved.
# Issued under the Academic Public License.
#
# You can be released from the terms, and requirements of the Academic Public
# License by purchasing a commercial license.
# Purchase of a commercial license is mandatory for any use of the
# neuro-san-studio SDK Software in commercial settings.

"""Agentforce coded tool."""

from typing import Any, Dict, Optional

from neuro_san.interfaces.coded_tool import CodedTool

from coded_tools.agentforce.agentforce_adapter import AgentforceAdapter


class AgentforceAPI(CodedTool):
    """Interact with Agentforce agents using the Agentforce API."""

    def __init__(self, agentforce: Optional[AgentforceAdapter] = None) -> None:
        """Construct the tool.

        Parameters
        ----------
        agentforce:
            Optional pre-configured :class:`AgentforceAdapter` instance. If not
            provided, an instance will be created using environment variables.
        """

        self.agentforce = agentforce or AgentforceAdapter()

    def invoke(self, args: Dict[str, Any], sly_data: Dict[str, Any]) -> str:
        """Call the Agentforce API.

        Parameters
        ----------
        args:
            Dictionary containing the user's inquiry under the ``"inquiry"``
            key.
        sly_data:
            Dictionary containing ``session_id`` and ``access_token`` used to
            continue an existing conversation. The dictionary is updated with
            the latest values.

        Returns
        -------
        str
            The response message from Agentforce.

        Raises
        ------
        RuntimeError
            If the underlying adapter is not configured.
        """

        inquiry: str = args.get("inquiry")
        session_id: Optional[str] = sly_data.get("session_id")
        access_token: Optional[str] = sly_data.get("access_token")

        if not getattr(self.agentforce, "is_configured", True):
            raise RuntimeError(
                "AgentforceAdapter is not configured. Set AGENTFORCE_* environment variables."
            )

        response = self.agentforce.post_message(inquiry, session_id, access_token)

        sly_data["session_id"] = response["session_id"]
        sly_data["access_token"] = response["access_token"]
        return response["response"]["messages"][0]["message"]

    async def async_invoke(self, args: Dict[str, Any], sly_data: Dict[str, Any]) -> str:
        """Delegates to :meth:`invoke`."""

        return self.invoke(args, sly_data)


# Example usage: See tests/coded_tools/agentforce/test_agentforce_api.py

