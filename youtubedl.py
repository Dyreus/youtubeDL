# -*- coding: utf-8 -*-
import sys
import os
import json
import subprocess
import shutil
import urllib.request
import threading

# ── Version & GitHub ─────────────────────────────────────────────────────────
APP_VERSION = "1.0.4"
GITHUB_REPO = "Dyreus/youtubeDL"
GITHUB_API  = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"

# ── Thư mục gốc của app ──────────────────────────────────────────────────────
APP_DIR = os.path.dirname(os.path.abspath(sys.argv[0]))
APP_EXE = os.path.abspath(sys.argv[0])

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

def cls():
    os.system("cls" if os.name == "nt" else "clear")

def getch():
    """Đọc 1 phím bấm, không cần Enter"""
    try:
        import msvcrt
        ch = msvcrt.getch()
        return ch.decode("utf-8", errors="ignore")
    except Exception:
        return input()

import yt_dlp

# ── Tự động cập nhật app qua GitHub Releases ────────────────────────────────
def check_app_update():
    if not getattr(sys, "frozen", False):
        return  # chỉ update khi chạy exe
    try:
        req = urllib.request.Request(GITHUB_API, headers={"User-Agent": "YouTubeDL-Updater"})
        with urllib.request.urlopen(req, timeout=5) as r:
            data = json.loads(r.read())
        latest = data["tag_name"].lstrip("v")
        if latest <= APP_VERSION:
            return  # đã là bản mới nhất

        # Tìm file exe trong release assets
        asset_url = None
        for asset in data.get("assets", []):
            if asset["name"].endswith(".exe"):
                asset_url = asset["browser_download_url"]
                break
        if not asset_url:
            return

        print(f"🆕 Có bản mới: v{latest} (hiện tại: v{APP_VERSION})")
        print("⏳ Đang tải bản cập nhật...")

        new_exe = APP_EXE + ".new"
        urllib.request.urlretrieve(asset_url, new_exe)

        # Dùng batch script để thay thế exe sau khi app đóng
        bat = APP_EXE + "_update.bat"
        with open(bat, "w") as f:
            f.write(f"""@echo off
ping 127.0.0.1 -n 3 >nul
move /y "{new_exe}" "{APP_EXE}"
start "" "{APP_EXE}"
del "%~f0"
""")
        subprocess.Popen(["cmd", "/c", bat], creationflags=0x08000000)
        print("✅ Cập nhật xong! App sẽ tự khởi động lại...")
        os._exit(0)

    except Exception:
        pass  # không có mạng hoặc lỗi → bỏ qua, chạy bình thường

# Chạy update ngầm, không block khởi động
threading.Thread(target=check_app_update, daemon=True).start()

# ── Tự động cập nhật yt-dlp ─────────────────────────────────────────────────
def ensure_ytdlp():
    if getattr(sys, "frozen", False):
        try:
            from yt_dlp import YoutubeDL
            with YoutubeDL({"quiet": True}) as ydl:
                ydl.update_self(to_screen=False, use_updater=True)
        except Exception:
            pass
    else:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-U", "yt-dlp", "-q"],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

threading.Thread(target=ensure_ytdlp, daemon=True).start()

# ── Tìm ffmpeg (bundled trong exe hoặc trong PATH) ───────────────────────────
def find_ffmpeg():
    if getattr(sys, "frozen", False):
        bundled = os.path.join(sys._MEIPASS, "ffmpeg.exe")
        if os.path.exists(bundled):
            return bundled
    local = os.path.join(APP_DIR, "ffmpeg.exe")
    if os.path.exists(local):
        return local
    if shutil.which("ffmpeg"):
        return shutil.which("ffmpeg")
    return None

FFMPEG_PATH = find_ffmpeg()

# ── Config ──────────────────────────────────────────────────────────────────
CONFIG_FILE = os.path.join(APP_DIR, "config.json")

DEFAULT_CONFIG = {
    "video_folder": str(os.path.join(os.path.expanduser("~"), "Videos")),
    "audio_folder": str(os.path.join(os.path.expanduser("~"), "Music")),
}

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return DEFAULT_CONFIG.copy()

def save_config(config):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

# ── Download ─────────────────────────────────────────────────────────────────
def base_opts():
    opts = {
        "no_warnings": True,
        "concurrent_fragment_downloads": 16,
        "buffersize": 1024 * 16,
        "http_chunk_size": 1024 * 1024 * 10,
    }
    opts["extractor_args"] = {"youtube": {"player_client": ["default"]}}
    if FFMPEG_PATH:
        opts["ffmpeg_location"] = os.path.dirname(FFMPEG_PATH) if os.path.isfile(FFMPEG_PATH) else None
    return opts

def download_video(url, folder):
    ydl_opts = {
        "format": "bestvideo+bestaudio[ext=m4a]/bestvideo+bestaudio/best",
        "merge_output_format": "mp4",
        "outtmpl": os.path.join(folder, "%(title)s.%(ext)s"),
        **base_opts(),
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
        print(f"  ✅ Xong: {info.get('title', 'Unknown')}")
    except Exception as e:
        print(f"  ❌ Thất bại: {e}")

def download_audio(url, folder):
    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": os.path.join(folder, "%(title)s.%(ext)s"),
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "m4a",
            "preferredquality": "0",
        }],
        **base_opts(),
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
        print(f"  ✅ Xong: {info.get('title', 'Unknown')}")
    except Exception as e:
        print(f"  ❌ Thất bại: {e}")

# ── Fetch tên video từ link ──────────────────────────────────────────────────
def fetch_title(url):
    opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "extractor_args": {"youtube": {"player_client": ["android_vr", "android", "tv_embedded"]}},
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return info.get("title", url)
    except Exception:
        return None

# ── Menu danh sách link ──────────────────────────────────────────────────────
def show_queue_menu(queue, folder):
    cls()
    print(f"📁 Lưu vào: {folder}")
    print(f"📋 Danh sách ({len(queue)} link):")
    if queue:
        for i, (url, title) in enumerate(queue, 1):
            print(f"  {i}. {title}")
            print(f"     {url}")
    else:
        print("  [Chưa có link nào]")
    print("\nVui lòng chọn 1 trong các lựa chọn sau:")
    print("  1. Thêm link")
    if queue:
        print("  2. Xóa link")
        print("  3. Bắt đầu tải")
    print("  0. Quay lại menu chính")

def input_links(action, folder):
    queue = []

    while True:
        show_queue_menu(queue, folder)
        print("\nChọn: ", end="", flush=True)
        choice = getch().strip()

        if choice == "0":
            break

        elif choice == "1":
            cls()
            link = input("Nhập link YouTube: ").strip()
            if not link:
                continue
            print("🔍 Đang lấy thông tin video...")
            title = fetch_title(link)
            if title is None:
                input("❌ Link không hợp lệ hoặc không lấy được thông tin.\n[Nhấn Enter để tiếp tục]")
            else:
                queue.append((link, title))

        elif choice == "2" and queue:
            cls()
            print(f"📋 Danh sách ({len(queue)} link):")
            for i, (url, title) in enumerate(queue, 1):
                print(f"  {i}. {title}")
            idx = input(f"\nNhập số thứ tự link muốn xóa (1-{len(queue)}): ").strip()
            if idx.isdigit() and 1 <= int(idx) <= len(queue):
                queue.pop(int(idx) - 1)

        elif choice == "3" and queue:
            cls()
            print(f"⏳ Đang tải {len(queue)} mục...\n")
            for i, (url, title) in enumerate(queue, 1):
                print(f"[{i}/{len(queue)}] {title}")
                action(url, folder)
                print()
            queue.clear()
            input("\n✅ Hoàn thành tất cả!\n[Nhấn Enter để quay lại]")

# ── Đổi đường dẫn ────────────────────────────────────────────────────────────
def pick_folder(current_path):
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        chosen = filedialog.askdirectory(initialdir=current_path, title="Chọn thư mục lưu")
        root.destroy()
        return chosen if chosen else None
    except Exception:
        return None

def change_folder(config, key):
    new_path = pick_folder(config[key])
    if new_path:
        config[key] = new_path
        save_config(config)

# ── Main ─────────────────────────────────────────────────────────────────────
def show_main_menu(config):
    cls()
    print("=" * 40)
    print(f"   YouTube Downloader  v{APP_VERSION}")
    print("=" * 40)
    print(f"  1. Tải video  (MP4)  →  {config['video_folder']}")
    print(f"  2. Tải âm thanh (M4A) →  {config['audio_folder']}")
    print(f"  3. Đổi đường dẫn lưu video")
    print(f"  4. Đổi đường dẫn lưu âm thanh")
    print(f"  0. Thoát")
    print("=" * 40)
    print("Vui lòng chọn 1 trong các lựa chọn trên:")

def main():
    config = load_config()

    while True:
        show_main_menu(config)
        print("Chọn: ", end="", flush=True)
        choice = getch().strip()

        if choice == "1":
            input_links(download_video, config["video_folder"])
        elif choice == "2":
            input_links(download_audio, config["audio_folder"])
        elif choice == "3":
            change_folder(config, "video_folder")
        elif choice == "4":
            change_folder(config, "audio_folder")
        elif choice == "0":
            cls()
            break

if __name__ == "__main__":
    main()
