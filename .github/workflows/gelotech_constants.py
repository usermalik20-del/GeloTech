import os
import sys

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