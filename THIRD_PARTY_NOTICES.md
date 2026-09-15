# SnowRelay 第三方组件声明

SnowRelay 项目自身代码采用 [GPL-3.0-or-later](LICENSE)。第三方组件保持各自的上游许可证。

| 组件 | 用途 | 说明 |
| --- | --- | --- |
| Python / Tcl / Tk | 应用运行时与桌面界面 | 独立 EXE 构建可能包含对应运行库；以构建所用 Python 发行版的许可证为准 |
| pandas | 表格数据整理 | 以安装版本随附的包元数据和许可证文件为准 |
| openpyxl / xlrd | Excel 文件读取与写入 | 以安装版本随附的包元数据和许可证文件为准 |
| tkinterdnd2 | Windows 文件拖放 | 以安装版本随附的包元数据和许可证文件为准 |
| Pillow | 图像和图标处理 | 以安装版本随附的包元数据和许可证文件为准 |
| PyInstaller | Windows EXE 构建 | 以构建工具及其 bootloader 随附许可证为准 |

依赖名称不表示相关权利人对 SnowRelay 的认可。源码分发和 Windows 发布目录应保留项目 `LICENSE` 与本文件。正式构建会根据实际环境生成 `THIRD_PARTY_LICENSES/INDEX.md`，并复制可识别的依赖许可证文件到同一目录。
