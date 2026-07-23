"""Auth token refresh daemon — captures fresh token via tshark+SDK, writes to disk.

Runs continuously, refreshes token every REFRESH_INTERVAL seconds.
For use as a Windows service via NSSM.
"""
import subprocess, sys, time, os, logging

TSHARK = r"C:\Program Files\Wireshark\tshark.exe"
SERVICE = "LogixMCPServer"
TOKEN_FILE = r"C:\temp\grpc_auth_token.bin"
ACD = r"C:\Users\MaB Technologies\Documents\PLC Projects\Mativ\Mativ_Sim.ACD"
REFRESH_INTERVAL = 1800  # 30 minutes
PCAP = r"C:\temp\grpc_auth_refresh.pcapng"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(r"C:\temp\auth_daemon.log"), logging.StreamHandler()]
)
log = logging.getLogger("auth_daemon")


def capture_auth_token():
    """Restart service, capture tshark, open project via SDK, extract token."""
    # Stop any existing capture
    subprocess.run(["taskkill", "/F", "/IM", "tshark.exe"], capture_output=True)

    # Start capture
    cap = subprocess.Popen(
        [TSHARK, "-i", "5", "-f", "tcp port 53204", "-w", PCAP],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    time.sleep(1)

    # Restart service
    subprocess.run(["sc", "stop", SERVICE], capture_output=True, timeout=30)
    time.sleep(5)
    subprocess.run(["sc", "start", SERVICE], capture_output=True, timeout=30)
    time.sleep(12)

    # Open project via SDK to trigger auth handshake
    sys.path.insert(0, r"C:\projects\LogixDesigner-MCP\src")
    from logix_mcp.sdk_interop_real import RealSdkInterop
    sdk = RealSdkInterop()
    try:
        info = sdk.open_project(ACD)
        log.info(f"SDK opened: {info.name}")
    except Exception as e:
        log.error(f"SDK open failed: {e}")
    time.sleep(2)
    sdk.close_project()

    cap.terminate()
    cap.wait(timeout=5)

    # Extract token from capture
    r = subprocess.run(
        [TSHARK, "-r", PCAP, "-Y", "tcp.payload", "-T", "fields", "-e", "tcp.payload"],
        capture_output=True, text=True
    )

    for line in r.stdout.splitlines()[:200]:
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        try:
            d = bytes.fromhex(parts[1])
            idx = d.find(b'c0sh')
            if idx < 14:
                continue
            tag_pos = idx
            while tag_pos > 0 and d[tag_pos] != 0x0a:
                tag_pos -= 1
            if tag_pos == 0:
                continue
            length = 0
            shift = 0
            p = tag_pos + 1
            while p < len(d):
                b = d[p]
                p += 1
                length |= (b & 0x7f) << shift
                if not (b & 0x80):
                    break
                shift += 7
            token = d[p:p+length]
            if len(token) >= 1500:
                with open(TOKEN_FILE, "wb") as f:
                    f.write(token)
                log.info(f"Token captured: {len(token)}B")
                return token
        except Exception:
            pass

    log.error("No auth token found in capture")
    return None


def main():
    log.info("Auth token daemon starting")
    while True:
        try:
            token = capture_auth_token()
            if token:
                log.info(f"Next refresh in {REFRESH_INTERVAL}s")
            else:
                log.warning("Token capture failed, will retry")
        except Exception as e:
            log.error(f"Refresh cycle crashed: {e}")
        time.sleep(REFRESH_INTERVAL)


if __name__ == "__main__":
    main()
