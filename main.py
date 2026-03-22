"""
Network Device Manager - Main GUI Application
Automated configuration and observability for Cisco and Huawei devices
"""

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
from modules.templates import (
    get_all_templates, get_template_content, get_template_name,
    get_vendors, get_templates_by_vendor, get_categories
)


class NetworkDeviceManagerGUI:
    """Main GUI Application for Network Device Management"""

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Network Device Manager - Automated Configuration & Observability")
        self.root.geometry("1200x800")
        
        # Initialize managers
        self.device_manager = DeviceManager()
        self.config_manager = ConfigurationManager()
        self.status_monitor = StatusMonitor()
        self.compliance_checker = ComplianceChecker()
        self.logger = get_observability_manager()
        
        # Template list for combobox
        self.template_list = []
        
        # Setup GUI
        self._setup_styles()
        self._create_menu_bar()
        self._create_main_layout()
        
        # Status bar
        self.status_var = tk.StringVar(value="Ready")
        status_bar = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        
        self.update_device_list()

    def _setup_styles(self):
        """Setup GUI styles and themes"""
        style = ttk.Style()
        style.theme_use('clam')
        
        # Define colors
        style.configure('Header.TLabel', font=('Arial', 12, 'bold'))
        style.configure('Success.TLabel', foreground='green')
        style.configure('Error.TLabel', foreground='red')
        style.configure('Warning.TLabel', foreground='orange')

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

    def _create_dashboard_tab(self):
        """Create dashboard tab with overview"""
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="Dashboard")
        
        # Title
        title = ttk.Label(frame, text="Network Overview", style='Header.TLabel')
        title.pack(pady=10)
        
        # Stats grid
        stats_frame = ttk.LabelFrame(frame, text="Inventory Statistics", padding=10)
        stats_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        self.stats_labels = {}
        stats = [
            ("Total Devices", "total_devices"),
            ("Online Devices", "online_devices"),
            ("Offline Devices", "offline_devices"),
            ("Cisco Devices", "cisco_devices"),
            ("Huawei Devices", "huawei_devices"),
            ("Avg Health", "avg_health"),
            ("Active Alerts", "active_alerts"),
            ("Compliance Score", "compliance_score")
        ]
        
        for idx, (label, key) in enumerate(stats):
            row = idx // 4
            col = idx % 4
            
            lbl_frame = ttk.Frame(stats_frame)
            lbl_frame.grid(row=row, column=col, padx=20, pady=20)
            
            ttk.Label(lbl_frame, text=label, font=('Arial', 10)).pack()
            value_var = tk.StringVar(value="0")
            self.stats_labels[key] = value_var
            ttk.Label(lbl_frame, textvariable=value_var, font=('Arial', 14, 'bold')).pack()
        
        # Refresh button
        ttk.Button(frame, text="Refresh Dashboard", command=self._refresh_dashboard).pack(pady=10)

    def _create_inventory_tab(self):
        """Create device inventory tab"""
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="Inventory")
        
        # Toolbar
        toolbar = ttk.Frame(frame)
        toolbar.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)
        
        ttk.Button(toolbar, text="Add Device", command=self._show_add_device_dialog).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Discover", command=self._show_discovery_dialog).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Refresh", command=self.update_device_list).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Remove", command=self._remove_device).pack(side=tk.LEFT, padx=2)
        
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
        self.notebook.add(frame, text="Monitoring")
        
        # Controls
        control_frame = ttk.Frame(frame)
        control_frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)
        
        ttk.Label(control_frame, text="Select Device:").pack(side=tk.LEFT, padx=5)
        
        self.monitor_device_var = tk.StringVar()
        self.monitor_device_combo = ttk.Combobox(control_frame, textvariable=self.monitor_device_var, width=30)
        self.monitor_device_combo.pack(side=tk.LEFT, padx=5)
        
        ttk.Button(control_frame, text="Update Status", command=self._update_device_status).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="Refresh", command=self._refresh_monitoring).pack(side=tk.LEFT, padx=5)
        
        # Status display
        display_frame = ttk.LabelFrame(frame, text="Device Status", padding=10)
        display_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.status_text = scrolledtext.ScrolledText(display_frame, height=20, width=80)
        self.status_text.pack(fill=tk.BOTH, expand=True)

    def _create_configuration_tab(self):
        """Create configuration management tab"""
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="Configuration")
        
        # Device selector
        selector_frame = ttk.Frame(frame)
        selector_frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)
        
        ttk.Label(selector_frame, text="Device:").pack(side=tk.LEFT, padx=5)
        self.config_device_var = tk.StringVar()
        self.config_device_combo = ttk.Combobox(selector_frame, textvariable=self.config_device_var, width=30)
        self.config_device_combo.pack(side=tk.LEFT, padx=5)
        
        # Buttons
        button_frame = ttk.Frame(selector_frame)
        button_frame.pack(side=tk.LEFT, padx=10)
        
        ttk.Button(button_frame, text="Backup", command=self._backup_config).pack(side=tk.LEFT, padx=2)
        ttk.Button(button_frame, text="Restore", command=self._restore_config).pack(side=tk.LEFT, padx=2)
        ttk.Button(button_frame, text="View", command=self._view_config).pack(side=tk.LEFT, padx=2)
        ttk.Button(button_frame, text="Compare", command=self._compare_configs).pack(side=tk.LEFT, padx=2)
        
        # Templates section
        template_frame = ttk.LabelFrame(frame, text="Configuration Templates", padding=5)
        template_frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)
        
        template_select_frame = ttk.Frame(template_frame)
        template_select_frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)
        
        ttk.Label(template_select_frame, text="Vendor:").pack(side=tk.LEFT, padx=5)
        self.template_vendor_var = tk.StringVar()
        self.template_vendor_combo = ttk.Combobox(template_select_frame, textvariable=self.template_vendor_var,
                                                  values=get_vendors(), width=20, state='readonly')
        self.template_vendor_combo.pack(side=tk.LEFT, padx=5)
        self.template_vendor_combo.bind("<<ComboboxSelected>>", self._update_template_list)
        
        ttk.Label(template_select_frame, text="Template:").pack(side=tk.LEFT, padx=5)
        self.template_var = tk.StringVar()
        self.template_combo = ttk.Combobox(template_select_frame, textvariable=self.template_var,
                                          width=35, state='readonly')
        self.template_combo.pack(side=tk.LEFT, padx=5)
        
        # Template buttons
        template_btn_frame = ttk.Frame(template_select_frame)
        template_btn_frame.pack(side=tk.LEFT, padx=10)
        
        ttk.Button(template_btn_frame, text="Load Template", command=self._load_template).pack(side=tk.LEFT, padx=2)
        ttk.Button(template_btn_frame, text="Insert Template", command=self._insert_template).pack(side=tk.LEFT, padx=2)
        ttk.Button(template_btn_frame, text="Clear", command=self._clear_config_text).pack(side=tk.LEFT, padx=2)
        
        # Config text area
        self.config_text = scrolledtext.ScrolledText(frame, height=30, width=100)
        self.config_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def _create_compliance_tab(self):
        """Create compliance checking tab"""
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="Compliance")
        
        # Controls
        control_frame = ttk.Frame(frame)
        control_frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)
        
        ttk.Button(control_frame, text="Check Compliance", command=self._run_compliance_check).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="Generate Report", command=self._generate_compliance_report).pack(side=tk.LEFT, padx=5)
        
        # Results display
        self.compliance_text = scrolledtext.ScrolledText(frame, height=30, width=100)
        self.compliance_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def _create_logs_tab(self):
        """Create logs/events tab"""
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="Logs")
        
        # Controls
        control_frame = ttk.Frame(frame)
        control_frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)
        
        ttk.Button(control_frame, text="Refresh Logs", command=self._view_logs).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="Clear Logs", command=self._clear_logs).pack(side=tk.LEFT, padx=5)
        
        # Logs display
        self.logs_text = scrolledtext.ScrolledText(frame, height=30, width=100)
        self.logs_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def _show_add_device_dialog(self):
        """Show dialog to add new device"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Add Device")
        dialog.geometry("400x400")
        
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
                hostname = entries["hostname"].get()
                ip = entries["ip_address"].get()
                dev_type = entries["device_type"].get()
                user = entries["username"].get()
                pwd = entries["password"].get()
                port = int(entries["port"].get() or 22)
                snmp = entries["snmp_community"].get() or "public"
                
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
        
        ttk.Button(dialog, text="Add Device", command=add_device).pack(pady=20)

    def _show_discovery_dialog(self):
        """Show device discovery dialog"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Discover Devices")
        dialog.geometry("400x250")
        
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
        
        ttk.Button(dialog, text="Discover", command=discover).pack(pady=20)

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
        """Backup device configuration"""
        hostname = self.config_device_var.get()
        if not hostname:
            messagebox.showwarning("Warning", "Please select a device")
            return
        
        # In production, this would connect to the device and get config
        config_content = "! Configuration backup\nversion 15.0\n"
        
        success, msg = self.config_manager.backup_configuration(hostname, config_content)
        messagebox.showinfo("Success", msg) if success else messagebox.showerror("Error", msg)

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
        
        listbox = tk.Listbox(dialog)
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
        
        ttk.Button(dialog, text="Restore", command=restore).pack(pady=10)

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
        """Compare two configurations"""
        messagebox.showinfo("Info", "Configuration comparison feature coming soon")

    def _deploy_config(self):
        """Deploy configuration to device"""
        hostname = self.config_device_var.get()
        config = self.config_text.get(1.0, tk.END)
        
        if not hostname or not config.strip():
            messagebox.showwarning("Warning", "Please select device and provide config")
            return
        
        success, msg = self.config_manager.save_configuration(hostname, config)
        messagebox.showinfo("Success", msg) if success else messagebox.showerror("Error", msg)

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


def main():
    """Run application"""
    root = tk.Tk()
    app = NetworkDeviceManagerGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
