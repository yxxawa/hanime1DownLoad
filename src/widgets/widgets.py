"""
Custom widgets for Hanime1DL
"""

import logging

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QDrag
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QAction,
    QApplication,
    QComboBox,
    QHBoxLayout,
    QLineEdit,
    QListWidget,
    QMenu,
    QPushButton,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


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
        self.layout.setContentsMargins(0, 8, 0, 8)
        self.layout.setSpacing(4)

        # 水平布局用于按钮
        buttons_layout = QHBoxLayout()
        buttons_layout.setContentsMargins(0, 0, 0, 0)
        buttons_layout.setSpacing(8)

        # 第一页按钮
        self.first_button = QPushButton("首页")
        self.first_button.setFixedSize(70, 36)
        self.first_button.clicked.connect(self.go_to_first_page)
        buttons_layout.addWidget(self.first_button)

        # 上一页按钮
        self.prev_button = QPushButton("上一页")
        self.prev_button.setFixedSize(80, 36)
        self.prev_button.clicked.connect(self.go_to_prev_page)
        buttons_layout.addWidget(self.prev_button)

        buttons_layout.addStretch()  # 中间左侧弹簧，将首页/上一页推向最左侧

        # 页码按钮容器
        self.pages_container = QWidget()
        self.pages_layout = QHBoxLayout(self.pages_container)
        self.pages_layout.setContentsMargins(0, 0, 0, 0)
        self.pages_layout.setSpacing(5)
        self.pages_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        buttons_layout.addWidget(self.pages_container)

        buttons_layout.addStretch()  # 中间右侧弹簧，将下一页/末页推向最右侧

        # 下一页按钮
        self.next_button = QPushButton("下一页")
        self.next_button.setFixedSize(80, 36)
        self.next_button.clicked.connect(self.go_to_next_page)
        buttons_layout.addWidget(self.next_button)

        # 最后一页按钮
        self.last_button = QPushButton("末页")
        self.last_button.setFixedSize(70, 36)
        self.last_button.clicked.connect(self.go_to_last_page)
        buttons_layout.addWidget(self.last_button)

        # 添加按钮布局到主布局
        self.layout.addLayout(buttons_layout)

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

        # 更新页码按钮
        self.update_page_buttons()
        
    def get_page_info_text(self):
        """获取页码信息文本"""
        return f"第 {self.current_page} 页 / 共 {self.total_pages} 页"

    def update_page_buttons(self):
        """更新页码按钮"""
        # 清空现有按钮和间隔项
        for i in reversed(range(self.pages_layout.count())):
            item = self.pages_layout.itemAt(i)
            if item:
                widget = item.widget()
                if widget:
                    widget.deleteLater()
                else:
                    self.pages_layout.removeItem(item)

        # 计算显示的页码范围
        start_page = max(1, self.current_page - self.max_visible_pages // 2)
        end_page = min(self.total_pages, start_page + self.max_visible_pages - 1)

        # 调整起始页码，确保显示足够数量的页码
        if end_page - start_page + 1 < self.max_visible_pages:
            start_page = max(1, end_page - self.max_visible_pages + 1)

        # 按顺序添加页码按钮
        for page in range(start_page, end_page + 1):
            button = QPushButton(str(page))
            # 确保页码按钮与导航按钮高度完全一致
            button.setFixedSize(50, 36)
            button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
            # 确保页码按钮与导航按钮样式完全一致
            if page == self.current_page:
                button.setObjectName("primary_btn")
                button.setStyleSheet("QPushButton#primary_btn { background-color: #1890ff; color: white; border: 1px solid #1890ff; border-radius: 8px; padding: 0 12px; font-family: 'Segoe UI'; font-size: 9pt; min-height: 36px; } QPushButton#primary_btn:pressed { background-color: #096dd9; border-color: #096dd9; }")
            else:
                button.setObjectName("")
                # 设置普通页码按钮的样式，确保与导航按钮完全一致
                button.setStyleSheet("QPushButton { background-color: #f8f9fa; border: 1px solid #e0e0e0; border-radius: 8px; padding: 0 12px; color: #333; font-family: 'Segoe UI'; font-size: 9pt; min-height: 36px; } QPushButton:pressed { background-color: #e6e6e6; border-color: #1890ff; }")
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


class DownloadListWidget(QListWidget):
    """
    支持拖拽排序和长按多选的下载列表
    """

    order_changed = pyqtSignal(list, int)  # 选中行索引列表, 目标位置索引

    def __init__(self, parent=None):
        super().__init__(parent)
        self.downloads_ref = []  # 由外部注入下载列表引用
        self.setAcceptDrops(True)
        self.setDragEnabled(False)  # 禁用自动左键拖拽
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setDefaultDropAction(Qt.MoveAction)

        # 右键拖拽相关状态
        self.right_drag_start_pos = None
        self.is_right_dragging = False

    def mousePressEvent(self, event):
        if event.button() == Qt.RightButton:
            # 记录右键按下位置，准备可能的拖拽
            self.right_drag_start_pos = event.pos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.RightButton and self.right_drag_start_pos:
            # 检查移动距离是否足以触发拖拽
            delta = event.pos() - self.right_drag_start_pos
            if delta.manhattanLength() >= QApplication.startDragDistance() and abs(delta.y()) > abs(
                delta.x()
            ):
                # 检查选中的项中是否有正在下载的
                for item in self.selectedItems():
                    row = self.row(item)
                    if 0 <= row < len(self.downloads_ref):
                        if self.downloads_ref[row].get("status") == "downloading":
                            return  # 正在下载的项目不允许拖动

                # 手动开启拖拽
                drag = QDrag(self)
                mime_data = self.model().mimeData(self.selectedIndexes())
                drag.setMimeData(mime_data)

                # 执行拖拽
                drag.exec_(Qt.MoveAction)
                self.right_drag_start_pos = None
                return
        super().mouseMoveEvent(event)

    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat("application/x-qabstractitemmodeldatalist"):
            event.accept()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasFormat("application/x-qabstractitemmodeldatalist"):
            # 检查选中的项中是否有正在下载的
            for item in self.selectedItems():
                row = self.row(item)
                if 0 <= row < len(self.downloads_ref):
                    if self.downloads_ref[row].get("status") == "downloading":
                        event.ignore()
                        return
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event):
        if event.source() == self:
            # 获取选中的所有行索引
            selected_rows = sorted([self.row(item) for item in self.selectedItems()])
            if not selected_rows:
                event.ignore()
                return

            # 获取释放位置对应的目标索引
            target_item = self.itemAt(event.pos())
            target_index = self.row(target_item) if target_item else self.count()

            # 计算实际插入位置
            # 如果目标位置在选中项范围内，可能需要特殊处理，但这里我们简单处理：
            # 先发射信号让父窗口处理数据同步
            self.order_changed.emit(selected_rows, target_index)

            # 调用父类处理 UI 上的移动
            super().dropEvent(event)
            event.accept()
        else:
            event.ignore()


class ChineseLineEdit(QLineEdit):
    def contextMenuEvent(self, event):
        menu = QMenu(self)
        undo_act = QAction("撤销", self, triggered=self.undo, enabled=self.isUndoAvailable())
        redo_act = QAction(
            "重做",
            self,
            triggered=self.redo,
            enabled=self.isRedoAvailable() if hasattr(self, "isRedoAvailable") else True,
        )
        cut_act = QAction("剪切", self, triggered=self.cut, enabled=self.hasSelectedText())
        copy_act = QAction("复制", self, triggered=self.copy, enabled=self.hasSelectedText())
        paste_act = QAction("粘贴", self, triggered=self.paste)
        delete_act = QAction("删除", self, triggered=self.delete_action)
        select_all_act = QAction("全选", self, triggered=self.selectAll)
        clear_act = QAction("清除", self, triggered=self.clear)
        menu.addAction(undo_act)
        menu.addAction(redo_act)
        menu.addSeparator()
        menu.addAction(cut_act)
        menu.addAction(copy_act)
        menu.addAction(paste_act)
        menu.addAction(delete_act)
        menu.addSeparator()
        menu.addAction(select_all_act)
        menu.addAction(clear_act)
        menu.exec_(event.globalPos())

    def delete_action(self):
        cursor = self.cursorPosition()
        if self.hasSelectedText():
            try:
                self.backspace()
            except Exception as e:
                logging.warning(f"Failed to delete selected text: {e}")
        else:
            try:
                if hasattr(QLineEdit, "del_"):
                    QLineEdit.del_(self)
                else:
                    text = self.text()
                    if cursor < len(text):
                        self.setText(text[:cursor] + text[cursor + 1 :])
                        self.setCursorPosition(cursor)
            except Exception as e:
                logging.warning(f"Failed to delete character: {e}")


class ChineseTextEdit(QTextEdit):
    def contextMenuEvent(self, event):
        menu = QMenu(self)
        undo_act = QAction(
            "撤销", self, triggered=self.undo, enabled=self.document().isUndoAvailable()
        )
        redo_act = QAction(
            "重做", self, triggered=self.redo, enabled=self.document().isRedoAvailable()
        )
        cut_act = QAction(
            "剪切", self, triggered=self.cut, enabled=self.textCursor().hasSelection()
        )
        copy_act = QAction(
            "复制", self, triggered=self.copy, enabled=self.textCursor().hasSelection()
        )
        paste_act = QAction("粘贴", self, triggered=self.paste)
        delete_act = QAction("删除", self, triggered=self.delete_)
        select_all_act = QAction("全选", self, triggered=self.selectAll)
        clear_act = QAction("清除", self, triggered=self.clear)
        menu.addAction(undo_act)
        menu.addAction(redo_act)
        menu.addSeparator()
        menu.addAction(cut_act)
        menu.addAction(copy_act)
        menu.addAction(paste_act)
        menu.addAction(delete_act)
        menu.addSeparator()
        menu.addAction(select_all_act)
        menu.addAction(clear_act)
        menu.exec_(event.globalPos())

    def delete_(self):
        cursor = self.textCursor()
        if cursor.hasSelection():
            cursor.removeSelectedText()
        else:
            cursor.deleteChar()
            self.setTextCursor(cursor)


class ChineseComboBox(QComboBox):
    def contextMenuEvent(self, event):
        le = self.lineEdit()
        if le and isinstance(le, QLineEdit):
            menu = QMenu(self)
            undo_act = QAction("撤销", self, triggered=le.undo, enabled=le.isUndoAvailable())
            redo_act = QAction(
                "重做",
                self,
                triggered=le.redo,
                enabled=le.isRedoAvailable() if hasattr(le, "isRedoAvailable") else True,
            )
            cut_act = QAction("剪切", self, triggered=le.cut, enabled=le.hasSelectedText())
            copy_act = QAction("复制", self, triggered=le.copy, enabled=le.hasSelectedText())
            paste_act = QAction("粘贴", self, triggered=le.paste)
            delete_act = QAction("删除", self, triggered=lambda: self._delete_in_lineedit(le))
            select_all_act = QAction("全选", self, triggered=le.selectAll)
            clear_act = QAction("清除", self, triggered=le.clear)
            menu.addAction(undo_act)
            menu.addAction(redo_act)
            menu.addSeparator()
            menu.addAction(cut_act)
            menu.addAction(copy_act)
            menu.addAction(paste_act)
            menu.addAction(delete_act)
            menu.addSeparator()
            menu.addAction(select_all_act)
            menu.addAction(clear_act)
            menu.exec_(event.globalPos())
        else:
            super().contextMenuEvent(event)

    def _delete_in_lineedit(self, le):
        cursor = le.cursorPosition()
        if le.hasSelectedText():
            le.del_() if hasattr(le, "del_") else le.backspace()
        else:
            text = le.text()
            if cursor < len(text):
                le.setText(text[:cursor] + text[cursor + 1 :])
                le.setCursorPosition(cursor)
