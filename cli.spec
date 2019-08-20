# -*- mode: python -*-

import os
import sys
block_cipher = None

hiddenimports_strategies = [
    'dexbot',
    'dexbot.strategies',
    'dexbot.strategies.echo',
    'dexbot.strategies.relative_orders',
    'dexbot.strategies.staggered_orders',
    'dexbot.strategies.king_of_the_hill',
    'dexbot.strategies.storagedemo',
    'dexbot.strategies.walls',
]

hiddenimports_packaging = [
    'packaging',
    'packaging.version',
    'packaging.specifiers',
    'packaging.requirements',
]

# We're not importing migrations anywhere, so we need to package them as data files
data_files = [
    ('dexbot/migrations', 'migrations')
]

a = Analysis(['dexbot/cli.py'],
             binaries=[],
             datas=data_files,
             hiddenimports=hiddenimports_packaging + hiddenimports_strategies,
             hookspath=['hooks'],
             runtime_hooks=['hooks/rthook-Crypto.py'],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher)

pyz = PYZ(a.pure, a.zipped_data,
          cipher=block_cipher)

exe = EXE(pyz,
          a.scripts,
          a.binaries,
          a.zipfiles,
          a.datas,
          name=os.path.join('dist', 'DEXBot-cli' + ('.exe' if sys.platform == 'win32' else '')),
          debug=True,
          strip=False,
          upx=True,
          runtime_tmpdir=None,
          console=True )
