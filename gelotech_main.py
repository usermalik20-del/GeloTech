import sys
from PyQt6.QtWidgets import QApplication, QMessageBox, QFileDialog
from .adb_utils import find_adb_executable
from .ui import GeloTechApp

def main(argv=None):
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
                    from .constants import ADB_PATH_FILE
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
