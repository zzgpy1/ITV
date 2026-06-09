#!/usr/bin/env python3
# src/server.py
import os
import sys
from pathlib import Path
from http.server import HTTPServer, SimpleHTTPRequestHandler

print("Starting HTTP server...", flush=True)
sys.stdout.flush()
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from src.config import OUTPUT_DIR, WEB_SERVER_HOST, WEB_SERVER_PORT
    from src.logger import logger
except ImportError as e:
    print(f"⚠️ 导入配置失败，使用默认值: {e}", file=sys.stderr)
    OUTPUT_DIR = Path("/app/output")
    WEB_SERVER_HOST = "0.0.0.0"
    WEB_SERVER_PORT = 8000
    import logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("HTTPServer")

def start_file_server():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    os.chdir(OUTPUT_DIR)

    class CORSRequestHandler(SimpleHTTPRequestHandler):
        def end_headers(self):
            self.send_header('Access-Control-Allow-Origin', '*')
            super().end_headers()
        def log_message(self, format, *args):
            logger.info(f"HTTP: {self.address_string()} - {format % args}")

    server = HTTPServer((WEB_SERVER_HOST, WEB_SERVER_PORT), CORSRequestHandler)
    logger.info(f"📁 HTTP 文件服务器已启动，提供文件服务: {OUTPUT_DIR}")
    logger.info(f"🌐 访问地址: http://{WEB_SERVER_HOST}:{WEB_SERVER_PORT}/")
    logger.info(f"📄 播放列表地址: http://{WEB_SERVER_HOST}:{WEB_SERVER_PORT}/tv.m3u")
    server.serve_forever()

if __name__ == "__main__":
    start_file_server()
