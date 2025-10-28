#!/usr/bin/env python3
"""
GeloTech Android Ad Remover Utility
Enhanced UI — Quick Actions moved into Ad Detector tab, Export Report added.
PyQt6 | Python 3.14 compatible | PyInstaller-ready
"""

import os
import sys
import subprocess
import datetime
import webbrowser
from typing import List, Dict, Optional

from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QPushButton, QLabel, QProgressBar, QLineEdit, QFileDialog,
    QMessageBox, QTableWidget, QTableWidgetItem, QHeaderView, QTextEdit,
    QGroupBox, QSizePolicy
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QColor, QIcon, QPalette

# -------------------------
# Constants & Paths
# -------------------------
BASE_DIR = os.path.dirname(os.path.abspath(sys.argv[0]))
ADB_PATH_FILE = os.path.join(BASE_DIR, "adb_path.txt")
ICO_FILE = os.path.join(BASE_DIR, "gelotech.ico")
BACKUP_DIR = os.path.join(BASE_DIR, "backups")
ADAWAY_LINK = "https://github.com/usermalik20-del/GeloTech/blob/33c8df2b28d8efbb31a5c17133033e46141adeaa/.github/workflows/AdAway-6.1.4.apk"

EXTENDED_AD_SDKS = [
    "com.google.android.gms.ads", "com.google.ads", "com.facebook.ads",
    "com.mopub", "com.startapp", "com.inmobi", "com.applovin",
    "com.unity3d.ads", "com.bytedance", "com.ironsource",
    "com.vungle", "com.adcolony", "com.chartboost"
]

# -------------------------
# Helpers
# -------------------------
def find_adb_executable() -> Optional[str]:
    try:
        if os.path.exists(ADB_PATH_FILE):
            with open(ADB_PATH_FILE, "r", encoding="utf-8") as f:
                saved = f.read().strip()
            if saved and os.path.exists(saved):
                return saved
    except Exception:
        pass

    candidates = [
        os.path.join(BASE_DIR, "platform-tools", "adb.exe"),
        os.path.join(BASE_DIR, "platform-tools", "adb"),
        r"C:\Android\platform-tools\adb.exe",
        r"C:\Program Files (x86)\Android\android-sdk\platform-tools\adb.exe",
        r"C:\Program Files\Android\android-sdk\platform-tools\adb.exe",
    ]
    for p in candidates:
        if p and os.path.exists(p):
            return p
    for path_dir in os.getenv("PATH", "").split(os.pathsep):
        if not path_dir:
            continue
        for fn in ("adb.exe", "adb"):
            adb_candidate = os.path.join(path_dir.strip('"'), fn)
            if os.path.exists(adb_candidate):
                return adb_candidate
    return None

def _run(cmd, timeout=30):
    try:
        out = subprocess.check_output(cmd, stderr=subprocess.STDOUT, timeout=timeout)
        return out.decode(errors="ignore")
    except Exception as e:
        return str(e)

# -------------------------
# Worker Threads
# -------------------------
class RemoveWorker(QThread):
    finished = pyqtSignal(str, bool)
    def __init__(self, adb_path: str, package: str):
        super().__init__()
        self.adb = adb_path
        self.pkg = package
    def run(self):
        try:
            p = subprocess.run([self.adb, "shell", "pm", "uninstall", "--user", "0", self.pkg],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=60)
            out = (p.stdout or "") + (p.stderr or "")
            ok = "Success" in out
            self.finished.emit(self.pkg if ok else out.strip(), ok)
        except Exception as e:
            self.finished.emit(str(e), False)

class ScanAdsWorker(QThread):
    progress = pyqtSignal(int)
    log = pyqtSignal(str)
    result = pyqtSignal(dict)
    def __init__(self, adb_path: str, ad_identifiers: List[str]):
        super().__init__()
        self.adb = adb_path
        self.ad_identifiers = ad_identifiers
        self._stop = False
    def stop(self): self._stop = True
    def run(self):
        results = {}
        try:
            self.log.emit("Scanning packages...")
            p = subprocess.run([self.adb, "shell", "pm", "list", "packages", "-f"],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=25)
            lines = [ln.strip() for ln in (p.stdout or p.stderr or "").splitlines() if ln.strip()]
            total = max(1, len(lines))
            for idx, ln in enumerate(lines, start=1):
                if self._stop:
                    self.log.emit("Scan cancelled.")
                    break
                pkg = ln.split("=", 1)[-1] if "=" in ln else ln.replace("package:", "")
                matches = set()
                # attempt pm dump analysis (best-effort)
                try:
                    dump = subprocess.run([self.adb, "shell", "pm", "dump", pkg],
                                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=8)
                    text = (dump.stdout or dump.stderr or "").lower()
                    for ident in self.ad_identifiers:
                        if ident.lower() in text:
                            matches.add(ident)
                except Exception:
                    pass
                # fallback: check package name or listing line
                if not matches:
                    low = ln.lower() + " " + pkg.lower()
                    for ident in self.ad_identifiers:
                        if ident.lower() in low:
                            matches.add(ident)
                if matches:
                    results[pkg] = sorted(matches)
                    self.log.emit(f"{pkg}: {', '.join(matches)}")
                self.progress.emit(int(idx / total * 100))
            self.result.emit(results)
        except Exception as e:
            self.log.emit(f"Scan error: {e}")
            self.result.emit(results)

# -------------------------
# Main Application
# -------------------------
class GeloTechApp(QWidget):
    def __init__(self, adb_path: Optional[str]):
        super().__init__()
        self.setWindowTitle("GeloTech Android Ad Remover")
        if os.path.exists(ICO_FILE):
            try: self.setWindowIcon(QIcon(ICO_FILE))
            except Exception: pass
        self.resize(1100, 720)
        self.adb = adb_path or ""
        self.scan_worker = None
        self.remove_worker = None
        self.last_scan_results: Dict[str, List[str]] = {}

        self._apply_dark_theme()
        self._build_ui()
        self._auto_connect_and_refresh()

    # ----- UI + Theme -----
    def _apply_dark_theme(self):
        QApplication.setStyle("Fusion")
        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window, QColor(45,45,48))
        palette.setColor(QPalette.ColorRole.WindowText, QColor(230,230,230))
        palette.setColor(QPalette.ColorRole.Base, QColor(30,30,30))
        palette.setColor(QPalette.ColorRole.Text, QColor(230,230,230))
        palette.setColor(QPalette.ColorRole.Button, QColor(60,60,63))
        palette.setColor(QPalette.ColorRole.ButtonText, QColor(230,230,230))
        palette.setColor(QPalette.ColorRole.Highlight, QColor(0,122,204))
        QApplication.setPalette(palette)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        dash = QGroupBox("")
        dash_layout = QHBoxLayout()
        self.status_label = QLabel("Status: Ready")
        dash_layout.addWidget(self.status_label)
        dash_layout.addStretch()
        self.btn_connect = QPushButton("🔌 Connect / Refresh")
        self.btn_connect.clicked.connect(self._auto_connect_and_refresh)
        dash_layout.addWidget(self.btn_connect)
        btn_adaway = QPushButton("⬇️ View AdAway")
        btn_adaway.clicked.connect(lambda: webbrowser.open(ADAWAY_LINK))
        dash_layout.addWidget(btn_adaway)
        dash.setLayout(dash_layout)
        layout.addWidget(dash)

        self.tabs = QTabWidget()
        layout.addWidget(self.tabs, stretch=1)
        self._build_device_apps_tab()
        self._build_detector_tab()
        self._build_tools_tab()
        self.setLayout(layout)

    # ----- Tabs -----
    def _build_device_apps_tab(self):
        tab = QWidget()
        vbox = QVBoxLayout(tab)

        info_box = QGroupBox("Device Info")
        il = QVBoxLayout()

        # Detailed device info labels
        self.lbl_conn = QLabel("Connection: ❌ No device")
        self.lbl_serial = QLabel("Serial: -")
        self.lbl_manufacturer = QLabel("Manufacturer: -")
        self.lbl_model = QLabel("Model: -")
        self.lbl_android = QLabel("Android: -")
        self.lbl_sdk = QLabel("SDK: -")
        self.lbl_cpu = QLabel("CPU ABI: -")
        self.lbl_battery = QLabel("Battery: -")
        self.lbl_storage = QLabel("Storage (/data): -")
        self.lbl_ip = QLabel("IP (wlan0): -")

        # Refresh info button
        btn_info_refresh = QPushButton("🔄 Refresh Device Info")
        btn_info_refresh.setToolTip("Query device for latest information")
        btn_info_refresh.clicked.connect(self.refresh_device_info)

        # Add to layout in an intuitive grouping
        il.addWidget(self.lbl_conn)
        il.addWidget(self.lbl_serial)

        top_row = QHBoxLayout()
        left_col = QVBoxLayout()
        left_col.addWidget(self.lbl_manufacturer)
        left_col.addWidget(self.lbl_model)
        left_col.addWidget(self.lbl_cpu)
        top_row.addLayout(left_col)

        right_col = QVBoxLayout()
        right_col.addWidget(self.lbl_android)
        right_col.addWidget(self.lbl_sdk)
        right_col.addWidget(self.lbl_ip)
        top_row.addLayout(right_col)

        il.addLayout(top_row)

        bottom_row = QHBoxLayout()
        bottom_row.addWidget(self.lbl_battery)
        bottom_row.addWidget(self.lbl_storage)
        bottom_row.addStretch()
        bottom_row.addWidget(btn_info_refresh)
        il.addLayout(bottom_row)

        info_box.setLayout(il)
        vbox.addWidget(info_box)

        search = QLineEdit()
        search.setPlaceholderText("Filter installed packages...")
        search.textChanged.connect(self._filter_apps)
        vbox.addWidget(search)

        self.apps_table = QTableWidget(0, 2)
        self.apps_table.setHorizontalHeaderLabels(["Package", "Flag"])
        self.apps_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.apps_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.apps_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        vbox.addWidget(self.apps_table, stretch=1)
        tab.setLayout(vbox)
        self.tabs.addTab(tab, "📱 Device & Apps")

    def _build_detector_tab(self):
        tab = QWidget()
        vbox = QVBoxLayout(tab)

        # ---- Enhanced Quick Actions ----
        act_box = QGroupBox("Quick Actions")
        hl = QHBoxLayout()
        btn_refresh = QPushButton("🔄 Refresh")
        btn_refresh.setToolTip("Reload installed apps from device")
        btn_refresh.clicked.connect(self.refresh_apps)

        btn_scan = QPushButton("🔍 Scan for Ads")
        btn_scan.setToolTip("Scan apps for ad SDKs")
        btn_scan.clicked.connect(self.start_scan_ads)

        btn_backup = QPushButton("💾 Backup Selected")
        btn_backup.setToolTip("Save selected app’s APK to backups folder")
        btn_backup.clicked.connect(self.backup_selected)

        btn_uninstall = QPushButton("❌ Uninstall Selected")
        btn_uninstall.setToolTip("Remove selected app from device")
        btn_uninstall.clicked.connect(self.remove_selected)

        btn_export = QPushButton("📄 Export Report")
        btn_export.setToolTip("Export flagged apps report")
        btn_export.clicked.connect(self._export_flagged_report)

        for b in (btn_refresh, btn_scan, btn_backup, btn_uninstall, btn_export):
            b.setMinimumHeight(36)
            hl.addWidget(b)
        hl.addStretch()
        act_box.setLayout(hl)
        vbox.addWidget(act_box)

        info = QLabel("Detect apps using known Ad SDKs. Flagged apps show ⚠️ below.")
        info.setWordWrap(True)
        vbox.addWidget(info)

        ctrl = QHBoxLayout()
        self.scan_btn = QPushButton("▶️ Start Scan")
        self.scan_btn.clicked.connect(self.start_scan_ads)
        self.scan_stop_btn = QPushButton("⏹ Stop")
        self.scan_stop_btn.clicked.connect(self._stop_scan)
        self.scan_stop_btn.setEnabled(False)
        ctrl.addWidget(self.scan_btn)
        ctrl.addWidget(self.scan_stop_btn)
        ctrl.addStretch()
        self.progress = QProgressBar()
        self.progress.setValue(0)
        ctrl.addWidget(self.progress, stretch=1)
        vbox.addLayout(ctrl)

        self.flagged_label = QLabel("Flagged: 0 apps")
        self.flagged_label.setStyleSheet("font-weight:bold;")
        vbox.addWidget(self.flagged_label)

        # Detector-specific table (separate widget)
        self.detector_table = QTableWidget(0, 2)
        self.detector_table.setHorizontalHeaderLabels(["Package", "Flag"])
        self.detector_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.detector_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.detector_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        vbox.addWidget(self.detector_table, stretch=1)

        tab.setLayout(vbox)
        self.tabs.addTab(tab, "🚫 Ad Detector")

    def _build_tools_tab(self):
        tab = QWidget()
        vbox = QVBoxLayout(tab)
        row = QHBoxLayout()
        btn_restore = QPushButton("♻️ Restore Backups")
        btn_restore.clicked.connect(self.restore_backup)
        btn_adb = QPushButton("⚙️ Change ADB Path")
        btn_adb.clicked.connect(self._choose_adb)
        row.addWidget(btn_restore)
        row.addWidget(btn_adb)
        row.addStretch()
        vbox.addLayout(row)
        self.log_console = QTextEdit()
        self.log_console.setReadOnly(True)
        vbox.addWidget(QLabel("Activity Log"))
        vbox.addWidget(self.log_console, stretch=1)
        tab.setLayout(vbox)
        self.tabs.addTab(tab, "🧰 Tools & Logs")

    # ----- Core Actions -----
    def log(self, msg):
        t = datetime.datetime.now().strftime("%H:%M:%S")
        if hasattr(self, "log_console"):
            self.log_console.append(f"[{t}] {msg}")
        print(f"[{t}] {msg}")

    def _auto_connect_and_refresh(self):
        adb = find_adb_executable()
        if adb:
            self.adb = adb
            try:
                with open(ADB_PATH_FILE, "w", encoding="utf-8") as f:
                    f.write(adb)
            except Exception:
                pass
            self.status_label.setText("Status: Connected to ADB")
            self.refresh_apps()
        else:
            self.status_label.setText("Status: ADB not found")
            # let user choose if they want
            dlg = QMessageBox(self)
            dlg.setWindowTitle("ADB Not Found")
            dlg.setText("ADB executable not found. Would you like to select it now?")
            dlg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            r = dlg.exec()
            if r == QMessageBox.StandardButton.Yes:
                self._choose_adb()

    def _choose_adb(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select adb executable", "", "ADB executable (adb*);;All Files (*)")
        if not path:
            return
        self.adb = path
        try:
            with open(ADB_PATH_FILE, "w", encoding="utf-8") as f:
                f.write(path)
        except Exception:
            pass
        self.status_label.setText("Status: ADB path set")
        self.refresh_apps()

    def refresh_apps(self):
        # clear both tables and populate them with the same package list
        self.apps_table.setRowCount(0)
        self.detector_table.setRowCount(0)
        if not self.adb:
            QMessageBox.warning(self, "ADB missing", "Set ADB first.")
            return
        self.status_label.setText("Status: Loading apps…")
        try:
            p = subprocess.run([self.adb, "shell", "pm", "list", "packages"],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=12)
            lines = [ln.strip().replace("package:", "") for ln in (p.stdout or p.stderr or "").splitlines() if ln.strip()]
            for pkg in lines:
                # device table
                r = self.apps_table.rowCount()
                self.apps_table.insertRow(r)
                self.apps_table.setItem(r, 0, QTableWidgetItem(pkg))
                self.apps_table.setItem(r, 1, QTableWidgetItem(""))
                # detector table (flags will be updated after scans)
                r2 = self.detector_table.rowCount()
                self.detector_table.insertRow(r2)
                self.detector_table.setItem(r2, 0, QTableWidgetItem(pkg))
                self.detector_table.setItem(r2, 1, QTableWidgetItem(""))
            self.lbl_conn.setText("Connected: ✅ Device")
            self.status_label.setText(f"Status: {len(lines)} apps loaded")
            self.log(f"Loaded {len(lines)} packages.")
            # refresh device details too (lightweight)
            self.refresh_device_info()
        except Exception as e:
            self.log(f"App load error: {e}")
            self.status_label.setText("Status: Load failed")

    def _filter_apps(self, text):
        t = text.lower().strip()
        for table in (self.apps_table, self.detector_table):
            for r in range(table.rowCount()):
                it = table.item(r, 0)
                if it:
                    table.setRowHidden(r, t not in it.text().lower())

    def _active_table(self) -> QTableWidget:
        # Return detector table when user is on the Detector tab, otherwise device table
        if self.tabs.currentIndex() == 1:
            return self.detector_table
        return self.apps_table

    def _get_selected_package(self) -> Optional[str]:
        table = self._active_table()
        row = table.currentRow()
        if row < 0:
            return None
        it = table.item(row, 0)
        return it.text() if it else None

    # ----- Device Info -----
    def _safe_getprop(self, prop: str) -> str:
        try:
            p = subprocess.run([self.adb, "shell", "getprop", prop], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=4)
            return (p.stdout or "").strip()
        except Exception:
            return ""

    def refresh_device_info(self):
        # Best-effort, lightweight device info collection
        try:
            if not self.adb:
                self.lbl_conn.setText("Connection: ❌ No ADB")
                return

            # check connected devices
            p = subprocess.run([self.adb, "devices"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=4)
            out = p.stdout or p.stderr or ""
            lines = [ln.strip() for ln in out.splitlines() if ln.strip()]
            # devices list typically starts after header, find lines with 'device'
            devices = []
            for ln in lines[1:]:
                if '\t' in ln:
                    serial, state = ln.split('\t', 1)
                    if state.strip() == "device":
                        devices.append(serial.strip())
                elif "device" in ln and not ln.startswith("List"):
                    parts = ln.split()
                    if parts:
                        devices.append(parts[0].strip())
            if not devices:
                self.lbl_conn.setText("Connection: ❌ No device")
                self.lbl_serial.setText("Serial: -")
                self.lbl_manufacturer.setText("Manufacturer: -")
                self.lbl_model.setText("Model: -")
                self.lbl_android.setText("Android: -")
                self.lbl_sdk.setText("SDK: -")
                self.lbl_cpu.setText("CPU ABI: -")
                self.lbl_battery.setText("Battery: -")
                self.lbl_storage.setText("Storage (/data): -")
                self.lbl_ip.setText("IP (wlan0): -")
                return

            serial = devices[0]
            self.lbl_serial.setText(f"Serial: {serial}")
            self.lbl_conn.setText("Connection: ✅ Device")

            # properties
            manufacturer = self._safe_getprop("ro.product.manufacturer") or "-"
            model = self._safe_getprop("ro.product.model") or "-"
            android = self._safe_getprop("ro.build.version.release") or "-"
            sdk = self._safe_getprop("ro.build.version.sdk") or "-"
            cpu = (self._safe_getprop("ro.product.cpu.abi") or
                   self._safe_getprop("ro.product.cpu.abilist") or "-")

            self.lbl_manufacturer.setText(f"Manufacturer: {manufacturer}")
            self.lbl_model.setText(f"Model: {model}")
            self.lbl_android.setText(f"Android: {android}")
            self.lbl_sdk.setText(f"SDK: {sdk}")
            self.lbl_cpu.setText(f"CPU ABI: {cpu}")

            # battery info
            try:
                bp = subprocess.run([self.adb, "shell", "dumpsys", "battery"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=4)
                b_out = bp.stdout or bp.stderr or ""
                level = "-"
                status = "-"
                for line in b_out.splitlines():
                    line = line.strip()
                    if line.startswith("level:"):
                        level = line.split(":", 1)[1].strip()
                    elif line.startswith("status:"):
                        # status numeric may be 1/2/3/4/5 map to unknown/charging/discharging/not charging/full
                        st = line.split(":", 1)[1].strip()
                        status_map = {"1": "Unknown", "2": "Charging", "3": "Discharging", "4": "Not charging", "5": "Full"}
                        status = status_map.get(st, st)
                self.lbl_battery.setText(f"Battery: {level}% ({status})" if level != "-" else f"Battery: {status}")
            except Exception:
                self.lbl_battery.setText("Battery: -")

            # storage for /data (best-effort)
            try:
                sp = subprocess.run([self.adb, "shell", "df", "/data"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=4)
                s_out = sp.stdout or sp.stderr or ""
                # parse the first line that contains '/', columns either: Filesystem Size Used Avail Use% Mounted on
                storage_text = "-"
                for line in s_out.splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    # skip header lines that don't contain '/'
                    if '/' in line and ('/data' in line or line.startswith('/')):
                        cols = line.split()
                        # try to show "Used / Size" or last two columns if available
                        if len(cols) >= 3:
                            # assume columns like: Filesystem 1K-blocks Used Available Use% Mounted on
                            # find numeric columns
                            numeric = [c for c in cols if any(ch.isdigit() for ch in c)]
                            if len(numeric) >= 2:
                                storage_text = f"{numeric[1]} / {numeric[0]}"
                            else:
                                storage_text = line
                        else:
                            storage_text = line
                        break
                self.lbl_storage.setText(f"Storage (/data): {storage_text}")
            except Exception:
                self.lbl_storage.setText("Storage (/data): -")

            # IP address (wlan0) - best-effort
            try:
                ip_p = subprocess.run([self.adb, "shell", "ip", "-4", "addr", "show", "wlan0"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=3)
                ip_out = ip_p.stdout or ip_p.stderr or ""
                ip = "-"
                for line in ip_out.splitlines():
                    line = line.strip()
                    if line.startswith("inet "):
                        # format: inet 192.168.x.y/24 ...
                        parts = line.split()
                        if len(parts) >= 2:
                            ip = parts[1].split('/')[0]
                            break
                self.lbl_ip.setText(f"IP (wlan0): {ip}")
            except Exception:
                self.lbl_ip.setText("IP (wlan0): -")

        except Exception as e:
            self.log(f"Device info error: {e}")
            # leave labels as-is on failure

    # ----- Backup & Restore -----
    def backup_selected(self):
        pkg = self._get_selected_package()
        if not pkg:
            QMessageBox.information(self, "Select app", "Select an app first.")
            return
        try:
            os.makedirs(BACKUP_DIR, exist_ok=True)
            p = subprocess.run([self.adb, "shell", "pm", "path", pkg],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=8)
            path = (p.stdout or "").replace("package:", "").strip()
            if not path:
                QMessageBox.warning(self, "Backup failed", "Could not find APK path.")
                return
            dest = os.path.join(BACKUP_DIR, f"{pkg}.apk")
            pull = subprocess.run([self.adb, "pull", path, dest], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=30)
            out = (pull.stdout or "") + (pull.stderr or "")
            if os.path.exists(dest) or "1 file pulled" in out.lower():
                QMessageBox.information(self, "Backup complete", f"APK saved to: {dest}")
                self.log(f"APK backed up: {dest}")
            else:
                QMessageBox.warning(self, "Backup incomplete", f"Pull output: {out[:200]}")
                self.log(f"APK pull issue: {out}")
        except Exception as e:
            QMessageBox.warning(self, "Backup error", f"Error: {e}")
            self.log(f"Backup error: {e}")

    def restore_backup(self):
        if not os.path.exists(BACKUP_DIR):
            QMessageBox.information(self, "No backups", f"No backups folder found at {BACKUP_DIR}")
            return
        files, _ = QFileDialog.getOpenFileNames(self, "Select APKs to restore", BACKUP_DIR, "APK Files (*.apk)")
        if not files:
            return
        for fp in files:
            try:
                self.status_label.setText(f"Installing {os.path.basename(fp)}")
                subprocess.run([self.adb, "install", "-r", fp], stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
                self.log(f"Installed {fp}")
            except Exception as e:
                self.log(f"Restore error {fp}: {e}")
        self.status_label.setText("Status: Restore complete")
        self.refresh_apps()

    # ----- Uninstall -----
    def remove_selected(self):
        pkg = self._get_selected_package()
        if not pkg:
            QMessageBox.information(self, "No selection", "Select an app to uninstall.")
            return
        confirm = QMessageBox.question(self, "Confirm Uninstall", f"Uninstall {pkg}?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if confirm != QMessageBox.StandardButton.Yes:
            return
        self.status_label.setText(f"Status: Uninstalling {pkg}...")
        self.remove_worker = RemoveWorker(self.adb, pkg)
        self.remove_worker.finished.connect(self._on_uninstall_finished)
        self.remove_worker.start()

    def _on_uninstall_finished(self, info: str, success: bool):
        if success:
            QMessageBox.information(self, "Uninstalled", f"{info} uninstalled.")
            self.log(f"Uninstalled: {info}")
        else:
            QMessageBox.warning(self, "Uninstall Failed", f"{info}")
            self.log(f"Uninstall failed: {info}")
        self.status_label.setText("Status: Ready")
        self.refresh_apps()

    # ----- Scan Ads -----
    def start_scan_ads(self):
        if not self.adb:
            QMessageBox.information(self, "ADB missing", "ADB path not set. Please select adb.")
            return
        if self.apps_table.rowCount() == 0:
            QMessageBox.information(self, "No apps", "App list is empty. Refresh apps first.")
            return
        self.scan_btn.setEnabled(False)
        self.scan_stop_btn.setEnabled(True)
        self.progress.setValue(0)
        self.status_label.setText("Status: Scanning for ad SDKs...")
        self.scan_worker = ScanAdsWorker(self.adb, EXTENDED_AD_SDKS)
        self.scan_worker.progress.connect(self.progress.setValue)
        self.scan_worker.log.connect(self.log)
        self.scan_worker.result.connect(self._scan_done)
        self.scan_worker.start()

    def _stop_scan(self):
        if self.scan_worker:
            self.scan_worker.stop()
            self.scan_worker = None
            self.scan_btn.setEnabled(True)
            self.scan_stop_btn.setEnabled(False)
            self.status_label.setText("Status: Scan stopped")
            self.log("Scan stopped by user.")
            self.progress.setValue(0)

    def _scan_done(self, results: Dict[str, List[str]]):
        # clear previous flags on detector table
        for r in range(self.detector_table.rowCount()):
            it_pkg = self.detector_table.item(r, 0)
            flag_item = self.detector_table.item(r, 1)
            if it_pkg:
                it_pkg.setForeground(QColor(Qt.GlobalColor.white))
                it_pkg.setToolTip("")
            if flag_item:
                flag_item.setText("")
        flagged = 0
        for pkg, matches in results.items():
            for r in range(self.detector_table.rowCount()):
                it = self.detector_table.item(r, 0)
                if it and it.text() == pkg:
                    it.setForeground(QColor(Qt.GlobalColor.red))
                    flag_it = self.detector_table.item(r, 1)
                    if flag_it:
                        flag_it.setText("⚠️")
                    it.setToolTip("Detected: " + ", ".join(matches))
                    flagged += 1
                    break
        self.flagged_label.setText(f"Flagged: {flagged} apps")
        self.progress.setValue(100)
        self.scan_btn.setEnabled(True)
        self.scan_stop_btn.setEnabled(False)
        self.status_label.setText(f"Status: Scan complete. Flagged {flagged} apps.")
        self.log(f"Scan complete. Flagged {flagged} apps.")
        self.last_scan_results = results

    # ----- Export Report -----
    def _export_flagged_report(self):
        if not self.last_scan_results:
            QMessageBox.information(self, "No flagged apps", "No scan results to export.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Save Flagged Report", "flagged_apps.txt", "Text Files (*.txt)")
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write("GeloTech Android Ad Remover - Flagged Apps Report\n")
                f.write(f"Generated: {datetime.datetime.now()}\n\n")
                for pkg, matches in self.last_scan_results.items():
                    f.write(f"{pkg} -> {', '.join(matches)}\n")
            QMessageBox.information(self, "Report Saved", f"Report saved to:\n{path}")
            self.log(f"Flagged apps report saved: {path}")
        except Exception as e:
            QMessageBox.warning(self, "Export Failed", f"Failed to export: {e}")
            self.log(f"Export failed: {e}")

# -------------------------
# Entrypoint
# -------------------------
def main():
    app = QApplication(sys.argv)
    adb = find_adb_executable()
    if not adb:
        dlg = QMessageBox()
        dlg.setText("ADB executable not found automatically.")
        dlg.setInformativeText("Would you like to select adb now?")
        dlg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        ret = dlg.exec()
        if ret == QMessageBox.StandardButton.Yes:
            path, _ = QFileDialog.getOpenFileName(None, "Select adb executable", "", "ADB executable (adb.exe);;All Files (*)")
            if not path:
                adb = ""
            else:
                adb = path
                try:
                    with open(ADB_PATH_FILE, "w", encoding="utf-8") as f:
                        f.write(adb)
                except Exception:
                    pass
        else:
            adb = ""
    window = GeloTechApp(adb)
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()