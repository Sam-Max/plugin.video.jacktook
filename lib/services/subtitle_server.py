# -*- coding: utf-8 -*-
"""
Local web server for uploading subtitle files from a browser.

Serves a web UI with drag & drop file upload and exposes an API endpoint
to receive the subtitle file via HTTP POST.
"""
import os
import socket
import threading
import json
import uuid
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler

from lib.utils.kodi.utils import ADDON_PROFILE_PATH, kodilog


_WEB_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "resources",
    "web",
)

# Supported subtitle extensions
SUBTITLE_EXTENSIONS = {'.srt', '.ass', '.ssa', '.sub', '.vtt', '.txt'}


def _ensure_upload_dir():
    """Create upload directory if it doesn't exist."""
    upload_dir = os.path.join(ADDON_PROFILE_PATH, "Subtitles", "uploads")
    os.makedirs(upload_dir, exist_ok=True)
    return upload_dir


def _is_valid_extension(filename):
    """Check if file has a supported subtitle extension."""
    ext = os.path.splitext(filename)[1].lower()
    return ext in SUBTITLE_EXTENSIONS


class SubtitleUploadHandler(BaseHTTPRequestHandler):
    """Handles HTTP requests for subtitle upload."""

    @property
    def wrapper_server(self):
        """Get the SubtitleUploadServer wrapper instance."""
        # The wrapper is stored as an attribute on the HTTPServer
        return getattr(self.server, 'wrapper_server', None)

    def log_message(self, format, *args):
        kodilog(f"[SubtitleServer] {format % args}")

    def _send_json(self, data, status=200):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, html_content):
        body = html_content.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_error_page(self, message):
        safe_message = self._html_escape(message)
        error_html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Upload Error</title>
    <style>
        body {{ font-family: sans-serif; background: #0d1117; color: #e6edf3; 
               display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; }}
        .error-box {{ background: #161b22; border: 1px solid #f85149; border-radius: 12px; 
                      padding: 30px; text-align: center; max-width: 400px; }}
        h1 {{ color: #f85149; margin: 0 0 15px 0; }}
        p {{ color: #8b949e; margin: 0; }}
        .back {{ margin-top: 20px; color: #58a6ff; text-decoration: none; }}
    </style>
</head>
<body>
    <div class="error-box">
        <h1>Upload Failed</h1>
        <p>{safe_message}</p>
        <a href="/" class="back">&larr; Go back</a>
    </div>
</body>
</html>"""
        self._send_html(error_html)

    @staticmethod
    def _html_escape(text):
        """Escape HTML special characters to prevent XSS."""
        return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;").replace("'", "&#39;")

    def _send_success_page(self, filename):
        safe_filename = self._html_escape(filename)
        success_html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Upload Successful</title>
    <style>
        body {{ font-family: sans-serif; background: #0d1117; color: #e6edf3; 
               display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; }}
        .success-box {{ background: #161b22; border: 1px solid #3fb950; border-radius: 12px; 
                        padding: 30px; text-align: center; max-width: 400px; }}
        h1 {{ color: #3fb950; margin: 0 0 15px 0; }}
        p {{ color: #8b949e; margin: 0; }}
        .filename {{ color: #e6edf3; font-weight: bold; margin-top: 10px; }}
        .close {{ margin-top: 20px; color: #8b949e; font-size: 0.9rem; }}
    </style>
</head>
<body>
    <div class="success-box">
        <h1>Upload Successful!</h1>
        <p>File received:</p>
        <p class="filename">{safe_filename}</p>
        <p class="close">You can close this tab now.</p>
    </div>
</body>
</html>"""
        self._send_html(success_html)

    def do_GET(self):
        if self.path == "/" or self.path == "":
            self._serve_index()
        elif self.path == "/status":
            self._serve_status()
        else:
            self.send_error(404)

    def do_POST(self):
        if self.path == "/upload":
            self._handle_upload()
        else:
            self.send_error(404)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def _serve_index(self):
        index_path = os.path.join(_WEB_DIR, "upload.html")
        try:
            with open(index_path, "r", encoding="utf-8") as f:
                self._send_html(f.read())
        except FileNotFoundError:
            self.send_error(500, "Upload page not found")

    def _serve_status(self):
        """Return current upload status."""
        wrapper = self.wrapper_server
        uploaded_file = wrapper.get_uploaded_file() if wrapper else None
        self._send_json({
            "uploaded": uploaded_file is not None,
            "path": uploaded_file
        })

    def _parse_multipart(self):
        """
        Parse multipart/form-data without cgi module.
        Returns (filename, file_content) tuple or (None, error_message).
        """
        content_type = self.headers.get('Content-Type', '')
        
        if not content_type.startswith('multipart/form-data'):
            return None, "Invalid content type"

        # Extract boundary from content-type
        boundary_marker = 'boundary='
        boundary_idx = content_type.find(boundary_marker)
        if boundary_idx == -1:
            return None, "No boundary in content type"
        
        boundary = content_type[boundary_idx + len(boundary_marker):]
        boundary = boundary.strip('"')
        boundary_bytes = ('--' + boundary).encode('utf-8')
        end_boundary_bytes = ('--' + boundary + '--').encode('utf-8')

        content_length = int(self.headers.get('Content-Length', 0))
        if content_length == 0:
            return None, "No data received"

        # Read raw POST data
        post_data = self.rfile.read(content_length)
        
        # Find first boundary
        start_idx = post_data.find(boundary_bytes)
        if start_idx == -1:
            return None, "Invalid multipart data"

        # Parse each part
        pos = start_idx + len(boundary_bytes)
        
        while pos < len(post_data):
            # Check for end boundary
            if post_data[pos:pos + 2] == b'--':
                break
            
            # Skip CRLF after boundary
            if post_data[pos:pos + 2] == b'\r\n':
                pos += 2
            elif post_data[pos:pos + 1] == b'\n':
                pos += 1
            
            # Find headers end (double CRLF)
            header_end = post_data.find(b'\r\n\r\n', pos)
            if header_end == -1:
                header_end = post_data.find(b'\n\n', pos)
                header_end_len = 2
                if header_end == -1:
                    continue
            else:
                header_end_len = 4
            
            headers = post_data[pos:header_end].decode('utf-8', errors='replace')
            pos = header_end + header_end_len
            
            # Check if this is a file field
            if 'Content-Disposition' not in headers:
                continue
                
            # Find next boundary
            next_boundary = post_data.find(boundary_bytes, pos)
            if next_boundary == -1:
                next_boundary = post_data.find(end_boundary_bytes, pos)
            if next_boundary == -1:
                break
            
            # Extract field data (remove trailing CRLF)
            field_data = post_data[pos:next_boundary]
            if field_data.endswith(b'\r\n'):
                field_data = field_data[:-2]
            elif field_data.endswith(b'\n'):
                field_data = field_data[:-1]
            
            # Parse Content-Disposition for filename
            if 'filename="' in headers or "filename='" in headers:
                # Extract filename
                filename_start = headers.find('filename="')
                if filename_start == -1:
                    filename_start = headers.find("filename='")
                    quote_char = "'"
                else:
                    quote_char = '"'
                
                if filename_start != -1:
                    filename_start += 10  # len('filename="')
                    filename_end = headers.find(quote_char, filename_start)
                    if filename_end != -1:
                        filename = headers[filename_start:filename_end]
                        return filename, field_data
            
            pos = next_boundary
        
        return None, "No file found in upload"

    def _handle_upload(self):
        """Handle multipart form data upload."""
        try:
            filename, file_content = self._parse_multipart()
            
            if filename is None:
                error_msg = file_content
                kodilog(f"[SubtitleServer] Upload error: {error_msg}")
                self._send_json({"error": error_msg}, 400)
                return

            filename = os.path.basename(filename)
            
            # Validate extension
            if not _is_valid_extension(filename):
                ext = os.path.splitext(filename)[1].lower() or "unknown"
                self._send_json({
                    "error": f"Invalid file type: {ext}. Supported: {', '.join(SUBTITLE_EXTENSIONS)}"
                }, 400)
                return

            # Save the file with unique name to avoid collisions
            upload_dir = _ensure_upload_dir()
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            unique_id = str(uuid.uuid4())[:8]
            safe_filename = f"{timestamp}_{unique_id}_{filename}"
            file_path = os.path.join(upload_dir, safe_filename)

            with open(file_path, 'wb') as f:
                f.write(file_content if isinstance(file_content, bytes) else file_content.encode('utf-8'))

            kodilog(f"[SubtitleServer] File uploaded: {file_path}")
            
            # Notify server instance
            wrapper = self.wrapper_server
            if wrapper:
                wrapper.set_uploaded_file(file_path)
            else:
                kodilog("[SubtitleServer] Warning: wrapper_server not available")
            
            # Send success response (HTML page for browser, JSON for API)
            accept = self.headers.get('Accept', '')
            if 'application/json' in accept:
                self._send_json({
                    "success": True,
                    "filename": filename,
                    "path": file_path
                })
            else:
                self._send_success_page(filename)

        except Exception as e:
            kodilog(f"[SubtitleServer] Upload error: {e}")
            import traceback
            kodilog(traceback.format_exc())
            self._send_json({"error": str(e)}, 500)


class SubtitleUploadServer:
    """Threaded HTTP server for subtitle uploads."""

    def __init__(self, port=8082):
        self.port = port
        self._server = None
        self._thread = None
        self._uploaded_file = None
        self._upload_event = threading.Event()

    def start(self):
        if self._server:
            return
        try:
            self._server = HTTPServer(("0.0.0.0", self.port), SubtitleUploadHandler)
            # Store reference to this wrapper so handlers can access it
            self._server.wrapper_server = self
            self._thread = threading.Thread(
                target=self._server.serve_forever, daemon=True
            )
            self._thread.start()
            kodilog(f"[SubtitleServer] Started on port {self.port}")
        except OSError:
            fallback = find_available_port(preferred=self.port + 1)
            self.port = fallback
            try:
                self._server = HTTPServer(("0.0.0.0", self.port), SubtitleUploadHandler)
                self._server.wrapper_server = self
                self._thread = threading.Thread(
                    target=self._server.serve_forever, daemon=True
                )
                self._thread.start()
                kodilog(f"[SubtitleServer] Started on fallback port {self.port}")
            except Exception as e:
                kodilog(f"[SubtitleServer] Failed to start on fallback port: {e}")
                self._server = None
        except Exception as e:
            kodilog(f"[SubtitleServer] Failed to start: {e}")
            self._server = None

    def stop(self):
        if self._server:
            try:
                self._server.shutdown()
                self._server.server_close()
            except Exception as e:
                kodilog(f"[SubtitleServer] Error stopping: {e}")
            self._server = None
            self._thread = None
            kodilog("[SubtitleServer] Stopped")

    def set_uploaded_file(self, file_path):
        """Called by handler when file is uploaded."""
        self._uploaded_file = file_path
        self._upload_event.set()

    def get_uploaded_file(self):
        """Get the uploaded file path (None if not uploaded yet)."""
        return self._uploaded_file

    def wait_for_upload(self, timeout=None):
        """Block until a file is uploaded or timeout. Returns True if file uploaded."""
        return self._upload_event.wait(timeout)

    @property
    def is_running(self):
        return self._server is not None


def _is_port_available(port):
    """Check if a port is available for binding."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(("0.0.0.0", port))
        s.close()
        return True
    except OSError:
        return False


def find_available_port(preferred=8082, max_attempts=10):
    """Find an available port, starting from the preferred one."""
    for offset in range(max_attempts):
        port = preferred + offset
        if _is_port_available(port):
            return port
    # Last resort: let the OS assign one
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(("0.0.0.0", 0))
        port = s.getsockname()[1]
        s.close()
        return port
    except OSError:
        return preferred


def get_local_ip():
    """Get the machine's LAN IP address."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"
