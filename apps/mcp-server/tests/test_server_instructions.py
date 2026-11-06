"""The server tells an agent how to turn a request into IR, and when to refuse."""

from mcp_server.client import CorePipeClient
from mcp_server.server import create_mcp_server


def _instructions() -> str:
    server = create_mcp_server(CorePipeClient(pipe_name="unused", token="unused"))
    options = server.create_initialization_options()
    assert options.instructions is not None
    return options.instructions


def test_instructions_point_to_the_guide_first() -> None:
    text = _instructions()
    assert "get_authoring_guide" in text
    assert text.index("get_authoring_guide") < text.index("validate_part_graph")


def test_instructions_state_the_workflow_order() -> None:
    text = _instructions()
    assert text.index("validate_part_graph") < text.index("apply_part_graph")


def test_instructions_tell_the_agent_to_refuse_not_approximate() -> None:
    text = _instructions().lower()
    assert "cannot fulfil" in text
    assert "approximate" in text
