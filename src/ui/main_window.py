"""
メインウィンドウ
"""

import sys
from pathlib import Path
from typing import Optional, List

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QTreeWidget, QTreeWidgetItem, QTableWidget, QTableWidgetItem,
    QTabWidget, QPushButton, QLabel, QComboBox, QProgressBar,
    QTextEdit, QMenuBar, QMenu, QStatusBar, QMessageBox,
    QFileDialog, QGroupBox, QCheckBox, QSpinBox, QFormLayout
)
from PySide6.QtCore import Qt, QTimer, QThread, Signal, QSize, QDateTime, QObject, QUrl
from PySide6.QtGui import QAction, QIcon, QFont, QDesktopServices

from core.project_manager import ProjectManager
from core.sync_engine import SyncEngine, SyncOptions, SyncProgressCallback
from core.file_watcher import FileWatcher, WatchEvent
from config.config_manager import ConfigManager
from utils.logger import get_logger, init_global_logger
from ui.project_dialog import ProjectDialog
from ui.sync_dialog import SyncDialog
from ui.drag_drop_tree import DragDropTreeWidget


class SyncThread(QThread):
    """同期処理スレッド"""
    
    progress = Signal(int, int, str, str)  # current, total, file_path, status
    finished = Signal(object)  # SyncResult
    error = Signal(str)
    
    def __init__(self, sync_engine, folder_pair, options):
        super().__init__()
        self.sync_engine = sync_engine
        self.folder_pair = folder_pair
        self.options = options
    
    def run(self):
        """同期実行"""
        try:
            callback = SyncCallback()
            callback.progress.connect(self.progress.emit)
            callback.error.connect(self.error.emit)
            
            result = self.sync_engine.sync_folder_pair(
                self.folder_pair, self.options, callback
            )
            self.finished.emit(result)
            
        except Exception as e:
            self.error.emit(f"同期エラー: {e}")


class MultipleSyncThread(QThread):
    """複数フォルダペア同期処理スレッド"""
    
    progress = Signal(int, int, str, str)  # current, total, file_path, status
    finished = Signal(object)  # SyncResult
    error = Signal(str)
    
    def __init__(self, sync_engine, folder_pairs, options):
        super().__init__()
        self.sync_engine = sync_engine
        self.folder_pairs = folder_pairs
        self.options = options
    
    def run(self):
        """複数同期実行"""
        try:
            callback = SyncCallback()
            callback.progress.connect(self.progress.emit)
            callback.error.connect(self.error.emit)
            
            result = self.sync_engine.sync_multiple_folder_pairs(
                self.folder_pairs, self.options, callback
            )
            self.finished.emit(result)
            
        except Exception as e:
            self.error.emit(f"複数同期エラー: {e}")


class SyncCallback(QObject, SyncProgressCallback):
    """同期進捗コールバック（Qt版）"""
    
    progress = Signal(int, int, str, str)
    error = Signal(str)
    
    def on_file_progress(self, current, total, file_path, status):
        self.progress.emit(current, total, file_path, status)
    
    def on_error(self, error):
        self.error.emit(error)


class MainWindow(QMainWindow):
    """メインウィンドウ"""
    
    def __init__(self):
        super().__init__()
        
        # ログ初期化
        self.logger = init_global_logger()
        
        # コア機能初期化
        self.config_manager = ConfigManager()
        self.project_manager = ProjectManager(self.config_manager)
        self.sync_engine = SyncEngine()
        self.file_watcher = FileWatcher()
        
        # UI初期化
        self.sync_thread = None
        self.init_ui()
        self.connect_signals()
        self.load_settings()
        
        # 最後に使ったプロジェクトを読み込み
        self.load_last_project()
        
        self.logger.info("メインウィンドウ初期化完了")
    
    def init_ui(self):
        """UI初期化"""
        self.setWindowTitle("YrYr Asset Sync - ゲーム開発用リソース同期ツール")
        self.setMinimumSize(1000, 700)
        
        # 中央ウィジェット
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # レイアウト
        main_layout = QVBoxLayout(central_widget)
        
        # ツールバー
        toolbar_layout = self.create_toolbar()
        main_layout.addLayout(toolbar_layout)
        
        # スプリッター（左右分割）
        splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(splitter)
        
        # 左パネル（プロジェクト・フォルダペア）
        left_panel = self.create_left_panel()
        splitter.addWidget(left_panel)
        
        # 右パネル（詳細・ログ）
        right_panel = self.create_right_panel()
        splitter.addWidget(right_panel)
        
        # スプリッター比率設定
        splitter.setSizes([400, 600])
        
        # ステータスバー
        self.create_status_bar()
        
        # メニューバー
        self.create_menu_bar()
    
    def create_toolbar(self) -> QHBoxLayout:
        """ツールバー作成"""
        toolbar_layout = QHBoxLayout()
        
        # プロジェクト選択
        self.project_combo = QComboBox()
        self.project_combo.setMinimumWidth(200)
        self.project_combo.currentTextChanged.connect(self.on_project_changed)
        
        toolbar_layout.addWidget(QLabel("プロジェクト:"))
        toolbar_layout.addWidget(self.project_combo)
        
        # プロジェクト管理ボタン
        self.new_project_btn = QPushButton("新規")
        self.edit_project_btn = QPushButton("編集")
        self.delete_project_btn = QPushButton("削除")
        
        toolbar_layout.addWidget(self.new_project_btn)
        toolbar_layout.addWidget(self.edit_project_btn)
        toolbar_layout.addWidget(self.delete_project_btn)
        
        toolbar_layout.addStretch()
        
        # 監視状態表示
        self.watch_status_label = QLabel("監視: 停止中")
        toolbar_layout.addWidget(self.watch_status_label)
        
        # 監視制御ボタン
        self.start_watch_btn = QPushButton("監視開始")
        self.stop_watch_btn = QPushButton("監視停止")
        self.stop_watch_btn.setEnabled(False)
        
        toolbar_layout.addWidget(self.start_watch_btn)
        toolbar_layout.addWidget(self.stop_watch_btn)
        
        return toolbar_layout
    
    def create_left_panel(self) -> QWidget:
        """左パネル作成"""
        left_panel = QWidget()
        layout = QVBoxLayout(left_panel)
        
        # フォルダペア一覧
        folder_group = QGroupBox("フォルダペア")
        folder_layout = QVBoxLayout(folder_group)
        
        # フォルダペア操作ボタン
        folder_btn_layout = QHBoxLayout()
        self.add_folder_btn = QPushButton("追加")
        self.edit_folder_btn = QPushButton("編集")
        self.remove_folder_btn = QPushButton("削除")
        self.sync_folder_btn = QPushButton("選択同期")
        
        folder_btn_layout.addWidget(self.add_folder_btn)
        folder_btn_layout.addWidget(self.edit_folder_btn)
        folder_btn_layout.addWidget(self.remove_folder_btn)
        folder_btn_layout.addStretch()
        folder_btn_layout.addWidget(self.sync_folder_btn)
        
        folder_layout.addLayout(folder_btn_layout)
        
        # フォルダペアツリー（ドラッグ&ドロップ対応）
        self.folder_tree = DragDropTreeWidget()
        self.folder_tree.setHeaderLabels(["名前", "ソース", "ターゲット", "状態"])
        self.folder_tree.setSelectionMode(QTreeWidget.ExtendedSelection)  # 一般的な複数選択動作
        self.folder_tree.itemSelectionChanged.connect(self.on_folder_selection_changed)
        self.folder_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.folder_tree.customContextMenuRequested.connect(self.show_folder_context_menu)
        self.folder_tree.set_drop_callback(self.on_folders_dropped)
        
        folder_layout.addWidget(self.folder_tree)
        layout.addWidget(folder_group)
        
        # 同期オプション
        options_group = QGroupBox("同期オプション")
        options_layout = QFormLayout(options_group)
        
        self.force_copy_check = QCheckBox("強制コピー（日付無視）")
        self.create_backup_check = QCheckBox("バックアップ作成")
        self.create_backup_check.setChecked(True)
        self.preserve_timestamp_check = QCheckBox("タイムスタンプ保持")
        self.preserve_timestamp_check.setChecked(True)
        self.dry_run_check = QCheckBox("ドライラン（実際にコピーしない）")
        
        self.max_workers_spin = QSpinBox()
        self.max_workers_spin.setRange(1, 8)
        self.max_workers_spin.setValue(4)
        
        options_layout.addRow(self.force_copy_check)
        options_layout.addRow(self.create_backup_check)
        options_layout.addRow(self.preserve_timestamp_check)
        options_layout.addRow(self.dry_run_check)
        options_layout.addRow("並行処理数:", self.max_workers_spin)
        
        layout.addWidget(options_group)
        
        return left_panel
    
    def create_right_panel(self) -> QWidget:
        """右パネル作成"""
        right_panel = QTabWidget()
        
        # 同期状況タブ
        sync_tab = QWidget()
        sync_layout = QVBoxLayout(sync_tab)
        
        # プログレスバー
        self.progress_bar = QProgressBar()
        self.progress_label = QLabel("準備完了")
        
        sync_layout.addWidget(self.progress_label)
        sync_layout.addWidget(self.progress_bar)
        
        # 同期結果テーブル
        self.sync_result_table = QTableWidget()
        self.sync_result_table.setColumnCount(4)
        self.sync_result_table.setHorizontalHeaderLabels(["ファイル", "状態", "サイズ", "時刻"])
        self.sync_result_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.sync_result_table.customContextMenuRequested.connect(self.show_result_context_menu)
        
        sync_layout.addWidget(self.sync_result_table)
        
        right_panel.addTab(sync_tab, "同期状況")
        
        # ログタブ
        log_tab = QWidget()
        log_layout = QVBoxLayout(log_tab)
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Consolas", 9))
        
        log_layout.addWidget(self.log_text)
        
        right_panel.addTab(log_tab, "ログ")
        
        return right_panel
    
    def create_status_bar(self):
        """ステータスバー作成"""
        self.status_bar = self.statusBar()
        self.status_bar.showMessage("準備完了")
        
        # 常駐表示アイテム
        self.project_status_label = QLabel("プロジェクト: なし")
        self.sync_status_label = QLabel("同期: 待機中")
        
        self.status_bar.addPermanentWidget(self.project_status_label)
        self.status_bar.addPermanentWidget(self.sync_status_label)
    
    def create_menu_bar(self):
        """メニューバー作成"""
        menubar = self.menuBar()
        
        # ファイルメニュー
        file_menu = menubar.addMenu("ファイル(&F)")
        
        new_project_action = QAction("新しいプロジェクト(&N)", self)
        new_project_action.setShortcut("Ctrl+N")
        new_project_action.triggered.connect(self.new_project)
        file_menu.addAction(new_project_action)
        
        open_project_action = QAction("プロジェクトを開く(&O)", self)
        open_project_action.setShortcut("Ctrl+O")
        open_project_action.triggered.connect(self.open_project)
        file_menu.addAction(open_project_action)
        
        file_menu.addSeparator()
        
        import_action = QAction("プロジェクトをインポート(&I)", self)
        import_action.triggered.connect(self.import_project)
        file_menu.addAction(import_action)
        
        export_action = QAction("プロジェクトをエクスポート(&E)", self)
        export_action.triggered.connect(self.export_project)
        file_menu.addAction(export_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction("終了(&X)", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # 同期メニュー
        sync_menu = menubar.addMenu("同期(&S)")
        
        sync_all_action = QAction("全て同期(&A)", self)
        sync_all_action.setShortcut("F5")
        sync_all_action.triggered.connect(self.sync_all)
        sync_menu.addAction(sync_all_action)
        
        sync_selected_action = QAction("選択を同期(&S)", self)
        sync_selected_action.setShortcut("Ctrl+F5")
        sync_selected_action.triggered.connect(self.sync_selected)
        sync_menu.addAction(sync_selected_action)
        
        # フォルダメニュー  
        folder_menu = menubar.addMenu("フォルダ(&D)")
        
        recent_folders_menu = QMenu("最近開いたフォルダ(&R)", self)
        folder_menu.addMenu(recent_folders_menu)
        
        # 最近開いたフォルダリストを更新
        self.update_recent_folders_menu(recent_folders_menu)
        
        folder_menu.addSeparator()
        
        open_data_folder_action = QAction("データフォルダを開く(&D)", self)
        open_data_folder_action.triggered.connect(self.open_data_folder)
        folder_menu.addAction(open_data_folder_action)
        
        open_log_folder_action = QAction("ログフォルダを開く(&L)", self)
        open_log_folder_action.triggered.connect(self.open_log_folder)
        folder_menu.addAction(open_log_folder_action)
        
        # ヘルプメニュー
        help_menu = menubar.addMenu("ヘルプ(&H)")
        
        about_action = QAction("YrYr Asset Syncについて(&A)", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
    
    def connect_signals(self):
        """シグナル接続"""
        # ボタンクリックイベント
        self.new_project_btn.clicked.connect(self.new_project)
        self.edit_project_btn.clicked.connect(self.edit_project)
        self.delete_project_btn.clicked.connect(self.delete_project)
        
        self.add_folder_btn.clicked.connect(self.add_folder_pair)
        self.edit_folder_btn.clicked.connect(self.edit_folder_pair)
        self.remove_folder_btn.clicked.connect(self.remove_folder_pair)
        self.sync_folder_btn.clicked.connect(self.sync_selected)
        
        self.start_watch_btn.clicked.connect(self.start_file_watching)
        self.stop_watch_btn.clicked.connect(self.stop_file_watching)
        
        # ファイル監視イベント
        if self.file_watcher.is_available():
            self.file_watcher.add_callback(self.on_file_changed)
    
    def load_settings(self):
        """設定読み込み"""
        settings = self.config_manager.app_settings
        
        # ウィンドウサイズ・位置
        geometry = settings.window_geometry
        if geometry:
            self.resize(geometry.get('width', 1000), geometry.get('height', 700))
            self.move(geometry.get('x', 100), geometry.get('y', 100))
    
    def save_settings(self):
        """設定保存"""
        # ウィンドウサイズ・位置保存
        geometry = self.geometry()
        self.config_manager.app_settings.window_geometry = {
            'width': geometry.width(),
            'height': geometry.height(),
            'x': geometry.x(),
            'y': geometry.y()
        }
        
        self.config_manager.save_app_settings()
    
    def load_last_project(self):
        """最後に使用したプロジェクトを読み込み"""
        current_project_id = self.config_manager.app_settings.current_project_id
        if current_project_id:
            if self.project_manager.load_project(current_project_id):
                self.refresh_ui()
    
    def refresh_project_list(self):
        """プロジェクト一覧を更新"""
        self.project_combo.clear()
        
        projects = self.project_manager.list_all_projects()
        for project in projects:
            self.project_combo.addItem(project['name'], project['id'])
        
        # 現在のプロジェクトを選択
        if self.project_manager.current_project:
            for i in range(self.project_combo.count()):
                if self.project_combo.itemData(i) == self.project_manager.current_project.id:
                    self.project_combo.setCurrentIndex(i)
                    break
    
    def refresh_folder_pairs(self):
        """フォルダペア一覧を更新"""
        self.folder_tree.clear()
        
        if not self.project_manager.current_project:
            return
        
        for folder_pair in self.project_manager.current_project.folder_pairs:
            item = QTreeWidgetItem(self.folder_tree)
            item.setText(0, folder_pair.name)
            item.setText(1, folder_pair.source_path)
            item.setText(2, folder_pair.target_path)
            item.setText(3, "有効" if folder_pair.enabled else "無効")
            item.setData(0, Qt.UserRole, folder_pair.id)
        
        self.folder_tree.resizeColumnToContents(0)
        self.folder_tree.resizeColumnToContents(3)
    
    def refresh_ui(self):
        """UI全体を更新"""
        self.refresh_project_list()
        self.refresh_folder_pairs()
        
        # ステータス更新
        if self.project_manager.current_project:
            self.project_status_label.setText(f"プロジェクト: {self.project_manager.current_project.name}")
        else:
            self.project_status_label.setText("プロジェクト: なし")
    
    def get_sync_options(self) -> SyncOptions:
        """UI設定から同期オプションを取得"""
        return SyncOptions(
            force_copy=self.force_copy_check.isChecked(),
            create_backup=self.create_backup_check.isChecked(),
            preserve_timestamp=self.preserve_timestamp_check.isChecked(),
            dry_run=self.dry_run_check.isChecked(),
            max_workers=self.max_workers_spin.value()
        )
    
    def add_log_message(self, message: str):
        """ログメッセージを追加"""
        self.log_text.append(message)
        self.log_text.ensureCursorVisible()
    
    # イベントハンドラ
    def on_project_changed(self, project_name: str):
        """プロジェクト変更"""
        if not project_name:
            return
        
        project_id = self.project_combo.currentData()
        if project_id and project_id != (self.project_manager.current_project.id if self.project_manager.current_project else None):
            if self.project_manager.load_project(project_id):
                self.refresh_ui()
                self.add_log_message(f"プロジェクト切り替え: {project_name}")
    
    def on_folder_selection_changed(self):
        """フォルダペア選択変更"""
        selected_items = self.folder_tree.selectedItems()
        has_selection = len(selected_items) > 0
        single_selection = len(selected_items) == 1
        
        # 編集・削除は単一選択のみ有効
        self.edit_folder_btn.setEnabled(single_selection)
        self.remove_folder_btn.setEnabled(single_selection)
        
        # 同期は選択があれば有効（複数選択対応）
        self.sync_folder_btn.setEnabled(has_selection)
    
    def on_file_changed(self, event: WatchEvent):
        """ファイル変更イベント"""
        self.add_log_message(f"ファイル{event.event_type}: {event.file_path}")
        
        # 自動同期が有効な場合は同期を実行
        folder_pair = self.project_manager.get_folder_pair(event.folder_pair_id)
        if folder_pair and folder_pair.auto_sync:
            # TODO: 自動同期実装
            pass
    
    # アクション実装
    def new_project(self):
        """新しいプロジェクト作成"""
        dialog = ProjectDialog(self)
        if dialog.exec() == ProjectDialog.Accepted:
            project_data = dialog.get_project_data()
            project = self.project_manager.create_new_project(
                project_data['name'],
                project_data['description']
            )
            if project:
                self.project_manager.load_project(project.id)
                self.refresh_ui()
                self.add_log_message(f"新しいプロジェクトを作成しました: {project.name}")
    
    def edit_project(self):
        """プロジェクト編集"""
        if not self.project_manager.current_project:
            QMessageBox.warning(self, "警告", "編集するプロジェクトがありません。")
            return
        
        dialog = ProjectDialog(self, self.project_manager.current_project)
        if dialog.exec() == ProjectDialog.Accepted:
            project_data = dialog.get_project_data()
            self.project_manager.current_project.name = project_data['name']
            self.project_manager.current_project.description = project_data['description']
            self.project_manager.save_current_project()
            self.refresh_ui()
            self.add_log_message("プロジェクトを更新しました")
    
    def delete_project(self):
        """プロジェクト削除"""
        if not self.project_manager.current_project:
            QMessageBox.warning(self, "警告", "削除するプロジェクトがありません。")
            return
        
        project_name = self.project_manager.current_project.name
        result = QMessageBox.question(
            self, "確認",
            f"プロジェクト '{project_name}' を削除しますか？\n\nこの操作は元に戻せません。",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if result == QMessageBox.Yes:
            project_id = self.project_manager.current_project.id
            if self.project_manager.delete_project(project_id):
                self.refresh_ui()
                self.add_log_message(f"プロジェクトを削除しました: {project_name}")
            else:
                QMessageBox.critical(self, "エラー", "プロジェクトの削除に失敗しました。")
    
    def open_project(self):
        """プロジェクトを開く"""
        projects = self.project_manager.list_all_projects()
        if not projects:
            QMessageBox.information(self, "情報", "開くプロジェクトがありません。")
            return
        
        # プロジェクト選択ダイアログを表示（簡易版）
        # TODO: より詳細なプロジェクト選択ダイアログを実装
        pass
    
    def import_project(self):
        """プロジェクトインポート"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "プロジェクトファイルを選択", "", "JSON Files (*.json)"
        )
        
        if file_path:
            project = self.project_manager.import_project(file_path)
            if project:
                self.project_manager.load_project(project.id)
                self.refresh_ui()
                self.add_log_message(f"プロジェクトをインポートしました: {project.name}")
            else:
                QMessageBox.critical(self, "エラー", "プロジェクトのインポートに失敗しました。")
    
    def export_project(self):
        """プロジェクトエクスポート"""
        if not self.project_manager.current_project:
            QMessageBox.warning(self, "警告", "エクスポートするプロジェクトがありません。")
            return
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, "エクスポート先を選択", 
            f"{self.project_manager.current_project.name}.json",
            "JSON Files (*.json)"
        )
        
        if file_path:
            if self.project_manager.export_project(self.project_manager.current_project.id, file_path):
                self.add_log_message(f"プロジェクトをエクスポートしました: {file_path}")
            else:
                QMessageBox.critical(self, "エラー", "プロジェクトのエクスポートに失敗しました。")
    
    def add_folder_pair(self):
        """フォルダペア追加"""
        if not self.project_manager.current_project:
            QMessageBox.warning(self, "警告", "プロジェクトが選択されていません。")
            return
        
        dialog = SyncDialog(self)
        if dialog.exec() == SyncDialog.Accepted:
            folder_data = dialog.get_folder_data()
            folder_pair = self.project_manager.add_folder_pair(
                folder_data['name'],
                folder_data['source_path'],
                folder_data['target_path'],
                folder_data['include_patterns'],
                folder_data['exclude_patterns']
            )
            
            # マッピングルールを設定
            if folder_pair and 'mapping_rules' in folder_data and folder_data['mapping_rules']:
                folder_pair.file_mapping_rules = folder_data['mapping_rules']
                self.project_manager.save_current_project()
            
            # リネームルールを設定
            if folder_pair and 'rename_rules' in folder_data and folder_data['rename_rules']:
                folder_pair.file_rename_rules = folder_data['rename_rules']
                self.project_manager.save_current_project()
            
            if folder_pair:
                self.refresh_folder_pairs()
                self.add_log_message(f"フォルダペアを追加しました: {folder_pair.name}")
    
    def edit_folder_pair(self):
        """フォルダペア編集"""
        selected_items = self.folder_tree.selectedItems()
        if not selected_items:
            return
        
        folder_pair_id = selected_items[0].data(0, Qt.UserRole)
        folder_pair = self.project_manager.get_folder_pair(folder_pair_id)
        
        if folder_pair:
            dialog = SyncDialog(self, folder_pair)
            if dialog.exec() == SyncDialog.Accepted:
                folder_data = dialog.get_folder_data()
                self.project_manager.update_folder_pair(
                    folder_pair_id,
                    name=folder_data['name'],
                    source_path=folder_data['source_path'],
                    target_path=folder_data['target_path']
                )
                # TODO: フィルタルール更新も実装
                self.refresh_folder_pairs()
                self.add_log_message(f"フォルダペアを更新しました: {folder_data['name']}")
    
    def remove_folder_pair(self):
        """フォルダペア削除"""
        selected_items = self.folder_tree.selectedItems()
        if not selected_items:
            return
        
        folder_pair_id = selected_items[0].data(0, Qt.UserRole)
        folder_name = selected_items[0].text(0)
        
        result = QMessageBox.question(
            self, "確認",
            f"フォルダペア '{folder_name}' を削除しますか？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if result == QMessageBox.Yes:
            if self.project_manager.remove_folder_pair(folder_pair_id):
                self.refresh_folder_pairs()
                self.add_log_message(f"フォルダペアを削除しました: {folder_name}")
    
    def sync_selected(self):
        """選択されたフォルダペアを同期"""
        selected_items = self.folder_tree.selectedItems()
        if not selected_items:
            self.sync_all()
            return
        
        # 選択されたフォルダペアを取得
        folder_pairs = []
        for item in selected_items:
            folder_pair_id = item.data(0, Qt.UserRole)
            folder_pair = self.project_manager.get_folder_pair(folder_pair_id)
            if folder_pair:
                folder_pairs.append(folder_pair)
        
        if folder_pairs:
            if len(folder_pairs) == 1:
                # 1つの場合は単一同期
                self.start_sync(folder_pairs[0])
            else:
                # 複数の場合は複数同期
                self.start_multiple_sync(folder_pairs)
    
    def sync_all(self):
        """全フォルダペアを同期"""
        folder_pairs = self.project_manager.get_all_folder_pairs()
        enabled_pairs = [fp for fp in folder_pairs if fp.enabled]
        
        if not enabled_pairs:
            QMessageBox.information(self, "情報", "同期するフォルダペアがありません。")
            return
        
        # TODO: 複数フォルダペアの同期実装
        self.start_sync(enabled_pairs[0])  # とりあえず最初のものだけ
    
    def start_sync(self, folder_pair):
        """同期開始"""
        if self.sync_thread and self.sync_thread.isRunning():
            QMessageBox.warning(self, "警告", "既に同期が実行中です。")
            return
        
        options = self.get_sync_options()
        
        self.sync_thread = SyncThread(self.sync_engine, folder_pair, options)
        self.sync_thread.progress.connect(self.on_sync_progress)
        self.sync_thread.finished.connect(self.on_sync_finished)
        self.sync_thread.error.connect(self.on_sync_error)
        
        self.progress_bar.setValue(0)
        self.progress_label.setText(f"同期開始: {folder_pair.name}")
        self.sync_status_label.setText("同期: 実行中")
        
        self.sync_thread.start()
        self.add_log_message(f"同期開始: {folder_pair.name}")
    
    def start_multiple_sync(self, folder_pairs):
        """複数フォルダペアの同期開始"""
        if self.sync_thread and self.sync_thread.isRunning():
            QMessageBox.warning(self, "警告", "既に同期が実行中です。")
            return
        
        options = self.get_sync_options()
        
        self.sync_thread = MultipleSyncThread(self.sync_engine, folder_pairs, options)
        self.sync_thread.progress.connect(self.on_sync_progress)
        self.sync_thread.finished.connect(self.on_sync_finished)
        self.sync_thread.error.connect(self.on_sync_error)
        
        self.progress_bar.setValue(0)
        folder_names = ", ".join([fp.name for fp in folder_pairs])
        self.progress_label.setText(f"複数同期開始: {folder_names}")
        self.sync_status_label.setText("同期: 実行中")
        
        self.sync_thread.start()
        self.add_log_message(f"複数同期開始: {folder_names}")
    
    def start_file_watching(self):
        """ファイル監視開始"""
        if not self.file_watcher.is_available():
            QMessageBox.warning(self, "警告", "ファイル監視機能が利用できません。\nwatchdogライブラリをインストールしてください。")
            return
        
        folder_pairs = self.project_manager.get_all_folder_pairs()
        auto_sync_pairs = [fp for fp in folder_pairs if fp.enabled and fp.auto_sync]
        
        if not auto_sync_pairs:
            QMessageBox.information(self, "情報", "自動同期が有効なフォルダペアがありません。")
            return
        
        if self.file_watcher.start_watching(auto_sync_pairs):
            self.start_watch_btn.setEnabled(False)
            self.stop_watch_btn.setEnabled(True)
            self.watch_status_label.setText("監視: 実行中")
            self.add_log_message("ファイル監視を開始しました")
    
    def stop_file_watching(self):
        """ファイル監視停止"""
        self.file_watcher.stop_watching()
        self.start_watch_btn.setEnabled(True)
        self.stop_watch_btn.setEnabled(False)
        self.watch_status_label.setText("監視: 停止中")
        self.add_log_message("ファイル監視を停止しました")
    
    def on_sync_progress(self, current, total, file_path, status):
        """同期進捗更新"""
        if total > 0:
            progress = int((current / total) * 100)
            self.progress_bar.setValue(progress)
        
        self.progress_label.setText(f"({current}/{total}) {status}: {file_path}")
        
        # 結果テーブルに追加
        row = self.sync_result_table.rowCount()
        self.sync_result_table.insertRow(row)
        self.sync_result_table.setItem(row, 0, QTableWidgetItem(file_path))
        self.sync_result_table.setItem(row, 1, QTableWidgetItem(status))
        self.sync_result_table.setItem(row, 2, QTableWidgetItem(""))  # サイズは後で
        self.sync_result_table.setItem(row, 3, QTableWidgetItem(QDateTime.currentDateTime().toString()))
        
        self.sync_result_table.scrollToBottom()
    
    def on_sync_finished(self, result):
        """同期完了"""
        self.progress_bar.setValue(100)
        self.progress_label.setText("同期完了")
        self.sync_status_label.setText("同期: 完了")
        
        message = f"同期完了 - コピー: {len(result.copied_files)}, " + \
                  f"スキップ: {len(result.skipped_files)}, " + \
                  f"エラー: {len(result.error_files)}"
        
        self.add_log_message(message)
        self.status_bar.showMessage(message, 5000)
    
    def on_sync_error(self, error_message):
        """同期エラー"""
        self.progress_label.setText("同期エラー")
        self.sync_status_label.setText("同期: エラー")
        self.add_log_message(f"同期エラー: {error_message}")
        QMessageBox.critical(self, "同期エラー", error_message)
    
    def show_folder_context_menu(self, position):
        """フォルダペアのコンテキストメニューを表示"""
        item = self.folder_tree.itemAt(position)
        if not item:
            return
        
        folder_pair_id = item.data(0, Qt.UserRole)
        if not folder_pair_id:
            return
        
        folder_pair = self.project_manager.get_folder_pair(folder_pair_id)
        if not folder_pair:
            return
        
        menu = QMenu(self)
        
        # ソースフォルダを開く
        if Path(folder_pair.source_path).exists():
            open_source_action = QAction("ソースフォルダを開く", self)
            open_source_action.triggered.connect(lambda: self.open_folder(folder_pair.source_path))
            menu.addAction(open_source_action)
        
        # ターゲットフォルダを開く
        target_path = Path(folder_pair.target_path)
        if target_path.exists():
            open_target_action = QAction("ターゲットフォルダを開く", self)
            open_target_action.triggered.connect(lambda: self.open_folder(folder_pair.target_path))
            menu.addAction(open_target_action)
        elif target_path.parent.exists():
            open_target_parent_action = QAction("ターゲット親フォルダを開く", self)
            open_target_parent_action.triggered.connect(lambda: self.open_folder(str(target_path.parent)))
            menu.addAction(open_target_parent_action)
        
        menu.addSeparator()
        
        # 編集
        edit_action = QAction("編集", self)
        edit_action.triggered.connect(self.edit_folder_pair)
        menu.addAction(edit_action)
        
        # 同期実行
        sync_action = QAction("同期実行", self)
        sync_action.triggered.connect(lambda: self.start_sync(folder_pair))
        menu.addAction(sync_action)
        
        # 削除
        delete_action = QAction("削除", self)
        delete_action.triggered.connect(self.remove_folder_pair)
        menu.addAction(delete_action)
        
        # メニューを表示
        menu.exec(self.folder_tree.mapToGlobal(position))
    
    def open_folder(self, folder_path: str):
        """フォルダをエクスプローラで開く"""
        try:
            folder_path = Path(folder_path).resolve()
            if folder_path.exists():
                if folder_path.is_dir():
                    # フォルダを開く
                    QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder_path)))
                else:
                    # ファイルの場合は親フォルダを開く
                    QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder_path.parent)))
                
                self.add_log_message(f"フォルダを開きました: {folder_path}")
                
                # 最近開いたフォルダに追加
                self.config_manager.add_recent_folder(str(folder_path))
            else:
                QMessageBox.warning(self, "警告", f"フォルダが存在しません: {folder_path}")
        except Exception as e:
            self.add_log_message(f"フォルダを開くのに失敗: {e}")
            QMessageBox.critical(self, "エラー", f"フォルダを開くのに失敗しました: {e}")
    
    def update_recent_folders_menu(self, menu: QMenu):
        """最近開いたフォルダメニューを更新"""
        menu.clear()
        
        recent_folders = self.config_manager.app_settings.recent_folders[:10]  # 最新10件
        
        if not recent_folders:
            no_folders_action = QAction("（なし）", self)
            no_folders_action.setEnabled(False)
            menu.addAction(no_folders_action)
            return
        
        for folder_path in recent_folders:
            if Path(folder_path).exists():
                # フォルダ名だけを表示（パスが長い場合は短縮）
                folder_name = Path(folder_path).name
                if len(folder_path) > 50:
                    display_text = f"{folder_name} (...{folder_path[-30:]})"
                else:
                    display_text = folder_path
                
                action = QAction(display_text, self)
                action.setToolTip(folder_path)
                action.triggered.connect(lambda checked, path=folder_path: self.open_folder(path))
                menu.addAction(action)
    
    def open_data_folder(self):
        """データフォルダを開く"""
        data_folder = self.config_manager.data_dir
        self.open_folder(str(data_folder))
    
    def open_log_folder(self):
        """ログフォルダを開く"""
        log_folder = self.config_manager.data_dir / "logs"
        self.open_folder(str(log_folder))
    
    def show_result_context_menu(self, position):
        """同期結果テーブルのコンテキストメニューを表示"""
        item = self.sync_result_table.itemAt(position)
        if not item:
            return
        
        row = item.row()
        file_path_item = self.sync_result_table.item(row, 0)
        if not file_path_item:
            return
        
        file_path = file_path_item.text()
        if not file_path:
            return
        
        menu = QMenu(self)
        
        # ファイルが存在する場合の操作
        full_path = None
        current_folder_pair = self.get_current_folder_pair()
        
        if current_folder_pair:
            # ソースファイルパスを構築
            source_path = Path(current_folder_pair.source_path) / file_path
            target_path = Path(current_folder_pair.target_path) / file_path
            
            if source_path.exists():
                open_source_action = QAction("ソースファイルを開く", self)
                open_source_action.triggered.connect(lambda: self.open_folder(str(source_path)))
                menu.addAction(open_source_action)
                
                open_source_folder_action = QAction("ソースフォルダを開く", self)
                open_source_folder_action.triggered.connect(lambda: self.open_folder(str(source_path.parent)))
                menu.addAction(open_source_folder_action)
                
                menu.addSeparator()
            
            if target_path.exists():
                open_target_action = QAction("ターゲットファイルを開く", self)
                open_target_action.triggered.connect(lambda: self.open_folder(str(target_path)))
                menu.addAction(open_target_action)
                
                open_target_folder_action = QAction("ターゲットフォルダを開く", self)
                open_target_folder_action.triggered.connect(lambda: self.open_folder(str(target_path.parent)))
                menu.addAction(open_target_folder_action)
            
            if menu.actions():
                menu.exec(self.sync_result_table.mapToGlobal(position))
    
    def get_current_folder_pair(self):
        """現在選択されているフォルダペアを取得"""
        selected_items = self.folder_tree.selectedItems()
        if selected_items:
            folder_pair_id = selected_items[0].data(0, Qt.UserRole)
            return self.project_manager.get_folder_pair(folder_pair_id)
        return None
    
    def on_folders_dropped(self, folder_paths: List[str]):
        """フォルダがドロップされた時の処理"""
        if not self.project_manager.current_project:
            QMessageBox.warning(self, "警告", "プロジェクトが選択されていません。\n先にプロジェクトを作成してください。")
            return
        
        if not folder_paths:
            return
        
        # 複数フォルダがドロップされた場合の処理
        if len(folder_paths) == 1:
            self.create_folder_pair_from_drop(folder_paths[0], None)
        elif len(folder_paths) == 2:
            # 2つのフォルダがドロップされた場合、ソースとターゲットとして設定
            result = QMessageBox.question(
                self, "フォルダペア作成",
                f"2つのフォルダがドロップされました：\n\n"
                f"1つ目: {folder_paths[0]}\n"
                f"2つ目: {folder_paths[1]}\n\n"
                f"1つ目をソース、2つ目をターゲットとして設定しますか？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes
            )
            
            if result == QMessageBox.Yes:
                self.create_folder_pair_from_drop(folder_paths[0], folder_paths[1])
            else:
                # 個別に処理
                for folder_path in folder_paths:
                    self.create_folder_pair_from_drop(folder_path, None)
        else:
            # 3つ以上の場合は個別に処理
            for folder_path in folder_paths:
                self.create_folder_pair_from_drop(folder_path, None)
    
    def create_folder_pair_from_drop(self, source_path: str, target_path: str = None):
        """ドロップされたフォルダからフォルダペアを作成"""
        dialog = SyncDialog(self)
        
        # ドロップされたパスを設定
        dialog.source_path_edit.setText(source_path)
        if target_path:
            dialog.target_path_edit.setText(target_path)
        
        # フォルダ名から適切なペア名を生成
        source_name = Path(source_path).name
        if target_path:
            target_name = Path(target_path).name
            suggested_name = f"{source_name} → {target_name}"
        else:
            suggested_name = f"{source_name} の同期"
        
        dialog.name_edit.setText(suggested_name)
        
        if dialog.exec() == SyncDialog.Accepted:
            folder_data = dialog.get_folder_data()
            folder_pair = self.project_manager.add_folder_pair(
                folder_data['name'],
                folder_data['source_path'],
                folder_data['target_path'],
                folder_data['include_patterns'],
                folder_data['exclude_patterns']
            )
            
            # マッピングルールを設定
            if folder_pair and 'mapping_rules' in folder_data and folder_data['mapping_rules']:
                folder_pair.file_mapping_rules = folder_data['mapping_rules']
                self.project_manager.save_current_project()
            
            # リネームルールを設定
            if folder_pair and 'rename_rules' in folder_data and folder_data['rename_rules']:
                folder_pair.file_rename_rules = folder_data['rename_rules']
                self.project_manager.save_current_project()
            
            if folder_pair:
                self.refresh_folder_pairs()
                self.add_log_message(f"ドロップからフォルダペアを作成: {folder_pair.name}")
    
    def show_about(self):
        """アプリについて表示"""
        QMessageBox.about(self, "YrYr Asset Syncについて", 
                          "YrYr Asset Sync v1.0.0\n\n"
                          "ゲーム開発用リソース同期ツール\n"
                          "リソース作成ソフトからゲーム用フォルダへの\n"
                          "効率的なアセット同期を支援します。")
    
    def closeEvent(self, event):
        """アプリケーション終了"""
        # ファイル監視停止
        if self.file_watcher.is_watching():
            self.file_watcher.stop_watching()
        
        # 同期処理停止
        if self.sync_thread and self.sync_thread.isRunning():
            self.sync_engine.cancel()
            self.sync_thread.wait(5000)  # 5秒待機
        
        # 設定保存
        self.save_settings()
        
        self.logger.info("アプリケーション終了")
        event.accept()