from __future__ import annotations

import os
import json
import subprocess
import sys
import threading
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import pandas as pd
from tkinterdnd2 import DND_FILES, TkinterDnD

from app.import_paths import classify_input_paths
from app.pipeline import export_result, export_to_snowedge, inspect_inputs, mapping_key, process_files
from models.schema import EXPORT_LABELS, STANDARD_COLUMNS

APP_NAME = "SnowRelay"
APP_SUBTITLE = "Security Finding Normalization"
APP_VERSION = "v0.5.0"

# SnowEdge light workspace palette
BG = "#F6F8FC"
SIDEBAR = "#FFFFFF"
PANEL = "#FFFFFF"
PANEL_2 = "#F8FAFD"
BORDER = "#DCE3EE"
TEXT = "#17213A"
MUTED = "#62708A"
ACCENT = "#4F46E5"
ACCENT_DARK = "#EEF0FF"
SUCCESS = "#14B88A"
WARNING = "#B45309"
DANGER = "#BE123C"

DISPLAY_SCALES = {
    "90%": 0.9,
    "100%": 1.0,
    "110%": 1.1,
    "120%": 1.2,
    "130%": 1.3,
}


def preferences_path() -> Path:
    base = Path(os.environ.get("LOCALAPPDATA") or Path.home())
    return base / "SnowPeak" / "SnowRelay" / "preferences.json"


def load_preferences() -> dict:
    try:
        return json.loads(preferences_path().read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return {}


def save_preferences(values: dict) -> None:
    try:
        path = preferences_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(values, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass


def configure_windows_app() -> None:
    """Give Windows a stable app identity and render Tk at native DPI."""
    if os.name != "nt":
        return
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("SnowEdge.SnowRelay.0.5.0")
        try:
            # PER_MONITOR_AWARE_V2 keeps text crisp when moving between displays.
            value = -4 & ((1 << (ctypes.sizeof(ctypes.c_void_p) * 8)) - 1)
            ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(value))
        except Exception:
            try:
                ctypes.windll.shcore.SetProcessDpiAwareness(2)
            except Exception:
                ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


def resource_root() -> Path:
    bundled = getattr(sys, "_MEIPASS", None)
    return Path(bundled) if bundled else Path(__file__).resolve().parent.parent

NAV_ITEMS = [
    ("dashboard", "工作台", "▰"),
    ("import", "数据导入", "＋"),
    ("mapping", "字段映射", "◇"),
    ("results", "风险结果", "⚠"),
    ("export", "导出与联动", "⇩"),
    ("rules", "规则中心", "⚙"),
]

STANDARD_DISPLAY = {
    "": "— 不映射 —",
    "asset_ip": "asset_ip · 资产IP",
    "hostname": "hostname · 主机名",
    "target_url": "target_url · 目标URL",
    "port": "port · 端口",
    "protocol": "protocol · 协议",
    "service": "service · 服务",
    "severity": "severity · 风险等级",
    "cvss": "cvss · CVSS",
    "vuln_name": "vuln_name · 漏洞名称",
    "cve": "cve · CVE",
    "cnvd": "cnvd · CNVD",
    "cnnvd": "cnnvd · CNNVD",
    "username": "username · 用户名",
    "password": "password · 密码/口令",
    "description": "description · 漏洞描述",
    "evidence": "evidence · 证据/结果",
    "solution": "solution · 修复建议",
}
EDITABLE_STANDARD_FIELDS = list(STANDARD_DISPLAY.keys())
DISPLAY_TO_FIELD = {v: k for k, v in STANDARD_DISPLAY.items()}


def open_path(path: Path) -> None:
    path = path.resolve()
    if os.name == "nt":
        os.startfile(str(path))  # type: ignore[attr-defined]
    elif sys_platform() == "darwin":
        subprocess.Popen(["open", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path)])


def sys_platform() -> str:
    import sys
    return sys.platform


class SnowButton(tk.Button):
    def __init__(self, master, text, command=None, kind="primary", **kwargs):
        palette = {
            "primary": (ACCENT, "#FFFFFF", "#4338CA"),
            "secondary": ("#F3F5FF", TEXT, "#E8EBFF"),
            "danger": ("#FFF1F3", DANGER, "#FFE2E7"),
        }
        bg, fg, active = palette[kind]
        super().__init__(
            master,
            text=text,
            command=command,
            bg=bg,
            fg=fg,
            activebackground=active,
            activeforeground=fg,
            relief="flat",
            bd=0,
            cursor="hand2",
            font=("Microsoft YaHei UI", 11, "bold"),
            padx=17,
            pady=10,
            highlightbackground=BORDER,
            highlightthickness=1 if kind == "secondary" else 0,
            **kwargs,
        )


class MainWindow(TkinterDnD.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"{APP_NAME} {APP_VERSION}")
        self.geometry("1360x860")
        self.minsize(1024, 680)
        self.configure(bg=BG)

        prefs = load_preferences()
        try:
            self.ui_scale = float(prefs.get("ui_scale", 1.0))
        except (TypeError, ValueError):
            self.ui_scale = 1.0
        if self.ui_scale not in DISPLAY_SCALES.values():
            self.ui_scale = 1.0
        self.base_tk_scaling = float(self.tk.call("tk", "scaling"))
        self.tk.call("tk", "scaling", self.base_tk_scaling * self.ui_scale)

        self.root_dir = resource_root()
        self.icon_path = self.root_dir / "assets" / "brand" / "snowrelay-app-48.png"
        self.icon_ico_path = self.root_dir / "assets" / "brand" / "snowrelay.ico"
        if self.icon_ico_path.exists() and os.name == "nt":
            try:
                self.iconbitmap(default=str(self.icon_ico_path))
            except tk.TclError:
                pass
        if self.icon_path.exists():
            try:
                self._app_icon = tk.PhotoImage(file=str(self.icon_path))
                # Windows selects the correct native size from the multi-layer
                # ICO. Replacing it with a large PNG makes taskbar icons blurry.
                if os.name != "nt":
                    self.iconphoto(True, self._app_icon)
            except tk.TclError:
                self._app_icon = None
        self.rules_dir = self.root_dir / "rules"
        self.files: list[str] = []
        self.inspect_meta: list[dict] = []
        self.mapping_overrides: dict[str, dict[str, str]] = {}
        self.result_df: pd.DataFrame | None = None
        self.result_meta: list[dict] = []
        self.active_page = "dashboard"
        self.active_result_filter = "全部"
        self.busy = False

        self.output_var = tk.StringVar(value=str(Path.cwd() / "SnowRelay_标准化结果.xlsx"))
        self.snowedge_output_var = tk.StringVar(value=str(Path.cwd() / "SnowRelay_SnowEdge联动包.snowedge.json"))
        self.mask_var = tk.BooleanVar(value=True)
        self.auto_convert_var = tk.BooleanVar(value=True)
        self.status_var = tk.StringVar(value="READY · 等待导入安全结果")
        self.mapping_source_var = tk.StringVar()
        self.mapping_target_var = tk.StringVar(value=STANDARD_DISPLAY[""])

        self._configure_ttk()
        self._build_shell()
        self.show_page("dashboard")
        self._refresh_all()

    def _configure_ttk(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure(
            "Snow.Treeview",
            background=PANEL,
            fieldbackground=PANEL,
            foreground=TEXT,
            rowheight=round(40 * self.ui_scale),
            borderwidth=0,
            relief="flat",
            font=("Microsoft YaHei UI", 11),
        )
        style.map("Snow.Treeview", background=[("selected", ACCENT_DARK)], foreground=[("selected", ACCENT)])
        style.configure(
            "Snow.Treeview.Heading",
            background="#F1F4F9",
            foreground="#44516B",
            relief="flat",
            font=("Microsoft YaHei UI", 11, "bold"),
            padding=(9, 10),
        )
        style.map("Snow.Treeview.Heading", background=[("active", "#E8ECF4")])
        style.configure(
            "Snow.TCombobox",
            fieldbackground=PANEL_2,
            background=PANEL_2,
            foreground=TEXT,
            arrowcolor=ACCENT,
            bordercolor=BORDER,
            lightcolor=BORDER,
            darkcolor=BORDER,
        )
        self.option_add("*TCombobox*Listbox.background", PANEL_2)
        self.option_add("*TCombobox*Listbox.foreground", TEXT)
        self.option_add("*TCombobox*Listbox.selectBackground", ACCENT_DARK)
        self.option_add("*TCombobox*Listbox.selectForeground", ACCENT)
        self.option_add("*Font", ("Microsoft YaHei UI", 11))

    def _build_shell(self):
        self.sidebar = tk.Frame(self, bg=SIDEBAR, width=220, highlightbackground=BORDER, highlightthickness=1)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        brand = tk.Frame(self.sidebar, bg=SIDEBAR, padx=20, pady=22)
        brand.pack(fill="x")
        if getattr(self, "_app_icon", None):
            self._brand_icon = self._app_icon
            tk.Label(brand, image=self._brand_icon, bg=SIDEBAR).pack(side="left")
        else:
            tk.Label(brand, text="SF", bg=ACCENT_DARK, fg=ACCENT, font=("Segoe UI", 14, "bold"), padx=8, pady=6).pack(side="left")
        bt = tk.Frame(brand, bg=SIDEBAR)
        bt.pack(side="left", padx=(10, 0))
        tk.Label(bt, text=APP_NAME, bg=SIDEBAR, fg=TEXT, font=("Segoe UI", 18, "bold")).pack(anchor="w")
        tk.Label(bt, text="SNOWEDGE TOOLCHAIN", bg=SIDEBAR, fg=MUTED, font=("Segoe UI", 9, "bold")).pack(anchor="w", fill="x")

        self.nav_buttons = {}
        nav = tk.Frame(self.sidebar, bg=SIDEBAR, padx=10)
        nav.pack(fill="x", pady=(14, 0))
        for key, label, icon in NAV_ITEMS:
            btn = tk.Button(
                nav,
                text=f" {icon}   {label}",
                command=lambda k=key: self.show_page(k),
                anchor="w",
                bg=SIDEBAR,
                fg="#596780",
                activebackground=PANEL,
                activeforeground=TEXT,
                relief="flat",
                bd=0,
                padx=14,
                pady=11,
                font=("Microsoft YaHei UI", 11),
                cursor="hand2",
            )
            btn.pack(fill="x", pady=2)
            self.nav_buttons[key] = btn

        footer = tk.Frame(self.sidebar, bg=SIDEBAR, padx=20, pady=18)
        footer.pack(side="bottom", fill="x")
        tk.Label(footer, text=f"{APP_VERSION}", bg=SIDEBAR, fg=MUTED, font=("Segoe UI", 9, "bold")).pack(anchor="w")
        tk.Label(footer, text="SnowEdge Toolchain", bg=SIDEBAR, fg=MUTED, font=("Segoe UI", 9)).pack(anchor="w", pady=(3, 0))
        scale_row = tk.Frame(footer, bg=SIDEBAR)
        scale_row.pack(fill="x", pady=(12, 0))
        tk.Label(scale_row, text="显示大小", bg=SIDEBAR, fg=MUTED, font=("Microsoft YaHei UI", 9)).pack(side="left")
        self.scale_var = tk.StringVar(value=f"{int(self.ui_scale * 100)}%")
        scale_picker = ttk.Combobox(
            scale_row,
            textvariable=self.scale_var,
            values=list(DISPLAY_SCALES),
            state="readonly",
            width=6,
            style="Snow.TCombobox",
        )
        scale_picker.pack(side="right")
        scale_picker.bind("<<ComboboxSelected>>", self._change_ui_scale)

        self.main = tk.Frame(self, bg=BG)
        self.main.pack(side="left", fill="both", expand=True)

        self.topbar = tk.Frame(self.main, bg=BG, height=94, padx=30, pady=15)
        self.topbar.pack(fill="x")
        self.topbar.pack_propagate(False)
        title_wrap = tk.Frame(self.topbar, bg=BG)
        title_wrap.pack(side="left", fill="y")
        self.page_title = tk.Label(title_wrap, text="", bg=BG, fg=TEXT, font=("Microsoft YaHei UI", 18, "bold"))
        self.page_title.pack(anchor="w")
        self.page_subtitle = tk.Label(title_wrap, text="", bg=BG, fg=MUTED, font=("Microsoft YaHei UI", 11))
        self.page_subtitle.pack(anchor="w", pady=(2, 0))

        SnowButton(self.topbar, "一键转换", self.start_analysis, "primary").pack(side="right", pady=2)

        body = tk.Frame(self.main, bg=BG, padx=30, pady=0)
        body.pack(fill="both", expand=True)
        self.page_host = tk.Frame(body, bg=BG)
        self.page_host.pack(fill="both", expand=True)

        status = tk.Frame(self.main, bg="#FFFFFF", height=34, padx=20, highlightbackground=BORDER, highlightthickness=1)
        status.pack(fill="x", side="bottom", before=body)
        status.pack_propagate(False)
        self.status_dot = tk.Label(status, text="●", bg="#FFFFFF", fg=SUCCESS, font=("Segoe UI", 9))
        self.status_dot.pack(side="left")
        tk.Label(status, textvariable=self.status_var, bg="#FFFFFF", fg=MUTED, font=("Microsoft YaHei UI", 10)).pack(side="left", padx=8)

        self.pages = {}
        self._build_dashboard_page()
        self._build_import_page()
        self._build_mapping_page()
        self._build_results_page()
        self._build_export_page()
        self._build_rules_page()

    def _new_page(self, key: str) -> tk.Frame:
        page = tk.Frame(self.page_host, bg=BG)
        self.pages[key] = page
        return page

    def _change_ui_scale(self, _event=None):
        scale = DISPLAY_SCALES.get(self.scale_var.get(), 1.0)
        self.ui_scale = scale
        self.tk.call("tk", "scaling", self.base_tk_scaling * scale)
        ttk.Style(self).configure("Snow.Treeview", rowheight=round(40 * scale))
        save_preferences({"ui_scale": scale})
        self.update_idletasks()

    def _panel(self, master, **pack_kwargs):
        f = tk.Frame(master, bg=PANEL, highlightbackground=BORDER, highlightthickness=1)
        if pack_kwargs:
            f.pack(**pack_kwargs)
        return f

    def _section_header(self, master, title, subtitle=""):
        wrap = tk.Frame(master, bg=master.cget("bg"))
        tk.Label(wrap, text=title, bg=master.cget("bg"), fg=TEXT, font=("Microsoft YaHei UI", 12, "bold")).pack(anchor="w")
        if subtitle:
            tk.Label(wrap, text=subtitle, bg=master.cget("bg"), fg=MUTED, font=("Microsoft YaHei UI", 10)).pack(anchor="w", pady=(2, 0))
        return wrap

    # ---------- Dashboard ----------
    def _build_dashboard_page(self):
        page = self._new_page("dashboard")
        hero = self._panel(page)
        hero.pack(fill="x", pady=(0, 16))
        hleft = tk.Frame(hero, bg=PANEL, padx=22, pady=18)
        hleft.pack(side="left", fill="both", expand=True)
        tk.Label(hleft, text="SECURITY DATA FORGE", bg=PANEL, fg=ACCENT, font=("Segoe UI", 9, "bold")).pack(anchor="w")
        tk.Label(hleft, text="把不同平台的漏洞结果，锻造成统一标准数据。", bg=PANEL, fg=TEXT, font=("Microsoft YaHei UI", 15, "bold")).pack(anchor="w", pady=(5, 0))
        tk.Label(hleft, text="Drop · Detect · Normalize · Govern", bg=PANEL, fg=MUTED, font=("Segoe UI", 10)).pack(anchor="w", pady=(5, 0))
        SnowButton(hero, "导入数据", lambda: self.show_page("import"), "secondary").pack(side="right", padx=22)

        cards = tk.Frame(page, bg=BG)
        cards.pack(fill="x", pady=(0, 16))
        self.card_values = {}
        for idx, (key, label, accent) in enumerate([
            ("total", "标准化记录", ACCENT),
            ("vuln", "高危漏洞", DANGER),
            ("port", "高危端口", WARNING),
            ("weak", "弱口令", SUCCESS),
        ]):
            card = self._panel(cards)
            card.pack(side="left", fill="both", expand=True, padx=(0 if idx == 0 else 6, 0 if idx == 3 else 6))
            inner = tk.Frame(card, bg=PANEL, padx=18, pady=14)
            inner.pack(fill="both", expand=True)
            tk.Label(inner, text=label, bg=PANEL, fg=MUTED, font=("Microsoft YaHei UI", 10)).pack(anchor="w")
            value = tk.Label(inner, text="0", bg=PANEL, fg=accent, font=("Segoe UI", 24, "bold"))
            value.pack(anchor="w", pady=(4, 0))
            self.card_values[key] = value

        lower = tk.Frame(page, bg=BG)
        lower.pack(fill="both", expand=True)
        left = self._panel(lower)
        left.pack(side="left", fill="both", expand=True, padx=(0, 8))
        lhead = self._section_header(left, "当前数据集", "来源平台与处理状态")
        lhead.pack(fill="x", padx=18, pady=(15, 8))
        self.dashboard_tree = ttk.Treeview(left, columns=("platform", "rows", "file"), show="headings", style="Snow.Treeview", height=9)
        for c, t, w in [("platform", "平台", 150), ("rows", "记录", 80), ("file", "来源文件", 360)]:
            self.dashboard_tree.heading(c, text=t)
            self.dashboard_tree.column(c, width=w, anchor="w")
        self.dashboard_tree.pack(fill="both", expand=True, padx=14, pady=(0, 14))

        right = self._panel(lower)
        right.pack(side="left", fill="both", expand=False, padx=(8, 0))
        right.configure(width=310)
        right.pack_propagate(False)
        rhead = self._section_header(right, "处理链路", "SnowRelay Pipeline")
        rhead.pack(fill="x", padx=18, pady=(15, 10))
        for i, (name, desc) in enumerate([
            ("01  IMPORT", "CSV / XLS / XLSX"),
            ("02  MAP", "字段自动映射 + 手工纠正"),
            ("03  CLASSIFY", "高危漏洞 / 高危端口 / 弱口令"),
            ("04  DELIVER", "Excel 交付 / SnowEdge 联动"),
        ]):
            row = tk.Frame(right, bg=PANEL, padx=18, pady=9)
            row.pack(fill="x")
            tk.Label(row, text=name, bg=PANEL, fg=ACCENT if i == 0 else TEXT, font=("Consolas", 10, "bold")).pack(anchor="w")
            tk.Label(row, text=desc, bg=PANEL, fg=MUTED, font=("Microsoft YaHei UI", 10)).pack(anchor="w", pady=(2, 0))

    # ---------- Import ----------
    def _build_import_page(self):
        page = self._new_page("import")
        drop = self._panel(page)
        drop.pack(fill="x", pady=(0, 14))
        self.drop_box = tk.Frame(
            drop, bg="#F7F7FF", padx=20, pady=24,
            highlightbackground="#A5B4FC", highlightcolor=ACCENT,
            highlightthickness=2, cursor="hand2",
        )
        self.drop_box.pack(fill="x", padx=12, pady=12)
        self.drop_icon = tk.Label(self.drop_box, text="⇩", bg="#F7F7FF", fg=ACCENT, font=("Segoe UI", 30, "bold"), cursor="hand2")
        self.drop_icon.pack()
        self.drop_title = tk.Label(self.drop_box, text="拖动客户表格到这里", bg="#F7F7FF", fg=TEXT, font=("Microsoft YaHei UI", 14, "bold"), cursor="hand2")
        self.drop_title.pack(pady=(4, 2))
        self.drop_hint = tk.Label(
            self.drop_box,
            text="可一次拖入多个 CSV / XLS / XLSX / XLSM 文件，也可以点击下方按钮选择",
            bg="#F7F7FF", fg=MUTED, font=("Microsoft YaHei UI", 10), cursor="hand2",
        )
        self.drop_hint.pack()
        SnowButton(self.drop_box, "选择客户表格", self.add_files, "primary").pack(pady=(14, 6))
        tk.Checkbutton(
            self.drop_box, text="导入后自动转换（推荐）", variable=self.auto_convert_var,
            bg="#F7F7FF", fg=TEXT, activebackground="#F7F7FF", activeforeground=TEXT,
            selectcolor="#F7F7FF", font=("Microsoft YaHei UI", 10), cursor="hand2",
        ).pack()
        self._register_drop_target_tree(self.drop_box)

        bar = tk.Frame(page, bg=BG)
        bar.pack(fill="x", pady=(0, 8))
        tk.Label(bar, text="已导入文件", bg=BG, fg=TEXT, font=("Microsoft YaHei UI", 11, "bold")).pack(side="left")
        SnowButton(bar, "清空", self.clear_files, "danger").pack(side="right")
        SnowButton(bar, "移除选中", self.remove_selected_file, "secondary").pack(side="right", padx=8)

        panel = self._panel(page)
        panel.pack(fill="both", expand=True)
        self.import_tree = ttk.Treeview(panel, columns=("name", "platform", "rows", "status"), show="headings", style="Snow.Treeview")
        for c, t, w in [("name", "文件 / Sheet", 420), ("platform", "平台识别", 170), ("rows", "数据量", 90), ("status", "状态", 130)]:
            self.import_tree.heading(c, text=t)
            self.import_tree.column(c, width=w, anchor="w")
        self.import_tree.pack(fill="both", expand=True, padx=12, pady=12)

    # ---------- Mapping ----------
    def _build_mapping_page(self):
        page = self._new_page("mapping")
        top = self._panel(page)
        top.pack(fill="x", pady=(0, 14))
        inner = tk.Frame(top, bg=PANEL, padx=18, pady=14)
        inner.pack(fill="x")
        tk.Label(inner, text="数据源", bg=PANEL, fg=MUTED, font=("Microsoft YaHei UI", 10)).pack(side="left")
        self.mapping_combo = ttk.Combobox(inner, textvariable=self.mapping_source_var, state="readonly", style="Snow.TCombobox", width=52)
        self.mapping_combo.pack(side="left", padx=10)
        self.mapping_combo.bind("<<ComboboxSelected>>", lambda _e: self._refresh_mapping_table())
        SnowButton(inner, "重新检测", self.inspect_files, "secondary").pack(side="right")

        workspace = tk.Frame(page, bg=BG)
        workspace.pack(fill="both", expand=True)
        left = self._panel(workspace)
        left.pack(side="left", fill="both", expand=True, padx=(0, 8))
        self.mapping_tree = ttk.Treeview(left, columns=("source", "target", "state"), show="headings", style="Snow.Treeview")
        for c, t, w in [("source", "原始字段", 260), ("target", "SnowRelay Schema", 290), ("state", "识别状态", 120)]:
            self.mapping_tree.heading(c, text=t)
            self.mapping_tree.column(c, width=w, anchor="w")
        self.mapping_tree.pack(fill="both", expand=True, padx=12, pady=12)
        self.mapping_tree.bind("<<TreeviewSelect>>", self._on_mapping_select)

        right = self._panel(workspace)
        right.pack(side="left", fill="y", padx=(8, 0))
        right.configure(width=330)
        right.pack_propagate(False)
        pane = tk.Frame(right, bg=PANEL, padx=18, pady=18)
        pane.pack(fill="both", expand=True)
        tk.Label(pane, text="手工纠正", bg=PANEL, fg=TEXT, font=("Microsoft YaHei UI", 12, "bold")).pack(anchor="w")
        tk.Label(pane, text="自动识别不准确时，可覆盖当前字段映射。", bg=PANEL, fg=MUTED, font=("Microsoft YaHei UI", 10), wraplength=270, justify="left").pack(anchor="w", pady=(4, 18))
        tk.Label(pane, text="原始字段", bg=PANEL, fg=MUTED, font=("Microsoft YaHei UI", 10)).pack(anchor="w")
        self.mapping_selected_label = tk.Label(pane, text="未选择", bg=PANEL_2, fg=TEXT, anchor="w", padx=10, pady=9)
        self.mapping_selected_label.pack(fill="x", pady=(4, 14))
        tk.Label(pane, text="目标字段", bg=PANEL, fg=MUTED, font=("Microsoft YaHei UI", 10)).pack(anchor="w")
        self.mapping_target_combo = ttk.Combobox(pane, textvariable=self.mapping_target_var, state="readonly", style="Snow.TCombobox", values=list(STANDARD_DISPLAY.values()))
        self.mapping_target_combo.pack(fill="x", pady=(4, 14))
        SnowButton(pane, "应用映射", self.apply_mapping_override, "primary").pack(fill="x")
        SnowButton(pane, "恢复自动识别", self.reset_mapping_override, "secondary").pack(fill="x", pady=(8, 0))

    # ---------- Results ----------
    def _build_results_page(self):
        page = self._new_page("results")
        tabs = tk.Frame(page, bg=BG)
        tabs.pack(fill="x", pady=(0, 10))
        self.result_tab_buttons = {}
        for label in ["全部", "高危漏洞", "高危端口", "弱口令", "未识别"]:
            b = tk.Button(
                tabs, text=label, command=lambda x=label: self.set_result_filter(x),
                bg=PANEL, fg=MUTED, activebackground=ACCENT_DARK, activeforeground=ACCENT,
                relief="flat", bd=0, padx=16, pady=9, font=("Microsoft YaHei UI", 10, "bold"), cursor="hand2"
            )
            b.pack(side="left", padx=(0, 6))
            self.result_tab_buttons[label] = b
        self.result_count_label = tk.Label(tabs, text="", bg=BG, fg=MUTED, font=("Microsoft YaHei UI", 10))
        self.result_count_label.pack(side="right")

        panel = self._panel(page)
        panel.pack(fill="both", expand=True)
        cols = ("asset_ip", "port", "severity", "type", "name", "cve", "platform")
        self.results_tree = ttk.Treeview(panel, columns=cols, show="headings", style="Snow.Treeview")
        heads = {
            "asset_ip": ("资产IP", 135), "port": ("端口", 70), "severity": ("等级", 85),
            "type": ("分类", 150), "name": ("风险名称", 330), "cve": ("CVE", 150), "platform": ("来源", 120),
        }
        for c in cols:
            self.results_tree.heading(c, text=heads[c][0])
            self.results_tree.column(c, width=heads[c][1], anchor="w")
        self.results_tree.pack(fill="both", expand=True, padx=12, pady=12)
        self.results_tree.bind("<Double-1>", self.show_result_detail)

    # ---------- Export ----------
    def _build_export_page(self):
        page = self._new_page("export")
        panel = self._panel(page)
        panel.pack(fill="x", pady=(0, 14))
        inner = tk.Frame(panel, bg=PANEL, padx=22, pady=20)
        inner.pack(fill="x")
        tk.Label(inner, text="EXPORT CENTER", bg=PANEL, fg=ACCENT, font=("Consolas", 9, "bold")).pack(anchor="w")
        tk.Label(inner, text="标准化结果交付", bg=PANEL, fg=TEXT, font=("Microsoft YaHei UI", 15, "bold")).pack(anchor="w", pady=(4, 14))

        tk.Label(inner, text="Excel 输出文件", bg=PANEL, fg=MUTED, font=("Microsoft YaHei UI", 10)).pack(anchor="w")
        path_row = tk.Frame(inner, bg=PANEL)
        path_row.pack(fill="x", pady=(5, 14))
        self.output_entry = tk.Entry(path_row, textvariable=self.output_var, bg=PANEL_2, fg=TEXT, insertbackground=TEXT, relief="flat", bd=0, font=("Consolas", 9))
        self.output_entry.pack(side="left", fill="x", expand=True, ipady=9, padx=(0, 8))
        SnowButton(path_row, "选择", self.choose_output, "secondary").pack(side="left")

        opts = tk.Frame(inner, bg=PANEL)
        opts.pack(fill="x", pady=(0, 18))
        self.mask_check = tk.Checkbutton(
            opts, text="导出时对密码/口令脱敏（推荐）", variable=self.mask_var,
            bg=PANEL, fg=TEXT, activebackground=PANEL, activeforeground=TEXT, selectcolor=PANEL_2,
            font=("Microsoft YaHei UI", 10), bd=0
        )
        self.mask_check.pack(side="left")

        actions = tk.Frame(inner, bg=PANEL)
        actions.pack(fill="x")
        SnowButton(actions, "生成 Excel", self.start_export, "primary").pack(side="left")
        SnowButton(actions, "打开输出目录", self.open_output_dir, "secondary").pack(side="left", padx=8)

        bridge = self._panel(page)
        bridge.pack(fill="x", pady=(0, 14))
        bridge_inner = tk.Frame(bridge, bg=PANEL, padx=22, pady=20)
        bridge_inner.pack(fill="x")
        tk.Label(bridge_inner, text="SNOWEDGE TOOLCHAIN", bg=PANEL, fg=ACCENT, font=("Segoe UI", 10, "bold")).pack(anchor="w")
        tk.Label(bridge_inner, text="交接到 SnowEdge", bg=PANEL, fg=TEXT, font=("Microsoft YaHei UI", 15, "bold")).pack(anchor="w", pady=(4, 3))
        tk.Label(
            bridge_inner,
            text="生成可审计的离线联动包。在 SnowEdge 项目的“导入数据”中预览后导入资产、服务、候选 Finding 与 Evidence；联动包不包含口令明文。",
            bg=PANEL, fg=MUTED, font=("Microsoft YaHei UI", 10), wraplength=900, justify="left",
        ).pack(anchor="w", pady=(0, 12))
        bridge_path = tk.Frame(bridge_inner, bg=PANEL)
        bridge_path.pack(fill="x", pady=(0, 12))
        tk.Entry(
            bridge_path, textvariable=self.snowedge_output_var, bg=PANEL_2, fg=TEXT,
            insertbackground=TEXT, relief="flat", bd=0, font=("Consolas", 10),
            highlightbackground=BORDER, highlightthickness=1,
        ).pack(side="left", fill="x", expand=True, ipady=10, padx=(0, 8))
        SnowButton(bridge_path, "选择", self.choose_snowedge_output, "secondary").pack(side="left")
        SnowButton(bridge_inner, "生成 SnowEdge 联动包", self.start_snowedge_export, "primary").pack(anchor="w")

        info = self._panel(page)
        info.pack(fill="both", expand=True)
        ib = tk.Frame(info, bg=PANEL, padx=20, pady=18)
        ib.pack(fill="both", expand=True)
        tk.Label(ib, text="Excel 输出结构", bg=PANEL, fg=TEXT, font=("Microsoft YaHei UI", 12, "bold")).pack(anchor="w")
        for text in ["汇总", "高危漏洞", "高危端口", "弱口令", "未识别数据", "全部标准化数据"]:
            row = tk.Frame(ib, bg=PANEL, pady=5)
            row.pack(fill="x")
            tk.Label(row, text="✓", bg=PANEL, fg=SUCCESS, font=("Segoe UI", 9, "bold")).pack(side="left")
            tk.Label(row, text=text, bg=PANEL, fg=MUTED, font=("Microsoft YaHei UI", 10)).pack(side="left", padx=8)

    # ---------- Rules ----------
    def _build_rules_page(self):
        page = self._new_page("rules")
        self.rule_cards_host = tk.Frame(page, bg=BG)
        self.rule_cards_host.pack(fill="x")
        notes = self._panel(page)
        notes.pack(fill="both", expand=True, pady=(14, 0))
        n = tk.Frame(notes, bg=PANEL, padx=20, pady=18)
        n.pack(fill="both", expand=True)
        tk.Label(n, text="规则说明", bg=PANEL, fg=TEXT, font=("Microsoft YaHei UI", 11, "bold")).pack(anchor="w")
        tk.Label(
            n,
            text="高危端口用于标记需要重点核查的开放端口，不应脱离资产暴露面、访问控制和业务必要性直接判定为漏洞。规则文件均为纯文本，可按组织要求更新。",
            bg=PANEL, fg=MUTED, font=("Microsoft YaHei UI", 10), wraplength=760, justify="left"
        ).pack(anchor="w", pady=(8, 0))

    # ---------- Navigation ----------
    def show_page(self, key: str):
        self.active_page = key
        titles = {
            "dashboard": ("工作台", f"{APP_SUBTITLE} · 两高一弱数据治理"),
            "import": ("数据导入", "导入平台导出的 CSV / Excel 漏洞结果"),
            "mapping": ("字段映射", "自动识别原始字段，并允许手工纠正 SnowRelay Schema"),
            "results": ("风险结果", "查看高危漏洞、高危端口、弱口令与标准化明细"),
            "export": ("导出与联动", "生成标准 Excel，或交接到 SnowEdge 项目继续研判与报告"),
            "rules": ("规则中心", "维护两高一弱规则库"),
        }
        self.page_title.config(text=titles[key][0])
        self.page_subtitle.config(text=titles[key][1])
        for k, btn in self.nav_buttons.items():
            btn.config(bg=ACCENT_DARK if k == key else SIDEBAR, fg=ACCENT if k == key else "#596780")
        for p in self.pages.values():
            p.pack_forget()
        self.pages[key].pack(fill="both", expand=True)
        if key == "mapping" and self.files and not self.inspect_meta:
            self.inspect_files()
        if key == "rules":
            self.refresh_rules()

    # ---------- Data operations ----------
    def add_files(self):
        paths = filedialog.askopenfilenames(filetypes=[
            ("安全结果文件", "*.csv *.xls *.xlsx *.xlsm"),
            ("CSV", "*.csv"), ("Excel", "*.xls *.xlsx *.xlsm"), ("所有文件", "*.*")
        ])
        self._add_input_paths(paths)

    def _set_drop_style(self, active: bool):
        bg = "#EEF0FF" if active else "#F7F7FF"
        border = ACCENT if active else "#A5B4FC"
        self.drop_box.configure(bg=bg, highlightbackground=border)
        for widget in (self.drop_icon, self.drop_title, self.drop_hint):
            widget.configure(bg=bg)

    def _register_drop_target_tree(self, widget):
        """Make every visible part of the import area accept file drops."""
        widget.drop_target_register(DND_FILES)
        widget.dnd_bind("<<DropEnter>>", self._on_drop_enter)
        widget.dnd_bind("<<DropLeave>>", self._on_drop_leave)
        widget.dnd_bind("<<Drop>>", self._on_files_dropped)
        for child in widget.winfo_children():
            self._register_drop_target_tree(child)

    def _on_drop_enter(self, event):
        self._set_drop_style(True)
        return event.action

    def _on_drop_leave(self, event):
        self._set_drop_style(False)
        return event.action

    def _on_files_dropped(self, event):
        self._set_drop_style(False)
        # TkDND passes a Tcl list. splitlist preserves paths containing spaces.
        paths = self.tk.splitlist(event.data)
        self._add_input_paths(paths, dropped=True)
        return event.action

    def _add_input_paths(self, paths, dropped: bool = False):
        accepted, rejected = classify_input_paths(paths)
        existing = {os.path.normcase(str(Path(p).resolve())) for p in self.files}
        additions = [p for p in accepted if os.path.normcase(p) not in existing]
        changed = bool(additions)
        self.files.extend(additions)

        if changed:
            self.inspect_meta = []
            self.result_df = None
            self.result_meta = []
            verb = "已拖入" if dropped else "已选择"
            self.status_var.set(f"IMPORTED · {verb} {len(additions)} 个文件 · 共 {len(self.files)} 个")
            self._refresh_all()
            self.inspect_files()
        elif accepted and not rejected:
            self.status_var.set("READY · 所选文件已在导入列表中")

        if rejected:
            preview = "\n".join(f"• {item}" for item in rejected[:8])
            extra = f"\n…另有 {len(rejected) - 8} 项" if len(rejected) > 8 else ""
            messagebox.showwarning(
                "部分文件未导入",
                f"SnowRelay 仅接收 CSV / XLS / XLSX / XLSM 文件。\n\n{preview}{extra}",
            )

    def remove_selected_file(self):
        selected = self.import_tree.selection()
        paths = set()
        for item in selected:
            values = self.import_tree.item(item, "values")
            if values:
                display = str(values[0]).split("  /  ")[0]
                for p in self.files:
                    if Path(p).name == display:
                        paths.add(p)
        if not paths:
            return
        self.files = [p for p in self.files if p not in paths]
        self.inspect_meta = []
        self.result_df = None
        self.mapping_overrides = {k: v for k, v in self.mapping_overrides.items() if not any(k.startswith(p + "::") for p in paths)}
        self._refresh_all()
        if self.files:
            self.inspect_files()

    def clear_files(self):
        self.files.clear()
        self.inspect_meta.clear()
        self.mapping_overrides.clear()
        self.result_df = None
        self.result_meta.clear()
        self.status_var.set("READY · 等待导入安全结果")
        self._refresh_all()

    def inspect_files(self):
        if not self.files or self.busy:
            return
        self._set_busy(True, "DETECTING · 正在识别平台与字段…")

        def worker():
            try:
                meta = inspect_inputs(self.files)
                self.after(0, lambda: self._inspection_done(meta))
            except Exception as exc:
                self.after(0, lambda: messagebox.showerror("字段检测失败", str(exc)))
                self.after(0, lambda: self._set_busy(False, "ERROR · 字段检测失败"))

        threading.Thread(target=worker, daemon=True).start()

    def _inspection_done(self, meta: list[dict]):
        self.inspect_meta = meta
        self._set_busy(False, f"DETECTED · {len(meta)} data source(s) · 字段识别完成")
        self._refresh_all()
        if self.auto_convert_var.get():
            self.start_analysis()

    def start_analysis(self):
        if not self.files:
            messagebox.showwarning("SnowRelay", "请先在“数据导入”中添加 CSV / Excel 文件。")
            self.show_page("import")
            return
        if self.busy:
            return
        self._set_busy(True, "NORMALIZING · 正在执行字段标准化与规则分类…")

        def progress(text):
            self.after(0, lambda: self.status_var.set("RUNNING · " + text))

        def worker():
            try:
                df, meta = process_files(self.files, str(self.rules_dir), self.mapping_overrides, progress)
                self.after(0, lambda: self._analysis_done(df, meta))
            except Exception as exc:
                self.after(0, lambda: messagebox.showerror("标准化失败", str(exc)))
                self.after(0, lambda: self._set_busy(False, "ERROR · 标准化失败"))

        threading.Thread(target=worker, daemon=True).start()

    def _analysis_done(self, df: pd.DataFrame, meta: list[dict]):
        self.result_df = df
        self.result_meta = meta
        hv = int((df["is_high_vulnerability"] == "是").sum())
        hp = int((df["is_high_risk_port"] == "是").sum())
        wp = int((df["is_weak_password"] == "是").sum())
        self._set_busy(False, f"DONE · {len(df)} records · 高危漏洞 {hv} / 高危端口 {hp} / 弱口令 {wp}")
        self._refresh_all()
        self.show_page("results")

    def start_export(self):
        if self.result_df is None:
            messagebox.showwarning("SnowRelay", "请先执行标准化，再导出结果。")
            return
        if self.busy:
            return
        output = self.output_var.get().strip()
        if not output:
            self.choose_output()
            output = self.output_var.get().strip()
        if not output:
            return
        if Path(output).exists() and not messagebox.askyesno("覆盖文件", f"文件已存在，是否覆盖？\n\n{output}"):
            return
        self._set_busy(True, "EXPORTING · 正在生成 Excel…")

        def progress(text):
            self.after(0, lambda: self.status_var.set("EXPORT · " + text))

        def worker():
            try:
                export_result(self.result_df, output, self.files, self.mask_var.get(), progress)
                self.after(0, lambda: self._export_done(output))
            except Exception as exc:
                self.after(0, lambda: messagebox.showerror("导出失败", str(exc)))
                self.after(0, lambda: self._set_busy(False, "ERROR · 导出失败"))

        threading.Thread(target=worker, daemon=True).start()

    def _export_done(self, output: str):
        self._set_busy(False, f"EXPORTED · {output}")
        messagebox.showinfo("SnowRelay", f"标准化结果已生成。\n\n{output}")

    def start_snowedge_export(self):
        if self.result_df is None:
            messagebox.showwarning("SnowRelay", "请先执行标准化，再生成 SnowEdge 联动包。")
            return
        if self.busy:
            return
        output = self.snowedge_output_var.get().strip()
        if not output:
            self.choose_snowedge_output()
            output = self.snowedge_output_var.get().strip()
        if not output:
            return
        if Path(output).exists() and not messagebox.askyesno("覆盖文件", f"文件已存在，是否覆盖？\n\n{output}"):
            return
        self._set_busy(True, "EXPORTING · 正在生成 SnowEdge 联动包…")

        def progress(text):
            self.after(0, lambda: self.status_var.set("SNOWEDGE · " + text))

        def worker():
            try:
                export_to_snowedge(self.result_df, output, self.files, progress)
                self.after(0, lambda: self._snowedge_export_done(output))
            except Exception as exc:
                self.after(0, lambda: messagebox.showerror("联动包导出失败", str(exc)))
                self.after(0, lambda: self._set_busy(False, "ERROR · 联动包导出失败"))

        threading.Thread(target=worker, daemon=True).start()

    def _snowedge_export_done(self, output: str):
        self._set_busy(False, f"SNOWEDGE PACKAGE · {output}")
        messagebox.showinfo(
            "SnowRelay → SnowEdge",
            f"联动包已生成。\n\n请在 SnowEdge 项目的“导入数据”中选择 SnowRelay 联动包。\n\n{output}",
        )

    def _set_busy(self, busy: bool, text: str):
        self.busy = busy
        self.status_var.set(text)
        self.status_dot.config(fg=WARNING if busy else SUCCESS)

    # ---------- Mapping ----------
    def _meta_label(self, meta: dict) -> str:
        return f"{Path(meta['file']).name}  /  {meta['sheet']}"

    def _current_mapping_meta(self):
        value = self.mapping_source_var.get()
        for meta in self.inspect_meta:
            if self._meta_label(meta) == value:
                return meta
        return None

    def _refresh_mapping_table(self):
        for i in self.mapping_tree.get_children():
            self.mapping_tree.delete(i)
        meta = self._current_mapping_meta()
        if not meta:
            return
        key = mapping_key(meta["file"], meta["sheet"])
        overrides = self.mapping_overrides.get(key, {})
        auto = meta.get("mapping", {})
        for source in meta.get("source_columns", []):
            target = overrides.get(source, auto.get(source, ""))
            if source in overrides:
                state = "手工"
            elif source in auto:
                state = "自动"
            else:
                state = "未识别"
            self.mapping_tree.insert("", "end", values=(source, STANDARD_DISPLAY.get(target, target or "—"), state))

    def _on_mapping_select(self, _event=None):
        sel = self.mapping_tree.selection()
        if not sel:
            return
        source, target_display, _ = self.mapping_tree.item(sel[0], "values")
        self.mapping_selected_label.config(text=source)
        target = DISPLAY_TO_FIELD.get(target_display, "")
        self.mapping_target_var.set(STANDARD_DISPLAY.get(target, STANDARD_DISPLAY[""]))

    def apply_mapping_override(self):
        meta = self._current_mapping_meta()
        sel = self.mapping_tree.selection()
        if not meta or not sel:
            messagebox.showinfo("字段映射", "请先选择一个原始字段。")
            return
        source = str(self.mapping_tree.item(sel[0], "values")[0])
        target = DISPLAY_TO_FIELD.get(self.mapping_target_var.get(), "")
        key = mapping_key(meta["file"], meta["sheet"])
        overrides = self.mapping_overrides.setdefault(key, {})
        if target:
            for src, tgt in list(overrides.items()):
                if tgt == target and src != source:
                    del overrides[src]
            overrides[source] = target
        else:
            # Empty target explicitly means "ignore this column"; reset button restores auto detection.
            overrides[source] = ""
        self.result_df = None
        self._refresh_mapping_table()
        self.status_var.set("MAPPING UPDATED · 请重新执行标准化")

    def reset_mapping_override(self):
        meta = self._current_mapping_meta()
        sel = self.mapping_tree.selection()
        if not meta or not sel:
            return
        source = str(self.mapping_tree.item(sel[0], "values")[0])
        key = mapping_key(meta["file"], meta["sheet"])
        self.mapping_overrides.get(key, {}).pop(source, None)
        self.result_df = None
        self._refresh_mapping_table()
        self.status_var.set("MAPPING RESET · 已恢复自动识别")

    # ---------- Results ----------
    def set_result_filter(self, label: str):
        self.active_result_filter = label
        self._refresh_results()

    def _filtered_df(self) -> pd.DataFrame:
        if self.result_df is None:
            return pd.DataFrame()
        df = self.result_df
        if self.active_result_filter == "高危漏洞":
            return df[df["is_high_vulnerability"] == "是"]
        if self.active_result_filter == "高危端口":
            return df[df["is_high_risk_port"] == "是"]
        if self.active_result_filter == "弱口令":
            return df[df["is_weak_password"] == "是"]
        if self.active_result_filter == "未识别":
            return df[df["risk_type"] == ""]
        return df

    def show_result_detail(self, _event=None):
        if self.result_df is None:
            return
        sel = self.results_tree.selection()
        if not sel:
            return
        item = self.results_tree.item(sel[0])
        row_index = item.get("tags", [None])[0] if item.get("tags") else None
        if row_index is None:
            return
        try:
            row = self.result_df.loc[int(row_index)]
        except Exception:
            return

        win = tk.Toplevel(self)
        win.title("SnowRelay · 风险详情")
        win.geometry("720x620")
        win.configure(bg=BG)
        wrap = tk.Frame(win, bg=BG, padx=22, pady=20)
        wrap.pack(fill="both", expand=True)
        tk.Label(wrap, text=str(row.get("vuln_name", "未命名风险")) or "未命名风险", bg=BG, fg=TEXT, font=("Microsoft YaHei UI", 15, "bold"), wraplength=650, justify="left").pack(anchor="w")
        tk.Label(wrap, text=str(row.get("risk_type", "未命中两高一弱")) or "未命中两高一弱", bg=BG, fg=ACCENT, font=("Microsoft YaHei UI", 10, "bold")).pack(anchor="w", pady=(5, 14))
        text = tk.Text(wrap, bg=PANEL, fg=TEXT, insertbackground=TEXT, relief="flat", bd=0, wrap="word", font=("Microsoft YaHei UI", 10), padx=14, pady=12, highlightbackground=BORDER, highlightthickness=1)
        text.pack(fill="both", expand=True)
        fields = [
            ("资产", f"{row.get('asset_ip','')}:{row.get('port','')}".rstrip(":")),
            ("目标URL", row.get("target_url", "")),
            ("风险等级", row.get("severity", "")), ("CVSS", row.get("cvss", "")),
            ("CVE", row.get("cve", "")), ("客户原始分类", row.get("source_category", "")),
            ("来源平台", row.get("source_platform", "")),
            ("命中原因", row.get("match_reason", "")), ("描述", row.get("description", "")),
            ("证据/结果", row.get("evidence", "")), ("修复建议", row.get("solution", "")),
        ]
        for name, value in fields:
            text.insert("end", f"{name}\n", ("h",))
            text.insert("end", f"{value or '—'}\n\n")
        text.tag_config("h", foreground=ACCENT, font=("Microsoft YaHei UI", 10, "bold"))
        text.config(state="disabled")

    # ---------- Export / rules ----------
    def choose_output(self):
        p = filedialog.asksaveasfilename(
            defaultextension=".xlsx", filetypes=[("Excel", "*.xlsx")], initialfile="SnowRelay_标准化结果.xlsx"
        )
        if p:
            self.output_var.set(p)

    def choose_snowedge_output(self):
        p = filedialog.asksaveasfilename(
            defaultextension=".snowedge.json",
            filetypes=[("SnowEdge 联动包", "*.snowedge.json"), ("JSON", "*.json")],
            initialfile="SnowRelay_SnowEdge联动包.snowedge.json",
        )
        if p:
            self.snowedge_output_var.set(p)

    def open_output_dir(self):
        path = Path(self.output_var.get() or Path.cwd() / "SnowRelay_标准化结果.xlsx").expanduser().resolve().parent
        path.mkdir(parents=True, exist_ok=True)
        try:
            open_path(path)
        except Exception as exc:
            messagebox.showerror("打开目录失败", str(exc))

    def refresh_rules(self):
        for child in self.rule_cards_host.winfo_children():
            child.destroy()
        configs = [
            ("high_vulnerabilities.txt", "高危漏洞规则", "CVE / 漏洞清单"),
            ("high_ports.txt", "高危端口规则", "重点核查端口"),
            ("weak_passwords.txt", "弱口令字典", "组织批准的检查字典"),
        ]
        for idx, (file_name, title, desc) in enumerate(configs):
            path = self.rules_dir / file_name
            count = 0
            if path.exists():
                count = len([x for x in path.read_text(encoding="utf-8-sig").splitlines() if x.strip() and not x.strip().startswith("#")])
            card = self._panel(self.rule_cards_host)
            card.pack(side="left", fill="both", expand=True, padx=(0 if idx == 0 else 6, 0 if idx == 2 else 6))
            box = tk.Frame(card, bg=PANEL, padx=18, pady=16)
            box.pack(fill="both", expand=True)
            tk.Label(box, text=title, bg=PANEL, fg=TEXT, font=("Microsoft YaHei UI", 10, "bold")).pack(anchor="w")
            tk.Label(box, text=desc, bg=PANEL, fg=MUTED, font=("Microsoft YaHei UI", 10)).pack(anchor="w", pady=(2, 10))
            tk.Label(box, text=str(count), bg=PANEL, fg=ACCENT, font=("Segoe UI", 22, "bold")).pack(anchor="w")
            tk.Label(box, text="条规则", bg=PANEL, fg=MUTED, font=("Microsoft YaHei UI", 10)).pack(anchor="w")
            SnowButton(box, "打开规则文件", lambda p=path: self.open_rule_file(p), "secondary").pack(anchor="w", pady=(12, 0))

    def open_rule_file(self, path: Path):
        try:
            open_path(path)
        except Exception as exc:
            messagebox.showerror("打开失败", str(exc))

    # ---------- Refresh ----------
    def _refresh_all(self):
        self._refresh_import_tree()
        self._refresh_dashboard()
        self._refresh_mapping_sources()
        self._refresh_results()

    def _refresh_import_tree(self):
        if not hasattr(self, "import_tree"):
            return
        for i in self.import_tree.get_children():
            self.import_tree.delete(i)
        if self.inspect_meta:
            for m in self.inspect_meta:
                unmapped = len(m.get("unmapped_columns", []))
                category = m.get("source_category", "")
                platform = m.get("platform", "通用表格")
                display_type = f"{category} · {platform}" if category else platform
                header_note = f" · 表头第{m.get('header_row')}行" if m.get("header_row", 1) > 1 else ""
                status = ("✓ 已识别" if unmapped == 0 else f"⚠ {unmapped}列待核查") + header_note
                self.import_tree.insert("", "end", values=(self._meta_label(m), display_type, m.get("rows", 0), status))
        else:
            for p in self.files:
                self.import_tree.insert("", "end", values=(Path(p).name, "等待检测", "—", "等待识别"))

    def _refresh_dashboard(self):
        df = self.result_df
        values = {
            "total": len(df) if df is not None else 0,
            "vuln": int((df["is_high_vulnerability"] == "是").sum()) if df is not None else 0,
            "port": int((df["is_high_risk_port"] == "是").sum()) if df is not None else 0,
            "weak": int((df["is_weak_password"] == "是").sum()) if df is not None else 0,
        }
        for key, label in self.card_values.items():
            label.config(text=str(values[key]))
        for i in self.dashboard_tree.get_children():
            self.dashboard_tree.delete(i)
        meta = self.result_meta or self.inspect_meta
        for m in meta[:100]:
            self.dashboard_tree.insert("", "end", values=(m.get("platform", "通用表格"), m.get("rows", 0), self._meta_label(m)))

    def _refresh_mapping_sources(self):
        values = [self._meta_label(m) for m in self.inspect_meta]
        self.mapping_combo["values"] = values
        if values and self.mapping_source_var.get() not in values:
            self.mapping_source_var.set(values[0])
        if not values:
            self.mapping_source_var.set("")
        self._refresh_mapping_table()

    def _refresh_results(self):
        if not hasattr(self, "results_tree"):
            return
        for label, btn in self.result_tab_buttons.items():
            active = label == self.active_result_filter
            btn.config(bg=ACCENT_DARK if active else PANEL, fg=ACCENT if active else MUTED)
        for i in self.results_tree.get_children():
            self.results_tree.delete(i)
        df = self._filtered_df()
        self.result_count_label.config(text=f"{len(df)} records" if self.result_df is not None else "尚未执行标准化")
        if df.empty:
            return
        for idx, row in df.head(1000).iterrows():
            self.results_tree.insert(
                "", "end",
                values=(row.get("asset_ip", ""), row.get("port", ""), row.get("severity", ""), row.get("risk_type", ""), row.get("vuln_name", ""), row.get("cve", ""), row.get("source_platform", "")),
                tags=(str(idx),),
            )
        if len(df) > 1000:
            self.result_count_label.config(text=f"{len(df)} records · 当前预览前 1000 条")


def main(smoke: bool = False):
    configure_windows_app()
    window = MainWindow()
    if smoke:
        window.after(900, window.destroy)
    window.mainloop()


if __name__ == "__main__":
    main()
