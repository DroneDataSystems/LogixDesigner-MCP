"""Shared fixtures for logix-mcp tests."""

import pytest
import pytest_asyncio

from logix_mcp.sdk_interop_mock import MockSdkInterop

@pytest.fixture
def mock_sdk() -> MockSdkInterop:
    """Fresh mock SDK instance (no project open)."""
    return MockSdkInterop()

@pytest.fixture
def open_sdk(mock_sdk: MockSdkInterop, tmp_path) -> MockSdkInterop:
    """Mock SDK with a fake ACD project already opened."""
    fake_acd = tmp_path / "Test_Controller.ACD"
    fake_acd.write_bytes(b"FAKE_ACD_BINARY_CONTENT")
    mock_sdk.open_project(str(fake_acd))
    return mock_sdk


@pytest_asyncio.fixture
async def mcp():
    """FastMCP server instance for async tool tests."""
    from logix_mcp.server import create_app

    return create_app()
