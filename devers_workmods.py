import sys
import os
import json
import shutil
import zipfile
import math
import time
import uuid
import hashlib
import base64
import webbrowser
import requests
import traceback
from pathlib import Path
from datetime import datetime
from urllib.parse import urlparse, parse_qs
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QTabWidget, QVBoxLayout,
    QHBoxLayout, QLabel, QPushButton, QListWidget, QListWidgetItem,
    QLineEdit, QTextEdit, QProgressBar, QFileDialog, QMessageBox,
    QFrame, QSplitter, QComboBox, QDialog, QFormLayout, QScrollArea, QInputDialog
)
from PyQt6.QtCore import Qt, QUrl, QTimer, QObject, pyqtSignal, QSize, QRectF, QThread, QSignalBlocker
from PyQt6.QtGui import QIcon, QFont, QColor, QPainter, QPixmap
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply

APP_NAME = "Workmods"
APP_VERSION = "1.0.0"
DATA_DIR = Path("data")
CONFIG_DIR = Path.home() / ".devers_workmods"
CONFIG_FILE = CONFIG_DIR / "config.json"

GITHUB_CLIENT_ID = "Ov23liTU4bp8UkRw1Wco"
GITHUB_CLIENT_SECRET = "876493fead76f7880f20e51c7dc072832e4980e2"
REGISTRY_REPO = "Made-by-One/Devers-Workmods"
BOT_SECRET = "super_secret_workmods_2026" 

DEFAULT_CONFIG = {
    "registry_url": f"https://raw.githubusercontent.com/{REGISTRY_REPO}/main/registry.json",
    "install_dir": str(Path.home() / "DeversMods"),
    "language": "en",
    "github_token": ""
}

def global_except_hook(exctype, value, tb):
    traceback.print_exception(exctype, value, tb)
    sys.__excepthook__(exctype, value, tb)

sys.excepthook = global_except_hook

# ==========================================
# 1. УТИЛИТЫ
# ==========================================
class Localization:
    def __init__(self, lang="en"):
        self.lang = lang
        self.strings = {}
        self.load(lang)
    def load(self, lang):
        self.lang = lang
        p = DATA_DIR / "localization" / f"{lang}.json"
        if p.exists():
            try:
                with open(p, "r", encoding="utf-8") as f: self.strings = json.load(f)
            except: pass
    def t(self, key, default=""): return self.strings.get(key, default)

def get_available_languages():
    lang_dir = DATA_DIR / "localization"
    if not lang_dir.exists(): return ["en"]
    langs = [f.stem for f in lang_dir.glob("*.json")]
    return sorted(langs) if langs else ["en"]

def load_config():
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            for k, v in DEFAULT_CONFIG.items(): cfg.setdefault(k, v)
            return cfg
        except Exception: pass
    return dict(DEFAULT_CONFIG)

def save_config(cfg):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)

def get_icon(name):
    p = DATA_DIR / "icon" / f"{name}.png"
    if not p.exists(): return QIcon()
    pixmap_white = QPixmap(str(p))
    img = pixmap_white.toImage(); img.invertPixels()
    result = QIcon()
    result.addPixmap(pixmap_white, QIcon.Mode.Normal)
    result.addPixmap(QPixmap.fromImage(img), QIcon.Mode.Selected)
    result.addPixmap(pixmap_white, QIcon.Mode.Active)
    return result

def is_mod_installed(config, mod_id):
    return (Path(config["install_dir"]) / mod_id).is_dir()

def read_mod_meta(config, mod_id):
    p = Path(config["install_dir"]) / mod_id / ".devers_meta.json"
    if p.exists():
        try:
            with open(p, "r", encoding="utf-8") as f: return json.load(f)
        except: pass
    return {}

def open_folder(path):
    if not path: return
    if sys.platform == "win32": os.startfile(path)
    elif sys.platform == "darwin": os.system(f"open '{path}'")
    else: os.system(f"xdg-open '{path}'")

def get_sha256(filepath):
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

# ==========================================
# 2. ПОТОКИ И СЕТЬ
# ==========================================
class GitHubFetcher(QThread):
    finished = pyqtSignal(dict, str)
    def __init__(self, token):
        super().__init__()
        self.token = token
    def run(self):
        try:
            headers = {"Authorization": f"token {self.token}"}
            res = requests.get("https://api.github.com/user", headers=headers, timeout=5)
            if res.status_code == 200: self.finished.emit(res.json(), "")
            else: self.finished.emit({}, "Session expired.")
        except Exception as e: self.finished.emit({}, str(e))

class GitHubRepoFetcher(QThread):
    finished = pyqtSignal(list, str)
    def __init__(self, token):
        super().__init__()
        self.token = token
    def run(self):
        try:
            headers = {"Authorization": f"token {self.token}"}
            res = requests.get("https://api.github.com/user/repos?per_page=100&sort=updated", headers=headers, timeout=10)
            if res.status_code == 200: self.finished.emit(res.json(), "")
            else: self.finished.emit([], "Failed to fetch repos.")
        except Exception as e: self.finished.emit([], str(e))

class OAuthServerThread(QThread):
    auth_success = pyqtSignal(str)
    def run(self):
        class Handler(BaseHTTPRequestHandler):
            def do_GET(inner_self):
                parsed = urlparse(inner_self.path)
                if parsed.path == '/':
                    query = parse_qs(parsed.query)
                    if 'code' in query:
                        code = query['code'][0]
                        res = requests.post('https://github.com/login/oauth/access_token', 
                            headers={'Accept': 'application/json'},
                            data={'client_id': GITHUB_CLIENT_ID, 'client_secret': GITHUB_CLIENT_SECRET, 'code': code})
                        if res.status_code == 200:
                            token = res.json().get('access_token')
                            if token:
                                inner_self.send_response(200)
                                inner_self.send_header('Content-Type', 'text/html; charset=utf-8')
                                inner_self.end_headers()
                                
                                html_success = """
                                <!DOCTYPE html>
                                <html>
                                <head>
                                    <title>Authentication Successful</title>
                                    <style>
                                        body {
                                            background-color: #0a0a0b;
                                            color: #c9c5c7;
                                            font-family: 'Consolas', 'Courier New', monospace;
                                            display: flex;
                                            justify-content: center;
                                            align-items: center;
                                            height: 100vh;
                                            margin: 0;
                                        }
                                        .container {
                                            text-align: center;
                                            border: 1px solid #262326;
                                            padding: 40px;
                                            background: #0e0d0f;
                                            border-radius: 8px;
                                            box-shadow: 0 4px 20px rgba(0,0,0,0.5);
                                        }
                                        h1 { color: #a78bfa; margin-bottom: 10px; font-size: 24px; }
                                        p { color: #858080; font-size: 14px; }
                                        .icon { font-size: 40px; margin-bottom: 20px; color: #a78bfa; }
                                    </style>
                                </head>
                                <body>
                                    <div class="container">
                                        <div class="icon">✓</div>
                                        <h1>Auth Successful</h1>
                                        <p>You can close this window and return to Workmods.</p>
                                    </div>
                                </body>
                                </html>
                                """
                                inner_self.wfile.write(html_success.encode('utf-8'))
                                self.auth_success.emit(token)
                                return
                
                inner_self.send_response(400)
                inner_self.send_header('Content-Type', 'text/html; charset=utf-8')
                inner_self.end_headers()
                
                html_error = """
                <!DOCTYPE html>
                <html>
                <head>
                    <title>Authentication Failed</title>
                    <style>
                        body {
                            background-color: #0a0a0b;
                            color: #c9c5c7;
                            font-family: 'Consolas', 'Courier New', monospace;
                            display: flex;
                            justify-content: center;
                            align-items: center;
                            height: 100vh;
                            margin: 0;
                        }
                        .container {
                            text-align: center;
                            border: 1px solid #5a1a1a;
                            padding: 40px;
                            background: #1a0000;
                            border-radius: 8px;
                        }
                        h1 { color: #ff8888; margin-bottom: 10px; font-size: 24px; }
                        p { color: #858080; font-size: 14px; }
                        .icon { font-size: 40px; margin-bottom: 20px; color: #ff8888; }
                    </style>
                </head>
                <body>
                    <div class="container">
                        <div class="icon">✗</div>
                        <h1>Auth Failed</h1>
                        <p>Could not authenticate. Please try again in the app.</p>
                    </div>
                </body>
                </html>
                """
                inner_self.wfile.write(html_error.encode('utf-8'))
        
        try:
            server = HTTPServer(('localhost', 8080), Handler)
            server.timeout = 60
            server.handle_request()
        except Exception as e: print("OAuth Server error:", e)

class RegistryLoader(QObject):
    loaded = pyqtSignal(list, str)
    def __init__(self):
        super().__init__()
        self.nam = QNetworkAccessManager()
    def load(self, url):
        reply = self.nam.get(QNetworkRequest(QUrl(url)))
        reply.finished.connect(lambda: self._on_reply(reply))
    def _on_reply(self, reply):
        if reply.error() == QNetworkReply.NetworkError.NoError:
            try:
                parsed = json.loads(bytes(reply.readAll()).decode("utf-8"))
                self.loaded.emit(parsed.get("mods", []), "")
            except Exception as e: self.loaded.emit([], str(e))
        else: self.loaded.emit([], reply.errorString())
        reply.deleteLater()

class ImageDownloader(QThread):
    finished = pyqtSignal(str, bytes)
    def __init__(self, url, tag):
        super().__init__()
        self.url = url
        self.tag = tag
    def run(self):
        try:
            res = requests.get(self.url, timeout=10)
            if res.status_code == 200: self.finished.emit(self.tag, res.content)
        except: pass

# ==========================================
# 3. ДИЗАЙН
# ==========================================
class OptimizedFluidBackground(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)
        self.cell_size = 16
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(50)
        self.cols = 0
        self.rows = 0
        self.current = []
        self.previous = []

    def init_grid(self):
        if self.width() > 0 and self.height() > 0:
            self.cols = self.width() // self.cell_size
            self.rows = self.height() // self.cell_size
            self.current = [[0.0 for _ in range(self.cols)] for _ in range(self.rows)]
            self.previous = [[0.0 for _ in range(self.cols)] for _ in range(self.rows)]

    def resizeEvent(self, event):
        self.init_grid()
        super().resizeEvent(event)

    def tick(self):
        if not self.current: return
        for y in range(self.rows):
            for x in range(self.cols):
                dist = math.hypot(x - self.cols/2, y - self.rows/2)
                val = math.sin(dist * 0.1 - time.time() * 1.5) * math.exp(-dist * 0.03)
                self.current[y][x] = val
        self.previous, self.current = self.current, self.previous
        self.update()

    def paintEvent(self, event):
        if not self.previous: return
        painter = QPainter(self)
        painter.fillRect(self.rect(), Qt.GlobalColor.black)
        for y in range(self.rows):
            for x in range(self.cols):
                val = self.previous[y][x]
                intensity = (val + 1) / 2 
                brightness = int(intensity * 25) 
                if brightness > 5:
                    color = QColor(brightness, brightness, brightness)
                    rect = QRectF(x * self.cell_size, y * self.cell_size, self.cell_size - 1, self.cell_size - 1)
                    painter.fillRect(rect, color)

class AsciiLogo(QLabel):
    def __init__(self):
        super().__init__()
        self.setStyleSheet("color: #FFFFFF; background: transparent; font-family: 'Consolas', monospace; font-size: 11px; font-weight: bold; letter-spacing: 1px;")
        self.setText("""
 ██╗    ██╗ ██████╗ ██████╗ ██╗  ██╗███╗   ███╗ ██████╗ ██████╗ ███████╗
 ██║    ██║██╔═══██╗██╔══██╗██║ ██╔╝████╗ ████║██╔═══██╗██╔══██╗██╔════╝
 ██║ █╗ ██║██║   ██║██████╔╝█████╔╝ ██╔████╔██║██║   ██║██║  ██║███████╗
 ██║███╗██║██║   ██║██╔══██╗██╔═██╗ ██║╚██╔╝██║██║   ██║██║  ██║╚════██║
 ╚███╔███╔╝╚██████╔╝██║  ██║██║  ██╗██║ ╚═╝ ██║╚██████╔╝██████╔╝███████║
  ╚══╝╚══╝  ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝     ╚═╝ ╚═════╝ ╚═════╝ ╚══════╝
        """)

# ==========================================
# 4. ДИАЛОГ ЗАГРУЗКИ
# ==========================================
class UploadDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Processing")
        self.resize(400, 150)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowCloseButtonHint)
        
        layout = QVBoxLayout(self)
        self.status_label = QLabel("Preparing...")
        self.status_label.setStyleSheet("color: #c9c5c7; font-weight: bold;")
        
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        
        layout.addWidget(self.status_label)
        layout.addWidget(self.progress)
        layout.addStretch()

    def set_status(self, text, val=None):
        self.status_label.setText(text)
        if val is not None:
            self.progress.setValue(val)

# ==========================================
# 5. ВКЛАДКИ
# ==========================================
class CatalogTab(QWidget):
    download_requested = pyqtSignal(dict)
    def __init__(self, config, loc):
        super().__init__()
        self.config = config
        self.loc = loc
        self.image_downloader_banner = None
        self.image_downloader_icon = None
        self._build_ui()
        self.loader = RegistryLoader()
        self.loader.loaded.connect(self._on_loaded)
        
    def _build_ui(self):
        layout = QVBoxLayout(self)
        
        top_layout = QHBoxLayout()
        self.search = QLineEdit(); self.search.setPlaceholderText("SEARCH MODS...")
        self.btn_refresh = QPushButton(get_icon("refresh"), "")
        self.btn_refresh.setFixedWidth(40)
        self.btn_refresh.setToolTip("Refresh Catalog")
        self.btn_refresh.clicked.connect(self.load_registry)
        top_layout.addWidget(self.search)
        top_layout.addWidget(self.btn_refresh)
        layout.addLayout(top_layout)
        
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        self.list = QListWidget()
        self.list.currentItemChanged.connect(self._on_select)
        splitter.addWidget(self.list)
        
        self.detail_frame = QFrame()
        self.detail_frame.setObjectName("detailPanel")
        detail_layout = QVBoxLayout(self.detail_frame)
        
        self.banner_label = QLabel()
        self.banner_label.setFixedHeight(140)
        self.banner_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.banner_label.setStyleSheet("background: #0a0a0b; border: 1px solid #333; color: #444;")
        self.banner_label.setText("NO BANNER")
        
        info_layout = QHBoxLayout()
        self.icon_label = QLabel()
        self.icon_label.setFixedSize(64, 64)
        self.icon_label.setStyleSheet("background: #0a0a0b; border: 1px solid #333;")
        
        title_layout = QVBoxLayout()
        self.title_label = QLabel("SELECT A MOD")
        self.title_label.setStyleSheet("font-size: 20px; font-weight: bold; color: #FFFFFF;")
        self.author_label = QLabel("")
        self.author_label.setStyleSheet("font-size: 12px; color: #888;")
        title_layout.addWidget(self.title_label)
        title_layout.addWidget(self.author_label)
        
        info_layout.addWidget(self.icon_label)
        info_layout.addLayout(title_layout)
        info_layout.addStretch()
        
        self.desc_label = QTextEdit()
        self.desc_label.setReadOnly(True)
        self.desc_label.setStyleSheet("background: transparent; border: none; color: #ccc;")
        
        self.btn_install = QPushButton("INSTALL")
        self.btn_install.setObjectName("primary")
        self.btn_install.setFixedHeight(40)
        self.btn_install.clicked.connect(self._install)
        
        self.btn_folder = QPushButton(get_icon("folder"), "OPEN FOLDER")
        self.btn_folder.clicked.connect(self._open_folder)
        self.btn_folder.setEnabled(False)
        self.btn_folder.hide()

        detail_layout.addWidget(self.banner_label)
        detail_layout.addLayout(info_layout)
        detail_layout.addWidget(self.desc_label, 1)
        
        btn_box = QHBoxLayout()
        btn_box.addWidget(self.btn_install)
        btn_box.addWidget(self.btn_folder)
        detail_layout.addLayout(btn_box)
        
        splitter.addWidget(self.detail_frame)
        splitter.setSizes([350, 500])
        layout.addWidget(splitter, 1)
        
    def load_registry(self):
        url = self.config.get("registry_url")
        if url: 
            self.btn_refresh.setEnabled(False)
            self.loader.load(url)
        
    def _on_loaded(self, mods, err):
        self.btn_refresh.setEnabled(True)
        if err: return
        with QSignalBlocker(self.list):
            self.list.clear()
            for m in mods:
                item = QListWidgetItem(m.get("name", "Unknown").upper())
                item.setData(Qt.ItemDataRole.UserRole, m)
                self.list.addItem(item)
            
    def _on_select(self, current, prev):
        if not current:
            self.title_label.setText("SELECT A MOD")
            self.author_label.setText("")
            self.desc_label.clear()
            self.banner_label.setText("NO BANNER")
            self.banner_label.setPixmap(QPixmap())
            self.icon_label.setPixmap(QPixmap())
            self.btn_install.setEnabled(False)
            self.btn_folder.setEnabled(False)
            return
            
        mod = current.data(Qt.ItemDataRole.UserRole)
        self.title_label.setText(mod.get("name", "Unknown"))
        self.author_label.setText(f"by {mod.get('author', 'Unknown')} • v{mod.get('version', '?')}")
        self.desc_label.setPlainText(mod.get("description", "No description."))
        self.btn_install.setEnabled(True)
        
        installed = is_mod_installed(self.config, mod.get("id", ""))
        self.btn_folder.setVisible(installed)
        self.btn_folder.setEnabled(installed)
        
        if installed:
            self.btn_install.setText("REINSTALL / UPDATE")
            self.btn_install.setObjectName("")
        else:
            self.btn_install.setText("INSTALL")
            self.btn_install.setObjectName("primary")
        self.btn_install.setStyleSheet(self.btn_install.styleSheet())
        
        self.banner_label.setText("LOADING...")
        self.banner_label.setPixmap(QPixmap())
        self.icon_label.setPixmap(QPixmap())
        
        if mod.get("banner_url"):
            self.image_downloader_banner = ImageDownloader(mod["banner_url"], "banner")
            self.image_downloader_banner.finished.connect(self._set_banner)
            self.image_downloader_banner.start()
        else:
            self.banner_label.setText("NO BANNER")
            
        if mod.get("icon_url"):
            self.image_downloader_icon = ImageDownloader(mod["icon_url"], "icon")
            self.image_downloader_icon.finished.connect(self._set_icon)
            self.image_downloader_icon.start()

    def _set_banner(self, tag, data):
        pixmap = QPixmap()
        pixmap.loadFromData(data)
        self.banner_label.setPixmap(pixmap.scaled(500, 140, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))

    def _set_icon(self, tag, data):
        pixmap = QPixmap()
        pixmap.loadFromData(data)
        self.icon_label.setPixmap(pixmap.scaled(64, 64, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))

    def _install(self):
        item = self.list.currentItem()
        if item: self.download_requested.emit(item.data(Qt.ItemDataRole.UserRole))

    def _open_folder(self):
        item = self.list.currentItem()
        if not item: return
        mod = item.data(Qt.ItemDataRole.UserRole)
        path = Path(self.config["install_dir"]) / mod.get("id", "")
        if path.exists(): open_folder(str(path))

class InstalledTab(QWidget):
    def __init__(self, config, loc):
        super().__init__()
        self.config = config
        self.loc = loc
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        top = QHBoxLayout()
        btn_refresh = QPushButton(get_icon("refresh"), "REFRESH")
        btn_refresh.clicked.connect(self.scan)
        top.addWidget(btn_refresh)
        top.addStretch()
        layout.addLayout(top)
        
        layout.addWidget(QLabel("INSTALLED MODS"))
        self.list = QListWidget()
        layout.addWidget(self.list, 1)
        
        btn_layout = QHBoxLayout()
        btn_del = QPushButton(get_icon("trash"), "DELETE SELECTED")
        btn_del.setObjectName("danger")
        btn_del.clicked.connect(self._delete)
        
        self.btn_folder = QPushButton(get_icon("folder"), "")
        self.btn_folder.setToolTip("Open Mod Folder")
        self.btn_folder.clicked.connect(self._open_folder)
        self.btn_folder.setFixedWidth(40)
        
        btn_layout.addWidget(btn_del)
        btn_layout.addWidget(self.btn_folder)
        layout.addLayout(btn_layout)
        self.scan()

    def scan(self):
        with QSignalBlocker(self.list):
            self.list.clear()
            d = Path(self.config["install_dir"])
            if d.exists():
                for entry in d.iterdir():
                    if entry.is_dir() and not entry.name.startswith("."):
                        meta = read_mod_meta(self.config, entry.name)
                        status = ""
                        item = QListWidgetItem(f"{meta.get('name', entry.name).upper()} (v{meta.get('version', '?')}) {status}")
                        item.setData(Qt.ItemDataRole.UserRole, entry.name)
                        self.list.addItem(item)

    def _delete(self):
        item = self.list.currentItem()
        if not item: return
        mod_id = item.data(Qt.ItemDataRole.UserRole)
        ans = QMessageBox.question(self, "Delete", f"Delete '{mod_id}'?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if ans == QMessageBox.StandardButton.Yes:
            target = Path(self.config["install_dir"]) / mod_id
            if target.exists(): shutil.rmtree(target)
            self.scan()

    def _open_folder(self):
        item = self.list.currentItem()
        if not item: return
        mod_id = item.data(Qt.ItemDataRole.UserRole)
        path = Path(self.config["install_dir"]) / mod_id
        if path.exists(): open_folder(str(path))

class ModEditorDialog(QDialog):
    def __init__(self, config, parent=None, mod_data=None, repos=None, is_published=False):
        super().__init__(parent)
        self.config = config
        self.mod_data = mod_data or {}
        self.repos = repos or []
        self.is_published = is_published
        self.setWindowTitle("Mod Editor")
        self.resize(500, 750)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        
        if not self.mod_data.get("id"):
            self.mod_data["id"] = str(uuid.uuid4())[:8]

        self.id_input = QLineEdit(self.mod_data.get("id", ""))
        self.id_input.setDisabled(True)
        
        self.repo_combo = QComboBox()
        self.repo_combo.addItem("Local Only (No Repo)")
        for r in self.repos:
            self.repo_combo.addItem(r["full_name"])
        if self.mod_data.get("repo"):
            idx = self.repo_combo.findText(self.mod_data["repo"])
            if idx >= 0: self.repo_combo.setCurrentIndex(idx)
        
        self.name_input = QLineEdit(self.mod_data.get("name", ""))
        self.desc_input = QTextEdit()
        self.desc_input.setPlainText(self.mod_data.get("description", ""))
        self.version_input = QLineEdit(self.mod_data.get("version", "1.0.0"))
        
        self.icon_path = self.mod_data.get("icon_path", "")
        self.banner_path = self.mod_data.get("banner_path", "")
        self.mod_files_dir = self.mod_data.get("mod_files_dir", "")
        
        self.icon_preview = QLabel("No Icon")
        self.icon_preview.setFixedSize(64, 64)
        self.icon_preview.setStyleSheet("border: 1px solid #333;")
        if self.icon_path and os.path.exists(self.icon_path):
            self.icon_preview.setPixmap(QPixmap(self.icon_path).scaled(64, 64, Qt.AspectRatioMode.KeepAspectRatio))
            
        self.banner_preview = QLabel("No Banner")
        self.banner_preview.setFixedSize(300, 100)
        self.banner_preview.setStyleSheet("border: 1px solid #333;")
        if self.banner_path and os.path.exists(self.banner_path):
            self.banner_preview.setPixmap(QPixmap(self.banner_path).scaled(300, 100, Qt.AspectRatioMode.KeepAspectRatio))
        
        self.btn_icon = QPushButton("SELECT ICON")
        self.btn_icon.clicked.connect(lambda: self._pick_file("icon"))
        if self.icon_path: self.btn_icon.setText(f"ICON: {Path(self.icon_path).name}")
        
        self.btn_banner = QPushButton("SELECT BANNER")
        self.btn_banner.clicked.connect(lambda: self._pick_file("banner"))
        if self.banner_path: self.btn_banner.setText(f"BANNER: {Path(self.banner_path).name}")
        
        self.btn_files = QPushButton("SELECT MOD FILES FOLDER")
        self.btn_files.clicked.connect(self._pick_files_folder)
        if self.mod_files_dir: self.btn_files.setText(f"FILES: {Path(self.mod_files_dir).name}")
        
        save_btn = QPushButton("SAVE MOD")
        save_btn.setObjectName("primary")
        save_btn.clicked.connect(self.save_mod)
        
        self.btn_publish = QPushButton("UPDATE ON GITHUB" if self.is_published else "PUBLISH & REQUEST ADDITION")
        self.btn_publish.setObjectName("danger")
        self.btn_publish.clicked.connect(self.publish_mod)
        self.btn_publish.setEnabled(bool(self.mod_data.get("repo")))
        
        self.btn_unpublish = QPushButton("UNPUBLISH (REMOVE FROM REGISTRY)")
        self.btn_unpublish.setObjectName("danger")
        self.btn_unpublish.clicked.connect(self.unpublish_mod)
        self.btn_unpublish.setVisible(self.is_published)

        form = QFormLayout()
        form.addRow("GitHub Repository:", self.repo_combo)
        form.addRow("Mod ID (Auto):", self.id_input)
        form.addRow("Mod Name:", self.name_input)
        form.addRow("Description:", self.desc_input)
        form.addRow("Version:", self.version_input)
        form.addRow("Icon:", self.btn_icon)
        form.addRow("Preview:", self.icon_preview)
        form.addRow("Banner:", self.btn_banner)
        form.addRow("Preview:", self.banner_preview)
        form.addRow("Files Folder:", self.btn_files)
        
        layout.addLayout(form)
        layout.addWidget(save_btn)
        layout.addWidget(self.btn_publish)
        layout.addWidget(self.btn_unpublish)

    def _pick_file(self, type_):
        f, _ = QFileDialog.getOpenFileName(self, f"Select {type_}", "", "Images (*.png *.jpg *.ico)")
        if f:
            if type_ == "icon":
                self.icon_path = f
                self.icon_preview.setPixmap(QPixmap(f).scaled(64, 64, Qt.AspectRatioMode.KeepAspectRatio))
                self.btn_icon.setText(f"ICON: {Path(f).name}")
            else:
                self.banner_path = f
                self.banner_preview.setPixmap(QPixmap(f).scaled(300, 100, Qt.AspectRatioMode.KeepAspectRatio))
                self.btn_banner.setText(f"BANNER: {Path(f).name}")

    def _pick_files_folder(self):
        d = QFileDialog.getExistingDirectory(self, "Select Folder with Mod Files")
        if d:
            self.mod_files_dir = d
            self.btn_files.setText(f"FILES: {Path(d).name}")

    def save_mod(self):
        try:
            mod_id = self.id_input.text().strip()
            if not mod_id or not self.name_input.text().strip():
                QMessageBox.warning(self, "Error", "Mod Name is required.")
                return
                
            target = Path(self.config["install_dir"]) / mod_id
            target.mkdir(parents=True, exist_ok=True)
            
            repo_selected = self.repo_combo.currentText()
            if repo_selected == "Local Only (No Repo)": repo_selected = ""
            
            meta = {
                "id": mod_id, 
                "repo": repo_selected,
                "name": self.name_input.text().strip(),
                "description": self.desc_input.toPlainText().strip(),
                "version": self.version_input.text().strip(),
                "icon_path": "icon.png" if self.icon_path else "",
                "banner_path": "banner.png" if self.banner_path else "",
                "mod_files_dir": self.mod_files_dir,
                "installed_at": datetime.now().isoformat(), 
                "author": "Local"
            }
            
            if self.icon_path and os.path.exists(self.icon_path):
                src_icon = Path(self.icon_path).resolve()
                dst_icon = (target / "icon.png").resolve()
                if src_icon != dst_icon: shutil.copy(src_icon, dst_icon)
                    
            if self.banner_path and os.path.exists(self.banner_path):
                src_banner = Path(self.banner_path).resolve()
                dst_banner = (target / "banner.png").resolve()
                if src_banner != dst_banner: shutil.copy(src_banner, dst_banner)

            with open(target / ".devers_meta.json", "w", encoding="utf-8") as f:
                json.dump(meta, f, indent=2, ensure_ascii=False)
                
            self.btn_publish.setEnabled(bool(repo_selected))
            QMessageBox.information(self, "Saved", "Mod saved successfully.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save mod:\n{e}")

    def publish_mod(self):
        token = self.config.get("github_token")
        repo = self.repo_combo.currentText()
        if not token or not repo or repo == "Local Only (No Repo)":
            QMessageBox.warning(self, "Error", "No repository selected or not logged in.")
            return
            
        mod_id = self.id_input.text().strip()
        mod_name = self.name_input.text().strip()
        version = self.version_input.text().strip()
        files_dir = self.mod_files_dir
        
        if not files_dir or not os.path.exists(files_dir):
            QMessageBox.warning(self, "Error", "Please select a folder with mod files first.")
            return

        self.upload_dialog = UploadDialog(self)
        
        def upload_task():
            try:
                self.upload_dialog.set_status("Packing ZIP...", 10)
                zip_path = Path(self.config["install_dir"]) / f"{mod_id}.zip"
                with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as z:
                    for root, _, files in os.walk(files_dir):
                        for file in files:
                            file_path = Path(root) / file
                            z.write(file_path, file_path.relative_to(files_dir))
                            
                self.upload_dialog.set_status("Calculating SHA-256...", 20)
                sha256 = get_sha256(zip_path)
                
                self.upload_dialog.set_status("Uploading files to Repository...", 30)
                headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
                for root, _, files in os.walk(files_dir):
                    for file in files:
                        file_path = Path(root) / file
                        rel_path = file_path.relative_to(files_dir).as_posix()
                        file_url = f"https://api.github.com/repos/{repo}/contents/{rel_path}"
                        get_res = requests.get(file_url, headers=headers)
                        file_sha = get_res.json().get("sha") if get_res.status_code == 200 else None
                        with open(file_path, "rb") as f_img:
                            b64_content = base64.b64encode(f_img.read()).decode("utf-8")
                        data = {"message": f"Update {rel_path}", "content": b64_content}
                        if file_sha: data["sha"] = file_sha
                        requests.put(file_url, headers=headers, json=data)

                self.upload_dialog.set_status("Creating Release...", 50)
                release_url = f"https://api.github.com/repos/{repo}/releases"
                release_data = {"tag_name": f"v{version}", "name": f"v{version}", "body": "Automated upload from Workmods"}
                res = requests.post(release_url, headers=headers, json=release_data)
                
                if res.status_code not in (201, 422):
                    raise Exception(f"Failed to create release: {res.text}")
                    
                if res.status_code == 201:
                    upload_url = res.json()["upload_url"].split("{")[0]
                else:
                    r_get = requests.get(f"{release_url}/tags/v{version}", headers=headers)
                    upload_url = r_get.json()["upload_url"].split("{")[0]
                
                self.upload_dialog.set_status("Uploading ZIP to Release...", 70)
                with open(zip_path, 'rb') as f:
                    headers["Content-Type"] = "application/zip"
                    res_upload = requests.post(f"{upload_url}?name={mod_id}.zip", headers=headers, data=f)
                    if res_upload.status_code != 201:
                        raise Exception(f"Failed to upload ZIP: {res_upload.text}")

                self.upload_dialog.set_status("Sending to Registry...", 90)
                payload = {
                    "event_type": "add_mod",
                    "client_payload": {
                        "secret": BOT_SECRET,
                        "id": mod_id,
                        "name": mod_name,
                        "version": version,
                        "repo": repo,
                        "sha256": sha256,
                        "download_url": f"https://github.com/{repo}/releases/download/v{version}/{mod_id}.zip",
                        "icon_url": f"https://raw.githubusercontent.com/{repo}/main/icon.png" if self.icon_path else "",
                        "banner_url": f"https://raw.githubusercontent.com/{repo}/main/banner.png" if self.banner_path else ""
                    }
                }
                res_webhook = requests.post(f"https://api.github.com/repos/{REGISTRY_REPO}/dispatches", headers=headers, json=payload)
                
                if res_webhook.status_code != 204:
                    raise Exception(f"Registry rejected: {res_webhook.text}")

                self.upload_dialog.set_status("Success!", 100)
                time.sleep(1.5)
                
                QTimer.singleShot(0, self.upload_dialog.accept)
                QTimer.singleShot(100, lambda: QMessageBox.information(self, "Success", "Mod published to repository, release created, and sent to registry!"))
                
            except Exception as e:
                QTimer.singleShot(0, self.upload_dialog.accept)
                QTimer.singleShot(100, lambda: QMessageBox.critical(self, "Error", f"Failed to publish:\n{e}"))

        threading.Thread(target=upload_task, daemon=True).start()
        self.upload_dialog.exec()

    def unpublish_mod(self):
        token = self.config.get("github_token")
        if not token: return
        
        ans = QMessageBox.question(self, "Unpublish", "Remove this mod from the registry? (The GitHub repository and files will remain).", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if ans != QMessageBox.StandardButton.Yes: return
        
        mod_id = self.id_input.text().strip()
        
        try:
            headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
            payload = {
                "event_type": "remove_mod",
                "client_payload": {
                    "secret": BOT_SECRET,
                    "id": mod_id
                }
            }
            res = requests.post(f"https://api.github.com/repos/{REGISTRY_REPO}/dispatches", headers=headers, json=payload)
            
            if res.status_code == 204:
                QMessageBox.information(self, "Success", "Mod successfully removed from registry.")
                self.is_published = False
                self.btn_publish.setText("PUBLISH & REQUEST ADDITION")
                self.btn_unpublish.setVisible(False)
            else:
                QMessageBox.critical(self, "Error", f"Failed to remove: {res.text}")
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

class AuthorStudioTab(QWidget):
    def __init__(self, config, loc):
        super().__init__()
        self.config = config
        self.loc = loc
        self.user_data = None
        self.user_repos = []
        self.registry_mods = set()
        self.fetcher = None
        self.repo_fetcher = None
        self.registry_loader = RegistryLoader()
        self.registry_loader.loaded.connect(self._on_registry_for_pub)
        self.registry_loader.load(self.config.get("registry_url"))
        
        self.editing_mod_id = None
        self._build_ui()
        self.refresh_data()
        
    def _on_registry_for_pub(self, mods, err):
        if not err:
            self.registry_mods = set(m["id"] for m in mods)
            self.refresh_data()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        
        auth_layout = QHBoxLayout()
        self.avatar_label = QLabel()
        self.avatar_label.setFixedSize(40, 40)
        self.avatar_label.setStyleSheet("border-radius: 20px; background: #333;")
        self.avatar_label.hide()
        
        self.auth_label = QLabel("Not Logged In")
        self.auth_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        
        self.btn_auth = QPushButton(get_icon("web"), "LOGIN VIA GITHUB")
        self.btn_auth.clicked.connect(self._login)
        self.btn_logout = QPushButton("LOGOUT")
        self.btn_logout.clicked.connect(self._logout)
        self.btn_logout.hide()
        
        auth_layout.addWidget(self.avatar_label)
        auth_layout.addWidget(self.auth_label)
        auth_layout.addStretch()
        auth_layout.addWidget(self.btn_auth)
        auth_layout.addWidget(self.btn_logout)
        layout.addLayout(auth_layout)
        
        layout.addWidget(QLabel("MY MODS"))
        self.mod_list = QListWidget()
        layout.addWidget(self.mod_list, 1)
        
        btn_layout = QHBoxLayout()
        
        self.btn_new_repo = QPushButton(get_icon("web"), "NEW REPO")
        self.btn_new_repo.setToolTip("Create a new repository on GitHub")
        self.btn_new_repo.clicked.connect(self._create_repo)
        
        self.btn_create = QPushButton(get_icon("edit"), "CREATE")
        self.btn_create.clicked.connect(self._create_mod)
        
        self.btn_edit = QPushButton(get_icon("edit"), "EDIT")
        self.btn_edit.clicked.connect(self._edit_mod)
        
        self.btn_folder = QPushButton(get_icon("folder"), "")
        self.btn_folder.setToolTip("Open Mod Folder")
        self.btn_folder.clicked.connect(self._open_folder)
        self.btn_folder.setFixedWidth(40)
        
        self.btn_delete = QPushButton(get_icon("trash"), "DELETE")
        self.btn_delete.setObjectName("danger")
        self.btn_delete.clicked.connect(self._delete_mod)
        
        btn_layout.addWidget(self.btn_new_repo)
        btn_layout.addWidget(self.btn_create)
        btn_layout.addWidget(self.btn_edit)
        btn_layout.addWidget(self.btn_folder)
        btn_layout.addWidget(self.btn_delete)
        layout.addLayout(btn_layout)

    def refresh_data(self):
        if self.editing_mod_id: return
        
        d = Path(self.config["install_dir"])
        current_ids = []
        if d.exists():
            for entry in d.iterdir():
                if entry.is_dir() and not entry.name.startswith("."):
                    current_ids.append(entry.name)
                    
        with QSignalBlocker(self.mod_list):
            if self.mod_list.count() != len(current_ids):
                self.mod_list.clear()
                for mid in sorted(current_ids):
                    meta = read_mod_meta(self.config, mid)
                    status = "[PUB]" if mid in self.registry_mods else "[LOCAL]"
                    item = QListWidgetItem(f"{status} {meta.get('name', mid).upper()}")
                    item.setData(Qt.ItemDataRole.UserRole, mid)
                    self.mod_list.addItem(item)
                    
        token = self.config.get("github_token")
        if token and not self.user_data and not self.fetcher:
            self._start_fetch(token)
        elif not token:
            self.btn_auth.show()
            self.btn_logout.hide()
            self.avatar_label.hide()
            self.btn_new_repo.setEnabled(False)
            self.btn_create.setEnabled(False)
            self.btn_edit.setEnabled(False)
            self.auth_label.setText("Not Logged In (Read Only)")

    def _start_fetch(self, token):
        self.fetcher = GitHubFetcher(token)
        self.fetcher.finished.connect(self._on_user_fetched)
        self.fetcher.start()
        
        self.repo_fetcher = GitHubRepoFetcher(token)
        self.repo_fetcher.finished.connect(self._on_repos_fetched)
        self.repo_fetcher.start()

    def _on_user_fetched(self, data, err):
        self.fetcher = None
        if data:
            self.user_data = data
            self.auth_label.setText(f"Logged in as: {self.user_data['login']}")
            self.btn_auth.hide()
            self.btn_logout.show()
            self.btn_new_repo.setEnabled(True)
            self.btn_create.setEnabled(True)
            self.btn_edit.setEnabled(True)
            
            avatar_url = self.user_data.get("avatar_url")
            if avatar_url:
                self.avatar_dl = ImageDownloader(avatar_url, "avatar")
                self.avatar_dl.finished.connect(self._set_avatar)
                self.avatar_dl.start()
        else:
            self.auth_label.setText(f"Error: {err}")
            self._logout(silent=True)

    def _set_avatar(self, tag, data):
        pixmap = QPixmap()
        pixmap.loadFromData(data)
        self.avatar_label.setPixmap(pixmap.scaled(40, 40, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        self.avatar_label.show()
            
    def _on_repos_fetched(self, repos, err):
        self.repo_fetcher = None
        if repos: self.user_repos = repos

    def _login(self):
        self.btn_auth.setText("WAITING FOR BROWSER...")
        self.btn_auth.setEnabled(False)
        
        self.oauth_thread = OAuthServerThread()
        self.oauth_thread.auth_success.connect(self._on_auth_success)
        self.oauth_thread.start()
        
        webbrowser.open(f"https://github.com/login/oauth/authorize?client_id={GITHUB_CLIENT_ID}&scope=repo")

    def _on_auth_success(self, token):
        cfg = load_config()
        cfg["github_token"] = token
        save_config(cfg)
        self.config["github_token"] = token
        self.btn_auth.setText("LOGIN VIA GITHUB")
        self.btn_auth.setEnabled(True)
        self._start_fetch(token)

    def _logout(self, silent=False):
        cfg = load_config()
        cfg["github_token"] = ""
        save_config(cfg)
        self.config["github_token"] = ""
        self.user_data = None
        self.user_repos = []
        self.btn_auth.show()
        self.btn_logout.hide()
        self.avatar_label.hide()
        self.btn_new_repo.setEnabled(False)
        self.btn_create.setEnabled(False)
        self.btn_edit.setEnabled(False)
        self.auth_label.setText("Not Logged In (Read Only)")
        if not silent:
            QMessageBox.information(self, "Logout", "Logged out successfully.")
            
    def _create_repo(self):
        token = self.config.get("github_token")
        if not token: return
        
        name, ok = QInputDialog.getText(self, "New Repository", "Repository Name:")
        if not ok or not name.strip(): return
        
        try:
            headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
            res = requests.post("https://api.github.com/user/repos", 
                                json={"name": name.strip(), "private": False, "auto_init": True}, 
                                headers=headers)
            if res.status_code == 201:
                QMessageBox.information(self, "Success", "Repository created successfully!")
                self._start_fetch(token)
            else:
                QMessageBox.critical(self, "Error", res.text)
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def _create_mod(self):
        self.editing_mod_id = "NEW"
        dialog = ModEditorDialog(self.config, self, repos=self.user_repos)
        dialog.exec()
        self.editing_mod_id = None
        self.refresh_data()

    def _edit_mod(self):
        item = self.mod_list.currentItem()
        if not item: return
        self.editing_mod_id = item.data(Qt.ItemDataRole.UserRole)
        mod_id = self.editing_mod_id
        
        meta = read_mod_meta(self.config, mod_id)
        target = Path(self.config["install_dir"]) / mod_id
        
        if (target / "icon.png").exists(): meta["icon_path"] = str(target / "icon.png")
        if (target / "banner.png").exists(): meta["banner_path"] = str(target / "banner.png")
        
        is_pub = mod_id in self.registry_mods
        dialog = ModEditorDialog(self.config, self, meta, repos=self.user_repos, is_published=is_pub)
        dialog.exec()
        self.editing_mod_id = None
        self.refresh_data()

    def _open_folder(self):
        item = self.mod_list.currentItem()
        if not item: return
        mod_id = item.data(Qt.ItemDataRole.UserRole)
        path = Path(self.config["install_dir"]) / mod_id
        if path.exists(): open_folder(str(path))

    def _delete_mod(self):
        item = self.mod_list.currentItem()
        if not item: return
        mod_id = item.data(Qt.ItemDataRole.UserRole)
        ans = QMessageBox.question(self, "Delete", f"Delete '{mod_id}' locally?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if ans == QMessageBox.StandardButton.Yes:
            target = Path(self.config["install_dir"]) / mod_id
            if target.exists(): shutil.rmtree(target)
            self.refresh_data()

class SettingsTab(QWidget):
    def __init__(self, config, loc):
        super().__init__()
        self.config = config
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        
        self.lang = QComboBox()
        langs = get_available_languages()
        self.lang.addItems(langs)
        self.lang.setCurrentText(self.config.get("language", "en"))
        self.lang.currentTextChanged.connect(self.save)
        
        layout.addWidget(QLabel("LANGUAGE")); layout.addWidget(self.lang)
        layout.addStretch()
        
    def save(self):
        self.config["language"] = self.lang.currentText()
        save_config(self.config)

# ==========================================
# 6. ГЛАВНОЕ ОКНО
# ==========================================
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.config = load_config()
        self.loc = Localization(self.config.get("language", "en"))
        
        icon_path = DATA_DIR / "icon" / "app.ico"
        if icon_path.exists(): self.setWindowIcon(QIcon(str(icon_path)))
            
        self.setWindowTitle(APP_NAME)
        self.resize(1050, 750)
        
        self.bg = OptimizedFluidBackground(self)
        self.bg.setGeometry(0, 0, 1050, 750)
        self.bg.lower()
        
        central = QWidget()
        central.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        
        header = QHBoxLayout()
        logo = AsciiLogo()
        header.addWidget(logo)
        header.addStretch()
        layout.addLayout(header)
        
        self.tabs = QTabWidget()
        
        self.tab_catalog = CatalogTab(self.config, self.loc)
        self.tab_installed = InstalledTab(self.config, self.loc)
        self.tab_author = AuthorStudioTab(self.config, self.loc)
        self.tab_settings = SettingsTab(self.config, self.loc)
        
        self.tabs.addTab(self.tab_catalog, get_icon("library"), "CATALOG")
        self.tabs.addTab(self.tab_installed, get_icon("folder"), "INSTALLED")
        self.tabs.addTab(self.tab_author, get_icon("edit"), "AUTHOR STUDIO")
        self.tabs.addTab(self.tab_settings, get_icon("settings"), "SETTINGS")
        
        layout.addWidget(self.tabs)
        
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.tab_author.refresh_data)
        self.refresh_timer.start(3000)
        
        QTimer.singleShot(100, self.tab_catalog.load_registry)
        
    def resizeEvent(self, event):
        self.bg.resize(self.size())
        super().resizeEvent(event)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    app.setStyleSheet("""
        QWidget { background: transparent; color: #c9c5c7; font-family: 'Consolas', monospace; font-size: 13px; }
        QMainWindow { background: #0a0a0b; }
        QTabWidget::pane { border: 1px solid #262326; background: #0e0d0f; }
        QTabBar::tab { background: #0a0a0b; border: 1px solid #262326; border-bottom: none; padding: 10px 20px; margin-right: 2px; color: #858080; }
        QTabBar::tab:selected { background: #0e0d0f; color: #fdfcfc; border-top: 2px solid #a78bfa; }
        QPushButton { background: #0e0d0f; border: 1px solid #3a3438; padding: 8px 16px; color: #c9c5c7; border-radius: 4px; }
        QPushButton:hover { border-color: #858080; color: #fdfcfc; background: #111013; }
        QPushButton#primary { background: rgba(167, 139, 250, .07); color: #c9b8ff; border: 1px solid #4a3b7a; }
        QPushButton#primary:hover { background: rgba(167, 139, 250, .13); border-color: #a78bfa; color: #fdfcfc; }
        QPushButton#danger { background: #1a0000; border: 1px solid #5a1a1a; color: #ff8888; }
        QPushButton#danger:hover { background: #5a1a1a; color: #fdfcfc; }
        QLineEdit, QTextEdit, QListWidget { background: #0a0a0b; border: 1px solid #262326; padding: 6px; color: #fdfcfc; border-radius: 4px; outline: none; }
        QLineEdit:focus, QTextEdit:focus { border: 1px solid #a78bfa; }
        QListWidget::item { padding: 10px; border-bottom: 1px solid #1b191c; color: #c9c5c7; outline: none; }
        QListWidget::item:hover { background: #111013; }
        QListWidget::item:selected { background: rgba(167, 139, 250, .07); color: #c9b8ff; border-left: 3px solid #a78bfa; outline: none; }
        QScrollBar:vertical { background: #0a0a0b; width: 10px; margin: 0; }
        QScrollBar::handle:vertical { background: #2a2629; min-height: 20px; }
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        QProgressBar { background: #0a0a0b; border: 1px solid #262326; text-align: center; color: #fdfcfc; border-radius: 4px; }
        QProgressBar::chunk { background-color: #a78bfa; }
        QFrame#detailPanel { border: 1px solid #262326; background: #0e0d0f; border-radius: 4px; }
    """)
    
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
