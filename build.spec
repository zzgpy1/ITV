# build.spec
# PyInstaller 打包配置文件

import sys
from pathlib import Path

# 确保 resources 目录存在
Path('resources').mkdir(exist_ok=True)

block_cipher = None

# 检查图标文件是否存在
icon_path = Path('resources/icon.ico')
if icon_path.exists():
    icon_file = str(icon_path)
else:
    icon_file = None

a = Analysis(
    ['src/main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('alias.txt', '.'),
        ('blacklist.txt', '.'),
        ('demo.txt', '.'),
        ('resources', 'resources'),
    ],
    hiddenimports=[
        # 核心模块
        'src.config',
        'src.run',
        'src.fetcher',
        'src.parser',
        'src.speed_tester',
        'src.ffmpeg_validator',
        'src.merger',
        'src.generator',
        'src.demo_filter',
        'src.classifier',
        'src.blacklist_filter',
        'src.database',
        'src.logger',
        'src.alias_matcher',
        'src.fixed_sources',
        # 自治模式模块
        'src.stable',
        'src.stable.manager',
        'src.source_pool',
        'src.source_pool.discoverer',
        'src.candidate',
        'src.candidate.observer',
        'src.quality',
        'src.quality.monitor',
        'src.orchestrator',
        # 扩展功能
        'src.iptv_org_adapter',
        'src.global_channels',
        'src.generator_enhanced',
        'src.overseas_filter',
        'src.special_categories',
        # GUI 模块
        'src.gui',
        'src.gui.main_window',
        'src.gui.widgets',
        'src.gui.styles',
        # 工具模块
        'src.utils',
        'src.utils.logger_handler',
        # 第三方库
        'pypinyin',
        'pypinyin.core',
        'pypinyin.style',
        'aiohttp',
        'aiosqlite',
        'tqdm',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyd = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyd,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='IPTV_Manager',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon_file if (sys.platform == 'win32' and icon_file) else None,
)
