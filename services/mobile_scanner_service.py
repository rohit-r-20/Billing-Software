"""
Mobile Wi-Fi Barcode Scanner Service for Anti Matrix Billing ERP.
Hosts a secure local HTTP service allowing smartphones on the same Wi-Fi
network to act as wireless barcode scanners for the desktop POS terminal.
"""
import os
import sys
import json
import time
import socket
import secrets
import threading
from typing import Dict, Any, Optional, Callable
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from pathlib import Path

from services.catalogue_service import catalogue_service
from core.logging_config import logger


def get_local_lan_ip() -> str:
    """Discovers the computer's primary LAN IP address on the Wi-Fi/Ethernet network."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # Connecting to public UDP doesn't transmit packets, but prompts OS to select interface routing to LAN
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
    except Exception:
        try:
            ip = socket.gethostbyname(socket.gethostname())
        except Exception:
            ip = '127.0.0.1'
    finally:
        s.close()
    return ip


class ScannerHTTPHandler(BaseHTTPRequestHandler):
    """Handles mobile scanner webpage delivery, pairing handshake, and barcode scans."""
    
    server_instance = None  # Reference to MobileScannerService

    def log_message(self, format, *args):
        # Silence standard HTTP access logs to keep terminal output clean
        pass

    def send_json_response(self, status_code: int, data: Dict[str, Any]):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Scanner-Token")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Scanner-Token")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)
        token = query.get("token", [""])[0]

        # 1. Serve static ZXing library
        if path == "/static/zxing.min.js":
            zxing_path = Path(__file__).resolve().parent.parent / "desktop" / "static" / "zxing.min.js"
            if zxing_path.exists():
                content = zxing_path.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "application/javascript; charset=utf-8")
                self.send_header("Content-Length", str(len(content)))
                self.send_header("Cache-Control", "public, max-age=86400")
                self.end_headers()
                self.wfile.write(content)
                return
            else:
                self.send_response(404)
                self.end_headers()
                return

        # 2. Status API endpoint
        if path == "/api/status":
            svc = self.server_instance
            if not svc:
                self.send_json_response(500, {"error": "Server not initialized"})
                return
            valid_token = svc.current_token and token == svc.current_token
            self.send_json_response(200, {
                "active": svc.is_running,
                "token_valid": valid_token,
                "status": svc.status,
                "connected_device": svc.connected_device,
                "last_scan": svc.last_scan
            })
            return

        # 3. Serve Mobile Scanner HTML Webpage
        if path == "/scanner" or path == "/":
            svc = self.server_instance
            if not svc:
                self.send_response(500)
                self.end_headers()
                return

            # Check token for security
            if not svc.current_token or token != svc.current_token:
                self.send_response(401)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                unauth_html = """
                <!DOCTYPE html>
                <html><head><meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Unauthorized - Anti Matrix Scanner</title>
                <style>body{font-family:sans-serif;text-align:center;padding:40px 20px;background:#0f172a;color:#fff;}
                .box{max-width:380px;margin:auto;background:#1e293b;padding:24px;border-radius:12px;}
                h1{color:#ef4444;font-size:22px;} p{color:#94a3b8;font-size:14px;}</style>
                </head><body><div class="box">
                <h1>⚠️ Invalid or Expired Pairing Token</h1>
                <p>This wireless scanner link is unauthorized. Please scan the QR code displayed on your desktop billing screen to link your phone.</p>
                </div></body></html>
                """
                self.wfile.write(unauth_html.encode("utf-8"))
                return

            html = svc.generate_scanner_html(token)
            body = html.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        svc = self.server_instance
        if not svc:
            self.send_json_response(500, {"error": "Server not initialized"})
            return

        # Payload size security limit (10 KB)
        try:
            content_length = int(self.headers.get("Content-Length", 0))
        except ValueError:
            self.send_json_response(400, {"error": "Invalid Content-Length header"})
            return

        if content_length > 10240:
            self.send_json_response(413, {"error": "Payload too large (max 10KB)"})
            return

        raw_body = self.rfile.read(content_length)
        try:
            payload = json.loads(raw_body.decode("utf-8")) if raw_body else {}
        except Exception:
            self.send_json_response(400, {"error": "Malformed JSON payload"})
            return

        token = payload.get("token") or self.headers.get("X-Scanner-Token")
        if not svc.current_token or token != svc.current_token:
            self.send_json_response(401, {"error": "Unauthorized: Invalid or expired pairing token"})
            return

        # Handle Pairing Handshake
        if path == "/api/pair":
            device_info = payload.get("device", "Mobile Camera Device")
            svc.handle_device_paired(device_info, self.client_address[0])
            self.send_json_response(200, {
                "success": True,
                "message": "Connected to Anti Matrix Desktop ERP",
                "company_id": svc.active_company_id
            })
            return

        # Handle Barcode Scan
        if path == "/api/scan":
            barcode = str(payload.get("barcode", "")).strip().upper()
            if not barcode or len(barcode) > 64:
                self.send_json_response(400, {"error": "Invalid barcode format (must be 1-64 characters)"})
                return

            device_info = payload.get("device", "Mobile Scanner")
            result = svc.handle_barcode_received(barcode, device_info)
            self.send_json_response(200, result)
            return

        # Handle Disconnect
        if path == "/api/disconnect":
            svc.handle_device_disconnected()
            self.send_json_response(200, {"success": True, "message": "Disconnected cleanly"})
            return

        self.send_json_response(404, {"error": "Endpoint not found"})


class MobileScannerService:
    """Manages the background HTTP scanner server, pairing tokens, and scan callbacks."""

    def __init__(
        self,
        scan_callback: Optional[Callable[[str, str], None]] = None,
        status_callback: Optional[Callable[[str, str], None]] = None
    ):
        self.server: Optional[HTTPServer] = None
        self.server_thread: Optional[threading.Thread] = None
        self.lan_ip: str = "127.0.0.1"
        self.port: int = 8990
        self.current_token: str = ""
        self.status: str = "Disconnected"  # Disconnected, Waiting for Pairing, Connected, Error
        self.connected_device: str = ""
        self.connected_ip: str = ""
        self.active_company_id: str = "COMP0001"
        self.scan_callback: Optional[Callable[[str, str], None]] = scan_callback
        self.status_callback: Optional[Callable[[str, str], None]] = status_callback
        self.is_running: bool = False
        self.last_scan: Optional[Dict[str, Any]] = None
        self._last_scan_time: float = 0
        self._last_scan_code: str = ""

    def start_server(self, company_id: str = "COMP0001", port: int = 8990) -> Dict[str, Any]:
        """Starts the local Wi-Fi scanner server on LAN interface."""
        if self.is_running and self.server:
            self.active_company_id = company_id
            return self.get_info()

        self.active_company_id = company_id
        self.lan_ip = get_local_lan_ip()
        self.current_token = secrets.token_urlsafe(12)
        self.status = "Waiting for Pairing"
        self.connected_device = ""
        self.connected_ip = ""

        # Find available port starting from requested port
        selected_port = port
        for attempt_port in range(port, port + 10):
            try:
                ScannerHTTPHandler.server_instance = self
                self.server = HTTPServer(("0.0.0.0", attempt_port), ScannerHTTPHandler)
                selected_port = attempt_port
                break
            except OSError:
                continue

        if not self.server:
            self.status = "Error"
            logger.error(f"Failed to bind Mobile Scanner server on ports {port}-{port+9}")
            return {"error": "Failed to bind to local network port"}

        self.port = selected_port
        self.is_running = True

        self.server_thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.server_thread.start()

        logger.info(f"Mobile Wi-Fi Scanner server started at http://{self.lan_ip}:{self.port}/scanner?token={self.current_token}")
        if self.status_callback:
            self.status_callback("WAITING_PAIRING", f"Listening on {self.lan_ip}:{self.port}")

        return self.get_info()

    def stop_server(self) -> Dict[str, Any]:
        """Stops the running HTTP scanner server."""
        if self.server:
            try:
                self.server.shutdown()
                self.server.server_close()
            except Exception as e:
                logger.warning(f"Error closing scanner server: {e}")
        self.server = None
        self.server_thread = None
        self.is_running = False
        self.status = "Disconnected"
        self.connected_device = ""
        self.connected_ip = ""
        logger.info("Mobile Wi-Fi Scanner server stopped.")
        if self.status_callback:
            self.status_callback("DISCONNECTED", "Scanner server stopped")
        return {"success": True, "status": "Disconnected"}

    def revoke_token(self) -> Dict[str, Any]:
        """Revokes the current pairing token and generates a fresh one."""
        self.current_token = secrets.token_urlsafe(12)
        self.status = "Waiting for Pairing"
        self.connected_device = ""
        self.connected_ip = ""
        logger.info(f"Revoked pairing token. New token: {self.current_token}")
        if self.status_callback:
            self.status_callback("WAITING_PAIRING", "Token regenerated. Please pair new device.")
        return self.get_info()

    def handle_device_paired(self, device_info: str, client_ip: str):
        """Called when a smartphone connects and handshakes successfully."""
        self.connected_device = device_info
        self.connected_ip = client_ip
        self.status = "Connected"
        logger.info(f"Smartphone connected: {device_info} ({client_ip})")
        if self.status_callback:
            self.status_callback("CONNECTED", f"{device_info} ({client_ip})")

    def handle_device_disconnected(self):
        """Called when phone disconnects."""
        prev = self.connected_device
        self.connected_device = ""
        self.connected_ip = ""
        self.status = "Waiting for Pairing"
        logger.info(f"Smartphone disconnected: {prev}")
        if self.status_callback:
            self.status_callback("WAITING_PAIRING", f"Disconnected from {prev}")

    def handle_barcode_received(self, barcode: str, device_info: str) -> Dict[str, Any]:
        """
        Validates, deduplicates rapid double-scans (< 800ms),
        looks up product in catalogue, and notifies desktop UI.
        """
        now = time.time()
        # Debounce identical barcode received within 800ms
        if barcode == self._last_scan_code and (now - self._last_scan_time) < 0.8:
            logger.info(f"Ignored rapid duplicate scan for {barcode} within 800ms.")
            return {
                "success": True,
                "barcode": barcode,
                "debounced": True,
                "message": "Duplicate scan ignored (debounced)"
            }

        self._last_scan_code = barcode
        self._last_scan_time = now

        # Perform catalogue lookup
        item = catalogue_service.find_by_barcode(self.active_company_id, barcode)

        self.last_scan = {
            "barcode": barcode,
            "device": device_info,
            "timestamp": time.strftime("%H:%M:%S"),
            "found": item is not None,
            "product_name": item["name"] if item else "Unknown Barcode",
            "price": item["sales_price"] if item else None
        }

        # Deliver scan to registered desktop listener (e.g. Qt WebChannel bridge)
        if self.scan_callback:
            try:
                self.scan_callback(barcode, device_info)
            except Exception as e:
                logger.error(f"Error invoking scan_callback: {e}")

        logger.info(f"Delivered barcode scan '{barcode}' from {device_info} (Found: {item is not None}).")

        return {
            "success": True,
            "barcode": barcode,
            "found": item is not None,
            "item": {
                "name": item["name"] if item else None,
                "sales_price": item["sales_price"] if item else 0.0,
                "unit": item["unit"] if item else "Pcs."
            } if item else None
        }

    def simulate_scan(self, company_id: str, barcode: str) -> Dict[str, Any]:
        """Simulates a scan directly on desktop, exercising the exact same product lookup and event flow."""
        self.active_company_id = company_id
        return self.handle_barcode_received(barcode.strip().upper(), "Desktop Simulator")

    def get_info(self) -> Dict[str, Any]:
        """Returns full network URL, QR payload, and status for desktop UI."""
        pairing_url = f"http://{self.lan_ip}:{self.port}/scanner?token={self.current_token}"
        return {
            "is_running": self.is_running,
            "lan_ip": self.lan_ip,
            "port": self.port,
            "token": self.current_token,
            "url": pairing_url,
            "status": self.status,
            "connected_device": self.connected_device,
            "connected_ip": self.connected_ip,
            "last_scan": self.last_scan
        }

    def generate_scanner_html(self, token: str) -> str:
        """Generates the lightweight, responsive mobile camera scanner webpage."""
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
  <title>Anti Matrix &bull; Mobile Barcode Scanner</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      background: #0f172a;
      color: #ffffff;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
      min-height: 100vh;
      display: flex;
      flex-direction: column;
    }}
    header {{
      background: #1e293b;
      padding: 14px 16px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      border-bottom: 1px solid #334155;
    }}
    .brand {{
      display: flex;
      align-items: center;
      gap: 10px;
    }}
    .brand-badge {{
      background: #2563eb;
      color: #fff;
      font-weight: 900;
      font-size: 14px;
      padding: 2px 7px;
      border-radius: 4px;
    }}
    .brand-title {{
      font-size: 15px;
      font-weight: 800;
      letter-spacing: 0.3px;
    }}
    .status-pill {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 4px 10px;
      border-radius: 12px;
      font-size: 11px;
      font-weight: 700;
      background: #064e3b;
      color: #34d399;
      border: 1px solid #059669;
    }}
    .status-dot {{
      width: 7px;
      height: 7px;
      border-radius: 50%;
      background: #34d399;
      animation: pulse 1.5s infinite;
    }}
    @keyframes pulse {{
      0% {{ opacity: 1; transform: scale(1); }}
      50% {{ opacity: 0.4; transform: scale(1.2); }}
      100% {{ opacity: 1; transform: scale(1); }}
    }}
    main {{
      flex: 1;
      padding: 16px;
      display: flex;
      flex-direction: column;
      max-width: 500px;
      margin: 0 auto;
      width: 100%;
    }}
    .viewfinder-card {{
      background: #020617;
      border: 2px solid #334155;
      border-radius: 12px;
      overflow: hidden;
      position: relative;
      aspect-ratio: 4/3;
      display: flex;
      align-items: center;
      justify-content: center;
      box-shadow: 0 8px 20px rgba(0,0,0,0.4);
      margin-bottom: 16px;
    }}
    video {{
      width: 100%;
      height: 100%;
      object-fit: cover;
    }}
    .laser-line {{
      position: absolute;
      top: 50%;
      left: 10%;
      right: 10%;
      height: 2px;
      background: #ef4444;
      box-shadow: 0 0 8px #ef4444;
      animation: laserSweep 2s ease-in-out infinite alternate;
      z-index: 10;
    }}
    @keyframes laserSweep {{
      0% {{ top: 20%; }}
      100% {{ top: 80%; }}
    }}
    .viewfinder-overlay {{
      position: absolute;
      inset: 20px;
      border: 2px dashed rgba(255, 255, 255, 0.4);
      border-radius: 8px;
      pointer-events: none;
      z-index: 5;
    }}
    .camera-notice {{
      position: absolute;
      text-align: center;
      padding: 16px;
      color: #94a3b8;
      font-size: 13px;
      z-index: 2;
    }}
    .btn-camera-trigger {{
      width: 100%;
      background: #2563eb;
      color: #ffffff;
      border: none;
      border-radius: 8px;
      padding: 13px;
      font-size: 14px;
      font-weight: 800;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
      margin-bottom: 14px;
      box-shadow: 0 4px 10px rgba(37,99,235,0.3);
    }}
    .btn-camera-trigger:active {{
      background: #1d4ed8;
      transform: translateY(1px);
    }}
    .manual-entry-box {{
      background: #1e293b;
      border: 1px solid #334155;
      border-radius: 8px;
      padding: 12px;
      margin-bottom: 16px;
    }}
    .manual-title {{
      font-size: 12px;
      font-weight: 700;
      color: #94a3b8;
      margin-bottom: 8px;
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }}
    .input-row {{
      display: flex;
      gap: 8px;
    }}
    .barcode-input {{
      flex: 1;
      height: 40px;
      background: #0f172a;
      border: 1px solid #475569;
      border-radius: 6px;
      padding: 0 12px;
      color: #fff;
      font-size: 14px;
      font-family: monospace;
      font-weight: 700;
      outline: none;
    }}
    .barcode-input:focus {{
      border-color: #3b82f6;
    }}
    .btn-send-manual {{
      background: #10b981;
      color: #fff;
      border: none;
      border-radius: 6px;
      padding: 0 16px;
      font-size: 13px;
      font-weight: 800;
      cursor: pointer;
    }}
    .btn-send-manual:active {{
      background: #059669;
    }}
    .quick-demo-box {{
      background: #1e293b;
      border: 1px solid #334155;
      border-radius: 8px;
      padding: 12px;
      margin-bottom: 16px;
    }}
    .quick-chips {{
      display: flex;
      flex-direction: column;
      gap: 6px;
      margin-top: 8px;
    }}
    .btn-demo-chip {{
      background: #334155;
      border: 1px solid #475569;
      border-radius: 6px;
      padding: 8px 12px;
      color: #f8fafc;
      font-size: 12px;
      font-weight: 700;
      text-align: left;
      cursor: pointer;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }}
    .btn-demo-chip:active {{
      background: #2563eb;
      border-color: #3b82f6;
    }}
    .btn-demo-chip .chip-code {{
      font-family: monospace;
      color: #60a5fa;
    }}
    .last-scan-card {{
      background: #1e293b;
      border: 1px solid #334155;
      border-radius: 8px;
      padding: 12px;
      display: none;
    }}
    .last-scan-header {{
      display: flex;
      justify-content: space-between;
      font-size: 11px;
      color: #94a3b8;
      font-weight: 700;
      margin-bottom: 6px;
    }}
    .last-scan-item-name {{
      font-size: 15px;
      font-weight: 800;
      color: #34d399;
      margin-bottom: 2px;
    }}
    .last-scan-meta {{
      font-size: 13px;
      color: #cbd5e1;
      font-family: monospace;
    }}
    .toast {{
      position: fixed;
      bottom: 20px;
      left: 50%;
      transform: translateX(-50%);
      background: #10b981;
      color: #fff;
      padding: 10px 18px;
      border-radius: 20px;
      font-size: 13px;
      font-weight: 800;
      display: none;
      z-index: 100;
      box-shadow: 0 4px 12px rgba(0,0,0,0.3);
      animation: toastIn 0.2s ease-out;
    }}
    @keyframes toastIn {{
      from {{ transform: translate(-50%, 10px); opacity: 0; }}
      to {{ transform: translate(-50%, 0); opacity: 1; }}
    }}
  </style>
  <script src="/static/zxing.min.js"></script>
</head>
<body>
  <header>
    <div class="brand">
      <span class="brand-badge">&alpha;</span>
      <span class="brand-title">Anti Matrix Scanner</span>
    </div>
    <div class="status-pill" id="status-pill">
      <span class="status-dot"></span>
      <span id="status-text">Linked to POS</span>
    </div>
  </header>

  <main>
    <!-- Viewfinder -->
    <div class="viewfinder-card" id="viewfinder-card">
      <video id="scanner-video" playsinline muted></video>
      <div class="laser-line"></div>
      <div class="viewfinder-overlay"></div>
      <div class="camera-notice" id="camera-notice">
        Tap "Start Camera" below to scan barcodes continuously with your rear camera.
      </div>
    </div>

    <!-- Camera Trigger Buttons -->
    <button type="button" class="btn-camera-trigger" id="btn-toggle-camera">
      <span>📹 Start Live Camera Scan</span>
    </button>
    <input type="file" accept="image/*" capture="environment" id="file-snap-input" style="display:none;">
    <button type="button" class="btn-camera-trigger" id="btn-snap-photo" style="background:#475569;">
      <span>📷 Take Barcode Photo (Fallback)</span>
    </button>

    <!-- Manual Barcode Submission -->
    <div class="manual-entry-box">
      <div class="manual-title">Manual Barcode Input</div>
      <div class="input-row">
        <input type="text" id="manual-barcode-input" class="barcode-input" placeholder="Type barcode e.g. 890_TEST_001" autocomplete="off" />
        <button type="button" class="btn-send-manual" id="btn-send-manual">Send</button>
      </div>
    </div>

    <!-- Quick Demo Barcode Buttons -->
    <div class="quick-demo-box">
      <div class="manual-title">Tap to Test Demo Barcodes</div>
      <div class="quick-chips">
        <button type="button" class="btn-demo-chip" data-code="890_TEST_001">
          <span>Milk Bikis (₹10)</span>
          <span class="chip-code">890_TEST_001</span>
        </button>
        <button type="button" class="btn-demo-chip" data-code="890_TEST_002">
          <span>Hide &amp; Seek (₹20)</span>
          <span class="chip-code">890_TEST_002</span>
        </button>
        <button type="button" class="btn-demo-chip" data-code="8909263004690">
          <span>Levosalbutamol (Medical)</span>
          <span class="chip-code">8909263004690</span>
        </button>
      </div>
    </div>

    <!-- Last Scan Result Display -->
    <div class="last-scan-card" id="last-scan-card">
      <div class="last-scan-header">
        <span>LAST DELIVERED SCAN</span>
        <span id="scan-time">Just now</span>
      </div>
      <div class="last-scan-item-name" id="scan-name">Product Name</div>
      <div class="last-scan-meta" id="scan-code">Barcode: 890_TEST_001</div>
    </div>
  </main>

  <div class="toast" id="toast-msg">✓ Sent to Desktop POS!</div>

  <script>
    const TOKEN = "{token}";
    const videoElem = document.getElementById("scanner-video");
    const cameraNotice = document.getElementById("camera-notice");
    const btnToggleCam = document.getElementById("btn-toggle-camera");
    const btnSnap = document.getElementById("btn-snap-photo");
    const fileSnapInput = document.getElementById("file-snap-input");
    const manualInput = document.getElementById("manual-barcode-input");
    const btnSendManual = document.getElementById("btn-send-manual");
    const lastScanCard = document.getElementById("last-scan-card");
    const scanName = document.getElementById("scan-name");
    const scanCode = document.getElementById("scan-code");
    const scanTime = document.getElementById("scan-time");
    const toast = document.getElementById("toast-msg");

    let isScanning = false;
    let codeReader = null;
    let audioCtx = null;

    // Web Audio Synthesizer Beep
    function playBeep() {{
      try {{
        if (!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        if (audioCtx.state === 'suspended') audioCtx.resume();
        const osc = audioCtx.createOscillator();
        const gain = audioCtx.createGain();
        osc.connect(gain);
        gain.connect(audioCtx.destination);
        osc.type = "sine";
        osc.frequency.setValueAtTime(1760, audioCtx.currentTime); // 1.76kHz crisp POS beep
        gain.gain.setValueAtTime(0.2, audioCtx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + 0.12);
        osc.start();
        osc.stop(audioCtx.currentTime + 0.12);
      }} catch (e) {{}}
      if (navigator.vibrate) navigator.vibrate(80);
    }}

    function showToast(msg, isError = false) {{
      toast.textContent = msg;
      toast.style.background = isError ? "#ef4444" : "#10b981";
      toast.style.display = "block";
      setTimeout(() => {{ toast.style.display = "none"; }}, 2500);
    }}

    // Device Handshake on Page Load
    async function sendPairHandshake() {{
      const userAgent = navigator.userAgent;
      let devName = "Mobile Device";
      if (/iPhone|iPad/i.test(userAgent)) devName = "Apple iOS Device";
      else if (/Android/i.test(userAgent)) devName = "Android Device";

      try {{
        await fetch("/api/pair", {{
          method: "POST",
          headers: {{ "Content-Type": "application/json" }},
          body: JSON.stringify({{ token: TOKEN, device: devName }})
        }});
      }} catch (e) {{}}
    }}
    sendPairHandshake();

    // Barcode Delivery to Desktop
    async function transmitBarcode(barcode) {{
      const code = String(barcode).trim();
      if (!code) return;
      playBeep();

      try {{
        const resp = await fetch("/api/scan", {{
          method: "POST",
          headers: {{ "Content-Type": "application/json" }},
          body: JSON.stringify({{ token: TOKEN, barcode: code, device: navigator.userAgent }})
        }});
        const data = await resp.json();
        if (data.success) {{
          showToast(`✓ Sent: ${{code}}`);
          lastScanCard.style.display = "block";
          scanTime.textContent = new Date().toLocaleTimeString();
          scanCode.textContent = `Barcode: ${{code}}`;
          if (data.item && data.item.name) {{
            scanName.textContent = `${{data.item.name}} (₹${{data.item.sales_price}})`;
            scanName.style.color = "#34d399";
          }} else {{
            scanName.textContent = "Product Not Registered in POS";
            scanName.style.color = "#fbbf24";
          }}
        }} else {{
          showToast(`⚠️ Error: ${{data.error || 'Failed'}}`, true);
        }}
      }} catch (err) {{
        showToast("⚠️ Network Error. Check Wi-Fi.", true);
      }}
    }}

    // Continuous Live Camera Scanning via ZXing
    async function startCameraScanner() {{
      if (typeof ZXing === "undefined") {{
        showToast("ZXing library loading...", true);
        return;
      }}
      try {{
        codeReader = new ZXing.BrowserMultiFormatReader();
        const devices = await codeReader.listVideoInputDevices();
        if (devices.length === 0) {{
          alert("No camera found on this device.");
          return;
        }}
        // Prefer back camera
        let selectedId = devices[0].deviceId;
        const backCam = devices.find(d => /back|rear|environment/i.test(d.label));
        if (backCam) selectedId = backCam.deviceId;

        cameraNotice.style.display = "none";
        isScanning = true;
        btnToggleCam.innerHTML = "<span>⏹ Stop Live Camera</span>";
        btnToggleCam.style.background = "#dc2626";

        codeReader.decodeFromVideoDevice(selectedId, "scanner-video", (result, err) => {{
          if (result) {{
            transmitBarcode(result.getText());
          }}
        }});
      }} catch (e) {{
        cameraNotice.innerHTML = "Live camera access requires HTTPS on some mobile browsers.<br>Use the <b>Take Barcode Photo</b> button below as fallback!";
        cameraNotice.style.display = "block";
        isScanning = false;
        btnToggleCam.innerHTML = "<span>📹 Start Live Camera Scan</span>";
        btnToggleCam.style.background = "#2563eb";
      }}
    }}

    function stopCameraScanner() {{
      if (codeReader) {{
        codeReader.reset();
        codeReader = null;
      }}
      isScanning = false;
      btnToggleCam.innerHTML = "<span>📹 Start Live Camera Scan</span>";
      btnToggleCam.style.background = "#2563eb";
      cameraNotice.style.display = "block";
    }}

    btnToggleCam.addEventListener("click", () => {{
      if (isScanning) stopCameraScanner();
      else startCameraScanner();
    }});

    // Camera Photo Fallback (works on 100% of mobile browsers without HTTPS constraints)
    btnSnap.addEventListener("click", () => fileSnapInput.click());
    fileSnapInput.addEventListener("change", async (e) => {{
      const file = e.target.files[0];
      if (!file) return;
      if (typeof ZXing === "undefined") return;
      try {{
        const reader = new FileReader();
        reader.onload = async (event) => {{
          const img = new Image();
          img.onload = async () => {{
            const zx = new ZXing.BrowserMultiFormatReader();
            try {{
              const result = await zx.decodeFromImage(img);
              if (result) transmitBarcode(result.getText());
            }} catch (decodeErr) {{
              showToast("Could not detect barcode in photo. Try closer.", true);
            }}
          }};
          img.src = event.target.result;
        }};
        reader.readAsDataURL(file);
      }} catch (err) {{
        showToast("Error processing photo.", true);
      }}
    }});

    // Manual Barcode Buttons
    btnSendManual.addEventListener("click", () => {{
      if (manualInput.value.trim()) {{
        transmitBarcode(manualInput.value.trim());
        manualInput.value = "";
      }}
    }});
    manualInput.addEventListener("keydown", (e) => {{
      if (e.key === "Enter") {{
        btnSendManual.click();
      }}
    }});

    // Quick Demo Barcode Chips
    document.querySelectorAll(".btn-demo-chip").forEach(btn => {{
      btn.addEventListener("click", () => {{
        transmitBarcode(btn.dataset.code);
      }});
    }});
  </script>
</body>
</html>"""


mobile_scanner_service = MobileScannerService()
