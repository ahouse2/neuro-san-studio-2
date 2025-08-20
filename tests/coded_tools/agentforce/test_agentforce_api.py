# Copyright (C) 2023-2025 Cognizant Digital Business, Evolutionary AI.
# All Rights Reserved.
# Issued under the Academic Public License.
#
# You can be released from the terms, and requirements of the Academic Public
# License by purchasing a commercial license.
# Purchase of a commercial license is mandatory for any use of the
# neuro-san-studio SDK Software in commercial settings.
#
from unittest import TestCase

from unittest.mock import patch

from coded_tools.agentforce.agentforce_api import AgentforceAPI


class TestAgentforceAPI(TestCase):
    """
    Unit tests for AgentforceAPI class.
    """

    def test_invoke(self):
        """Agentforce API invokes the adapter and updates sly_data."""

        class FakeAgentforceAdapter:
            def __init__(self):
                self.is_configured = True
                self.calls = 0

            def post_message(self, message, session_id=None, access_token=None):
                self.calls += 1
                if self.calls == 1:
                    return {
                        "session_id": "sess-1",
                        "access_token": "token-1",
                        "response": {"messages": [{"message": "resp-1"}]},
                    }
                return {
                    "session_id": "sess-1",
                    "access_token": "token-1",
                    "response": {"messages": [{"message": "resp-2"}]},
                }

            @staticmethod
            def close_session(session_id, access_token):
                return None

        with patch("coded_tools.agentforce.agentforce_api.AgentforceAdapter", FakeAgentforceAdapter):
            agentforce_tool = AgentforceAPI()
            sly_data = {}
            response_1 = agentforce_tool.invoke(args={"inquiry": "q1"}, sly_data=sly_data)
            self.assertEqual("resp-1", response_1)
            self.assertEqual("sess-1", sly_data["session_id"])
            self.assertEqual("token-1", sly_data["access_token"])

            response_2 = agentforce_tool.invoke(args={"inquiry": "q2"}, sly_data=sly_data)
            self.assertEqual("resp-2", response_2)
            self.assertEqual("sess-1", sly_data["session_id"])
            self.assertEqual("token-1", sly_data["access_token"])

            agentforce_tool.agentforce.close_session(sly_data["session_id"], sly_data["access_token"])
