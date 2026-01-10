import sys
import logging
import os
import json
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QListWidget,
    QLabel, QPushButton, QLineEdit, QSpinBox, QProgressBar, QTextEdit,
    QGroupBox, QFormLayout, QTabWidget, QComboBox, QMenu, QAction, QDialog,
    QCheckBox, QScrollArea, QSizePolicy, QListWidgetItem, QToolButton
)
from PyQt5.QtCore import Qt, QRunnable, QThreadPool, pyqtSignal, pyqtSlot, QObject
from hanime1_api import Hanime1API

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='hanime1_gui.log',
    filemode='a'
)

gui_logger = logging.getLogger('Hanime1GUI')

class WorkerSignals(QObject):
    finished = pyqtSignal()
    error = pyqtSignal(str)
    result = pyqtSignal(object)
    progress = pyqtSignal(dict)

class SearchWorker(QRunnable):
    def __init__(self, api, query, page=1):
        super().__init__()
        self.api = api
        self.query = query
        self.page = page
        self.signals = WorkerSignals()
    
    @pyqtSlot()
    def run(self):
        try:
            result = self.api.search_videos(
                query=self.query,
                page=self.page
            )
            self.signals.result.emit(result)
        except Exception as e:
            self.signals.error.emit(str(e))
        finally:
            self.signals.finished.emit()

class PageNavigationWidget(QWidget):
    """
    网页式页码导航控件
    """
    page_changed = pyqtSignal(int)  # 页码变化信号
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_page = 1
        self.total_pages = 1
        self.max_visible_pages = 5  # 最多显示的页码按钮数量
        
        self.init_ui()
    
    def init_ui(self):
        # 使用垂直布局，避免元素重叠
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(2)
        
        # 水平布局用于按钮
        buttons_layout = QHBoxLayout()
        buttons_layout.setContentsMargins(0, 0, 0, 0)
        buttons_layout.setSpacing(5)
        
        # 第一页按钮
        self.first_button = QPushButton("首页")
        self.first_button.setFixedSize(50, 25)
        self.first_button.clicked.connect(self.go_to_first_page)
        buttons_layout.addWidget(self.first_button)
        
        # 上一页按钮
        self.prev_button = QPushButton("上一页")
        self.prev_button.setFixedSize(60, 25)
        self.prev_button.clicked.connect(self.go_to_prev_page)
        buttons_layout.addWidget(self.prev_button)
        
        # 页码按钮容器
        self.pages_container = QWidget()
        self.pages_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.pages_layout = QHBoxLayout(self.pages_container)
        self.pages_layout.setContentsMargins(0, 0, 0, 0)
        self.pages_layout.setSpacing(3)
        buttons_layout.addWidget(self.pages_container)
        
        # 下一页按钮
        self.next_button = QPushButton("下一页")
        self.next_button.setFixedSize(60, 25)
        self.next_button.clicked.connect(self.go_to_next_page)
        buttons_layout.addWidget(self.next_button)
        
        # 最后一页按钮
        self.last_button = QPushButton("末页")
        self.last_button.setFixedSize(50, 25)
        self.last_button.clicked.connect(self.go_to_last_page)
        buttons_layout.addWidget(self.last_button)
        
        # 添加按钮布局到主布局
        self.layout.addLayout(buttons_layout)
        
        # 页码信息，单独一行显示
        self.page_info = QLabel("第 1 页 / 共 1 页")
        self.page_info.setAlignment(Qt.AlignCenter)
        self.layout.addWidget(self.page_info)
        
        # 初始化状态
        self.update_buttons()
    
    def set_current_page(self, page):
        """设置当前页码"""
        if page < 1 or page > self.total_pages:
            return
        self.current_page = page
        self.update_buttons()
        self.page_changed.emit(page)
    
    def set_total_pages(self, total_pages):
        """设置总页数"""
        if total_pages < 1:
            total_pages = 1
        self.total_pages = total_pages
        if self.current_page > total_pages:
            self.current_page = total_pages
        self.update_buttons()
    
    def update_buttons(self):
        """更新按钮状态"""
        # 更新按钮启用状态
        self.first_button.setEnabled(self.current_page > 1)
        self.prev_button.setEnabled(self.current_page > 1)
        self.next_button.setEnabled(self.current_page < self.total_pages)
        self.last_button.setEnabled(self.current_page < self.total_pages)
        
        # 更新页码信息
        self.page_info.setText(f"第 {self.current_page} 页 / 共 {self.total_pages} 页")
        
        # 更新页码按钮
        self.update_page_buttons()
    
    def update_page_buttons(self):
        """更新页码按钮"""
        # 清空现有按钮
        for i in reversed(range(self.pages_layout.count())):
            widget = self.pages_layout.itemAt(i).widget()
            if widget:
                widget.deleteLater()
        
        # 计算显示的页码范围
        start_page = max(1, self.current_page - self.max_visible_pages // 2)
        end_page = min(self.total_pages, start_page + self.max_visible_pages - 1)
        
        # 调整起始页码，确保显示足够数量的页码
        if end_page - start_page + 1 < self.max_visible_pages:
            start_page = max(1, end_page - self.max_visible_pages + 1)
        
        # 按顺序添加页码按钮
        for page in range(start_page, end_page + 1):
            button = QPushButton(str(page))
            button.setFixedWidth(30)
            button.setFixedHeight(25)
            if page == self.current_page:
                button.setStyleSheet("background-color: #4a90e2; color: white; border: 1px solid #357abd; border-radius: 3px;")
            else:
                button.setStyleSheet("background-color: #f0f0f0; color: #333; border: 1px solid #ddd; border-radius: 3px;")
            button.clicked.connect(lambda checked, p=page: self.set_current_page(p))
            self.pages_layout.addWidget(button)
    
    def go_to_first_page(self):
        """跳转到第一页"""
        self.set_current_page(1)
    
    def go_to_prev_page(self):
        """跳转到上一页"""
        self.set_current_page(self.current_page - 1)
    
    def go_to_next_page(self):
        """跳转到下一页"""
        self.set_current_page(self.current_page + 1)
    
    def go_to_last_page(self):
        """跳转到最后一页"""
        self.set_current_page(self.total_pages)

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
    def __init__(self, url, filename, save_path=".", num_threads=4):
        super().__init__()
        self.url = url
        self.filename = filename
        self.save_path = save_path
        self.num_threads = num_threads
        self.signals = WorkerSignals()
        self.is_cancelled = False
    
    @pyqtSlot()
    def run(self):
        try:
            import requests
            import os
            import threading
            
            os.makedirs(self.save_path, exist_ok=True)
            self.full_path = os.path.join(self.save_path, self.filename)
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            response = requests.head(self.url, headers=headers, timeout=10)
            response.raise_for_status()
            
            content_length = response.headers.get('content-length')
            total_size = int(content_length) if content_length else 0
            
            # 检查服务器是否支持断点续传
            accept_ranges = response.headers.get('accept-ranges', 'none')
            can_use_range = accept_ranges.lower() == 'bytes' and total_size > 0
            
            downloaded_size = 0
            # 使用线程锁确保进度更新的线程安全
            self.progress_lock = threading.Lock()
            
            if can_use_range:
                # 多线程下载
                chunk_size = total_size // self.num_threads
                if chunk_size < 1024 * 1024:  # 小于1MB时使用单线程
                    self.num_threads = 1
                    chunk_size = total_size
                
                temp_files = []
                for i in range(self.num_threads):
                    temp_files.append(f"{self.full_path}.part{i}")
                
                ranges = []
                for i in range(self.num_threads):
                    start = i * chunk_size
                    end = start + chunk_size - 1 if i < self.num_threads - 1 else total_size - 1
                    ranges.append((start, end))
                
                def download_chunk_with_progress(index, range_tuple):
                    """带进度更新的文件块下载"""
                    start, end = range_tuple
                    headers = {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                        'Range': f'bytes={start}-{end}'
                    }
                    
                    temp_file_path = f"{self.full_path}.part{index}"
                    chunk_downloaded = 0
                    chunk_total = end - start + 1
                    
                    with requests.get(self.url, headers=headers, stream=True, timeout=30) as r:
                        r.raise_for_status()
                        with open(temp_file_path, 'wb') as f:
                            for chunk in r.iter_content(chunk_size=8192):
                                if self.is_cancelled:
                                    return {'size': 0}
                                if chunk:
                                    f.write(chunk)
                                    chunk_downloaded += len(chunk)
                                    
                                    # 更新全局进度
                                    with self.progress_lock:
                                        nonlocal downloaded_size
                                        downloaded_size += len(chunk)
                                        current_progress = (downloaded_size / total_size) * 100
                                        
                                        # 实时发送进度更新
                                        self.signals.progress.emit({
                                            'progress': current_progress,
                                            'filename': self.filename,
                                            'size': downloaded_size,
                                            'total_size': total_size
                                        })
                    
                    return {'size': chunk_downloaded}
                
                # 使用线程池下载
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor(max_workers=self.num_threads) as executor:
                    future_to_chunk = {
                        executor.submit(download_chunk_with_progress, i, ranges[i]): i 
                        for i in range(self.num_threads)
                    }
                    
                    # 等待所有任务完成
                    concurrent.futures.wait(future_to_chunk)
                    
                    if self.is_cancelled:
                        self.cleanup_temp_files(temp_files)
                        return
                
                # 合并文件
                with open(self.full_path, 'wb') as f:
                    for temp_file in temp_files:
                        with open(temp_file, 'rb') as tf:
                            f.write(tf.read())
                
                # 清理临时文件
                self.cleanup_temp_files(temp_files)
            else:
                # 单线程下载
                with requests.get(self.url, headers=headers, stream=True, timeout=30) as r:
                    r.raise_for_status()
                    with open(self.full_path, 'wb') as f:
                        for chunk in r.iter_content(chunk_size=8192):
                            if self.is_cancelled:
                                return
                            if chunk:
                                f.write(chunk)
                                downloaded_size += len(chunk)
                                progress = (downloaded_size / total_size) * 100 if total_size > 0 else 0
                                
                                self.signals.progress.emit({
                                    'progress': progress,
                                    'filename': self.filename,
                                    'size': downloaded_size,
                                    'total_size': total_size
                                })
            
            self.signals.finished.emit()
        except Exception as e:
            self.signals.error.emit(str(e))
    
    def download_chunk(self, index, range_tuple):
        """下载单个文件块"""
        import requests
        start, end = range_tuple
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Range': f'bytes={start}-{end}'
        }
        
        temp_file_path = f"{self.full_path}.part{index}"
        chunk_downloaded = 0
        
        with requests.get(self.url, headers=headers, stream=True, timeout=30) as r:
            r.raise_for_status()
            with open(temp_file_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    if self.is_cancelled:
                        return {'size': 0}
                    if chunk:
                        f.write(chunk)
                        chunk_downloaded += len(chunk)
        
        return {'size': chunk_downloaded}
    
    def cleanup_temp_files(self, temp_files):
        """清理临时文件"""
        for temp_file in temp_files:
            if os.path.exists(temp_file):
                os.remove(temp_file)
    
    def cancel(self):
        """取消下载"""
        self.is_cancelled = True



class Hanime1GUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.api = Hanime1API()
        self.threadpool = QThreadPool()
        
        # 设置默认值
        self.settings = {
            'download_mode': 'multi_thread',
            'num_threads': 4,
            'download_quality': '最高',
            'download_path': os.path.join(os.getcwd(), 'hamineDownload')
        }
        
        # 搜索筛选参数
        self.filter_params = {
            'genre': '',
            'sort': '',
            'date': '',
            'duration': '',
            'tags': [],
            'broad': False
        }
        
        self.current_search_results = []
        self.current_video_info = None
        self.downloads = []
        self.active_downloads = {}
        self.current_cover_url = ""
        
        # 先初始化UI
        self.init_ui()
        
        # 收藏夹相关
        self.favorites = []
        self.favorites_file = os.path.join(os.getcwd(), 'favorites.json')
        self.load_favorites()
        gui_logger.info("Hanime1GUI主窗口初始化完成")
    
    def init_ui(self):
        self.setWindowTitle("Hanime1视频工具")
        self.setGeometry(100, 100, 1200, 800)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setSpacing(16)
        main_layout.setContentsMargins(16, 16, 16, 16)
        
        # 左侧布局
        left_widget = QWidget()
        left_widget.setMinimumWidth(350)
        # 取消最大宽度限制，让左侧布局可以根据内容自动扩展
        left_widget.setMaximumWidth(1000)
        left_layout = QVBoxLayout(left_widget)
        left_layout.setSpacing(12)
        
        # 搜索区域
        search_title = QLabel("视频搜索")
        left_layout.addWidget(search_title)
        
        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("请输入搜索关键词...")
        self.search_input.returnPressed.connect(self.search_videos)
        search_layout.addWidget(self.search_input, 1)
        
        self.search_button = QPushButton("搜索")
        self.search_button.clicked.connect(self.search_videos)
        search_layout.addWidget(self.search_button)
        
        left_layout.addLayout(search_layout)
        
        # 页码导航
        left_layout.addWidget(QLabel("页码导航:"))
        self.page_navigation = PageNavigationWidget()
        self.page_navigation.page_changed.connect(self.on_page_changed)
        left_layout.addWidget(self.page_navigation)
        
        # 标签页
        tab_widget = QTabWidget()
        
        # 视频列表
        self.video_list = QListWidget()
        self.video_list.itemClicked.connect(self.on_video_selected)
        self.video_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.video_list.customContextMenuRequested.connect(self.show_video_context_menu)
        self.video_list.setSelectionMode(QListWidget.ExtendedSelection)
        tab_widget.addTab(self.video_list, "搜索结果")
        
        # 收藏夹列表
        self.favorites_list = QListWidget()
        self.favorites_list.itemClicked.connect(self.on_favorite_selected)
        self.favorites_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.favorites_list.customContextMenuRequested.connect(self.show_favorite_context_menu)
        self.favorites_list.setSelectionMode(QListWidget.ExtendedSelection)
        tab_widget.addTab(self.favorites_list, "收藏夹")
        
        left_layout.addWidget(tab_widget)
        
        main_layout.addWidget(left_widget)
        
        # 右侧布局
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setSpacing(16)
        
        # 视频信息区域
        info_group = QGroupBox("视频信息")
        info_layout = QVBoxLayout(info_group)
        info_layout.setSpacing(8)
        
        self.info_form = QFormLayout()
        self.info_form.setSpacing(5)
        self.info_form.setVerticalSpacing(8)
        
        # 视频信息字段
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
        
        self.info_form.addRow(QLabel("标题:"), self.title_label)
        self.info_form.addRow(QLabel("中文标题:"), self.chinese_title_label)
        self.info_form.addRow(QLabel("观看次数:"), self.views_label)
        self.info_form.addRow(QLabel("上传日期:"), self.upload_date_label)
        self.info_form.addRow(QLabel("点赞:"), self.likes_label)
        self.info_form.addRow(QLabel("标签:"), self.tags_label)
        self.info_form.addRow(QLabel("封面:"), self.view_cover_button)
        self.info_form.addRow(QLabel("描述:"), self.description_text)
        
        info_layout.addLayout(self.info_form)
        
        # 相关视频
        related_group = QGroupBox("相关视频")
        related_layout = QVBoxLayout(related_group)
        related_layout.setSpacing(5)
        
        self.related_list = QListWidget()
        self.related_list.setMinimumHeight(150)
        self.related_list.setMaximumHeight(200)
        self.related_list.itemClicked.connect(self.on_related_video_clicked)
        related_layout.addWidget(self.related_list)
        info_layout.addWidget(related_group)
        
        # 视频源链接
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
        
        # 下载管理区域
        download_group = QGroupBox("下载管理")
        download_layout = QVBoxLayout(download_group)
        download_layout.setSpacing(8)
        
        # 下载列表
        self.download_list = QListWidget()
        self.download_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.download_list.customContextMenuRequested.connect(self.show_download_context_menu)
        download_layout.addWidget(QLabel("下载队列:"))
        download_layout.addWidget(self.download_list)
        
        # 下载控制按钮
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
        
        # 下载进度
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
    
    def on_page_changed(self, page):
        """页码变化处理"""
        self.search_videos()
    
    def search_videos(self):
        """搜索视频"""
        keyword = self.search_input.text().strip()
        if not keyword:
            return
        
        page = self.page_navigation.current_page
        
        self.statusBar().showMessage(f"正在搜索: {keyword}...")
        
        worker = SearchWorker(
            api=self.api,
            query=keyword,
            page=page
        )
        
        worker.signals.result.connect(self.on_search_complete)
        worker.signals.error.connect(self.on_search_error)
        worker.signals.finished.connect(self.on_search_finished)
        
        self.threadpool.start(worker)
    
    def on_search_complete(self, search_result):
        """搜索完成回调"""
        if search_result and search_result['videos']:
            self.current_search_results = search_result['videos']
            self.video_list.clear()
            for video in search_result['videos']:
                self.video_list.addItem(f"[{video['video_id']}] {video['title']}")
            
            # 更新页码导航
            total_pages = search_result.get('total_pages', 1)
            self.page_navigation.set_total_pages(total_pages)
            
            self.statusBar().showMessage(f"搜索完成，找到 {len(search_result['videos'])} 个结果")
        else:
            self.video_list.clear()
            # 重置页码导航
            self.page_navigation.set_total_pages(1)
            self.statusBar().showMessage("未找到视频结果")
    
    def on_search_error(self, error):
        """搜索错误回调"""
        self.statusBar().showMessage(f"搜索出错: {error}")
    
    def on_search_finished(self):
        """搜索结束回调"""
        pass
    
    def on_video_selected(self, item):
        """视频选择回调"""
        index = self.video_list.row(item)
        if 0 <= index < len(self.current_search_results):
            video = self.current_search_results[index]
            self.get_video_info(video['video_id'])
    
    def get_video_info(self, video_id):
        """获取视频信息"""
        self.statusBar().showMessage(f"正在获取视频 {video_id} 的信息...")
        
        # 清空显示
        self.title_label.setText("加载中...")
        self.chinese_title_label.setText("加载中...")
        self.views_label.setText("加载中...")
        self.upload_date_label.setText("加载中...")
        self.likes_label.setText("加载中...")
        self.tags_label.setText("加载中...")
        self.description_text.setText("加载中...")
        self.current_cover_url = ""
        self.view_cover_button.setEnabled(False)
        self.related_list.clear()
        self.update_source_links([])
        
        worker = GetVideoInfoWorker(self.api, video_id)
        worker.signals.result.connect(lambda result: self.on_video_info_complete(result, video_id))
        worker.signals.error.connect(lambda error: self.on_video_info_error(error, video_id))
        worker.signals.finished.connect(self.on_video_info_finished)
        
        self.threadpool.start(worker)
    
    def on_video_info_complete(self, video_info, video_id):
        """视频信息获取完成回调"""
        if video_info:
            self.current_video_info = video_info
            
            self.title_label.setText(video_info['title'])
            self.chinese_title_label.setText(video_info['chinese_title'])
            self.views_label.setText(video_info['views'])
            self.upload_date_label.setText(video_info['upload_date'])
            self.likes_label.setText(video_info['likes'])
            self.tags_label.setText(", ".join(video_info['tags']))
            self.description_text.setText(video_info['description'])
            
            if video_info['thumbnail']:
                self.current_cover_url = video_info['thumbnail']
                self.view_cover_button.setEnabled(True)
            
            # 相关视频
            self.related_list.clear()
            for related in video_info['series']:
                related_id = related.get('video_id', '')
                title = related.get('chinese_title', related.get('title', f"视频 {related_id}"))
                self.related_list.addItem(f"[{related_id}] {title}")
            
            # 视频源链接
            self.update_source_links(video_info['video_sources'])
            
            self.statusBar().showMessage(f"视频 {video_id} 信息加载完成")
        else:
            self.statusBar().showMessage(f"无法获取视频 {video_id} 的信息")
    
    def on_video_info_error(self, error, video_id):
        """视频信息获取错误回调"""
        self.statusBar().showMessage(f"获取视频 {video_id} 信息出错: {error}")
    
    def on_video_info_finished(self):
        """视频信息获取结束回调"""
        pass
    
    def update_source_links(self, video_sources):
        """更新视频源链接显示"""
        # 清空现有链接
        for i in reversed(range(self.source_links_layout.count())):
            widget = self.source_links_layout.itemAt(i).widget()
            if widget:
                widget.deleteLater()
        
        # 添加新链接
        for source in video_sources:
            link_widget = QWidget()
            link_layout = QHBoxLayout(link_widget)
            link_layout.setContentsMargins(0, 0, 0, 0)
            
            quality_label = QLabel(f"画质: {source['quality']}")
            download_button = QPushButton("下载")
            download_button.clicked.connect(lambda checked, s=source: self.on_download_button_clicked(s))
            
            link_layout.addWidget(quality_label, 1)
            link_layout.addWidget(download_button)
            
            self.source_links_layout.addWidget(link_widget)
    
    def on_download_button_clicked(self, source):
        """下载按钮点击回调"""
        if self.current_video_info:
            self.add_to_download_queue(self.current_video_info, source)
    
    def add_to_download_queue(self, video_info, source):
        """添加到下载队列"""
        # 生成安全的文件名
        import re
        safe_title = video_info['title'][:100]
        safe_title = re.sub(r'[\\/:*?"<>|]', '_', safe_title)
        safe_title = safe_title.strip(' _')
        if not safe_title:
            safe_title = f"video_{video_info['video_id']}"
        
        filename = f"{safe_title}.mp4"
        
        download_task = {
            'video_id': video_info['video_id'],
            'title': video_info['title'],
            'url': source['url'],
            'status': 'pending',
            'progress': 0,
            'size': 0,
            'total_size': 0,
            'source': source
        }
        
        self.downloads.append(download_task)
        self.update_download_list()
        
        self.statusBar().showMessage(f"视频 {video_info['title'][:20]}... 已添加到下载队列")
    
    def update_download_list(self):
        """更新下载列表显示"""
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
        """开始下载"""
        for i, download in enumerate(self.downloads):
            if download['status'] in ['pending', 'paused']:
                self.start_download(i)
                break
    
    def start_download(self, index):
        """开始单个下载任务"""
        if 0 <= index < len(self.downloads):
            download = self.downloads[index]
            if download['status'] in ['pending', 'paused']:
                # 生成安全的文件名
                import re
                safe_title = download['title'][:100]
                safe_title = re.sub(r'[\\/:*?"<>|]', '_', safe_title)
                safe_title = safe_title.strip(' _')
                if not safe_title:
                    safe_title = f"video_{download['video_id']}"
                filename = f"{safe_title}.mp4"
                
                # 设置下载路径
                download_path = self.settings.get('download_path', os.path.join(os.getcwd(), 'hamineDownload'))
                
                # 选择线程数
                if self.settings['download_mode'] == 'multi_thread':
                    num_threads = self.settings['num_threads']
                else:
                    num_threads = 1
                
                worker = DownloadWorker(download['url'], filename, save_path=download_path, num_threads=num_threads)
                
                worker.signals.progress.connect(lambda progress_info, idx=index: self.on_download_progress(progress_info, idx))
                worker.signals.finished.connect(lambda idx=index: self.on_download_finished(idx))
                worker.signals.error.connect(lambda error, idx=index: self.on_download_error(error, idx))
                
                self.downloads[index]['status'] = 'downloading'
                self.downloads[index]['filename'] = filename
                self.update_download_list()
                
                self.active_downloads[index] = worker
                
                self.threadpool.start(worker)
                
                self.statusBar().showMessage(f"开始下载视频 {download['title'][:20]}...")
    
    def on_download_progress(self, progress_info, index):
        """下载进度回调"""
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
        """下载完成回调"""
        if 0 <= index < len(self.downloads):
            download_title = self.downloads[index]['title'][:20]
            
            if index in self.active_downloads:
                self.active_downloads.pop(index)
            
            # 从队列中移除已完成的任务
            self.downloads.pop(index)
            
            self.update_download_list()
            
            # 清空进度显示
            if not self.downloads:  # 队列为空时
                self.download_progress.setValue(0)
                self.download_info.setText("准备下载")
            
            self.statusBar().showMessage(f"视频 {download_title}... 下载完成，已移出队列")
            
            # 继续下载下一个任务
            self.on_start_download()
    
    def on_download_error(self, error, index):
        """下载错误回调"""
        if 0 <= index < len(self.downloads):
            self.downloads[index]['status'] = 'error'
            
            if index in self.active_downloads:
                self.active_downloads.pop(index)
            
            self.update_download_list()
            
            self.statusBar().showMessage(f"视频 {self.downloads[index]['title'][:20]}... 下载出错: {error}")
    
    def on_pause_download(self):
        """暂停下载"""
        for index, worker in self.active_downloads.items():
            worker.cancel()
            self.downloads[index]['status'] = 'paused'
            self.update_download_list()
            self.statusBar().showMessage(f"已暂停下载视频 {self.downloads[index]['title'][:20]}...")
            break
    
    def on_cancel_download(self):
        """取消下载"""
        for index, worker in self.active_downloads.items():
            worker.cancel()
            self.downloads[index]['status'] = 'cancelled'
            self.active_downloads.pop(index)
            self.update_download_list()
            self.statusBar().showMessage(f"已取消下载视频 {self.downloads[index]['title'][:20]}...")
            break
    
    def on_clear_download_list(self):
        """清空下载列表"""
        for worker in self.active_downloads.values():
            worker.cancel()
        
        self.downloads.clear()
        self.active_downloads.clear()
        self.update_download_list()
        self.download_progress.setValue(0)
        self.download_info.setText("准备下载")
        
        self.statusBar().showMessage("已清空下载列表")
    
    def show_cover(self):
        """显示封面"""
        if self.current_cover_url:
            try:
                from PyQt5.QtWidgets import QDialog, QVBoxLayout
                from PyQt5.QtGui import QPixmap
                import requests
                
                dialog = QDialog(self)
                dialog.setWindowTitle("视频封面")
                dialog.setGeometry(100, 100, 800, 600)
                
                layout = QVBoxLayout(dialog)
                
                cover_label = QLabel()
                cover_label.setAlignment(Qt.AlignCenter)
                
                response = requests.get(self.current_cover_url, timeout=10)
                response.raise_for_status()
                
                pixmap = QPixmap()
                pixmap.loadFromData(response.content)
                
                scaled_pixmap = pixmap.scaled(780, 540, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                cover_label.setPixmap(scaled_pixmap)
                
                layout.addWidget(cover_label)
                
                dialog.exec_()
            except Exception as e:
                self.statusBar().showMessage(f"显示封面失败: {str(e)}")
        else:
            self.statusBar().showMessage("没有可用的封面")
    
    def on_related_video_clicked(self, item):
        """相关视频点击回调"""
        text = item.text()
        import re
        match = re.search(r'\[(\d+)\]', text)
        if match:
            video_id = match.group(1)
            self.get_video_info(video_id)
    
    def show_video_context_menu(self, position):
        """视频列表右键菜单"""
        selected_items = self.video_list.selectedItems()
        if not selected_items:
            return
        
        menu = QMenu()
        
        # 下载选项
        download_action = QAction("下载", self)
        download_action.triggered.connect(lambda: self.on_download_from_menu(selected_items))
        menu.addAction(download_action)
        
        menu.exec_(self.video_list.viewport().mapToGlobal(position))
    
    def on_download_from_menu(self, items):
        """从菜单下载"""
        for item in items:
            text = item.text()
            import re
            match = re.search(r'\[(\d+)\]', text)
            if match:
                video_id = match.group(1)
                # 先获取视频信息，然后添加到下载队列
                worker = GetVideoInfoWorker(self.api, video_id)
                worker.signals.result.connect(self.on_video_info_for_download)
                self.threadpool.start(worker)
    
    def on_video_info_for_download(self, video_info):
        """为下载获取视频信息完成"""
        if video_info and video_info['video_sources']:
            # 选择第一个视频源
            source = video_info['video_sources'][0]
            self.add_to_download_queue(video_info, source)
    
    def load_favorites(self):
        """加载收藏夹"""
        if os.path.exists(self.favorites_file):
            try:
                with open(self.favorites_file, 'r', encoding='utf-8') as f:
                    import json
                    self.favorites = json.load(f)
                self.update_favorites_list()
            except Exception as e:
                self.favorites = []
    
    def save_favorites(self):
        """保存收藏夹"""
        try:
            with open(self.favorites_file, 'w', encoding='utf-8') as f:
                import json
                json.dump(self.favorites, f, ensure_ascii=False, indent=2)
        except Exception as e:
            pass
    
    def update_favorites_list(self):
        """更新收藏夹列表显示"""
        self.favorites_list.clear()
        for favorite in self.favorites:
            self.favorites_list.addItem(f"[{favorite['video_id']}] {favorite['title']}")
    
    def add_to_favorites(self, video_info):
        """添加到收藏夹"""
        # 检查是否已在收藏夹中
        for favorite in self.favorites:
            if favorite['video_id'] == video_info['video_id']:
                return  # 已存在，不重复添加
        
        # 添加到收藏夹
        favorite_item = {
            'video_id': video_info['video_id'],
            'title': video_info['title'],
            'chinese_title': video_info.get('chinese_title', ''),
            'thumbnail': video_info.get('thumbnail', ''),
            'url': video_info['url']
        }
        
        self.favorites.append(favorite_item)
        self.save_favorites()
        self.update_favorites_list()
        self.statusBar().showMessage(f"视频 '{video_info['title'][:20]}...' 已添加到收藏夹")
    
    def remove_from_favorites(self, video_id):
        """从收藏夹移除"""
        self.favorites = [fav for fav in self.favorites if fav['video_id'] != video_id]
        self.save_favorites()
        self.update_favorites_list()
    
    def show_video_context_menu(self, position):
        """视频列表右键菜单"""
        selected_items = self.video_list.selectedItems()
        if not selected_items:
            return
        
        menu = QMenu()
        
        # 下载选项
        download_action = QAction("下载", self)
        download_action.triggered.connect(lambda: self.on_download_from_menu(selected_items))
        menu.addAction(download_action)
        
        # 添加到收藏夹选项
        add_favorite_action = QAction("添加到收藏夹", self)
        add_favorite_action.triggered.connect(lambda: self.on_add_to_favorites_from_menu(selected_items))
        menu.addAction(add_favorite_action)
        
        menu.exec_(self.video_list.viewport().mapToGlobal(position))
    
    def on_add_to_favorites_from_menu(self, items):
        """从菜单添加到收藏夹"""
        for item in items:
            text = item.text()
            import re
            match = re.search(r'\[(\d+)]\s*(.+)', text)
            if match:
                video_id = match.group(1)
                title = match.group(2)
                
                # 直接添加到收藏夹，不获取完整视频信息
                favorite_item = {
                    'video_id': video_id,
                    'title': title,
                    'chinese_title': '',
                    'thumbnail': '',
                    'url': f"https://hanime1.me/watch?v={video_id}"
                }
                
                # 检查是否已在收藏夹中
                already_exists = any(fav['video_id'] == video_id for fav in self.favorites)
                if not already_exists:
                    self.favorites.append(favorite_item)
                    self.save_favorites()
                    self.update_favorites_list()
                    self.statusBar().showMessage(f"视频 '{title[:20]}...' 已添加到收藏夹")
                else:
                    self.statusBar().showMessage(f"视频 '{title[:20]}...' 已在收藏夹中")
    
    def show_favorite_context_menu(self, position):
        """收藏夹右键菜单"""
        selected_items = self.favorites_list.selectedItems()
        if not selected_items:
            return
        
        menu = QMenu()
        
        # 播放/查看信息选项
        view_action = QAction("查看视频信息", self)
        view_action.triggered.connect(lambda: self.on_view_favorite_info(selected_items))
        menu.addAction(view_action)
        
        # 下载选项
        download_action = QAction("下载", self)
        download_action.triggered.connect(lambda: self.on_download_favorite(selected_items))
        menu.addAction(download_action)
        
        # 从收藏夹移除选项
        remove_action = QAction("从收藏夹移除", self)
        remove_action.triggered.connect(lambda: self.on_remove_from_favorites(selected_items))
        menu.addAction(remove_action)
        
        menu.exec_(self.favorites_list.viewport().mapToGlobal(position))
    
    def on_remove_from_favorites(self, items):
        """从收藏夹移除"""
        for item in items:
            text = item.text()
            import re
            match = re.search(r'\[(\d+)]', text)
            if match:
                video_id = match.group(1)
                self.remove_from_favorites(video_id)
                self.statusBar().showMessage(f"视频已从收藏夹移除")
    
    def on_view_favorite_info(self, items):
        """查看收藏夹视频信息"""
        for item in items:
            text = item.text()
            import re
            match = re.search(r'\[(\d+)]', text)
            if match:
                video_id = match.group(1)
                self.get_video_info(video_id)
                break
    
    def on_download_favorite(self, items):
        """下载收藏夹视频"""
        for item in items:
            text = item.text()
            import re
            match = re.search(r'\[(\d+)]', text)
            if match:
                video_id = match.group(1)
                # 先获取视频信息，然后添加到下载队列
                worker = GetVideoInfoWorker(self.api, video_id)
                worker.signals.result.connect(self.on_video_info_for_download)
                self.threadpool.start(worker)
    
    def on_favorite_selected(self, item):
        """收藏夹视频选择"""
        text = item.text()
        import re
        match = re.search(r'\[(\d+)]', text)
        if match:
            video_id = match.group(1)
            self.get_video_info(video_id)
    
    def show_download_context_menu(self, position):
        """下载列表右键菜单"""
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
        """从菜单开始下载"""
        index = self.download_list.row(item)
        self.start_download(index)
    
    def on_pause_download_from_menu(self, item):
        """从菜单暂停下载"""
        index = self.download_list.row(item)
        if 0 <= index < len(self.downloads) and index in self.active_downloads:
            self.active_downloads[index].cancel()
            self.downloads[index]['status'] = 'paused'
            self.update_download_list()
            self.statusBar().showMessage(f"已暂停下载视频 {self.downloads[index]['title'][:20]}...")
    
    def on_cancel_download_from_menu(self, item):
        """从菜单取消下载"""
        index = self.download_list.row(item)
        if 0 <= index < len(self.downloads) and index in self.active_downloads:
            self.active_downloads[index].cancel()
            self.downloads[index]['status'] = 'cancelled'
            self.active_downloads.pop(index)
            self.update_download_list()
            self.statusBar().showMessage(f"已取消下载视频 {self.downloads[index]['title'][:20]}...")
    
    def on_remove_from_download_queue(self, item):
        """从队列中移除"""
        index = self.download_list.row(item)
        if 0 <= index < len(self.downloads):
            if index in self.active_downloads:
                self.active_downloads[index].cancel()
                self.active_downloads.pop(index)
            del self.downloads[index]
            self.update_download_list()

def main():
    app = QApplication(sys.argv)
    window = Hanime1GUI()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
