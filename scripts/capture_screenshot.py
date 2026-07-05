"""Создаёт скриншот окна Junk Cleaner для страницы загрузки."""

import os
import subprocess
import sys
import time

try:
    import mss
    import mss.tools
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "mss", "-q"])
    import mss
    import mss.tools


def main():
    exe = os.path.join(os.environ["USERPROFILE"], "Desktop", "JunkCleaner.exe")
    if not os.path.isfile(exe):
        exe = os.path.join(os.path.dirname(__file__), "..", "release", "v1.0.0", "JunkCleaner-1.0.0-windows.exe")
        exe = os.path.abspath(exe)

    out_dir = os.path.join(os.path.dirname(__file__), "..", "docs", "screenshots")
    os.makedirs(out_dir, exist_ok=True)

    proc = subprocess.Popen([exe])
    time.sleep(6)

    with mss.mss() as sct:
        monitor = sct.monitors[1]
        shot = sct.grab(monitor)
        path = os.path.join(out_dir, "main-window.png")
        mss.tools.to_png(shot.rgb, shot.size, output=path)

    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()

    print(f"Screenshot saved: {path}")


if __name__ == "__main__":
    main()
