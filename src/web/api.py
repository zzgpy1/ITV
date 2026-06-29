# src/web/api.py
"""Web 管理界面 REST API"""

import json
import subprocess
import sys
import os
from pathlib import Path
from flask import Blueprint, request, jsonify
from src.config import (
    OUTPUT_DIR, MAX_WORKERS, TIMEOUT, FFMPEG_ENABLE,
    MAX_SOURCES_PER_CHANNEL, DEMO_MATCH_MODE,
    CACHE_RAW_HOURS, CACHE_SPEED_HOURS
)
from src.stable.manager import StableManager
from src.source_pool.discoverer import SourceDiscoverer
from src.candidate.observer import CandidateObserver
from src.web.db import get_quality_history, get_all_channels_with_history, record_quality

api_bp = Blueprint('api', __name__, url_prefix='/api')


def get_channel_category(name: str) -> str:
    """根据频道名判断分类"""
    if name.startswith('CCTV') or '央视' in name:
        return '央视'
    if '卫视' in name:
        return '卫视'
    if any(kw in name for kw in ['港', '澳', '台', '凤凰', '翡翠', '明珠', 'TVB', '东森', '民视', '台视', '华视', '中视', '三立', '纬来']):
        return '港澳台'
    if '频道' in name:
        return '地方'
    return '其他'


@api_bp.route('/status')
def get_status():
    stable_mgr = StableManager()
    stable_sources = stable_mgr.get_active_sources()
    discoverer = SourceDiscoverer()
    pool_stats = discoverer.get_statistics()
    observer = CandidateObserver()
    candidate_stats = observer.get_statistics()
    stats_file = OUTPUT_DIR / "stats.json"
    last_run = None
    if stats_file.exists():
        with open(stats_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            last_run = data.get('timestamp')
    return jsonify({
        'stable_count': len(stable_sources),
        'fixed_count': sum(1 for s in stable_sources.values() if s.is_fixed),
        'pool_total': pool_stats.get('total', 0),
        'candidate_observing': candidate_stats.get('observing', 0),
        'last_run': last_run,
        'status': 'running'
    })


@api_bp.route('/channels')
def get_channels():
    search = request.args.get('search', '').strip().lower()
    category = request.args.get('category', '')
    stable_mgr = StableManager()
    sources = stable_mgr.get_active_sources()
    channels = []
    for name, src in sources.items():
        if not src.url:
            continue
        if search and search not in name.lower():
            continue
        cat = get_channel_category(name)
        if category and cat != category:
            continue
        channels.append({
            'name': name,
            'url': src.url,
            'latency': src.latency,
            'codec': src.video_codec,
            'is_fixed': src.is_fixed,
            'category': cat,
            'last_verified': src.last_verified.isoformat() if src.last_verified else None
        })
    channels.sort(key=lambda x: x['name'])
    return jsonify(channels)


@api_bp.route('/fixed_sources', methods=['GET'])
def get_fixed_sources():
    stable_mgr = StableManager()
    # 返回格式：{ 'name': {'url': '...', 'auto_optimize': True/False} }
    fixed = {name: {'url': src.url, 'auto_optimize': getattr(src, 'auto_optimize', False)} 
             for name, src in stable_mgr.stable_sources.items() if src.is_fixed}
    return jsonify(fixed)


@api_bp.route('/fixed_sources', methods=['POST'])
def add_fixed_source():
    data = request.get_json()
    name = data.get('name')
    url = data.get('url')
    auto_optimize = data.get('auto_optimize', False)
    if not name or not url:
        return jsonify({'error': '缺少频道名或URL'}), 400
    stable_mgr = StableManager()
    if stable_mgr.set_fixed_source(name, url, auto_optimize):
        return jsonify({'success': True, 'message': f'已添加固定源 {name}'})
    else:
        return jsonify({'error': '添加失败'}), 500


@api_bp.route('/fixed_sources/<name>', methods=['DELETE'])
def delete_fixed_source(name):
    stable_mgr = StableManager()
    if name in stable_mgr.stable_sources and stable_mgr.stable_sources[name].is_fixed:
        stable_mgr.stable_sources[name].is_fixed = False
        stable_mgr.stable_sources[name].status = 'active'
        stable_mgr._save()
        return jsonify({'success': True, 'message': f'已移除固定源 {name}'})
    return jsonify({'error': '固定源不存在'}), 404


@api_bp.route('/fixed_sources/<name>/optimize', methods=['PUT'])
def update_fixed_optimize(name):
    data = request.get_json()
    auto_optimize = data.get('auto_optimize', False)
    stable_mgr = StableManager()
    if name in stable_mgr.stable_sources and stable_mgr.stable_sources[name].is_fixed:
        stable_mgr.stable_sources[name].auto_optimize = auto_optimize
        stable_mgr._save()
        return jsonify({'success': True, 'message': f'已更新 {name} 的自动优化状态'})
    return jsonify({'error': '固定源不存在'}), 404


@api_bp.route('/config', methods=['GET'])
def get_config():
    return jsonify({
        'max_workers': MAX_WORKERS,
        'timeout': TIMEOUT,
        'ffmpeg_enable': FFMPEG_ENABLE,
        'max_sources_per_channel': MAX_SOURCES_PER_CHANNEL,
        'demo_match_mode': DEMO_MATCH_MODE,
        'cache_raw_hours': CACHE_RAW_HOURS,
        'cache_speed_hours': CACHE_SPEED_HOURS,
    })


@api_bp.route('/config', methods=['POST'])
def update_config():
    data = request.get_json()
    from src.config_manager import ConfigManager
    cm = ConfigManager()
    for key, value in data.items():
        cm.set(key.upper(), value)
    return jsonify({'success': True, 'message': '配置已更新，无需重启生效。'})


@api_bp.route('/config/reload', methods=['POST'])
def reload_config():
    from src.config_manager import ConfigManager
    ConfigManager().reload()
    return jsonify({'success': True, 'message': '配置已重新加载'})


@api_bp.route('/collection/start', methods=['POST'])
def start_collection():
    """启动采集任务（子进程）"""
    # 检查是否已有任务在运行（通过 pid 文件，这里简化）
    pid_file = Path('/tmp/iptv_collector.pid')
    if pid_file.exists():
        try:
            with open(pid_file, 'r') as f:
                old_pid = int(f.read().strip())
            # 检查进程是否存活
            if os.path.exists(f'/proc/{old_pid}'):
                return jsonify({'success': False, 'error': '采集任务已在运行中'}), 409
        except:
            pass
    try:
        python_path = sys.executable
        run_script = os.path.join(os.path.dirname(__file__), '..', 'run.py')
        env = os.environ.copy()
        env['COLLECTION_MODE'] = 'subprocess'
        proc = subprocess.Popen([python_path, run_script], env=env)
        with open(pid_file, 'w') as f:
            f.write(str(proc.pid))
        return jsonify({'success': True, 'pid': proc.pid, 'message': '采集任务已启动'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/collection/progress')
def get_progress():
    """返回当前采集进度"""
    try:
        from src.run import progress
        return jsonify(progress)
    except ImportError:
        return jsonify({'percent': 0, 'current': 0, 'total': 0, 'valid': 0, 'invalid': 0, 'finished': False, 'phase': 'idle'})


@api_bp.route('/logs')
def get_logs():
    """返回最近日志"""
    log_file = OUTPUT_DIR / 'run.log'
    if not log_file.exists():
        return jsonify({'logs': '暂无日志'})
    lines = request.args.get('lines', 500, type=int)
    with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
        all_lines = f.readlines()
        last_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines
    return jsonify({'logs': ''.join(last_lines)})


@api_bp.route('/quality/<channel_name>')
def get_quality(channel_name):
    days = request.args.get('days', 7, type=int)
    history = get_quality_history(channel_name, days)
    return jsonify(history)


@api_bp.route('/quality/all')
def get_all_quality():
    days = request.args.get('days', 7, type=int)
    data = get_all_channels_with_history(days)
    return jsonify(data)
