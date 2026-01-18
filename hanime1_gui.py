import sys
import os
import json
import re
import threading
import time
import concurrent.futures
import webbrowser
import datetime
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QListWidget,
    QLabel, QPushButton, QLineEdit, QSpinBox, QProgressBar, QTextEdit,
    QGroupBox, QFormLayout, QTabWidget, QMenu, QAction, QDialog,
    QSizePolicy, QRadioButton, QFileDialog, QComboBox, QCheckBox, QMessageBox, QInputDialog
)
from PyQt5.QtCore import Qt, QObject, pyqtSignal, QRunnable, QThreadPool, pyqtSlot
from PyQt5.QtGui import QPixmap
import requests



from hanime1_api import Hanime1API



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

class SettingsDialog(QDialog):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings.copy()
        # 设置默认值
        self.default_settings = {
            'download_mode': 'multi_thread',
            'num_threads': 4,
            'max_simultaneous_downloads': 2,  # 最大同时下载数
            'download_quality': '最高',
            'download_path': os.path.join(os.getcwd(), 'hanimeDownload'),
            'file_naming_rule': '{title}',  # 文件名命名规则
            'overwrite_existing': False,  # 是否覆盖已存在的文件
            'cloudflare_cookie': ''  # Cloudflare Cookie
        }
        # 合并默认设置
        for key, value in self.default_settings.items():
            if key not in self.settings:
                self.settings[key] = value
        self.parent = parent
        self.init_ui()
    
    def init_ui(self):
        self.setWindowTitle("设置")
        self.setGeometry(300, 300, 450, 550)
        
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(16)
        main_layout.setContentsMargins(16, 16, 16, 16)
        
        # 下载方式
        download_mode_group = QGroupBox("下载方式")
        download_mode_layout = QVBoxLayout(download_mode_group)
        
        self.multi_thread_radio = QRadioButton("多线程下载")
        self.single_thread_radio = QRadioButton("单线程下载")
        
        if self.settings['download_mode'] == 'multi_thread':
            self.multi_thread_radio.setChecked(True)
        else:
            self.single_thread_radio.setChecked(True)
        
        download_mode_layout.addWidget(self.multi_thread_radio)
        download_mode_layout.addWidget(self.single_thread_radio)
        main_layout.addWidget(download_mode_group)
        
        # 线程数设置
        thread_count_group = QGroupBox("线程数设置")
        thread_count_layout = QVBoxLayout(thread_count_group)
        
        thread_count_form = QFormLayout()
        self.thread_spinbox = QSpinBox()
        self.thread_spinbox.setMinimum(1)
        self.thread_spinbox.setMaximum(16)
        self.thread_spinbox.setValue(self.settings['num_threads'])
        thread_count_form.addRow("线程数量:", self.thread_spinbox)
        thread_count_layout.addLayout(thread_count_form)
        main_layout.addWidget(thread_count_group)
        
        # 最大同时下载数设置
        max_downloads_group = QGroupBox("同时下载设置")
        max_downloads_layout = QVBoxLayout(max_downloads_group)
        
        max_downloads_form = QFormLayout()
        self.max_downloads_spinbox = QSpinBox()
        self.max_downloads_spinbox.setMinimum(1)
        self.max_downloads_spinbox.setMaximum(8)
        self.max_downloads_spinbox.setValue(self.settings['max_simultaneous_downloads'])
        max_downloads_form.addRow("最大同时下载数:", self.max_downloads_spinbox)
        max_downloads_layout.addLayout(max_downloads_form)
        main_layout.addWidget(max_downloads_group)
        
        # 批量下载画质
        quality_group = QGroupBox("批量下载画质")
        quality_layout = QVBoxLayout(quality_group)
        
        self.highest_quality_radio = QRadioButton("最高")
        self.lowest_quality_radio = QRadioButton("最低")
        
        if self.settings['download_quality'] == '最高':
            self.highest_quality_radio.setChecked(True)
        else:
            self.lowest_quality_radio.setChecked(True)
        
        quality_layout.addWidget(self.highest_quality_radio)
        quality_layout.addWidget(self.lowest_quality_radio)
        main_layout.addWidget(quality_group)
        
        # 下载位置
        download_path_group = QGroupBox("下载位置")
        download_path_layout = QVBoxLayout(download_path_group)
        
        path_layout = QHBoxLayout()
        self.path_edit = QLineEdit(self.settings['download_path'])
        self.browse_button = QPushButton("浏览...")
        self.browse_button.clicked.connect(self.browse_path)
        
        path_layout.addWidget(self.path_edit, 1)
        path_layout.addWidget(self.browse_button)
        download_path_layout.addLayout(path_layout)
        main_layout.addWidget(download_path_group)
        
        # 文件命名规则
        naming_rule_group = QGroupBox("文件命名规则")
        naming_rule_layout = QVBoxLayout(naming_rule_group)
        
        naming_form = QFormLayout()
        
        self.naming_rule_combo = QComboBox()
        self.naming_rule_combo.addItem("仅标题", "{title}")
        self.naming_rule_combo.addItem("[视频ID]标题", "[{video_id}] {title}")
        
        # 设置当前选中的命名规则
        current_rule = self.settings['file_naming_rule']
        index = self.naming_rule_combo.findData(current_rule)
        if index != -1:
            self.naming_rule_combo.setCurrentIndex(index)
        
        naming_form.addRow("命名规则:", self.naming_rule_combo)
        
        # 命名规则说明
        rule_desc = QLabel("可用变量: {title} (视频标题), {video_id} (视频ID)")
        rule_desc.setWordWrap(True)
        naming_rule_layout.addLayout(naming_form)
        naming_rule_layout.addWidget(rule_desc)
        main_layout.addWidget(naming_rule_group)
        
        # 文件覆盖选项
        overwrite_group = QGroupBox("文件覆盖选项")
        overwrite_layout = QVBoxLayout(overwrite_group)
        
        self.overwrite_checkbox = QCheckBox("覆盖已存在的文件")
        self.overwrite_checkbox.setChecked(self.settings['overwrite_existing'])
        overwrite_layout.addWidget(self.overwrite_checkbox)
        main_layout.addWidget(overwrite_group)
        
        # Cloudflare Cookie设置
        cloudflare_group = QGroupBox("Cloudflare Cookie设置")
        cloudflare_layout = QVBoxLayout(cloudflare_group)
        
        cloudflare_form = QFormLayout()
        
        # Cloudflare Cookie输入框
        self.cloudflare_cookie_edit = QTextEdit()
        self.cloudflare_cookie_edit.setFixedHeight(100)
        self.cloudflare_cookie_edit.setPlaceholderText("输入Cloudflare Cookie，格式为：cf_clearance=value")
        self.cloudflare_cookie_edit.setPlainText(self.settings['cloudflare_cookie'])
        cloudflare_form.addRow("Cloudflare Cookie:", self.cloudflare_cookie_edit)
        
        # Cookie操作按钮
        cookie_button_layout = QHBoxLayout()
        self.clear_cookie_button = QPushButton("清除Cookie")
        self.clear_cookie_button.clicked.connect(self.clear_cookie)
        
        cookie_button_layout.addWidget(self.clear_cookie_button)
        
        # Cookie说明
        cookie_desc = QLabel("说明：当获取视频失败时，可手动输入从浏览器获取的cf_clearance Cookie")
        cookie_desc.setWordWrap(True)
        
        cloudflare_layout.addLayout(cloudflare_form)
        cloudflare_layout.addLayout(cookie_button_layout)
        cloudflare_layout.addWidget(cookie_desc)
        main_layout.addWidget(cloudflare_group)
        
        # 按钮组
        button_layout = QHBoxLayout()
        self.save_button = QPushButton("保存")
        self.save_button.clicked.connect(self.accept)
        
        self.cancel_button = QPushButton("取消")
        self.cancel_button.clicked.connect(self.reject)
        
        button_layout.addStretch(1)
        button_layout.addWidget(self.save_button)
        button_layout.addWidget(self.cancel_button)
        main_layout.addLayout(button_layout)
    

    
    

    
    def browse_path(self):
        path = QFileDialog.getExistingDirectory(self, "选择下载路径", self.settings['download_path'])
        if path:
            self.path_edit.setText(path)
    
    def clear_cookie(self):
        """清除Cloudflare Cookie"""
        # 清除UI中的Cookie
        self.cloudflare_cookie_edit.clear()
        # 更新当前对话框的设置
        self.settings['cloudflare_cookie'] = ''
        
        if hasattr(self.parent, 'api'):
            # 清除API实例中的Cookie
            self.parent.api.session.cookies.clear()
            
            # 更新主程序的settings
            self.parent.settings['cloudflare_cookie'] = ''
            
            # 从settings.json中移除session信息和cloudflare_cookie
            if os.path.exists('settings.json'):
                with open('settings.json', 'r', encoding='utf-8') as f:
                    settings = json.load(f)
                
                if 'session' in settings:
                    del settings['session']
                if 'cloudflare_cookie' in settings:
                    del settings['cloudflare_cookie']
                
                # 保存更新后的settings
                with open('settings.json', 'w', encoding='utf-8') as f:
                    json.dump(settings, f, ensure_ascii=False, indent=2)
                
                # 保存主程序的设置
                self.parent.save_settings()
            
            QMessageBox.information(self, "成功", "Cookie已清除")
    

    

    
    def accept(self):
        """重写accept方法，在保存设置时同时保存Cookie到会话"""
        # 保存Cookie到会话（如果有输入）
        cookie_text = self.cloudflare_cookie_edit.toPlainText().strip()
        if cookie_text:
            try:
                if hasattr(self.parent, 'api'):
                    # 清除现有Cookie
                    self.parent.api.session.cookies.clear()
                    
                    # 添加新Cookie
                    if cookie_text.startswith('cf_clearance='):
                        # 直接是cf_clearance=value格式
                        cf_clearance = cookie_text.split('=', 1)[1]
                        self.parent.api.session.cookies.set('cf_clearance', cf_clearance, domain='.hanime1.me', path='/')
                    else:
                        # 尝试解析完整的Cookie字符串
                        cookies = cookie_text.split(';')
                        for cookie in cookies:
                            cookie = cookie.strip()
                            if '=' in cookie:
                                name, value = cookie.split('=', 1)
                                # 为所有Cookie设置正确的domain和path
                                self.parent.api.session.cookies.set(name, value, domain='.hanime1.me', path='/')
                    
                    # 保存会话
                    self.parent.api.save_session()
            except Exception as e:
                QMessageBox.critical(self, "错误", f"保存Cookie失败: {str(e)}")
                return
        
        super().accept()
    
    def get_settings(self):
        self.settings['download_mode'] = 'multi_thread' if self.multi_thread_radio.isChecked() else 'single_thread'
        self.settings['num_threads'] = self.thread_spinbox.value()
        self.settings['max_simultaneous_downloads'] = self.max_downloads_spinbox.value()
        self.settings['download_quality'] = '最高' if self.highest_quality_radio.isChecked() else '最低'
        self.settings['download_path'] = self.path_edit.text()
        self.settings['file_naming_rule'] = self.naming_rule_combo.currentData()
        self.settings['overwrite_existing'] = self.overwrite_checkbox.isChecked()
        self.settings['cloudflare_cookie'] = self.cloudflare_cookie_edit.toPlainText().strip()
        return self.settings





class DownloadWorker(QRunnable):
    """下载工作线程，支持多线程和断点续传"""
    
    # 常量定义
    USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    CHUNK_SIZE = 131072  # 下载块大小从8KB增加到128KB，减少I/O操作次数
    MIN_CHUNK_SIZE = 1024 * 1024  # 最小块大小(1MB)，小于此值使用单线程
    
    def __init__(self, url, filename, save_path=".", num_threads=4):
        """初始化下载工作线程
        
        Args:
            url: 下载链接
            filename: 保存文件名
            save_path: 保存路径
            num_threads: 线程数量
        """
        super().__init__()
        self.url = url
        self.filename = filename
        self.save_path = save_path
        self.num_threads = num_threads
        self.signals = WorkerSignals()
        self.is_cancelled = False
        self.is_paused = False
        self.progress_lock = None
        self.pause_event = threading.Event()
        self.pause_event.set()  # 默认不暂停
        
        # 进度更新节流机制
        self.last_progress_update = 0  # 上次更新时间
        self.last_progress_value = 0  # 上次更新进度值
        self.progress_update_interval = 0.1  # 更新间隔（秒）
        self.progress_update_threshold = 1.0  # 进度变化阈值（百分比）
        
        # 下载速度计算
        self.start_time = time.time()
        self.last_speed_update = 0
        self.last_downloaded_size = 0
        self.current_speed = 0  # 当前下载速度（字节/秒）
    
    @pyqtSlot()
    def run(self):
        """执行下载任务"""
        try:
            # 创建保存目录
            os.makedirs(self.save_path, exist_ok=True)
            self.full_path = os.path.join(self.save_path, self.filename)
            
            # 获取文件信息
            file_info = self._get_file_info()
            if not file_info:
                return
            
            file_total_size, supports_range_requests = file_info
            self.progress_lock = threading.Lock()
            downloaded_size = 0
            
            # 根据服务器支持情况选择下载方式
            if supports_range_requests and file_total_size > 0:
                self._download_with_multithreading(file_total_size)
            else:
                self._download_with_singlethread(file_total_size, downloaded_size)
            
            # 发送最终进度更新，确保进度条显示100%
            self.signals.progress.emit({
                'progress': 100,
                'filename': self.filename,
                'size': file_total_size,
                'total_size': file_total_size
            })
            
            self.signals.finished.emit()
        except Exception as e:
            self.signals.error.emit(str(e))
    
    def _get_file_info(self):
        """获取文件信息
        
        Returns:
            tuple: (文件总大小, 是否支持断点续传)
        """
        headers = {
            'User-Agent': self.USER_AGENT
        }
        
        response = requests.head(self.url, headers=headers, timeout=10)
        response.raise_for_status()
        
        content_length = response.headers.get('content-length')
        file_total_size = int(content_length) if content_length else 0
        
        # 检查服务器是否支持断点续传
        accept_ranges = response.headers.get('accept-ranges', 'none')
        supports_range_requests = accept_ranges.lower() == 'bytes' and file_total_size > 0
        
        return file_total_size, supports_range_requests
    
    def _download_with_multithreading(self, file_total_size):
        """多线程下载
        
        Args:
            file_total_size: 文件总大小
        """
        # 根据文件大小动态调整线程数，提高下载效率
        # 小文件使用较少线程，大文件使用更多线程
        if file_total_size < 10 * 1024 * 1024:  # 小于10MB
            optimal_threads = min(self.num_threads, 2)
        elif file_total_size < 50 * 1024 * 1024:  # 10MB-50MB
            optimal_threads = min(self.num_threads, 4)
        elif file_total_size < 200 * 1024 * 1024:  # 50MB-200MB
            optimal_threads = min(self.num_threads, 8)
        else:  # 大于200MB
            optimal_threads = min(self.num_threads, 16)
        
        # 计算分块大小
        chunk_size = file_total_size // optimal_threads
        if chunk_size < self.MIN_CHUNK_SIZE:
            optimal_threads = 1
            chunk_size = file_total_size
        
        # 使用动态调整后的线程数
        self.num_threads = optimal_threads
        
        # 准备临时文件和下载范围
        temp_files = [f"{self.full_path}.part{i}" for i in range(self.num_threads)]
        ranges = []
        for i in range(self.num_threads):
            start = i * chunk_size
            end = start + chunk_size - 1 if i < self.num_threads - 1 else file_total_size - 1
            ranges.append((start, end))
        
        # 使用可变对象存储已下载大小，以便线程间共享
        downloaded_size_container = [0]  # 使用列表作为容器，实现引用传递
        
        # 使用线程池下载
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.num_threads) as executor:
            future_to_chunk = {
                executor.submit(self._download_chunk, i, range_tuple, file_total_size, downloaded_size_container): i 
                for i, range_tuple in enumerate(ranges)
            }
            
            # 等待所有任务完成
            concurrent.futures.wait(future_to_chunk)
            
            if self.is_cancelled:
                self._cleanup_temp_files(temp_files)
                return
        
        # 合并文件
        self._merge_files(temp_files)
        
        # 清理临时文件
        self._cleanup_temp_files(temp_files)
    
    def _download_with_singlethread(self, file_total_size, downloaded_size):
        """单线程下载
        
        Args:
            file_total_size: 文件总大小
            downloaded_size: 已下载大小
        """
        headers = {
            'User-Agent': self.USER_AGENT
        }
        
        with requests.get(self.url, headers=headers, stream=True, timeout=30) as r:
            r.raise_for_status()
            with open(self.full_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=self.CHUNK_SIZE):
                    if self.is_cancelled:
                        return
                    # 检查是否暂停
                    self.pause_event.wait()  # 阻塞直到继续信号
                    if chunk:
                        f.write(chunk)
                        downloaded_size += len(chunk)
                        progress = (downloaded_size / file_total_size) * 100 if file_total_size > 0 else 0
                        
                        # 计算下载速度
                        current_time = time.time()
                        time_diff = current_time - self.last_speed_update
                        if time_diff >= 1.0:  # 每秒更新一次速度
                            bytes_diff = downloaded_size - self.last_downloaded_size
                            self.current_speed = bytes_diff / time_diff
                            self.last_speed_update = current_time
                            self.last_downloaded_size = downloaded_size
                        
                        # 使用节流机制更新进度
                        if self._should_update_progress(progress):
                            self.signals.progress.emit({
                                'progress': progress,
                                'filename': self.filename,
                                'size': downloaded_size,
                                'total_size': file_total_size,
                                'speed': self.current_speed  # 添加下载速度信息
                            })
    
    def _download_chunk(self, index, range_tuple, file_total_size, downloaded_size_container):
        """下载单个文件块
        
        Args:
            index: 块索引
            range_tuple: 下载范围 (start, end)
            file_total_size: 文件总大小
            downloaded_size_container: 已下载大小的容器（列表，用于线程间共享）
            
        Returns:
            dict: 下载结果 {'size': 下载大小}
        """
        start, end = range_tuple
        headers = {
            'User-Agent': self.USER_AGENT,
            'Range': f'bytes={start}-{end}'
        }
        
        temp_file_path = f"{self.full_path}.part{index}"
        downloaded_chunk_size = 0
        
        with requests.get(self.url, headers=headers, stream=True, timeout=30) as r:
            r.raise_for_status()
            with open(temp_file_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=self.CHUNK_SIZE):
                    if self.is_cancelled:
                        return {'size': 0}
                    # 检查是否暂停
                    self.pause_event.wait()  # 阻塞直到继续信号
                    if chunk:
                        f.write(chunk)
                        downloaded_chunk_size += len(chunk)
                        
                        # 更新全局进度
                        with self.progress_lock:
                            downloaded_size_container[0] += len(chunk)
                            current_progress = (downloaded_size_container[0] / file_total_size) * 100
                            
                            # 计算下载速度
                            current_time = time.time()
                            time_diff = current_time - self.last_speed_update
                            if time_diff >= 1.0:  # 每秒更新一次速度
                                bytes_diff = downloaded_size_container[0] - self.last_downloaded_size
                                self.current_speed = bytes_diff / time_diff
                                self.last_speed_update = current_time
                                self.last_downloaded_size = downloaded_size_container[0]
                            
                            # 使用节流机制更新进度
                            if self._should_update_progress(current_progress):
                                self.signals.progress.emit({
                                    'progress': current_progress,
                                    'filename': self.filename,
                                    'size': downloaded_size_container[0],
                                    'total_size': file_total_size,
                                    'speed': self.current_speed  # 添加下载速度信息
                                })
        
        return {'size': downloaded_chunk_size}
    
    def _merge_files(self, temp_files):
        """合并临时文件，优化磁盘I/O
        
        Args:
            temp_files: 临时文件列表
        """
        with open(self.full_path, 'wb') as f:
            for temp_file in temp_files:
                with open(temp_file, 'rb') as tf:
                    # 使用更大的缓冲区读取文件，减少I/O操作次数
                    while True:
                        chunk = tf.read(1024 * 1024)  # 1MB缓冲区
                        if not chunk:
                            break
                        f.write(chunk)
    
    def _cleanup_temp_files(self, temp_files):
        """清理临时文件
        
        Args:
            temp_files: 临时文件列表
        """
        for temp_file in temp_files:
            if os.path.exists(temp_file):
                os.remove(temp_file)
    
    def _should_update_progress(self, current_progress):
        """检查是否需要更新进度，实现节流机制
        
        Args:
            current_progress: 当前进度值（百分比）
            
        Returns:
            bool: 是否需要更新进度
        """
        # 计算当前时间
        current_time = time.time()
        
        # 检查时间间隔和进度变化阈值
        time_passed = current_time - self.last_progress_update
        progress_changed = abs(current_progress - self.last_progress_value) >= self.progress_update_threshold
        
        if time_passed >= self.progress_update_interval or progress_changed:
            # 更新上次更新时间和进度值
            self.last_progress_update = current_time
            self.last_progress_value = current_progress
            return True
        return False
    
    def pause(self):
        """暂停下载"""
        self.is_paused = True
        self.pause_event.clear()
    
    def resume(self):
        """恢复下载"""
        self.is_paused = False
        self.pause_event.set()
    
    def cancel(self):
        """取消下载"""
        self.is_cancelled = True
        self.pause_event.set()  # 取消时也恢复，以便线程退出



class Hanime1GUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.api = Hanime1API()
        self.threadpool = QThreadPool()
        self.threadpool.setMaxThreadCount(32)  # 设置最大线程数为32，避免过多线程切换
        
        # 初始化设置
        self.settings_file = os.path.join(os.getcwd(), 'settings.json')
        # 设置默认值
        self.default_settings = {
            'download_mode': 'multi_thread',
            'num_threads': 4,
            'max_simultaneous_downloads': 2,
            'download_quality': '最高',
            'download_path': os.path.join(os.getcwd(), 'hanimeDownload'),
            'file_naming_rule': '{title}',
            'overwrite_existing': False,
            'cloudflare_cookie': '',
            'window_size': {'width': 1320, 'height': 1485}
        }
        # 加载设置
        self.settings = self.load_settings()
        # 如果设置文件不存在，保存默认设置
        if not os.path.exists(self.settings_file):
            self.save_settings()
        
        # 应用Cloudflare Cookie到API实例
        cloudflare_cookie = self.settings.get('cloudflare_cookie', '')
        if cloudflare_cookie:
            # 清除现有Cookie
            self.api.session.cookies.clear()
            # 添加新Cookie
            if cloudflare_cookie.startswith('cf_clearance='):
                # 直接是cf_clearance=value格式
                cf_clearance = cloudflare_cookie.split('=', 1)[1]
                self.api.session.cookies.set('cf_clearance', cf_clearance, domain='.hanime1.me')
            else:
                # 尝试解析完整的Cookie字符串
                cookies = cloudflare_cookie.split(';')
                for cookie in cookies:
                    cookie = cookie.strip()
                    if '=' in cookie:
                        name, value = cookie.split('=', 1)
                        if name == 'cf_clearance':
                            self.api.session.cookies.set(name, value, domain='.hanime1.me')
            # 保存会话
            self.api.save_session()
        
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
        
        # 初始化数据结构
        self.favorites = {}
        self.current_favorite_folder = '默认收藏夹'
        self.favorites_file = os.path.join(os.getcwd(), 'favorites.json')
        
        self.download_history = []
        self.history_file = os.path.join(os.getcwd(), 'download_history.json')
        
        # 先初始化UI，创建所有组件
        self.init_ui()
        
        # 然后加载数据
        self.load_favorites()
        self.load_download_history()
        
        # 更新列表
        self.update_history_list()
    
    def init_ui(self):
        """初始化用户界面"""
        self._init_main_window()
        self._init_left_panel()
        self._init_right_panel()
        self.statusBar()
    
    def _init_main_window(self):
        """初始化主窗口"""
        self.setWindowTitle("Hanime1视频工具")
        
        # 从设置中加载窗口大小
        window_size = self.settings.get('window_size', {'width': 1320, 'height': 1485})
        width = window_size.get('width', 1320)
        height = window_size.get('height', 1485)
        self.setGeometry(100, 100, width, height)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        self.main_layout = QHBoxLayout(central_widget)
        self.main_layout.setSpacing(16)
        self.main_layout.setContentsMargins(16, 16, 16, 16)
    
    def _init_left_panel(self):
        """初始化左侧面板"""
        left_widget = QWidget()
        left_widget.setMinimumWidth(350)
        left_widget.setMaximumWidth(1000)
        left_layout = QVBoxLayout(left_widget)
        left_layout.setSpacing(12)
        
        self._init_search_area(left_layout)
        self._init_page_navigation(left_layout)
        self._init_tab_widget(left_layout)
        
        self.main_layout.addWidget(left_widget)
    
    def _init_search_area(self, parent_layout):
        """初始化搜索区域
        
        Args:
            parent_layout: 父布局
        """
        search_title = QLabel("视频搜索")
        parent_layout.addWidget(search_title)
        
        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("请输入搜索关键词...")
        self.search_input.returnPressed.connect(self.search_videos)
        search_layout.addWidget(self.search_input, 1)
        
        self.search_button = QPushButton("搜索")
        self.search_button.clicked.connect(self.search_videos)
        search_layout.addWidget(self.search_button)
        
        self.settings_button = QPushButton("设置")
        self.settings_button.clicked.connect(self.open_settings)
        search_layout.addWidget(self.settings_button)
        
        parent_layout.addLayout(search_layout)
    
    def _init_page_navigation(self, parent_layout):
        """初始化页码导航
        
        Args:
            parent_layout: 父布局
        """
        parent_layout.addWidget(QLabel("页码导航:"))
        self.page_navigation = PageNavigationWidget()
        self.page_navigation.page_changed.connect(self.on_page_changed)
        parent_layout.addWidget(self.page_navigation)
    
    def _init_tab_widget(self, parent_layout):
        """初始化标签页
        
        Args:
            parent_layout: 父布局
        """
        tab_widget = QTabWidget()
        
        # 视频列表
        self.video_list = QListWidget()
        self.video_list.itemClicked.connect(self.on_video_selected)
        self.video_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.video_list.customContextMenuRequested.connect(self.show_video_context_menu)
        self.video_list.setSelectionMode(QListWidget.ExtendedSelection)
        tab_widget.addTab(self.video_list, "搜索结果")
        
        # 收藏夹列表
        favorites_widget = QWidget()
        favorites_layout = QVBoxLayout(favorites_widget)
        
        # 收藏夹管理栏
        favorites_manage_layout = QHBoxLayout()
        
        # 收藏夹选择下拉框
        self.folder_combobox = QComboBox()
        self.folder_combobox.currentTextChanged.connect(self.on_folder_changed)
        favorites_manage_layout.addWidget(self.folder_combobox, 1)
        
        # 新建收藏夹按钮
        new_folder_button = QPushButton("新建")
        new_folder_button.clicked.connect(self.on_new_folder)
        favorites_manage_layout.addWidget(new_folder_button)
        
        # 删除收藏夹按钮
        delete_folder_button = QPushButton("删除")
        delete_folder_button.clicked.connect(self.on_delete_folder)
        favorites_manage_layout.addWidget(delete_folder_button)
        
        favorites_layout.addLayout(favorites_manage_layout)
        
        # 收藏夹搜索和操作栏
        favorites_top_layout = QHBoxLayout()
        
        # 收藏夹搜索框
        self.favorites_search_input = QLineEdit()
        self.favorites_search_input.setPlaceholderText("在收藏夹中搜索...")
        self.favorites_search_input.textChanged.connect(self.on_favorites_search)
        favorites_top_layout.addWidget(self.favorites_search_input, 1)
        
        # 收藏夹操作按钮
        export_favorites_button = QPushButton("导出")
        export_favorites_button.clicked.connect(self.on_export_favorites)
        favorites_top_layout.addWidget(export_favorites_button)
        
        import_favorites_button = QPushButton("导入")
        import_favorites_button.clicked.connect(self.on_import_favorites)
        favorites_top_layout.addWidget(import_favorites_button)
        
        # 收藏分享按钮
        share_button = QPushButton("收藏分享")
        share_button.clicked.connect(self.on_share_website)
        favorites_top_layout.addWidget(share_button)
        
        favorites_layout.addLayout(favorites_top_layout)
        
        # 收藏夹列表
        self.favorites_list = QListWidget()
        self.favorites_list.itemClicked.connect(self.on_favorite_selected)
        self.favorites_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.favorites_list.customContextMenuRequested.connect(self.show_favorite_context_menu)
        self.favorites_list.setSelectionMode(QListWidget.ExtendedSelection)
        favorites_layout.addWidget(self.favorites_list)
        
        # 刷新收藏夹列表
        self.update_folder_combobox()
        
        tab_widget.addTab(favorites_widget, "收藏夹")
        
        # 下载历史
        history_widget = QWidget()
        history_layout = QVBoxLayout(history_widget)
        
        # 历史记录操作栏
        history_top_layout = QHBoxLayout()
        
        # 刷新按钮
        refresh_button = QPushButton("刷新")
        refresh_button.clicked.connect(self.refresh_download_history)
        history_top_layout.addWidget(refresh_button)
        
        # 清空按钮
        clear_button = QPushButton("清空历史")
        clear_button.clicked.connect(self.clear_download_history)
        history_top_layout.addWidget(clear_button)
        
        history_top_layout.addStretch(1)
        
        history_layout.addLayout(history_top_layout)
        
        # 历史记录列表
        self.history_list = QListWidget()
        self.history_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.history_list.customContextMenuRequested.connect(self.show_history_context_menu)
        history_layout.addWidget(self.history_list)
        
        tab_widget.addTab(history_widget, "下载历史")
        
        parent_layout.addWidget(tab_widget)
    
    def _init_right_panel(self):
        """初始化右侧面板"""
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setSpacing(16)
        
        self._init_video_info_area(right_layout)
        self._init_download_manager_area(right_layout)
        
        self.main_layout.addWidget(right_widget)
    
    def _init_video_info_area(self, parent_layout):
        """初始化视频信息区域
        
        Args:
            parent_layout: 父布局
        """
        info_group = QGroupBox("视频信息")
        info_layout = QVBoxLayout(info_group)
        info_layout.setSpacing(8)
        
        self._init_video_info_form(info_layout)
        self._init_related_videos(info_layout)
        self._init_source_links(info_layout)
        
        parent_layout.addWidget(info_group)
    
    def _init_video_info_form(self, parent_layout):
        """初始化视频信息表单
        
        Args:
            parent_layout: 父布局
        """
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
        
        parent_layout.addLayout(self.info_form)
    
    def _init_related_videos(self, parent_layout):
        """初始化相关视频
        
        Args:
            parent_layout: 父布局
        """
        related_group = QGroupBox("相关视频")
        related_layout = QVBoxLayout(related_group)
        related_layout.setSpacing(5)
        
        self.related_list = QListWidget()
        self.related_list.setMinimumHeight(150)
        self.related_list.setMaximumHeight(200)
        self.related_list.itemClicked.connect(self.on_related_video_clicked)
        related_layout.addWidget(self.related_list)
        parent_layout.addWidget(related_group)
    
    def _init_source_links(self, parent_layout):
        """初始化视频源链接
        
        Args:
            parent_layout: 父布局
        """
        source_links_title = QLabel("当前视频源链接:")
        parent_layout.addWidget(source_links_title)
        
        self.source_links_widget = QWidget()
        self.source_links_widget.setMinimumHeight(150)
        self.source_links_widget.setMaximumHeight(250)
        self.source_links_layout = QVBoxLayout(self.source_links_widget)
        self.source_links_layout.setSpacing(8)
        self.source_links_layout.setContentsMargins(10, 5, 10, 5)
        parent_layout.addWidget(self.source_links_widget)
    
    def _init_download_manager_area(self, parent_layout):
        """初始化下载管理区域
        
        Args:
            parent_layout: 父布局
        """
        download_group = QGroupBox("下载管理")
        download_layout = QVBoxLayout(download_group)
        download_layout.setSpacing(8)
        
        self._init_download_list(download_layout)
        self._init_download_controls(download_layout)
        self._init_download_progress(download_layout)
        
        parent_layout.addWidget(download_group)
    
    def _init_download_list(self, parent_layout):
        """初始化下载列表
        
        Args:
            parent_layout: 父布局
        """
        # 创建下载列表容器
        list_container = QWidget()
        list_layout = QVBoxLayout(list_container)
        
        # 下载队列标题
        list_layout.addWidget(QLabel("下载队列:"))
        
        # 下载列表和优先级按钮
        list_with_buttons_layout = QHBoxLayout()
        
        # 下载列表
        self.download_list = QListWidget()
        self.download_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.download_list.customContextMenuRequested.connect(self.show_download_context_menu)
        list_with_buttons_layout.addWidget(self.download_list, 1)
        
        # 优先级调整按钮
        priority_buttons_widget = QWidget()
        priority_buttons_layout = QVBoxLayout(priority_buttons_widget)
        priority_buttons_layout.setSpacing(5)
        
        self.move_up_button = QPushButton("上移")
        self.move_up_button.setFixedWidth(60)
        self.move_up_button.clicked.connect(self.on_move_up)
        priority_buttons_layout.addWidget(self.move_up_button)
        
        self.move_down_button = QPushButton("下移")
        self.move_down_button.setFixedWidth(60)
        self.move_down_button.clicked.connect(self.on_move_down)
        priority_buttons_layout.addWidget(self.move_down_button)
        
        priority_buttons_layout.addStretch()
        
        list_with_buttons_layout.addWidget(priority_buttons_widget)
        
        list_layout.addLayout(list_with_buttons_layout)
        
        parent_layout.addWidget(list_container)
    
    def _init_download_controls(self, parent_layout):
        """初始化下载控制按钮
        
        Args:
            parent_layout: 父布局
        """
        download_control_layout = QHBoxLayout()
        download_control_layout.setSpacing(5)
        
        self.start_download_button = QPushButton("开始下载")
        self.start_download_button.clicked.connect(self.on_start_download)
        
        self.pause_download_button = QPushButton("暂停下载")
        self.pause_download_button.clicked.connect(self.on_pause_download)
        
        self.resume_download_button = QPushButton("恢复下载")
        self.resume_download_button.clicked.connect(self.on_resume_download)
        
        self.cancel_download_button = QPushButton("取消下载")
        self.cancel_download_button.clicked.connect(self.on_cancel_download)
        
        self.clear_download_button = QPushButton("清空列表")
        self.clear_download_button.clicked.connect(self.on_clear_download_list)
        
        download_control_layout.addWidget(self.start_download_button)
        download_control_layout.addWidget(self.pause_download_button)
        download_control_layout.addWidget(self.resume_download_button)
        download_control_layout.addWidget(self.cancel_download_button)
        download_control_layout.addWidget(self.clear_download_button)
        
        parent_layout.addLayout(download_control_layout)
    
    def _init_download_progress(self, parent_layout):
        """初始化下载进度显示
        
        Args:
            parent_layout: 父布局
        """
        progress_layout = QVBoxLayout()
        progress_layout.setSpacing(5)
        
        self.download_progress = QProgressBar()
        self.download_progress.setValue(0)
        
        self.download_info = QLabel("准备下载")
        
        progress_layout.addWidget(QLabel("下载进度:"))
        progress_layout.addWidget(self.download_progress)
        progress_layout.addWidget(self.download_info)
        
        parent_layout.addLayout(progress_layout)
    
    def on_page_changed(self, page):
        """页码变化处理"""
        self.search_videos()
    
    def search_videos(self):
        """根据关键词搜索视频"""
        keyword = self.search_input.text().strip()
        if not keyword:
            return
        
        # 检查是否是hanime1视频链接
        video_link_pattern = r'https?://hanime1\.me/watch\?v=(\d+)'  # 匹配视频ID
        match = re.search(video_link_pattern, keyword)
        
        if match:
            # 提取视频ID
            video_id = match.group(1)
            # 直接获取视频信息，不进行搜索
            self.statusBar().showMessage(f"正在获取视频 {video_id} 的信息...")
            # 清空之前的搜索结果
            self.current_search_results = []
            self.video_list.clear()
            # 获取视频信息
            self.get_video_info(video_id)
            return
        
        # 正常搜索流程
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
            current_video_index = -1
            
            for i, related in enumerate(video_info['series']):
                related_id = related.get('video_id', '')
                title = related.get('chinese_title', related.get('title', f"视频 {related_id}"))
                self.related_list.addItem(f"[{related_id}] {title}")
                
                # 检查是否是当前视频
                if related_id == video_id:
                    current_video_index = i
            
            # 处理当前视频高亮和可见性
            if current_video_index >= 0:
                # 设置当前视频项为选中状态，使用系统原生的选中样式（浅蓝色）
                self.related_list.setCurrentRow(current_video_index)
                current_item = self.related_list.item(current_video_index)
                if current_item:
                    current_item.setSelected(True)
                # 确保当前视频可见
                self.related_list.scrollToItem(self.related_list.item(current_video_index), QListWidget.PositionAtCenter)
            
            # 视频源链接
            self.update_source_links(video_info['video_sources'])
            
            # 检查是否是通过视频链接直接获取的视频信息
            if not self.current_search_results:
                # 将当前视频添加到搜索结果列表中
                self.current_search_results = [{"video_id": video_id, "title": video_info["title"]}]
                # 在视频列表中添加该视频
                self.video_list.clear()
                self.video_list.addItem(f"[{video_id}] {video_info['title']}")
            
            self.statusBar().showMessage(f"视频 {video_id} 信息加载完成")
        else:
            self.statusBar().showMessage(f"无法获取视频 {video_id} 的信息")
    
    def on_video_info_error(self, error, video_id):
        """视频信息获取错误回调"""
        self.statusBar().showMessage(f"获取视频 {video_id} 信息出错: {error}")
    
    def on_video_info_finished(self):
        """视频信息获取结束回调"""
    
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
        safe_title = video_info['title'][:100]
        safe_title = re.sub(r'[\\/:*?"<>|]', '_', safe_title)
        safe_title = safe_title.strip(' _')
        if not safe_title:
            safe_title = f"video_{video_info['video_id']}"
        
        # 根据设置的命名规则生成文件名
        naming_rule = self.settings.get('file_naming_rule', '{title}')
        
        # 新添加的任务优先级为当前队列长度（最低优先级）
        priority = len(self.downloads)
        
        download_task = {
            'video_id': video_info['video_id'],
            'title': video_info['title'],
            'url': source['url'],
            'status': 'pending',
            'progress': 0,
            'size': 0,
            'total_size': 0,
            'priority': priority,
            'retry_count': 0,
            'max_retries': 3
        }
        
        self.downloads.append(download_task)
        self.update_download_list()
        
        self.statusBar().showMessage(f"视频 {video_info['title'][:20]}... 已添加到下载队列")
    
    def update_download_list(self):
        """更新下载列表显示，包含每个任务的进度百分比"""
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
            
            # 添加进度百分比显示
            progress = int(download.get('progress', 0))
            if download['status'] == 'downloading':
                status_text += f" ({progress}%)"
            
            self.download_list.addItem(f"[{download['video_id']}] {download['title'][:30]}... - {status_text}")
    
    def on_start_download(self):
        """开始下载，根据最大同时下载数设置同时启动多个下载任务"""
        # 获取最大同时下载数设置
        max_simultaneous = self.settings.get('max_simultaneous_downloads', 2)
        
        # 计算当前活跃下载数
        current_active = len(self.active_downloads)
        
        # 计算还能启动多少个下载
        available_slots = max_simultaneous - current_active
        if available_slots <= 0:
            return
        
        # 查找待下载任务并启动
        started_count = 0
        for i, download in enumerate(self.downloads):
            if download['status'] in ['pending', 'paused']:
                self.start_download(i)
                started_count += 1
                if started_count >= available_slots:
                    break
    
    def start_download(self, index):
        """开始单个下载任务"""
        if 0 <= index < len(self.downloads):
            download = self.downloads[index]
            if download['status'] in ['pending', 'paused']:
                # 生成安全的文件名
                safe_title = download['title'][:100]
                safe_title = re.sub(r'[\\/:*?"<>|]', '_', safe_title)
                safe_title = safe_title.strip(' _')
                if not safe_title:
                    safe_title = f"video_{download['video_id']}"
                
                # 根据设置的命名规则生成文件名
                naming_rule = self.settings.get('file_naming_rule', '{title}')
                filename_pattern = naming_rule.format(
                    title=safe_title,
                    video_id=download['video_id']
                )
                filename = f"{filename_pattern}.mp4"
                
                # 设置下载路径
                download_path = self.settings.get('download_path', os.path.join(os.getcwd(), 'hamineDownload'))
                
                # 检查文件是否已存在
                full_path = os.path.join(download_path, filename)
                if os.path.exists(full_path) and not self.settings.get('overwrite_existing', False):
                    self.statusBar().showMessage(f"文件 {filename} 已存在，跳过下载")
                    # 从下载队列中移除该任务
                    del self.downloads[index]
                    # 更新下载列表
                    self.update_download_list()
                    # 继续下载下一个任务
                    self.on_start_download()
                    return
                
                # 选择线程数
                if self.settings['download_mode'] == 'multi_thread':
                    num_threads = self.settings['num_threads']
                else:
                    num_threads = 1
                
                # 保存当前任务的唯一标识符（视频ID）
                video_id = download['video_id']
                
                worker = DownloadWorker(download['url'], filename, save_path=download_path, num_threads=num_threads)
                
                # 为worker添加视频ID属性，用于标识
                worker.video_id = video_id
                
                # 使用video_id作为唯一标识符，而不是索引
                worker.signals.progress.connect(lambda progress_info, vid=video_id: self.on_download_progress_by_id(progress_info, vid))
                worker.signals.finished.connect(lambda vid=video_id: self.on_download_finished_by_id(vid))
                worker.signals.error.connect(lambda error, vid=video_id: self.on_download_error_by_id(error, vid))
                
                self.downloads[index]['status'] = 'downloading'
                self.downloads[index]['filename'] = filename
                self.downloads[index]['video_id'] = video_id
                self.update_download_list()
                
                self.active_downloads[video_id] = worker
                
                self.threadpool.start(worker)
                
                self.statusBar().showMessage(f"开始下载视频 {download['title'][:20]}...")
    
    def on_download_progress(self, progress_info, index):
        """下载进度回调，更新单个任务进度并计算整体进度"""
        if 0 <= index < len(self.downloads):
            self.downloads[index]['progress'] = progress_info['progress']
            self.downloads[index]['size'] = progress_info['size']
            self.downloads[index]['total_size'] = progress_info['total_size']
            
            # 更新下载列表中的进度显示
            self.update_download_list()
            
            # 计算整体进度
            self.calculate_and_update_overall_progress()
    
    def on_download_progress_by_id(self, progress_info, video_id):
        """根据视频ID更新下载进度"""
        # 查找对应视频ID的任务
        for i, download in enumerate(self.downloads):
            if download.get('video_id') == video_id:
                # 更新任务进度
                self.downloads[i]['progress'] = progress_info['progress']
                self.downloads[i]['size'] = progress_info['size']
                self.downloads[i]['total_size'] = progress_info['total_size']
                
                # 更新下载列表中的进度显示
                self.update_download_list()
                
                # 计算整体进度
                self.calculate_and_update_overall_progress()
                break
    
    def calculate_and_update_overall_progress(self):
        """计算并更新整体进度"""
        total_downloaded = 0
        total_size = 0
        active_downloads = []
        
        # 遍历所有下载任务，计算总大小和已下载大小
        for download in self.downloads:
            if download['status'] == 'downloading':
                total_downloaded += download.get('size', 0)
                total_size += download.get('total_size', 1)  # 避免除以0
                active_downloads.append(download)
        
        # 显示整体进度
        if active_downloads:
            if total_size > 0:
                overall_progress = int((total_downloaded / total_size) * 100)
                self.download_progress.setValue(overall_progress)
            
            # 显示当前活跃下载的数量和总进度
            total_size_mb = total_size / (1024 * 1024)
            downloaded_size_mb = total_downloaded / (1024 * 1024)
            self.download_info.setText(f"同时下载: {len(active_downloads)} 个任务 - 总进度: {downloaded_size_mb:.1f}MB / {total_size_mb:.1f}MB")
        else:
            # 检查是否有等待中的任务
            pending_count = sum(1 for d in self.downloads if d['status'] == 'pending')
            if pending_count > 0:
                self.download_info.setText(f"准备下载: {pending_count} 个任务等待中")
            else:
                # 没有活跃下载和等待任务时重置进度条
                self.download_progress.setValue(0)
                self.download_info.setText("准备下载")
    
    def on_download_finished(self, index):
        """下载完成回调"""
        if 0 <= index < len(self.downloads):
            download = self.downloads[index]
            video_id = download.get('video_id')
            
            # 从活动下载中移除
            if video_id in self.active_downloads:
                del self.active_downloads[video_id]
            
            # 添加到下载历史
            history_item = {
                'video_id': download['video_id'],
                'title': download['title'],
                'filename': download.get('filename', f"video_{download['video_id']}.mp4"),
                'download_date': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            self.download_history.append(history_item)
            self.save_download_history()
            self.update_history_list()
            
            # 显示状态栏消息
            self.statusBar().showMessage(f"视频 {download['title'][:20]}... 下载完成")
            
            # 从下载队列中移除已完成的视频
            del self.downloads[index]
            
            # 更新下载列表显示
            self.update_download_list()
            
            # 重新计算整体进度
            self.calculate_and_update_overall_progress()
            
            # 检查是否还有待下载的视频，如果有，自动开始下载下一个，保持最大同时下载数
            self.on_start_download()
            
            # 检查是否有等待重试的任务
            self.check_and_retry_failed_downloads()
    
    def on_download_finished_by_id(self, video_id):
        """根据视频ID处理下载完成"""
        # 查找对应视频ID的任务索引
        task_index = -1
        for i, download in enumerate(self.downloads):
            if download.get('video_id') == video_id:
                task_index = i
                break
        
        if task_index != -1:
            download = self.downloads[task_index]
            
            # 从活动下载中移除
            if video_id in self.active_downloads:
                del self.active_downloads[video_id]
            
            # 添加到下载历史
            history_item = {
                'video_id': download['video_id'],
                'title': download['title'],
                'filename': download.get('filename', f"video_{download['video_id']}.mp4"),
                'download_date': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            self.download_history.append(history_item)
            self.save_download_history()
            self.update_history_list()
            
            # 显示状态栏消息
            self.statusBar().showMessage(f"视频 {download['title'][:20]}... 下载完成")
            
            # 从下载队列中移除已完成的视频
            del self.downloads[task_index]
            
            # 更新下载列表显示
            self.update_download_list()
            
            # 重新计算整体进度
            self.calculate_and_update_overall_progress()
            
            # 检查是否还有待下载的视频，如果有，自动开始下载下一个，保持最大同时下载数
            self.on_start_download()
    
    def on_download_error(self, error, index):
        """下载错误回调，更新进度显示"""
        if 0 <= index < len(self.downloads):
            self.downloads[index]['status'] = 'error'
            self.downloads[index]['error'] = str(error)
            
            # 从活动下载中移除
            video_id = self.downloads[index].get('video_id')
            if video_id in self.active_downloads:
                del self.active_downloads[video_id]
            
            # 更新下载列表显示
            self.update_download_list()
            
            # 重新计算整体进度
            self.calculate_and_update_overall_progress()
            
            self.statusBar().showMessage(f"视频下载出错: {error}")
    
    def on_download_error_by_id(self, error, video_id):
        """根据视频ID处理下载错误"""
        # 查找对应视频ID的任务
        for i, download in enumerate(self.downloads):
            if download.get('video_id') == video_id:
                # 更新重试计数
                retry_count = download.get('retry_count', 0) + 1
                self.downloads[i]['retry_count'] = retry_count
                self.downloads[i]['error'] = str(error)
                
                # 从活动下载中移除
                if video_id in self.active_downloads:
                    del self.active_downloads[video_id]
                
                # 更新下载列表显示
                self.update_download_list()
                
                # 重新计算整体进度
                self.calculate_and_update_overall_progress()
                
                if retry_count < download.get('max_retries', 3):
                    # 还有重试机会，将状态改为pending，立即触发重试
                    self.downloads[i]['status'] = 'pending'
                    self.statusBar().showMessage(f"视频 {download['title'][:20]}... 下载出错，将重试 ({retry_count}/{download.get('max_retries', 3)})")
                    
                    # 立即检查并重试失败的下载任务
                    self.check_and_retry_failed_downloads()
                else:
                    # 重试次数已达上限
                    self.downloads[i]['status'] = 'error'
                    self.statusBar().showMessage(f"视频 {download['title'][:20]}... 下载出错，已达到最大重试次数")
                break
    
    def on_pause_download(self):
        """暂停所有当前下载"""
        for video_id, worker in self.active_downloads.items():
            # 调用worker的pause方法，实现真正的暂停
            worker.pause()
            # 查找对应视频ID的任务并更新状态
            for i, download in enumerate(self.downloads):
                if download.get('video_id') == video_id:
                    self.downloads[i]['status'] = 'paused'
                    break
        
        # 批量更新下载列表和进度显示
        self.update_download_list()
        
        # 保存当前进度，不重置进度条
        self.download_info.setText(f"所有下载已暂停 - 已下载: {len(self.active_downloads)} 个任务")
        
        self.statusBar().showMessage(f"已暂停 {len(self.active_downloads)} 个下载任务")
    
    def on_resume_download(self):
        """恢复所有当前下载"""
        for video_id, worker in self.active_downloads.items():
            # 调用worker的resume方法，恢复下载
            worker.resume()
            # 查找对应视频ID的任务并更新状态
            for i, download in enumerate(self.downloads):
                if download.get('video_id') == video_id:
                    self.downloads[i]['status'] = 'downloading'
                    break
        
        # 批量更新下载列表
        self.update_download_list()
        
        # 更新进度条显示为"准备下载"
        self.download_info.setText("正在恢复下载...")
        
        self.statusBar().showMessage(f"已恢复 {len(self.active_downloads)} 个下载任务")
    
    def on_cancel_download(self):
        """取消所有当前下载"""
        # 保存需要取消的视频ID，避免在遍历字典时修改字典
        cancelled_video_ids = list(self.active_downloads.keys())
        cancelled_count = len(cancelled_video_ids)
        
        if cancelled_count > 0:
            for video_id in cancelled_video_ids:
                worker = self.active_downloads[video_id]
                worker.cancel()
                
                # 查找对应视频ID的任务
                for i, download in enumerate(self.downloads):
                    if download.get('video_id') == video_id:
                        # 更新任务状态
                        self.downloads[i]['status'] = 'cancelled'
                        
                        # 删除本地文件
                        file_path = os.path.join(self.settings['download_path'], download['filename'])
                        if os.path.exists(file_path):
                            try:
                                os.remove(file_path)
                            except Exception as e:
                                pass
                        break
                
                # 从活跃下载中移除
                del self.active_downloads[video_id]
            
            # 批量更新下载列表
            self.update_download_list()
            
            # 更新进度条显示
            self.download_progress.setValue(0)
            self.download_info.setText("所有下载已取消")
            
            self.statusBar().showMessage(f"已取消 {cancelled_count} 个下载任务并删除临时文件")
    
    def check_and_retry_failed_downloads(self):
        """检查并重试失败的下载任务"""
        # 获取最大同时下载数设置
        max_simultaneous = self.settings.get('max_simultaneous_downloads', 2)
        
        # 计算当前活跃下载数
        current_active = len(self.active_downloads)
        
        # 计算还能启动多少个下载
        available_slots = max_simultaneous - current_active
        if available_slots <= 0:
            return
        
        # 查找等待重试的任务
        retry_tasks = []
        for i, download in enumerate(self.downloads):
            if download['status'] == 'pending' and download.get('retry_count', 0) > 0:
                retry_tasks.append(i)
        
        # 按重试次数排序，优先重试重试次数少的任务
        retry_tasks.sort(key=lambda i: self.downloads[i]['retry_count'])
        
        # 逐个重试
        for i in retry_tasks[:available_slots]:
            download = self.downloads[i]
            video_id = download['video_id']
            
            # 获取新的视频信息和下载链接
            worker = GetVideoInfoWorker(self.api, video_id)
            worker.signals.result.connect(lambda video_info, idx=i: self.on_video_info_for_retry(video_info, idx))
            self.threadpool.start(worker)
    
    def on_video_info_for_retry(self, video_info, index):
        """获取视频信息用于重试下载"""
        if video_info and video_info['video_sources']:
            # 根据用户设置选择画质
            download_quality = self.settings.get('download_quality', '最高')
            video_sources = video_info['video_sources']
            
            if download_quality == '最高':
                # 选择质量最高的源进行下载
                source = video_sources[0]
            else:
                # 选择质量最低的源进行下载
                source = video_sources[-1]
            
            # 更新下载任务的URL
            self.downloads[index]['url'] = source['url']
            self.downloads[index]['status'] = 'downloading'
            
            # 启动下载
            self.start_download(index)
    
    def on_clear_download_list(self):
        """清空下载列表（仅清空未下载的任务，保留正在下载的任务）"""
        # 保留正在下载的任务，只清空未下载的任务
        remaining_downloads = []
        active_video_ids = list(self.active_downloads.keys())
        
        for i, download in enumerate(self.downloads):
            # 如果是活动下载，保留
            if download.get('video_id') in active_video_ids:
                remaining_downloads.append(download)
        
        # 更新下载列表，重新分配优先级
        self.downloads = remaining_downloads
        for i, download in enumerate(self.downloads):
            download['priority'] = i
        
        self.update_download_list()
        self.statusBar().showMessage("已清空下载列表（正在下载的任务已保留）")
    
    def on_move_up(self):
        """上移下载任务"""
        current_row = self.download_list.currentRow()
        if current_row > 0:
            # 交换位置
            self.downloads[current_row], self.downloads[current_row - 1] = self.downloads[current_row - 1], self.downloads[current_row]
            # 更新优先级
            for i, download in enumerate(self.downloads):
                download['priority'] = i
            # 更新列表
            self.update_download_list()
            # 重新选中
            self.download_list.setCurrentRow(current_row - 1)
    
    def on_move_down(self):
        """下移下载任务"""
        current_row = self.download_list.currentRow()
        if current_row < len(self.downloads) - 1:
            # 交换位置
            self.downloads[current_row], self.downloads[current_row + 1] = self.downloads[current_row + 1], self.downloads[current_row]
            # 更新优先级
            for i, download in enumerate(self.downloads):
                download['priority'] = i
            # 更新列表
            self.update_download_list()
            # 重新选中
            self.download_list.setCurrentRow(current_row + 1)
    
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
    
    def on_download_from_menu(self, items):
        """从菜单下载"""
        for item in items:
            text = item.text()
            match = re.search(r'\[(\d+)]\s*(.+)', text)
            if match:
                video_id = match.group(1)
                worker = GetVideoInfoWorker(self.api, video_id)
                worker.signals.result.connect(self.on_video_info_for_download)
                self.threadpool.start(worker)
    
    def on_video_info_for_download(self, video_info):
        """获取视频信息用于下载"""
        if video_info and video_info['video_sources']:
            # 根据用户设置选择画质
            download_quality = self.settings.get('download_quality', '最高')
            video_sources = video_info['video_sources']
            
            if download_quality == '最高':
                # 选择质量最高的源进行下载
                # 假设video_sources列表已经按质量从高到低排序
                source = video_sources[0]
            else:
                # 选择质量最低的源进行下载
                source = video_sources[-1]
            
            self.add_to_download_queue(video_info, source)
    
    def load_favorites(self):
        """加载收藏夹，支持多个收藏夹"""
        if os.path.exists(self.favorites_file):
            try:
                with open(self.favorites_file, 'r', encoding='utf-8') as f:
                    loaded_data = json.load(f)
                    # 确保数据结构正确
                    if isinstance(loaded_data, list):
                        # 兼容旧版本数据结构
                        self.favorites = {'默认收藏夹': loaded_data}
                    else:
                        self.favorites = loaded_data
                        # 清理无效的收藏夹名称（如只有空格的收藏夹）
                        invalid_folders = []
                        for folder_name in self.favorites.keys():
                            if not folder_name.strip():
                                invalid_folders.append(folder_name)
                        for folder_name in invalid_folders:
                            del self.favorites[folder_name]
                        # 如果清理后没有收藏夹，添加默认收藏夹
                        if not self.favorites:
                            self.favorites = {'默认收藏夹': []}
            except Exception as e:
                self.favorites = {'默认收藏夹': []}
        else:
            self.favorites = {'默认收藏夹': []}
        
        # 更新收藏夹下拉框和列表
        self.update_folder_combobox()
    
    def save_favorites(self):
        """保存收藏夹"""
        try:
            with open(self.favorites_file, 'w', encoding='utf-8') as f:
                json.dump(self.favorites, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.statusBar().showMessage(f"保存收藏夹失败: {str(e)}")
    
    def update_favorites_list(self):
        """更新收藏夹列表显示"""
        # 重置搜索状态
        if hasattr(self, '_original_favorites'):
            delattr(self, '_original_favorites')
        
        self._refresh_favorites_list()
    
    def _refresh_favorites_list(self, filtered_favorites=None):
        """刷新收藏夹列表
        
        Args:
            filtered_favorites: 过滤后的收藏夹列表，为空则显示全部
        """
        self.favorites_list.clear()
        
        # 确保当前收藏夹存在
        if self.current_favorite_folder not in self.favorites:
            self.favorites[self.current_favorite_folder] = []
        
        # 获取要显示的收藏夹内容
        favorites_to_show = filtered_favorites if filtered_favorites is not None else self.favorites[self.current_favorite_folder]
        
        for favorite in favorites_to_show:
            self.favorites_list.addItem(f"[{favorite['video_id']}] {favorite['title']}")
    
    def update_folder_combobox(self):
        """更新收藏夹下拉框"""
        current_folder = self.folder_combobox.currentText()
        self.folder_combobox.clear()
        
        # 显示所有收藏夹
        for folder_name in self.favorites:
            self.folder_combobox.addItem(folder_name)
        
        # 恢复当前选中的收藏夹
        if current_folder and self.folder_combobox.findText(current_folder) != -1:
            self.folder_combobox.setCurrentText(current_folder)
        elif self.favorites:
            # 默认选择第一个收藏夹
            self.folder_combobox.setCurrentIndex(0)
            self.current_favorite_folder = self.folder_combobox.currentText()
        
        # 更新收藏夹列表
        self.update_favorites_list()
    
    def on_folder_changed(self, folder_name):
        """切换收藏夹
        
        Args:
            folder_name: 选中的收藏夹名称
        """
        self.current_favorite_folder = folder_name
        self.update_favorites_list()
    
    def on_new_folder(self):
        """新建收藏夹"""
        from PyQt5.QtWidgets import QInputDialog
        
        # 弹出输入对话框让用户输入新收藏夹名称
        folder_name, ok = QInputDialog.getText(self, "新建收藏夹", "请输入收藏夹名称:")
        
        if ok and folder_name.strip():
            folder_name = folder_name.strip()
            
            # 检查收藏夹名称是否已存在
            if folder_name in self.favorites:
                self.statusBar().showMessage(f"收藏夹 '{folder_name}' 已存在")
                return
            
            # 创建新收藏夹
            self.favorites[folder_name] = []
            
            # 保存收藏夹
            self.save_favorites()
            
            # 更新下拉框并选中新创建的收藏夹
            self.update_folder_combobox()
            self.folder_combobox.setCurrentText(folder_name)
            
            self.statusBar().showMessage(f"已创建收藏夹 '{folder_name}'")
    
    def on_delete_folder(self):
        """删除收藏夹"""
        from PyQt5.QtWidgets import QMessageBox
        
        current_folder = self.folder_combobox.currentText()
        
        # 不能删除默认收藏夹
        if current_folder == '默认收藏夹':
            QMessageBox.information(self, "提示", "默认收藏夹不能被删除")
            return
        
        # 询问用户是否确定要删除
        reply = QMessageBox.question(self, "确认删除", 
                                     f"确定要删除收藏夹 '{current_folder}' 吗？此操作不可恢复。",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            # 删除收藏夹
            if current_folder in self.favorites:
                del self.favorites[current_folder]
                
                # 保存收藏夹
                self.save_favorites()
                
                # 更新下拉框
                self.update_folder_combobox()
                
                self.statusBar().showMessage(f"已删除收藏夹 '{current_folder}'")
    
    def on_favorites_search(self, text):
        """收藏夹搜索功能
        
        Args:
            text: 搜索关键词
        """
        if not hasattr(self, '_original_favorites'):
            self._original_favorites = self.favorites.get(self.current_favorite_folder, [])
        
        if not text.strip():
            # 搜索关键词为空，显示全部
            self._refresh_favorites_list()
        else:
            # 搜索关键词不为空，过滤匹配的视频
            search_text = text.lower()
            filtered = [
                favorite for favorite in self._original_favorites 
                if search_text in favorite['title'].lower() or 
                   search_text in favorite.get('chinese_title', '').lower() or
                   search_text in favorite.get('video_id', '')
            ]
            self._refresh_favorites_list(filtered)
    
    def on_export_favorites(self):
        """导出当前选中的收藏夹"""
        # 获取当前选中的收藏夹
        current_folder = self.folder_combobox.currentText()
        
        # 如果没有选中收藏夹或收藏夹为空，显示提示
        if not current_folder or current_folder not in self.favorites:
            QMessageBox.warning(self, "提示", "请先选择一个有效的收藏夹")
            return
        
        # 设置默认文件名
        default_filename = f"{current_folder}.json"
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, "导出收藏夹", default_filename, "JSON Files (*.json)"
        )
        
        if file_path:
            try:
                # 只导出当前选中的收藏夹
                export_data = {current_folder: self.favorites[current_folder]}
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(export_data, f, ensure_ascii=False, indent=2)
                self.statusBar().showMessage(f"收藏夹 '{current_folder}' 已导出到 {file_path}")
            except Exception as e:
                self.statusBar().showMessage(f"导出收藏夹失败: {str(e)}")
    

    
    def on_import_favorites(self):
        """导入收藏夹"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "导入收藏夹", "", "JSON Files (*.json)"
        )
        
        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    imported_favorites = json.load(f)
                
                # 处理每个导入的收藏夹
                for folder_name, videos in imported_favorites.items():
                    # 验证收藏夹名称是否有效
                    if not folder_name.strip():
                        continue
                    
                    # 初始处理的收藏夹名称
                    current_folder_name = folder_name
                    
                    # 如果收藏夹名称已存在，询问用户如何处理
                    if current_folder_name in self.favorites:
                        # 创建自定义按钮的消息框
                        msg_box = QMessageBox()
                        msg_box.setWindowTitle("收藏夹已存在")
                        msg_box.setText(f"收藏夹 '{current_folder_name}' 已存在，您想如何处理？")
                        
                        # 添加自定义按钮
                        merge_button = msg_box.addButton("与已有收藏夹合并", QMessageBox.AcceptRole)
                        rename_button = msg_box.addButton("重命名该收藏夹", QMessageBox.RejectRole)
                        cancel_button = msg_box.addButton("取消", QMessageBox.RejectRole)
                        
                        # 设置默认按钮
                        msg_box.setDefaultButton(merge_button)
                        
                        # 显示消息框并获取用户选择
                        msg_box.exec_()
                        clicked_button = msg_box.clickedButton()
                        
                        if clicked_button == cancel_button:
                            # 用户取消导入
                            continue
                        elif clicked_button == merge_button:
                            # 合并现有收藏夹
                            existing_video_ids = {v['video_id'] for v in self.favorites[current_folder_name]}
                            new_videos = [v for v in videos if v['video_id'] not in existing_video_ids]
                            self.favorites[current_folder_name].extend(new_videos)
                            continue
                        else:  # rename_button - 重命名
                            # 循环获取新名称，直到名称有效且不冲突
                            while True:
                                new_name, ok = QInputDialog.getText(
                                    self, "重命名收藏夹",
                                    f"请输入新的收藏夹名称（当前名称：{current_folder_name}）："
                                )
                                
                                if not ok:
                                    # 用户取消重命名
                                    current_folder_name = None
                                    break
                                
                                # 验证新名称
                                new_name = new_name.strip()
                                if not new_name:
                                    QMessageBox.warning(self, "提示", "收藏夹名称不能为空")
                                    continue
                                
                                if new_name == current_folder_name:
                                    QMessageBox.warning(self, "提示", "新名称不能与原名称相同")
                                    continue
                                
                                if new_name in self.favorites:
                                    QMessageBox.warning(self, "提示", "该名称已被使用，请选择其他名称")
                                    continue
                                
                                # 名称有效，使用新名称
                                current_folder_name = new_name
                                break
                    
                    # 如果用户没有取消，添加新的收藏夹
                    if current_folder_name:
                        self.favorites[current_folder_name] = videos
                
                self.save_favorites()
                self.update_folder_combobox()
                self.update_favorites_list()
                self.statusBar().showMessage(f"收藏夹已从 {file_path} 导入")
            except Exception as e:
                self.statusBar().showMessage(f"导入收藏夹失败: {str(e)}")
    
    def on_share_website(self):
        """打开hanime1.yxxawa.top网站"""
        webbrowser.open("https://hanime1.yxxawa.top")
        self.statusBar().showMessage("正在打开hanime1.yxxawa.top网站")
    
    def add_to_favorites(self, video_info):
        """添加到收藏夹，询问用户要添加到哪个收藏夹"""
        # 如果没有收藏夹，创建默认收藏夹
        if not self.favorites:
            self.favorites['默认收藏夹'] = []
        
        # 如果只有一个收藏夹，直接添加
        if len(self.favorites) == 1:
            folder_name = list(self.favorites.keys())[0]
        else:
            # 弹出对话框让用户选择要添加到哪个收藏夹
            folder_names = list(self.favorites.keys())
            folder_name, ok = QInputDialog.getItem(self, "选择收藏夹", "请选择要添加到的收藏夹:", folder_names, 0, False)
            
            if not ok or not folder_name:
                return
        
        # 检查是否已在该收藏夹中
        if folder_name in self.favorites:
            for favorite in self.favorites[folder_name]:
                if favorite['video_id'] == video_info['video_id']:
                    QMessageBox.information(self, "提示", f"视频已在收藏夹 '{folder_name}' 中")
                    return
        else:
            # 收藏夹不存在，创建新收藏夹
            self.favorites[folder_name] = []
        
        # 添加到收藏夹
        favorite_item = {
            'video_id': video_info['video_id'],
            'title': video_info['title'],
            'chinese_title': video_info.get('chinese_title', ''),
            'thumbnail': video_info.get('thumbnail', ''),
            'url': video_info['url']
        }
        
        self.favorites[folder_name].append(favorite_item)
        self.save_favorites()
        self.update_favorites_list()
        self.statusBar().showMessage(f"视频 '{video_info['title'][:20]}...' 已添加到收藏夹 '{folder_name}'")
    
    def remove_from_favorites(self, video_id):
        """从当前选中的收藏夹移除视频"""
        if self.current_favorite_folder in self.favorites:
            # 从当前选中的收藏夹中移除指定视频
            self.favorites[self.current_favorite_folder] = [
                fav for fav in self.favorites[self.current_favorite_folder] 
                if fav['video_id'] != video_id
            ]
            self.save_favorites()
            self.update_favorites_list()
    
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
    
    def on_add_to_favorites_from_menu(self, items):
        """从菜单添加到收藏夹，询问用户要添加到哪个收藏夹"""
        # 如果没有选择任何视频，直接返回
        if not items:
            return
        
        # 如果没有收藏夹，创建默认收藏夹
        if not self.favorites:
            self.favorites['默认收藏夹'] = []
        
        # 弹出对话框让用户选择要添加到哪个收藏夹（只弹一次）
        folder_names = list(self.favorites.keys())
        if len(folder_names) == 1:
            folder_name = folder_names[0]
        else:
            folder_name, ok = QInputDialog.getItem(self, "选择收藏夹", "请选择要添加到的收藏夹:", folder_names, 0, False)
            
            if not ok or not folder_name:
                return
        
        # 确保收藏夹存在
        if folder_name not in self.favorites:
            self.favorites[folder_name] = []
        
        # 统计成功添加的视频数量
        added_count = 0
        already_exists_count = 0
        
        for item in items:
            text = item.text()
            match = re.search(r'\[(\d+)]\s*(.+)', text)
            if match:
                video_id = match.group(1)
                title = match.group(2)
                
                # 检查是否已在该收藏夹中
                already_exists = any(fav['video_id'] == video_id for fav in self.favorites[folder_name])
                if already_exists:
                    already_exists_count += 1
                    continue
                
                # 直接添加到收藏夹，不获取完整视频信息
                favorite_item = {
                    'video_id': video_id,
                    'title': title,
                    'chinese_title': '',
                    'thumbnail': '',
                    'url': f"https://hanime1.me/watch?v={video_id}"
                }
                
                self.favorites[folder_name].append(favorite_item)
                added_count += 1
        
        # 只有在有视频被添加时才保存和更新
        if added_count > 0:
            self.save_favorites()
            self.update_favorites_list()
            
            # 显示添加结果
            message = f"已将 {added_count} 个视频添加到收藏夹 '{folder_name}'"
            if already_exists_count > 0:
                message += f"，{already_exists_count} 个视频已存在"
            self.statusBar().showMessage(message)
        elif already_exists_count > 0:
            self.statusBar().showMessage(f"所有 {already_exists_count} 个视频已在收藏夹 '{folder_name}' 中")
    
    def on_remove_from_favorites(self, items):
        """从收藏夹移除"""
        # 先收集所有要移除的视频ID，避免在遍历过程中修改列表
        video_ids_to_remove = []
        for item in items:
            text = item.text()
            match = re.search(r'\[(\d+)]', text)
            if match:
                video_ids_to_remove.append(match.group(1))
        
        # 一次性移除所有视频
        if video_ids_to_remove:
            # 确保当前收藏夹存在
            if self.current_favorite_folder in self.favorites:
                # 从当前收藏夹中移除指定视频
                self.favorites[self.current_favorite_folder] = [
                    fav for fav in self.favorites[self.current_favorite_folder] 
                    if fav['video_id'] not in video_ids_to_remove
                ]
                self.save_favorites()
                self.update_favorites_list()
                count = len(video_ids_to_remove)
                self.statusBar().showMessage(f"已从收藏夹 '{self.current_favorite_folder}' 移除 {count} 个视频")
    
    def on_favorite_selected(self, item):
        """收藏夹视频选择回调"""
        text = item.text()
        match = re.search(r'\[(\d+)]', text)
        if match:
            video_id = match.group(1)
            self.get_video_info(video_id)
    
    def on_view_favorite_info(self, items):
        """查看收藏夹视频信息"""
        for item in items:
            text = item.text()
            match = re.search(r'\[(\d+)]', text)
            if match:
                video_id = match.group(1)
                self.get_video_info(video_id)
                break
    
    def on_download_favorite(self, items):
        """下载收藏夹视频"""
        for item in items:
            text = item.text()
            match = re.search(r'\[(\d+)]', text)
            if match:
                video_id = match.group(1)
                # 先获取视频信息，然后添加到下载队列
                worker = GetVideoInfoWorker(self.api, video_id)
                worker.signals.result.connect(self.on_video_info_for_download)
                self.threadpool.start(worker)
    
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
        
        resume_action = QAction("恢复下载", self)
        resume_action.triggered.connect(lambda: self.on_resume_download_from_menu(item))
        menu.addAction(resume_action)
        
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
            self.active_downloads[index].pause()
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
    
    def load_settings(self):
        """加载设置"""
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            pass
        return self.default_settings.copy()
    
    def save_settings(self):
        """保存设置"""
        try:
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, ensure_ascii=False, indent=2)
        except Exception as e:
            pass
    
    def closeEvent(self, event):
        """窗口关闭事件，保存当前窗口大小"""
        # 保存当前窗口大小
        geometry = self.geometry()
        self.settings['window_size'] = {
            'width': geometry.width(),
            'height': geometry.height()
        }
        self.save_settings()
        
        # 调用父类的closeEvent方法
        super().closeEvent(event)
    
    def open_settings(self):
        """打开设置对话框"""
        dialog = SettingsDialog(self.settings, self)
        if dialog.exec_():
            new_settings = dialog.get_settings()
            
            # 检查Cloudflare Cookie是否有变化
            old_cookie = self.settings.get('cloudflare_cookie', '')
            new_cookie = new_settings.get('cloudflare_cookie', '')
            
            # 更新设置
            self.settings.update(new_settings)
            self.save_settings()
            
            # 如果Cloudflare Cookie有变化，应用到API实例
            if old_cookie != new_cookie:
                # 清除现有Cookie（包括所有domain的Cookie）
                self.api.session.cookies.clear()
                
                if new_cookie:
                    # 应用新Cookie
                    if new_cookie.startswith('cf_clearance='):
                        # 直接是cf_clearance=value格式
                        cf_clearance = new_cookie.split('=', 1)[1]
                        # 确保设置正确的domain和path
                        self.api.session.cookies.set('cf_clearance', cf_clearance, domain='.hanime1.me', path='/')
                    else:
                        # 尝试解析完整的Cookie字符串
                        cookies = new_cookie.split(';')
                        for cookie in cookies:
                            cookie = cookie.strip()
                            if '=' in cookie:
                                name, value = cookie.split('=', 1)
                                # 为所有Cookie设置正确的domain和path
                                if name in ['cf_clearance', 'XSRF-TOKEN', 'hanime1_session', 'remember_web_59ba36addc2b2f9401580f014c7f58ea4e30989d']:
                                    self.api.session.cookies.set(name, value, domain='.hanime1.me', path='/')
                                else:
                                    # 其他Cookie也添加到会话中
                                    self.api.session.cookies.set(name, value, domain='.hanime1.me', path='/')
                    # 保存会话到settings.json
                    self.api.save_session()
                    # 显示当前Cookie状态
                    print(f"已应用Cookie: cf_clearance={'***' + cf_clearance[-10:] if 'cf_clearance' in locals() else '未找到'}")
                    print(f"当前会话Cookie: {dict(self.api.session.cookies)}")
                    self.statusBar().showMessage("设置已保存，Cloudflare Cookie已应用")
                else:
                    # 从settings.json中移除session信息
                    if os.path.exists('settings.json'):
                        with open('settings.json', 'r', encoding='utf-8') as f:
                            settings = json.load(f)
                        
                        if 'session' in settings:
                            del settings['session']
                            # 保存更新后的settings
                            with open('settings.json', 'w', encoding='utf-8') as f:
                                json.dump(settings, f, ensure_ascii=False, indent=2)
                    self.statusBar().showMessage("设置已保存，Cloudflare Cookie已清除")
            else:
                self.statusBar().showMessage("设置已保存")
    
    def load_download_history(self):
        """加载下载历史"""
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    self.download_history = json.load(f)
            except Exception as e:
                self.download_history = []
    
    def save_download_history(self):
        """保存下载历史"""
        try:
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(self.download_history, f, ensure_ascii=False, indent=2)
        except Exception as e:
            pass
    
    def update_history_list(self):
        """更新下载历史列表"""
        self.history_list.clear()
        for item in reversed(self.download_history):
            self.history_list.addItem(f"[{item['video_id']}] {item['title'][:30]}... - {item['download_date']}")
    
    def refresh_download_history(self):
        """刷新下载历史"""
        self.load_download_history()
        self.update_history_list()
    
    def clear_download_history(self):
        """清空下载历史"""
        from PyQt5.QtWidgets import QMessageBox
        
        reply = QMessageBox.question(self, "确认清空", "确定要清空所有下载历史吗？此操作不可恢复。",
                                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            self.download_history = []
            self.save_download_history()
            self.update_history_list()
            self.statusBar().showMessage("下载历史已清空")
    
    def show_history_context_menu(self, position):
        """下载历史右键菜单"""
        selected_items = self.history_list.selectedItems()
        if not selected_items:
            return
        
        menu = QMenu()
        
        # 查看信息选项
        view_action = QAction("查看视频信息", self)
        view_action.triggered.connect(lambda: self.on_view_history_video_info(selected_items))
        menu.addAction(view_action)
        
        menu.exec_(self.history_list.viewport().mapToGlobal(position))
    
    def on_view_history_video_info(self, items):
        """查看历史视频信息"""
        for item in items:
            text = item.text()
            import re
            match = re.search(r'\[(\d+)]', text)
            if match:
                video_id = match.group(1)
                self.get_video_info(video_id)
                break
    
    def show_cover(self):
        """显示封面图片（程序内弹窗）"""
        if not self.current_cover_url:
            return
        
        # 创建弹窗
        cover_dialog = QDialog(self)
        cover_dialog.setWindowTitle("封面预览")
        cover_dialog.setMinimumSize(400, 500)
        # 不设置最大尺寸，允许自由放大
        
        # 创建布局
        layout = QVBoxLayout(cover_dialog)
        
        # 创建标签用于显示图片
        cover_label = QLabel()
        cover_label.setAlignment(Qt.AlignCenter)
        cover_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout.addWidget(cover_label)
        
        try:
            # 下载封面图片
            response = requests.get(self.current_cover_url)
            response.raise_for_status()
            
            # 加载图片到QPixmap
            pixmap = QPixmap()
            pixmap.loadFromData(response.content)
            
            if not pixmap.isNull():
                # 缩放图片以适应窗口，保持比例
                scaled_pixmap = pixmap.scaled(
                    cover_label.size(), 
                    Qt.KeepAspectRatio, 
                    Qt.SmoothTransformation
                )
                cover_label.setPixmap(scaled_pixmap)
                
                # 连接窗口大小变化事件，重新缩放图片
                def resize_image(event):
                    scaled_pixmap = pixmap.scaled(
                        cover_label.size(), 
                        Qt.KeepAspectRatio, 
                        Qt.SmoothTransformation
                    )
                    cover_label.setPixmap(scaled_pixmap)
                    # 调用原始的resizeEvent方法
                    QLabel.resizeEvent(cover_label, event)
                
                cover_label.resizeEvent = resize_image
            else:
                cover_label.setText("无法加载图片")
        except Exception as e:
            cover_label.setText(f"加载失败: {str(e)}")
            QMessageBox.warning(self, "错误", f"无法加载封面图片: {str(e)}")
        
        # 显示弹窗
        cover_dialog.exec_()
    
    def on_related_video_clicked(self, item):
        """点击相关视频"""
        text = item.text()
        match = re.search(r'\[(\d+)]', text)
        if match:
            video_id = match.group(1)
            self.get_video_info(video_id)
    

def main():
    app = QApplication(sys.argv)
    window = Hanime1GUI()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
