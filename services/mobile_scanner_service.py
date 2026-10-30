"""
Mobile Wi-Fi Barcode Scanner Service for Anti Matrix Billing ERP.
Hosts a local HTTPS service with TLS certificate management allowing smartphones
on the same Wi-Fi network to act as high-speed wireless barcode scanners.
"""
import os
import ssl
import sys
import json
import time
import socket
import atexit
import secrets
import threading
from typing import Dict, Any, Optional, Callable
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from pathlib import Path

from services.catalogue_service import catalogue_service
from services.cert_service import cert_service
from core.logging_config import logger


# Explicit Truthful Connection States
STATE_SERVER_WAITING = "Service Running — Waiting for Phone"
STATE_PAIRING = "Pairing in Progress"
STATE_CONNECTED = "Phone Connected"
STATE_DISCONNECTED = "Disconnected"
STATE_ERROR = "Connection Error"


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
    """Handles mobile scanner webpage delivery, pairing handshake, and barcode scans over HTTPS."""

    server_instance = None  # Reference to MobileScannerService

    def log_message(self, format, *args):
        # Silence access logs to keep terminal output clean
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

        # 1. Download Root CA Certificate
        if path == "/ca.crt":
            try:
                content = cert_service.get_ca_cert_pem()
                self.send_response(200)
                self.send_header("Content-Type", "application/x-x509-ca-cert")
                self.send_header("Content-Disposition", 'attachment; filename="anti_matrix_ca.crt"')
                self.send_header("Content-Length", str(len(content)))
                self.send_header("Cache-Control", "no-cache")
                self.end_headers()
                self.wfile.write(content)
                return
            except Exception as e:
                logger.error(f"Error serving CA certificate: {e}")
                self.send_response(500)
                self.end_headers()
                return

        # 2. Serve Static ZXing library
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

        # 3. Setup and Instructions Page
        if path == "/setup":
            svc = self.server_instance
            html = svc.generate_setup_html(token) if svc else "<h1>Setup</h1>"
            body = html.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        # 4. Status API endpoint
        if path == "/api/status":
            svc = self.server_instance
            if not svc:
                self.send_json_response(500, {"error": "Server not initialized"})
                return
            valid_token = bool(svc.current_token and token == svc.current_token)
            self.send_json_response(200, {
                "active": svc.is_running,
                "token_valid": valid_token,
                "status": svc.status,
                "is_https": True,
                "port": svc.port,
                "client_connected": svc.client_connected,
                "connected_device": svc.connected_device if svc.client_connected else "",
                "last_heartbeat": svc.get_last_heartbeat_str(),
                "last_scan": svc.last_scan
            })
            return

        # 4b. Heartbeat GET endpoint
        if path == "/api/heartbeat":
            svc = self.server_instance
            if not svc:
                self.send_json_response(500, {"error": "Server not initialized"})
                return
            if not svc.current_token or token != svc.current_token:
                self.send_json_response(401, {"error": "Unauthorized: Invalid token"})
                return
            svc.handle_heartbeat(self.client_address[0])
            self.send_json_response(200, {
                "success": True,
                "status": svc.status,
                "client_connected": svc.client_connected
            })
            return

        # 4c. Disconnect GET endpoint (e.g. for Beacon or image ping)
        if path == "/api/disconnect":
            svc = self.server_instance
            if svc and svc.current_token and token == svc.current_token:
                svc.handle_device_disconnected()
            self.send_json_response(200, {"success": True, "message": "Disconnected"})
            return

        # 5. Serve Mobile Scanner HTML Webpage
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
                .box{max-width:380px;margin:auto;background:#1e293b;padding:24px;border-radius:12px;border:1px solid #334155;}
                h1{color:#ef4444;font-size:20px;margin-bottom:12px;} p{color:#94a3b8;font-size:14px;line-height:1.5;}</style>
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

        # Handle Heartbeat
        if path == "/api/heartbeat":
            svc.handle_heartbeat(self.client_address[0])
            self.send_json_response(200, {
                "success": True,
                "status": svc.status,
                "client_connected": svc.client_connected
            })
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


class CompanionHTTPHandler(BaseHTTPRequestHandler):
    """
    Companion plain-HTTP server that runs alongside the primary HTTPS server.
    Serves Root CA downloads without certificate warnings and redirects HTTP traffic to HTTPS.
    """

    server_instance = None  # Reference to MobileScannerService

    def log_message(self, format, *args):
        pass

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)
        token = query.get("token", [""])[0]
        svc = self.server_instance

        # 1. Download Root CA Certificate over plain HTTP
        if path == "/ca.crt":
            try:
                content = cert_service.get_ca_cert_pem()
                self.send_response(200)
                self.send_header("Content-Type", "application/x-x509-ca-cert")
                self.send_header("Content-Disposition", 'attachment; filename="anti_matrix_ca.crt"')
                self.send_header("Content-Length", str(len(content)))
                self.send_header("Cache-Control", "no-cache")
                self.end_headers()
                self.wfile.write(content)
                return
            except Exception as e:
                logger.error(f"Error serving CA cert on companion port: {e}")
                self.send_response(500)
                self.end_headers()
                return

        # 2. Setup Guide
        if path == "/setup":
            html = svc.generate_setup_html(token) if svc else "<h1>Setup</h1>"
            body = html.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        # 3. Static ZXing library
        if path == "/static/zxing.min.js":
            zxing_path = Path(__file__).resolve().parent.parent / "desktop" / "static" / "zxing.min.js"
            if zxing_path.exists():
                content = zxing_path.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "application/javascript; charset=utf-8")
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)
                return

        # 4. Redirect all other HTTP requests to HTTPS
        if svc:
            target_token = token or svc.current_token
            redirect_url = f"https://{svc.lan_ip}:{svc.port}/scanner?token={target_token}"
            self.send_response(302)
            self.send_header("Location", redirect_url)
            self.end_headers()
            return

        self.send_response(404)
        self.end_headers()


class MobileScannerService:
    """Manages the background HTTPS scanner server, TLS certificates, pairing tokens, and scan callbacks."""

    def __init__(
        self,
        scan_callback: Optional[Callable[[str, str], None]] = None,
        status_callback: Optional[Callable[[str, str], None]] = None
    ):
        self.server: Optional[HTTPServer] = None
        self.server_thread: Optional[threading.Thread] = None
        self.http_server: Optional[HTTPServer] = None
        self.http_server_thread: Optional[threading.Thread] = None
        self._watchdog_thread: Optional[threading.Thread] = None
        self._watchdog_running: bool = False
        self._lock = threading.Lock()

        self.lan_ip: str = "127.0.0.1"
        self.port: int = 8990
        self.http_port: int = 8989
        self.current_token: str = ""
        self.status: str = STATE_DISCONNECTED
        self.client_connected: bool = False
        self.connected_device: str = ""
        self.connected_ip: str = ""
        self.last_heartbeat_time: float = 0.0
        self.heartbeat_timeout_seconds: float = 10.0  # Phone heartbeats every 3s, times out after 10s

        self.active_company_id: str = "COMP0001"
        self.scan_callback: Optional[Callable[[str, str], None]] = scan_callback
        self.status_callback: Optional[Callable[[str, str], None]] = status_callback
        self.is_running: bool = False
        self.last_scan: Optional[Dict[str, Any]] = None
        self._last_scan_time: float = 0
        self._last_scan_code: str = ""

        # Auto-register process exit hook
        atexit.register(self.stop_server)

    def _clean_device_name(self, raw_device: str) -> str:
        """
        Ensures device identification follows strict truthful rules:
        Never display generic 'Android Device' unless verified model details exist.
        Otherwise return 'Mobile device'.
        """
        raw = (raw_device or "").strip()
        if not raw or raw in ["Android Device", "Mobile Scanner", "Mobile Camera Device"]:
            return "Mobile device"

        import re
        # Check if Android user agent with specific phone model (e.g. SM-G998B, Pixel 7)
        m = re.search(r"Android[^;]+;\s*([^;/\)]+)\s*(?:Build/|\))", raw)
        if m:
            model = m.group(1).strip()
            if model and model.upper() not in ["K", "ANDROID"]:
                return f"{model} (Mobile device)"

        if "iPhone" in raw or "iPad" in raw:
            return "iPhone (Mobile device)"

        return raw if len(raw) <= 30 else "Mobile device"

    def get_last_heartbeat_str(self) -> str:
        if self.last_heartbeat_time > 0 and self.client_connected:
            return time.strftime("%H:%M:%S", time.localtime(self.last_heartbeat_time))
        return "None"

    def _start_watchdog(self):
        self._watchdog_running = True
        if self._watchdog_thread and self._watchdog_thread.is_alive():
            return
        self._watchdog_thread = threading.Thread(target=self._watchdog_loop, daemon=True)
        self._watchdog_thread.start()

    def _watchdog_loop(self):
        while self._watchdog_running and self.is_running:
            time.sleep(0.5)
            with self._lock:
                if self.client_connected:
                    elapsed = time.time() - self.last_heartbeat_time
                    if elapsed > self.heartbeat_timeout_seconds:
                        logger.info(f"Mobile scanner heartbeat expired ({elapsed:.1f}s > {self.heartbeat_timeout_seconds}s). Marking Disconnected.")
                        self.client_connected = False
                        self.status = STATE_SERVER_WAITING
                        prev_dev = self.connected_device or "Mobile device"
                        self.connected_device = ""
                        self.connected_ip = ""
                        if self.status_callback:
                            try:
                                self.status_callback("HEARTBEAT_TIMEOUT", f"Connection lost from {prev_dev} (Heartbeat timed out)")
                            except Exception as e:
                                logger.error(f"Error in status_callback on timeout: {e}")

    def start_server(self, company_id: str = "COMP0001", port: int = 8990) -> Dict[str, Any]:
        """Starts the local HTTPS scanner server and companion HTTP helper on LAN interfaces."""
        if self.is_running and self.server:
            self.active_company_id = company_id
            return self.get_info()

        self.active_company_id = company_id
        self.lan_ip = get_local_lan_ip()
        self.current_token = secrets.token_urlsafe(12)
        self.status = STATE_SERVER_WAITING
        self.client_connected = False
        self.connected_device = ""
        self.connected_ip = ""
        self.last_heartbeat_time = 0.0

        # 1. Ensure TLS certificates exist with current LAN IP in SAN
        try:
            certs = cert_service.get_or_create_server_certificate(self.lan_ip)
            server_crt = certs["server_crt"]
            server_key = certs["server_key"]
        except Exception as e:
            logger.error(f"Failed to generate TLS certificates: {e}")
            self.status = STATE_ERROR
            return {"error": f"TLS Certificate Error: {e}"}

        # 2. Bind primary HTTPS Server (wrapped with TLS)
        ScannerHTTPHandler.server_instance = self
        selected_https_port = port
        self.server = None

        ssl_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ssl_ctx.load_cert_chain(certfile=server_crt, keyfile=server_key)

        for attempt in range(port, port + 10):
            try:
                base_srv = HTTPServer(("0.0.0.0", attempt), ScannerHTTPHandler)
                base_srv.socket = ssl_ctx.wrap_socket(base_srv.socket, server_side=True)
                self.server = base_srv
                selected_https_port = attempt
                break
            except OSError:
                continue

        if not self.server:
            self.status = STATE_ERROR
            logger.error(f"Failed to bind Mobile Scanner HTTPS server on ports {port}-{port+9}")
            return {"error": "Failed to bind to local network HTTPS port"}

        self.port = selected_https_port

        # 3. Bind Companion HTTP Server (for plain-HTTP CA cert download and redirect)
        CompanionHTTPHandler.server_instance = self
        selected_http_port = 8989
        self.http_server = None
        for attempt_http in [8989, selected_https_port + 1, 8988, 8987]:
            try:
                self.http_server = HTTPServer(("0.0.0.0", attempt_http), CompanionHTTPHandler)
                selected_http_port = attempt_http
                break
            except OSError:
                continue

        self.http_port = selected_http_port
        self.is_running = True

        # Launch threads
        self.server_thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.server_thread.start()

        if self.http_server:
            self.http_server_thread = threading.Thread(target=self.http_server.serve_forever, daemon=True)
            self.http_server_thread.start()

        # Start connection watchdog
        self._start_watchdog()

        logger.info(f"Mobile Wi-Fi Scanner HTTPS server started at https://{self.lan_ip}:{self.port}/scanner?token={self.current_token}")
        logger.info(f"Companion HTTP server active at http://{self.lan_ip}:{self.http_port}/ (CA cert: /ca.crt)")

        if self.status_callback:
            self.status_callback("WAITING_PHONE", STATE_SERVER_WAITING)

        return self.get_info()

    def stop_server(self) -> Dict[str, Any]:
        """Stops the running HTTPS scanner and companion HTTP servers cleanly."""
        self._watchdog_running = False
        if not self.is_running and not self.server and not self.http_server:
            return {"success": True, "status": STATE_DISCONNECTED}

        if self.server:
            try:
                self.server.shutdown()
                self.server.server_close()
            except Exception as e:
                logger.warning(f"Error closing HTTPS scanner server: {e}")

        if self.http_server:
            try:
                self.http_server.shutdown()
                self.http_server.server_close()
            except Exception as e:
                logger.warning(f"Error closing HTTP companion server: {e}")

        self.server = None
        self.server_thread = None
        self.http_server = None
        self.http_server_thread = None
        self.is_running = False
        self.status = STATE_DISCONNECTED
        self.client_connected = False
        self.connected_device = ""
        self.connected_ip = ""
        self.last_heartbeat_time = 0.0

        try:
            logger.info("Mobile Wi-Fi Scanner service stopped.")
        except Exception:
            pass
        if self.status_callback:
            try:
                self.status_callback("DISCONNECTED", "Scanner server stopped")
            except Exception:
                pass
        return {"success": True, "status": STATE_DISCONNECTED}

    def revoke_token(self) -> Dict[str, Any]:
        """Revokes the current pairing token, resets connection, and generates a fresh one."""
        with self._lock:
            self.current_token = secrets.token_urlsafe(12)
            self.status = STATE_SERVER_WAITING if self.is_running else STATE_DISCONNECTED
            self.client_connected = False
            self.connected_device = ""
            self.connected_ip = ""
            self.last_heartbeat_time = 0.0

        logger.info(f"Revoked pairing token. New token: {self.current_token}")
        if self.status_callback:
            self.status_callback("DISCONNECTED", "Token regenerated. Waiting for phone connection.")
        return self.get_info()

    def handle_device_paired(self, device_info: str, client_ip: str):
        """Called when a smartphone connects and handshakes successfully."""
        with self._lock:
            self.connected_device = self._clean_device_name(device_info)
            self.connected_ip = client_ip
            self.client_connected = True
            self.last_heartbeat_time = time.time()
            self.status = STATE_CONNECTED

        logger.info(f"Smartphone connected: {self.connected_device} ({client_ip})")
        if self.status_callback:
            self.status_callback("CONNECTED", f"{self.connected_device} ({client_ip})")

    def handle_heartbeat(self, client_ip: str = ""):
        """Handles heartbeat ping from authenticated smartphone client."""
        with self._lock:
            now = time.time()
            self.last_heartbeat_time = now
            if not self.client_connected:
                # Phone was marked disconnected or reconnected
                self.client_connected = True
                self.status = STATE_CONNECTED
                if not self.connected_device:
                    self.connected_device = "Mobile device"
                if client_ip:
                    self.connected_ip = client_ip
                logger.info(f"Smartphone reconnected: {self.connected_device} ({self.connected_ip})")
                if self.status_callback:
                    self.status_callback("CONNECTED", f"{self.connected_device} ({self.connected_ip})")

    def handle_device_disconnected(self):
        """Called when phone disconnects cleanly."""
        with self._lock:
            prev = self.connected_device or "Mobile device"
            self.connected_device = ""
            self.connected_ip = ""
            self.client_connected = False
            self.status = STATE_SERVER_WAITING if self.is_running else STATE_DISCONNECTED

        logger.info(f"Smartphone disconnected: {prev}")
        if self.status_callback:
            self.status_callback("DISCONNECTED", f"Disconnected from {prev}")

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
            "device": device_info,
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
        # Explicitly labeled as Simulated Scan; does not modify phone connection status
        return self.handle_barcode_received(barcode.strip().upper(), "Simulated Scan")

    def get_info(self) -> Dict[str, Any]:
        """Returns full HTTPS network URL, QR payload, and status for desktop UI."""
        pairing_url = f"https://{self.lan_ip}:{self.port}/scanner?token={self.current_token}"
        return {
            "is_running": self.is_running,
            "protocol": "https",
            "lan_ip": self.lan_ip,
            "port": self.port,
            "http_port": self.http_port,
            "token": self.current_token,
            "url": pairing_url,
            "http_url": f"http://{self.lan_ip}:{self.http_port}/scanner?token={self.current_token}",
            "ca_url": f"http://{self.lan_ip}:{self.http_port}/ca.crt",
            "setup_url": f"https://{self.lan_ip}:{self.port}/setup?token={self.current_token}",
            "status": self.status,
            "client_connected": self.client_connected,
            "connected_device": self.connected_device if self.client_connected else "",
            "connected_ip": self.connected_ip if self.client_connected else "",
            "last_heartbeat": self.get_last_heartbeat_str(),
            "last_scan": self.last_scan
        }

    def generate_setup_html(self, token: str) -> str:
        """Generates the mobile-friendly step-by-step certificate and camera setup page."""
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
  <title>Anti Matrix Scanner &bull; Mobile Camera Setup</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      background: #0f172a;
      color: #f8fafc;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
      padding: 20px 16px;
      line-height: 1.5;
    }}
    .container {{
      max-width: 520px;
      margin: 0 auto;
    }}
    .header {{
      text-align: center;
      margin-bottom: 24px;
    }}
    .badge {{
      background: #2563eb;
      color: #fff;
      font-weight: 900;
      font-size: 13px;
      padding: 3px 8px;
      border-radius: 4px;
      display: inline-block;
      margin-bottom: 8px;
    }}
    h1 {{
      font-size: 20px;
      font-weight: 800;
      color: #ffffff;
    }}
    .card {{
      background: #1e293b;
      border: 1px solid #334155;
      border-radius: 10px;
      padding: 18px;
      margin-bottom: 16px;
    }}
    .card-title {{
      font-size: 15px;
      font-weight: 800;
      color: #38bdf8;
      display: flex;
      align-items: center;
      gap: 8px;
      margin-bottom: 10px;
    }}
    p, li {{
      font-size: 13px;
      color: #cbd5e1;
    }}
    ol {{
      margin: 10px 0 10px 20px;
    }}
    li {{
      margin-bottom: 8px;
    }}
    .btn-download {{
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
      width: 100%;
      background: #10b981;
      color: #ffffff;
      text-decoration: none;
      padding: 12px;
      border-radius: 6px;
      font-weight: 800;
      font-size: 14px;
      margin: 12px 0 6px 0;
    }}
    .btn-download:active {{
      background: #059669;
    }}
    .code-box {{
      background: #090d16;
      border: 1px solid #334155;
      padding: 8px 10px;
      border-radius: 4px;
      font-family: monospace;
      font-size: 12px;
      color: #34d399;
      word-break: break-all;
      margin: 8px 0;
      user-select: all;
    }}
    .btn-scanner {{
      display: block;
      text-align: center;
      width: 100%;
      background: #2563eb;
      color: #fff;
      text-decoration: none;
      padding: 12px;
      border-radius: 6px;
      font-weight: 800;
      font-size: 14px;
      margin-top: 16px;
    }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <span class="badge">&alpha; Anti Matrix</span>
      <h1>Enable Camera Scanner</h1>
      <p style="margin-top: 4px; color: #94a3b8; font-size: 12px;">Android &amp; iOS Secure Context Setup</p>
    </div>

    <!-- Option 1: Install CA Certificate -->
    <div class="card">
      <div class="card-title">
        <span>📜 Option 1 (Recommended): Trust CA Certificate</span>
      </div>
      <p>Android requires installing the local Anti Matrix Certificate Authority to grant the green lock and continuous camera streaming.</p>
      
      <a href="/ca.crt" class="btn-download" download="anti_matrix_ca.crt">
        <span>📥 Download anti_matrix_ca.crt</span>
      </a>

      <ol>
        <li>Tap the button above to download <code>anti_matrix_ca.crt</code>.</li>
        <li>On Android, open <strong>Settings &rarr; Security &amp; Privacy &rarr; More Security Settings &rarr; Encryption &amp; Credentials</strong>.</li>
        <li>Tap <strong>Install a certificate &rarr; CA certificate</strong>.</li>
        <li>Tap <strong>Install anyway</strong> and select the downloaded <code>anti_matrix_ca.crt</code>.</li>
        <li>Return to the scanner. Chrome will now show the trusted green lock and stream the camera!</li>
      </ol>
    </div>

    <!-- Option 2: Chrome Insecure Origin Flag -->
    <div class="card">
      <div class="card-title">
        <span>⚡ Option 2 (Fastest): Chrome Flag (No Install)</span>
      </div>
      <p>If you don't want to install a certificate, Android Chrome allows developer origin whitelisting in 30 seconds:</p>
      <ol>
        <li>Copy this URL into Android Chrome address bar:
          <div class="code-box">chrome://flags/#unsafely-treat-insecure-origin-as-secure</div>
        </li>
        <li>In the text field under that flag, enter:
          <div class="code-box">https://{self.lan_ip}:{self.port}</div>
        </li>
        <li>Change the dropdown to <strong>Enabled</strong> and tap <strong>Relaunch</strong> at bottom.</li>
      </ol>
    </div>

    <!-- Option 3: Fallback -->
    <div class="card">
      <div class="card-title">
        <span>📷 Option 3: Instant Fallback Photo Mode</span>
      </div>
      <p>No configuration required! Open the scanner and tap <strong>Take Barcode Photo</strong>. It works immediately on 100% of mobile browsers.</p>
    </div>

    <a href="/scanner?token={token}" class="btn-scanner">&larr; Return to Barcode Scanner</a>
  </div>
</body>
</html>"""

    def generate_scanner_html(self, token: str) -> str:
        """Generates the lightweight, responsive mobile camera scanner webpage with HTTPS checks."""
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
      padding: 12px 16px;
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
      font-size: 13px;
      padding: 2px 7px;
      border-radius: 4px;
    }}
    .brand-title {{
      font-size: 14px;
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
      transition: all 0.2s ease;
    }}
    .status-pill.disconnected {{
      background: #7f1d1d !important;
      color: #fca5a5 !important;
      border-color: #ef4444 !important;
    }}
    .status-dot {{
      width: 7px;
      height: 7px;
      border-radius: 50%;
      background: currentColor;
      animation: pulse 1.5s infinite;
    }}
    @keyframes pulse {{
      0% {{ opacity: 1; transform: scale(1); }}
      50% {{ opacity: 0.4; transform: scale(1.2); }}
      100% {{ opacity: 1; transform: scale(1); }}
    }}
    main {{
      flex: 1;
      padding: 14px;
      display: flex;
      flex-direction: column;
      max-width: 500px;
      margin: 0 auto;
      width: 100%;
    }}

    /* Security / Capability Alert Banners */
    .alert-banner {{
      padding: 10px 12px;
      border-radius: 8px;
      font-size: 12px;
      line-height: 1.4;
      margin-bottom: 12px;
      display: none;
    }}
    .alert-banner.warning {{
      background: #451a03;
      border: 1px solid #d97706;
      color: #fde68a;
    }}
    .alert-banner.error {{
      background: #450a0a;
      border: 1px solid #dc2626;
      color: #fca5a5;
    }}
    .alert-banner.info {{
      background: #082f49;
      border: 1px solid #0284c7;
      color: #bae6fd;
    }}
    .alert-banner a {{
      color: #38bdf8;
      font-weight: 700;
      text-decoration: underline;
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
      margin-bottom: 12px;
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
      display: none;
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
      padding: 12px;
      font-size: 14px;
      font-weight: 800;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
      margin-bottom: 10px;
      box-shadow: 0 4px 10px rgba(37,99,235,0.3);
      transition: all 0.15s ease;
    }}
    .btn-camera-trigger:active {{
      transform: translateY(1px);
    }}
    .manual-entry-box {{
      background: #1e293b;
      border: 1px solid #334155;
      border-radius: 8px;
      padding: 12px;
      margin-bottom: 12px;
    }}
    .manual-title {{
      font-size: 11px;
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
      height: 38px;
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
      margin-bottom: 12px;
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
    <!-- Dynamic Alert Banner for Camera / Context / Permission Status -->
    <div id="camera-alert-banner" class="alert-banner"></div>

    <!-- Viewfinder -->
    <div class="viewfinder-card" id="viewfinder-card">
      <video id="scanner-video" playsinline muted autoplay></video>
      <div class="laser-line" id="laser-line"></div>
      <div class="viewfinder-overlay"></div>
      <div class="camera-notice" id="camera-notice">
        Tap <strong>"Start Live Camera Scan"</strong> below to begin continuous rear-camera scanning.
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
    const laserLine = document.getElementById("laser-line");
    const cameraNotice = document.getElementById("camera-notice");
    const alertBanner = document.getElementById("camera-alert-banner");
    const statusPill = document.getElementById("status-pill");
    const statusText = document.getElementById("status-text");

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
    let isRequestInFlight = false;

    // Client-side debounce state to prevent duplicate cart entries
    let lastScannedText = "";
    let lastScannedTime = 0;

    function showAlert(type, htmlContent) {{
      alertBanner.className = `alert-banner ${{type}}`;
      alertBanner.innerHTML = htmlContent;
      alertBanner.style.display = "block";
    }}

    function hideAlert() {{
      alertBanner.style.display = "none";
    }}

    // Pre-flight Secure Context and Capability Validation
    function validateCameraPrerequisites() {{
      if (!window.isSecureContext) {{
        showAlert("warning", '⚠️ <strong>Insecure Context:</strong> Android Chrome blocks camera streaming on non-HTTPS origins. <br><a href="/setup" target="_blank">&rarr; Tap here for 1-minute Setup Guide (Install CA or Chrome Flag)</a>');
        return false;
      }}
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {{
        showAlert("error", '⚠️ <strong>Camera Unavailable:</strong> Your browser does not expose camera APIs in this context. Please use Chrome on Android over HTTPS, or use the <strong>Take Barcode Photo</strong> fallback below.');
        return false;
      }}
      return true;
    }}

    // Check camera permission if Permissions API is supported
    if (navigator.permissions && navigator.permissions.query) {{
      navigator.permissions.query({{ name: "camera" }}).then(res => {{
        if (res.state === "denied") {{
          showAlert("error", '🚫 <strong>Camera Permission Blocked:</strong> Tap the lock or tune icon in your browser address bar &rarr; Permissions &rarr; Camera &rarr; Allow, then refresh.');
        }}
        res.onchange = () => {{
          if (res.state === "granted") hideAlert();
          else if (res.state === "denied") showAlert("error", '🚫 <strong>Camera Permission Blocked:</strong> Please allow camera access in browser settings.');
        }};
      }}).catch(() => {{}});
    }}

    // Run prerequisite check on load
    validateCameraPrerequisites();

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
        osc.frequency.setValueAtTime(1760, audioCtx.currentTime);
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

      try {{
        const resp = await fetch("/api/pair", {{
          method: "POST",
          headers: {{ "Content-Type": "application/json" }},
          body: JSON.stringify({{ token: TOKEN, device: userAgent }})
        }});
        if (resp.ok) {{
          statusPill.className = "status-pill";
          statusText.textContent = "Linked to POS";
        }}
      }} catch (e) {{
        statusPill.className = "status-pill disconnected";
        statusText.textContent = "POS Offline";
      }}
    }}
    sendPairHandshake();

    // Regular Heartbeat to detect POS connection state and maintain active session
    setInterval(async () => {{
      try {{
        const resp = await fetch(`/api/heartbeat?token=${{TOKEN}}`);
        if (resp.ok) {{
          const data = await resp.json();
          if (data.client_connected || data.success) {{
            statusPill.className = "status-pill";
            statusText.textContent = "Linked to POS";
          }} else {{
            statusPill.className = "status-pill disconnected";
            statusText.textContent = "POS Standby";
          }}
        }} else {{
          statusPill.className = "status-pill disconnected";
          statusText.textContent = "POS Disconnected";
        }}
      }} catch (err) {{
        statusPill.className = "status-pill disconnected";
        statusText.textContent = "POS Offline";
      }}
    }}, 3000);

    // Clean disconnect on mobile browser tab close / navigation
    window.addEventListener("pagehide", () => {{
      try {{
        navigator.sendBeacon(`/api/disconnect?token=${{TOKEN}}`);
      }} catch (e) {{}}
    }});
    window.addEventListener("beforeunload", () => {{
      try {{
        navigator.sendBeacon(`/api/disconnect?token=${{TOKEN}}`);
      }} catch (e) {{}}
    }});

    // Barcode Delivery to Desktop POS with Client-Side Debouncing
    async function transmitBarcode(barcode) {{
      const code = String(barcode).trim();
      if (!code) return;

      const now = Date.now();
      // Client-side debounce: ignore identical barcode within 1.2s to prevent multiple frame triggers
      if (code === lastScannedText && (now - lastScannedTime) < 1200) {{
        return;
      }}
      lastScannedText = code;
      lastScannedTime = now;

      playBeep();

      try {{
        const resp = await fetch("/api/scan", {{
          method: "POST",
          headers: {{ "Content-Type": "application/json" }},
          body: JSON.stringify({{ token: TOKEN, barcode: code, device: navigator.userAgent }})
        }});
        const data = await resp.json();
        if (data.success) {{
          if (data.debounced) return; // Server debounced

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
        showToast("ZXing scanner library loading...", true);
        return;
      }}

      if (!validateCameraPrerequisites()) {{
        return;
      }}

      try {{
        hideAlert();
        cameraNotice.textContent = "Connecting to device camera...";
        cameraNotice.style.display = "block";

        codeReader = new ZXing.BrowserMultiFormatReader();
        const devices = await codeReader.listVideoInputDevices();
        if (!devices || devices.length === 0) {{
          showAlert("error", "📷 No camera devices detected on this smartphone.");
          cameraNotice.textContent = "No camera found.";
          return;
        }}

        // Prefer back / environment camera
        let selectedId = devices[0].deviceId;
        const backCam = devices.find(d => /back|rear|environment/i.test(d.label));
        if (backCam) selectedId = backCam.deviceId;

        cameraNotice.style.display = "none";
        laserLine.style.display = "block";
        isScanning = true;
        btnToggleCam.innerHTML = "<span>⏹ Stop Live Camera</span>";
        btnToggleCam.style.background = "#dc2626";

        showToast("✓ Live Camera Active");

        codeReader.decodeFromVideoDevice(selectedId, "scanner-video", (result, err) => {{
          if (result) {{
            transmitBarcode(result.getText());
          }}
        }});
      }} catch (e) {{
        isScanning = false;
        laserLine.style.display = "none";
        btnToggleCam.innerHTML = "<span>📹 Start Live Camera Scan</span>";
        btnToggleCam.style.background = "#2563eb";

        const errName = e.name || "";
        if (errName === "NotAllowedError" || errName === "PermissionDeniedError") {{
          showAlert("error", '🚫 <strong>Camera Permission Blocked:</strong> Please allow camera permission in Chrome site settings and refresh.<br><a href="/setup" target="_blank">&rarr; Setup Guide</a>');
          cameraNotice.textContent = "Camera permission was denied.";
        }} else if (errName === "NotFoundError" || errName === "DevicesNotFoundError") {{
          showAlert("error", "📷 No back camera found on this device.");
          cameraNotice.textContent = "No camera device available.";
        }} else if (errName === "NotReadableError" || errName === "TrackStartError") {{
          showAlert("error", "⚠️ Camera is currently in use by another app.");
          cameraNotice.textContent = "Camera hardware busy.";
        }} else {{
          showAlert("warning", `⚠️ <strong>Camera Error (${{errName || e.message}}):</strong> Android Chrome requires a trusted certificate or flag for camera access.<br><a href="/setup" target="_blank">&rarr; Open 1-Minute Setup Guide</a>`);
          cameraNotice.innerHTML = 'Live camera requires HTTPS trust.<br>Use <strong>Take Barcode Photo</strong> below!';
        }}
        cameraNotice.style.display = "block";
      }}
    }}

    function stopCameraScanner() {{
      if (codeReader) {{
        codeReader.reset();
        codeReader = null;
      }}
      isScanning = false;
      laserLine.style.display = "none";
      btnToggleCam.innerHTML = "<span>📹 Start Live Camera Scan</span>";
      btnToggleCam.style.background = "#2563eb";
      cameraNotice.textContent = 'Tap "Start Live Camera Scan" below to begin scanning.';
      cameraNotice.style.display = "block";
    }}

    btnToggleCam.addEventListener("click", () => {{
      if (isScanning) stopCameraScanner();
      else startCameraScanner();
    }});

    // Camera Photo Fallback (Works on 100% of mobile browsers regardless of context)
    btnSnap.addEventListener("click", () => fileSnapInput.click());
    fileSnapInput.addEventListener("change", async (e) => {{
      const file = e.target.files[0];
      if (!file) return;
      if (typeof ZXing === "undefined") return;

      showToast("Processing photo...");
      try {{
        const reader = new FileReader();
        reader.onload = async (event) => {{
          const img = new Image();
          img.onload = async () => {{
            const zx = new ZXing.BrowserMultiFormatReader();
            try {{
              const result = await zx.decodeFromImage(img);
              if (result) {{
                transmitBarcode(result.getText());
              }}
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


# Global singleton instance
mobile_scanner_service = MobileScannerService()
