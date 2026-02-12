"""
Hanime1DL 主入口文件
"""

import multiprocessing
import os
import sys

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication, QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
import requests
import json

from src.gui.gui import Hanime1GUI


class DeclarationDialog(QDialog):
    """首次启动时的声明弹窗"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("声明")
        self.setMinimumSize(500, 300)
        # 设置窗口标志，禁用关闭按钮
        self.setWindowFlags(Qt.Dialog | Qt.WindowTitleHint | Qt.CustomizeWindowHint)
        self.setModal(True)

        # 主布局
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(12)
        main_layout.setContentsMargins(16, 16, 16, 16)

        # 法律声明
        legal_text = QLabel()
        legal_text.setWordWrap(True)
        # 设置字体大小
        font = legal_text.font()
        font.setPointSize(13)
        legal_text.setFont(font)
        legal_text.setText("""
本工具仅用于学习和研究目的
请遵守相关法律法规，合理使用本工具
下载的视频资源版权归原作者所有，请在24小时内删除
点击同意即代表接受
        """)
        main_layout.addWidget(legal_text)

        # 按钮布局
        button_layout = QHBoxLayout()

        reject_button = QPushButton("拒绝")
        reject_button.clicked.connect(self.reject)
        button_layout.addWidget(reject_button)

        button_layout.addStretch(1)

        accept_button = QPushButton("同意")
        accept_button.clicked.connect(self.accept)
        button_layout.addWidget(accept_button)

        # 添加到主布局
        main_layout.addLayout(button_layout)


class AnnouncementDialog(QDialog):
    """远程公告弹窗"""
    
    def __init__(self, content, title, parent=None):
        super().__init__(parent)
        # 设置窗口标志，禁用上下文帮助按钮
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self.setWindowTitle(title)
        self.setMinimumSize(600, 400)
        self.setModal(True)
        
        # 主布局
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(12)
        main_layout.setContentsMargins(16, 16, 16, 16)
        
        # 公告内容
        content_label = QLabel()
        content_label.setWordWrap(True)
        # 设置字体大小
        font = content_label.font()
        font.setPointSize(13)
        content_label.setFont(font)
        content_label.setText(content)
        main_layout.addWidget(content_label)
        
        # 按钮布局
        button_layout = QHBoxLayout()
        button_layout.addStretch(1)
        
        ok_button = QPushButton("确认")
        ok_button.clicked.connect(self.accept)
        button_layout.addWidget(ok_button)
        
        # 添加到主布局
        main_layout.addLayout(button_layout)


def _get_remote_content():
    """从远程获取内容"""
    url = "https://gitee.com/yxxawa/gg/raw/master/GG.txt"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        content = response.text
        lines = content.strip().split('\n')
        return lines
    except Exception as e:
        return []


def get_remote_announcement():
    """从远程获取公告内容"""
    lines = _get_remote_content()
    title = "公告"
    announcement_content = ""
    
    if lines:
        # 第一行可能包含标题，格式如"标题-内容"
        first_line = lines[0]
        if '-' in first_line:
            parts = first_line.split('-', 1)
            title = parts[0].strip()
            announcement_content = parts[1].strip()
            # 剩余行作为公告内容
            if len(lines) > 1:
                announcement_content += '\n' + '\n'.join(lines[1:])
        else:
            announcement_content = '\n'.join(lines)
    else:
        announcement_content = "无法获取远程公告"
    
    return title, announcement_content


def get_program_title():
    """从远程获取程序标题"""
    lines = _get_remote_content()
    if lines:
        first_line = lines[0]
        if '-' in first_line:
            parts = first_line.split('-', 1)
            return parts[0].strip()
    return ""


def _launch_application(app, show_announcements):
    """启动应用程序"""
    # 获取远程公告并显示
    if show_announcements:
        title, content = get_remote_announcement()
        announcement_dialog = AnnouncementDialog(content, title)
        announcement_dialog.exec_()
    
    # 启动应用
    window = Hanime1GUI()
    # 设置窗口标题
    program_title = get_program_title()
    if program_title:
        window.setWindowTitle(f"{program_title}")
    window.show()
    sys.exit(app.exec_())


def main():
    app = QApplication(sys.argv)
    
    # 确保config文件夹存在
    config_dir = os.path.join(os.getcwd(), "config")
    if not os.path.exists(config_dir):
        os.makedirs(config_dir)
    
    # 检查settings.json文件是否存在
    settings_file = os.path.join(config_dir, "settings.json")
    show_announcements = True  # 默认显示公告
    
    # 如果settings.json文件存在，加载设置
    if os.path.exists(settings_file):
        try:
            with open(settings_file, "r", encoding="utf-8") as f:
                settings = json.load(f)
                show_announcements = settings.get("show_announcements", True)
        except Exception as e:
            pass
    
    if not os.path.exists(settings_file):
        # 显示声明弹窗
        dialog = DeclarationDialog()
        if dialog.exec_() == QDialog.Accepted:
            # 用户点击同意，启动应用
            _launch_application(app, show_announcements)
        else:
            # 用户点击拒绝，退出应用
            sys.exit(0)
    else:
        # settings.json文件存在，直接启动应用
        _launch_application(app, show_announcements)


if __name__ == "__main__":
    # 处理 multiprocessing 在打包后的问题
    multiprocessing.freeze_support()
    main()
