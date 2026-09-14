"""Bundle tkinterdnd2's native TkDND libraries with SnowRelay."""

from PyInstaller.utils.hooks import collect_data_files


datas = collect_data_files("tkinterdnd2")
