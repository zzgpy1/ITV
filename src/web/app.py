# src/web/app.py
"""Flask 应用工厂"""

import os
from pathlib import Path
from flask import Flask, send_from_directory
from flask_cors import CORS
from src.web.api import api_bp
from src.config import WEB_SERVER_HOST, WEB_SERVER_PORT, OUTPUT_DIR

def create_app():
    app = Flask(__name__, 
                template_folder='templates',
                static_folder='static')
    app.config['SECRET_KEY'] = os.urandom(24)
    app.config['TEMPLATES_AUTO_RELOAD'] = True
    app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
    CORS(app)
    
    app.register_blueprint(api_bp)
    
    # 原有文件路由（保留）
    @app.route('/files/<path:filename>')
    def serve_output(filename):
        return send_from_directory(OUTPUT_DIR, filename)
    
    # 新增：支持 /output/tv.txt 这样的路径
    @app.route('/output/<path:filename>')
    def serve_output_direct(filename):
        return send_from_directory(OUTPUT_DIR, filename)
    
    @app.route('/')
    def index():
        return send_from_directory(app.template_folder, 'index.html')
    
    return app

def run_server():
    app = create_app()
    print(f"🌐 Web 管理界面启动: http://{WEB_SERVER_HOST}:{WEB_SERVER_PORT}")
    app.run(host=WEB_SERVER_HOST, port=WEB_SERVER_PORT, debug=False, threaded=True)
