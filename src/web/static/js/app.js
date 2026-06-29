// src/web/static/js/app.js
// IPTV 智能管理面板前端逻辑

const API_BASE = '/api';
let qualityChartInstance = null;
let progressInterval = null;

// ========== 页面导航 ==========
document.addEventListener('DOMContentLoaded', function() {
    document.querySelectorAll('.nav-link[data-page]').forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            document.querySelectorAll('.nav-link').forEach(l => l.classList.remove('active'));
            this.classList.add('active');
            loadPage(this.dataset.page);
        });
    });
    document.getElementById('refresh-btn').addEventListener('click', function() {
        const active = document.querySelector('.nav-link.active');
        if (active) loadPage(active.dataset.page);
    });
    loadPage('dashboard');
});

async function loadPage(page) {
    const content = document.getElementById('page-content');
    const title = document.getElementById('page-title');
    try {
        switch(page) {
            case 'dashboard': title.textContent = '📊 仪表盘'; await renderDashboard(content); break;
            case 'channels': title.textContent = '📋 频道列表'; await renderChannels(content); break;
            case 'fixed': title.textContent = '📌 固定源管理'; await renderFixed(content); break;
            case 'config': title.textContent = '⚙️ 配置管理'; await renderConfig(content); break;
            case 'quality': title.textContent = '📈 质量趋势'; await renderQuality(content); break;
            default: content.innerHTML = '<div class="alert alert-warning">页面未找到</div>';
        }
    } catch(e) {
        content.innerHTML = `<div class="alert alert-danger">加载失败: ${e.message}</div>`;
        console.error(e);
    }
}

// ===== 仪表盘 =====
async function renderDashboard(container) {
    const resp = await fetch(`${API_BASE}/status`);
    const data = await resp.json();
    container.innerHTML = `
        <div class="row">
            <div class="col-md-3 mb-3"><div class="card"><div class="card-body text-center"><h6 class="text-muted">稳定源</h6><div class="stat-number">${data.stable_count || 0}</div></div></div></div>
            <div class="col-md-3 mb-3"><div class="card"><div class="card-body text-center"><h6 class="text-muted">固定源</h6><div class="stat-number">${data.fixed_count || 0}</div></div></div></div>
            <div class="col-md-3 mb-3"><div class="card"><div class="card-body text-center"><h6 class="text-muted">源池总量</h6><div class="stat-number">${data.pool_total || 0}</div></div></div></div>
            <div class="col-md-3 mb-3"><div class="card"><div class="card-body text-center"><h6 class="text-muted">候选观察中</h6><div class="stat-number">${data.candidate_observing || 0}</div></div></div></div>
        </div>
        <div class="card"><div class="card-header">系统信息</div><div class="card-body"><p><strong>最后运行时间：</strong>${data.last_run || '暂无'}</p><p><strong>系统状态：</strong><span class="badge bg-success">运行中</span></p>
        <button class="btn btn-primary mt-2" id="run-collection-btn"><i class="fas fa-play"></i> 立即运行采集</button>
        </div></div>
        <div class="card"><div class="card-header">采集进度</div><div class="card-body">
            <div class="progress" style="height:25px;">
                <div id="progress-bar" class="progress-bar" role="progressbar" style="width:0%;">0%</div>
            </div>
            <div id="progress-info" class="mt-2 text-muted">就绪</div>
        </div></div>
    `;
    document.getElementById('run-collection-btn').addEventListener('click', startCollection);
    document.getElementById('last-update').textContent = '更新于: ' + new Date().toLocaleString();
    // 自动轮询进度
    startProgressPolling();
}

// ===== 采集控制 =====
async function startCollection() {
    try {
        const resp = await fetch(`${API_BASE}/collection/start`, { method: 'POST' });
        const data = await resp.json();
        if (data.success) {
            alert('采集任务已启动，请查看进度');
        } else {
            alert('启动失败: ' + data.error);
        }
    } catch(e) {
        alert('请求失败: ' + e.message);
    }
}

function startProgressPolling() {
    if (progressInterval) clearInterval(progressInterval);
    progressInterval = setInterval(async function() {
        try {
            const resp = await fetch(`${API_BASE}/collection/progress`);
            const data = await resp.json();
            const bar = document.getElementById('progress-bar');
            const info = document.getElementById('progress-info');
            if (bar) {
                bar.style.width = data.percent + '%';
                bar.textContent = data.percent + '%';
            }
            if (info) {
                info.textContent = `阶段: ${data.phase} | 已处理 ${data.current}/${data.total}，有效 ${data.valid}，无效 ${data.invalid}`;
            }
            if (data.finished) {
                clearInterval(progressInterval);
                // 刷新仪表盘数据
                setTimeout(() => loadPage('dashboard'), 1000);
            }
        } catch(e) {}
    }, 2000);
}

// ===== 频道列表 =====
async function renderChannels(container) {
    container.innerHTML = `
        <div class="row mb-3">
            <div class="col-md-4"><input type="text" class="form-control" id="search-input" placeholder="搜索频道..."></div>
            <div class="col-md-3">
                <select class="form-select" id="category-filter">
                    <option value="">全部分类</option>
                    <option value="央视">央视</option>
                    <option value="卫视">卫视</option>
                    <option value="地方">地方</option>
                    <option value="港澳台">港澳台</option>
                    <option value="其他">其他</option>
                </select>
            </div>
            <div class="col-md-2"><button class="btn btn-primary" id="apply-filter-btn">筛选</button></div>
        </div>
        <div class="table-responsive">
            <table class="table table-hover" id="channel-table">
                <thead><tr><th>频道名</th><th>分类</th><th>延迟(ms)</th><th>编码</th><th>固定</th><th>操作</th></tr></thead>
                <tbody id="channel-tbody"><tr><td colspan="6" class="text-center">加载中...</td></tr></tbody>
            </table>
        </div>
    `;
    document.getElementById('apply-filter-btn').addEventListener('click', loadChannels);
    document.getElementById('search-input').addEventListener('keyup', e => { if(e.key === 'Enter') loadChannels(); });
    await loadChannels();

    async function loadChannels() {
        const search = document.getElementById('search-input').value.trim();
        const category = document.getElementById('category-filter').value;
        let url = `${API_BASE}/channels?`;
        if(search) url += `search=${encodeURIComponent(search)}&`;
        if(category) url += `category=${encodeURIComponent(category)}&`;
        try {
            const resp = await fetch(url);
            const channels = await resp.json();
            const tbody = document.getElementById('channel-tbody');
            if(!channels.length) {
                tbody.innerHTML = '<tr><td colspan="6" class="text-center">暂无频道</td></tr>';
                return;
            }
            tbody.innerHTML = channels.map(ch => `
                <tr>
                    <td><strong>${ch.name}</strong></td>
                    <td><span class="badge bg-secondary">${ch.category || '其他'}</span></td>
                    <td>${ch.latency || '--'}</td>
                    <td>${ch.codec || '--'}</td>
                    <td>${ch.is_fixed ? '<span class="badge-fixed">固定</span>' : '<span class="badge-normal">普通</span>'}</td>
                    <td>
                        <button class="btn btn-sm btn-outline-info view-quality" data-name="${ch.name}">
                            <i class="fas fa-chart-line"></i>
                        </button>
                    </td>
                </tr>
            `).join('');
            document.querySelectorAll('.view-quality').forEach(btn => {
                btn.addEventListener('click', function() {
                    const name = this.dataset.name;
                    document.querySelector('.nav-link[data-page="quality"]').click();
                    setTimeout(() => {
                        const input = document.getElementById('quality-channel-input');
                        if(input) {
                            input.value = name;
                            document.getElementById('quality-search-btn').click();
                        }
                    }, 300);
                });
            });
        } catch(e) {
            console.error(e);
        }
    }
}

// ===== 固定源管理（含自动优化开关） =====
async function renderFixed(container) {
    container.innerHTML = `
        <div class="row mb-3">
            <div class="col-md-8">
                <h5>添加固定源</h5>
                <div class="input-group mb-2">
                    <input type="text" class="form-control" id="fixed-name" placeholder="频道名 (如 CCTV-1)">
                    <input type="text" class="form-control" id="fixed-url" placeholder="URL">
                    <button class="btn btn-primary" id="add-fixed-btn">添加</button>
                </div>
                <div class="form-check form-switch">
                    <input class="form-check-input" type="checkbox" id="fixed-auto-optimize">
                    <label class="form-check-label" for="fixed-auto-optimize">允许自动优化（当质量下降时自动替换）</label>
                </div>
                <div id="fixed-message" class="mt-2"></div>
            </div>
        </div>
        <div class="table-responsive">
            <table class="table table-hover" id="fixed-table">
                <thead><tr><th>频道名</th><th>URL</th><th>自动优化</th><th>操作</th></tr></thead>
                <tbody id="fixed-tbody"><tr><td colspan="4" class="text-center">加载中...</td></tr></tbody>
            </table>
        </div>
    `;
    // 添加固定源
    document.getElementById('add-fixed-btn').addEventListener('click', async function() {
        const name = document.getElementById('fixed-name').value.trim();
        const url = document.getElementById('fixed-url').value.trim();
        const auto_optimize = document.getElementById('fixed-auto-optimize').checked;
        if(!name || !url) {
            document.getElementById('fixed-message').innerHTML = '<div class="alert alert-warning">请填写完整信息</div>';
            return;
        }
        try {
            const resp = await fetch(`${API_BASE}/fixed_sources`, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({name, url, auto_optimize})
            });
            const data = await resp.json();
            if(data.success) {
                document.getElementById('fixed-message').innerHTML = `<div class="alert alert-success">${data.message}</div>`;
                document.getElementById('fixed-name').value = '';
                document.getElementById('fixed-url').value = '';
                document.getElementById('fixed-auto-optimize').checked = false;
                loadFixedList();
            } else {
                document.getElementById('fixed-message').innerHTML = `<div class="alert alert-danger">${data.error}</div>`;
            }
        } catch(e) {
            document.getElementById('fixed-message').innerHTML = '<div class="alert alert-danger">添加失败</div>';
        }
    });
    await loadFixedList();

    async function loadFixedList() {
        try {
            const resp = await fetch(`${API_BASE}/fixed_sources`);
            const data = await resp.json();
            const tbody = document.getElementById('fixed-tbody');
            let entries = Object.entries(data);
            if (entries.length && typeof entries[0][1] === 'string') {
                const newData = {};
                for (const [name, url] of entries) {
                    newData[name] = { url, auto_optimize: false };
                }
                entries = Object.entries(newData);
            }
            if(!entries.length) {
                tbody.innerHTML = '<tr><td colspan="4" class="text-center">暂无固定源</td></tr>';
                return;
            }
            tbody.innerHTML = entries.map(([name, info]) => {
                const url = typeof info === 'string' ? info : info.url;
                const autoOpt = typeof info === 'string' ? false : !!info.auto_optimize;
                return `
                <tr>
                    <td><strong>${name}</strong></td>
                    <td><code>${url}</code></td>
                    <td>
                        <div class="form-check form-switch">
                            <input class="form-check-input toggle-optimize" type="checkbox" data-name="${name}" ${autoOpt ? 'checked' : ''}>
                        </div>
                    </td>
                    <td>
                        <button class="btn btn-sm btn-danger delete-fixed" data-name="${name}">
                            <i class="fas fa-trash-alt"></i>
                        </button>
                    </td>
                </tr>
            `}).join('');

            document.querySelectorAll('.toggle-optimize').forEach(cb => {
                cb.addEventListener('change', async function() {
                    const name = this.dataset.name;
                    const auto_optimize = this.checked;
                    try {
                        const resp = await fetch(`${API_BASE}/fixed_sources/${encodeURIComponent(name)}/optimize`, {
                            method: 'PUT',
                            headers: {'Content-Type': 'application/json'},
                            body: JSON.stringify({auto_optimize})
                        });
                        const data = await resp.json();
                        if(data.success) {
                            document.getElementById('fixed-message').innerHTML = `<div class="alert alert-success">${data.message}</div>`;
                        } else {
                            this.checked = !auto_optimize;
                            document.getElementById('fixed-message').innerHTML = `<div class="alert alert-danger">${data.error}</div>`;
                        }
                    } catch(e) {
                        this.checked = !auto_optimize;
                        document.getElementById('fixed-message').innerHTML = '<div class="alert alert-danger">更新失败</div>';
                    }
                });
            });

            document.querySelectorAll('.delete-fixed').forEach(btn => {
                btn.addEventListener('click', async function() {
                    const name = this.dataset.name;
                    if(!confirm(`确定移除固定源 ${name} 吗？`)) return;
                    try {
                        const resp = await fetch(`${API_BASE}/fixed_sources/${encodeURIComponent(name)}`, {method: 'DELETE'});
                        const data = await resp.json();
                        if(data.success) {
                            loadFixedList();
                            document.getElementById('fixed-message').innerHTML = `<div class="alert alert-success">${data.message}</div>`;
                        } else {
                            alert(data.error || '删除失败');
                        }
                    } catch(e) {
                        alert('删除失败');
                    }
                });
            });
        } catch(e) {
            console.error('加载固定源失败', e);
        }
    }
}

// ===== 配置管理 =====
async function renderConfig(container) {
    container.innerHTML = `
        <div class="card">
            <div class="card-header">系统配置</div>
            <div class="card-body">
                <form id="config-form">
                    <div class="row mb-3">
                        <div class="col-md-6">
                            <label class="form-label">最大并发数</label>
                            <input type="number" class="form-control" id="cfg-max-workers" name="max_workers">
                        </div>
                        <div class="col-md-6">
                            <label class="form-label">超时时间 (秒)</label>
                            <input type="number" class="form-control" id="cfg-timeout" name="timeout">
                        </div>
                    </div>
                    <div class="row mb-3">
                        <div class="col-md-6">
                            <label class="form-label">每个频道保留源数</label>
                            <input type="number" class="form-control" id="cfg-max-sources" name="max_sources_per_channel">
                        </div>
                        <div class="col-md-6">
                            <label class="form-label">Demo匹配模式</label>
                            <select class="form-select" id="cfg-demo-mode" name="demo_match_mode">
                                <option value="contains">包含</option>
                                <option value="exact">精确</option>
                            </select>
                        </div>
                    </div>
                    <div class="mb-3">
                        <div class="form-check form-switch">
                            <input class="form-check-input" type="checkbox" id="cfg-ffmpeg" name="ffmpeg_enable">
                            <label class="form-check-label">启用 ffmpeg 深度验证</label>
                        </div>
                    </div>
                    <button type="submit" class="btn btn-primary">保存配置</button>
                    <button type="button" class="btn btn-secondary" id="reload-config-btn">重新加载配置</button>
                    <div id="config-message" class="mt-3"></div>
                </form>
            </div>
        </div>
    `;
    // 加载当前配置
    try {
        const resp = await fetch(`${API_BASE}/config`);
        const config = await resp.json();
        document.getElementById('cfg-max-workers').value = config.max_workers || 20;
        document.getElementById('cfg-timeout').value = config.timeout || 8;
        document.getElementById('cfg-max-sources').value = config.max_sources_per_channel || 3;
        document.getElementById('cfg-demo-mode').value = config.demo_match_mode || 'contains';
        document.getElementById('cfg-ffmpeg').checked = config.ffmpeg_enable || false;
    } catch(e) { console.error('加载配置失败', e); }
    // 提交表单
    document.getElementById('config-form').addEventListener('submit', async function(e) {
        e.preventDefault();
        const data = {
            max_workers: parseInt(document.getElementById('cfg-max-workers').value),
            timeout: parseInt(document.getElementById('cfg-timeout').value),
            max_sources_per_channel: parseInt(document.getElementById('cfg-max-sources').value),
            demo_match_mode: document.getElementById('cfg-demo-mode').value,
            ffmpeg_enable: document.getElementById('cfg-ffmpeg').checked,
        };
        try {
            const resp = await fetch(`${API_BASE}/config`, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(data)
            });
            const result = await resp.json();
            document.getElementById('config-message').innerHTML = 
                `<div class="alert alert-${result.success ? 'success' : 'danger'}">${result.message}</div>`;
        } catch(e) {
            document.getElementById('config-message').innerHTML = '<div class="alert alert-danger">保存失败</div>';
        }
    });
    document.getElementById('reload-config-btn').addEventListener('click', async function() {
        try {
            const resp = await fetch(`${API_BASE}/config/reload`, { method: 'POST' });
            const result = await resp.json();
            document.getElementById('config-message').innerHTML = `<div class="alert alert-success">${result.message}</div>`;
        } catch(e) {
            document.getElementById('config-message').innerHTML = '<div class="alert alert-danger">重新加载失败</div>';
        }
    });
}

// ===== 质量趋势 =====
async function renderQuality(container) {
    container.innerHTML = `
        <div class="row mb-3">
            <div class="col-md-4">
                <input type="text" class="form-control" id="quality-channel-input" placeholder="输入频道名">
            </div>
            <div class="col-md-2">
                <button class="btn btn-primary" id="quality-search-btn">查看趋势</button>
            </div>
            <div class="col-md-3">
                <select class="form-select" id="quality-days">
                    <option value="7">最近7天</option>
                    <option value="14">最近14天</option>
                    <option value="30">最近30天</option>
                </select>
            </div>
        </div>
        <div class="card">
            <div class="card-header" id="quality-chart-title">请选择频道查看延迟趋势</div>
            <div class="card-body">
                <canvas id="quality-chart" height="250"></canvas>
            </div>
        </div>
    `;
    document.getElementById('quality-search-btn').addEventListener('click', loadQuality);
    document.getElementById('quality-channel-input').addEventListener('keyup', e => { if(e.key === 'Enter') loadQuality(); });

    async function loadQuality() {
        const name = document.getElementById('quality-channel-input').value.trim();
        if(!name) return;
        const days = document.getElementById('quality-days').value;
        try {
            const resp = await fetch(`${API_BASE}/quality/${encodeURIComponent(name)}?days=${days}`);
            const data = await resp.json();
            if(!data || !data.length) {
                document.getElementById('quality-chart-title').textContent = `"${name}" 暂无质量数据`;
                if(qualityChartInstance) { qualityChartInstance.destroy(); qualityChartInstance = null; }
                return;
            }
            document.getElementById('quality-chart-title').textContent = `"${name}" 延迟趋势 (最近${days}天)`;
            const labels = data.map(d => new Date(d.timestamp).toLocaleString());
            const latencies = data.map(d => d.latency || 0);
            const ctx = document.getElementById('quality-chart').getContext('2d');
            if(qualityChartInstance) qualityChartInstance.destroy();
            qualityChartInstance = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: labels,
                    datasets: [{
                        label: '延迟 (ms)',
                        data: latencies,
                        borderColor: 'rgb(13, 110, 253)',
                        backgroundColor: 'rgba(13, 110, 253, 0.1)',
                        tension: 0.2,
                        pointBackgroundColor: data.map(d => d.success ? 'green' : 'red'),
                        pointRadius: 3,
                    }]
                },
                options: {
                    responsive: true,
                    plugins: {
                        legend: { labels: { color: '#e9ecef' } },
                        tooltip: {
                            callbacks: {
                                afterBody: function(tooltipItems) {
                                    const idx = tooltipItems[0].dataIndex;
                                    return '状态: ' + (data[idx].success ? '✅ 成功' : '❌ 失败');
                                }
                            }
                        }
                    },
                    scales: {
                        y: { beginAtZero: true, grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: '#adb5bd' } },
                        x: { grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: '#adb5bd', maxTicksLimit: 15 } }
                    }
                }
            });
        } catch(e) {
            alert('查询失败: ' + e.message);
        }
    }
}
