# Build with: pyinstaller packaging/pyinstaller/marpme.spec
import os

from PyInstaller.utils.hooks import collect_all, copy_metadata

project_root = os.path.abspath(os.path.join(SPECPATH, "..", ".."))
copier_data, copier_binaries, copier_hidden = collect_all("copier")
questionary_data, questionary_binaries, questionary_hidden = collect_all("questionary")
ansible_data, ansible_binaries, ansible_hidden = collect_all("jinja2_ansible_filters")
marpme_metadata = copy_metadata("marpme")

a = Analysis(
    [os.path.join(project_root, "src", "marpme", "__main__.py")],
    pathex=[os.path.join(project_root, "src")],
    binaries=copier_binaries + questionary_binaries + ansible_binaries,
    datas=copier_data + questionary_data + ansible_data + marpme_metadata,
    hiddenimports=copier_hidden + questionary_hidden + ansible_hidden,
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="marpme",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
)
