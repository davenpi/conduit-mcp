"""
Test tool-related types.
"""

import pytest
from pydantic import ValidationError

from conduit.protocol.common import ProgressNotification
from conduit.protocol.tools import (
    InputSchema,
    ListToolsRequest,
    ListToolsResult,
    Tool,
    ToolAnnotations,
)


class TestTools:
    def test_list_tools_request_round_trip_with_cursor_and_progress_token(self):
        # Arrange
        request = ListToolsRequest(
            cursor="123",
            progress_token="456",
        )

        # Act
        protocol_data = request.to_protocol()
        wire_format = {"jsonrpc": "2.0", "id": 1, **protocol_data}
        reconstructed = ListToolsRequest.from_protocol(wire_format)

        # Assert
        assert reconstructed == request
        assert reconstructed.cursor == "123"
        assert reconstructed.progress_token == "456"
        assert reconstructed.method == "tools/list"

    def test_progress_notification_roundtrip_with_metadata(self):
        # Arrange
        payload = {
            "method": "notifications/progress",
            "params": {
                "progressToken": "progress_token",
                "progress": 0.5,
                "total": 100,
                "message": "test",
                "_meta": {"some": {"nested": "value"}},
            },
        }
        wire_format = {
            "jsonrpc": "2.0",
            "id": 1,
            **payload,
        }

        # Act
        progress_notif = ProgressNotification.from_protocol(wire_format)
        serialized = progress_notif.to_protocol()

        # Assert
        assert progress_notif.method == "notifications/progress"
        assert progress_notif.progress_token == "progress_token"
        assert progress_notif.progress == 0.5
        assert progress_notif.total == 100
        assert progress_notif.message == "test"
        assert progress_notif.metadata == {"some": {"nested": "value"}}

        # Assert
        assert serialized == payload

    def test_progress_notification_ignores_empty_metadata(self):
        # Arrange
        payload = {
            "method": "notifications/progress",
            "params": {
                "progressToken": "progress_token",
                "progress": 0.5,
                "total": 100,
                "_meta": {},
            },
        }
        wire_format = {
            "jsonrpc": "2.0",
            "id": 1,
            **payload,
        }

        # Act
        notif = ProgressNotification.from_protocol(wire_format)

        # Assert
        assert notif.metadata is None

    def test_list_tools_request_roundtrip(self):
        # Arrange
        request = ListToolsRequest(cursor="page_2")

        # Act
        protocol_data = request.to_protocol()
        wire_format = {"jsonrpc": "2.0", "id": 1, **protocol_data}
        reconstructed = ListToolsRequest.from_protocol(wire_format)

        # Assert
        assert reconstructed == request
        assert reconstructed.method == "tools/list"
        assert reconstructed.cursor == "page_2"

    def test_list_tools_result_roundtrip_with_tool_schema(self):
        # Arrange
        schema = InputSchema(
            type="object",
            properties={
                "query": {"type": "string", "description": "Search term"},
                "limit": {"type": "integer", "minimum": 1, "default": 10},
            },
            required=["query"],
        )

        tool = Tool(
            name="search_files",
            description="Search for files",
            input_schema=schema,
        )

        result = ListToolsResult(tools=[tool], next_cursor="next_page_token")

        # Act
        serialized = result.to_protocol()
        wire_format = {"jsonrpc": "2.0", "id": 1, "result": serialized}
        reconstructed = ListToolsResult.from_protocol(wire_format)

        # Assert
        assert reconstructed == result
        assert len(reconstructed.tools) == 1
        assert reconstructed.tools[0].name == "search_files"
        assert (
            reconstructed.tools[0].input_schema.properties["query"]["type"] == "string"
        )
        assert reconstructed.next_cursor == "next_page_token"

    def test_input_schema_validation(self):
        # Arrange
        schema = InputSchema(
            type="object", properties={"name": {"type": "string"}}, required=["name"]
        )

        # Assert
        assert schema.type == "object"
        with pytest.raises(ValidationError):
            InputSchema(type="array")

    def test_list_tools_result_protocol_roundtrip_complex_nested_schema(self):
        # Arrange
        schema = InputSchema(
            properties={
                "config": {
                    "type": "object",
                    "properties": {
                        "timeout": {"type": "integer"},
                        "retries": {"type": "integer"},
                    },
                },
                "files": {"type": "array", "items": {"type": "string"}},
            },
            required=["config"],
        )

        annotations = ToolAnnotations(
            title="Complex Tool", read_only_hint=True, destructive_hint=False
        )

        tool = Tool(
            name="complex_tool",
            description="A tool with complex schema",
            input_schema=schema,
            annotations=annotations,
        )
        metadata = {
            "some": "metadata",
            "other": "metadata",
        }

        original_result = ListToolsResult(
            tools=[tool], next_cursor="next_page", metadata=metadata
        )

        # Act
        serialized = original_result.to_protocol()
        wire_format = {"jsonrpc": "2.0", "id": 1, "result": serialized}
        reconstructed_result = ListToolsResult.from_protocol(wire_format)

        # Assert that the serialized result is valid
        assert "tools" in serialized
        assert isinstance(serialized["tools"], list)
        assert "nextCursor" in serialized

        # Assert that the reconstructed result is valid
        assert len(reconstructed_result.tools) == 1
        reconstructed_tool = reconstructed_result.tools[0]

        # Assert
        assert reconstructed_tool.input_schema.properties["config"]["type"] == "object"
        assert (
            reconstructed_tool.input_schema.properties["config"]["properties"][
                "timeout"
            ]["type"]
            == "integer"
        )
        assert (
            reconstructed_tool.input_schema.properties["files"]["items"]["type"]
            == "string"
        )
        assert reconstructed_tool.input_schema.required == ["config"]

        # Assert
        assert reconstructed_tool.annotations.title == "Complex Tool"
        assert reconstructed_tool.annotations.read_only_hint is True
        assert reconstructed_tool.annotations.destructive_hint is False

        # Assert
        assert reconstructed_result.next_cursor == "next_page"

        # Assert
        assert reconstructed_result.metadata == metadata
