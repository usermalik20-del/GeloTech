import os
import datetime
import webbrowser
import subprocess
from typing import List, Dict, Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QPushButton, QLabel, QProgressBar, QLineEdit, QFileDialog,
    QMessageBox, QTableWidget, QTableWidgetItem, QHeaderView, QTextEdit,
    QGroupBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QIcon, QPalette

from .constants import ADAWAY_LINK, EXTENDED_AD_SDKS, ADB_PATH_FILE, ICO_FILE, BACKUP_DIR
from .adb_utils import find_adb_executable
from .workers import RemoveWorker, ScanAdsWorker, ServicesWorker
from .logger import log, register_console_widget

class GeloTechApp(QWidget):
    def __init__(self, adb_path: Optional[str]):
        super().__init__()
        self.setWindowTitle("GeloTech Android Ad Remover V1")
        if os.path.exists(ICO_FILE):
            try:
                self.setWindowIcon(QIcon(ICO_FILE))
            except Exception:
                pass
        self.resize(1100, 720)
        self.adb = adb_path or ""
        self.scan_worker = None
        self.remove_worker = None
        self.services_worker = None
        self.last_scan_results: Dict[str, List[str]] = {}

        self._apply_dark_theme()
        self._build_ui()
        self._auto_connect_and_refresh()

    def _apply_dark_theme(self):
        QApplication = __import__("PyQt6.QtWidgets", fromlist=["QApplication"]).QApplication
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
        btn_adaway = QPushButton("⬇️ Download AdAway")
        btn_adaway.clicked.connect(lambda: webbrowser.open(ADAWAY_LINK))
        dash_layout.addWidget(btn_adaway)
        dash.setLayout(dash_layout)
        layout.addWidget(dash)

        self.tabs = QTabWidget()
        layout.addWidget(self.tabs, stretch=1)
        self._build_device_apps_tab()
        self._build_detector_tab()
        self._build_services_tab()   # NEW: Running Services tab
        self._build_tools_tab()
        self.setLayout(layout)

    def _build_device_apps_tab(self):
        tab = QWidget()
        vbox = QVBoxLayout(tab)

        info_box = QGroupBox("Device Info")
        il = QVBoxLayout()

        self.lbl_conn = QLabel("Connection: ❌ No device found")
        self.lbl_serial = QLabel("Serial: -")
        self.lbl_manufacturer = QLabel("Manufacturer: -")
        self.lbl_model = QLabel("Model: -")
        self.lbl_android = QLabel("Android: -")
        self.lbl_sdk = QLabel("SDK: -")
        self.lbl_cpu = QLabel("CPU ABI: -")
        self.lbl_battery = QLabel("Battery: -")
        self.lbl_storage = QLabel("Storage (/data): -")
        self.lbl_ip = QLabel("IP (wlan0): -")

        btn_info_refresh = QPushButton("🔄 Refresh Device Info")
        btn_info_refresh.setToolTip("Query device for latest information")
        btn_info_refresh.clicked.connect(self.refresh_device_info)

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
        self.tabs.addTab(tab, "📱 Connected Device")

    def _build_detector_tab(self):
        tab = QWidget()
        vbox = QVBoxLayout(tab)

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
            b.setMinimumHeight(40)
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

        self.detector_table = QTableWidget(0, 2)
        self.detector_table.setHorizontalHeaderLabels(["Package", "Flag"])
        self.detector_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.detector_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.detector_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        vbox.addWidget(self.detector_table, stretch=1)

        tab.setLayout(vbox)
        self.tabs.addTab(tab, "🚫 Ad Detector")

    def _build_services_tab(self):
        tab = QWidget()
        vbox = QVBoxLayout(tab)

        act_box = QGroupBox("Services")
        hl = QHBoxLayout()
        self.btn_services_refresh = QPushButton("🔄 Refresh Services")
        self.btn_services_refresh.setToolTip("Query device for running services")
        self.btn_services_refresh.clicked.connect(self.refresh_services)

        self.btn_services_stop = QPushButton("⛔ Stop Selected Service")
        self.btn_services_stop.setToolTip("Stop the selected service component on device")
        self.btn_services_stop.clicked.connect(self.stop_selected_service)

        hl.addWidget(self.btn_services_refresh)
        hl.addWidget(self.btn_services_stop)
        hl.addStretch()

        self.services_busy = QProgressBar()
        self.services_busy.setRange(0, 0)  # indeterminate
        self.services_busy.setVisible(False)
        self.services_busy.setFixedWidth(120)
        hl.addWidget(self.services_busy)

        act_box.setLayout(hl)
        vbox.addWidget(act_box)

        info = QLabel("List running service components discovered via adb dumpsys. Select a service then click Stop.")
        info.setWordWrap(True)
        vbox.addWidget(info)

        self.services_table = QTableWidget(0, 2)
        self.services_table.setHorizontalHeaderLabels(["Package", "Service Component"])
        self.services_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.services_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.services_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        vbox.addWidget(self.services_table, stretch=1)

        tab.setLayout(vbox)
        self.tabs.addTab(tab, "⚙️ Running Services")

    def refresh_services(self):
        if not self.adb:
            QMessageBox.information(self, "ADB missing", "ADB path not set. Please select adb.")
            return
        self.status_label.setText("Status: Querying running services...")
        self.services_table.setRowCount(0)
        self.services_busy.setVisible(True)
        self.btn_services_refresh.setEnabled(False)
        self.btn_services_stop.setEnabled(False)

        self.services_worker = ServicesWorker(self.adb)
        self.services_worker.log.connect(self.log)
        self.services_worker.result.connect(self._services_done)
        self.services_worker.start()

    def _services_done(self, results: Dict[str, List[str]]):
        self.services_busy.setVisible(False)
        self.btn_services_refresh.setEnabled(True)
        self.btn_services_stop.setEnabled(True)

        self.services_table.setRowCount(0)
        rows = 0
        for pkg, comps in sorted(results.items()):
            for comp in comps:
                r = self.services_table.rowCount()
                self.services_table.insertRow(r)
                self.services_table.setItem(r, 0, QTableWidgetItem(pkg))
                self.services_table.setItem(r, 1, QTableWidgetItem(comp))
                rows += 1
        self.status_label.setText(f"Status: Services listed ({rows}).")
        self.log(f"Services listed: {rows} rows.")
        self.services_worker = None

    def _active_table(self) -> QTableWidget:
        idx = self.tabs.currentIndex()
        if idx == 2:
            return self.services_table
        if idx == 1:
            return self.detector_table
        return self.apps_table

    def stop_selected_service(self):
        if not self.adb:
            QMessageBox.information(self, "ADB missing", "ADB not set.")
            return
        table = self.services_table
        row = table.currentRow()
        if row < 0:
            QMessageBox.information(self, "Select service", "Select a service to stop.")
            return
        comp_item = table.item(row, 1)
        if not comp_item:
            QMessageBox.information(self, "No service selected", "Select a valid service row.")
            return
        component = comp_item.text().strip()
        confirm = QMessageBox.question(self, "Stop Service", f"Stop service:\n{component} ?",
                                       QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if confirm != QMessageBox.StandardButton.Yes:
            return
        self.status_label.setText(f"Status: Stopping {component} ...")
        try:
            p = subprocess.run([self.adb, "shell", "am", "stopservice", "--user", "0", component],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=12)
            out = (p.stdout or "") + (p.stderr or "")
            if "Stopping service" in out or "StopService" in out or p.returncode == 0:
                QMessageBox.information(self, "Service Stopped", f"Stop request sent for {component}")
                self.log(f"Stopservice output: {out.strip()}")
            else:
                if p.returncode == 0:
                    QMessageBox.information(self, "Service Stop Requested", f"Stop request sent for {component}")
                    self.log(f"Stopservice returned code 0 for {component}")
                else:
                    QMessageBox.warning(self, "Stop Failed", f"Output: {out.strip()}")
                    self.log(f"Stopservice failed: {out.strip()}")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Error stopping service: {e}")
            self.log(f"Stop service error: {e}")
        finally:
            self.refresh_services()
