"""
同期設定ダイアログ（フォルダペア設定）
"""

from typing import Optional, Dict, List
from pathlib import Path

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLineEdit, QTextEdit, QPushButton, QLabel, QCheckBox,
    QMessageBox, QGroupBox, QFileDialog, QListWidget,
    QListWidgetItem, QTabWidget, QWidget, QSplitter
)
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices

from config.models import FolderPair, FileMappingRule
import uuid


class SyncDialog(QDialog):
    """同期設定ダイアログ"""
    
    def __init__(self, parent=None, folder_pair: Optional[FolderPair] = None):
        super().__init__(parent)
        
        self.folder_pair = folder_pair
        self.is_edit_mode = folder_pair is not None
        
        self.init_ui()
        
        if self.is_edit_mode:
            self.load_folder_pair_data()
    
    def init_ui(self):
        """UI初期化"""
        title = "フォルダペア編集" if self.is_edit_mode else "新しいフォルダペア"
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumSize(600, 500)
        
        layout = QVBoxLayout(self)
        
        # タブウィジェット
        tab_widget = QTabWidget()
        
        # 基本設定タブ
        basic_tab = self.create_basic_tab()
        tab_widget.addTab(basic_tab, "基本設定")
        
        # フィルタ設定タブ
        filter_tab = self.create_filter_tab()
        tab_widget.addTab(filter_tab, "フィルタ設定")
        
        # オプション設定タブ
        options_tab = self.create_options_tab()
        tab_widget.addTab(options_tab, "オプション")
        
        # ファイルマッピングタブ
        mapping_tab = self.create_mapping_tab()
        tab_widget.addTab(mapping_tab, "ファイル振り分け")
        
        layout.addWidget(tab_widget)
        
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
        
        # デフォルトボタン設定
        self.ok_button.setDefault(True)
    
    def create_basic_tab(self) -> QWidget:
        """基本設定タブ作成"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # 基本情報
        basic_group = QGroupBox("基本情報")
        basic_layout = QFormLayout(basic_group)
        
        # 名前
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("フォルダペアの名前を入力してください")
        basic_layout.addRow("名前(&N):", self.name_edit)
        
        layout.addWidget(basic_group)
        
        # フォルダ設定
        folder_group = QGroupBox("フォルダ設定")
        folder_layout = QFormLayout(folder_group)
        
        # ソースフォルダ
        source_layout = QHBoxLayout()
        self.source_path_edit = QLineEdit()
        self.source_path_edit.setPlaceholderText("コピー元フォルダパスを入力してください")
        self.source_browse_btn = QPushButton("参照...")
        self.source_browse_btn.clicked.connect(self.browse_source_folder)
        self.source_open_btn = QPushButton("開く")
        self.source_open_btn.clicked.connect(self.open_source_folder)
        
        source_layout.addWidget(self.source_path_edit)
        source_layout.addWidget(self.source_browse_btn)
        source_layout.addWidget(self.source_open_btn)
        folder_layout.addRow("ソースフォルダ(&S):", source_layout)
        
        # ターゲットフォルダ
        target_layout = QHBoxLayout()
        self.target_path_edit = QLineEdit()
        self.target_path_edit.setPlaceholderText("コピー先フォルダパスを入力してください")
        self.target_browse_btn = QPushButton("参照...")
        self.target_browse_btn.clicked.connect(self.browse_target_folder)
        self.target_open_btn = QPushButton("開く")
        self.target_open_btn.clicked.connect(self.open_target_folder)
        
        target_layout.addWidget(self.target_path_edit)
        target_layout.addWidget(self.target_browse_btn)
        target_layout.addWidget(self.target_open_btn)
        folder_layout.addRow("ターゲットフォルダ(&T):", target_layout)
        
        layout.addWidget(folder_group)
        
        # 情報表示（編集モードのみ）
        if self.is_edit_mode:
            info_group = QGroupBox("フォルダペア情報")
            info_layout = QFormLayout(info_group)
            
            self.id_label = QLabel()
            self.last_sync_label = QLabel()
            
            info_layout.addRow("ID:", self.id_label)
            info_layout.addRow("最後の同期:", self.last_sync_label)
            
            layout.addWidget(info_group)
        
        layout.addStretch()
        return tab
    
    def create_filter_tab(self) -> QWidget:
        """フィルタ設定タブ作成"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # フィルタ有効化
        self.filter_enabled_check = QCheckBox("フィルタを有効にする")
        self.filter_enabled_check.setChecked(True)
        layout.addWidget(self.filter_enabled_check)
        
        # スプリッター（上下分割）
        splitter = QSplitter(Qt.Vertical)
        layout.addWidget(splitter)
        
        # 含むパターン
        include_group = QGroupBox("含むパターン")
        include_layout = QVBoxLayout(include_group)
        
        include_help = QLabel("含むパターンを指定してください（空の場合は全てを含む）\n"
                             "例: *.jpg, *.png, *.fbx\n"
                             "正規表現: regex:.*\\.jpe?g$")
        include_help.setWordWrap(True)
        include_help.setStyleSheet("color: #666666; font-size: 10px;")
        include_layout.addWidget(include_help)
        
        # 含むパターンリスト
        self.include_list = QListWidget()
        self.include_list.setMaximumHeight(120)
        include_layout.addWidget(self.include_list)
        
        # 含むパターン追加・削除
        include_btn_layout = QHBoxLayout()
        self.include_add_btn = QPushButton("追加")
        self.include_remove_btn = QPushButton("削除")
        self.include_edit_btn = QPushButton("編集")
        
        self.include_add_btn.clicked.connect(self.add_include_pattern)
        self.include_remove_btn.clicked.connect(self.remove_include_pattern)
        self.include_edit_btn.clicked.connect(self.edit_include_pattern)
        
        include_btn_layout.addWidget(self.include_add_btn)
        include_btn_layout.addWidget(self.include_remove_btn)
        include_btn_layout.addWidget(self.include_edit_btn)
        include_btn_layout.addStretch()
        
        include_layout.addLayout(include_btn_layout)
        splitter.addWidget(include_group)
        
        # 除外パターン
        exclude_group = QGroupBox("除外パターン")
        exclude_layout = QVBoxLayout(exclude_group)
        
        exclude_help = QLabel("除外パターンを指定してください\n"
                             "例: *.tmp, *.bak, *~\n"
                             "正規表現: regex:.*\\.temp$")
        exclude_help.setWordWrap(True)
        exclude_help.setStyleSheet("color: #666666; font-size: 10px;")
        exclude_layout.addWidget(exclude_help)
        
        # 除外パターンリスト
        self.exclude_list = QListWidget()
        self.exclude_list.setMaximumHeight(120)
        exclude_layout.addWidget(self.exclude_list)
        
        # 除外パターン追加・削除
        exclude_btn_layout = QHBoxLayout()
        self.exclude_add_btn = QPushButton("追加")
        self.exclude_remove_btn = QPushButton("削除")
        self.exclude_edit_btn = QPushButton("編集")
        
        self.exclude_add_btn.clicked.connect(self.add_exclude_pattern)
        self.exclude_remove_btn.clicked.connect(self.remove_exclude_pattern)
        self.exclude_edit_btn.clicked.connect(self.edit_exclude_pattern)
        
        exclude_btn_layout.addWidget(self.exclude_add_btn)
        exclude_btn_layout.addWidget(self.exclude_remove_btn)
        exclude_btn_layout.addWidget(self.exclude_edit_btn)
        exclude_btn_layout.addStretch()
        
        exclude_layout.addLayout(exclude_btn_layout)
        splitter.addWidget(exclude_group)
        
        # よく使用されるパターン
        common_group = QGroupBox("よく使用されるパターン")
        common_layout = QVBoxLayout(common_group)
        
        common_patterns = [
            ("画像ファイル", ["*.jpg", "*.jpeg", "*.png", "*.gif", "*.bmp", "*.tiff"]),
            ("3Dファイル", ["*.fbx", "*.obj", "*.dae", "*.3ds", "*.blend"]),
            ("テキストファイル", ["*.txt", "*.json", "*.xml", "*.csv"]),
            ("一時ファイル除外", ["*.tmp", "*.temp", "*.bak", "*~", "*.swp"])
        ]
        
        for name, patterns in common_patterns:
            btn = QPushButton(f"{name}を追加")
            btn.clicked.connect(lambda checked, p=patterns: self.add_common_patterns(p))
            common_layout.addWidget(btn)
        
        layout.addWidget(common_group)
        
        return tab
    
    def create_options_tab(self) -> QWidget:
        """オプション設定タブ作成"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # 同期オプション
        sync_group = QGroupBox("同期オプション")
        sync_layout = QVBoxLayout(sync_group)
        
        self.enabled_check = QCheckBox("このフォルダペアを有効にする")
        self.enabled_check.setChecked(True)
        sync_layout.addWidget(self.enabled_check)
        
        self.auto_sync_check = QCheckBox("自動同期を有効にする（ファイル監視）")
        sync_layout.addWidget(self.auto_sync_check)
        
        self.backup_enabled_check = QCheckBox("上書き前にバックアップを作成する")
        self.backup_enabled_check.setChecked(True)
        sync_layout.addWidget(self.backup_enabled_check)
        
        layout.addWidget(sync_group)
        
        layout.addStretch()
        return tab
    
    def create_mapping_tab(self) -> QWidget:
        """ファイルマッピングタブ作成"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # 説明
        help_text = QLabel(
            "同一フォルダ内のファイルを異なる同期先に振り分けることができます。\n"
            "例：ボタン画像は ui/buttons フォルダ、アイコン画像は ui/icons フォルダ など"
        )
        help_text.setWordWrap(True)
        help_text.setStyleSheet("color: #666666; font-size: 10px; margin-bottom: 10px;")
        layout.addWidget(help_text)
        
        # マッピング有効化
        self.mapping_enabled_check = QCheckBox("ファイル振り分け機能を有効にする")
        layout.addWidget(self.mapping_enabled_check)
        
        # マッピングルールリスト
        mapping_group = QGroupBox("振り分けルール")
        mapping_layout = QVBoxLayout(mapping_group)
        
        # マッピングルール操作ボタン
        mapping_btn_layout = QHBoxLayout()
        self.mapping_add_btn = QPushButton("ルール追加")
        self.mapping_edit_btn = QPushButton("ルール編集")
        self.mapping_remove_btn = QPushButton("ルール削除")
        
        self.mapping_add_btn.clicked.connect(self.add_mapping_rule)
        self.mapping_edit_btn.clicked.connect(self.edit_mapping_rule)
        self.mapping_remove_btn.clicked.connect(self.remove_mapping_rule)
        
        mapping_btn_layout.addWidget(self.mapping_add_btn)
        mapping_btn_layout.addWidget(self.mapping_edit_btn)
        mapping_btn_layout.addWidget(self.mapping_remove_btn)
        mapping_btn_layout.addStretch()
        
        mapping_layout.addLayout(mapping_btn_layout)
        
        # マッピングルールテーブル
        from PySide6.QtWidgets import QTableWidget, QHeaderView
        self.mapping_table = QTableWidget()
        self.mapping_table.setColumnCount(4)
        self.mapping_table.setHorizontalHeaderLabels(["パターン", "振り分け先", "説明", "有効"])
        
        # テーブルの列幅調整
        header = self.mapping_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        
        mapping_layout.addWidget(self.mapping_table)
        layout.addWidget(mapping_group)
        
        # サンプルルール例
        sample_group = QGroupBox("サンプルルール")
        sample_layout = QVBoxLayout(sample_group)
        
        sample_text = QLabel(
            "• button_*.png → ui/buttons （ボタン類）\n"
            "• icon_*.png → ui/icons （アイコン類）\n"
            "• bg_*.jpg → backgrounds （背景画像）\n"
            "• se_*.wav → audio/se （効果音）\n"
            "• regex:.*_ui\\.(png|jpg) → ui （UI画像全般）"
        )
        sample_text.setStyleSheet("font-family: 'Consolas', monospace; font-size: 9px; color: #555555;")
        sample_layout.addWidget(sample_text)
        
        # サンプル追加ボタン
        sample_btn_layout = QHBoxLayout()
        
        sample_buttons = [
            ("ボタン用ルール", "button_*", "ui/buttons"),
            ("アイコン用ルール", "icon_*", "ui/icons"),
            ("背景用ルール", "bg_*", "backgrounds"),
            ("UI画像用ルール", "regex:.*_ui\\.(png|jpg)", "ui"),
        ]
        
        for name, pattern, target in sample_buttons:
            btn = QPushButton(name)
            btn.clicked.connect(lambda checked, p=pattern, t=target, n=name: self.add_sample_rule(n, p, t))
            sample_btn_layout.addWidget(btn)
        
        sample_btn_layout.addStretch()
        sample_layout.addLayout(sample_btn_layout)
        layout.addWidget(sample_group)
        
        return tab
    
    def load_folder_pair_data(self):
        """フォルダペアデータを読み込み"""
        if not self.folder_pair:
            return
        
        # 基本情報
        self.name_edit.setText(self.folder_pair.name)
        self.source_path_edit.setText(self.folder_pair.source_path)
        self.target_path_edit.setText(self.folder_pair.target_path)
        
        # フィルタ設定
        filter_rule = self.folder_pair.filter_rule
        self.filter_enabled_check.setChecked(filter_rule.enabled)
        
        # 含むパターン
        for pattern in filter_rule.include_patterns:
            item = QListWidgetItem(pattern)
            self.include_list.addItem(item)
        
        # 除外パターン
        for pattern in filter_rule.exclude_patterns:
            item = QListWidgetItem(pattern)
            self.exclude_list.addItem(item)
        
        # オプション
        self.enabled_check.setChecked(self.folder_pair.enabled)
        self.auto_sync_check.setChecked(self.folder_pair.auto_sync)
        self.backup_enabled_check.setChecked(self.folder_pair.backup_enabled)
        
        # ファイルマッピング
        if hasattr(self.folder_pair, 'file_mapping_rules'):
            self.mapping_enabled_check.setChecked(len(self.folder_pair.file_mapping_rules) > 0)
            self.load_mapping_rules()
        
        # 情報表示
        if hasattr(self, 'id_label'):
            self.id_label.setText(self.folder_pair.id)
            last_sync = self.folder_pair.last_sync or "未同期"
            self.last_sync_label.setText(last_sync)
    
    def get_folder_data(self) -> Dict:
        """フォルダペアデータを取得"""
        # 含むパターン収集
        include_patterns = []
        for i in range(self.include_list.count()):
            pattern = self.include_list.item(i).text().strip()
            if pattern:
                include_patterns.append(pattern)
        
        # 除外パターン収集
        exclude_patterns = []
        for i in range(self.exclude_list.count()):
            pattern = self.exclude_list.item(i).text().strip()
            if pattern:
                exclude_patterns.append(pattern)
        
        return {
            'name': self.name_edit.text().strip(),
            'source_path': self.source_path_edit.text().strip(),
            'target_path': self.target_path_edit.text().strip(),
            'include_patterns': include_patterns,
            'exclude_patterns': exclude_patterns,
            'filter_enabled': self.filter_enabled_check.isChecked(),
            'mapping_rules': self.get_mapping_rules() if self.mapping_enabled_check.isChecked() else [],
            'enabled': self.enabled_check.isChecked(),
            'auto_sync': self.auto_sync_check.isChecked(),
            'backup_enabled': self.backup_enabled_check.isChecked()
        }
    
    def validate_input(self) -> bool:
        """入力値検証"""
        name = self.name_edit.text().strip()
        source_path = self.source_path_edit.text().strip()
        target_path = self.target_path_edit.text().strip()
        
        if not name:
            QMessageBox.warning(self, "入力エラー", "名前を入力してください。")
            self.name_edit.setFocus()
            return False
        
        if not source_path:
            QMessageBox.warning(self, "入力エラー", "ソースフォルダパスを入力してください。")
            self.source_path_edit.setFocus()
            return False
        
        if not target_path:
            QMessageBox.warning(self, "入力エラー", "ターゲットフォルダパスを入力してください。")
            self.target_path_edit.setFocus()
            return False
        
        # パス存在チェック
        source = Path(source_path)
        if not source.exists():
            result = QMessageBox.question(
                self, "確認",
                f"ソースフォルダが存在しません: {source_path}\n\n続行しますか？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if result == QMessageBox.No:
                return False
        elif not source.is_dir():
            QMessageBox.warning(self, "入力エラー", f"ソースパスがディレクトリではありません: {source_path}")
            return False
        
        # 同じパスチェック
        if Path(source_path).resolve() == Path(target_path).resolve():
            QMessageBox.warning(self, "入力エラー", "ソースフォルダとターゲットフォルダが同じです。")
            return False
        
        return True
    
    def browse_source_folder(self):
        """ソースフォルダを選択"""
        folder = QFileDialog.getExistingDirectory(
            self, "ソースフォルダを選択", self.source_path_edit.text()
        )
        if folder:
            self.source_path_edit.setText(folder)
    
    def browse_target_folder(self):
        """ターゲットフォルダを選択"""
        folder = QFileDialog.getExistingDirectory(
            self, "ターゲットフォルダを選択", self.target_path_edit.text()
        )
        if folder:
            self.target_path_edit.setText(folder)
    
    def add_include_pattern(self):
        """含むパターン追加"""
        from PySide6.QtWidgets import QInputDialog
        
        pattern, ok = QInputDialog.getText(
            self, "パターン追加", "含むパターンを入力してください:"
        )
        
        if ok and pattern.strip():
            item = QListWidgetItem(pattern.strip())
            self.include_list.addItem(item)
    
    def remove_include_pattern(self):
        """含むパターン削除"""
        current_item = self.include_list.currentItem()
        if current_item:
            self.include_list.takeItem(self.include_list.row(current_item))
    
    def edit_include_pattern(self):
        """含むパターン編集"""
        current_item = self.include_list.currentItem()
        if not current_item:
            return
        
        from PySide6.QtWidgets import QInputDialog
        
        pattern, ok = QInputDialog.getText(
            self, "パターン編集", "含むパターンを編集してください:",
            text=current_item.text()
        )
        
        if ok and pattern.strip():
            current_item.setText(pattern.strip())
    
    def add_exclude_pattern(self):
        """除外パターン追加"""
        from PySide6.QtWidgets import QInputDialog
        
        pattern, ok = QInputDialog.getText(
            self, "パターン追加", "除外パターンを入力してください:"
        )
        
        if ok and pattern.strip():
            item = QListWidgetItem(pattern.strip())
            self.exclude_list.addItem(item)
    
    def remove_exclude_pattern(self):
        """除外パターン削除"""
        current_item = self.exclude_list.currentItem()
        if current_item:
            self.exclude_list.takeItem(self.exclude_list.row(current_item))
    
    def edit_exclude_pattern(self):
        """除外パターン編集"""
        current_item = self.exclude_list.currentItem()
        if not current_item:
            return
        
        from PySide6.QtWidgets import QInputDialog
        
        pattern, ok = QInputDialog.getText(
            self, "パターン編集", "除外パターンを編集してください:",
            text=current_item.text()
        )
        
        if ok and pattern.strip():
            current_item.setText(pattern.strip())
    
    def add_common_patterns(self, patterns: List[str]):
        """よく使用されるパターンを追加"""
        # デフォルトで含むパターンに追加（一時ファイルは除外に）
        if "一時ファイル" in str(patterns):
            list_widget = self.exclude_list
        else:
            list_widget = self.include_list
        
        for pattern in patterns:
            # 重複チェック
            exists = False
            for i in range(list_widget.count()):
                if list_widget.item(i).text() == pattern:
                    exists = True
                    break
            
            if not exists:
                item = QListWidgetItem(pattern)
                list_widget.addItem(item)
    
    def open_source_folder(self):
        """ソースフォルダを開く"""
        folder_path = self.source_path_edit.text().strip()
        if folder_path:
            self.open_folder(folder_path)
        else:
            QMessageBox.information(self, "情報", "ソースフォルダパスが入力されていません。")
    
    def open_target_folder(self):
        """ターゲットフォルダを開く"""
        folder_path = self.target_path_edit.text().strip()
        if folder_path:
            self.open_folder(folder_path)
        else:
            QMessageBox.information(self, "情報", "ターゲットフォルダパスが入力されていません。")
    
    def open_folder(self, folder_path: str):
        """フォルダをエクスプローラで開く"""
        try:
            path = Path(folder_path).resolve()
            if path.exists():
                if path.is_dir():
                    QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
                else:
                    # ファイルの場合は親フォルダを開く
                    QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.parent)))
            else:
                # 存在しない場合は親フォルダを確認
                parent = path.parent
                if parent.exists():
                    result = QMessageBox.question(
                        self, "確認",
                        f"指定されたフォルダが存在しません: {path}\n\n親フォルダを開きますか？",
                        QMessageBox.Yes | QMessageBox.No,
                        QMessageBox.Yes
                    )
                    if result == QMessageBox.Yes:
                        QDesktopServices.openUrl(QUrl.fromLocalFile(str(parent)))
                else:
                    QMessageBox.warning(self, "警告", f"フォルダが存在しません: {folder_path}")
        except Exception as e:
            QMessageBox.critical(self, "エラー", f"フォルダを開くのに失敗しました: {e}")
    
    def add_mapping_rule(self):
        """マッピングルールを追加"""
        from PySide6.QtWidgets import QInputDialog, QDialog, QVBoxLayout, QFormLayout
        
        # カスタムダイアログを作成
        dialog = QDialog(self)
        dialog.setWindowTitle("振り分けルール追加")
        dialog.setModal(True)
        dialog.resize(400, 200)
        
        layout = QVBoxLayout(dialog)
        form_layout = QFormLayout()
        
        pattern_edit = QLineEdit()
        pattern_edit.setPlaceholderText("例: button_*, *.png, regex:.*_ui\\.(png|jpg)")
        target_edit = QLineEdit() 
        target_edit.setPlaceholderText("例: ui/buttons, icons")
        desc_edit = QLineEdit()
        desc_edit.setPlaceholderText("説明（任意）")
        
        form_layout.addRow("パターン:", pattern_edit)
        form_layout.addRow("振り分け先:", target_edit)
        form_layout.addRow("説明:", desc_edit)
        
        layout.addLayout(form_layout)
        
        # ボタン
        btn_layout = QHBoxLayout()
        ok_btn = QPushButton("OK")
        cancel_btn = QPushButton("キャンセル")
        
        ok_btn.clicked.connect(dialog.accept)
        cancel_btn.clicked.connect(dialog.reject)
        
        btn_layout.addStretch()
        btn_layout.addWidget(ok_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)
        
        if dialog.exec() == QDialog.Accepted:
            pattern = pattern_edit.text().strip()
            target = target_edit.text().strip()
            description = desc_edit.text().strip()
            
            if pattern and target:
                self.add_mapping_rule_to_table(pattern, target, description, True)
    
    def edit_mapping_rule(self):
        """マッピングルールを編集"""
        current_row = self.mapping_table.currentRow()
        if current_row < 0:
            QMessageBox.information(self, "情報", "編集するルールを選択してください。")
            return
        
        # 現在の値を取得
        pattern_item = self.mapping_table.item(current_row, 0)
        target_item = self.mapping_table.item(current_row, 1)
        desc_item = self.mapping_table.item(current_row, 2)
        enabled_item = self.mapping_table.item(current_row, 3)
        
        if not all([pattern_item, target_item, desc_item, enabled_item]):
            return
        
        # カスタムダイアログを作成
        dialog = QDialog(self)
        dialog.setWindowTitle("振り分けルール編集")
        dialog.setModal(True)
        dialog.resize(400, 200)
        
        layout = QVBoxLayout(dialog)
        form_layout = QFormLayout()
        
        pattern_edit = QLineEdit(pattern_item.text())
        target_edit = QLineEdit(target_item.text())
        desc_edit = QLineEdit(desc_item.text())
        enabled_check = QCheckBox("有効")
        enabled_check.setChecked(enabled_item.text() == "有効")
        
        form_layout.addRow("パターン:", pattern_edit)
        form_layout.addRow("振り分け先:", target_edit)
        form_layout.addRow("説明:", desc_edit)
        form_layout.addRow("", enabled_check)
        
        layout.addLayout(form_layout)
        
        # ボタン
        btn_layout = QHBoxLayout()
        ok_btn = QPushButton("OK")
        cancel_btn = QPushButton("キャンセル")
        
        ok_btn.clicked.connect(dialog.accept)
        cancel_btn.clicked.connect(dialog.reject)
        
        btn_layout.addStretch()
        btn_layout.addWidget(ok_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)
        
        if dialog.exec() == QDialog.Accepted:
            pattern_item.setText(pattern_edit.text().strip())
            target_item.setText(target_edit.text().strip())
            desc_item.setText(desc_edit.text().strip())
            enabled_item.setText("有効" if enabled_check.isChecked() else "無効")
    
    def remove_mapping_rule(self):
        """マッピングルールを削除"""
        current_row = self.mapping_table.currentRow()
        if current_row < 0:
            QMessageBox.information(self, "情報", "削除するルールを選択してください。")
            return
        
        pattern_item = self.mapping_table.item(current_row, 0)
        if pattern_item:
            result = QMessageBox.question(
                self, "確認",
                f"ルール '{pattern_item.text()}' を削除しますか？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            
            if result == QMessageBox.Yes:
                self.mapping_table.removeRow(current_row)
    
    def add_sample_rule(self, name: str, pattern: str, target: str):
        """サンプルルールを追加"""
        # 重複チェック
        for row in range(self.mapping_table.rowCount()):
            pattern_item = self.mapping_table.item(row, 0)
            if pattern_item and pattern_item.text() == pattern:
                QMessageBox.information(self, "情報", f"パターン '{pattern}' は既に存在します。")
                return
        
        description = name.replace("用ルール", "")
        self.add_mapping_rule_to_table(pattern, target, description, True)
    
    def add_mapping_rule_to_table(self, pattern: str, target: str, description: str, enabled: bool):
        """マッピングルールをテーブルに追加"""
        from PySide6.QtWidgets import QTableWidgetItem
        
        row = self.mapping_table.rowCount()
        self.mapping_table.insertRow(row)
        
        self.mapping_table.setItem(row, 0, QTableWidgetItem(pattern))
        self.mapping_table.setItem(row, 1, QTableWidgetItem(target))
        self.mapping_table.setItem(row, 2, QTableWidgetItem(description))
        self.mapping_table.setItem(row, 3, QTableWidgetItem("有効" if enabled else "無効"))
    
    def load_mapping_rules(self):
        """マッピングルールをテーブルに読み込み"""
        if not self.folder_pair or not hasattr(self.folder_pair, 'file_mapping_rules'):
            return
        
        self.mapping_table.setRowCount(0)
        for rule in self.folder_pair.file_mapping_rules:
            self.add_mapping_rule_to_table(rule.pattern, rule.target_subpath, rule.description, rule.enabled)
    
    def get_mapping_rules(self) -> List[FileMappingRule]:
        """テーブルからマッピングルールを取得"""
        rules = []
        for row in range(self.mapping_table.rowCount()):
            pattern_item = self.mapping_table.item(row, 0)
            target_item = self.mapping_table.item(row, 1)
            desc_item = self.mapping_table.item(row, 2)
            enabled_item = self.mapping_table.item(row, 3)
            
            if pattern_item and target_item and desc_item and enabled_item:
                rule = FileMappingRule(
                    id=str(uuid.uuid4()),
                    pattern=pattern_item.text(),
                    target_subpath=target_item.text(),
                    description=desc_item.text(),
                    enabled=enabled_item.text() == "有効"
                )
                rules.append(rule)
        
        return rules
    
    def accept_dialog(self):
        """OK ボタンクリック"""
        if self.validate_input():
            self.accept()