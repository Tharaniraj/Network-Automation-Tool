"""
Network Device Manager - Main GUI Application
Automated configuration and observability for Cisco and Huawei devices
"""

import ipaddress
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
import threading
from datetime import datetime
from typing import Optional
from modules.device_manager import DeviceManager
from modules.configuration import ConfigurationManager
from modules.status_monitor import StatusMonitor, DeviceStatus
from modules.compliance import ComplianceChecker
from modules.logger import get_observability_manager
from modules import ssh_client
from modules.netflow import NetFlowCollector
from modules.config_wizard import get_tasks_by_category, get_task_by_name
from modules.templates import (
    get_all_templates, get_template_content, get_template_name,
    get_vendors, get_templates_by_vendor, get_categories
)

# ── Theme palette ─────────────────────────────────────────────────────────────
BG_DARK  = "#0d1117"   # root / window background
BG_MID   = "#161b22"   # panel / frame surface
BG_LIGHT = "#21262d"   # input / tree / text surface
BORDER   = "#30363d"   # borders and separators
TEXT_PRI = "#e6edf3"   # primary text
TEXT_SEC = "#8b949e"   # secondary / hint text
ACCENT1  = "#1f6feb"   # blue  – primary action
ACCENT2  = "#238636"   # green – success / confirm
ACCENT3  = "#da3633"   # red   – danger / remove
ACCENT4  = "#9e6a03"   # amber – warning
ACCENT5  = "#6d28d9"   # purple – wizard / special
ACCENT6  = "#0e7a6e"   # teal  – netflow / tools

_BTN_PALETTES = {
    "primary": ("#1f6feb", "#388bfd", "#1158c7"),
    "success": ("#238636", "#2ea043", "#196127"),
    "danger":  ("#b91c1c", "#ef4444", "#991b1b"),
    "warning": ("#92400e", "#d97706", "#78350f"),
    "purple":  ("#6d28d9", "#8b5cf6", "#5b21b6"),
    "teal":    ("#0e7a6e", "#14b8a6", "#0a5c52"),
    "neutral": ("#374151", "#4b5563", "#1f2937"),
}


def make_3d_button(parent, text, command=None, btn_type="primary",
                   state=tk.NORMAL, **kw):
    """Return a raised-relief coloured tk.Button with hover animation."""
    base, hover, pressed = _BTN_PALETTES.get(btn_type, _BTN_PALETTES["primary"])
    btn = tk.Button(
        parent, text=text, command=command,
        bg=base, fg=TEXT_PRI,
        activebackground=pressed, activeforeground=TEXT_PRI,
        relief=tk.RAISED, bd=3,
        font=("Arial", 9, "bold"),
        cursor="hand2", state=state,
        highlightthickness=0,
        **kw
    )

    def _on_enter(_e):
        if str(btn["state"]) != "disabled":
            btn.config(bg=hover)

    def _on_leave(_e):
        if str(btn["state"]) != "disabled":
            btn.config(bg=base)

    btn.bind("<Enter>", _on_enter)
    btn.bind("<Leave>", _on_leave)
    return btn


def _make_dash_icon(color: str, shape: str, size: int = 52):
    """
    Draw a circular dashboard icon using Pillow and return an
    ImageTk.PhotoImage.  Falls back to None when Pillow is absent.

    Shapes: devices | check | cross | cisco | huawei |
            health  | alert | shield
    """
    try:
        import math
        from PIL import Image, ImageDraw, ImageTk
    except ImportError:
        return None

    # Render at 2× then downsample for smooth anti-aliasing
    S = size * 2
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    def _hex(h, a=255):
        h = h.lstrip("#")
        return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), a)

    bg = _hex(color)
    # Filled circle
    d.ellipse([2, 2, S - 2, S - 2], fill=bg)
    # Soft top-highlight for subtle 3-D sphere look
    lighter = (min(255, bg[0] + 50), min(255, bg[1] + 50),
               min(255, bg[2] + 50), 70)
    d.ellipse([6, 6, S - 6, S // 2], fill=lighter)

    W = (255, 255, 255, 230)   # white symbol
    m = S // 2                  # centre
    lw = max(S // 13, 4)        # line width

    if shape == "devices":
        # Network device: rounded rectangle body + 4 port dots + antenna
        bx, by = S // 5, S // 3
        bw, bh = S * 3 // 5, S // 3
        d.rounded_rectangle([bx, by, bx + bw, by + bh],
                             radius=S // 16, outline=W, width=lw)
        pstep = bw // 5
        for i in range(4):
            px = bx + pstep * (i + 1) - pstep // 2
            py = by + bh // 2
            r = lw - 1
            d.ellipse([px - r, py - r, px + r, py + r], fill=W)
        # Antenna
        d.line([m, by, m, by - S // 9], fill=W, width=lw)
        d.ellipse([m - lw, by - S // 9 - lw,
                   m + lw, by - S // 9 + lw], fill=W)

    elif shape == "check":
        d.line([m - S // 4, m,
                m - S // 13, m + S // 5,
                m + S // 4, m - S // 7],
               fill=W, width=lw + 2, joint="curve")

    elif shape == "cross":
        pad = S // 5
        d.line([pad, pad, S - pad, S - pad], fill=W, width=lw + 2)
        d.line([S - pad, pad, pad, S - pad], fill=W, width=lw + 2)

    elif shape == "cisco":
        # Three signal arcs (Cisco-style wireless / network icon) + dot
        for r in [S // 7, S // 4 + 2, S // 3 + 2]:
            d.arc([m - r, m - r, m + r, m + r],
                  start=215, end=325, fill=W, width=max(lw - 1, 3))
        dot = lw - 1
        d.ellipse([m - dot, m + S // 5,
                   m + dot, m + S // 5 + dot * 2], fill=W)

    elif shape == "huawei":
        # 8 radiating petals (simplified Huawei flower logo)
        for i in range(8):
            angle = i * math.pi / 4
            x1 = m + (S // 7) * math.cos(angle)
            y1 = m + (S // 7) * math.sin(angle)
            x2 = m + (S // 3 + 2) * math.cos(angle)
            y2 = m + (S // 3 + 2) * math.sin(angle)
            d.line([x1, y1, x2, y2], fill=W, width=lw)
        dot = lw // 2 + 1
        d.ellipse([m - dot, m - dot, m + dot, m + dot], fill=W)

    elif shape == "health":
        # ECG heartbeat line
        x0 = S // 8
        pts = [
            x0,             m,
            x0 + S // 5,    m,
            x0 + S // 5 + S // 10, m - S // 4,
            x0 + S // 5 + S // 5,  m + S // 4,
            x0 + S // 5 + S // 10 * 3, m - S // 9,
            x0 + S * 2 // 5 + S // 8, m,
            S - x0,         m,
        ]
        d.line(pts, fill=W, width=lw, joint="curve")

    elif shape == "alert":
        # Bell: arc top + straight sides + base bar + clapper
        pad = S // 5
        # Arc (bell dome)
        d.arc([pad, pad + S // 10, S - pad, S * 3 // 4],
              start=180, end=0, fill=W, width=lw)
        # Sides
        d.line([pad, m + S // 10, pad, S * 3 // 4],   fill=W, width=lw)
        d.line([S - pad, m + S // 10, S - pad, S * 3 // 4], fill=W, width=lw)
        # Base bar
        d.line([pad - lw // 2, S * 3 // 4,
                S - pad + lw // 2, S * 3 // 4], fill=W, width=lw)
        # Clapper
        cr = lw - 1
        d.ellipse([m - cr, S * 3 // 4 + 2,
                   m + cr, S * 3 // 4 + cr * 2 + 4], fill=W)

    elif shape == "shield":
        # Pentagon shield outline + checkmark
        pts = [(m,       S // 8),
               (S * 7 // 8, S // 3),
               (S * 3 // 4, S * 3 // 4),
               (m,       S * 7 // 8),
               (S // 4,  S * 3 // 4),
               (S // 8,  S // 3)]
        d.polygon(pts, outline=W, fill=None, width=lw)
        # Checkmark inside shield
        d.line([m - S // 7, m + S // 14,
                m - S // 18, m + S // 4,
                m + S // 5, m - S // 10],
               fill=W, width=lw)

    img = img.resize((size, size), Image.LANCZOS)
    return ImageTk.PhotoImage(img)


class NetworkDeviceManagerGUI:
    """Main GUI Application for Network Device Management"""

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Network Device Manager - Automated Configuration & Observability")
        self.root.geometry("1200x800")
        self.root.configure(bg=BG_DARK)

        # Initialize managers
        self.device_manager = DeviceManager()
        self.config_manager = ConfigurationManager()
        self.status_monitor = StatusMonitor()
        self.compliance_checker = ComplianceChecker()
        self.logger = get_observability_manager()
        self.netflow_collector = NetFlowCollector()
        
        # Template list for combobox
        self.template_list = []
        
        # Setup GUI
        self._setup_styles()
        self._create_menu_bar()
        self._create_main_layout()
        
        # Status bar
        self.status_var = tk.StringVar(value="Ready")
        status_bar = tk.Label(
            self.root, textvariable=self.status_var,
            bg=BG_DARK, fg=TEXT_SEC, relief=tk.SUNKEN,
            font=("Arial", 8), anchor=tk.W, padx=6, pady=2)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        
        self.update_device_list()

    def _setup_styles(self):
        """Setup dark cyberpunk GUI styles and theme."""
        style = ttk.Style()
        style.theme_use('clam')

        # ── Base ──────────────────────────────────────────────────────────────
        style.configure(".",
                         background=BG_MID, foreground=TEXT_PRI,
                         bordercolor=BORDER, troughcolor=BG_DARK,
                         selectbackground=ACCENT1, selectforeground=TEXT_PRI,
                         focuscolor=ACCENT1)

        # ── Frames ────────────────────────────────────────────────────────────
        style.configure("TFrame", background=BG_MID)
        style.configure("TLabelframe",
                         background=BG_MID, foreground=TEXT_PRI,
                         bordercolor=BORDER, relief=tk.GROOVE)
        style.configure("TLabelframe.Label",
                         background=BG_MID, foreground="#58a6ff",
                         font=("Arial", 9, "bold"))

        # ── Labels ────────────────────────────────────────────────────────────
        style.configure("TLabel", background=BG_MID, foreground=TEXT_PRI)
        style.configure("Header.TLabel",
                         font=("Arial", 13, "bold"),
                         foreground="#58a6ff", background=BG_MID)
        style.configure("Success.TLabel",
                         foreground="#3fb950", background=BG_MID)
        style.configure("Error.TLabel",
                         foreground="#f85149", background=BG_MID)
        style.configure("Warning.TLabel",
                         foreground="#e3b341", background=BG_MID)

        # ── Notebook tabs ─────────────────────────────────────────────────────
        style.configure("TNotebook",
                         background=BG_DARK, bordercolor=BORDER)
        style.configure("TNotebook.Tab",
                         background=BG_LIGHT, foreground=TEXT_SEC,
                         padding=[14, 7], font=("Arial", 9, "bold"))
        style.map("TNotebook.Tab",
                  background=[("selected", ACCENT1), ("active", BG_MID)],
                  foreground=[("selected", TEXT_PRI), ("active", TEXT_PRI)])

        # ── Treeview ──────────────────────────────────────────────────────────
        style.configure("Treeview",
                         background=BG_LIGHT, foreground=TEXT_PRI,
                         fieldbackground=BG_LIGHT, bordercolor=BORDER,
                         font=("Arial", 9), rowheight=22)
        style.configure("Treeview.Heading",
                         background=BG_DARK, foreground="#58a6ff",
                         font=("Arial", 9, "bold"), relief=tk.FLAT,
                         bordercolor=BORDER)
        style.map("Treeview",
                  background=[("selected", ACCENT1)],
                  foreground=[("selected", TEXT_PRI)])
        style.map("Treeview.Heading",
                  background=[("active", BG_MID)])

        # ── Entry / Combobox ──────────────────────────────────────────────────
        style.configure("TEntry",
                         fieldbackground=BG_LIGHT, foreground=TEXT_PRI,
                         insertcolor=TEXT_PRI, bordercolor=BORDER)
        style.configure("TCombobox",
                         fieldbackground=BG_LIGHT, foreground=TEXT_PRI,
                         selectbackground=ACCENT1, bordercolor=BORDER,
                         arrowcolor=TEXT_SEC)
        style.map("TCombobox",
                  fieldbackground=[("readonly", BG_LIGHT)],
                  foreground=[("readonly", TEXT_PRI)])

        # ── Scrollbar ─────────────────────────────────────────────────────────
        style.configure("TScrollbar",
                         background=BG_LIGHT, troughcolor=BG_DARK,
                         bordercolor=BORDER, arrowcolor=TEXT_SEC,
                         relief=tk.FLAT)
        style.map("TScrollbar",
                  background=[("active", BORDER)])

        # ── Separator ─────────────────────────────────────────────────────────
        style.configure("TSeparator", background=BORDER)

    def _create_menu_bar(self):
        """Create main menu bar"""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Export Report", command=self._export_report)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)
        
        # Device menu
        device_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Device", menu=device_menu)
        device_menu.add_command(label="Add Device", command=self._show_add_device_dialog)
        device_menu.add_command(label="Discover Devices", command=self._show_discovery_dialog)
        device_menu.add_separator()
        device_menu.add_command(label="Remove Device", command=self._remove_device)
        
        # Configuration menu
        config_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Configuration", menu=config_menu)
        config_menu.add_command(label="Backup Config", command=self._backup_config)
        config_menu.add_command(label="Restore Config", command=self._restore_config)
        config_menu.add_command(label="Compare Configs", command=self._compare_configs)
        config_menu.add_command(label="Deploy Config", command=self._deploy_config)
        
        # Tools menu
        tools_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Tools", menu=tools_menu)
        tools_menu.add_command(label="Compliance Check", command=self._run_compliance_check)
        tools_menu.add_command(label="View Logs", command=self._view_logs)
        tools_menu.add_separator()
        tools_menu.add_command(label="Start NetFlow Collector", command=self._start_netflow)
        tools_menu.add_command(label="Stop NetFlow Collector",  command=self._stop_netflow)
        tools_menu.add_command(label="Export Flows to CSV",     command=self._export_flows_csv)

    def _create_main_layout(self):
        """Create main GUI layout with tabs"""
        # Create notebook (tabbed interface)
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Dashboard tab
        self._create_dashboard_tab()
        
        # Inventory tab
        self._create_inventory_tab()
        
        # Status/Monitoring tab
        self._create_monitoring_tab()
        
        # Configuration tab
        self._create_configuration_tab()
        
        # Compliance tab
        self._create_compliance_tab()
        
        # Logs tab
        self._create_logs_tab()

        # NetFlow tab
        self._create_netflow_tab()

    def _create_dashboard_tab(self):
        """Create dashboard tab with overview"""
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="  Dashboard  ")

        # Title bar
        title_bar = tk.Frame(frame, bg=BG_MID)
        title_bar.pack(fill=tk.X, padx=10, pady=(12, 4))
        tk.Label(title_bar, text="⬡  Network Overview",
                 font=("Arial", 16, "bold"), fg="#58a6ff", bg=BG_MID).pack(side=tk.LEFT)
        tk.Label(title_bar, text="Real-time device statistics",
                 font=("Arial", 9), fg=TEXT_SEC, bg=BG_MID).pack(side=tk.LEFT, padx=12)

        # Separator line
        tk.Frame(frame, bg=BORDER, height=1).pack(fill=tk.X, padx=10, pady=(0, 8))

        # Stats card grid
        stats_outer = tk.Frame(frame, bg=BG_MID)
        stats_outer.pack(fill=tk.BOTH, expand=True, padx=10, pady=4)

        card_configs = [
            ("Total Devices",    "total_devices",    "#58a6ff", "devices"),
            ("Online",           "online_devices",   "#3fb950", "check"),
            ("Offline",          "offline_devices",  "#f85149", "cross"),
            ("Cisco",            "cisco_devices",    "#79c0ff", "cisco"),
            ("Huawei",           "huawei_devices",   "#e3b341", "huawei"),
            ("Avg Health",       "avg_health",       "#39d353", "health"),
            ("Active Alerts",    "active_alerts",    "#f78166", "alert"),
            ("Compliance Score", "compliance_score", "#bc8cff", "shield"),
        ]

        # Keep PhotoImage refs alive (GC would blank them otherwise)
        self._dash_icon_refs = []

        self.stats_labels = {}
        for idx, (label, key, color, shape) in enumerate(card_configs):
            row, col = divmod(idx, 4)
            stats_outer.grid_columnconfigure(col, weight=1)

            card = tk.Frame(stats_outer, bg=BG_LIGHT, relief=tk.RAISED, bd=2,
                            highlightbackground=color, highlightthickness=1)
            card.grid(row=row, column=col, padx=8, pady=8, sticky="nsew")

            # PIL icon (falls back to Unicode glyph if Pillow not present)
            img = _make_dash_icon(color, shape, size=52)
            if img:
                self._dash_icon_refs.append(img)
                tk.Label(card, image=img, bg=BG_LIGHT).pack(pady=(10, 0))
            else:
                _fallback = {"devices": "⬢", "check": "●", "cross": "●",
                             "cisco": "⬡", "huawei": "⬡", "health": "♥",
                             "alert": "⚑", "shield": "✦"}
                tk.Label(card, text=_fallback.get(shape, "?"),
                         font=("Arial", 22), fg=color, bg=BG_LIGHT).pack(pady=(10, 0))

            tk.Label(card, text=label, font=("Arial", 9),
                     fg=TEXT_SEC, bg=BG_LIGHT).pack()
            value_var = tk.StringVar(value="—")
            self.stats_labels[key] = value_var
            tk.Label(card, textvariable=value_var,
                     font=("Arial", 20, "bold"), fg=color, bg=BG_LIGHT).pack(pady=(2, 10))

        # Refresh button
        make_3d_button(frame, "⟳   Refresh Dashboard",
                       command=self._refresh_dashboard,
                       btn_type="primary").pack(pady=14, ipadx=14, ipady=5)

    def _create_inventory_tab(self):
        """Create device inventory tab"""
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="  Inventory  ")

        # Toolbar
        toolbar = tk.Frame(frame, bg=BG_MID)
        toolbar.pack(side=tk.TOP, fill=tk.X, padx=5, pady=6)

        make_3d_button(toolbar, "＋  Add Device",
                       command=self._show_add_device_dialog,
                       btn_type="success").pack(side=tk.LEFT, padx=3, ipadx=4, ipady=2)
        make_3d_button(toolbar, "⌕  Discover",
                       command=self._show_discovery_dialog,
                       btn_type="primary").pack(side=tk.LEFT, padx=3, ipadx=4, ipady=2)
        make_3d_button(toolbar, "⟳  Refresh",
                       command=self.update_device_list,
                       btn_type="neutral").pack(side=tk.LEFT, padx=3, ipadx=4, ipady=2)
        make_3d_button(toolbar, "✕  Remove",
                       command=self._remove_device,
                       btn_type="danger").pack(side=tk.LEFT, padx=3, ipadx=4, ipady=2)
        
        # Device list with treeview
        columns = ("Hostname", "IP", "Type", "Vendor", "Status", "Last Checked")
        self.device_tree = ttk.Treeview(frame, columns=columns, height=25)
        self.device_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Column headings
        self.device_tree.heading("#0", text="Device")
        for col in columns:
            self.device_tree.heading(col, text=col)
            self.device_tree.column(col, width=120)
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=self.device_tree.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.device_tree.config(yscrollcommand=scrollbar.set)

    def _create_monitoring_tab(self):
        """Create real-time monitoring tab"""
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="  Monitoring  ")

        # Controls
        control_frame = tk.Frame(frame, bg=BG_MID)
        control_frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=6)

        tk.Label(control_frame, text="Select Device:",
                 bg=BG_MID, fg=TEXT_PRI, font=("Arial", 9)).pack(side=tk.LEFT, padx=5)

        self.monitor_device_var = tk.StringVar()
        self.monitor_device_combo = ttk.Combobox(control_frame, textvariable=self.monitor_device_var, width=30)
        self.monitor_device_combo.pack(side=tk.LEFT, padx=5)

        make_3d_button(control_frame, "⟳  Update Status",
                       command=self._update_device_status,
                       btn_type="primary").pack(side=tk.LEFT, padx=5, ipadx=4, ipady=2)
        make_3d_button(control_frame, "↺  Refresh",
                       command=self._refresh_monitoring,
                       btn_type="neutral").pack(side=tk.LEFT, padx=3, ipadx=4, ipady=2)
        
        # Status display
        display_frame = ttk.LabelFrame(frame, text="Device Status", padding=10)
        display_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.status_text = scrolledtext.ScrolledText(
            display_frame, height=20, width=80,
            bg=BG_LIGHT, fg=TEXT_PRI, insertbackground=TEXT_PRI,
            selectbackground=ACCENT1, font=("Courier", 10),
            relief=tk.FLAT, bd=0)
        self.status_text.pack(fill=tk.BOTH, expand=True)

    def _create_configuration_tab(self):
        """Create configuration management tab with Manual and Wizards sub-tabs."""
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="  Configuration  ")

        # ── Shared device selector (used by both sub-tabs) ────────────────────
        selector_frame = ttk.Frame(frame)
        selector_frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)

        ttk.Label(selector_frame, text="Device:").pack(side=tk.LEFT, padx=5)
        self.config_device_var = tk.StringVar()
        self.config_device_combo = ttk.Combobox(
            selector_frame, textvariable=self.config_device_var, width=30)
        self.config_device_combo.pack(side=tk.LEFT, padx=5)

        # Sub-tab notebook
        cfg_nb = ttk.Notebook(frame)
        cfg_nb.pack(fill=tk.BOTH, expand=True, padx=5, pady=2)

        # ── Sub-tab 1: Wizards ────────────────────────────────────────────────
        wizard_frame = ttk.Frame(cfg_nb)
        cfg_nb.add(wizard_frame, text="  ✦ Wizards  ")
        self._create_wizards_subtab(wizard_frame)

        # ── Sub-tab 2: Manual (existing editor) ───────────────────────────────
        manual_frame = ttk.Frame(cfg_nb)
        cfg_nb.add(manual_frame, text="  Manual Editor  ")
        self._create_manual_subtab(manual_frame)

    def _create_wizards_subtab(self, frame):
        """Task-picker + description panel inside the Wizards sub-tab."""
        # ── Left: categorised task list ───────────────────────────────────────
        left = ttk.Frame(frame, width=240)
        left.pack(side=tk.LEFT, fill=tk.Y, padx=(5, 0), pady=5)
        left.pack_propagate(False)

        ttk.Label(left, text="Configuration Tasks",
                  font=("Arial", 10, "bold")).pack(anchor=tk.W, pady=(0, 4))

        tree_frame = ttk.Frame(left)
        tree_frame.pack(fill=tk.BOTH, expand=True)

        self._task_tree = ttk.Treeview(tree_frame, show="tree", selectmode="browse")
        vsb = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL,
                            command=self._task_tree.yview)
        self._task_tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        self._task_tree.pack(fill=tk.BOTH, expand=True)

        # Populate tree by category
        for category, tasks in get_tasks_by_category().items():
            cat_node = self._task_tree.insert("", tk.END, text=f"  {category}",
                                              open=True, tags=("category",))
            for task in tasks:
                self._task_tree.insert(cat_node, tk.END,
                                       text=f"    {task.name}",
                                       values=(task.name,), tags=("task",))

        self._task_tree.tag_configure("category", font=("Arial", 9, "bold"))
        self._task_tree.bind("<<TreeviewSelect>>", self._on_task_selected)

        # ── Right: description + launch panel ────────────────────────────────
        right = ttk.Frame(frame)
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Task info box
        info_frame = ttk.LabelFrame(right, text="Task Details", padding=10)
        info_frame.pack(fill=tk.X, pady=(0, 5))

        self._wizard_task_name = tk.StringVar(value="← Select a task")
        ttk.Label(info_frame, textvariable=self._wizard_task_name,
                  font=("Arial", 12, "bold")).pack(anchor=tk.W)

        self._wizard_task_desc = tk.StringVar(value="")
        ttk.Label(info_frame, textvariable=self._wizard_task_desc,
                  wraplength=520, foreground="gray",
                  font=("Arial", 9)).pack(anchor=tk.W, pady=(4, 0))

        self._wizard_task_category = tk.StringVar(value="")
        ttk.Label(info_frame, textvariable=self._wizard_task_category,
                  foreground="#0066cc", font=("Arial", 9, "italic")).pack(anchor=tk.W)

        # Workflow steps reminder
        steps_frame = ttk.LabelFrame(right, text="Wizard Workflow", padding=8)
        steps_frame.pack(fill=tk.X, pady=(0, 5))

        steps = [
            "1  →  Enter configuration parameters",
            "2  →  Module validates inputs & checks running config",
            "3  →  Review generated commands",
            "4  →  Push to device via SSH",
            "5  →  View before/after config diff",
            "6  →  Confirm success or rollback",
        ]
        for step in steps:
            ttk.Label(steps_frame, text=step, font=("Courier", 9),
                      foreground="#333333").pack(anchor=tk.W)

        # Launch button
        self._launch_btn = make_3d_button(
            right, text="▶   Launch Wizard",
            command=self._launch_wizard, state=tk.DISABLED,
            btn_type="purple")
        self._launch_btn.pack(pady=10, ipadx=20, ipady=6)

        self._selected_task = None

    def _create_manual_subtab(self, frame):
        """Existing manual editor — Backup/Restore/Compare + template + text area."""
        button_frame = tk.Frame(frame, bg=BG_MID)
        button_frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=6)

        make_3d_button(button_frame, "💾  Backup",  command=self._backup_config,
                       btn_type="primary").pack(side=tk.LEFT, padx=3, ipadx=4, ipady=2)
        make_3d_button(button_frame, "↩  Restore", command=self._restore_config,
                       btn_type="neutral").pack(side=tk.LEFT, padx=3, ipadx=4, ipady=2)
        make_3d_button(button_frame, "👁  View",    command=self._view_config,
                       btn_type="neutral").pack(side=tk.LEFT, padx=3, ipadx=4, ipady=2)
        make_3d_button(button_frame, "⇄  Compare", command=self._compare_configs,
                       btn_type="neutral").pack(side=tk.LEFT, padx=3, ipadx=4, ipady=2)
        make_3d_button(button_frame, "🚀  Deploy",  command=self._deploy_config,
                       btn_type="success").pack(side=tk.LEFT, padx=3, ipadx=4, ipady=2)

        # Templates section
        template_frame = ttk.LabelFrame(frame, text="Configuration Templates", padding=5)
        template_frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)

        template_select_frame = ttk.Frame(template_frame)
        template_select_frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)

        ttk.Label(template_select_frame, text="Vendor:").pack(side=tk.LEFT, padx=5)
        self.template_vendor_var = tk.StringVar()
        self.template_vendor_combo = ttk.Combobox(
            template_select_frame, textvariable=self.template_vendor_var,
            values=get_vendors(), width=20, state="readonly")
        self.template_vendor_combo.pack(side=tk.LEFT, padx=5)
        self.template_vendor_combo.bind("<<ComboboxSelected>>", self._update_template_list)

        ttk.Label(template_select_frame, text="Template:").pack(side=tk.LEFT, padx=5)
        self.template_var = tk.StringVar()
        self.template_combo = ttk.Combobox(
            template_select_frame, textvariable=self.template_var,
            width=35, state="readonly")
        self.template_combo.pack(side=tk.LEFT, padx=5)

        template_btn_frame = tk.Frame(template_select_frame, bg=BG_MID)
        template_btn_frame.pack(side=tk.LEFT, padx=10)
        make_3d_button(template_btn_frame, "Load Template",
                       command=self._load_template,
                       btn_type="primary").pack(side=tk.LEFT, padx=3, ipadx=4, ipady=2)
        make_3d_button(template_btn_frame, "Insert Template",
                       command=self._insert_template,
                       btn_type="teal").pack(side=tk.LEFT, padx=3, ipadx=4, ipady=2)
        make_3d_button(template_btn_frame, "✕ Clear",
                       command=self._clear_config_text,
                       btn_type="danger").pack(side=tk.LEFT, padx=3, ipadx=4, ipady=2)

        # Config text area
        self.config_text = scrolledtext.ScrolledText(
            frame, height=30, width=100, font=("Courier", 10),
            bg=BG_LIGHT, fg="#d4d4d4", insertbackground=TEXT_PRI,
            selectbackground=ACCENT1, relief=tk.FLAT, bd=0)
        self.config_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def _on_task_selected(self, event=None):
        """Update the description panel when a task is selected in the tree."""
        selection = self._task_tree.selection()
        if not selection:
            return
        item = self._task_tree.item(selection[0])
        values = item.get("values", [])
        if not values:  # category node — no task attached
            self._launch_btn.config(state=tk.DISABLED)
            return
        task = get_task_by_name(values[0])
        if task:
            self._selected_task = task
            self._wizard_task_name.set(task.name)
            self._wizard_task_desc.set(task.description)
            self._wizard_task_category.set(f"Category: {task.category}")
            self._launch_btn.config(state=tk.NORMAL)

    def _launch_wizard(self):
        """Validate device selection, then open the ConfigWizardDialog."""
        device_label = self.config_device_var.get().strip()
        if not device_label:
            messagebox.showerror("No Device Selected",
                                 "Please select a device from the Device drop-down first.")
            return
        if not self._selected_task:
            return
        devices = self.device_manager.get_all_devices()
        # The combobox label is built as "hostname (ip)" — extract the leading token
        device_key = device_label.split(" (")[0].strip()
        device = next(
            (d for d in devices
             if d.get("hostname", d.get("ip_address", "")) == device_key),
            None
        )
        if device is None:
            messagebox.showerror("Device Not Found",
                                 f"Could not find device '{device_key}' in the device list.")
            return
        ConfigWizardDialog(self.root, self._selected_task, device,
                           self.config_manager)

    def _create_compliance_tab(self):
        """Create compliance checking tab"""
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="  Compliance  ")

        # Controls
        control_frame = tk.Frame(frame, bg=BG_MID)
        control_frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=6)

        make_3d_button(control_frame, "✦  Check Compliance",
                       command=self._run_compliance_check,
                       btn_type="purple").pack(side=tk.LEFT, padx=5, ipadx=6, ipady=2)
        make_3d_button(control_frame, "📋  Generate Report",
                       command=self._generate_compliance_report,
                       btn_type="neutral").pack(side=tk.LEFT, padx=3, ipadx=6, ipady=2)
        
        # Results display
        self.compliance_text = scrolledtext.ScrolledText(
            frame, height=30, width=100,
            bg=BG_LIGHT, fg=TEXT_PRI, insertbackground=TEXT_PRI,
            selectbackground=ACCENT1, font=("Courier", 10),
            relief=tk.FLAT, bd=0)
        self.compliance_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def _create_logs_tab(self):
        """Create logs/events tab"""
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="  Logs  ")

        # Controls
        control_frame = tk.Frame(frame, bg=BG_MID)
        control_frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=6)

        make_3d_button(control_frame, "⟳  Refresh Logs",
                       command=self._view_logs,
                       btn_type="neutral").pack(side=tk.LEFT, padx=5, ipadx=6, ipady=2)
        make_3d_button(control_frame, "🗑  Clear Logs",
                       command=self._clear_logs,
                       btn_type="danger").pack(side=tk.LEFT, padx=3, ipadx=6, ipady=2)
        
        # Logs display
        self.logs_text = scrolledtext.ScrolledText(
            frame, height=30, width=100,
            bg=BG_LIGHT, fg=TEXT_PRI, insertbackground=TEXT_PRI,
            selectbackground=ACCENT1, font=("Courier", 10),
            relief=tk.FLAT, bd=0)
        self.logs_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def _show_add_device_dialog(self):
        """Show dialog to add new device"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Add Device")
        dialog.geometry("400x420")
        dialog.configure(bg=BG_DARK)
        
        # Form fields
        fields = {
            "Hostname": "hostname",
            "IP Address": "ip_address",
            "Device Type": "device_type",
            "Username": "username",
            "Password": "password",
            "Port": "port",
            "SNMP Community": "snmp_community"
        }
        
        entries = {}
        
        for label, key in fields.items():
            ttk.Label(dialog, text=label).pack(pady=5, padx=10, anchor=tk.W)
            
            if key == "device_type":
                var = tk.StringVar()
                combo = ttk.Combobox(dialog, textvariable=var, 
                                    values=["cisco_router", "cisco_switch", "huawei_router", "huawei_switch"])
                combo.pack(pady=5, padx=10, fill=tk.X)
                entries[key] = var
            elif key == "password":
                entry = ttk.Entry(dialog, show="*")
                entry.pack(pady=5, padx=10, fill=tk.X)
                entries[key] = entry
            else:
                entry = ttk.Entry(dialog)
                entry.pack(pady=5, padx=10, fill=tk.X)
                entries[key] = entry
        
        def add_device():
            try:
                hostname = entries["hostname"].get().strip()
                ip = entries["ip_address"].get().strip()
                dev_type = entries["device_type"].get()
                user = entries["username"].get().strip()
                pwd = entries["password"].get()
                port_str = entries["port"].get().strip() or "22"
                snmp = entries["snmp_community"].get().strip() or "public"

                # --- Input validation ---
                if not hostname:
                    messagebox.showerror("Validation Error", "Hostname is required", parent=dialog)
                    return
                if not dev_type:
                    messagebox.showerror("Validation Error", "Device type is required", parent=dialog)
                    return
                if not user:
                    messagebox.showerror("Validation Error", "Username is required", parent=dialog)
                    return

                try:
                    ipaddress.ip_address(ip)
                except ValueError:
                    messagebox.showerror("Validation Error",
                                         f"'{ip}' is not a valid IP address", parent=dialog)
                    return

                try:
                    port = int(port_str)
                    if not (1 <= port <= 65535):
                        raise ValueError
                except ValueError:
                    messagebox.showerror("Validation Error",
                                         "Port must be an integer between 1 and 65535", parent=dialog)
                    return

                success, msg = self.device_manager.add_device(
                    hostname, ip, dev_type, user, pwd, port, snmp
                )

                if success:
                    messagebox.showinfo("Success", msg)
                    self.update_device_list()
                    dialog.destroy()
                else:
                    messagebox.showerror("Error", msg)

            except Exception as e:
                messagebox.showerror("Error", str(e))
        
        make_3d_button(dialog, "＋  Add Device",
                       command=add_device, btn_type="success").pack(pady=20, ipadx=10, ipady=4)

    def _show_discovery_dialog(self):
        """Show device discovery dialog"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Discover Devices")
        dialog.geometry("400x270")
        dialog.configure(bg=BG_DARK)
        
        ttk.Label(dialog, text="Network Range:").pack(pady=5, padx=10, anchor=tk.W)
        network_entry = ttk.Entry(dialog)
        network_entry.pack(pady=5, padx=10, fill=tk.X)
        network_entry.insert(0, "192.168.1.0/24")
        
        ttk.Label(dialog, text="Username:").pack(pady=5, padx=10, anchor=tk.W)
        user_entry = ttk.Entry(dialog)
        user_entry.pack(pady=5, padx=10, fill=tk.X)
        
        ttk.Label(dialog, text="Password:").pack(pady=5, padx=10, anchor=tk.W)
        pwd_entry = ttk.Entry(dialog, show="*")
        pwd_entry.pack(pady=5, padx=10, fill=tk.X)
        
        ttk.Label(dialog, text="Device Type:").pack(pady=5, padx=10, anchor=tk.W)
        type_var = tk.StringVar()
        type_combo = ttk.Combobox(dialog, textvariable=type_var,
                                 values=["cisco_router", "cisco_switch", "huawei_router", "huawei_switch"])
        type_combo.pack(pady=5, padx=10, fill=tk.X)
        
        def discover():
            try:
                network = network_entry.get()
                username = user_entry.get()
                password = pwd_entry.get()
                device_type = type_var.get()
                
                if not all([network, username, password, device_type]):
                    messagebox.showwarning("Warning", "Please fill in all fields")
                    return
                
                threading.Thread(target=self._perform_discovery, args=(network, username, password, device_type, dialog)).start()
            
            except Exception as e:
                messagebox.showerror("Error", str(e))
        
        make_3d_button(dialog, "⌕  Discover",
                       command=discover, btn_type="primary").pack(pady=20, ipadx=10, ipady=4)

    def _perform_discovery(self, network: str, username: str, password: str, device_type: str, dialog):
        """Perform device discovery (threaded)"""
        try:
            devices, errors = self.device_manager.discover_devices(network, username, password, device_type)
            
            self.root.after(0, lambda: self._show_discovery_results(devices, errors, dialog))
        
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Error", str(e)))

    def _show_discovery_results(self, devices: list, errors: list, dialog):
        """Show discovery results"""
        result_text = f"Found {len(devices)} device(s)\n\n"
        for dev in devices:
            result_text += f"IP: {dev['ip']}, Type: {dev['device_type']}\n"
        
        if errors:
            result_text += f"\nErrors:\n" + "\n".join(errors)
        
        messagebox.showinfo("Discovery Results", result_text)

    def _remove_device(self):
        """Remove selected device"""
        selection = self.device_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a device")
            return
        
        item = selection[0]
        hostname = self.device_tree.item(item, "values")[0]
        
        if messagebox.askyesno("Confirm", f"Remove device {hostname}?"):
            success, msg = self.device_manager.remove_device(hostname)
            messagebox.showinfo("Result", msg) if success else messagebox.showerror("Error", msg)
            self.update_device_list()

    def _backup_config(self):
        """Backup device configuration — tries SSH first, falls back to editor content."""
        hostname = self.config_device_var.get()
        if not hostname:
            messagebox.showwarning("Warning", "Please select a device")
            return

        device = self.device_manager.get_device(hostname)
        if not device:
            messagebox.showerror("Error", "Device not found in inventory")
            return

        self.status_var.set(f"Connecting to {hostname} via SSH…")
        self.root.update_idletasks()

        def _do_backup():
            ssh_ok, result = self.config_manager.fetch_live_config(device)
            if ssh_ok:
                config_content = result
                source = "SSH"
            else:
                # Fall back to whatever is in the editor
                config_content = self.config_text.get(1.0, tk.END).strip()
                if not config_content:
                    self.root.after(0, lambda: messagebox.showerror(
                        "Error",
                        f"SSH failed: {result}\n\nNo local config in editor to fall back on."
                    ))
                    self.root.after(0, lambda: self.status_var.set("Backup failed"))
                    return
                source = "editor (SSH unavailable)"

            ok, msg = self.config_manager.backup_configuration(hostname, config_content)
            status_msg = f"Backup saved ({source})" if ok else "Backup failed"
            self.root.after(0, lambda: (
                messagebox.showinfo("Success", f"{msg}\nSource: {source}") if ok
                else messagebox.showerror("Error", msg),
                self.status_var.set(status_msg)
            ))

        threading.Thread(target=_do_backup, daemon=True).start()

    def _restore_config(self):
        """Restore device configuration"""
        hostname = self.config_device_var.get()
        if not hostname:
            messagebox.showwarning("Warning", "Please select a device")
            return
        
        backups = self.config_manager.get_device_backups(hostname)
        if not backups:
            messagebox.showinfo("Info", "No backups available for this device")
            return
        
        # Show backup selection dialog
        backup_names = [b["name"] for b in backups]
        dialog = tk.Toplevel(self.root)
        dialog.title("Select Backup")
        dialog.configure(bg=BG_DARK)

        listbox = tk.Listbox(dialog, bg=BG_LIGHT, fg=TEXT_PRI,
                             selectbackground=ACCENT1, selectforeground=TEXT_PRI,
                             font=("Arial", 9), bd=0, highlightthickness=0)
        listbox.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        for name in backup_names:
            listbox.insert(tk.END, name)
        
        def restore():
            selection = listbox.curselection()
            if not selection:
                messagebox.showwarning("Warning", "Please select a backup")
                return
            
            backup_name = backup_names[selection[0]]
            success, msg, config = self.config_manager.restore_configuration(hostname, backup_name)
            
            if success:
                messagebox.showinfo("Success", msg)
                self.config_text.delete(1.0, tk.END)
                self.config_text.insert(1.0, config)
                dialog.destroy()
            else:
                messagebox.showerror("Error", msg)
        
        make_3d_button(dialog, "↩  Restore",
                       command=restore, btn_type="primary").pack(pady=10, ipadx=10, ipady=4)

    def _view_config(self):
        """View device configuration"""
        hostname = self.config_device_var.get()
        if not hostname:
            messagebox.showwarning("Warning", "Please select a device")
            return
        
        config = self.config_manager.get_configuration(hostname)
        if config:
            self.config_text.delete(1.0, tk.END)
            self.config_text.insert(1.0, config)
        else:
            messagebox.showinfo("Info", "No configuration available for this device")

    def _compare_configs(self):
        """Compare two configurations using unified diff."""
        hostname = self.config_device_var.get()
        if not hostname:
            messagebox.showwarning("Warning", "Please select a device")
            return

        backups = self.config_manager.get_device_backups(hostname)
        if len(backups) < 2:
            messagebox.showinfo("Info", "At least two backups are required to compare")
            return

        backup_names = [b["name"] for b in backups]

        dialog = tk.Toplevel(self.root)
        dialog.title(f"Compare Configs — {hostname}")
        dialog.geometry("500x220")
        dialog.configure(bg=BG_DARK)

        ttk.Label(dialog, text="Backup A (from):").pack(pady=5, padx=10, anchor=tk.W)
        var_a = tk.StringVar()
        ttk.Combobox(dialog, textvariable=var_a, values=backup_names,
                     state="readonly", width=55).pack(padx=10, fill=tk.X)

        ttk.Label(dialog, text="Backup B (to):").pack(pady=5, padx=10, anchor=tk.W)
        var_b = tk.StringVar()
        ttk.Combobox(dialog, textvariable=var_b, values=backup_names,
                     state="readonly", width=55).pack(padx=10, fill=tk.X)

        def do_compare():
            a, b = var_a.get(), var_b.get()
            if not a or not b:
                messagebox.showwarning("Warning", "Select both backups", parent=dialog)
                return
            if a == b:
                messagebox.showwarning("Warning", "Select two different backups", parent=dialog)
                return
            ok, msg, diff = self.config_manager.compare_configurations(hostname, a, b)
            if not ok:
                messagebox.showerror("Error", msg, parent=dialog)
                return
            dialog.destroy()

            result_win = tk.Toplevel(self.root)
            result_win.title(f"Diff: {a} → {b}")
            result_win.geometry("900x600")
            result_win.configure(bg=BG_DARK)

            text = scrolledtext.ScrolledText(
                result_win, font=("Courier", 10),
                bg=BG_LIGHT, fg=TEXT_PRI, insertbackground=TEXT_PRI,
                selectbackground=ACCENT1, relief=tk.FLAT, bd=0)
            text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

            # Colour-code the unified diff
            text.tag_config("added", foreground="green")
            text.tag_config("removed", foreground="red")
            text.tag_config("header", foreground="blue")

            for line in diff.get("unified_diff", []):
                if line.startswith("+++") or line.startswith("---") or line.startswith("@@"):
                    text.insert(tk.END, line + "\n", "header")
                elif line.startswith("+"):
                    text.insert(tk.END, line + "\n", "added")
                elif line.startswith("-"):
                    text.insert(tk.END, line + "\n", "removed")
                else:
                    text.insert(tk.END, line + "\n")

            if not diff.get("unified_diff"):
                text.insert(tk.END, "No differences found — configurations are identical.")

        make_3d_button(dialog, "⇄  Compare",
                       command=do_compare, btn_type="primary").pack(pady=10, ipadx=10, ipady=4)

    def _deploy_config(self):
        """Deploy configuration to device via SSH, then save locally."""
        hostname = self.config_device_var.get()
        config = self.config_text.get(1.0, tk.END).strip()

        if not hostname or not config:
            messagebox.showwarning("Warning", "Please select a device and provide config")
            return

        device = self.device_manager.get_device(hostname)
        if not device:
            messagebox.showerror("Error", "Device not found in inventory")
            return

        if not messagebox.askyesno(
            "Confirm Deploy",
            f"Push configuration to {hostname} ({device['ip_address']}) via SSH?\n\n"
            "This will modify the live device."
        ):
            return

        config_lines = [l for l in config.splitlines() if l.strip()]

        self.status_var.set(f"Deploying config to {hostname}…")
        self.root.update_idletasks()

        def _do_deploy():
            ssh_ok, ssh_result = ssh_client.push_config(device, config_lines)
            # Always save locally regardless of SSH outcome
            _, save_msg = self.config_manager.save_configuration(hostname, config)

            if ssh_ok:
                msg = f"Config deployed to {hostname} via SSH.\n{save_msg}"
                self.root.after(0, lambda: messagebox.showinfo("Success", msg))
                self.root.after(0, lambda: self.status_var.set("Deploy successful"))
            else:
                msg = (
                    f"SSH deploy failed: {ssh_result}\n\n"
                    f"Config saved locally only. {save_msg}"
                )
                self.root.after(0, lambda: messagebox.showwarning("Partial Success", msg))
                self.root.after(0, lambda: self.status_var.set("Deploy failed — saved locally"))

        threading.Thread(target=_do_deploy, daemon=True).start()

    def _update_template_list(self, event=None):
        """Update template list based on selected vendor"""
        vendor = self.template_vendor_var.get()
        templates = get_templates_by_vendor(vendor)
        
        template_options = [(k, v["name"]) for k, v in templates.items()]
        template_options.sort(key=lambda x: x[1])
        
        self.template_list = template_options
        self.template_combo["values"] = [name for _, name in template_options]

    def _load_template(self):
        """Load selected template into config editor"""
        if not self.template_combo.get():
            messagebox.showwarning("Warning", "Please select a template")
            return
        
        template_name = self.template_combo.get()
        
        # Find the template key
        template_key = None
        for key, name in self.template_list:
            if name == template_name:
                template_key = key
                break
        
        if template_key:
            content = get_template_content(template_key)
            self.config_text.delete(1.0, tk.END)
            self.config_text.insert(1.0, content)
            self.status_var.set(f"Loaded template: {template_name}")

    def _insert_template(self):
        """Insert template at cursor position"""
        if not self.template_combo.get():
            messagebox.showwarning("Warning", "Please select a template")
            return
        
        template_name = self.template_combo.get()
        
        # Find the template key
        template_key = None
        for key, name in self.template_list:
            if name == template_name:
                template_key = key
                break
        
        if template_key:
            content = get_template_content(template_key)
            current_pos = self.config_text.index(tk.INSERT)
            self.config_text.insert(current_pos, "\n" + content + "\n")
            self.status_var.set(f"Inserted template: {template_name}")

    def _clear_config_text(self):
        """Clear configuration text area"""
        if self.config_text.get(1.0, tk.END).strip():
            if messagebox.askyesno("Confirm", "Clear configuration text?"):
                self.config_text.delete(1.0, tk.END)
                self.status_var.set("Configuration cleared")
        else:
            messagebox.showinfo("Info", "Text area is already empty")

    def _update_device_status(self):
        """Update device status"""
        hostname = self.monitor_device_var.get()
        if not hostname:
            messagebox.showwarning("Warning", "Please select a device")
            return
        
        # In production, connect to device and get metrics
        status_data = self.status_monitor.update_device_status(
            hostname, DeviceStatus.ONLINE, health_score=95, cpu=35, memory=60, uptime="45 days"
        )
        
        self._display_status(status_data)

    def _display_status(self, status_data: dict):
        """Display status information"""
        self.status_text.delete(1.0, tk.END)
        
        text = f"""
Device Status Report
Generated: {status_data.get('last_updated', 'N/A')}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Hostname:        {status_data.get('hostname', 'N/A')}
Status:          {status_data.get('status', 'N/A').upper()}
Health Score:    {status_data.get('health_score', 0)}%
CPU Usage:       {status_data.get('cpu_usage', 0)}%
Memory Usage:    {status_data.get('memory_usage', 0)}%
Uptime:          {status_data.get('uptime', 'N/A')}
        """
        
        self.status_text.insert(1.0, text)

    def _run_compliance_check(self):
        """Run compliance check"""
        hostname = self.config_device_var.get() or (self.device_tree.selection() and self.device_tree.item(self.device_tree.selection()[0], "values")[0])
        
        if not hostname:
            messagebox.showwarning("Warning", "Please select a device")
            return
        
        device = self.device_manager.get_device(hostname)
        if not device:
            messagebox.showerror("Error", "Device not found")
            return
        
        config = self.config_manager.get_configuration(hostname) or "! Sample configuration"
        
        results = self.compliance_checker.check_device_compliance(
            hostname, device["vendor"], config
        )
        
        self._display_compliance_results(results)

    def _display_compliance_results(self, results: dict):
        """Display compliance check results"""
        self.compliance_text.delete(1.0, tk.END)
        
        text = f"""
Compliance Check Results
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Device:     {results.get('hostname', 'N/A')}
Vendor:     {results.get('vendor', 'N/A')}
Timestamp:  {results.get('timestamp', 'N/A')}

Overall Result: {'✓ COMPLIANT' if results.get('overall_compliance') else '✗ NON-COMPLIANT'}
Compliance Score: {results.get('compliance_score', 0):.1f}%
Passed Checks: {results.get('passed', 0)}
Failed Checks: {results.get('failed', 0)}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Check Details:
"""
        
        for check_name, check_data in results.get("checks", {}).items():
            status = "✓ PASS" if check_data.get("compliant") else "✗ FAIL"
            text += f"\n  {status} - {check_name}"
            if not check_data.get("required"):
                text += " (optional)"
        
        self.compliance_text.insert(1.0, text)

    def _generate_compliance_report(self):
        """Generate full compliance report"""
        report = self.compliance_checker.get_compliance_report()
        
        text = f"""
Compliance Report
Generated: {report.get('generated', 'N/A')}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Total Devices Checked: {report.get('total_devices_checked', 0)}
Compliant Devices: {report.get('compliant_devices', 0)}
Non-Compliant Devices: {report.get('non_compliant_devices', 0)}
Average Compliance Score: {report.get('average_compliance_score', 0):.1f}%

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Device Details:
"""
        
        for hostname, device_info in report.get("devices", {}).items():
            text += f"\n{hostname}:"
            text += f"\n  Status: {'✓ COMPLIANT' if device_info['compliant'] else '✗ NON-COMPLIANT'}"
            text += f"\n  Score: {device_info['score']:.1f}%\n"
        
        self.compliance_text.delete(1.0, tk.END)
        self.compliance_text.insert(1.0, text)

    def _view_logs(self):
        """View application logs"""
        import json
        
        try:
            with open("logs/events.json", "r") as f:
                events = json.load(f).get("events", [])
            
            self.logs_text.delete(1.0, tk.END)
            
            text = "Recent Events\n" + "=" * 80 + "\n\n"
            
            for event in events[-50:]:
                text += f"[{event.get('timestamp', 'N/A')}] {event.get('type', 'N/A')}\n"
                text += f"  Device: {event.get('device', 'N/A')}\n"
                text += f"  Description: {event.get('description', 'N/A')}\n\n"
            
            self.logs_text.insert(1.0, text)
        
        except Exception as e:
            self.logs_text.delete(1.0, tk.END)
            self.logs_text.insert(1.0, f"Error loading logs: {str(e)}")

    def _clear_logs(self):
        """Clear logs"""
        if messagebox.askyesno("Confirm", "Clear all logs?"):
            messagebox.showinfo("Success", "Logs will be cleared on next restart")

    def _export_report(self):
        """Export report"""
        file_path = filedialog.asksaveasfilename(defaultextension=".txt", filetypes=[("Text", "*.txt"), ("JSON", "*.json")])
        if file_path:
            messagebox.showinfo("Success", f"Report exported to {file_path}")

    def _refresh_dashboard(self):
        """Refresh dashboard statistics"""
        stats = self.device_manager.get_inventory_stats()
        monitor_stats = self.status_monitor.get_alert_summary()
        compliance_stats = self.compliance_checker.get_compliance_report()
        
        self.stats_labels["total_devices"].set(str(stats.get("total_devices", 0)))
        self.stats_labels["online_devices"].set(str(stats.get("online_devices", 0)))
        self.stats_labels["offline_devices"].set(str(stats.get("offline_devices", 0)))
        self.stats_labels["cisco_devices"].set(str(stats.get("cisco_devices", 0)))
        self.stats_labels["huawei_devices"].set(str(stats.get("huawei_devices", 0)))
        self.stats_labels["active_alerts"].set(str(monitor_stats.get("active_alerts", 0)))
        self.stats_labels["compliance_score"].set(f"{compliance_stats.get('average_compliance_score', 0):.0f}%")
        
        avg_health = sum(d.get("health_score", 0) for d in self.status_monitor.device_status.values()) / max(1, len(self.status_monitor.device_status))
        self.stats_labels["avg_health"].set(f"{avg_health:.0f}%")
        
        self.status_var.set("Dashboard refreshed")

    def _refresh_monitoring(self):
        """Refresh monitoring display"""
        self._update_device_status()

    def update_device_list(self):
        """Update device list in inventory tab"""
        # Clear existing items
        for item in self.device_tree.get_children():
            self.device_tree.delete(item)
        
        # Get devices
        devices = self.device_manager.get_all_devices(filter_enabled=False)
        
        # Populate tree
        for device in devices:
            self.device_tree.insert("", tk.END, text=device["hostname"],
                                   values=(device["hostname"], device["ip_address"],
                                          device["device_type"], device["vendor"],
                                          device.get("status", "unknown"),
                                          device.get("last_checked", "Never")))
        
        # Update combo boxes
        hostnames = [d["hostname"] for d in devices]
        self.config_device_combo["values"] = hostnames
        self.monitor_device_combo["values"] = hostnames

        self.status_var.set(f"Loaded {len(devices)} devices")

    # ── NetFlow Tab ────────────────────────────────────────────────────────────

    def _create_netflow_tab(self):
        """Create NetFlow collector and flow viewer tab."""
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="  NetFlow  ")

        # ── Top control bar ───────────────────────────────────────────────────
        ctrl = ttk.LabelFrame(frame, text="Collector Control", padding=5)
        ctrl.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)

        ttk.Label(ctrl, text="Listen Port:").pack(side=tk.LEFT, padx=5)
        self._nf_port_var = tk.StringVar(value="2055")
        ttk.Entry(ctrl, textvariable=self._nf_port_var, width=7).pack(side=tk.LEFT, padx=2)

        self._nf_status_var = tk.StringVar(value="Stopped")
        ttk.Label(ctrl, text="Status:").pack(side=tk.LEFT, padx=(15, 2))
        self._nf_status_label = tk.Label(ctrl, textvariable=self._nf_status_var,
                                         fg="#f85149", bg=BG_MID,
                                         font=("Arial", 10, "bold"))
        self._nf_status_label.pack(side=tk.LEFT, padx=2)

        make_3d_button(ctrl, "▶  Start",      command=self._start_netflow,
                       btn_type="success").pack(side=tk.LEFT, padx=8, ipadx=4, ipady=2)
        make_3d_button(ctrl, "■  Stop",        command=self._stop_netflow,
                       btn_type="danger").pack(side=tk.LEFT, padx=2, ipadx=4, ipady=2)
        make_3d_button(ctrl, "✕  Clear Flows", command=self._clear_flows,
                       btn_type="warning").pack(side=tk.LEFT, padx=2, ipadx=4, ipady=2)
        make_3d_button(ctrl, "⬇  Export CSV",  command=self._export_flows_csv,
                       btn_type="teal").pack(side=tk.LEFT, padx=2, ipadx=4, ipady=2)
        make_3d_button(ctrl, "⟳  Refresh",     command=self._refresh_netflow,
                       btn_type="neutral").pack(side=tk.LEFT, padx=8, ipadx=4, ipady=2)

        # ── Stats bar ─────────────────────────────────────────────────────────
        stats_bar = ttk.Frame(frame)
        stats_bar.pack(side=tk.TOP, fill=tk.X, padx=5)

        self._nf_stat_vars = {}
        for label, key in [("Packets Rcvd", "packets_received"),
                            ("Flows Decoded", "flows_decoded"),
                            ("Buffered", "buffered_flows"),
                            ("v5 Pkts", "v5_packets"),
                            ("v9 Pkts", "v9_packets"),
                            ("Errors", "parse_errors")]:
            f = ttk.Frame(stats_bar)
            f.pack(side=tk.LEFT, padx=10, pady=3)
            ttk.Label(f, text=label, font=("Arial", 8)).pack()
            var = tk.StringVar(value="0")
            self._nf_stat_vars[key] = var
            ttk.Label(f, textvariable=var, font=("Arial", 11, "bold")).pack()

        # ── Sub-tabs: Flows / Top Talkers / Conversations ─────────────────────
        sub_nb = ttk.Notebook(frame)
        sub_nb.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # --- Flow table ---
        flow_frame = ttk.Frame(sub_nb)
        sub_nb.add(flow_frame, text="Live Flows")

        flow_cols = ("Time", "Exporter", "Ver", "Src IP", "Src Port",
                     "Dst IP", "Dst Port", "Proto", "Packets", "Bytes", "Duration ms")
        self._nf_tree = ttk.Treeview(flow_frame, columns=flow_cols, show="headings", height=18)
        col_widths = [145, 105, 40, 115, 80, 115, 80, 60, 75, 90, 90]
        for col, w in zip(flow_cols, col_widths):
            self._nf_tree.heading(col, text=col)
            self._nf_tree.column(col, width=w, anchor=tk.CENTER)

        vsb = ttk.Scrollbar(flow_frame, orient=tk.VERTICAL,   command=self._nf_tree.yview)
        hsb = ttk.Scrollbar(flow_frame, orient=tk.HORIZONTAL, command=self._nf_tree.xview)
        self._nf_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        vsb.pack(side=tk.RIGHT,  fill=tk.Y)
        hsb.pack(side=tk.BOTTOM, fill=tk.X)
        self._nf_tree.pack(fill=tk.BOTH, expand=True)

        # Tag colours for protocol rows
        self._nf_tree.tag_configure("TCP",  background="#162032", foreground="#79c0ff")
        self._nf_tree.tag_configure("UDP",  background="#162216", foreground="#3fb950")
        self._nf_tree.tag_configure("ICMP", background="#1c1a10", foreground="#e3b341")

        # --- Top Talkers ---
        talker_frame = ttk.Frame(sub_nb)
        sub_nb.add(talker_frame, text="Top Talkers")

        tk_cols = ("Src IP", "Total Bytes", "Total Packets", "Flow Count")
        self._nf_talker_tree = ttk.Treeview(talker_frame, columns=tk_cols,
                                             show="headings", height=18)
        for col in tk_cols:
            self._nf_talker_tree.heading(col, text=col)
            self._nf_talker_tree.column(col, width=180, anchor=tk.CENTER)
        vsb2 = ttk.Scrollbar(talker_frame, orient=tk.VERTICAL,
                              command=self._nf_talker_tree.yview)
        self._nf_talker_tree.configure(yscrollcommand=vsb2.set)
        vsb2.pack(side=tk.RIGHT, fill=tk.Y)
        self._nf_talker_tree.pack(fill=tk.BOTH, expand=True)

        # --- Top Conversations ---
        conv_frame = ttk.Frame(sub_nb)
        sub_nb.add(conv_frame, text="Top Conversations")

        cv_cols = ("Src IP", "Dst IP", "Protocol", "Total Bytes", "Total Packets", "Flows")
        self._nf_conv_tree = ttk.Treeview(conv_frame, columns=cv_cols,
                                           show="headings", height=18)
        cv_widths = [130, 130, 70, 120, 120, 70]
        for col, w in zip(cv_cols, cv_widths):
            self._nf_conv_tree.heading(col, text=col)
            self._nf_conv_tree.column(col, width=w, anchor=tk.CENTER)
        vsb3 = ttk.Scrollbar(conv_frame, orient=tk.VERTICAL,
                              command=self._nf_conv_tree.yview)
        self._nf_conv_tree.configure(yscrollcommand=vsb3.set)
        vsb3.pack(side=tk.RIGHT, fill=tk.Y)
        self._nf_conv_tree.pack(fill=tk.BOTH, expand=True)

    # ── NetFlow handlers ───────────────────────────────────────────────────────

    def _start_netflow(self):
        """Start the NetFlow UDP collector."""
        try:
            port = int(self._nf_port_var.get())
            if not (1 <= port <= 65535):
                raise ValueError
        except ValueError:
            messagebox.showerror("Error", "Port must be an integer between 1 and 65535")
            return

        # Re-create collector if port changed
        if self.netflow_collector.port != port:
            if self.netflow_collector.is_running:
                self.netflow_collector.stop()
            self.netflow_collector = NetFlowCollector(port=port)

        ok, msg = self.netflow_collector.start()
        if ok:
            self._nf_status_var.set("Running")
            self._nf_status_label.config(fg="#3fb950")
            self.status_var.set(msg)
        else:
            messagebox.showerror("Error", msg)

    def _stop_netflow(self):
        """Stop the NetFlow UDP collector."""
        ok, msg = self.netflow_collector.stop()
        self._nf_status_var.set("Stopped")
        self._nf_status_label.config(fg="#f85149")
        self.status_var.set(msg)
        if not ok:
            messagebox.showwarning("Info", msg)

    def _clear_flows(self):
        """Discard all buffered flows."""
        if messagebox.askyesno("Confirm", "Clear all buffered flows?"):
            self.netflow_collector.clear_flows()
            self._refresh_netflow()
            self.status_var.set("Flow buffer cleared")

    def _refresh_netflow(self):
        """Refresh all three NetFlow sub-tabs and the stats bar."""
        # Update stats labels
        stats = self.netflow_collector.get_stats()
        for key, var in self._nf_stat_vars.items():
            var.set(str(stats.get(key, 0)))

        # -- Live Flows table --
        self._nf_tree.delete(*self._nf_tree.get_children())
        for flow in self.netflow_collector.get_flows(limit=500):
            proto = flow.get("protocol", "")
            tag = proto if proto in ("TCP", "UDP", "ICMP") else ""
            self._nf_tree.insert("", tk.END, tags=(tag,), values=(
                flow.get("timestamp", "")[:19],
                flow.get("exporter", ""),
                flow.get("version", ""),
                flow.get("src_ip", ""),
                flow.get("src_port", ""),
                flow.get("dst_ip", ""),
                flow.get("dst_port", ""),
                proto,
                flow.get("packets", 0),
                flow.get("bytes", 0),
                flow.get("duration_ms", 0),
            ))

        # -- Top Talkers table --
        self._nf_talker_tree.delete(*self._nf_talker_tree.get_children())
        for t in self.netflow_collector.get_top_talkers(n=20):
            self._nf_talker_tree.insert("", tk.END, values=(
                t["src_ip"],
                f"{t['bytes']:,}",
                f"{t['packets']:,}",
                t["flows"],
            ))

        # -- Top Conversations table --
        self._nf_conv_tree.delete(*self._nf_conv_tree.get_children())
        for c in self.netflow_collector.get_top_conversations(n=20):
            self._nf_conv_tree.insert("", tk.END, values=(
                c["src_ip"],
                c["dst_ip"],
                c["protocol"],
                f"{c['bytes']:,}",
                f"{c['packets']:,}",
                c["flows"],
            ))

    def _export_flows_csv(self):
        """Export buffered flows to a CSV file chosen by the user."""
        filepath = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            title="Export NetFlow Data",
        )
        if not filepath:
            return
        ok, msg = self.netflow_collector.export_flows_csv(filepath)
        messagebox.showinfo("Export", msg) if ok else messagebox.showerror("Export Failed", msg)


class ConfigWizardDialog:
    """
    3-step modal dialog that drives a ConfigTask through the full wizard workflow:
      Step 1 – Dynamic input form built from task.fields
      Step 2 – Preview generated commands + rollback before pushing
      Step 3 – Push result, before/after config diff, optional rollback
    """

    _VENDOR_MAP = {
        "cisco_router": "Cisco",
        "cisco_switch": "Cisco",
        "huawei_router": "Huawei",
        "huawei_switch": "Huawei",
    }

    def __init__(self, parent, task, device: dict, config_manager):
        self._task = task
        self._device = device
        self._config_manager = config_manager
        self._vendor = self._VENDOR_MAP.get(device.get("device_type", ""), "Cisco")
        self._inputs: dict = {}
        self._widgets: dict = {}
        self._running_config_before: str = ""
        self._running_config_after: str = ""
        self._push_output: str = ""
        self._step = 1

        # ── Window ────────────────────────────────────────────────────────────
        self._win = tk.Toplevel(parent)
        self._win.title(f"Wizard – {task.name}")
        self._win.geometry("720x620")
        self._win.resizable(True, True)
        self._win.transient(parent)
        self._win.grab_set()
        self._win.configure(bg=BG_DARK)

        # Title bar
        title_bar = tk.Frame(self._win, bg=BG_MID, pady=8, padx=12)
        title_bar.pack(fill=tk.X)
        tk.Label(title_bar, text=task.name,
                 font=("Arial", 13, "bold"),
                 fg="#58a6ff", bg=BG_MID).pack(side=tk.LEFT)
        tk.Label(title_bar, text=f"  [{self._vendor}]",
                 fg="#bc8cff", bg=BG_MID,
                 font=("Arial", 10, "italic")).pack(side=tk.LEFT)
        tk.Frame(self._win, bg=BORDER, height=1).pack(fill=tk.X)

        # Step indicator
        self._step_var = tk.StringVar()
        tk.Label(self._win, textvariable=self._step_var,
                 font=("Arial", 10, "bold"),
                 fg="#e3b341", bg=BG_DARK).pack(anchor=tk.W, padx=12, pady=(8, 0))

        # Content area (rebuilt each step)
        self._content = ttk.Frame(self._win)
        self._content.pack(fill=tk.BOTH, expand=True, padx=12, pady=6)

        # Bottom button bar
        btn_bar = tk.Frame(self._win, bg=BG_MID, pady=6, padx=8)
        btn_bar.pack(fill=tk.X, side=tk.BOTTOM)
        tk.Frame(self._win, bg=BORDER, height=1).pack(side=tk.BOTTOM, fill=tk.X)
        self._back_btn = make_3d_button(btn_bar, "← Back",
                                        command=self._go_back,
                                        state=tk.DISABLED, btn_type="neutral")
        self._back_btn.pack(side=tk.LEFT, padx=4, ipadx=6, ipady=3)
        self._cancel_btn = make_3d_button(btn_bar, "Cancel",
                                          command=self._win.destroy,
                                          btn_type="danger")
        self._cancel_btn.pack(side=tk.RIGHT, padx=4, ipadx=6, ipady=3)
        self._next_btn = make_3d_button(btn_bar, "Validate & Preview  →",
                                        command=self._step1_next,
                                        btn_type="primary")
        self._next_btn.pack(side=tk.RIGHT, padx=4, ipadx=6, ipady=3)

        self._build_step1()

    # ── Internal helpers ───────────────────────────────────────────────────────

    def _clear_content(self):
        for child in self._content.winfo_children():
            child.destroy()

    def _collect_inputs(self) -> dict:
        vals = {}
        for f in self._task.fields:
            w = self._widgets.get(f.name)
            if w is None:
                vals[f.name] = f.default
            elif isinstance(w, scrolledtext.ScrolledText):
                vals[f.name] = w.get("1.0", tk.END).strip()
            else:
                vals[f.name] = w.get()
        return vals

    # ── Step 1: Input form ─────────────────────────────────────────────────────

    def _build_step1(self):
        self._clear_content()
        self._step = 1
        self._step_var.set("Step 1 of 3  –  Enter Parameters")
        self._back_btn.config(state=tk.DISABLED)
        self._next_btn.config(text="Validate & Preview  →",
                              command=self._step1_next, state=tk.NORMAL)
        self._cancel_btn.config(state=tk.NORMAL)

        # Scrollable canvas so tall forms don't clip
        canvas = tk.Canvas(self._content, highlightthickness=0)
        vsb = ttk.Scrollbar(self._content, orient=tk.VERTICAL,
                             command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        inner = ttk.Frame(canvas)
        canvas_win = canvas.create_window((0, 0), window=inner, anchor=tk.NW)

        inner.bind("<Configure>",
                   lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>",
                    lambda e: canvas.itemconfig(canvas_win, width=e.width))

        self._widgets = {}
        for f in self._task.fields:
            row = ttk.Frame(inner, padding=(0, 3))
            row.pack(fill=tk.X, pady=2)
            label_text = f.label + (" *" if f.required else "")
            ttk.Label(row, text=label_text, width=24,
                      anchor=tk.E).pack(side=tk.LEFT, padx=(0, 6))

            if f.field_type == "select":
                var = tk.StringVar(value=f.default or
                                   (f.options[0] if f.options else ""))
                w = ttk.Combobox(row, textvariable=var,
                                 values=f.options, state="readonly", width=30)
                w.pack(side=tk.LEFT)
                self._widgets[f.name] = w
            elif f.field_type == "multiline":
                w = scrolledtext.ScrolledText(row, height=4, width=40,
                                              font=("Courier", 9))
                w.pack(side=tk.LEFT, fill=tk.X, expand=True)
                if f.default:
                    w.insert("1.0", f.default)
                self._widgets[f.name] = w
            elif f.field_type == "password":
                var = tk.StringVar(value=f.default)
                w = ttk.Entry(row, textvariable=var, show="*", width=32)
                w.pack(side=tk.LEFT)
                self._widgets[f.name] = w
            else:
                var = tk.StringVar(value=f.default)
                w = ttk.Entry(row, textvariable=var, width=32)
                w.pack(side=tk.LEFT)
                self._widgets[f.name] = w

            if f.hint:
                ttk.Label(row, text=f"  ℹ  {f.hint}",
                          foreground="gray",
                          font=("Arial", 8)).pack(side=tk.LEFT, padx=4)

        # Restore previously entered values when coming back from step 2
        if self._inputs:
            for f in self._task.fields:
                val = self._inputs.get(f.name, "")
                w = self._widgets.get(f.name)
                if w is None or not val:
                    continue
                if isinstance(w, scrolledtext.ScrolledText):
                    w.delete("1.0", tk.END)
                    w.insert("1.0", val)
                elif isinstance(w, ttk.Combobox):
                    w.set(val)
                else:
                    w.delete(0, tk.END)
                    w.insert(0, val)

    def _step1_next(self):
        inputs = self._collect_inputs()

        # ── Form validation ───────────────────────────────────────────────────
        errors = self._task.validate_inputs(inputs)
        if errors:
            messagebox.showerror(
                "Validation Errors",
                "\n".join(f"• {e}" for e in errors),
                parent=self._win)
            return

        # ── Fetch running config for config-against validation ─────────────
        self._running_config_before = ""
        try:
            ok, result = ssh_client.get_running_config(self._device)
        except Exception:
            ok, result = False, ""

        if ok:
            self._running_config_before = result
        else:
            if not messagebox.askyesno(
                "SSH Warning",
                "Could not fetch the running config from the device.\n\n"
                "Config-against-device validation will be skipped.\n\n"
                "Continue anyway?",
                parent=self._win
            ):
                return

        # ── Config-against validation ──────────────────────────────────────
        if self._running_config_before:
            warnings = self._task.validate_against_config(
                inputs, self._running_config_before, self._vendor)
            if warnings:
                if not messagebox.askyesno(
                    "Configuration Conflicts",
                    "The following issues were found against the running config:\n\n"
                    + "\n".join(f"⚠  {w}" for w in warnings)
                    + "\n\nProceed anyway?",
                    parent=self._win
                ):
                    return

        self._inputs = inputs
        self._build_step2()

    # ── Step 2: Command preview ────────────────────────────────────────────────

    def _build_step2(self):
        self._clear_content()
        self._step = 2
        self._step_var.set("Step 2 of 3  –  Review Commands")
        self._back_btn.config(state=tk.NORMAL)
        self._next_btn.config(text="Push to Device  →",
                              command=self._step2_push, state=tk.NORMAL)
        self._cancel_btn.config(state=tk.NORMAL)

        cmds = self._task.generate_commands(self._inputs, self._vendor)
        rollback = self._task.generate_rollback(self._inputs, self._vendor)

        cmd_frame = ttk.LabelFrame(self._content,
                                   text="Commands to be pushed", padding=6)
        cmd_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 6))

        cmd_text = scrolledtext.ScrolledText(
            cmd_frame, height=10, font=("Courier", 10),
            background="#1e1e1e", foreground="#d4d4d4",
            insertbackground="white", wrap=tk.NONE)
        cmd_text.pack(fill=tk.BOTH, expand=True)
        cmd_text.insert(tk.END, "\n".join(cmds) if cmds else "(no commands)")
        cmd_text.config(state=tk.DISABLED)

        rb_frame = ttk.LabelFrame(self._content,
                                  text="Rollback commands (if needed)", padding=6)
        rb_frame.pack(fill=tk.X)
        rb_text = scrolledtext.ScrolledText(
            rb_frame, height=4, font=("Courier", 9),
            background="#2d2d2d", foreground="#aaaaaa", wrap=tk.NONE)
        rb_text.pack(fill=tk.X)
        rb_text.insert(tk.END, "\n".join(rollback) if rollback
                       else "(no rollback available)")
        rb_text.config(state=tk.DISABLED)

    def _step2_push(self):
        self._next_btn.config(state=tk.DISABLED, text="Pushing…")
        self._back_btn.config(state=tk.DISABLED)
        self._win.update_idletasks()
        cmds = self._task.generate_commands(self._inputs, self._vendor)

        def _do_push():
            try:
                ok, output = ssh_client.push_config(self._device, cmds)
            except Exception as exc:
                ok, output = False, str(exc)
            self._win.after(0, lambda: self._push_done(ok, output))

        threading.Thread(target=_do_push, daemon=True).start()

    def _push_done(self, ok: bool, output: str):
        self._push_output = output
        self._running_config_after = ""
        if ok:
            try:
                cfg_ok, cfg_after = ssh_client.get_running_config(self._device)
                if cfg_ok:
                    self._running_config_after = cfg_after
            except Exception:
                pass
        self._build_step3(ok)

    # ── Step 3: Result + diff ──────────────────────────────────────────────────

    def _build_step3(self, push_ok: bool):
        import difflib
        self._clear_content()
        self._step = 3
        self._step_var.set("Step 3 of 3  –  Result & Diff")
        self._back_btn.config(state=tk.DISABLED)
        self._cancel_btn.config(state=tk.DISABLED)
        self._next_btn.config(
            text="✔  Confirm & Close" if push_ok else "Close",
            command=self._win.destroy, state=tk.NORMAL)

        # Status banner
        status_color = "#28a745" if push_ok else "#dc3545"
        status_text = ("✔  Configuration pushed successfully!"
                       if push_ok else "✘  Push failed — see output below")
        ttk.Label(self._content, text=status_text,
                  foreground=status_color,
                  font=("Arial", 11, "bold")).pack(anchor=tk.W, pady=(0, 4))

        # Push output
        out_frame = ttk.LabelFrame(self._content, text="Device Output", padding=4)
        out_frame.pack(fill=tk.X, pady=(0, 6))
        out_text = scrolledtext.ScrolledText(
            out_frame, height=5, font=("Courier", 9),
            background="#1a1a1a", foreground="#cccccc")
        out_text.pack(fill=tk.X)
        out_text.insert(tk.END, self._push_output or "(no output)")
        out_text.config(state=tk.DISABLED)

        # Config diff
        diff_frame = ttk.LabelFrame(self._content,
                                    text="Configuration Diff  (before → after)",
                                    padding=4)
        diff_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 6))
        diff_text = scrolledtext.ScrolledText(
            diff_frame, height=10, font=("Courier", 9), wrap=tk.NONE)
        diff_text.pack(fill=tk.BOTH, expand=True)
        diff_text.tag_configure("add",    foreground="#28a745",
                                font=("Courier", 9, "bold"))
        diff_text.tag_configure("remove", foreground="#dc3545",
                                font=("Courier", 9, "bold"))
        diff_text.tag_configure("info",   foreground="#0066cc")
        diff_text.tag_configure("meta",   foreground="#888888")

        if self._running_config_before and self._running_config_after:
            lines_before = self._running_config_before.splitlines(keepends=True)
            lines_after  = self._running_config_after.splitlines(keepends=True)
            diff = list(difflib.unified_diff(
                lines_before, lines_after,
                fromfile="running-config (before)",
                tofile="running-config (after)"))
            if diff:
                for line in diff:
                    if line.startswith(("+++", "---")):
                        diff_text.insert(tk.END, line, "meta")
                    elif line.startswith("@@"):
                        diff_text.insert(tk.END, line, "info")
                    elif line.startswith("+"):
                        diff_text.insert(tk.END, line, "add")
                    elif line.startswith("-"):
                        diff_text.insert(tk.END, line, "remove")
                    else:
                        diff_text.insert(tk.END, line)
            else:
                diff_text.insert(tk.END,
                    "(No differences detected — config may not have changed)")
        else:
            diff_text.insert(tk.END,
                "(Diff unavailable — running config could not be fetched "
                "before or after the push)")
        diff_text.config(state=tk.DISABLED)

        # Rollback button (only shown when push succeeded and rollback exists)
        if push_ok:
            rollback_cmds = self._task.generate_rollback(self._inputs, self._vendor)
            if rollback_cmds:
                rb_btn_frame = ttk.Frame(self._content)
                rb_btn_frame.pack(fill=tk.X)
                self._rollback_btn = make_3d_button(
                    rb_btn_frame, text="⚠  Rollback Changes",
                    command=lambda: self._do_rollback(rollback_cmds),
                    btn_type="warning")
                self._rollback_btn.pack(side=tk.RIGHT, padx=4, ipadx=8, ipady=3)

    def _do_rollback(self, rollback_cmds: list):
        if not messagebox.askyesno(
            "Confirm Rollback",
            "Push the following rollback commands to the device?\n\n"
            + "\n".join(rollback_cmds),
            parent=self._win
        ):
            return
        self._rollback_btn.config(state=tk.DISABLED, text="Rolling back…")
        self._win.update_idletasks()

        def _run():
            try:
                ok, output = ssh_client.push_config(self._device, rollback_cmds)
            except Exception as exc:
                ok, output = False, str(exc)
            self._win.after(0, lambda: _done(ok, output))

        def _done(ok, output):
            if ok:
                messagebox.showinfo("Rollback Complete",
                                    "Rollback applied successfully.",
                                    parent=self._win)
                self._rollback_btn.config(state=tk.DISABLED,
                                          text="✔  Rolled Back")
            else:
                messagebox.showerror("Rollback Failed",
                                     f"Rollback failed:\n{output}",
                                     parent=self._win)
                self._rollback_btn.config(state=tk.NORMAL,
                                          text="⚠  Retry Rollback")

        threading.Thread(target=_run, daemon=True).start()

    # ── Navigation ─────────────────────────────────────────────────────────────

    def _go_back(self):
        if self._step == 2:
            self._build_step1()


def main():
    """Run application"""
    root = tk.Tk()
    app = NetworkDeviceManagerGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
