import sys
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='hanime1_gui.log',
    filemode='a'
)

gui_logger = logging.getLogger('Hanime1GUI')

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, 
    QPushButton, QLineEdit, QListWidget, QLabel, QSplitter, 
    QGroupBox, QFormLayout, QTextEdit, QComboBox, QSpinBox, QRadioButton,
    QProgressBar, QMenu, QAction, QScrollArea, QCheckBox, QFrame, QMessageBox
)
from PyQt5.QtCore import Qt, QThread, QRunnable, QThreadPool, pyqtSignal, pyqtSlot, QObject
from PyQt5.QtGui import QPixmap, QImage
from PyQt5.QtNetwork import QNetworkAccessManager, QNetworkRequest

from hanime1_api import Hanime1API

class WorkerSignals(QObject):
    finished = pyqtSignal()
    error = pyqtSignal(str)
    result = pyqtSignal(object)
    progress = pyqtSignal(dict)

class SearchWorker(QRunnable):
    def __init__(self, api, query, genre="", sort="", date="", duration="", page=1):
        super().__init__()
        self.api = api
        self.query = query
        self.genre = genre
        self.sort = sort
        self.date = date
        self.duration = duration
        self.page = page
        self.signals = WorkerSignals()
    
    @pyqtSlot()
    def run(self):
        try:
            result = self.api.search_videos(
                query=self.query,
                genre=self.genre,
                sort=self.sort,
                date=self.date,
                duration=self.duration,
                page=self.page
            )
            self.signals.result.emit(result)
        except Exception as e:
            self.signals.error.emit(str(e))
        finally:
            self.signals.finished.emit()

class GetVideoInfoWorker(QRunnable):
    def __init__(self, api, video_id):
        super().__init__()
        self.api = api
        self.video_id = video_id
        self.signals = WorkerSignals()
    
    @pyqtSlot()
    def run(self):
        try:
            result = self.api.get_video_info(self.video_id)
            self.signals.result.emit(result)
        except Exception as e:
            self.signals.error.emit(str(e))
        finally:
            self.signals.finished.emit()

class DownloadWorker(QRunnable):
    def __init__(self, url, filename, save_path=".", num_threads=4, proxy_config=None):
        super().__init__()
        self.url = url
        self.filename = filename
        self.save_path = save_path
        self.num_threads = num_threads
        self.proxy_config = proxy_config
        self.signals = WorkerSignals()
        self.is_cancelled = False
        self.total_size = 0
        self.downloaded_size = 0
        self.chunk_size = 0
        self.can_use_range = True
        import threading
        self.threading = threading
    
    @pyqtSlot()
    def run(self):
        try:
            import os
            import requests
            
            os.makedirs(self.save_path, exist_ok=True)
            
            self.full_path = os.path.join(self.save_path, self.filename)
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            proxies = self.proxy_config if self.proxy_config else None
            
            response = requests.head(self.url, headers=headers, proxies=proxies, timeout=10)
            response.raise_for_status()
            
            content_length = response.headers.get('content-length')
            self.total_size = int(content_length) if content_length else 0
            
            accept_ranges = response.headers.get('accept-ranges', 'none')
            self.can_use_range = accept_ranges.lower() == 'bytes' and self.total_size > 0
            
            if self.can_use_range:
                self.chunk_size = self.total_size // self.num_threads
                
                if self.chunk_size < 1024 * 1024:
                    self.num_threads = 1
                    self.chunk_size = self.total_size
                
                self.temp_files = []
                for i in range(self.num_threads):
                    self.temp_files.append(f"{self.full_path}.part{i}")
                
                ranges = []
                for i in range(self.num_threads):
                    start = i * self.chunk_size
                    end = start + self.chunk_size - 1 if i < self.num_threads - 1 else self.total_size - 1
                    ranges.append((start, end))
                
                threads = []
                for i in range(self.num_threads):
                    t = self.threading.Thread(target=self.download_chunk, args=(i, ranges[i]))
                    threads.append(t)
                
                for t in threads:
                    t.start()
                
                for t in threads:
                    t.join()
                
                if self.is_cancelled:
                    self.cleanup_temp_files()
                    self.signals.error.emit("下载已取消")
                    return
                
                self.merge_chunks()
                
                self.cleanup_temp_files()
            else:
                self.download_single_thread()
                
                if self.is_cancelled:
                    if os.path.exists(self.full_path):
                        os.remove(self.full_path)
                    self.signals.error.emit("下载已取消")
                    return
            
            self.signals.finished.emit()
            
        except Exception as e:
            self.is_cancelled = True
            self.cleanup_temp_files()
            self.signals.error.emit(str(e))
    
    def download_chunk(self, index, range_tuple):
        import requests
        import os
        
        start, end = range_tuple
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Range': f'bytes={start}-{end}'
        }
        
        try:
            proxies = self.proxy_config if self.proxy_config else None
            response = requests.get(self.url, headers=headers, proxies=proxies, stream=True, timeout=30)
            response.raise_for_status()
            
            chunk_size = 8192
            chunk_downloaded = 0
            
            with open(self.temp_files[index], 'wb') as f:
                for chunk in response.iter_content(chunk_size=chunk_size):
                    if self.is_cancelled:
                        return
                    
                    if chunk:
                        f.write(chunk)
                        chunk_downloaded += len(chunk)
                        
                        with self.threading.Lock():
                            self.downloaded_size += len(chunk)
                            progress = (self.downloaded_size / self.total_size) * 100
                            
                            self.signals.progress.emit({"progress": progress, "filename": self.filename, "size": self.downloaded_size, "total_size": self.total_size})
        except Exception as e:
            self.is_cancelled = True
            self.signals.error.emit(str(e))
    
    def download_single_thread(self):
        import requests
        import os
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        try:
            proxies = self.proxy_config if self.proxy_config else None
            response = requests.get(self.url, headers=headers, proxies=proxies, stream=True, timeout=30)
            response.raise_for_status()
            
            content_length = response.headers.get('content-length')
            if content_length:
                self.total_size = int(content_length)
            
            chunk_size = 8192
            
            with open(self.full_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=chunk_size):
                    if self.is_cancelled:
                        return
                    
                    if chunk:
                        f.write(chunk)
                        self.downloaded_size += len(chunk)
                        
                        if self.total_size > 0:
                            progress = (self.downloaded_size / self.total_size) * 100
                        else:
                            progress = min(99.0, (self.downloaded_size / (1024 * 1024)) % 100)
                        
                        self.signals.progress.emit({"progress": progress, "filename": self.filename, "size": self.downloaded_size, "total_size": self.total_size})
        except Exception as e:
            self.is_cancelled = True
            self.signals.error.emit(str(e))
    
    def merge_chunks(self):
        import os
        
        try:
            with open(self.full_path, 'wb') as f:
                for temp_file in self.temp_files:
                    if os.path.exists(temp_file):
                        with open(temp_file, 'rb') as tf:
                            f.write(tf.read())
        except Exception as e:
            self.is_cancelled = True
            self.signals.error.emit(f"合并文件失败: {str(e)}")
    
    def cleanup_temp_files(self):
        import os
        
        if hasattr(self, 'temp_files'):
            for temp_file in self.temp_files:
                if os.path.exists(temp_file):
                    try:
                        os.remove(temp_file)
                    except:
                        pass
    
    def cancel(self):
        self.is_cancelled = True



class SettingsDialog(QDialog):
    def __init__(self, parent=None, settings=None):
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.setGeometry(100, 100, 400, 250)
        
        self.settings = settings or {
            'download_mode': 'multi_thread',
            'num_threads': 4,
            'download_quality': '最高',  # 新增：批量下载画质选择，默认最高
            'download_path': os.path.join(os.getcwd(), 'hamineDownload')  # 新增：下载位置，默认在当前文件夹下的hamineDownload目录
        }
        
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout()
        
        download_mode_group = QGroupBox("下载方式")
        download_mode_layout = QVBoxLayout()
        
        self.multi_thread_radio = QRadioButton("多线程下载")
        self.single_thread_radio = QRadioButton("单线程下载")
        
        if self.settings['download_mode'] == 'multi_thread':
            self.multi_thread_radio.setChecked(True)
        else:
            self.single_thread_radio.setChecked(True)
        
        download_mode_layout.addWidget(self.multi_thread_radio)
        download_mode_layout.addWidget(self.single_thread_radio)
        download_mode_group.setLayout(download_mode_layout)
        layout.addWidget(download_mode_group)
        
        threads_group = QGroupBox("线程数设置")
        threads_layout = QVBoxLayout()
        
        threads_layout.addWidget(QLabel("线程数量:"))
        self.threads_spinbox = QSpinBox()
        self.threads_spinbox.setMinimum(1)
        self.threads_spinbox.setMaximum(16)
        self.threads_spinbox.setValue(self.settings['num_threads'])
        threads_layout.addWidget(self.threads_spinbox)
        threads_group.setLayout(threads_layout)
        layout.addWidget(threads_group)
        
        # 新增：下载画质设置
        quality_group = QGroupBox("批量下载画质")
        quality_layout = QVBoxLayout()
        
        self.quality_high_radio = QRadioButton("最高")
        self.quality_low_radio = QRadioButton("最低")
        
        if self.settings.get('download_quality', '最高') == '最高':
            self.quality_high_radio.setChecked(True)
        else:
            self.quality_low_radio.setChecked(True)
        
        quality_layout.addWidget(self.quality_high_radio)
        quality_layout.addWidget(self.quality_low_radio)
        quality_group.setLayout(quality_layout)
        layout.addWidget(quality_group)
        
        self.multi_thread_radio.toggled.connect(self.on_download_mode_changed)
        self.single_thread_radio.toggled.connect(self.on_download_mode_changed)
        self.on_download_mode_changed()
        
        clear_logs_group = QGroupBox("日志管理")
        clear_logs_layout = QVBoxLayout()
        
        self.clear_logs_button = QPushButton("清除日志")
        self.clear_logs_button.clicked.connect(self.clear_logs)
        clear_logs_layout.addWidget(self.clear_logs_button)
        clear_logs_group.setLayout(clear_logs_layout)
        layout.addWidget(clear_logs_group)
        
        # 新增：下载位置设置
        download_path_group = QGroupBox("下载位置")
        download_path_layout = QVBoxLayout()
        
        path_layout = QHBoxLayout()
        path_layout.addWidget(QLabel("下载位置:"))
        self.download_path_edit = QLineEdit(self.settings.get('download_path', ''))
        path_layout.addWidget(self.download_path_edit, 1)
        
        self.browse_button = QPushButton("浏览...")
        self.browse_button.clicked.connect(self.browse_download_path)
        path_layout.addWidget(self.browse_button)
        
        download_path_layout.addLayout(path_layout)
        download_path_group.setLayout(download_path_layout)
        layout.addWidget(download_path_group)
        
        # 新增：缓存管理
        cache_group = QGroupBox("缓存管理")
        cache_layout = QVBoxLayout()
        
        self.clear_cache_button = QPushButton("清除缓存")
        self.clear_cache_button.clicked.connect(self.clear_cache)
        cache_layout.addWidget(self.clear_cache_button)
        cache_group.setLayout(cache_layout)
        layout.addWidget(cache_group)
        
        button_layout = QHBoxLayout()
        self.save_button = QPushButton("保存")
        self.save_button.clicked.connect(self.save_settings)
        self.cancel_button = QPushButton("取消")
        self.cancel_button.clicked.connect(self.reject)
        
        button_layout.addStretch()
        button_layout.addWidget(self.save_button)
        button_layout.addWidget(self.cancel_button)
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
    
    def on_download_mode_changed(self):
        self.threads_spinbox.setEnabled(self.multi_thread_radio.isChecked())
    
    def load_settings(self):
        try:
            import json
            import os
            if os.path.exists('settings.json'):
                with open('settings.json', 'r', encoding='utf-8') as f:
                    self.settings = json.load(f)
                gui_logger.info(f"成功加载设置: {self.settings}")
        except Exception as e:
            gui_logger.error(f"加载设置失败: {e}")
            self.settings = {
                'download_mode': 'multi_thread',
                'num_threads': 4
            }
    
    def browse_download_path(self):
        """
        浏览并选择下载位置
        """
        from PyQt5.QtWidgets import QFileDialog
        
        # 打开文件夹选择对话框
        folder = QFileDialog.getExistingDirectory(self, "选择下载位置", self.download_path_edit.text())
        if folder:
            self.download_path_edit.setText(folder)
    
    def save_settings(self):
        try:
            self.settings['download_mode'] = 'multi_thread' if self.multi_thread_radio.isChecked() else 'single_thread'
            self.settings['num_threads'] = self.threads_spinbox.value()
            self.settings['download_quality'] = '最高' if self.quality_high_radio.isChecked() else '最低'  # 保存画质设置
            self.settings['download_path'] = self.download_path_edit.text()  # 保存下载位置设置
            
            # 确保下载目录存在
            if not os.path.exists(self.settings['download_path']):
                os.makedirs(self.settings['download_path'], exist_ok=True)
            
            import json
            with open('settings.json', 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, ensure_ascii=False, indent=2)
            
            gui_logger.info(f"成功保存设置: {self.settings}")
            self.accept()
        except Exception as e:
            gui_logger.error(f"保存设置失败: {e}")
    
    def get_settings(self):
        return self.settings
    
    def clear_logs(self):
        try:
            import os
            import logging
            from PyQt5.QtWidgets import QMessageBox
            
            # 先关闭所有日志处理器，释放文件句柄
            for handler in logging.root.handlers[:]:
                logging.root.removeHandler(handler)
                handler.close()
            
            # 只清除实际存在的日志文件
            log_files = ["hanime1_gui.log"]  # 只有gui配置了日志
            deleted_files = []
            
            for log_file in log_files:
                if os.path.exists(log_file):
                    try:
                        os.remove(log_file)
                        deleted_files.append(log_file)
                    except Exception as file_error:
                        # 使用print而不是logger记录，因为logger可能已关闭
                        print(f"删除日志文件失败: {log_file}, 错误: {str(file_error)}")
            
            if deleted_files:
                QMessageBox.information(self, "清除日志", f"成功清除以下日志文件:\n{', '.join(deleted_files)}")
            else:
                QMessageBox.information(self, "清除日志", "没有找到日志文件")
            
            # 重新初始化日志记录器
            logging.basicConfig(
                level=logging.INFO,
                format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                filename='hanime1_gui.log',
                filemode='a'
            )
            
        except Exception as e:
            # 使用print而不是logger记录，因为logger可能有问题
            print(f"清除日志失败: {e}")
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.critical(self, "清除日志失败", f"清除日志时发生错误:\n{str(e)}")
    
    def clear_cache(self):
        """
        清除缓存
        """
        try:
            from PyQt5.QtWidgets import QMessageBox
            import os
            import shutil
            
            # 清除API缓存
            from hanime1_api import Hanime1API
            api = Hanime1API()
            api.clear_cache()
            
            # 清除缓存目录
            cache_dir = "cache"
            if os.path.exists(cache_dir):
                shutil.rmtree(cache_dir)
                os.makedirs(cache_dir)  # 重新创建空的缓存目录
            
            QMessageBox.information(self, "清除缓存", "成功清除所有缓存")
        except Exception as e:
            # 使用print而不是logger记录，因为logger可能有问题
            print(f"清除缓存失败: {e}")
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.critical(self, "清除缓存失败", f"清除缓存时发生错误:\n{str(e)}")

class AnnouncementDialog(QDialog):
    def __init__(self, parent=None, first_run=False, announcement=None):
        super().__init__(parent)
        self.first_run = first_run
        self.announcement = announcement or {
            'title': '欢迎使用Hanime1视频工具',
            'content': '这是一个用于搜索和下载Hanime1视频的工具。\n\n使用说明：\n1. 在搜索框中输入关键词或视频ID进行搜索\n2. 选择视频查看详情\n3. 点击下载按钮下载视频\n\n请注意遵守相关法律法规，合理使用本工具。\n\n仅用于学习，请在24小时内删除。'
        }
        
        self.setWindowTitle(self.announcement['title'])
        self.setModal(True)
        if self.first_run:
            self.setWindowFlags(Qt.WindowCloseButtonHint)
        else:
            self.setWindowFlags(Qt.Window | Qt.WindowTitleHint | Qt.WindowCloseButtonHint)
        
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # 使用滚动区域确保所有内容都能显示
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        # 公告内容容器
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        
        # 公告内容
        content_label = QLabel(self.announcement['content'])
        content_label.setWordWrap(True)
        content_label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        content_label.setMinimumHeight(150)
        content_layout.addWidget(content_label)
        
        scroll_area.setWidget(content_widget)
        layout.addWidget(scroll_area, 1)  # 占主要空间
        
        # 分隔线
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        layout.addWidget(line)
        
        # 按钮布局
        button_layout = QHBoxLayout()
        
        if self.first_run:
            # 首次启动模式：退出和同意按钮
            button_layout.addStretch()
            
            exit_button = QPushButton("退出")
            exit_button.clicked.connect(self.on_exit)
            button_layout.addWidget(exit_button)
            
            agree_button = QPushButton("同意")
            agree_button.clicked.connect(self.on_agree)
            agree_button.setDefault(True)
            button_layout.addWidget(agree_button)
        else:
            # 后续启动模式：只有关闭按钮
            button_layout.addStretch()
        
        layout.addLayout(button_layout)
        
        # 移除固定大小，改用合适的初始大小
        self.resize(500, 350)
    
    def on_exit(self):
        # 退出程序
        QApplication.instance().quit()
    
    def on_agree(self):
        # 标记为已同意，关闭对话框
        self.accept()

class Hanime1GUI(QMainWindow):
    def __init__(self):
        super().__init__()
        gui_logger.info("初始化Hanime1GUI主窗口")
        self.api = Hanime1API()
        self.current_search_results = []
        self.current_video_info = None
        
        self.favorites = []
        self.favorites_file = "hanime1_favorites.json"
        self.load_favorites()
        
        self.settings = {
            'download_mode': 'multi_thread',
            'num_threads': 4,
            'download_quality': '最高',
            'download_path': os.path.join(os.getcwd(), 'hamineDownload')
        }
        self.load_settings()
        
        self.filters = {
            'keyword': '',
            'genre': '全部',
            'sort': '最新上市',
            'date': '全部',
            'duration': '全部',
            'properties': [],
            'relationship': [],
            'character_setting': [],
            'appearance_body': [],
            'scene_location': [],
            'story_plot': [],
            'sexual_position': []
        }
        
        self.threadpool = QThreadPool()
        gui_logger.info(f"初始化线程池，最大线程数: {self.threadpool.maxThreadCount()}")
        
        self.init_ui()
        gui_logger.info("Hanime1GUI主窗口初始化完成")
        
    def init_ui(self):
        self.setWindowTitle("Hanime1视频工具")
        self.setGeometry(100, 100, 1200, 800)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setSpacing(16)
        main_layout.setContentsMargins(16, 16, 16, 16)
        
        left_widget = QWidget()
        left_widget.setMinimumWidth(350)
        left_widget.setMaximumWidth(500)
        left_layout = QVBoxLayout(left_widget)
        left_layout.setSpacing(12)
        
        search_title = QLabel("视频搜索")
        left_layout.addWidget(search_title)
        
        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("请输入搜索关键词...")
        self.search_input.returnPressed.connect(self.search_videos)  # 回车直接搜索
        search_layout.addWidget(self.search_input, 1)
        
        self.search_button = QPushButton("搜索")
        self.search_button.clicked.connect(self.search_videos)
        search_layout.addWidget(self.search_button)
        
        left_layout.addLayout(search_layout)
        
        page_layout = QHBoxLayout()
        page_layout.addWidget(QLabel("页码:"))
        self.page_spinbox = QSpinBox()
        self.page_spinbox.setMinimum(1)
        self.page_spinbox.setMaximum(100)
        page_layout.addWidget(self.page_spinbox)
        left_layout.addLayout(page_layout)
        

        
        self.settings_button = QPushButton("设置")
        self.settings_button.clicked.connect(self.show_settings)
        left_layout.addWidget(self.settings_button)
        
        # 默认启用代理，不再显示代理开关
        self.api.enable_proxy()
        
        from PyQt5.QtWidgets import QTabWidget
        tab_widget = QTabWidget()
        
        self.video_list = QListWidget()
        self.video_list.itemClicked.connect(self.on_video_selected)
        self.video_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.video_list.customContextMenuRequested.connect(self.show_video_context_menu)
        self.video_list.setSelectionMode(QListWidget.ExtendedSelection)  # 支持按住左键滑动多选
        tab_widget.addTab(self.video_list, "搜索结果")
        
        self.favorites_list = QListWidget()
        self.favorites_list.itemClicked.connect(self.on_favorite_selected)
        self.favorites_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.favorites_list.customContextMenuRequested.connect(self.show_favorite_context_menu)
        self.favorites_list.setSelectionMode(QListWidget.ExtendedSelection)  # 支持按住左键滑动多选
        tab_widget.addTab(self.favorites_list, "收藏夹")
        
        self.update_favorites_list()
        
        left_layout.addWidget(tab_widget)
        
        main_layout.addWidget(left_widget)
        
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setSpacing(16)
        
        info_group = QGroupBox("视频信息")
        info_layout = QVBoxLayout(info_group)
        info_layout.setSpacing(8)
        
        self.info_form = QFormLayout()
        self.info_form.setSpacing(5)
        self.info_form.setVerticalSpacing(8)
        
        self.title_label = QLabel("-")
        self.title_label.setWordWrap(True)
        self.chinese_title_label = QLabel("-")
        self.chinese_title_label.setWordWrap(True)
        self.views_label = QLabel("-")
        self.upload_date_label = QLabel("-")
        self.likes_label = QLabel("-")
        self.tags_label = QLabel("-")
        self.tags_label.setWordWrap(True)
        self.description_text = QTextEdit("-")
        self.description_text.setReadOnly(True)
        self.description_text.setMaximumHeight(120)
        
        self.view_cover_button = QPushButton("查看封面")
        self.view_cover_button.clicked.connect(self.show_cover)
        self.view_cover_button.setEnabled(False)
        
        self.current_cover_url = ""
        
        self.info_form.addRow(QLabel("标题:"), self.title_label)
        self.info_form.addRow(QLabel("中文标题:"), self.chinese_title_label)
        self.info_form.addRow(QLabel("观看次数:"), self.views_label)
        self.info_form.addRow(QLabel("上传日期:"), self.upload_date_label)
        self.info_form.addRow(QLabel("点赞:"), self.likes_label)
        self.info_form.addRow(QLabel("标签:"), self.tags_label)
        self.info_form.addRow(QLabel("封面:"), self.view_cover_button)
        self.info_form.addRow(QLabel("描述:"), self.description_text)
        
        info_layout.addLayout(self.info_form)
        
        related_group = QGroupBox("相关视频")
        related_layout = QVBoxLayout(related_group)
        related_layout.setSpacing(5)
        
        self.related_list = QListWidget()
        self.related_list.setMinimumHeight(150)
        self.related_list.setMaximumHeight(200)
        self.related_list.itemClicked.connect(self.on_related_video_clicked)
        related_layout.addWidget(self.related_list)
        info_layout.addWidget(related_group)
        
        source_links_title = QLabel("当前视频源链接:")
        info_layout.addWidget(source_links_title)
        
        self.source_links_widget = QWidget()
        self.source_links_widget.setMinimumHeight(150)
        self.source_links_widget.setMaximumHeight(250)
        self.source_links_layout = QVBoxLayout(self.source_links_widget)
        self.source_links_layout.setSpacing(8)
        self.source_links_layout.setContentsMargins(10, 5, 10, 5)
        info_layout.addWidget(self.source_links_widget)
        
        right_layout.addWidget(info_group)
        
        download_group = QGroupBox("下载管理")
        download_layout = QVBoxLayout(download_group)
        download_layout.setSpacing(8)
        
        self.download_list = QListWidget()
        self.download_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.download_list.customContextMenuRequested.connect(self.show_download_context_menu)
        download_layout.addWidget(QLabel("下载队列:"))
        download_layout.addWidget(self.download_list)
        
        download_control_layout = QHBoxLayout()
        download_control_layout.setSpacing(5)
        
        self.start_download_button = QPushButton("开始下载")
        self.start_download_button.clicked.connect(self.on_start_download)
        
        self.pause_download_button = QPushButton("暂停下载")
        self.pause_download_button.clicked.connect(self.on_pause_download)
        
        self.cancel_download_button = QPushButton("取消下载")
        self.cancel_download_button.clicked.connect(self.on_cancel_download)
        
        self.clear_download_button = QPushButton("清空列表")
        self.clear_download_button.clicked.connect(self.on_clear_download_list)
        
        download_control_layout.addWidget(self.start_download_button)
        download_control_layout.addWidget(self.pause_download_button)
        download_control_layout.addWidget(self.cancel_download_button)
        download_control_layout.addWidget(self.clear_download_button)
        
        download_layout.addLayout(download_control_layout)
        
        progress_layout = QVBoxLayout()
        progress_layout.setSpacing(5)
        
        self.download_progress = QProgressBar()
        self.download_progress.setValue(0)
        
        self.download_info = QLabel("准备下载")
        
        progress_layout.addWidget(QLabel("下载进度:"))
        progress_layout.addWidget(self.download_progress)
        progress_layout.addWidget(self.download_info)
        
        download_layout.addLayout(progress_layout)
        
        right_layout.addWidget(download_group)
        
        main_layout.addWidget(right_widget)
        
        self.statusBar()
        
        self.downloads = []
        self.active_downloads = {}
    def search_videos(self):
        keyword = self.search_input.text().strip()
        
        self.filters['keyword'] = keyword
        
        gui_logger.info(f"用户点击搜索，关键词: {keyword}, 筛选条件: {self.filters}")
        self.statusBar().showMessage(f"正在搜索: {keyword}...")
        
        genre = self.filters['genre'] if self.filters['genre'] != '全部' else ""
        sort = self.filters['sort'] if self.filters['sort'] != '最新上市' else ""
        date = self.filters['date'] if self.filters['date'] != '全部' else ""
        duration = self.filters['duration'] if self.filters['duration'] != '全部' else ""
        page = self.page_spinbox.value()
        gui_logger.debug(f"搜索参数: 分类={genre}, 排序={sort}, 日期={date}, 时长={duration}, 页码={page}")
        
        worker = SearchWorker(
            api=self.api,
            query=keyword,
            genre=genre,
            sort=sort,
            date=date,
            duration=duration,
            page=page
        )
        
        worker.signals.result.connect(self.on_search_complete)
        worker.signals.error.connect(self.on_search_error)
        worker.signals.finished.connect(self.on_search_finished)
        
        self.threadpool.start(worker)
    
    def on_search_complete(self, search_result):
        gui_logger.debug(f"搜索结果回调，结果类型: {type(search_result)}")
        if search_result and search_result['videos']:
            filtered_videos = search_result['videos']
            gui_logger.info(f"搜索结果: {len(filtered_videos)} 个视频")
            
            self.current_search_results = filtered_videos
            self.video_list.clear()
            for video in filtered_videos:
                self.video_list.addItem(f"[{video['video_id']}] {video['title']}")
            
            gui_logger.info(f"搜索完成，找到 {len(filtered_videos)} 个结果")
            self.statusBar().showMessage(f"搜索完成，找到 {len(filtered_videos)} 个结果")
        else:
            self.video_list.clear()
            query = self.search_input.text().strip()
            gui_logger.info(f"未找到视频结果，关键词: {query}")
            self.statusBar().showMessage("未找到视频结果")
    

    
    def on_search_error(self, error):
        gui_logger.error(f"搜索出错: {error}")
        self.statusBar().showMessage(f"搜索出错: {error}")
    
    def on_search_finished(self):
        gui_logger.debug("搜索操作完成")
    
    def on_video_selected(self, item):
        index = self.video_list.row(item)
        gui_logger.debug(f"视频列表项被点击，索引: {index}")
        if 0 <= index < len(self.current_search_results):
            video = self.current_search_results[index]
            gui_logger.info(f"用户选择视频: [{video['video_id']}] {video['title']}")
            self.get_video_info(video['video_id'])
    
    def get_video_info(self, video_id):
        gui_logger.info(f"开始获取视频信息，视频ID: {video_id}")
        self.statusBar().showMessage(f"正在获取视频 {video_id} 的信息...")
        
        # 清空所有显示的信息，显示加载中状态
        self.title_label.setText("加载中...")
        self.chinese_title_label.setText("加载中...")
        self.views_label.setText("加载中...")
        self.upload_date_label.setText("加载中...")
        self.likes_label.setText("加载中...")
        self.tags_label.setText("加载中...")
        self.description_text.setText("加载中...")
        
        # 清空封面信息
        self.current_cover_url = ""
        self.view_cover_button.setEnabled(False)
        
        # 清空相关视频列表
        self.related_list.clear()
        
        # 清空视频源链接
        self.update_source_links([])
        
        worker = GetVideoInfoWorker(
            api=self.api,
            video_id=video_id
        )
        
        worker.signals.result.connect(lambda result: self.on_video_info_complete(result, video_id))
        worker.signals.error.connect(lambda error: self.on_video_info_error(error, video_id))
        worker.signals.finished.connect(self.on_video_info_finished)
        
        self.threadpool.start(worker)
    
    def show_cover(self):
        if self.current_cover_url:
            gui_logger.info(f"显示封面: {self.current_cover_url}")
            try:
                from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton
                from PyQt5.QtCore import Qt
                from PyQt5.QtGui import QPixmap
                import requests
                
                dialog = QDialog(self)
                dialog.setWindowTitle("视频封面")
                dialog.setGeometry(100, 100, 800, 600)
                
                layout = QVBoxLayout(dialog)
                
                cover_label = QLabel()
                cover_label.setAlignment(Qt.AlignCenter)
                
                proxies = self.api.session.proxies if self.api.is_proxy_enabled() else None
                response = requests.get(self.current_cover_url, proxies=proxies, timeout=10)
                response.raise_for_status()
                
                pixmap = QPixmap()
                pixmap.loadFromData(response.content)
                
                scaled_pixmap = pixmap.scaled(780, 540, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                cover_label.setPixmap(scaled_pixmap)
                
                close_button = QPushButton("关闭")
                close_button.clicked.connect(dialog.close)
                
                layout.addWidget(cover_label)
                layout.addWidget(close_button)
                
                dialog.exec_()
                gui_logger.info("封面显示成功")
            except Exception as e:
                gui_logger.error(f"显示封面失败: {e}")
                self.statusBar().showMessage(f"显示封面失败: {str(e)}")
        else:
            self.statusBar().showMessage("没有可用的封面")
            gui_logger.warning("没有可用的封面")
    
    def on_video_info_complete(self, video_info, video_id):
        if video_info:
            gui_logger.debug(f"成功获取视频信息，视频ID: {video_id}")
            self.current_video_info = video_info
            
            self.title_label.setText(video_info['title'])
            self.chinese_title_label.setText(video_info['chinese_title'])
            self.views_label.setText(video_info['views'])
            self.upload_date_label.setText(video_info['upload_date'])
            self.likes_label.setText(video_info['likes'])
            self.tags_label.setText(", ".join(video_info['tags']))
            self.description_text.setText(video_info['description'])
            
            if 'thumbnail' in video_info and video_info['thumbnail']:
                self.current_cover_url = video_info['thumbnail']
                self.view_cover_button.setEnabled(True)
                gui_logger.info(f"已设置封面URL: {self.current_cover_url}")
            else:
                self.current_cover_url = ""
                self.view_cover_button.setEnabled(False)
                gui_logger.info("没有找到封面URL")
            
            self.related_list.clear()
            for i, related in enumerate(video_info['series']):
                video_id = related.get('video_id', '')
                
                title = related.get('chinese_title')
                if not title or title.strip() == '' or title == f"相关视频 {video_id}":
                    title = related.get('title')
                if not title or title.strip() == '' or title == f"相关视频 {video_id}":
                    title = f"视频 {video_id}"
                
                self.related_list.addItem(f"[{video_id}] {title}")
            gui_logger.debug(f"找到 {len(video_info['series'])} 个相关视频，详细信息: {video_info['series']}")
            
            self.update_source_links(video_info['video_sources'])
            
            if video_info['video_sources']:
                gui_logger.info(f"找到 {len(video_info['video_sources'])} 个视频源")
            else:
                gui_logger.warning(f"视频 {video_id} 没有可用的视频源")
            
            self.statusBar().showMessage(f"视频 {video_id} 信息加载完成")
        else:
            gui_logger.error(f"无法获取视频 {video_id} 的信息")
            self.statusBar().showMessage(f"无法获取视频 {video_id} 的信息")
            self.update_source_links([])
    
    def on_video_info_error(self, error, video_id):
        gui_logger.error(f"获取视频 {video_id} 信息出错: {error}")
        self.statusBar().showMessage(f"获取视频 {video_id} 信息出错: {error}")
    
    def on_video_info_finished(self):
        gui_logger.debug("获取视频信息操作完成")
    
    def load_favorites(self):
        import os
        if os.path.exists(self.favorites_file):
            try:
                import json
                with open(self.favorites_file, 'r', encoding='utf-8') as f:
                    self.favorites = json.load(f)
                gui_logger.info(f"成功加载 {len(self.favorites)} 个收藏的视频")
            except Exception as e:
                gui_logger.error(f"加载收藏夹数据时出错: {e}")
                self.favorites = []
        else:
            gui_logger.info("收藏夹文件不存在，创建空收藏夹")
            self.favorites = []
    
    def save_favorites(self):
        try:
            import json
            with open(self.favorites_file, 'w', encoding='utf-8') as f:
                json.dump(self.favorites, f, ensure_ascii=False, indent=2)
            gui_logger.info(f"成功保存 {len(self.favorites)} 个收藏的视频")
        except Exception as e:
            gui_logger.error(f"保存收藏夹数据时出错: {e}")
    
    def load_settings(self):
        try:
            import json
            import os
            if os.path.exists('settings.json'):
                with open('settings.json', 'r', encoding='utf-8') as f:
                    self.settings = json.load(f)
                gui_logger.info(f"成功加载设置: {self.settings}")
            else:
                self.save_settings()
        except Exception as e:
            gui_logger.error(f"加载设置失败: {e}")
            self.settings = {
                'download_mode': 'multi_thread',
                'num_threads': 4
            }
    
    def save_settings(self):
        try:
            import json
            with open('settings.json', 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, ensure_ascii=False, indent=2)
            gui_logger.info(f"成功保存设置: {self.settings}")
        except Exception as e:
            gui_logger.error(f"保存设置失败: {e}")
    
    def show_settings(self):
        dialog = SettingsDialog(self, self.settings)
        dialog.exec_()
        self.load_settings()
        gui_logger.info(f"设置已更新: {self.settings}")
    

    
    def add_to_favorites(self, video):
        for fav in self.favorites:
            if fav['video_id'] == video['video_id']:
                gui_logger.info(f"视频 {video['video_id']} 已在收藏夹中")
                self.statusBar().showMessage(f"视频 {video['title'][:20]}... 已在收藏夹中")
                return False
        
        self.favorites.append(video)
        self.save_favorites()
        gui_logger.info(f"成功将视频 {video['video_id']} 添加到收藏夹")
        self.statusBar().showMessage(f"成功将视频 {video['title'][:20]}... 添加到收藏夹")
        if hasattr(self, 'favorites_list'):
            self.update_favorites_list()
        return True
    
    def remove_from_favorites(self, video_id):
        for i, fav in enumerate(self.favorites):
            if fav['video_id'] == video_id:
                removed_video = self.favorites.pop(i)
                self.save_favorites()
                gui_logger.info(f"成功将视频 {video_id} 从收藏夹中移除")
                self.statusBar().showMessage(f"成功将视频 {removed_video['title'][:20]}... 从收藏夹中移除")
                if hasattr(self, 'favorites_list'):
                    self.update_favorites_list()
                return True
        gui_logger.info(f"视频 {video_id} 不在收藏夹中")
        self.statusBar().showMessage(f"视频不在收藏夹中")
        return False
    
    def is_favorite(self, video_id):
        for fav in self.favorites:
            if fav['video_id'] == video_id:
                return True
        return False
    
    def update_favorites_list(self):
        self.favorites_list.clear()
        for video in self.favorites:
            self.favorites_list.addItem(f"[{video['video_id']}] {video['title']}")
    
    def on_video_source_changed(self, index):
        gui_logger.debug(f"视频源选择改变，新索引: {index}")
        if index > 0 and self.current_video_info and self.current_video_info['video_sources']:
            source_index = index - 1
            if 0 <= source_index < len(self.current_video_info['video_sources']):
                source = self.current_video_info['video_sources'][source_index]
                gui_logger.info(f"用户选择视频源: {source['url']}")
    
    def extract_video_id(self, item):
        """
        从列表项中提取视频ID
        :param item: QListWidgetItem对象
        :return: 视频ID或None
        """
        text = item.text()
        import re
        match = re.search(r'\[(\d+)\]', text)
        if match:
            return match.group(1)
        return None
    
    def on_favorite_selected(self, item):
        video_id = self.extract_video_id(item)
        if video_id:
            gui_logger.info(f"用户选择收藏夹视频: {video_id}")
            self.get_video_info(video_id)
        else:
            gui_logger.error(f"无法从文本中提取视频ID: {text}")
    
    def show_video_context_menu(self, position):
        selected_items = self.video_list.selectedItems()
        if not selected_items:
            return
        
        menu = QMenu()
        
        # 多选添加到收藏夹
        if len(selected_items) == 1:
            # 单个选择时，保留原来的添加到收藏夹
            add_to_favorites_action = QAction("添加到收藏夹", self)
            add_to_favorites_action.triggered.connect(lambda: self.on_add_to_favorites_from_menu(selected_items[0]))
            menu.addAction(add_to_favorites_action)
        else:
            # 多选时，添加批量添加到收藏夹
            add_to_favorites_action = QAction("批量添加到收藏夹", self)
            add_to_favorites_action.triggered.connect(lambda: self.on_batch_add_to_favorites(selected_items))
            menu.addAction(add_to_favorites_action)
        
        # 批量下载
        batch_download_action = QAction("批量下载", self)
        batch_download_action.triggered.connect(lambda: self.on_batch_download_from_menu(selected_items))
        menu.addAction(batch_download_action)
        
        # 用浏览器打开（只支持单个）
        if len(selected_items) == 1:
            open_browser_action = QAction("用浏览器打开", self)
            open_browser_action.triggered.connect(lambda: self.on_open_video_in_browser(selected_items[0]))
            menu.addAction(open_browser_action)
        
        menu.exec_(self.video_list.viewport().mapToGlobal(position))
    
    def show_favorite_context_menu(self, position):
        selected_items = self.favorites_list.selectedItems()
        if not selected_items:
            return
        
        menu = QMenu()
        
        # 查看详情（只支持单个）
        if len(selected_items) == 1:
            view_details_action = QAction("查看详情", self)
            view_details_action.triggered.connect(lambda: self.on_favorite_selected(selected_items[0]))
            menu.addAction(view_details_action)
        
        # 从收藏夹移除（支持多选）
        if len(selected_items) == 1:
            remove_from_favorites_action = QAction("从收藏夹移除", self)
            remove_from_favorites_action.triggered.connect(lambda: self.on_remove_from_favorites_from_menu(selected_items[0]))
        else:
            remove_from_favorites_action = QAction("批量从收藏夹移除", self)
            remove_from_favorites_action.triggered.connect(lambda: self.on_batch_remove_from_favorites(selected_items))
        menu.addAction(remove_from_favorites_action)
        
        # 批量下载
        batch_download_action = QAction("批量下载", self)
        batch_download_action.triggered.connect(lambda: self.on_batch_download_from_favorites(selected_items))
        menu.addAction(batch_download_action)
        
        # 用浏览器打开（只支持单个）
        if len(selected_items) == 1:
            open_browser_action = QAction("用浏览器打开", self)
            open_browser_action.triggered.connect(lambda: self.on_open_video_in_browser(selected_items[0]))
            menu.addAction(open_browser_action)
        
        menu.exec_(self.favorites_list.viewport().mapToGlobal(position))
    
    def on_add_to_favorites_from_menu(self, item):
        video_id = self.extract_video_id(item)
        if video_id:
            for video in self.current_search_results:
                if video['video_id'] == video_id:
                    self.add_to_favorites(video)
                    break
    
    def on_open_video_in_browser(self, item):
        video_id = self.extract_video_id(item)
        if video_id:
            video_url = f"https://hanime1.me/watch?v={video_id}"
            gui_logger.info(f"用浏览器打开视频页面: {video_url}")
            
            try:
                import webbrowser
                webbrowser.open(video_url)
                gui_logger.info(f"成功用浏览器打开视频页面: {video_url}")
                self.statusBar().showMessage(f"已在浏览器中打开视频页面")
            except Exception as e:
                gui_logger.error(f"用浏览器打开视频页面失败: {e}")
                self.statusBar().showMessage(f"用浏览器打开失败: {str(e)}")
    
    def on_remove_from_favorites_from_menu(self, item):
        video_id = self.extract_video_id(item)
        if video_id:
            self.remove_from_favorites(video_id)
    
    def on_batch_add_to_favorites(self, items):
        """
        批量添加到收藏夹
        """
        added_count = 0
        for item in items:
            video_id = self.extract_video_id(item)
            if video_id:
                # 从搜索结果中查找视频
                video = next((v for v in self.current_search_results if v['video_id'] == video_id), None)
                if video:
                    if self.add_to_favorites(video):
                        added_count += 1
        
        self.statusBar().showMessage(f"成功添加 {added_count}/{len(items)} 个视频到收藏夹")
    
    def on_batch_remove_from_favorites(self, items):
        """
        批量从收藏夹移除
        """
        # 先收集所有要移除的视频ID，避免在遍历过程中修改列表
        video_ids_to_remove = []
        for item in items:
            video_id = self.extract_video_id(item)
            if video_id:
                video_ids_to_remove.append(video_id)
        
        removed_count = 0
        if video_ids_to_remove:
            # 一次性移除所有视频，只更新一次列表
            for video_id in video_ids_to_remove:
                # 直接修改收藏夹列表，不调用remove_from_favorites避免重复更新
                for i, fav in enumerate(self.favorites):
                    if fav['video_id'] == video_id:
                        self.favorites.pop(i)
                        removed_count += 1
                        break
            
            # 只保存一次
            self.save_favorites()
            # 只更新一次列表
            self.update_favorites_list()
        
        self.statusBar().showMessage(f"成功从收藏夹移除 {removed_count}/{len(items)} 个视频")
    
    def on_batch_download_from_menu(self, items):
        """
        从搜索结果批量下载
        """
        self.batch_download_videos(items, source='search')
    
    def on_batch_download_from_favorites(self, items):
        """
        从收藏夹批量下载
        """
        self.batch_download_videos(items, source='favorites')
    
    def batch_download_videos(self, items, source='search'):
        """
        批量下载视频
        :param items: 选中的列表项
        :param source: 来源，'search' 或 'favorites'
        """
        # 提取所有选中的视频ID
        video_ids = []
        for item in items:
            text = item.text()
            import re
            match = re.search(r'\[(\d+)\]', text)
            if match:
                video_ids.append(match.group(1))
        
        if video_ids:
            # 使用设置中的下载画质
            download_quality = self.settings.get('download_quality', '最高')
            self.statusBar().showMessage(f"开始处理 {len(video_ids)} 个视频，画质: {download_quality}")
            
            # 逐个添加到下载队列，使用现有的add_to_download_queue方法
            for video_id in video_ids:
                if source == 'search':
                    # 从搜索结果中查找视频
                    video = next((v for v in self.current_search_results if v['video_id'] == video_id), None)
                    if video:
                        self.add_to_download_queue(video)
                elif source == 'favorites':
                    # 从收藏夹中查找视频
                    video = next((fav for fav in self.favorites if fav['video_id'] == video_id), None)
                    if video:
                        self.add_to_download_queue(video)
            
            self.statusBar().showMessage(f"已将 {len(video_ids)} 个视频添加到下载队列")
    
    def on_download_video_from_menu(self, item):
        text = item.text()
        gui_logger.debug(f"用户从菜单选择下载视频: {text}")
        import re
        match = re.search(r'\[(\d+)\]', text)
        if match:
            video_id = match.group(1)
            video = None
            for v in self.current_search_results:
                if v['video_id'] == video_id:
                    video = v
                    break
            if not video:
                for v in self.favorites:
                    if v['video_id'] == video_id:
                        video = v
                        break
            if video:
                gui_logger.info(f"用户从菜单选择下载视频: {video['video_id']}")
                self.statusBar().showMessage(f"正在准备下载视频: {video['title'][:20]}...")
                self.add_to_download_queue(video)
    
    def add_to_download_queue(self, video):
        worker = GetVideoInfoWorker(self.api, video['video_id'])
        worker.signals.result.connect(lambda result: self.on_video_info_for_download(result, video))
        worker.signals.error.connect(lambda error: self.on_video_info_for_download_error(error, video))
        self.threadpool.start(worker)
    
    def on_video_info_for_download(self, video_info, original_video):
        if video_info and video_info['video_sources']:
            # 获取设置中的下载画质
            download_quality = self.settings.get('download_quality', '最高')
            
            # 选择合适的视频源
            video_sources = video_info['video_sources']
            if video_sources:
                if download_quality == '最高':
                    # 选择最高画质（假设size越大，画质越高）
                    source = max(video_sources, key=lambda x: int(x['quality'].replace('p', '')) if x['quality'] != 'unknown' else 0)
                else:
                    # 选择最低画质
                    source = min(video_sources, key=lambda x: int(x['quality'].replace('p', '')) if x['quality'] != 'unknown' else 9999)
            else:
                # 没有可用的视频源
                gui_logger.error(f"视频 {video_info['video_id']} 没有可用的视频源")
                self.statusBar().showMessage(f"视频 {video_info['title'][:20]}... 没有可用的视频源")
                return
            
            title = video_info['chinese_title']
            if not title or title.strip() == '-':
                title = video_info['title']
            
            download_task = {
                'video_id': video_info['video_id'],
                'title': title,
                'url': source['url'],
                'status': 'pending',
                'progress': 0,
                'size': 0,
                'total_size': 0,
                'source': source
            }
            
            self.downloads.append(download_task)
            
            self.update_download_list()
            
            gui_logger.info(f"视频 {video_info['video_id']} 已添加到下载队列")
            self.statusBar().showMessage(f"视频 {video_info['title'][:20]}... 已添加到下载队列")
        else:
            gui_logger.error(f"无法获取视频 {original_video['video_id']} 的视频源")
            self.statusBar().showMessage(f"无法获取视频 {original_video['title'][:20]}... 的视频源")
    
    def on_video_info_for_download_error(self, error, video):
        gui_logger.error(f"获取视频 {video['video_id']} 信息时出错: {error}")
        self.statusBar().showMessage(f"获取视频 {video['title'][:20]}... 信息时出错: {error}")
    
    def update_download_list(self):
        self.download_list.clear()
        for download in self.downloads:
            status_text = {
                'pending': '等待中',
                'downloading': '下载中',
                'paused': '已暂停',
                'completed': '已完成',
                'error': '出错',
                'cancelled': '已取消'
            }[download['status']]
            self.download_list.addItem(f"[{download['video_id']}] {download['title'][:30]}... - {status_text} ({download['progress']:.1f}%)")
    
    def on_start_download(self):
        for i, download in enumerate(self.downloads):
            if download['status'] == 'pending' or download['status'] == 'paused':
                self.start_download(i)
                break
    
    def start_download(self, index):
        if 0 <= index < len(self.downloads):
            download = self.downloads[index]
            if download['status'] in ['pending', 'paused']:
                import re
                
                safe_title = download['title'][:100]
                safe_title = re.sub(r'[\\/:*?"<>|]', '_', safe_title)
                safe_title = safe_title.strip(' _')
                if not safe_title:
                    safe_title = f"video_{download['video_id']}"
                filename = f"{safe_title}.mp4"
                
                if self.settings['download_mode'] == 'multi_thread':
                    num_threads = self.settings['num_threads']
                    gui_logger.info(f"使用多线程下载，线程数: {num_threads}")
                else:
                    num_threads = 1
                    gui_logger.info("使用单线程下载")
                
                # 获取设置中的下载路径
                download_path = self.settings.get('download_path', os.path.join(os.getcwd(), 'hamineDownload'))
                
                proxy_config = self.api.session.proxies if self.api.is_proxy_enabled() else None
                worker = DownloadWorker(download['url'], filename, save_path=download_path, num_threads=num_threads, proxy_config=proxy_config)
                
                worker.signals.progress.connect(lambda progress_info, idx=index: self.on_download_progress(progress_info, idx))
                worker.signals.finished.connect(lambda idx=index: self.on_download_finished(idx))
                worker.signals.error.connect(lambda error, idx=index: self.on_download_error(error, idx))
                
                self.downloads[index]['status'] = 'downloading'
                self.downloads[index]['filename'] = filename
                self.update_download_list()
                
                self.active_downloads[index] = worker
                
                self.threadpool.start(worker)
                
                gui_logger.info(f"开始下载视频 {download['video_id']}")
                self.statusBar().showMessage(f"开始下载视频 {download['title'][:20]}...")
    
    def on_pause_download(self):
        for index, worker in self.active_downloads.items():
            worker.cancel()
            self.downloads[index]['status'] = 'paused'
            self.update_download_list()
            gui_logger.info(f"已暂停下载视频 {self.downloads[index]['video_id']}")
            self.statusBar().showMessage(f"已暂停下载视频 {self.downloads[index]['title'][:20]}...")
            break
    
    def on_cancel_download(self):
        for index, worker in self.active_downloads.items():
            worker.cancel()
            self.downloads[index]['status'] = 'cancelled'
            self.active_downloads.pop(index)
            self.update_download_list()
            gui_logger.info(f"已取消下载视频 {self.downloads[index]['video_id']}")
            self.statusBar().showMessage(f"已取消下载视频 {self.downloads[index]['title'][:20]}...")
            break
    
    def on_clear_download_list(self):
        for worker in self.active_downloads.values():
            worker.cancel()
        
        self.downloads.clear()
        self.active_downloads.clear()
        self.update_download_list()
        self.download_progress.setValue(0)
        self.download_info.setText("准备下载")
        
        gui_logger.info("已清空下载列表")
        self.statusBar().showMessage("已清空下载列表")
    
    def on_download_progress(self, progress_info, index):
        if 0 <= index < len(self.downloads):
            self.downloads[index]['progress'] = progress_info['progress']
            self.downloads[index]['size'] = progress_info['size']
            self.downloads[index]['total_size'] = progress_info['total_size']
            
            self.update_download_list()
            
            self.download_progress.setValue(int(progress_info['progress']))
            
            total_size_mb = progress_info['total_size'] / (1024 * 1024)
            downloaded_size_mb = progress_info['size'] / (1024 * 1024)
            self.download_info.setText(f"正在下载: {progress_info['filename'][:30]}... {downloaded_size_mb:.1f}MB / {total_size_mb:.1f}MB")
    
    def on_download_finished(self, index):
        if 0 <= index < len(self.downloads):
            self.downloads[index]['status'] = 'completed'
            self.downloads[index]['progress'] = 100.0
            
            if index in self.active_downloads:
                self.active_downloads.pop(index)
            
            self.update_download_list()
            
            gui_logger.info(f"视频 {self.downloads[index]['video_id']} 下载完成")
            self.statusBar().showMessage(f"视频 {self.downloads[index]['title'][:20]}... 下载完成")
            
            self.on_start_download()
    
    def on_download_error(self, error, index):
        if 0 <= index < len(self.downloads):
            self.downloads[index]['status'] = 'error'
            
            if index in self.active_downloads:
                self.active_downloads.pop(index)
            
            self.update_download_list()
            
            gui_logger.error(f"视频 {self.downloads[index]['video_id']} 下载出错: {error}")
            self.statusBar().showMessage(f"视频 {self.downloads[index]['title'][:20]}... 下载出错: {error}")
            
            self.on_start_download()
    

    
    def show_download_context_menu(self, position):
        item = self.download_list.itemAt(position)
        if not item:
            return
        
        menu = QMenu()
        
        start_action = QAction("开始下载", self)
        start_action.triggered.connect(lambda: self.on_start_download_from_menu(item))
        menu.addAction(start_action)
        
        pause_action = QAction("暂停下载", self)
        pause_action.triggered.connect(lambda: self.on_pause_download_from_menu(item))
        menu.addAction(pause_action)
        
        cancel_action = QAction("取消下载", self)
        cancel_action.triggered.connect(lambda: self.on_cancel_download_from_menu(item))
        menu.addAction(cancel_action)
        
        remove_action = QAction("从队列中移除", self)
        remove_action.triggered.connect(lambda: self.on_remove_from_download_queue(item))
        menu.addAction(remove_action)
        
        menu.exec_(self.download_list.viewport().mapToGlobal(position))
    
    def on_start_download_from_menu(self, item):
        index = self.download_list.row(item)
        self.start_download(index)
    
    def on_pause_download_from_menu(self, item):
        index = self.download_list.row(item)
        if 0 <= index < len(self.downloads) and index in self.active_downloads:
            self.active_downloads[index].cancel()
            self.downloads[index]['status'] = 'paused'
            self.update_download_list()
            gui_logger.info(f"已暂停下载视频 {self.downloads[index]['video_id']}")
            self.statusBar().showMessage(f"已暂停下载视频 {self.downloads[index]['title'][:20]}...")
    
    def on_cancel_download_from_menu(self, item):
        index = self.download_list.row(item)
        if 0 <= index < len(self.downloads) and index in self.active_downloads:
            self.active_downloads[index].cancel()
            self.downloads[index]['status'] = 'cancelled'
            self.active_downloads.pop(index)
            self.update_download_list()
            gui_logger.info(f"已取消下载视频 {self.downloads[index]['video_id']}")
            self.statusBar().showMessage(f"已取消下载视频 {self.downloads[index]['title'][:20]}...")
    
    def on_remove_from_download_queue(self, item):
        index = self.download_list.row(item)
        if 0 <= index < len(self.downloads):
            if index in self.active_downloads:
                self.active_downloads[index].cancel()
                self.active_downloads.pop(index)
            
            removed_download = self.downloads.pop(index)
            self.update_download_list()
            gui_logger.info(f"已从下载队列中移除视频 {removed_download['video_id']}")
            self.statusBar().showMessage(f"已从下载队列中移除视频 {removed_download['title'][:20]}...")
    
    def on_related_video_clicked(self, item):
        text = item.text()
        gui_logger.debug(f"相关视频被点击: {text}")
        import re
        match = re.search(r'\[(\d+)\]', text)
        if match:
            video_id = match.group(1)
            gui_logger.info(f"用户点击相关视频，视频ID: {video_id}")
            self.get_video_info(video_id)
        else:
            gui_logger.error(f"无法从文本中提取视频ID: {text}")
    
    def update_source_links(self, video_sources):
        while self.source_links_layout.count() > 0:
            item = self.source_links_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        
        if not video_sources:
            no_sources_label = QLabel("当前视频没有可用的视频源")
            self.source_links_layout.addWidget(no_sources_label)
            return
        
        tips_label = QLabel("左键点击添加/移除下载队列，右键菜单")
        self.source_links_layout.addWidget(tips_label)
        
        for i, source in enumerate(video_sources):
            quality = source['quality'] if source['quality'] != 'unknown' else f"源{i+1}"
            button_text = f"{quality} - {source['type']}"
            
            source_button = QPushButton(button_text)
            source_button.setToolTip(source['url'])
            
            source_button.setContextMenuPolicy(Qt.CustomContextMenu)
            source_button.customContextMenuRequested.connect(lambda pos, btn=source_button, url=source['url']: self.show_source_link_context_menu(pos, btn, url))
            
            source_button.clicked.connect(lambda checked, url=source['url'], quality=quality: self.toggle_download_queue(url, quality))
            
            self.source_links_layout.addWidget(source_button)
        
        gui_logger.debug(f"已更新 {len(video_sources)} 个视频源链接按钮")
    
    def show_source_link_context_menu(self, position, button, url):
        menu = QMenu()
        
        copy_action = QAction("复制链接", self)
        copy_action.triggered.connect(lambda: self.copy_to_clipboard(url))
        menu.addAction(copy_action)
        
        download_action = QAction("下载视频", self)
        download_action.triggered.connect(lambda: self.download_from_source(url))
        menu.addAction(download_action)
        
        menu.exec_(button.mapToGlobal(position))
    
    def copy_to_clipboard(self, text):
        clipboard = QApplication.clipboard()
        clipboard.setText(text)
        gui_logger.info(f"已复制文本到剪贴板: {text[:30]}...")
        self.statusBar().showMessage(f"已复制链接到剪贴板")
    
    def download_from_source(self, url):
        if not self.current_video_info:
            gui_logger.error(f"无法下载视频，当前没有视频信息")
            self.statusBar().showMessage(f"无法下载视频，当前没有视频信息")
            return
        
        try:
            import re
            quality_match = re.search(r'-(\d+p)\.', url)
            quality = quality_match.group(1) if quality_match else 'unknown'
            
            video_id = self.current_video_info['video_id']
            title = self.current_video_info['chinese_title']
            if not title or title.strip() == '-':
                title = self.current_video_info['title']
            
            gui_logger.info(f"用户从视频源选择下载视频: {video_id}，清晰度: {quality}")
            self.statusBar().showMessage(f"正在准备下载视频: {title[:20]}...")
            
            download_task = {
                'video_id': video_id,
                'title': title,
                'url': url,
                'status': 'pending',
                'progress': 0,
                'size': 0,
                'total_size': 0,
                'source': {'url': url, 'quality': quality, 'type': 'mp4'}
            }
            
            self.downloads.append(download_task)
            
            self.update_download_list()
            
            gui_logger.info(f"视频 {video_id} (清晰度: {quality}) 已添加到下载队列")
            self.statusBar().showMessage(f"视频 {title[:20]}... (清晰度: {quality}) 已添加到下载队列")
        except Exception as e:
            gui_logger.error(f"准备下载视频失败: {e}")
            self.statusBar().showMessage(f"准备下载视频失败: {str(e)}")
    
    def toggle_download_queue(self, url, quality):
        if not self.current_video_info:
            gui_logger.error(f"无法下载视频，当前没有视频信息")
            self.statusBar().showMessage(f"无法下载视频，当前没有视频信息")
            return
        
        try:
            video_id = self.current_video_info['video_id']
            title = self.current_video_info['chinese_title']
            if not title or title.strip() == '-':
                title = self.current_video_info['title']
            
            existing_index = -1
            for i, task in enumerate(self.downloads):
                if task['video_id'] == video_id:
                    existing_index = i
                    break
            
            same_url_index = -1
            for i, task in enumerate(self.downloads):
                if task['url'] == url:
                    same_url_index = i
                    break
            
            if same_url_index != -1:
                self.downloads.pop(same_url_index)
                gui_logger.info(f"视频 {video_id} ({quality}) 已从下载队列中移除")
                self.statusBar().showMessage(f"视频 {title[:20]}... ({quality}) 已从下载队列中移除")
            else:
                if existing_index != -1:
                    self.downloads.pop(existing_index)
                    gui_logger.info(f"视频 {video_id} 已从下载队列中移除（更换清晰度）")
                
                download_task = {
                    'video_id': video_id,
                    'title': title,
                    'url': url,
                    'status': 'pending',
                    'progress': 0,
                    'size': 0,
                    'total_size': 0,
                    'source': {'url': url, 'quality': quality, 'type': 'mp4'}
                }
                
                self.downloads.append(download_task)
                gui_logger.info(f"视频 {video_id} ({quality}) 已添加到下载队列")
                self.statusBar().showMessage(f"视频 {title[:20]}... ({quality}) 已添加到下载队列")
            
            self.update_download_list()
        except Exception as e:
            gui_logger.error(f"切换下载队列失败: {e}")
            self.statusBar().showMessage(f"切换下载队列失败: {str(e)}")
    
    def closeEvent(self, event):
        gui_logger.info("程序关闭，开始清理资源")
        
        for worker in self.active_downloads.values():
            worker.cancel()
        
        gui_logger.info("资源清理完成，程序退出")
        event.accept()
    

if __name__ == "__main__":
    import os
    import json
    
    # 配置文件路径
    config_file = "hanime1_config.json"
    
    # 检查是否是第一次启动
    first_run = False
    if not os.path.exists(config_file):
        first_run = True
    else:
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            first_run = not config.get('has_agreed', False)
        except:
            first_run = True
    
    app = QApplication(sys.argv)
    
    # 创建API实例获取公告
    from hanime1_api import Hanime1API
    api = Hanime1API()
    announcement = api.get_remote_announcement()
    
    # 显示公告对话框
    if first_run:
        # 首次启动：显示带有退出和同意按钮的公告
        dialog = AnnouncementDialog(first_run=True, announcement=announcement)
        result = dialog.exec_()
        
        if result == QDialog.Accepted:
            # 用户同意，记录到配置文件
            config = {'has_agreed': True}
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            
            # 继续启动程序
            window = Hanime1GUI()
            window.show()
            sys.exit(app.exec_())
        else:
            # 用户取消或关闭窗口，退出程序
            sys.exit(0)
    else:
        # 后续启动：只创建主窗口，不显示公告
        window = Hanime1GUI()
        window.show()
        
        sys.exit(app.exec_())
