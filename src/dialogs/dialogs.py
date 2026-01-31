"""
Dialogs for Hanime1VideoTool
"""

import json
import os

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSpinBox,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from src.constants.constants import TAG_CATEGORIES, TAG_MAPPING
from src.widgets.widgets import ChineseLineEdit, ChineseTextEdit


class FilterDialog(QDialog):
    def __init__(self, filter_params, parent=None):
        super().__init__(parent)
        # 设置窗口标志，禁用上下文帮助按钮
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self.filter_params = filter_params.copy()
        # 设置默认值
        self.default_params = {
            "genre": "",
            "sort": "",
            "date": "",
            "duration": "",
            "tags": [],
            "broad": False,
        }
        # 合并默认设置
        for key, value in self.default_params.items():
            if key not in self.filter_params:
                self.filter_params[key] = value
        self.parent = parent
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("筛选设置")
        self.setGeometry(300, 300, 600, 800)

        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(16)
        main_layout.setContentsMargins(16, 16, 16, 16)

        # 影片类型
        genre_group = QGroupBox("影片类型")
        genre_layout = QVBoxLayout(genre_group)

        self.genre_combo = QComboBox()
        self.genre_combo.addItem("全部", "")
        self.genre_combo.addItem("里番", "裏番")
        self.genre_combo.addItem("泡面番", "泡麵番")
        self.genre_combo.addItem("Motion Anime", "Motion Anime")
        self.genre_combo.addItem("3DCG", "3DCG")
        self.genre_combo.addItem("2.5D", "2.5D")
        self.genre_combo.addItem("2D动画", "2D動畫")
        self.genre_combo.addItem("AI生成", "AI生成")
        self.genre_combo.addItem("MMD", "MMD")
        self.genre_combo.addItem("Cosplay", "Cosplay")

        # 设置当前选中的类型
        current_genre = self.filter_params.get("genre", "")
        index = self.genre_combo.findData(current_genre)
        if index != -1:
            self.genre_combo.setCurrentIndex(index)

        genre_layout.addWidget(self.genre_combo)
        main_layout.addWidget(genre_group)

        # 排序方式
        sort_group = QGroupBox("排序方式")
        sort_layout = QVBoxLayout(sort_group)

        self.sort_combo = QComboBox()
        self.sort_combo.addItem("默认", "")
        self.sort_combo.addItem("最新上市", "最新上市")
        self.sort_combo.addItem("最新上传", "最新上傳")
        self.sort_combo.addItem("本日排行", "本日排行")
        self.sort_combo.addItem("本周排行", "本週排行")
        self.sort_combo.addItem("本月排行", "本月排行")
        self.sort_combo.addItem("观看次数", "觀看次數")
        self.sort_combo.addItem("点赞比例", "讚好比例")
        self.sort_combo.addItem("时长最长", "時長最長")
        self.sort_combo.addItem("他们在看", "他們在看")

        # 设置当前选中的排序方式
        current_sort = self.filter_params.get("sort", "")
        index = self.sort_combo.findData(current_sort)
        if index != -1:
            self.sort_combo.setCurrentIndex(index)

        sort_layout.addWidget(self.sort_combo)
        main_layout.addWidget(sort_group)

        # 发布日期
        date_group = QGroupBox("发布日期")
        date_layout = QVBoxLayout(date_group)

        self.date_combo = QComboBox()
        self.date_combo.addItem("全部", "")
        self.date_combo.addItem("过去 24 小时", "過去 24 小時")
        self.date_combo.addItem("过去 2 天", "過去 2 天")
        self.date_combo.addItem("过去 1 周", "過去 1 週")
        self.date_combo.addItem("过去 1 个月", "過去 1 個月")
        self.date_combo.addItem("过去 3 个月", "過去 3 個月")
        self.date_combo.addItem("过去 1 年", "過去 1 年")

        # 设置当前选中的日期
        current_date = self.filter_params.get("date", "")
        index = self.date_combo.findData(current_date)
        if index != -1:
            self.date_combo.setCurrentIndex(index)

        date_layout.addWidget(self.date_combo)
        main_layout.addWidget(date_group)

        # 时长
        duration_group = QGroupBox("时长")
        duration_layout = QVBoxLayout(duration_group)

        self.duration_combo = QComboBox()
        self.duration_combo.addItem("全部", "")
        self.duration_combo.addItem("1 分钟 +", "1 分鐘 +")
        self.duration_combo.addItem("5 分钟 +", "5 分鐘 +")
        self.duration_combo.addItem("10 分钟 +", "10 分鐘 +")
        self.duration_combo.addItem("20 分钟 +", "20 分鐘 +")
        self.duration_combo.addItem("30 分钟 +", "30 分鐘 +")
        self.duration_combo.addItem("60 分钟 +", "60 分鐘 +")
        self.duration_combo.addItem("0 - 10 分钟", "0 - 10 分鐘")
        self.duration_combo.addItem("0 - 20 分钟", "0 - 20 分鐘")

        # 设置当前选中的时长
        current_duration = self.filter_params.get("duration", "")
        index = self.duration_combo.findData(current_duration)
        if index != -1:
            self.duration_combo.setCurrentIndex(index)

        duration_layout.addWidget(self.duration_combo)
        main_layout.addWidget(duration_group)

        # 广泛配对
        broad_group = QGroupBox("配对方式")
        broad_layout = QVBoxLayout(broad_group)

        self.broad_checkbox = QCheckBox("广泛配对（配对所有包含任何一个选择的标签的影片）")
        self.broad_checkbox.setChecked(self.filter_params.get("broad", False))
        broad_layout.addWidget(self.broad_checkbox)
        main_layout.addWidget(broad_group)

        # 内容标签
        tags_group = QGroupBox("内容标签")
        tags_layout = QVBoxLayout(tags_group)

        # 存储标签复选框（键为繁体中文标签，值为复选框对象）
        self.tag_checkboxes = {}

        # 添加标签分类和复选框
        for category, tags in TAG_CATEGORIES.items():
            # 分类标题（使用简体中文显示）
            category_label = QLabel(f"{TAG_MAPPING.get(category, category)}:")
            tags_layout.addWidget(category_label)

            # 标签网格布局
            tag_grid = QWidget()
            tag_grid_layout = QGridLayout(tag_grid)
            tag_grid_layout.setSpacing(5)

            # 添加标签复选框
            row = 0
            col = 0
            max_cols = 4

            for tag in tags:
                # 检查tag是否是元组（显示名称, 实际标签）
                if isinstance(tag, tuple):
                    display_name, actual_tag = tag
                else:
                    # 如果不是元组，使用标签本身作为显示名称和实际标签
                    display_name = TAG_MAPPING.get(tag, tag)
                    actual_tag = tag

                checkbox = QCheckBox(display_name)  # 显示简体中文
                checkbox.setChecked(
                    actual_tag in self.filter_params.get("tags", [])
                )  # 检查实际标签是否在选中列表中
                self.tag_checkboxes[actual_tag] = checkbox  # 使用实际标签作为键
                tag_grid_layout.addWidget(checkbox, row, col)
                col += 1
                if col >= max_cols:
                    col = 0
                    row += 1

            tags_layout.addWidget(tag_grid)

        # 添加滚动区域
        scroll_area = QWidget()
        scroll_area.setLayout(tags_layout)
        scroll = QScrollArea()
        scroll.setWidget(scroll_area)
        scroll.setWidgetResizable(True)
        scroll.setFixedHeight(400)
        main_layout.addWidget(scroll)

        # 按钮组
        button_layout = QHBoxLayout()
        self.reset_button = QPushButton("重置")
        self.reset_button.clicked.connect(self.reset_settings)

        self.save_button = QPushButton("保存")
        self.save_button.clicked.connect(self.accept)

        button_layout.addWidget(self.reset_button)
        button_layout.addStretch(1)
        button_layout.addWidget(self.save_button)
        main_layout.addLayout(button_layout)

    def reset_settings(self):
        """重置筛选设置"""
        self.genre_combo.setCurrentIndex(0)
        self.sort_combo.setCurrentIndex(0)
        self.date_combo.setCurrentIndex(0)
        self.duration_combo.setCurrentIndex(0)
        self.broad_checkbox.setChecked(False)
        for checkbox in self.tag_checkboxes.values():
            checkbox.setChecked(False)

    def accept(self):
        """保存筛选设置"""
        selected_tags = []
        for tag, checkbox in self.tag_checkboxes.items():
            if checkbox.isChecked():
                selected_tags.append(tag)

        self.filter_params["genre"] = self.genre_combo.currentData()
        self.filter_params["sort"] = self.sort_combo.currentData()
        self.filter_params["date"] = self.date_combo.currentData()
        self.filter_params["duration"] = self.duration_combo.currentData()
        self.filter_params["tags"] = selected_tags
        self.filter_params["broad"] = self.broad_checkbox.isChecked()

        super().accept()

    def get_filter_params(self):
        return self.filter_params


class VideoDetailsSettingsDialog(QDialog):
    """详细信息显示设置对话框"""

    def __init__(self, visibility_settings, parent=None):
        super().__init__(parent)
        # 设置窗口标志，禁用上下文帮助按钮
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self.settings = visibility_settings.copy()
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("详细信息显示设置")
        self.setFixedWidth(350)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        group = QGroupBox("自定义详情面板显示项")
        group_layout = QVBoxLayout(group)
        group_layout.setContentsMargins(15, 20, 15, 15)
        group_layout.setSpacing(12)

        self.checkboxes = {}
        items = [
            ("title", "标题"),
            ("upload_date", "上传日期"),
            ("likes", "点赞"),
            ("tags", "标签"),
            ("cover", "封面 (查看按钮)"),
            ("description", "描述"),
            ("related_videos", "相关视频"),
        ]

        # 默认显示设置（除了描述，其他默认开启）
        default_visibility = {
            "title": True,
            "upload_date": True,
            "likes": True,
            "tags": True,
            "cover": True,
            "description": False,
            "related_videos": True,
        }

        for key, label in items:
            cb = QCheckBox(label)
            # 优先使用保存的设置，如果没有则使用默认值
            cb.setChecked(self.settings.get(key, default_visibility.get(key, True)))
            self.checkboxes[key] = cb
            group_layout.addWidget(cb)

        layout.addWidget(group)

        btn_layout = QHBoxLayout()
        save_btn = QPushButton("确定")
        save_btn.setObjectName("primary_btn")
        save_btn.setFixedWidth(80)
        save_btn.clicked.connect(self.accept)

        cancel_btn = QPushButton("取消")
        cancel_btn.setFixedWidth(80)
        cancel_btn.clicked.connect(self.reject)

        btn_layout.addStretch()
        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

    def get_settings(self):
        for key, cb in self.checkboxes.items():
            self.settings[key] = cb.isChecked()
        return self.settings


class SettingsDialog(QDialog):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        # 设置窗口标志，禁用上下文帮助按钮
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self.settings = settings.copy()
        # 设置默认值
        self.default_settings = {
            "download_mode": "multi_thread",
            "num_threads": 4,
            "max_simultaneous_downloads": 2,
            "download_quality": "最高",
            "download_path": os.path.join(os.getcwd(), "hanimeDownload"),
            "file_naming_rule": "{title}",
            "overwrite_existing": False,
            "cloudflare_cookie": "",
            "show_thumbnails": False,
            "show_announcements": True,
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
        # 合并默认设置
        for key, value in self.default_settings.items():
            if key not in self.settings:
                self.settings[key] = value
        self.parent = parent
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("设置")
        self.setMinimumWidth(500)
        self.setMinimumHeight(600)

        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # 使用标签页组织设置，使界面整洁
        tab_widget = QTabWidget()
        main_layout.addWidget(tab_widget)

        # --- 下载设置标签页 ---
        download_tab = QWidget()
        download_layout = QVBoxLayout(download_tab)
        download_layout.setContentsMargins(16, 16, 16, 16)
        download_layout.setSpacing(16)

        # 下载基本配置
        basic_group = QGroupBox("基础下载配置")
        basic_form = QFormLayout(basic_group)
        basic_form.setSpacing(12)

        mode_layout = QHBoxLayout()
        self.multi_thread_radio = QRadioButton("多线程")
        self.single_thread_radio = QRadioButton("单线程")
        if self.settings["download_mode"] == "multi_thread":
            self.multi_thread_radio.setChecked(True)
        else:
            self.single_thread_radio.setChecked(True)
        mode_layout.addWidget(self.multi_thread_radio)
        mode_layout.addWidget(self.single_thread_radio)
        mode_layout.addStretch()
        basic_form.addRow("下载方式:", mode_layout)

        self.thread_spinbox = QSpinBox()
        self.thread_spinbox.setRange(1, 32)
        self.thread_spinbox.setValue(self.settings["num_threads"])
        basic_form.addRow("单文件并发线程:", self.thread_spinbox)

        self.max_downloads_spinbox = QSpinBox()
        self.max_downloads_spinbox.setRange(1, 10)
        self.max_downloads_spinbox.setValue(self.settings["max_simultaneous_downloads"])
        basic_form.addRow("最大同时下载任务:", self.max_downloads_spinbox)

        quality_layout = QHBoxLayout()
        self.highest_quality_radio = QRadioButton("最高")
        self.lowest_quality_radio = QRadioButton("最低")
        if self.settings["download_quality"] == "最高":
            self.highest_quality_radio.setChecked(True)
        else:
            self.lowest_quality_radio.setChecked(True)
        quality_layout.addWidget(self.highest_quality_radio)
        quality_layout.addWidget(self.lowest_quality_radio)
        quality_layout.addStretch()
        basic_form.addRow("首选画质:", quality_layout)

        download_layout.addWidget(basic_group)

        # 文件管理配置
        file_group = QGroupBox("文件管理")
        file_form = QFormLayout(file_group)
        file_form.setSpacing(12)

        path_layout = QHBoxLayout()
        self.path_edit = ChineseLineEdit(self.settings["download_path"])
        self.browse_button = QPushButton("浏览")
        self.browse_button.setFixedWidth(60)
        self.browse_button.clicked.connect(self.browse_path)
        path_layout.addWidget(self.path_edit)
        path_layout.addWidget(self.browse_button)
        file_form.addRow("保存路径:", path_layout)

        self.naming_rule_combo = QComboBox()
        self.naming_rule_combo.addItem("仅标题", "{title}")
        self.naming_rule_combo.addItem("[视频ID] 标题", "[{video_id}] {title}")
        current_rule = self.settings["file_naming_rule"]
        idx = self.naming_rule_combo.findData(current_rule)
        if idx != -1:
            self.naming_rule_combo.setCurrentIndex(idx)
        file_form.addRow("命名规则:", self.naming_rule_combo)

        self.overwrite_checkbox = QCheckBox("如果文件已存在则覆盖")
        self.overwrite_checkbox.setChecked(self.settings["overwrite_existing"])
        file_form.addRow("", self.overwrite_checkbox)

        download_layout.addWidget(file_group)
        download_layout.addStretch()
        tab_widget.addTab(download_tab, "下载设置")

        # --- 界面设置标签页 ---
        ui_tab = QWidget()
        ui_layout = QVBoxLayout(ui_tab)
        ui_layout.setContentsMargins(16, 16, 16, 16)
        ui_layout.setSpacing(16)

        display_group = QGroupBox("显示选项")
        display_vbox = QVBoxLayout(display_group)
        display_vbox.setSpacing(12)

        self.show_thumbnails_checkbox = QCheckBox("在列表中显示视频缩略图")
        self.show_thumbnails_checkbox.setChecked(self.settings.get("show_thumbnails", False))
        display_vbox.addWidget(self.show_thumbnails_checkbox)

        self.show_announcements_checkbox = QCheckBox("显示远程公告")
        self.show_announcements_checkbox.setChecked(self.settings.get("show_announcements", True))
        display_vbox.addWidget(self.show_announcements_checkbox)

        self.details_visibility_btn = QPushButton("自定义右侧详情面板显示项...")
        self.details_visibility_btn.clicked.connect(self.open_details_visibility_settings)
        display_vbox.addWidget(self.details_visibility_btn)

        ui_layout.addWidget(display_group)
        ui_layout.addStretch()
        tab_widget.addTab(ui_tab, "界面设置")

        # --- 网络设置标签页 ---
        network_tab = QWidget()
        network_layout = QVBoxLayout(network_tab)
        network_layout.setContentsMargins(16, 16, 16, 16)
        network_layout.setSpacing(16)

        cookie_group = QGroupBox("Cloudflare 验证")
        cookie_vbox = QVBoxLayout(cookie_group)
        cookie_vbox.setSpacing(10)

        self.cloudflare_cookie_edit = ChineseTextEdit()
        self.cloudflare_cookie_edit.setPlaceholderText("格式: cf_clearance=xxxx...")
        self.cloudflare_cookie_edit.setPlainText(self.settings["cloudflare_cookie"])
        self.cloudflare_cookie_edit.setMaximumHeight(100)
        cookie_vbox.addWidget(QLabel("cf_clearance Cookie:"))
        cookie_vbox.addWidget(self.cloudflare_cookie_edit)

        cookie_btns = QHBoxLayout()
        self.clear_cookie_button = QPushButton("清空 Cookie")
        self.clear_cookie_button.clicked.connect(self.clear_cookie)
        cookie_btns.addStretch()
        cookie_btns.addWidget(self.clear_cookie_button)
        cookie_vbox.addLayout(cookie_btns)

        network_layout.addWidget(cookie_group)
        network_layout.addStretch()
        tab_widget.addTab(network_tab, "网络设置")

        # 底部操作按钮
        bottom_layout = QHBoxLayout()
        bottom_layout.setContentsMargins(16, 10, 16, 16)
        bottom_layout.setSpacing(12)

        self.save_button = QPushButton("保存设置")
        self.save_button.setObjectName("primary_btn")  # 应用蓝色高亮样式
        self.save_button.setFixedWidth(100)
        self.save_button.clicked.connect(self.accept)

        self.cancel_button = QPushButton("取消")
        self.cancel_button.setFixedWidth(80)
        self.cancel_button.clicked.connect(self.reject)

        bottom_layout.addStretch()
        bottom_layout.addWidget(self.save_button)
        bottom_layout.addWidget(self.cancel_button)
        main_layout.addLayout(bottom_layout)

    def browse_path(self):
        path = QFileDialog.getExistingDirectory(
            self, "选择下载路径", self.settings["download_path"]
        )
        if path:
            self.path_edit.setText(path)

    def open_details_visibility_settings(self):
        dialog = VideoDetailsSettingsDialog(self.settings.get("video_details_visibility", {}), self)
        if dialog.exec_():
            self.settings["video_details_visibility"] = dialog.get_settings()

    def clear_cookie(self):
        """清除Cloudflare Cookie"""
        self.cloudflare_cookie_edit.clear()
        self.settings["cloudflare_cookie"] = ""
        if hasattr(self.parent, "api"):
            self.parent.api.session.cookies.clear()
            self.parent.settings["cloudflare_cookie"] = ""
            if os.path.exists("settings.json"):
                with open("settings.json", "r", encoding="utf-8") as f:
                    settings = json.load(f)
                if "session" in settings:
                    del settings["session"]
                if "cloudflare_cookie" in settings:
                    del settings["cloudflare_cookie"]
                with open("settings.json", "w", encoding="utf-8") as f:
                    json.dump(settings, f, ensure_ascii=False, indent=2)
                self.parent.save_settings()
            QMessageBox.information(self, "成功", "Cookie已清除")

    def accept(self):
        """重写accept方法，在保存设置时同时保存Cookie到会话"""
        cookie_text = self.cloudflare_cookie_edit.toPlainText().strip()
        if cookie_text and hasattr(self.parent, "apply_cloudflare_cookie"):
            self.parent.apply_cloudflare_cookie(cookie_text)
        super().accept()

    def get_settings(self):
        self.settings["download_mode"] = (
            "multi_thread" if self.multi_thread_radio.isChecked() else "single_thread"
        )
        self.settings["num_threads"] = self.thread_spinbox.value()
        self.settings["max_simultaneous_downloads"] = self.max_downloads_spinbox.value()
        self.settings["download_quality"] = (
            "最高" if self.highest_quality_radio.isChecked() else "最低"
        )
        self.settings["download_path"] = self.path_edit.text()
        self.settings["file_naming_rule"] = self.naming_rule_combo.currentData()
        self.settings["overwrite_existing"] = self.overwrite_checkbox.isChecked()
        self.settings["show_thumbnails"] = self.show_thumbnails_checkbox.isChecked()
        self.settings["show_announcements"] = self.show_announcements_checkbox.isChecked()
        self.settings["cloudflare_cookie"] = self.cloudflare_cookie_edit.toPlainText().strip()
        return self.settings
