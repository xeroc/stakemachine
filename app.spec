# -*- mode: python -*-

import os
import sys
block_cipher = None

hiddenimports_strategies = [
    'dexbot',
    'dexbot.strategies',
    'dexbot.strategies.echo',
    'dexbot.strategies.relative_orders',
    'dexbot.strategies.storagedemo',
    'dexbot.strategies.walls',
]

hiddenimports_packaging = [
    'packaging', 'packaging.version', 'packaging.specifiers', 'packaging.requirements'
]

a = Analysis(['app.py'],
             binaries=[],
             datas=[],
             hiddenimports=hiddenimports_packaging + hiddenimports_strategies,
             hookspath=['hooks'],
             runtime_hooks=['hooks/rthook-Crypto.py'],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher)

pyz = PYZ(a.pure, a.zipped_data,
          cipher=block_cipher)

a.binaries = [b for b in a.binaries if "libdrm.so.2" not in b[0]]

exe = EXE(pyz,
          a.scripts,
          a.binaries,
          a.zipfiles,
          a.datas,
          name=os.path.join('dist', 'DEXBot-gui' + ('.exe' if sys.platform == 'win32' else '')),
          debug=True,
          strip=False,
          icon=None,
          upx=True,
          runtime_tmpdir=None,
          console=True)

if sys.platform == 'darwin':
   app = BUNDLE(exe,
                name='DEXBot-gui.app',
                icon=None)

