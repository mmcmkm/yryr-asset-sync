"""
カテゴリ管理ダイアログ
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QListWidget,
    QPushButton, QInputDialog, QMessageBox
)
from PySide6.QtCore import Qt


class CategoryDialog(QDialog):
    """カテゴリ管理ダイアログ"""

    def __init__(self, categories, parent=None):
        super().__init__(parent)
        self.categories = categories.copy()
        self.init_ui()

    def init_ui(self):
        """UI初期化"""
        self.setWindowTitle("カテゴリ管理")
        self.setMinimumWidth(400)
        self.setMinimumHeight(400)

        layout = QVBoxLayout(self)

        # カテゴリリスト
        self.category_list = QListWidget()
        self.category_list.addItems(self.categories)
        layout.addWidget(self.category_list)

        # ボタンレイアウト
        btn_layout = QHBoxLayout()

        add_btn = QPushButton("追加")
        add_btn.clicked.connect(self.add_category)

        remove_btn = QPushButton("削除")
        remove_btn.clicked.connect(self.remove_category)

        btn_layout.addWidget(add_btn)
        btn_layout.addWidget(remove_btn)
        btn_layout.addStretch()

        layout.addLayout(btn_layout)

        # OK/キャンセルボタン
        dialog_btn_layout = QHBoxLayout()

        ok_btn = QPushButton("OK")
        ok_btn.clicked.connect(self.accept)

        cancel_btn = QPushButton("キャンセル")
        cancel_btn.clicked.connect(self.reject)

        dialog_btn_layout.addStretch()
        dialog_btn_layout.addWidget(ok_btn)
        dialog_btn_layout.addWidget(cancel_btn)

        layout.addLayout(dialog_btn_layout)

    def add_category(self):
        """カテゴリ追加"""
        text, ok = QInputDialog.getText(self, "カテゴリ追加", "新しいカテゴリ名:")
        if ok and text.strip():
            if text.strip() not in self.categories:
                self.categories.append(text.strip())
                self.category_list.addItem(text.strip())
            else:
                QMessageBox.warning(self, "警告", "同じ名前のカテゴリが既に存在します。")

    def remove_category(self):
        """カテゴリ削除"""
        item = self.category_list.currentItem()
        if item:
            if item.text() == "未分類":
                QMessageBox.warning(self, "警告", "「未分類」は削除できません。")
            else:
                self.categories.remove(item.text())
                self.category_list.takeItem(self.category_list.row(item))

    def get_categories(self):
        """カテゴリリストを取得"""
        return self.categories
