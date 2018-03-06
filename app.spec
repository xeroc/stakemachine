# -*- mode: python -*-

block_cipher = None


a = Analysis(['app.py'],
             binaries=[],
             datas=[('config.yml', '.')],
             hiddenimports=[],
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
          name='DEXBot',
          debug=False,
          strip=False,
          upx=True,
          runtime_tmpdir=None,
          console=False)
