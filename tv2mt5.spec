# tv2mt5.spec
# PyInstaller one-folder build for TV2MT5 Desktop. Build: pyinstaller --noconfirm tv2mt5.spec
from PyInstaller.utils.hooks import collect_all, collect_submodules

block_cipher = None

datas = [
    ('app/ui', 'app/ui'),                                  # html/js/css/img + tv2mt5.ico
    ('data/instruments.json', 'data'),                     # seed default
    # NOTE: symbol_mappings is intentionally NOT bundled — SymbolMapper self-
    # initialises from MT5 when absent (get_data_file with no seed_name). Seeding
    # a static template would suppress that and bake in a wrong broker suffix.
]
binaries = []
hiddenimports = [
    'pystray._win32',
    'win32timezone',
    'MetaTrader5',
]

# mitmproxy loads addons/protocols lazily; pywebview ships JS bridge data files.
# Collect everything for both so nothing is missed at runtime.
for pkg in ('mitmproxy', 'webview'):
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h

hiddenimports += collect_submodules('uvicorn')

a = Analysis(
    ['tv2mt5.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib'],
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='TV2MT5',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,                     # windowed: no console for end users
    icon='app/ui/img/tv2mt5.ico',
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name='TV2MT5',
)
