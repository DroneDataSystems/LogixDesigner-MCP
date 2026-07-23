"""Serve grpc_auth_token.bin over HTTP for Hermes cron fetch."""
from http.server import HTTPServer, BaseHTTPRequestHandler
import os

TOKEN_FILE = r"C:\temp\grpc_auth_token.bin"

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if os.path.exists(TOKEN_FILE):
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.end_headers()
            with open(TOKEN_FILE, "rb") as f:
                self.wfile.write(f.read())
        else:
            self.send_response(503)
            self.end_headers()
            self.wfile.write(b"token not available")
    def log_message(self, *args):
        pass  # Silent

HTTPServer(("127.0.0.1", 8770), Handler).serve_forever()
