"""
プロジェクト設定ダイアログ
"""

from typing import Optional, Dict

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLineEdit, QTextEdit, QPushButton, QLabel,
    QMessageBox, QGroupBox
)
from PySide6.QtCore import Qt

from config.models import ProjectSettings


class ProjectDialog(QDialog):
    """プロジェクト設定ダイアログ"""
    
    def __init__(self, parent=None, project: Optional[ProjectSettings] = None):
        super().__init__(parent)
        
        self.project = project
        self.is_edit_mode = project is not None
        
        self.init_ui()
        
        if self.is_edit_mode:
            self.load_project_data()
    
    def init_ui(self):
        """UI初期化"""
        title = "プロジェクト編集" if self.is_edit_mode else "新しいプロジェクト"
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumSize(400, 300)
        
        layout = QVBoxLayout(self)
        
        # 基本情報グループ
        basic_group = QGroupBox("基本情報")
        basic_layout = QFormLayout(basic_group)
        
        # プロジェクト名
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("プロジェクト名を入力してください")
        basic_layout.addRow("プロジェクト名(&N):", self.name_edit)
        
        # 説明
        self.description_edit = QTextEdit()
        self.description_edit.setPlaceholderText("プロジェクトの説明を入力してください（任意）")
        self.description_edit.setMaximumHeight(100)
        basic_layout.addRow("説明(&D):", self.description_edit)
        
        layout.addWidget(basic_group)
        
        # 情報表示（編集モードのみ）
        if self.is_edit_mode:
            info_group = QGroupBox("プロジェクト情報")
            info_layout = QFormLayout(info_group)
            
            self.id_label = QLabel()
            self.created_label = QLabel()
            self.updated_label = QLabel()
            self.folder_count_label = QLabel()
            
            info_layout.addRow("ID:", self.id_label)
            info_layout.addRow("作成日時:", self.created_label)
            info_layout.addRow("更新日時:", self.updated_label)
            info_layout.addRow("フォルダペア数:", self.folder_count_label)
            
            layout.addWidget(info_group)
        
        # ボタン
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self.ok_button = QPushButton("OK")
        self.cancel_button = QPushButton("キャンセル")
        
        self.ok_button.clicked.connect(self.accept_dialog)
        self.cancel_button.clicked.connect(self.reject)
        
        button_layout.addWidget(self.ok_button)
        button_layout.addWidget(self.cancel_button)
        
        layout.addLayout(button_layout)
        
        # フォーカス設定
        self.name_edit.setFocus()
        
        # デフォルトボタン設定
        self.ok_button.setDefault(True)
    
    def load_project_data(self):
        """プロジェクトデータを読み込み"""
        if not self.project:
            return
        
        self.name_edit.setText(self.project.name)
        self.description_edit.setPlainText(self.project.description)
        
        if hasattr(self, 'id_label'):
            self.id_label.setText(self.project.id)
            self.created_label.setText(self.project.created_at)
            self.updated_label.setText(self.project.updated_at)
            self.folder_count_label.setText(str(len(self.project.folder_pairs)))
    
    def get_project_data(self) -> Dict[str, str]:
        """プロジェクトデータを取得"""
        return {
            'name': self.name_edit.text().strip(),
            'description': self.description_edit.toPlainText().strip()
        }
    
    def validate_input(self) -> bool:
        """入力値検証"""
        name = self.name_edit.text().strip()
        
        if not name:
            QMessageBox.warning(self, "入力エラー", "プロジェクト名を入力してください。")
            self.name_edit.setFocus()
            return False
        
        if len(name) > 100:
            QMessageBox.warning(self, "入力エラー", "プロジェクト名は100文字以内で入力してください。")
            self.name_edit.setFocus()
            return False
        
        description = self.description_edit.toPlainText().strip()
        if len(description) > 500:
            QMessageBox.warning(self, "入力エラー", "説明は500文字以内で入力してください。")
            self.description_edit.setFocus()
            return False
        
        return True
    
    def accept_dialog(self):
        """OK ボタンクリック"""
        if self.validate_input():
            self.accept()