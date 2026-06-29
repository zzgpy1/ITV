# src/web/api.py
"""Web 管理界面 REST API"""

import json
import logging
import queue
import threading
import time
import asyncio
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


# ========== 采集任务管理 ==========
collector_status = {
    "running": False,
    "log": [],
    "start_time": None,
    "end_time": None,
    "result": None
}
log_queue = queue.Queue()


class QueueHandler(logging.Handler):
    """将日志消息放入队列"""
    def emit(self, record):
        log_queue.put(self.format(record))


def collector_worker():
    """在后台线程中运行采集任务"""
    global collector_status
    collector_status["running"] = True
    collector_status["start_time"] = time.time()
    collector_status["log"] = []
    collector_status["result"] = None

    # 配置日志重定向
    root_logger = logging.getLogger()
    queue_handler = QueueHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    queue_handler.setFormatter(formatter)
    root_logger.addHandler(queue_handler)

    try:
        # 导入并运行采集主函数
        from src.run import main as run_collector
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(run_collector())
        collector_status["result"] = "success" if result == 0 else "failed"
    except Exception as e:
        collector_status["result"] = f"error: {str(e)}"
        # 将异常信息也写入日志
        log_queue.put(f"❌ 采集异常: {e}")
    finally:
        collector_status["running"] = False
        collector_status["end_time"] = time.time()
        root_logger.removeHandler(queue_handler)


@api_bp.route('/collect/start', methods=['POST'])
def start_collection():
    """启动采集任务"""
    if collector_status["running"]:
        return jsonify({"success": False, "message": "采集任务正在运行中，请稍候"})

    thread = threading.Thread(target=collector_worker, daemon=True)
    thread.start()
    return jsonify({"success": True, "message": "采集任务已启动，请查看日志"})


@api_bp.route('/collect/status', methods=['GET'])
def get_collector_status():
    """获取采集任务状态和最新日志"""
    # 从队列中取出所有日志
    logs = []
    while not log_queue.empty():
        try:
            logs.append(log_queue.get_nowait())
        except queue.Empty:
            break
    # 保留最近200条
    collector_status["log"] = (collector_status["log"] + logs)[-200:]

    return jsonify({
        "running": collector_status["running"],
        "log": collector_status["log"],
        "start_time": collector_status["start_time"],
        "end_time": collector_status["end_time"],
        "result": collector_status["result"]
    })


# ========== 原有 API ==========
def get_channel_category(name: str) -> str:
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
    fixed = {name: src.url for name, src in stable_mgr.stable_sources.items() if src.is_fixed}
    return jsonify(fixed)


@api_bp.route('/fixed_sources', methods=['POST'])
def add_fixed_source():
    data = request.get_json()
    name = data.get('name')
    url = data.get('url')
    if not name or not url:
        return jsonify({'error': '缺少频道名或URL'}), 400
    stable_mgr = StableManager()
    if stable_mgr.set_fixed_source(name, url):
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
    env_path = Path('.env')
    if env_path.exists():
        with open(env_path, 'r') as f:
            lines = f.readlines()
    else:
        lines = []
    key_map = {
        'max_workers': 'MAX_WORKERS',
        'timeout': 'TIMEOUT',
        'ffmpeg_enable': 'FFMPEG_ENABLE',
        'max_sources_per_channel': 'MAX_SOURCES_PER_CHANNEL',
        'demo_match_mode': 'DEMO_MATCH_MODE',
    }
    new_lines = []
    updated_keys = set()
    for line in lines:
        line_stripped = line.strip()
        if line_stripped and not line_stripped.startswith('#'):
            key = line_stripped.split('=')[0].strip()
            if key in key_map.values():
                updated_keys.add(key)
                new_value = data.get(key_map[key], None)
                if new_value is not None:
                    new_lines.append(f"{key}={new_value}\n")
                    continue
        new_lines.append(line)
    for k, env_key in key_map.items():
        if env_key not in updated_keys and data.get(k) is not None:
            new_lines.append(f"{env_key}={data[k]}\n")
    with open(env_path, 'w') as f:
        f.writelines(new_lines)
    return jsonify({'success': True, 'message': '配置已更新，请重启服务生效。'})


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

@api_bp.route('/collection/progress')
def get_progress():
    """返回当前采集进度（需在 run.py 中实时更新）"""
    from src.run import progress
    return jsonify(progress)

@api_bp.route('/health/predict/<channel_name>')
async def predict(channel_name):
    # 获取该频道最新源的 channel_key
    stable = StableManager()
    if channel_name in stable.stable_sources:
        src = stable.stable_sources[channel_name]
        key = channel_key(channel_name, src.url)
        db = await get_db_cache()
        prob = await orchestrator.predict_failure_probability(key)
        return jsonify({'channel': channel_name, 'probability': prob})
    return jsonify({'error': '频道不存在'}), 404

# 获取固定源列表（包含 auto_optimize）
@api_bp.route('/fixed_sources', methods=['GET'])
def get_fixed_sources():
    stable_mgr = StableManager()
    fixed = {}
    for name, src in stable_mgr.stable_sources.items():
        if src.is_fixed:
            fixed[name] = {
                'url': src.url,
                'auto_optimize': src.auto_optimize
            }
    return jsonify(fixed)

# 添加固定源（支持 auto_optimize）
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

# 切换固定源的自动优化开关
@api_bp.route('/fixed_sources/<name>/auto_optimize', methods=['PUT'])
def toggle_auto_optimize(name):
    data = request.get_json()
    enabled = data.get('enabled', False)
    stable_mgr = StableManager()
    if stable_mgr.set_auto_optimize(name, enabled):
        return jsonify({'success': True, 'message': f'{name} 自动优化已切换至 {enabled}'})
    else:
        return jsonify({'error': '更新失败'}), 400
