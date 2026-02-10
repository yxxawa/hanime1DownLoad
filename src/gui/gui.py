"""
Hanime1DL 主界面窗口
"""

import json
import multiprocessing
import os
import re
import shutil
import threading
import time
import datetime

import requests
import sip
from PyQt5.QtCore import (
    QEvent,
    QObject,
    QRectF,
    QRunnable,
    QSize,
    Qt,
    QThreadPool,
    pyqtSignal,
    pyqtSlot,
)
from PyQt5.QtGui import QColor, QFont, QIcon, QPainter, QPainterPath, QPen, QPixmap
from PyQt5.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from src.api.hanime1_api import Hanime1API
from src.dialogs.dialogs import FilterDialog, SettingsDialog
from src.widgets.widgets import (
    ChineseComboBox,
    ChineseLineEdit,
    ChineseTextEdit,
    DownloadListWidget,
    PageNavigationWidget,
)
from src.workers.workers import DownloadWorker, GetVideoInfoWorker, SearchWorker


class Hanime1GUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.api = Hanime1API()
        self.threadpool = QThreadPool()
        # 根据系统CPU核心数动态调整线程池大小
        cpu_count = multiprocessing.cpu_count()
        max_threads = min(cpu_count * 3, 16)
        self.threadpool.setMaxThreadCount(max_threads)

        # 初始化设置
        self.settings_file = os.path.join(os.getcwd(), "settings.json")
        self.default_settings = {
            "download_mode": "multi_thread",
            "num_threads": 4,
            "max_simultaneous_downloads": 2,
            "download_quality": "最高",
            "download_path": os.path.join(os.getcwd(), "hanimeDownload"),
            "file_naming_rule": "{title}",
            "overwrite_existing": False,
            "cloudflare_cookie": "",
            "window_size": {"width": 1589, "height": 1415},
            "window_pos": {"x": 520, "y": 91},
            "search_history": [],
            "show_thumbnails": False,
            "show_announcements": True,
            "font": "Segoe UI",
            "font_size": 9,
            "video_details_visibility": {
                "title": True,
                "upload_date": True,
                "likes": True,
                "tags": True,
                "cover": True,
                "description": False,
                "related_videos": True,
            },
        }
        self.settings = self.load_settings()
        if not os.path.exists(self.settings_file):
            self.save_settings()

        # 应用Cloudflare Cookie到API实例
        cloudflare_cookie = self.settings.get("cloudflare_cookie", "")
        if cloudflare_cookie:
            self.apply_cloudflare_cookie(cloudflare_cookie)

        # 搜索筛选参数
        self.filter_params = {
            "genre": "",
            "sort": "",
            "date": "",
            "duration": "",
            "tags": [],
            "broad": False,
        }

        self.current_search_results = []
        self.current_video_info = None
        self.downloads = []
        self.active_downloads = {}
        self.current_cover_url = ""
        self.thumbnail_cache = {}  # 缩略图缓存
        self._op_lock = threading.Lock()
        self._last_action_time = {}

        # 初始化数据结构
        self.favorites = {}
        self.current_favorite_folder = "默认收藏夹"
        self.favorites_file = os.path.join(os.getcwd(), "favorites.json")

        self.download_history = []
        self.history_file = os.path.join(os.getcwd(), "download_history.json")
        self.temp_download_dir = os.path.join(os.getcwd(), ".HDDownload")
        self._ensure_temp_download_dir()

        # 初始化UI
        self.init_ui()

        # 加载数据
        self.load_favorites()
        self.load_download_history()
        self.update_history_list()

        # 应用详情显示设置
        self.apply_video_details_visibility()

    def init_ui(self):
        """初始化用户界面"""
        self._init_main_window()
        self._apply_global_styles()
        self._init_left_panel()
        self._init_right_panel()
        self.statusBar()



    def _apply_global_styles(self):
        """应用全局 QSS 样式"""
        # 设置全局字体
        font_name = self.settings.get("font", "Segoe UI")
        font_size = self.settings.get("font_size", 9)
        QApplication.setFont(QFont(font_name, font_size))
        
        # 直接使用相对路径，让Qt自动处理路径解析
        style_sheet = """
            /* 全局基础样式 */
            * {
                font-family: '%s';
                font-size: %dpt;
            }
            
            /* 窗口和面板样式 */
            QMainWindow, QWidget, QDialog {
                border-radius: 8px;
            }
            
            /* 列表和滚动区域样式 */
            QListWidget, QTextEdit, QScrollArea {
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                background-color: white;
                outline: none;
                padding: 0;
                margin: 0;
            }
            QListWidget::viewport {
                padding: 0;
                margin: 0;
            }
            QListWidget {
                margin-bottom: -4px;
            }
            QTextEdit, QScrollArea {
                padding: 4px;
            }
            
            /* 修复滚动条交汇处的白块 */
            QAbstractScrollArea::corner {
                background: transparent;
                border: none;
            }
            
            /* 现代感滚动条样式 */
            QScrollBar:vertical {
                border: none;
                background: #f5f5f5;
                width: 6px;
                margin: 0;
                border-radius: 3px;
            }
            QScrollBar::handle:vertical {
                background: #ccc;
                min-height: 20px;
                border-radius: 3px;
                margin: 0;
            }
            QScrollBar::handle:vertical:hover {
                background: #aaa;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            
            /* 横向滚动条隐藏逻辑优化 - 更加严格的显示控制 */
            QListWidget QScrollBar:horizontal, 
            QTextEdit QScrollBar:horizontal, 
            QScrollArea QScrollBar:horizontal {
                border: none;
                background: transparent;
                height: 0px;
                min-height: 0px;
                max-height: 0px;
                margin: 0px;
            }
            QListWidget:hover QScrollBar:horizontal, 
            QTextEdit:hover QScrollBar:horizontal, 
            QScrollArea:hover QScrollBar:horizontal {
                height: 6px;
                min-height: 6px;
                max-height: 6px;
                background: #f5f5f5;
                border-radius: 3px;
                margin: 0;
            }
            QListWidget:hover QScrollBar::handle:horizontal, 
            QTextEdit:hover QScrollBar::handle:horizontal, 
            QScrollArea:hover QScrollBar::handle:horizontal {
                background: #ccc;
                min-width: 20px;
                border-radius: 3px;
                margin: 0;
            }
            QScrollBar::handle:horizontal:hover {
                background: #aaa;
            }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                width: 0px;
                height: 0px;
                background: transparent;
            }
            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
                background: transparent;
            }
            
            /* 列表项样式 */
            QListWidget::item {
                border-bottom: 1px solid #f0f0f0;
                padding: 10px;
                color: #333;
                border-radius: 6px;
                margin: 1px;
            }
            QListWidget::item:selected {
                background-color: #e6f7ff;
                color: #1890ff;
                border-left: 4px solid #1890ff;
                border-radius: 6px;
            }
            QListWidget::item:hover {
                background-color: #f5f9ff;
                border-radius: 6px;
            }
            
            /* 分组框样式 */
            QGroupBox {
                font-weight: bold;
                border: 1px solid #e0e0e0;
                border-radius: 10px;
                margin-top: 12px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 6px 0 6px;
                border-radius: 4px;
            }
            
            /* 按钮样式 */
            QPushButton {
                background-color: #f8f9fa;
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                padding: 8px 16px;
                color: #333;
                min-height: 28px;
            }
            QPushButton:hover {
                background-color: #e6f7ff;
                border-color: #1890ff;
                color: #1890ff;
            }
            QPushButton:pressed {
                background-color: #e6e6e6;
                border-color: #1890ff;
                color: #1890ff;
            }
            QPushButton:disabled {
                background-color: #f5f5f5;
                color: #bfbfbf;
                border-color: #e0e0e0;
            }
            
            /* 主要操作按钮样式 */
            QPushButton#primary_btn {
                background-color: #1890ff;
                border-color: #1890ff;
                color: white;
            }
            QPushButton#primary_btn:hover {
                background-color: #40a9ff;
                border-color: #40a9ff;
            }
            QPushButton#primary_btn:pressed {
                background-color: #096dd9;
                border-color: #096dd9;
            }
            
            /* 输入控件样式 */
            QLineEdit, QSpinBox, QTextEdit, QComboBox {
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                padding: 6px 10px;
                background: white;
            }
            QLineEdit:focus, QSpinBox:focus, QTextEdit:focus, QComboBox:focus {
                border-color: #1890ff;
            }
            
            /* 美化右键菜单和下拉菜单 */
            QMenu {
                background-color: #ffffff;
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                padding: 4px 0px;
            }
            QMenu::item {
                padding: 8px 32px 8px 24px;
                border: 1px solid transparent;
                margin: 2px;
                border-radius: 6px;
            }
            QMenu::item:selected {
                background-color: #e6f7ff;
                color: #1890ff;
                border-radius: 6px;
            }
            QMenu::separator {
                height: 1px;
                background: #f0f0f0;
                margin: 4px 10px;
            }
            QMenu::icon {
                margin-left: 10px;
            }
            
            /* 下拉框样式 */
            QComboBox {
                min-height: 28px;
            }
            QComboBox:hover {
                border-color: #1890ff;
            }
            QComboBox::drop-down {
                border: none;
                width: 30px;
                border-top-right-radius: 8px;
                border-bottom-right-radius: 8px;
            }
            QComboBox::down-arrow {
                image: url(assets/open.png);
                width: 16px;
                height: 16px;
                margin: 0;
            }
            QComboBox::down-arrow:hover {
                image: url(assets/open.png);
            }
            QComboBox::down-arrow:on {
                image: url(assets/close.png);
            }
            QComboBox QAbstractItemView {
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                background-color: white;
                selection-background-color: #e6f7ff;
                selection-color: #1890ff;
                outline: none;
            }
            QComboBox QAbstractItemView::item {
                min-height: 32px;
                padding-left: 12px;
                border-radius: 6px;
                margin: 2px;
            }
            QComboBox QAbstractItemView::item:hover {
                background-color: #f5f9ff;
            }
            
            /* 数字输入框样式 */
            QSpinBox::up-button, QSpinBox::down-button {
                border: none;
                background: #f8f9fa;
                width: 20px;
                border-radius: 4px;
            }
            QSpinBox::up-button:hover, QSpinBox::down-button:hover {
                background: #e6f7ff;
            }
            QSpinBox::up-arrow {
                image: url(assets/up.png);
                width: 12px;
                height: 12px;
            }
            QSpinBox::down-arrow {
                image: url(assets/down.png);
                width: 12px;
                height: 12px;
            }
            
            /* 美化进度条 */
            QProgressBar {
                border: 1px solid #e0e0e0;
                border-radius: 10px;
                background-color: #f5f5f5;
                height: 20px;
                text-align: center;
                color: #333;
            }
            QProgressBar::chunk {
                background-color: #1890ff;
                border-radius: 9px;
                margin: 1px;
            }
            QProgressBar::chunk:disabled {
                background-color: #bfbfbf;
                border-radius: 9px;
                margin: 1px;
            }
            QProgressBar::chunk:completed {
                background-color: #52c41a;
                border-radius: 9px;
                margin: 1px;
            }
            QProgressBar::chunk:error {
                background-color: #ff4d4f;
                border-radius: 9px;
                margin: 1px;
            }
            QProgressBar::chunk:paused {
                background-color: #faad14;
                border-radius: 9px;
                margin: 1px;
            }
        """
        
        # 使用字符串格式化来插入字体名称和大小
        style_sheet = style_sheet % (font_name, font_size)
        self.setStyleSheet(style_sheet)
        
        # 强制更新界面
        self.update()
        self.repaint()
        # 更新所有子控件
        for widget in self.findChildren(QWidget):
            widget.update()
            widget.repaint()

    def _init_main_window(self):
        self.setWindowTitle("Hanime1视频工具---BY-yxxawa")
        window_size = self.settings.get("window_size", {"width": 1320, "height": 1485})
        window_pos = self.settings.get("window_pos", {"x": 100, "y": 100})
        self.setGeometry(
            window_pos.get("x", 100),
            window_pos.get("y", 100),
            window_size.get("width", 1320),
            window_size.get("height", 1485)
        )

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        self.main_layout = QHBoxLayout(central_widget)
        self.main_layout.setSpacing(16)
        self.main_layout.setContentsMargins(16, 16, 16, 16)

    def _init_left_panel(self):
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
        search_title = QLabel("视频搜索")
        parent_layout.addWidget(search_title)

        search_layout = QHBoxLayout()
        self.search_input = ChineseComboBox()
        self.search_input.setEditable(True)
        self.search_input.setLineEdit(ChineseLineEdit())
        self.search_input.lineEdit().setPlaceholderText("请输入搜索关键词...")
        self.search_input.lineEdit().returnPressed.connect(self.search_videos)
        self._update_search_history_ui()
        search_layout.addWidget(self.search_input, 1)

        self.search_button = QPushButton("搜索")
        self.search_button.clicked.connect(self.search_videos)
        search_layout.addWidget(self.search_button)

        self.filter_button = QPushButton("筛选")
        self.filter_button.clicked.connect(self.open_filter_dialog)
        search_layout.addWidget(self.filter_button)

        self.settings_button = QPushButton("设置")
        self.settings_button.clicked.connect(self.open_settings)
        search_layout.addWidget(self.settings_button)

        parent_layout.addLayout(search_layout)

    def _init_page_navigation(self, parent_layout):
        # 创建页码导航标签，包含页码信息
        self.page_navigation_label = QLabel(f"页码导航: 第 1 页 / 共 1 页")
        parent_layout.addWidget(self.page_navigation_label)
        
        self.page_navigation = PageNavigationWidget()
        self.page_navigation.page_changed.connect(self.on_page_changed)
        # 连接页码变化信号，更新标签文本
        self.page_navigation.page_changed.connect(self.update_page_navigation_label)
        parent_layout.addWidget(self.page_navigation)

    def _init_tab_widget(self, parent_layout):
        tab_widget = QTabWidget()

        # 视频列表
        self.video_list = QListWidget()
        self.video_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.video_list.itemClicked.connect(self.on_video_selected)
        self.video_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.video_list.customContextMenuRequested.connect(self.show_video_context_menu)
        self.video_list.setSelectionMode(QListWidget.ExtendedSelection)
        tab_widget.addTab(self.video_list, "搜索结果")

        # 收藏夹
        favorites_widget = QWidget()
        favorites_layout = QVBoxLayout(favorites_widget)

        favorites_manage_layout = QHBoxLayout()
        self.folder_combobox = QComboBox()
        self.folder_combobox.currentTextChanged.connect(self.on_folder_changed)
        favorites_manage_layout.addWidget(self.folder_combobox, 1)

        new_folder_button = QPushButton("新建")
        new_folder_button.clicked.connect(self.on_new_folder)
        favorites_manage_layout.addWidget(new_folder_button)

        delete_folder_button = QPushButton("删除")
        delete_folder_button.clicked.connect(self.on_delete_folder)
        favorites_manage_layout.addWidget(delete_folder_button)

        rename_folder_button = QPushButton("重命名")
        rename_folder_button.clicked.connect(self.on_rename_folder)
        favorites_manage_layout.addWidget(rename_folder_button)

        favorites_layout.addLayout(favorites_manage_layout)

        favorites_top_layout = QHBoxLayout()
        self.favorites_search_input = ChineseLineEdit()
        self.favorites_search_input.setPlaceholderText("在收藏夹中搜索...")
        self.favorites_search_input.textChanged.connect(self.on_favorites_search)
        favorites_top_layout.addWidget(self.favorites_search_input, 1)

        export_favorites_button = QPushButton("导出")
        export_favorites_button.clicked.connect(self.on_export_favorites)
        favorites_top_layout.addWidget(export_favorites_button)

        import_favorites_button = QPushButton("导入")
        import_favorites_button.clicked.connect(self.on_import_favorites)
        favorites_top_layout.addWidget(import_favorites_button)

        favorites_layout.addLayout(favorites_top_layout)

        self.favorites_list = QListWidget()
        self.favorites_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.favorites_list.itemClicked.connect(self.on_favorite_selected)
        self.favorites_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.favorites_list.customContextMenuRequested.connect(self.show_favorite_context_menu)
        self.favorites_list.setSelectionMode(QListWidget.ExtendedSelection)
        favorites_layout.addWidget(self.favorites_list)

        self.update_folder_combobox()
        tab_widget.addTab(favorites_widget, "收藏夹")

        # 下载历史
        history_widget = QWidget()
        history_layout = QVBoxLayout(history_widget)
        history_top_layout = QHBoxLayout()
        refresh_button = QPushButton("刷新")
        refresh_button.clicked.connect(self.refresh_download_history)
        history_top_layout.addWidget(refresh_button)
        clear_button = QPushButton("清空历史")
        clear_button.clicked.connect(self.clear_download_history)
        history_top_layout.addWidget(clear_button)
        history_top_layout.addStretch(1)
        history_layout.addLayout(history_top_layout)

        self.history_list = QListWidget()
        self.history_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.history_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.history_list.customContextMenuRequested.connect(self.show_history_context_menu)
        history_layout.addWidget(self.history_list)

        tab_widget.addTab(history_widget, "下载历史")

        parent_layout.addWidget(tab_widget)

    def _init_right_panel(self):
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setSpacing(16)
        self._init_video_info_area(right_layout)
        self._init_download_manager_area(right_layout)
        self.main_layout.addWidget(right_widget)

    def _init_video_info_area(self, parent_layout):
        info_group = QGroupBox("视频信息")
        info_layout = QVBoxLayout(info_group)
        info_layout.setSpacing(8)

        self.info_form = QFormLayout()

        # 存储表单行引用以便隐藏
        self.info_rows = {}

        self.title_label = QLabel("-")
        self.title_label.setWordWrap(True)
        title_tag = QLabel("标题:")
        self.info_form.addRow(title_tag, self.title_label)
        self.info_rows["title"] = (title_tag, self.title_label)

        self.upload_date_label = QLabel("-")
        date_tag = QLabel("上传日期:")
        self.info_form.addRow(date_tag, self.upload_date_label)
        self.info_rows["upload_date"] = (date_tag, self.upload_date_label)

        self.likes_label = QLabel("-")
        likes_tag = QLabel("点赞:")
        self.info_form.addRow(likes_tag, self.likes_label)
        self.info_rows["likes"] = (likes_tag, self.likes_label)

        self.tags_label = QLabel("-")
        self.tags_label.setWordWrap(True)
        tags_tag = QLabel("标签:")
        self.info_form.addRow(tags_tag, self.tags_label)
        self.info_rows["tags"] = (tags_tag, self.tags_label)

        self.view_cover_button = QPushButton("查看封面")
        self.view_cover_button.clicked.connect(self.show_cover)
        self.view_cover_button.setEnabled(False)
        cover_tag = QLabel("封面:")
        self.info_form.addRow(cover_tag, self.view_cover_button)
        self.info_rows["cover"] = (cover_tag, self.view_cover_button)

        self.description_text = ChineseTextEdit("-")
        self.description_text.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.description_text.setReadOnly(True)
        self.description_text.setMaximumHeight(120)
        desc_tag = QLabel("描述:")
        self.info_form.addRow(desc_tag, self.description_text)
        self.info_rows["description"] = (desc_tag, self.description_text)

        info_layout.addLayout(self.info_form)

        self.related_group = QGroupBox("相关视频")
        related_layout = QVBoxLayout(self.related_group)
        self.related_list = QListWidget()
        self.related_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.related_list.setMinimumHeight(150)
        self.related_list.setMaximumHeight(200)
        self.related_list.itemClicked.connect(self.on_related_video_clicked)
        self.related_list.setSelectionMode(QListWidget.ExtendedSelection)
        self.related_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.related_list.customContextMenuRequested.connect(self.show_related_video_context_menu)
        related_layout.addWidget(self.related_list)
        info_layout.addWidget(self.related_group)

        self.source_links_widget = QWidget()
        self.source_links_widget.setMinimumHeight(150)
        self.source_links_widget.setMaximumHeight(250)
        self.source_links_layout = QVBoxLayout(self.source_links_widget)
        info_layout.addWidget(self.source_links_widget)

        parent_layout.addWidget(info_group)

    def _init_download_manager_area(self, parent_layout):
        download_group = QGroupBox("下载管理")
        download_layout = QVBoxLayout(download_group)

        download_layout.addWidget(QLabel("下载队列 :"))
        self.download_list = DownloadListWidget()
        self.download_list.downloads_ref = self.downloads  # 注入引用
        self.download_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.download_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.download_list.customContextMenuRequested.connect(self.show_download_context_menu)
        self.download_list.order_changed.connect(self.on_download_order_changed)
        download_layout.addWidget(self.download_list, 1)

        download_control_layout = QHBoxLayout()
        # 合并后的开始/暂停按钮
        self.toggle_download_button = QPushButton("开始下载")
        self.toggle_download_button.clicked.connect(self.on_toggle_download)

        self.clear_download_button = QPushButton("清空列表")
        self.clear_download_button.clicked.connect(self.on_clear_download_list)

        for btn in [
            self.toggle_download_button,
            self.clear_download_button,
        ]:
            download_control_layout.addWidget(btn)
        download_layout.addLayout(download_control_layout)

        self.download_progress = QProgressBar()
        self.download_progress.setTextVisible(True)  # 显示进度条百分比
        self.download_progress.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Fixed
        )  # 设置响应式大小策略
        # 初始化进度条动画相关变量
        self.target_progress = 0
        self.current_progress = 0
        self.progress_timer = None

        # 使用水平布局显示进度信息
        info_line_layout = QHBoxLayout()
        self.download_info = QLabel("准备下载")

        info_line_layout.addWidget(self.download_info)
        info_line_layout.addStretch()

        download_layout.addWidget(QLabel("下载进度:"))
        download_layout.addWidget(self.download_progress)
        download_layout.addLayout(info_line_layout)

        parent_layout.addWidget(download_group)

    # 业务逻辑方法 (保持原逻辑不变，仅更新引用)
    def load_settings(self):
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, "r", encoding="utf-8") as f:
                    return json.load(f)
        except:
            pass
        return self.default_settings.copy()

    def save_settings(self):
        try:
            with open(self.settings_file, "w", encoding="utf-8") as f:
                json.dump(self.settings, f, ensure_ascii=False, indent=2)
        except:
            pass

    def closeEvent(self, event):
        geometry = self.geometry()
        self.settings["window_size"] = {"width": geometry.width(), "height": geometry.height()}
        self.settings["window_pos"] = {"x": geometry.x(), "y": geometry.y()}
        self.save_settings()
        try:
            self._clear_temp_download_folder()
        except:
            pass
        super().closeEvent(event)

    def apply_video_details_visibility(self):
        """应用详细信息显示设置"""
        visibility = self.settings.get("video_details_visibility", {})

        # 处理表单行
        for key, (tag, widget) in self.info_rows.items():
            is_visible = visibility.get(key, True)
            tag.setVisible(is_visible)
            widget.setVisible(is_visible)

        # 处理相关视频组
        self.related_group.setVisible(visibility.get("related_videos", True))

    def apply_cloudflare_cookie(self, cookie_text):
        if not cookie_text:
            return
        try:
            self.api.session.cookies.clear()
            if cookie_text.startswith("cf_clearance="):
                cf_clearance = cookie_text.split("=", 1)[1]
                self.api.session.cookies.set(
                    "cf_clearance", cf_clearance, domain=".hanime1.me", path="/"
                )
            else:
                cookies = cookie_text.split(";")
                for cookie in cookies:
                    cookie = cookie.strip()
                    if "=" in cookie:
                        name, value = cookie.split("=", 1)
                        self.api.session.cookies.set(name, value, domain=".hanime1.me", path="/")
            self.api.save_session()
        except Exception as e:
            print(f"应用 Cookie 失败: {str(e)}")

    def open_filter_dialog(self):
        dialog = FilterDialog(self.filter_params, self)
        if dialog.exec_():
            self.filter_params = dialog.get_filter_params()
            self.statusBar().showMessage("筛选设置已保存")

    def open_settings(self):
        dialog = SettingsDialog(self.settings, self)
        if dialog.exec_():
            new_settings = dialog.get_settings()
            old_cookie = self.settings.get("cloudflare_cookie", "")
            new_cookie = new_settings.get("cloudflare_cookie", "")
            old_show_thumbnails = self.settings.get("show_thumbnails", False)
            new_show_thumbnails = new_settings.get("show_thumbnails", False)
            old_font = self.settings.get("font", "Segoe UI")
            new_font = new_settings.get("font", "Segoe UI")
            old_font_size = self.settings.get("font_size", 9)
            new_font_size = new_settings.get("font_size", 9)

            self.settings.update(new_settings)
            self.save_settings()

            # 如果字体设置改变，重新应用全局样式
            if old_font != new_font or old_font_size != new_font_size:
                # 重新应用全局样式，包括新的字体设置
                self._apply_global_styles()
                # 刷新搜索列表（如果有结果）
                if self.current_search_results:
                    self.on_search_complete(
                        {
                            "videos": self.current_search_results,
                            "total_pages": self.page_navigation.total_pages,
                        }
                    )
                # 刷新收藏夹列表
                self.update_favorites_list()
            # 如果缩略图设置改变，刷新当前显示的列表
            elif old_show_thumbnails != new_show_thumbnails:
                # 刷新搜索列表（如果有结果）
                if self.current_search_results:
                    self.on_search_complete(
                        {
                            "videos": self.current_search_results,
                            "total_pages": self.page_navigation.total_pages,
                        }
                    )
                # 刷新收藏夹列表
                self.update_favorites_list()

            # 更新详情显示
            self.apply_video_details_visibility()

            if old_cookie != new_cookie:
                if new_cookie:
                    self.apply_cloudflare_cookie(new_cookie)
                    self.statusBar().showMessage("设置已保存，Cloudflare Cookie已应用")
                else:
                    self.api.session.cookies.clear()
                    if os.path.exists("settings.json"):
                        with open("settings.json", "r", encoding="utf-8") as f:
                            settings = json.load(f)
                        if "session" in settings:
                            del settings["session"]
                        with open("settings.json", "w", encoding="utf-8") as f:
                            json.dump(settings, f, ensure_ascii=False, indent=2)
                    self.statusBar().showMessage("设置已保存，Cloudflare Cookie已清除")
            else:
                self.statusBar().showMessage("设置已保存")

    def on_page_changed(self, page):
        self.search_videos(page=page)
    
    def update_page_navigation_label(self, page):
        """更新页码导航标签的文本"""
        self._update_page_label()

    def _update_search_history_ui(self):
        self.search_input.clear()
        self.search_input.addItems(self.settings.get("search_history", []))
        self.search_input.setCurrentText("")

    def _add_search_history(self, keyword):
        if not keyword:
            return
        history = self.settings.get("search_history", [])
        if keyword in history:
            history.remove(keyword)
        history.insert(0, keyword)
        self.settings["search_history"] = history[:10]
        self.save_settings()
        self._update_search_history_ui()
        self.search_input.setCurrentText(keyword)

    def search_videos(self, page=None):
        if not isinstance(page, int) or page <= 0:
            page = None
        keyword = self.search_input.currentText().strip()

        if keyword:
            video_link_pattern = r"https?://hanime1\.me/watch\?v=(\d+)"
            match = re.search(video_link_pattern, keyword)
            if match:
                video_id = match.group(1)
                self.statusBar().showMessage(f"正在获取视频 {video_id} 的信息...")
                self.current_search_results = []
                self.video_list.clear()
                self.get_video_info(video_id)
                return

        if page is None:
            if keyword:
                self._add_search_history(keyword)
            page = 1
            self.page_navigation.blockSignals(True)
            self.page_navigation.set_total_pages(1)
            self.page_navigation.set_current_page(1)
            self.page_navigation.blockSignals(False)

        self.statusBar().showMessage(f"正在搜索: {keyword} (第 {page} 页)...")
        worker = SearchWorker(self.api, keyword, page, self.filter_params)
        worker.signals.result.connect(self.on_search_complete)
        worker.signals.error.connect(self.on_search_error)
        self.threadpool.start(worker, priority=10)  # 搜索任务优先级设为 10

    def _update_page_label(self):
        """更新页码导航标签"""
        if hasattr(self, 'page_navigation_label'):
            page_info = self.page_navigation.get_page_info_text()
            self.page_navigation_label.setText(f"页码导航: {page_info}")

    def on_search_complete(self, search_result):
        if search_result and search_result["videos"]:
            self.current_search_results = search_result["videos"]
            self.video_list.clear()

            show_thumbnails = self.settings.get("show_thumbnails", False)
            if show_thumbnails:
                self.video_list.setIconSize(QSize(200, 112))

            for video in search_result["videos"]:
                item_text = f"[{video['video_id']}] {video['title']}"
                item = QListWidgetItem(item_text)

                if show_thumbnails and video.get("thumbnail"):
                    # 检查缓存
                    if video["thumbnail"] in self.thumbnail_cache:
                        item.setIcon(QIcon(self.thumbnail_cache[video["thumbnail"]]))
                    else:
                        # 异步加载
                        self._load_thumbnail_async(video["thumbnail"], item)

                self.video_list.addItem(item)

            self.page_navigation.set_total_pages(search_result.get("total_pages", 1))
            # 搜索完成后更新页码导航标签
            self._update_page_label()
            self.statusBar().showMessage(f"搜索完成，找到 {len(search_result['videos'])} 个结果")
        else:
            self.video_list.clear()
            self.page_navigation.set_total_pages(1)
            # 未找到视频结果时更新页码导航标签
            self._update_page_label()
            self.statusBar().showMessage("未找到视频结果")

    def _load_thumbnail_async(self, url, list_item):
        """异步加载缩略图"""

        class ThumbnailLoaderSignals(QObject):
            finished = pyqtSignal(bytes)

        class ThumbnailLoader(QRunnable):
            def __init__(self, url):
                super().__init__()
                self.url = url
                self.signals = ThumbnailLoaderSignals()

            @pyqtSlot()
            def run(self):
                try:
                    resp = requests.get(self.url, timeout=5)
                    if resp.status_code == 200:
                        self.signals.finished.emit(resp.content)
                except:
                    pass

        def on_loaded(data):
            # 检查设置是否仍然开启
            if not self.settings.get("show_thumbnails", False):
                return

            # 检查 list_item 是否已被 C++ 层销毁
            if sip.isdeleted(list_item):
                return

            # 检查 item 是否还属于某个列表
            if not list_item.listWidget():
                return

            pix = QPixmap()
            pix.loadFromData(data)
            if not pix.isNull():
                # 缩放并美化图片：添加圆角和边框
                target_size = QSize(200, 112)
                pix = pix.scaled(
                    target_size, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation
                )

                # 创建带圆角和边框的效果
                canvas = QPixmap(target_size)
                canvas.fill(Qt.transparent)

                painter = QPainter(canvas)
                painter.setRenderHint(QPainter.Antialiasing)
                painter.setRenderHint(QPainter.SmoothPixmapTransform)

                # 绘制圆角矩形裁剪区域
                path = QPainterPath()
                path.addRoundedRect(QRectF(0, 0, target_size.width(), target_size.height()), 8, 8)
                painter.setClipPath(path)

                # 居中绘制图片
                x = (target_size.width() - pix.width()) // 2
                y = (target_size.height() - pix.height()) // 2
                painter.drawPixmap(x, y, pix)

                # 绘制边框
                painter.setClipping(False)
                painter.setPen(QPen(QColor(200, 200, 200, 150), 2))
                painter.drawRoundedRect(
                    QRectF(1, 1, target_size.width() - 2, target_size.height() - 2), 8, 8
                )
                painter.end()

                self.thumbnail_cache[url] = canvas
                list_item.setIcon(QIcon(canvas))

        worker = ThumbnailLoader(url)
        worker.signals.finished.connect(on_loaded)
        self.threadpool.start(worker, priority=0)  # 缩略图加载优先级最低，设为 0

    def on_search_error(self, error):
        error_msg = str(error)
        if "Cloudflare" in error_msg:
            QMessageBox.warning(
                self,
                "搜索失败",
                "检测到 Cloudflare 验证拦截。\n\n请前往“设置”手动更新 Cloudflare Cookie。",
            )
        elif "certifi" in error_msg.lower() or "ssl" in error_msg.lower():
            QMessageBox.critical(self, "网络错误", f"SSL 证书验证失败。\n\n错误详情: {error_msg}")
        elif "zhconv" in error_msg.lower():
            QMessageBox.critical(
                self, "程序错误", f"繁简转换库 (zhconv) 运行出错。\n\n错误详情: {error_msg}"
            )
        else:
            QMessageBox.warning(self, "搜索出错", f"发生未知错误: {error_msg}")
        self.statusBar().showMessage(f"搜索出错: {error_msg}")

    def on_video_selected(self, item):
        index = self.video_list.row(item)
        if 0 <= index < len(self.current_search_results):
            video = self.current_search_results[index]
            self.get_video_info(video["video_id"], video["title"])

    def get_video_info(self, video_id, search_title=None):
        self.statusBar().showMessage(f"正在获取视频 {video_id} 的信息...")
        self.title_label.setText("加载中...")
        self.upload_date_label.setText("加载中...")
        self.likes_label.setText("加载中...")
        self.tags_label.setText("加载中...")
        self.description_text.setText("加载中...")
        self.current_cover_url = ""
        self.view_cover_button.setEnabled(False)
        self.related_list.clear()
        self.update_source_links([])

        # 获取当前显示设置
        visibility = self.settings.get("video_details_visibility", {})
        worker = GetVideoInfoWorker(self.api, video_id, visibility)
        worker.signals.result.connect(
            lambda result: self.on_video_info_complete(result, video_id, search_title)
        )
        worker.signals.error.connect(lambda error: self.on_video_info_error(error, video_id))
        self.threadpool.start(worker, priority=20)  # 详情获取优先级最高，设为 20

    def on_video_info_complete(self, video_info, video_id, search_title=None):
        if video_info:
            if search_title:
                video_info["title"] = search_title
            self.current_video_info = video_info
            self.title_label.setText(video_info["title"])
            self.upload_date_label.setText(video_info["upload_date"])
            self.likes_label.setText(video_info["likes"])

            # 清理标签中的 add/remove 并去重
            cleaned_tags = []
            if video_info.get("tags"):
                for tag in video_info["tags"]:
                    t = tag.replace("add", "").replace("remove", "").strip()
                    if t and t not in cleaned_tags:
                        cleaned_tags.append(t)
            self.tags_label.setText(", ".join(cleaned_tags))

            self.description_text.setText(video_info["description"])
            if video_info["thumbnail"]:
                self.current_cover_url = video_info["thumbnail"]
                self.view_cover_button.setEnabled(True)

            self.related_list.clear()
            current_video_index = -1
            for i, related in enumerate(video_info["series"]):
                related_id = related.get("video_id", "")
                self.related_list.addItem(
                    f"[{related_id}] {related.get('title', f'视频 {related_id}')}"
                )
                if related_id == video_id:
                    current_video_index = i

            if current_video_index >= 0:
                self.related_list.setCurrentRow(current_video_index)
                self.related_list.scrollToItem(
                    self.related_list.item(current_video_index), QListWidget.PositionAtCenter
                )

            self.update_source_links(video_info["video_sources"])
            if not self.current_search_results:
                self.current_search_results = [{"video_id": video_id, "title": video_info["title"]}]
                self.video_list.clear()
                self.video_list.addItem(f"[{video_id}] {video_info['title']}")
            self.statusBar().showMessage(f"视频 {video_id} 信息加载完成")
        else:
            self.statusBar().showMessage(f"无法获取视频 {video_id} 的信息")

    def on_video_info_error(self, error, video_id):
        self.statusBar().showMessage(f"获取视频 {video_id} 信息出错: {error}")

    def update_source_links(self, video_sources):
        for i in reversed(range(self.source_links_layout.count())):
            widget = self.source_links_layout.itemAt(i).widget()
            if widget:
                widget.deleteLater()
        for source in video_sources:
            link_widget = QWidget()
            link_layout = QHBoxLayout(link_widget)
            link_layout.setContentsMargins(0, 0, 0, 0)
            link_layout.addWidget(QLabel(f"画质: {source['quality']}"), 1)
            btn = QPushButton("下载")
            btn.clicked.connect(lambda checked, s=source: self.on_download_button_clicked(s))
            link_layout.addWidget(btn)
            self.source_links_layout.addWidget(link_widget)

    def on_download_button_clicked(self, source):
        if self.current_video_info:
            self.add_to_download_queue(self.current_video_info, source)

    def add_to_download_queue(self, video_info, source):
        safe_title = (
            re.sub(r'[\\/:*?"<>|]', "_", video_info["title"][:100]).strip(" _")
            or f"video_{video_info['video_id']}"
        )
        if any(
            d.get("video_id") == video_info["video_id"]
            and d["status"] in ["pending", "paused", "downloading"]
            for d in self.downloads
        ):
            self.statusBar().showMessage("该视频已在下载队列中")
            return
        download_task = {
            "video_id": video_info["video_id"],
            "title": video_info["title"],
            "url": source["url"],
            "status": "pending",
            "progress": 0,
            "size": 0,
            "total_size": 0,
            "priority": len(self.downloads),
            "retry_count": 0,
            "max_retries": 3,
        }
        self.downloads.append(download_task)
        self.update_download_list()
        self.statusBar().showMessage(f"视频 {video_info['title'][:20]}... 已添加到下载队列")

    def update_download_list(self):
        self.download_list.clear()
        any_downloading = False
        any_paused = False
        for download in self.downloads:
            if download["status"] == "downloading":
                any_downloading = True
            elif download["status"] == "paused":
                any_paused = True
            label_map = {
                "pending": "等待中",
                "downloading": "下载中",
                "paused": "已暂停",
                "completed": "已完成",
                "error": "出错",

            }
            base_label = label_map[download["status"]]
            if download["status"] == "downloading":
                base_label = f"{base_label} {int(download.get('progress', 0))}%"
            text = f"[{base_label}] [{download['video_id']}] {download['title'][:30]}"
            self.download_list.addItem(text)

        # 更新切换按钮文本: 开始 -> 暂停 -> 继续 -> 开始
        if any_downloading:
            self.toggle_download_button.setText("暂停下载")
        elif any_paused:
            self.toggle_download_button.setText("继续下载")
        else:
            self.toggle_download_button.setText("开始下载")

    def _update_toggle_button_state(self):
        any_downloading = any(d["status"] == "downloading" for d in self.downloads)
        any_paused = any(d["status"] == "paused" for d in self.downloads)
        if any_downloading:
            self.toggle_download_button.setText("暂停下载")
        elif any_paused:
            self.toggle_download_button.setText("继续下载")
        else:
            self.toggle_download_button.setText("开始下载")

    def _update_single_download_row_by_index(self, index):
        if 0 <= index < len(self.downloads) and index < self.download_list.count():
            d = self.downloads[index]
            label_map = {
                "pending": "等待中",
                "downloading": "下载中",
                "paused": "已暂停",
                "completed": "已完成",
                "error": "出错",

            }
            base_label = label_map[d["status"]]
            if d["status"] == "downloading":
                base_label = f"{base_label} {int(d.get('progress', 0))}%"
            text = f"[{base_label}] [{d['video_id']}] {d['title'][:30]}"
            item = self.download_list.item(index)
            if item:
                item.setText(text)

    def on_download_order_changed(self, selected_rows, target_index):
        """处理拖拽排序后的数据同步 (支持多选)"""
        if not selected_rows:
            return

        # 提取选中的项
        moved_items = [self.downloads[i] for i in selected_rows]

        # 按从大到小的顺序删除，避免索引变化
        for i in reversed(selected_rows):
            self.downloads.pop(i)

        # 计算插入位置
        # 如果插入位置在删除项之后，需要调整插入点
        adjustment = sum(1 for i in selected_rows if i < target_index)
        final_target = max(0, target_index - adjustment)

        # 插入项
        for i, item in enumerate(moved_items):
            self.downloads.insert(final_target + i, item)

        # 重新分配优先级并同步状态
        for i, d in enumerate(self.downloads):
            d["priority"] = i

        self.statusBar().showMessage(f"已调整 {len(moved_items)} 个任务的顺序", 2000)

    def on_toggle_download(self):
        """合并后的开始/暂停/恢复切换逻辑"""
        if not self._can_run_action("toggle"):
            return
        any_downloading = any(d["status"] == "downloading" for d in self.downloads)

        if any_downloading:
            # 如果正在下载，则全部暂停
            self.on_pause_download()
        else:
            # 如果没有正在下载的，则尝试开始或恢复
            any_paused = any(d["status"] == "paused" for d in self.downloads)
            if any_paused:
                self.on_resume_download()
            else:
                self.on_start_download()

    def on_start_download(self):
        max_simultaneous = self.settings.get("max_simultaneous_downloads", 2)
        available_slots = max_simultaneous - len(self.active_downloads)
        if available_slots <= 0:
            return
        started_count = 0
        for i, download in enumerate(self.downloads):
            if download["status"] in ["pending", "paused"]:
                self.start_download(i)
                started_count += 1
                if started_count >= available_slots:
                    break

    def start_download(self, index):
        if 0 <= index < len(self.downloads):
            download = self.downloads[index]
            if download["status"] in ["pending", "paused"]:
                safe_title = (
                    re.sub(r'[\\/:*?"<>|]', "_", download["title"][:100]).strip(" _")
                    or f"video_{download['video_id']}"
                )
                naming_rule = self.settings.get("file_naming_rule") or "{title}"
                try:
                    filename_core = naming_rule.format(
                        title=safe_title, video_id=download["video_id"]
                    )
                except Exception:
                    filename_core = safe_title
                filename = f"{filename_core}.mp4"
                download_path = self.settings.get(
                    "download_path", os.path.join(os.getcwd(), "hanimeDownload")
                )

                # 检查最终下载目录中是否已存在文件
                final_file = os.path.join(download_path, filename)
                if os.path.exists(final_file) and not self.settings.get(
                    "overwrite_existing", False
                ):
                    self.statusBar().showMessage(f"文件 {filename} 已存在，跳过下载")
                    del self.downloads[index]
                    self.update_download_list()
                    self.on_start_download()
                    return

                # 检查是否存在标题相同的视频文件（考虑仅标题保存格式的情况）
                if "{title}" in naming_rule:
                    # 获取安全标题
                    safe_title_only = re.sub(r'[\\/:*?"<>|]', "_", download["title"][:100]).strip(
                        " _"
                    )
                    if safe_title_only:
                        # 遍历下载目录中的所有mp4文件
                        if os.path.exists(download_path):
                            for existing_file in os.listdir(download_path):
                                if existing_file.endswith(".mp4"):
                                    # 提取文件名（不含扩展名）
                                    existing_name = os.path.splitext(existing_file)[0]
                                    # 检查是否标题相同
                                    if existing_name == safe_title_only:
                                        self.statusBar().showMessage(
                                            f"标题相同的视频 {existing_file} 已存在，跳过下载"
                                        )
                                        del self.downloads[index]
                                        self.update_download_list()
                                        self.on_start_download()
                                        return

                # 检查是否存在视频ID相同的视频文件
                if "{video_id}" in naming_rule or naming_rule == "{title}":
                    # 遍历下载目录中的所有mp4文件
                    if os.path.exists(download_path):
                        for existing_file in os.listdir(download_path):
                            if existing_file.endswith(".mp4"):
                                # 检查文件名中是否包含当前视频ID
                                if download["video_id"] in existing_file:
                                    self.statusBar().showMessage(
                                        f"视频ID相同的视频 {existing_file} 已存在，跳过下载"
                                    )
                                    del self.downloads[index]
                                    self.update_download_list()
                                    self.on_start_download()
                                    return

                # 检查临时目录中是否存在文件（可能是未完成的下载）
                temp_file = os.path.join(self.temp_download_dir, filename)
                if os.path.exists(temp_file):
                    # 检查临时文件大小是否合理
                    temp_size = os.path.getsize(temp_file)
                    if temp_size > 0:
                        self.statusBar().showMessage(f"发现未完成的下载，将尝试继续")

                num_threads = (
                    self.settings["num_threads"]
                    if self.settings["download_mode"] == "multi_thread"
                    else 1
                )
                # 获取已下载的大小，用于断点续传
                downloaded_size = download.get("size", 0)
                worker = DownloadWorker(
                    download["url"],
                    filename,
                    self.temp_download_dir,
                    num_threads,
                    self.api.session.headers,
                    self.api.session.cookies.get_dict(),
                    downloaded_size,
                )
                worker.video_id = download["video_id"]
                worker.signals.progress.connect(
                    lambda info, vid=worker.video_id: self.on_download_progress_by_id(info, vid)
                )
                worker.signals.finished.connect(
                    lambda vid=worker.video_id: self.on_download_finished_by_id(vid)
                )
                worker.signals.error.connect(
                    lambda err, vid=worker.video_id: self.on_download_error_by_id(err, vid)
                )

                # 更新下载任务状态
                self.downloads[index]["status"] = "downloading"
                self.downloads[index]["filename"] = filename
                self.downloads[index]["temp_path"] = os.path.join(self.temp_download_dir, filename)
                self.downloads[index]["final_dir"] = download_path

                # 更新UI和状态
                self.update_download_list()
                self.active_downloads[worker.video_id] = worker

                # 启动下载
                try:
                    # 如果是暂停后继续，使用现有的进度信息
                    if download.get("progress"):
                        self.on_download_progress_by_id(
                            {
                                "progress": download["progress"],
                                "size": download.get("size", 0),
                                "total_size": download.get("total_size", 0),
                            },
                            worker.video_id,
                        )
                    else:
                        self.on_download_progress_by_id(
                            {"progress": 0, "size": 0, "total_size": 0}, worker.video_id
                        )
                except:
                    pass

                self.threadpool.start(worker, priority=5)
                if download["status"] == "paused":
                    self.statusBar().showMessage(f"继续下载视频 {download['title'][:20]}...")
                else:
                    self.statusBar().showMessage(f"开始下载视频 {download['title'][:20]}...")

    def on_download_progress_by_id(self, progress_info, video_id):
        for i, download in enumerate(self.downloads):
            if download.get("video_id") == video_id:
                self.downloads[i].update(
                    {
                        "progress": progress_info["progress"],
                        "size": progress_info["size"],
                        "total_size": progress_info["total_size"],
                    }
                )
                self._update_single_download_row_by_index(i)
                self._update_toggle_button_state()
                self.calculate_and_update_overall_progress()
                break

    def set_progress_bar_status(self, status):
        """设置进度条状态，显示不同颜色"""
        if status == "downloading":
            color = "#1890ff"
        elif status == "completed":
            color = "#52c41a"
        elif status == "error":
            color = "#ff4d4f"
        elif status == "paused":
            color = "#faad14"
        else:
            color = "#bfbfbf"

        # 动态更新进度条样式
        self.download_progress.setStyleSheet(f""".QProgressBar {{ 
            border: 1px solid #d9d9d9;
            border-radius: 8px;
            background-color: #f5f5f5;
            height: 16px;
            text-align: center;
            color: #333;
        }}
        .QProgressBar::chunk {{ 
            background-color: {color};
            border-radius: 7px;
        }}""")

    def update_progress_smooth(self):
        """平滑更新进度条"""
        # 计算当前进度与目标进度的差异
        diff = abs(self.current_progress - self.target_progress)

        # 根据差异大小调整更新步长，提高性能
        if diff > 20:
            step = 5
        elif diff > 10:
            step = 3
        else:
            step = 1

        if self.current_progress < self.target_progress:
            self.current_progress = min(self.current_progress + step, self.target_progress)
            self.download_progress.setValue(self.current_progress)
        elif self.current_progress > self.target_progress:
            self.current_progress = max(self.current_progress - step, self.target_progress)
            self.download_progress.setValue(self.current_progress)
        else:
            if self.progress_timer:
                self.progress_timer.stop()
                self.progress_timer.deleteLater()
                self.progress_timer = None

    def calculate_and_update_overall_progress(self):
        total_downloaded = sum(
            d.get("size", 0) for d in self.downloads if d["status"] == "downloading"
        )
        total_size = sum(
            d.get("total_size", 1) for d in self.downloads if d["status"] == "downloading"
        )
        active_count = sum(1 for d in self.downloads if d["status"] == "downloading")

        # 计算当前总速度
        total_speed = 0
        for vid, worker in self.active_downloads.items():
            if hasattr(worker, "current_speed"):
                total_speed += worker.current_speed

        if active_count > 0:
            percent = int((total_downloaded / total_size) * 100) if total_size > 0 else 0
            self.target_progress = percent
            # 设置进度条状态为下载中
            self.set_progress_bar_status("downloading")
            # 启动平滑更新
            if not self.progress_timer:
                from PyQt5.QtCore import QTimer

                self.progress_timer = QTimer(self)
                self.progress_timer.timeout.connect(self.update_progress_smooth)
                self.progress_timer.start(20)  # 每20ms更新一次，实现平滑动画

            # 格式化速度显示
            speed_text = (
                f"{total_speed/1024/1024:.1f} MB/s"
                if total_speed > 1024 * 1024
                else f"{total_speed/1024:.1f} KB/s"
            )

            self.download_info.setText(
                f"正在下载: {active_count} 个任务 | "
                f"速度: {speed_text} | "
                f"已完成: {total_downloaded/1024/1024:.1f}MB / {total_size/1024/1024:.1f}MB"
            )
        else:
            pending_count = sum(1 for d in self.downloads if d["status"] == "pending")
            paused_count = sum(1 for d in self.downloads if d["status"] == "paused")
            error_count = sum(1 for d in self.downloads if d["status"] == "error")

            # 根据状态设置进度条颜色
            if paused_count > 0:
                self.set_progress_bar_status("paused")
            elif error_count > 0:
                self.set_progress_bar_status("error")
            else:
                self.set_progress_bar_status("idle")

            self.target_progress = 0
            # 启动平滑更新
            if not self.progress_timer:
                from PyQt5.QtCore import QTimer

                self.progress_timer = QTimer(self)
                self.progress_timer.timeout.connect(self.update_progress_smooth)
                self.progress_timer.start(20)

            status_parts = []
            if pending_count > 0:
                status_parts.append(f"{pending_count} 个任务等待中")
            if paused_count > 0:
                status_parts.append(f"{paused_count} 个任务已暂停")

            self.download_info.setText(" | ".join(status_parts) if status_parts else "准备下载")

    def on_download_finished_by_id(self, video_id):
        task_index = next(
            (i for i, d in enumerate(self.downloads) if d.get("video_id") == video_id), -1
        )
        if task_index != -1:
            download = self.downloads.pop(task_index)
            if video_id in self.active_downloads:
                del self.active_downloads[video_id]
            try:
                final_dir = download.get("final_dir") or self.settings.get(
                    "download_path", os.path.join(os.getcwd(), "hanimeDownload")
                )
                os.makedirs(final_dir, exist_ok=True)
                temp_file = download.get("temp_path") or os.path.join(
                    self.temp_download_dir, download.get("filename", "")
                )
                final_file = os.path.join(final_dir, download.get("filename", ""))
                if temp_file and os.path.exists(temp_file):
                    # 确保目标目录存在
                    os.makedirs(os.path.dirname(final_file), exist_ok=True)
                    # 使用shutil.move移动文件
                    shutil.move(temp_file, final_file)
                    self.statusBar().showMessage(f"视频已移动到: {final_file}")
                else:
                    self.statusBar().showMessage(f"临时文件不存在: {temp_file}")
            except Exception as e:
                self.statusBar().showMessage(f"文件移动失败: {str(e)}")
            self.download_history.append(
                {
                    "video_id": download["video_id"],
                    "title": download["title"],
                    "filename": download.get("filename", ""),
                    "download_date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                }
            )
            self.save_download_history()
            self.update_history_list()
            self.update_download_list()
            # 强制重置进度条状态
            self.current_progress = 0
            self.target_progress = 0
            if self.progress_timer:
                self.progress_timer.stop()
                self.progress_timer.deleteLater()
                self.progress_timer = None
            self.download_progress.setValue(0)
            self.calculate_and_update_overall_progress()
            self.on_start_download()
            self.statusBar().showMessage(f"视频 {download['title'][:20]}... 下载完成")

    def on_download_error_by_id(self, error, video_id):
        for i, download in enumerate(self.downloads):
            if download.get("video_id") == video_id:
                retry_count = download.get("retry_count", 0) + 1
                self.downloads[i].update({"retry_count": retry_count, "error": str(error)})
                if video_id in self.active_downloads:
                    del self.active_downloads[video_id]
                self.update_download_list()
                self.calculate_and_update_overall_progress()
                if retry_count < download.get("max_retries", 3):
                    self.downloads[i]["status"] = "pending"
                    self.check_and_retry_failed_downloads()
                else:
                    self.downloads[i]["status"] = "error"
                break

    def check_and_retry_failed_downloads(self):
        max_simultaneous = self.settings.get("max_simultaneous_downloads", 2)
        available_slots = max_simultaneous - len(self.active_downloads)
        if available_slots <= 0:
            return
        retry_tasks = sorted(
            [
                i
                for i, d in enumerate(self.downloads)
                if d["status"] == "pending" and d.get("retry_count", 0) > 0
            ],
            key=lambda i: self.downloads[i]["retry_count"],
        )
        for i in retry_tasks[:available_slots]:
            worker = GetVideoInfoWorker(
                self.api, self.downloads[i]["video_id"], None
            )  # 下载重试需要完整信息
            worker.signals.result.connect(
                lambda info, idx=i: self.on_video_info_for_retry(info, idx)
            )
            self.threadpool.start(worker, priority=20)

    def on_video_info_for_retry(self, video_info, index):
        if video_info and video_info["video_sources"]:
            quality = self.settings.get("download_quality", "最高")
            source = (
                video_info["video_sources"][0]
                if quality == "最高"
                else video_info["video_sources"][-1]
            )
            self.downloads[index].update({"url": source["url"], "status": "downloading"})
            self.start_download(index)

    def on_pause_download(self):
        if not self._can_run_action("pause"):
            return

        # 暂停所有active_downloads中的worker
        for vid, worker in list(self.active_downloads.items()):
            worker.pause()
            for i, d in enumerate(self.downloads):
                if d.get("video_id") == vid:
                    self.downloads[i]["status"] = "paused"

        # 清空active_downloads，因为所有worker都已暂停
        self.active_downloads.clear()

        self.update_download_list()
        paused_count = sum(1 for d in self.downloads if d["status"] == "paused")
        self.download_info.setText(f"所有下载已暂停 - 已暂停: {paused_count} 个任务")

    def on_resume_download(self):
        if not self._can_run_action("resume"):
            return

        # 首先检查是否有暂停的任务
        paused_tasks = [i for i, d in enumerate(self.downloads) if d["status"] == "paused"]
        if not paused_tasks:
            self.statusBar().showMessage("没有暂停的下载任务")
            return

        # 计算可用槽位
        max_simultaneous = self.settings.get("max_simultaneous_downloads", 2)
        available_slots = max_simultaneous - len(self.active_downloads)
        if available_slots <= 0:
            self.statusBar().showMessage("没有可用的下载槽位")
            self.update_download_list()
            return

        # 重新启动暂停的任务
        started_count = 0
        for i in paused_tasks:
            download = self.downloads[i]
            if download["status"] == "paused":
                # 重新启动暂停的任务
                self.start_download(i)
                started_count += 1
                if started_count >= available_slots:
                    break

        self.update_download_list()
        self.calculate_and_update_overall_progress()
        self.statusBar().showMessage(f"已继续下载 {started_count} 个任务")





    def _ensure_temp_download_dir(self):
        try:
            import ctypes
            
            os.makedirs(self.temp_download_dir, exist_ok=True)
            if os.name == "nt":
                FILE_ATTRIBUTE_HIDDEN = 0x02
                ctypes.windll.kernel32.SetFileAttributesW(
                    self.temp_download_dir, FILE_ATTRIBUTE_HIDDEN
                )
        except:
            pass

    def _clear_temp_download_folder(self):
        try:
            if os.path.exists(self.temp_download_dir):
                for name in os.listdir(self.temp_download_dir):
                    path = os.path.join(self.temp_download_dir, name)
                    try:
                        if os.path.isfile(path) or os.path.islink(path):
                            os.remove(path)
                        elif os.path.isdir(path):
                            shutil.rmtree(path)
                    except:
                        pass
        except:
            pass



    def on_clear_download_list(self):
        if not self._can_run_action("clear"):
            return
        active_vids = set(self.active_downloads.keys())
        self.downloads = [d for d in self.downloads if d.get("video_id") in active_vids]
        for i, d in enumerate(self.downloads):
            d["priority"] = i
        self.update_download_list()
        self.calculate_and_update_overall_progress()

    def _can_run_action(self, name, min_interval_ms=300):
        now = int(time.time() * 1000)
        last = self._last_action_time.get(name, 0)
        if now - last < min_interval_ms:
            return False
        self._last_action_time[name] = now
        return True

    def _probe_content_length(self, url):
        try:
            resp = requests.head(
                url,
                headers=self.api.session.headers,
                cookies=self.api.session.cookies.get_dict(),
                timeout=10,
            )
            cl = resp.headers.get("content-length")
            return int(cl) if cl else 0
        except:
            return 0

    def _has_enough_space(self, required_bytes):
        try:
            usage = shutil.disk_usage(self.temp_download_dir)
            margin = 100 * 1024 * 1024
            return usage.free >= required_bytes + margin
        except:
            return True

    def show_video_context_menu(self, pos):
        if self.video_list.selectedItems():
            menu = QMenu(self)
            menu.addAction("下载").triggered.connect(
                lambda: self.on_download_from_menu(self.video_list.selectedItems())
            )
            menu.addAction("添加到收藏夹").triggered.connect(
                lambda: self.on_add_to_favorites_from_menu(self.video_list.selectedItems())
            )
            menu.exec_(self.video_list.viewport().mapToGlobal(pos))

    def show_related_video_context_menu(self, pos):
        if self.related_list.selectedItems():
            menu = QMenu(self)
            menu.addAction("下载").triggered.connect(
                lambda: self.on_download_from_menu(self.related_list.selectedItems())
            )
            menu.addAction("添加到收藏夹").triggered.connect(
                lambda: self.on_add_to_favorites_from_menu(self.related_list.selectedItems())
            )
            menu.exec_(self.related_list.viewport().mapToGlobal(pos))

    def on_download_from_menu(self, items):
        for item in items:
            match = re.search(r"\[(\d+)\]\s*(.+)", item.text())
            if match:
                video_id = match.group(1)
                list_title = match.group(2)
                worker = GetVideoInfoWorker(self.api, video_id, None)  # 菜单下载需要完整信息
                worker.signals.result.connect(lambda result, title=list_title: self.on_video_info_for_download(result, title))
                self.threadpool.start(worker, priority=20)

    def on_video_info_for_download(self, video_info, list_title=None):
        if video_info and video_info["video_sources"]:
            # 使用列表中的标题而不是详细信息的标题
            if list_title:
                video_info["title"] = list_title
            quality = self.settings.get("download_quality", "最高")
            source = (
                video_info["video_sources"][0]
                if quality == "最高"
                else video_info["video_sources"][-1]
            )
            self.add_to_download_queue(video_info, source)

    def load_favorites(self):
        if os.path.exists(self.favorites_file):
            try:
                with open(self.favorites_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.favorites = {"默认收藏夹": data} if isinstance(data, list) else data
            except:
                self.favorites = {"默认收藏夹": []}
        else:
            self.favorites = {"默认收藏夹": []}
        self.update_folder_combobox()

    def save_favorites(self):
        try:
            with open(self.favorites_file, "w", encoding="utf-8") as f:
                json.dump(self.favorites, f, ensure_ascii=False, indent=2)
        except:
            pass

    def update_favorites_list(self):
        if hasattr(self, "_original_favorites"):
            delattr(self, "_original_favorites")
        self.favorites_list.clear()
        folder = self.current_favorite_folder
        if folder not in self.favorites:
            self.favorites[folder] = []

        show_thumbnails = self.settings.get("show_thumbnails", False)
        if show_thumbnails:
            self.favorites_list.setIconSize(QSize(200, 112))

        for fav in self.favorites[folder]:
            item = QListWidgetItem(f"[{fav['video_id']}] {fav['title']}")

            if show_thumbnails and fav.get("thumbnail"):
                if fav["thumbnail"] in self.thumbnail_cache:
                    item.setIcon(QIcon(self.thumbnail_cache[fav["thumbnail"]]))
                else:
                    self._load_thumbnail_async(fav["thumbnail"], item)

            self.favorites_list.addItem(item)

    def update_folder_combobox(self):
        self.folder_combobox.blockSignals(True)
        cur = self.folder_combobox.currentText()
        self.folder_combobox.clear()
        for name in self.favorites:
            self.folder_combobox.addItem(name)
        if cur in self.favorites:
            self.folder_combobox.setCurrentText(cur)
        elif self.favorites:
            self.folder_combobox.setCurrentIndex(0)
            self.current_favorite_folder = self.folder_combobox.currentText()
        self.folder_combobox.blockSignals(False)
        self.update_favorites_list()

    def on_folder_changed(self, name):
        if name:
            self.current_favorite_folder = name
            self.update_favorites_list()

    def create_custom_input_dialog(self, title, label, default_text=""):
        """创建自定义输入对话框，设置固定大小和中文按钮"""
        dialog = QDialog(self)
        dialog.setWindowTitle(title)
        dialog.setFixedSize(300, 180)
        
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        label_widget = QLabel(label)
        layout.addWidget(label_widget)
        
        input_widget = QLineEdit(default_text)
        layout.addWidget(input_widget)
        
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        cancel_button = QPushButton("取消")
        cancel_button.clicked.connect(dialog.reject)
        button_layout.addWidget(cancel_button)
        
        confirm_button = QPushButton("确认")
        confirm_button.setObjectName("primary_btn")
        confirm_button.clicked.connect(dialog.accept)
        button_layout.addWidget(confirm_button)
        
        layout.addLayout(button_layout)
        
        if dialog.exec_() == QDialog.Accepted:
            return input_widget.text(), True
        else:
            return "", False
    
    def create_custom_choice_dialog(self, title, label, items):
        """创建自定义选择对话框，设置固定大小和中文按钮"""
        dialog = QDialog(self)
        dialog.setWindowTitle(title)
        dialog.setFixedSize(350, 180)
        
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        label_widget = QLabel(label)
        layout.addWidget(label_widget)
        
        combo_box = QComboBox()
        combo_box.addItems(items)
        layout.addWidget(combo_box)
        
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        cancel_button = QPushButton("取消")
        cancel_button.clicked.connect(dialog.reject)
        button_layout.addWidget(cancel_button)
        
        confirm_button = QPushButton("确认")
        confirm_button.setObjectName("primary_btn")
        confirm_button.clicked.connect(dialog.accept)
        button_layout.addWidget(confirm_button)
        
        layout.addLayout(button_layout)
        
        if dialog.exec_() == QDialog.Accepted:
            return combo_box.currentText(), True
        else:
            return "", False
    
    def on_new_folder(self):
        name, ok = self.create_custom_input_dialog("新建收藏夹", "请输入名称:")
        if ok and name.strip() and name.strip() not in self.favorites:
            self.favorites[name.strip()] = []
            self.save_favorites()
            self.update_folder_combobox()
            self.folder_combobox.setCurrentText(name.strip())

    def on_delete_folder(self):
        cur = self.folder_combobox.currentText()
        if cur == "默认收藏夹":
            QMessageBox.information(self, "提示", "默认收藏夹不能删除")
            return
        if (
            QMessageBox.question(
                self, "确认删除", f"确定删除 '{cur}' 吗？", QMessageBox.Yes | QMessageBox.No
            )
            == QMessageBox.Yes
        ):
            if cur in self.favorites:
                del self.favorites[cur]
                self.save_favorites()
                self.update_folder_combobox()

    def on_rename_folder(self):
        cur = self.folder_combobox.currentText()
        name, ok = self.create_custom_input_dialog("重命名", f"重命名 '{cur}' 为:", cur)
        if ok and name.strip() and name.strip() != cur and name.strip() not in self.favorites:
            self.favorites[name.strip()] = self.favorites.pop(cur)
            self.save_favorites()
            self.update_folder_combobox()
            self.folder_combobox.setCurrentText(name.strip())

    def on_favorites_search(self, text):
        if not hasattr(self, "_original_favorites"):
            self._original_favorites = self.favorites.get(self.current_favorite_folder, [])
        self.favorites_list.clear()
        search = text.lower()

        show_thumbnails = self.settings.get("show_thumbnails", False)

        for fav in self._original_favorites:
            if not search or search in fav["title"].lower() or search in fav.get("video_id", ""):
                item = QListWidgetItem(f"[{fav['video_id']}] {fav['title']}")

                if show_thumbnails and fav.get("thumbnail"):
                    if fav["thumbnail"] in self.thumbnail_cache:
                        item.setIcon(QIcon(self.thumbnail_cache[fav["thumbnail"]]))
                    else:
                        self._load_thumbnail_async(fav["thumbnail"], item)

                self.favorites_list.addItem(item)

    def on_export_favorites(self):
        menu = QMenu(self)
        cur_act = menu.addAction("导出当前收藏夹 (.json)")
        all_act = menu.addAction("导出全部收藏夹 (.json)")
        # 菜单显示在按钮正下方
        act = menu.exec_(self.sender().mapToGlobal(self.sender().rect().bottomLeft()))
        if not act:
            return
        data = (
            {self.current_favorite_folder: self.favorites[self.current_favorite_folder]}
            if act == cur_act
            else self.favorites
        )
        path, _ = QFileDialog.getSaveFileName(
            self,
            "导出",
            f"{'favorites' if act == all_act else self.current_favorite_folder}.json",
            "JSON (*.json)",
        )
        if path:
            try:
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
            except:
                pass

    def on_import_favorites(self):
        path, _ = QFileDialog.getOpenFileName(self, "导入", "", "JSON (*.json)")
        if path:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    imported = json.load(f)
                for name, vids in imported.items():
                    if name in self.favorites:
                        btn = QMessageBox.warning(
                            self, "冲突", f"'{name}' 已存在", "合并", "重命名", "取消"
                        )
                        if btn == 0:
                            exist_ids = {v["video_id"] for v in self.favorites[name]}
                            self.favorites[name].extend(
                                [v for v in vids if v["video_id"] not in exist_ids]
                            )
                        elif btn == 1:
                            new_name, ok = QInputDialog.getText(self, "重命名", "新名称:")
                            if ok and new_name.strip():
                                self.favorites[new_name.strip()] = vids
                    else:
                        self.favorites[name] = vids
                self.save_favorites()
                self.update_folder_combobox()
            except:
                pass

    def show_favorite_context_menu(self, pos):
        if self.favorites_list.selectedItems():
            menu = QMenu(self)
            menu.addAction("查看信息").triggered.connect(
                lambda: self.on_view_favorite_info(self.favorites_list.selectedItems())
            )
            menu.addAction("下载").triggered.connect(
                lambda: self.on_download_favorite(self.favorites_list.selectedItems())
            )
            menu.addAction("移除").triggered.connect(
                lambda: self.on_remove_from_favorites(self.favorites_list.selectedItems())
            )
            menu.exec_(self.favorites_list.viewport().mapToGlobal(pos))

    def on_add_to_favorites_from_menu(self, items):
        names = list(self.favorites.keys())
        folder, ok = self.create_custom_choice_dialog("选择收藏夹", "选择:", names)
        if ok and folder:
            for item in items:
                match = re.search(r"\[(\d+)]\s*(.+)", item.text())
                if match:
                    vid, title = match.groups()
                    if not any(f["video_id"] == vid for f in self.favorites[folder]):
                        # 尝试从搜索结果中找缩略图
                        thumbnail = ""
                        for v in self.current_search_results:
                            if v["video_id"] == vid:
                                thumbnail = v.get("thumbnail", "")
                                break
                        self.favorites[folder].append(
                            {
                                "video_id": vid,
                                "title": title,
                                "thumbnail": thumbnail,
                                "url": f"https://hanime1.me/watch?v={vid}",
                            }
                        )
            self.save_favorites()
            self.update_favorites_list()

    def on_remove_from_favorites(self, items):
        vids = [
            re.search(r"\[(\d+)]", i.text()).group(1)
            for i in items
            if re.search(r"\[(\d+)]", i.text())
        ]
        if vids and self.current_favorite_folder in self.favorites:
            self.favorites[self.current_favorite_folder] = [
                f for f in self.favorites[self.current_favorite_folder] if f["video_id"] not in vids
            ]
            self.save_favorites()
            self.update_favorites_list()

    def on_favorite_selected(self, item):
        match = re.search(r"\[(\d+)]", item.text())
        if match:
            self.get_video_info(match.group(1))

    def on_view_favorite_info(self, items):
        match = re.search(r"\[(\d+)]", items[0].text())
        if match:
            self.get_video_info(match.group(1))

    def on_download_favorite(self, items):
        for i in items:
            match = re.search(r"\[(\d+)]", i.text())
            if match:
                worker = GetVideoInfoWorker(
                    self.api, match.group(1), None
                )  # 收藏夹下载需要完整信息
                worker.signals.result.connect(self.on_video_info_for_download)
                self.threadpool.start(worker, priority=20)

    def show_download_context_menu(self, pos):
        selected_items = self.download_list.selectedItems()
        if selected_items:
            menu = QMenu(self)

            # 检查是否有正在下载的项
            has_downloading = any(self.downloads[self.download_list.row(item)]["status"] == "downloading" for item in selected_items)
            # 检查是否有可开始/恢复的项
            has_startable = any(self.downloads[self.download_list.row(item)]["status"] in ["pending", "paused"] for item in selected_items)

            if has_downloading:
                menu.addAction("暂停选中项").triggered.connect(
                    lambda: self.on_pause_selected_downloads(selected_items)
                )
            if has_startable:
                menu.addAction("开始/恢复选中项").triggered.connect(
                    lambda: self.on_start_selected_downloads(selected_items)
                )

            menu.addAction("移除选中项").triggered.connect(
                lambda: self.on_remove_selected_downloads(selected_items)
            )
            menu.exec_(self.download_list.viewport().mapToGlobal(pos))

    def on_pause_download_from_menu(self, item):
        idx = self.download_list.row(item)
        vid = self.downloads[idx]["video_id"]
        if vid in self.active_downloads:
            self.active_downloads[vid].pause()
            self.downloads[idx]["status"] = "paused"
            self.update_download_list()

    def on_resume_download_from_menu(self, item):
        idx = self.download_list.row(item)
        vid = self.downloads[idx]["video_id"]
        if vid in self.active_downloads:
            self.active_downloads[vid].resume()
            self.downloads[idx]["status"] = "downloading"
            self.update_download_list()



    def on_remove_from_download_queue(self, item):
        idx = self.download_list.row(item)
        vid = self.downloads[idx]["video_id"]
        if vid in self.active_downloads:
            del self.active_downloads[vid]
        self.downloads.pop(idx)
        self.update_download_list()

    def on_pause_selected_downloads(self, items):
        for item in items:
            idx = self.download_list.row(item)
            if 0 <= idx < len(self.downloads):
                download = self.downloads[idx]
                if download["status"] == "downloading":
                    vid = download["video_id"]
                    if vid in self.active_downloads:
                        self.active_downloads[vid].pause()
                        download["status"] = "paused"
        self.update_download_list()

    def on_start_selected_downloads(self, items):
        for item in items:
            idx = self.download_list.row(item)
            if 0 <= idx < len(self.downloads):
                download = self.downloads[idx]
                if download["status"] in ["pending", "paused"]:
                    self.start_download(idx)



    def on_remove_selected_downloads(self, items):
        # 按索引从大到小排序，避免删除时索引变化
        indices = sorted([self.download_list.row(item) for item in items], reverse=True)
        for idx in indices:
            if 0 <= idx < len(self.downloads):
                vid = self.downloads[idx]["video_id"]
                if vid in self.active_downloads:
                    del self.active_downloads[vid]
                self.downloads.pop(idx)
        self.update_download_list()
        self.calculate_and_update_overall_progress()

    def load_download_history(self):
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, "r", encoding="utf-8") as f:
                    self.download_history = json.load(f)
            except:
                self.download_history = []

    def save_download_history(self):
        try:
            with open(self.history_file, "w", encoding="utf-8") as f:
                json.dump(self.download_history, f, ensure_ascii=False, indent=2)
        except:
            pass

    def update_history_list(self):
        self.history_list.clear()
        for item in reversed(self.download_history):
            self.history_list.addItem(
                f"[{item['video_id']}] {item['title'][:30]}... - {item['download_date']}"
            )

    def refresh_download_history(self):
        self.load_download_history()
        self.update_history_list()

    def clear_download_history(self):
        if (
            QMessageBox.question(self, "清空", "确定清空历史？", QMessageBox.Yes | QMessageBox.No)
            == QMessageBox.Yes
        ):
            self.download_history = []
            self.save_download_history()
            self.update_history_list()

    def show_history_context_menu(self, pos):
        if self.history_list.selectedItems():
            menu = QMenu(self)
            menu.addAction("查看信息").triggered.connect(
                lambda: self.on_view_history_video_info(self.history_list.selectedItems())
            )
            menu.exec_(self.history_list.viewport().mapToGlobal(pos))

    def on_view_history_video_info(self, items):
        match = re.search(r"\[(\d+)\]", items[0].text())
        if match:
            self.get_video_info(match.group(1))

    def show_cover(self):
        """显示封面图片（程序内弹窗）"""
        if not self.current_cover_url:
            return

        # 创建弹窗
        cover_dialog = QDialog(self)
        cover_dialog.setWindowTitle("封面预览")
        cover_dialog.setMinimumSize(400, 500)
        # 不设置最大尺寸，允许自由放大

        # 创建布局并设置边距为0，确保图片填满整个窗口
        layout = QVBoxLayout(cover_dialog)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 创建标签用于显示图片
        cover_label = QLabel()
        cover_label.setAlignment(Qt.AlignCenter)
        cover_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        cover_label.setScaledContents(False)  # 不自动缩放内容，我们手动控制
        cover_label.setText("正在加载封面...")
        layout.addWidget(cover_label)

        # 显示弹窗（非阻塞模式）
        cover_dialog.show()

        # 创建信号类用于线程间通信
        class CoverLoaderSignals(QObject):
            finished = pyqtSignal(bytes)
            error = pyqtSignal(str)

        # 创建封面加载工作线程
        class CoverLoader(QRunnable):
            def __init__(self, url):
                super().__init__()
                self.url = url
                self.signals = CoverLoaderSignals()

            @pyqtSlot()
            def run(self):
                try:
                    # 在后台线程下载封面图片
                    response = requests.get(self.url, timeout=10)
                    response.raise_for_status()
                    self.signals.finished.emit(response.content)
                except Exception as e:
                    self.signals.error.emit(str(e))

        # 定义图片缩放函数
        def scale_image_to_fit():
            if hasattr(cover_label, "_original_pixmap"):
                # 获取标签可用大小
                label_size = cover_label.size()
                if label_size.width() > 0 and label_size.height() > 0:
                    # 缩放图片以适应标签大小，保持比例
                    scaled_pixmap = cover_label._original_pixmap.scaled(
                        label_size, Qt.KeepAspectRatio, Qt.SmoothTransformation
                    )
                    cover_label.setPixmap(scaled_pixmap)

        # 下载完成处理函数
        def on_cover_loaded(image_data):
            try:
                # 加载图片到QPixmap
                pixmap = QPixmap()
                pixmap.loadFromData(image_data)

                if not pixmap.isNull():
                    # 保存原始pixmap
                    cover_label._original_pixmap = pixmap

                    # 获取图片宽高比
                    image_width = pixmap.width()
                    image_height = pixmap.height()
                    aspect_ratio = image_width / image_height

                    # 设置对话框初始大小为图片原始大小，但不超过屏幕一半
                    screen = QApplication.primaryScreen().size()
                    max_width = int(screen.width() * 0.8)
                    max_height = int(screen.height() * 0.8)

                    # 计算初始大小
                    initial_width = min(image_width, max_width)
                    initial_height = min(int(initial_width / aspect_ratio), max_height)

                    # 调整初始大小以匹配宽高比
                    cover_dialog.resize(initial_width, initial_height)

                    # 首次缩放图片
                    scale_image_to_fit()

                    # 使用事件过滤器来监听resize事件
                    def event_filter(obj, event):
                        if event.type() == QEvent.Resize:
                            scale_image_to_fit()
                        return False

                    cover_dialog.installEventFilter(cover_dialog)
                    cover_dialog.eventFilter = event_filter

                else:
                    cover_label.setText("无法加载图片")
            except Exception as e:
                cover_label.setText(f"加载失败: {str(e)}")

        # 下载错误处理函数
        def on_cover_error(error_msg):
            cover_label.setText(f"加载失败: {error_msg}")
            QMessageBox.warning(self, "错误", f"无法加载封面图片: {error_msg}")

        # 创建并启动工作线程
        worker = CoverLoader(self.current_cover_url)
        worker.signals.finished.connect(on_cover_loaded)
        worker.signals.error.connect(on_cover_error)

        # 使用实例线程池执行任务，优先级设为 15 (高于缩略图)
        self.threadpool.start(worker, priority=15)

    def on_related_video_clicked(self, item):
        match = re.search(r"\[(\d+)]\s*(.+)", item.text())
        if match:
            self.get_video_info(match.group(1), match.group(2))
