# tv2mt5.spec
# PyInstaller one-folder build for TV2MT5 Desktop. Build: pyinstaller --noconfirm tv2mt5.spec
import os

from PyInstaller.utils.hooks import collect_all, collect_submodules

block_cipher = None

# Repo root = the directory holding this spec. Pin it on the analysis path so the
# top-level `app` and `src` packages resolve regardless of the build CWD. SPECPATH
# is injected by PyInstaller; fall back to CWD if running the spec some other way.
ROOT = globals().get("SPECPATH") or os.path.abspath(os.getcwd())

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

# Our own packages are imported lazily (delayed) inside tv2mt5.py / the engine, so
# PyInstaller's static analysis can miss them. Collect them explicitly so the
# frozen app always has app.desktop, app.engine, the src.* engine modules, etc.
# Exclude src.scripts: those are dev/CLI utilities (init_db pulls psycopg2 — a
# dependency deliberately cut in Plan 1 — symbol_specifications pulls pandas, etc.)
# and are never run by the frozen app.
hiddenimports += collect_submodules('app')
hiddenimports += [m for m in collect_submodules('src') if not m.startswith('src.scripts')]

a = Analysis(
    ['tv2mt5.py'],
    pathex=[ROOT],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # psycopg2: SQLAlchemy's hook pulls in every DB dialect, but the app uses
    # SQLite only (Postgres was cut in Plan 1) — exclude the unused C extension.
    excludes=['tkinter', 'matplotlib', 'psycopg2', 'psycopg2cffi'],
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
