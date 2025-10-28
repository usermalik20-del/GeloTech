# (BEGIN FILE)
"""
ph_android_remover_singlefile.py
Android Adware Remover GUI (Resizable + Working Checkboxes + Select All)
Python 3.14 | PyInstaller-ready
"""

import os
import subprocess
import threading
import datetime
import tkinter as tk
from tkinter import ttk, filedialog

# ---------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------
DRY_RUN_DEFAULT = True
EXPORT_FOLDER = os.path.join(os.path.expanduser("~"), "ph_remover_exports")
os.makedirs(EXPORT_FOLDER, exist_ok=True)

AD_DB = {
    "com.startapp", "com.airpush", "com.mopub", "com.inmobi",
    "com.google.ads", "com.adcolony", "com.admob", "com.tapjoy",
    "com.appnext", "com.chartboost", "com.ironsource", "com.unity3d.ads",
    "com.vungle", "com.bytedance.sdk", "com.applovin", "com.advertising",
    "com.adsdk", "com.adsmogo", "com.mobvista", "com.mobfox", "com.bytedance",
    "com.buzzvil", "com.adpush", "com.adpush.android", "com.domob",
    "com.mobiroller", "com.adways", "com.adchina", "net.youmi",
    "com.judy", "com.android.judy", "cn.judy", "com.mobidash", "com.batmobi",
    "com.mobnetmedia", "com.twoappspy", "com.hiddenads", "com.pushad",
    "com.adware", "com.adultgame", "com.dianxinos.optimizer", "com.mf.ad",
    "org.malicious.ad"
}

# ---------------------------------------------------------------------
# ADB helpers
# ---------------------------------------------------------------------
def _run(cmd, timeout=30, shell=False):
    try:
        out = subprocess.check_output(cmd, stderr=subprocess.STDOUT,
                                      shell=shell, timeout=timeout)
        return out.decode(errors="ignore")
    except subprocess.CalledProcessError as e:
        return e.output.decode(errors="ignore")
    except Exception as e:
        return str(e)

def adb_available():
    out = _run(["adb", "version"], timeout=5)
    return "Android Debug Bridge" in out or "adb" in out.lower()

def get_device_info():
    try:
        sn = _run(["adb", "get-serialno"]).strip()
        if not sn or sn.lower().startswith("unknown") or "error" in sn.lower():
            return None
        props = _run(["adb", "shell", "getprop"]).splitlines()
        def g(k):
            for line in props:
                if k in line:
                    return line.split(":")[-1].strip(" []")
            return "N/A"
        return {
            "sn": sn,
            "brand": g("ro.product.brand"),
            "model": g("ro.product.model"),
            "os": g("ro.build.version.release"),
            "build": g("ro.build.display.id")
        }
    except Exception:
        return None

def list_user_apps():
    return [l.replace("package:", "").strip()
            for l in _run(["adb", "shell", "pm", "list", "packages", "-3"]).splitlines()
            if l.strip()]

def list_system_apps():
    return [l.replace("package:", "").strip()
            for l in _run(["adb", "shell", "pm", "list", "packages", "-s"]).splitlines()
            if l.strip()]

def list_disabled_apps():
    return [l.replace("package:", "").strip()
            for l in _run(["adb", "shell", "pm", "list", "packages", "-d"]).splitlines()
            if l.strip()]

def remove_app(pkg, dry_run=True):
    cmds = [
        ["adb", "shell", "pm", "uninstall", "--user", "0", pkg],
        ["adb", "shell", "pm", "uninstall", pkg],
    ]
    res = {"cmds": [" ".join(c) for c in cmds], "results": []}
    if dry_run:
        return res
    for c in cmds:
        out = _run(c, timeout=60)
        res["results"].append(out)
        if "Success" in out or "success" in out:
            break
    return res

def force_stop(pkg): return _run(["adb", "shell", "am", "force-stop", pkg])
def open_playstore(pkg): return _run(["adb", "shell", "am", "start",
                                      "-a", "android.intent.action.VIEW",
                                      "-d", f"market://details?id={pkg}"])
def now_str(): return datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

def safe_write_file(folder, base_name, content):
    path = os.path.join(folder, f"{base_name}_{now_str()}.txt")
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return path
    except Exception:
        return None

# ---------------------------------------------------------------------
# GUI
# ---------------------------------------------------------------------
class PHRemoverApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("PH Android Adware Remover")
        self.minsize(1000, 640)
        self.dry_run = DRY_RUN_DEFAULT
        self.ad_db = set(AD_DB)
        self.preview_commands = []
        self.export_folder = EXPORT_FOLDER

        self._create_layout()
        threading.Thread(target=self.initial_check, daemon=True).start()

    # ---------------------- UI Layout ----------------------
    def _create_layout(self):
        self.columnconfigure(0, weight=3)
        self.columnconfigure(1, weight=1)
        self.rowconfigure(2, weight=1)

        # Device info
        top = ttk.LabelFrame(self, text="Device & Controls")
        top.grid(row=0, column=0, columnspan=2, sticky="ew", padx=8, pady=4)
        for i in range(6):
            top.columnconfigure(i, weight=1)

        ttk.Label(top, text="ADB available:").grid(row=0, column=0, sticky="w")
        self.adb_status_var = tk.StringVar(value="Checking…")
        ttk.Label(top, textvariable=self.adb_status_var).grid(row=0, column=1, sticky="w")

        self.device_vars = {k: tk.StringVar(value="---")
                            for k in ["Brand", "Model", "OS", "Build", "SN"]}
        row = 1
        for key, var in self.device_vars.items():
            ttk.Label(top, text=f"{key}:").grid(row=row, column=0, sticky="e", padx=4)
            ttk.Label(top, textvariable=var).grid(row=row, column=1, sticky="w")
            row += 1

        ttk.Button(top, text="Check Device",
                   command=lambda: threading.Thread(target=self.refresh_device_info, daemon=True).start()).grid(row=1, column=5)
        ttk.Button(top, text="Refresh Apps",
                   command=lambda: threading.Thread(target=self.refresh_app_lists, daemon=True).start()).grid(row=2, column=5)
        ttk.Button(top, text="Restart ADB",
                   command=lambda: threading.Thread(target=self.restart_adb, daemon=True).start()).grid(row=3, column=5)

        self.dry_run_var = tk.BooleanVar(value=self.dry_run)
        ttk.Checkbutton(top, text="Dry-run (preview only)",
                        variable=self.dry_run_var,
                        command=self.toggle_dry_run).grid(row=4, column=5)

        # extra debug button: load sample apps
        ttk.Button(top, text="Load Sample Apps (debug)",
                   command=lambda: threading.Thread(target=self._load_sample_apps, daemon=True).start()).grid(row=4, column=4)

        # Search
        mid = ttk.Frame(self)
        mid.grid(row=1, column=0, sticky="ew", padx=8)
        ttk.Label(mid, text="Search:").pack(side="left", padx=4)
        self.search_var = tk.StringVar()
        ttk.Entry(mid, textvariable=self.search_var, width=60).pack(side="left", fill="x", expand=True)
        ttk.Button(mid, text="Scan Auto (AD_DB)",
                   command=lambda: threading.Thread(target=self.scan_auto, daemon=True).start()).pack(side="right")

        # Tabs
        self.tab_frame = ttk.Notebook(self)
        self.tab_frame.grid(row=2, column=0, sticky="nsew", padx=8, pady=4)

        self.user_tree, self.user_select_all = self._make_treeview_tab("User Apps")
        self.system_tree, self.system_select_all = self._make_treeview_tab("System Apps")
        self.disabled_tree, self.disabled_select_all = self._make_treeview_tab("Disabled Apps")

        # Right panel
        right = ttk.LabelFrame(self, text="Actions & Export")
        right.grid(row=2, column=1, sticky="nswe", padx=8, pady=4)
        for txt, fn in [
            ("Select by Search", self.select_by_search),
            ("Select AD_DB Matches", self.select_ad_db_matches),
            ("Preview Uninstall", self.preview_uninstall_selected),
            ("Execute Uninstall", self.execute_uninstall_selected),
            ("Force-stop Selected", self.force_stop_selected),
            ("Open PlayStore", self.playstore_selected),
            ("Export Log", self.export_log),
            ("Export Previewed Cmds", self.export_preview),
            ("Load AD_DB from File", self.load_ad_db_file)
        ]:
            ttk.Button(right, text=txt,
                       command=lambda f=fn: threading.Thread(target=f, daemon=True).start()).pack(fill="x", pady=3)

        # Log
        log_frame = ttk.LabelFrame(self, text="Log & Preview")
        log_frame.grid(row=3, column=0, columnspan=2, sticky="nsew", padx=8, pady=4)
        self.log_text = tk.Text(log_frame, height=4)
        self.log_text.pack(fill="both", expand=True)

        self.grid_rowconfigure(2, weight=1)
        self.grid_columnconfigure(0, weight=3)
        self.grid_columnconfigure(1, weight=1)

    # ---------------- Treeview & Checkboxes ----------------
    def _make_treeview_tab(self, name):
        frame = ttk.Frame(self.tab_frame)
        select_all_var = tk.BooleanVar(value=False)
        cb = ttk.Checkbutton(
            frame, text="Select All / Deselect All", variable=select_all_var,
            command=lambda v=select_all_var, f=frame: self._toggle_all_checkboxes(f, v)
        )
        cb.pack(anchor="w", padx=4, pady=2)

        tree = ttk.Treeview(frame, columns=("pkg",), show="headings", selectmode="browse")
        tree.heading("pkg", text="App Package")
        tree.column("pkg", width=600, anchor="w")
        tree.pack(fill="both", expand=True)

        yscroll = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=yscroll.set)
        yscroll.pack(side="right", fill="y")

        # double-click toggles checked state
        tree.bind("<Double-Button-1>", lambda e, t=tree: self._toggle_checkbox(e, t))
        self.tab_frame.add(frame, text=name)
        return tree, select_all_var

    def _toggle_all_checkboxes(self, frame, var):
        tree = next((w for w in frame.winfo_children() if isinstance(w, ttk.Treeview)), None)
        if not tree:
            return
        check = var.get()
        for i in tree.get_children():
            pkg = tree.item(i, "values")[0].split("]", 1)[-1].strip()
            tree.item(i, tags=("checked" if check else "unchecked",),
                      values=(f"[✔] {pkg}" if check else f"[ ] {pkg}",))
        self.log(f"{'Selected' if check else 'Deselected'} all in tab.")

    def _toggle_checkbox(self, event, tree):
        rowid = tree.identify_row(event.y)
        if not rowid:
            return
        pkg_val = tree.item(rowid, "values")[0]
        pkg = pkg_val.split("]", 1)[-1].strip()
        checked = "checked" in tree.item(rowid, "tags")
        if checked:
            tree.item(rowid, tags=("unchecked",), values=(f"[ ] {pkg}",))
            self.log("Deselected", pkg)
        else:
            tree.item(rowid, tags=("checked",), values=(f"[✔] {pkg}",))
            self.log("Selected", pkg)

    def _get_checked_items(self, tree):
        checked = []
        for i in tree.get_children():
            if "checked" in tree.item(i, "tags"):
                pkg = tree.item(i, "values")[0].split("]", 1)[-1].strip()
                checked.append(pkg)
        return checked

    # ---------------- General Helpers ----------------
    def log(self, *args):
        msg = " ".join(str(a) for a in args)
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        self.after(0, lambda: (
            self.log_text.insert("end", f"[{timestamp}] {msg}\n"),
            self.log_text.see("end"))
        )

    def toggle_dry_run(self):
        self.dry_run = bool(self.dry_run_var.get())
        self.log("Dry-run set to", self.dry_run)

    # ---------------- Device Handling ----------------
    def initial_check(self):
        ok = adb_available()
        self.adb_status_var.set("Yes" if ok else "No")
        self.log("ADB available." if ok else "ADB not found.")
        # We still call refresh_device_info so UI populates status and then apps (if device present)
        self.refresh_device_info()

    def refresh_device_info(self):
        info = get_device_info()
        if not info:
            self.log("No device detected or authorization missing.")
            for k in self.device_vars:
                self.device_vars[k].set("---")
            return
        for k in self.device_vars:
            self.device_vars[k].set(info.get(k.lower(), "N/A"))
        self.log("Device:", info.get("model"))
        self.refresh_app_lists()

    def refresh_app_lists(self):
        self.log("Loading app lists…")
        user, system, disabled = list_user_apps(), list_system_apps(), list_disabled_apps()
        for tree, data in [
            (self.user_tree, user), (self.system_tree, system), (self.disabled_tree, disabled)
        ]:
            tree.delete(*tree.get_children())
            for pkg in data:
                tree.insert("", "end", values=(f"[ ] {pkg}",), tags=("unchecked",))
        self.log(f"Loaded {len(user)} user, {len(system)} system, {len(disabled)} disabled apps.")

    # ---------------- Actions ----------------
    def _all_checked(self):
        return (
            self._get_checked_items(self.user_tree)
            + self._get_checked_items(self.system_tree)
            + self._get_checked_items(self.disabled_tree)
        )

    def preview_uninstall_selected(self):
        selected = self._all_checked()
        if not selected:
            return self.log("No apps selected.")
        self.preview_commands = []
        for pkg in selected:
            cmds = remove_app(pkg, dry_run=True)["cmds"]
            self.preview_commands.extend(cmds)
        for c in self.preview_commands:
            self.log("  ", c)
        self.log("Preview ready for", len(selected), "apps.")

    def execute_uninstall_selected(self):
        selected = self._all_checked()
        if not selected:
            return self.log("No apps selected.")
        for pkg in selected:
            res = remove_app(pkg, dry_run=self.dry_run)
            for cmd, out in zip(res["cmds"], res.get("results", [])):
                self.log(f"Executed: {cmd}")
                if out.strip():
                    self.log(out.strip())
        self.log("Execution complete.")

    def force_stop_selected(self):
        for pkg in self._all_checked():
            self.log("Force-stopping", pkg)
            self.log(force_stop(pkg).strip())

    def playstore_selected(self):
        for pkg in self._all_checked():
            self.log("Opening Play Store:", pkg)
            open_playstore(pkg)

    def select_by_search(self):
        q = self.search_var.get().strip().lower()
        if not q:
            return self.log("Search field empty.")
        for tree in [self.user_tree, self.system_tree, self.disabled_tree]:
            for i in tree.get_children():
                pkg = tree.item(i, "values")[0].split("]", 1)[-1].strip()
                if q in pkg.lower():
                    tree.item(i, tags=("checked",), values=(f"[✔] {pkg}",))
        self.log(f"Marked matches for '{q}'.")

    def select_ad_db_matches(self):
        for tree in [self.user_tree, self.system_tree, self.disabled_tree]:
            for i in tree.get_children():
                pkg = tree.item(i, "values")[0].split("]", 1)[-1].strip()
                if any(pkg.startswith(p) for p in self.ad_db):
                    tree.item(i, tags=("checked",), values=(f"[✔] {pkg}",))
        self.log("Marked AD_DB matches.")

    def export_log(self):
        content = self.log_text.get("1.0", "end").strip()
        path = safe_write_file(self.export_folder, "ph_remover_log", content)
        self.log("Log saved to", path if path else "Failed")

    def export_preview(self):
        if not self.preview_commands:
            return self.log("No preview commands.")
        content = "\n".join(self.preview_commands)
        path = safe_write_file(self.export_folder, "ph_remover_preview", content)
        self.log("Preview saved to", path if path else "Failed")

    def load_ad_db_file(self):
        path = filedialog.askopenfilename(title="Select AD_DB text file",
                                          filetypes=[("Text Files", "*.txt")])
        if not path:
            return
        with open(path, "r", encoding="utf-8") as f:
            entries = {line.strip() for line in f if line.strip()}
        self.ad_db.update(entries)
        self.log(f"Loaded {len(entries)} entries from file.")

    def scan_auto(self):
        self.log("Scanning with AD_DB…")
        self.select_ad_db_matches()
        self.log("Scan complete.")

    def restart_adb(self):
        _run(["adb", "kill-server"])
        _run(["adb", "start-server"])
        self.log("ADB restarted.")

    # ---------------- Debug helper ----------------
    def _load_sample_apps(self):
        sample_user = [f"com.example.userapp{i}" for i in range(1, 21)]
        sample_system = [f"com.android.systemapp{i}" for i in range(1, 11)]
        sample_disabled = [f"com.example.disabled{i}" for i in range(1, 6)]
        for tree, data in [
            (self.user_tree, sample_user), (self.system_tree, sample_system), (self.disabled_tree, sample_disabled)
        ]:
            tree.delete(*tree.get_children())
            for pkg in data:
                tree.insert("", "end", values=(f"[ ] {pkg}",), tags=("unchecked",))
        self.log("Loaded sample apps for debugging.")

# ---------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------
if __name__ == "__main__":
    app = PHRemoverApp()
    app.mainloop()
# (END FILE)
