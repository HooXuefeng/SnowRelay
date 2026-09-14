from __future__ import annotations

import argparse
import ctypes
import os
import sys
from pathlib import Path

PRODUCT = "SnowRelay"
VERSION = "v0.5.0"


def prepare_tk_runtime() -> None:
    """Initialize Tcl in the order required by affected Windows installs."""
    if os.name != "nt":
        return
    root = Path(getattr(sys, "_MEIPASS", sys.base_prefix))
    frozen = hasattr(sys, "_MEIPASS")
    dll = root / ("tcl86t.dll" if frozen else "DLLs/tcl86t.dll")
    tcl = root / ("_tcl_data" if frozen else "tcl/tcl8.6")
    tk = root / ("_tk_data" if frozen else "tcl/tk8.6")
    if not (dll.is_file() and tcl.is_dir() and tk.is_dir()):
        return
    library = ctypes.CDLL(str(dll))
    library.Tcl_FindExecutable.argtypes = [ctypes.c_char_p]
    library.Tcl_FindExecutable(os.fsencode(sys.executable))
    os.environ["TCL_LIBRARY"] = str(tcl)
    os.environ["TK_LIBRARY"] = str(tk)


def cli():
    parser = argparse.ArgumentParser(description=f"{PRODUCT} - Security Finding Normalization")
    parser.add_argument("inputs", nargs="*", help="CSV/XLS/XLSX 输入文件")
    parser.add_argument("-o", "--output", help="输出 XLSX；默认生成在第一个输入文件旁边")
    parser.add_argument("--rules", default=str(Path(__file__).resolve().parent / "rules"), help="规则目录")
    parser.add_argument("--no-mask", action="store_true", help="导出时不脱敏密码字段")
    parser.add_argument("--snowedge-output", help="同时生成 SnowEdge 联动包（.snowedge.json）")
    parser.add_argument("--gui", action="store_true", help="启动图形界面")
    parser.add_argument("--smoke", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--quiet", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()

    if args.gui or not args.inputs:
        prepare_tk_runtime()
        from app.gui import main
        main(smoke=args.smoke)
        return

    from app.pipeline import export_to_snowedge, run_pipeline
    output = args.output
    if not output:
        first = Path(args.inputs[0]).resolve()
        output = str(first.with_name(f"{first.stem}_SnowRelay转换结果.xlsx"))
    df, _ = run_pipeline(args.inputs, output, args.rules, mask_passwords=not args.no_mask, progress=print)
    if args.snowedge_output:
        export_to_snowedge(df, args.snowedge_output, args.inputs, progress=print)
    print(f"{PRODUCT} 完成：{len(df)} 条记录 -> {output}")
    if getattr(sys, "frozen", False) and os.name == "nt" and not args.quiet:
        ctypes.windll.user32.MessageBoxW(
            0,
            f"已完成 {len(df)} 条记录转换。\n\n输出文件：\n{output}",
            f"{PRODUCT} {VERSION}",
            0x40,
        )


if __name__ == "__main__":
    cli()
