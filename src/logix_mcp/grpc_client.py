"""gRPC client helper — reads cached auth token and provides typed stubs."""
import os
import grpc
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "proto"))
import logix_sdk_pb2 as pb
import logix_sdk_pb2_grpc as pb_grpc

TOKEN_PATH = os.path.expanduser("~/.hermes/grpc_auth_token.bin")
HOST = os.environ.get("LOGIX_GRPC_HOST", "localhost:53204")


def get_token() -> bytes:
    """Read cached auth token from disk."""
    if not os.path.exists(TOKEN_PATH):
        raise FileNotFoundError(
            f"Auth token not found at {TOKEN_PATH}. "
            "Run the grpc-auth-refresh cron job or capture manually."
        )
    with open(TOKEN_PATH, "rb") as f:
        return f.read()


def create_stub():
    """Create an authenticated LogixSDK stub."""
    channel = grpc.insecure_channel(HOST)
    return pb_grpc.LogixSDKStub(channel)
