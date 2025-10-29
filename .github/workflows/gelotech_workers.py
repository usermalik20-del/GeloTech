import subprocess
import re
from typing import List, Dict, Optional
from PyQt6.QtCore import QThread, pyqtSignal

def extract_components_from_text(dumpsys_text: str) -> Dict[str, List[str]]:
    """
    Robust extraction of package/component tokens from dumpsys output.

    Returns a mapping: package -> [component_token, ...]
    The extraction tries multiple patterns commonly observed in dumpsys outputs:
      - explicit package/component tokens like com.example/.MyService or com.example/MyService
      - tokens inside braces: ServiceRecord{... com.example/.MyService ...}
      - ComponentInfo{... com.example/.MyService ...}
      - fallback small tokens from 'service list' style output

    The function normalizes tokens, strips trailing punctuation, dedupes results,
    and groups components by their package name (left of slash).
    """
    if not dumpsys_text:
        return {}

    # keep original for nicer display (we will return tokens as found here when possible)
    orig = dumpsys_text

    # Prepare a set for matches (store normalized token form)
    matches = []

    # Pattern A: explicit package/component like com.example/.MyService or com.example/MyService
    # Accept letters, digits, underscore, dot for package; class part may include $ for inner classes.
    pat_a = re.compile(r'\b([A-Za-z0-9_\.]+/(?:\.[A-Za-z0-9_\.$]+|[A-Za-z0-9_\.$]+))\b')

    # Pattern B: ComponentInfo{... com.example/.MyService ...} or ServiceRecord{... com.example/.MyService ...}
    # We'll capture package/component tokens anywhere inside braces as well
    pat_b = re.compile(r'\{[^}]*?\b([A-Za-z0-9_\.]+/(?:\.[A-Za-z0-9_\.$]+|[A-Za-z0-9_\.$]+))\b[^}]*\}')

    # Pattern C: Component names appearing after keywords like "ComponentInfo:" or "service="
    pat_c = re.compile(r'(?:ComponentInfo:|service=|service_name=)\s*([A-Za-z0-9_\.]+/(?:\.[A-Za-z0-9_\.$]+|[A-Za-z0-9_\.$]+))', re.IGNORECASE)

    # Pattern D: fallback lines from `service list` or other outputs like:
    #  " 42: activity: [com.example/.MyService]" or "com.example/.MyService u0a123"
    pat_d = re.compile(r'\b([A-Za-z0-9_\.]+/[A-Za-z0-9_\.$]+)\b')

    # run patterns against original text (so we can preserve case when possible)
    for pat in (pat_a, pat_b, pat_c, pat_d):
        for m in pat.findall(orig):
            if not m:
                continue
            token = m.strip()
            # strip trailing punctuation that often appears in dumpsys snippets
            token = token.rstrip(';,)')
            # skip tokens that don't contain a slash (defensive)
            if '/' not in token:
                continue
            matches.append(token)

    # post-process matches: normalize duplicates (case sensitive preference to original-case),
    # remove tokens that are obviously not components (very short right-hand side)
    cleaned = []
    seen_lower = set()
    for tok in matches:
        # e.g., sometimes dumpsys includes numeric suffixes like "com.example/.SVC:123"
        tok = re.sub(r':[0-9]+$', '', tok)
        tok = tok.strip()
        if not tok or '/' not in tok:
            continue
        # right side should contain at least a letter
        right = tok.split('/', 1)[1]
        if not re.search(r'[A-Za-z]', right):
            continue
        key = tok.lower()
        if key in seen_lower:
            continue
        seen_lower.add(key)
        cleaned.append(tok)

    # Group by package (left of slash)
    mapping: Dict[str, List[str]] = {}
    for tok in cleaned:
        pkg = tok.split('/', 1)[0]
        mapping.setdefault(pkg, []).append(tok)

    # Sort components per package for stable output
    for pkg in list(mapping.keys()):
        mapping[pkg] = sorted(mapping[pkg])

    return mapping


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

    def stop(self):
        self._stop = True

    def run(self):
        results: Dict[str, List[str]] = {}
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
                try:
                    dump = subprocess.run([self.adb, "shell", "pm", "dump", pkg],
                                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=8)
                    text = (dump.stdout or dump.stderr or "").lower()
                    for ident in self.ad_identifiers:
                        if ident.lower() in text:
                            matches.add(ident)
                except Exception:
                    pass
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


class ServicesWorker(QThread):
    """
    Worker to discover running service components on the device using adb dumpsys.
    Emits a dict mapping package -> list of service components.
    """
    log = pyqtSignal(str)
    result = pyqtSignal(dict)

    def __init__(self, adb_path: str):
        super().__init__()
        self.adb = adb_path
        self._stop = False

    def stop(self):
        self._stop = True

    def _extract_components(self, dumpsys_text: str) -> Dict[str, List[str]]:
        # Use the helper so tests can call it directly
        return extract_components_from_text(dumpsys_text)

    def run(self):
        results: Dict[str, List[str]] = {}
        if not self.adb:
            self.log.emit("ADB path not set for ServicesWorker.")
            self.result.emit(results)
            return
        try:
            self.log.emit("Querying running services (dumpsys activity services)...")
            p = subprocess.run([self.adb, "shell", "dumpsys", "activity", "services"],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=30)
            out = (p.stdout or p.stderr or "")
            if not out.strip():
                # Fallback: 'service list' might present limited info on some devices.
                self.log.emit("Empty dumpsys output, trying 'service list' fallback...")
                p2 = subprocess.run([self.adb, "shell", "service", "list"],
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=10)
                out = (p2.stdout or p2.stderr or "")

            mapping = self._extract_components(out)
            self.log.emit(f"Found services for {len(mapping)} packages.")
            self.result.emit(mapping)
        except Exception as e:
            self.log.emit(f"Services query error: {e}")
            self.result.emit(results)