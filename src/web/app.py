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
    app.config['TEMPLATES_AUTO_RELOAD'] = True   # 禁用模板缓存
    app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0  # 禁用静态文件缓存
    CORS(app)
    
    app.register_blueprint(api_bp)
    
    @app.route('/files/<path:filename>')
    def serve_output(filename):
        return send_from_directory(OUTPUT_DIR, filename)
    
    @app.route('/')
    def index():
        return send_from_directory(app.template_folder, 'index.html')
    
    return app

def run_server():
    app = create_app()
    print(f"🌐 Web 管理界面启动: http://{WEB_SERVER_HOST}:{WEB_SERVER_PORT}")
    app.run(host=WEB_SERVER_HOST, port=WEB_SERVER_PORT, debug=False, threaded=True)
