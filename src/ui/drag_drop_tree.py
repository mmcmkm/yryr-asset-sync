"""
ドラッグ&ドロップ対応ツリーウィジェット
"""

from pathlib import Path
from typing import List, Callable

from PySide6.QtWidgets import QTreeWidget, QMessageBox
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDragEnterEvent, QDragMoveEvent, QDropEvent


class DragDropTreeWidget(QTreeWidget):
    """ドラッグ&ドロップ対応ツリーウィジェット"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # コールバック関数
        self.drop_callback: Callable[[List[str]], None] = None
        
        # ドラッグ&ドロップ設定
        self.setAcceptDrops(True)
        self.setDragDropMode(QTreeWidget.DropOnly)
    
    def set_drop_callback(self, callback: Callable[[List[str]], None]):
        """ドロップ時のコールバック関数を設定"""
        self.drop_callback = callback
    
    def dragEnterEvent(self, event: QDragEnterEvent):
        """ドラッグ開始イベント"""
        if event.mimeData().hasUrls():
            # URLを含む場合（ファイル・フォルダのドラッグ）
            event.acceptProposedAction()
        else:
            event.ignore()
    
    def dragMoveEvent(self, event: QDragMoveEvent):
        """ドラッグ中イベント"""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()
    
    def dropEvent(self, event: QDropEvent):
        """ドロップイベント"""
        if not event.mimeData().hasUrls():
            event.ignore()
            return
        
        # ドロップされたURLを取得
        urls = event.mimeData().urls()
        folder_paths = []
        
        for url in urls:
            if url.isLocalFile():
                file_path = Path(url.toLocalFile())
                if file_path.exists():
                    if file_path.is_dir():
                        # フォルダの場合
                        folder_paths.append(str(file_path))
                    else:
                        # ファイルの場合は親フォルダを追加
                        parent_folder = file_path.parent
                        if str(parent_folder) not in folder_paths:
                            folder_paths.append(str(parent_folder))
        
        if folder_paths and self.drop_callback:
            self.drop_callback(folder_paths)
        
        event.acceptProposedAction()
    
    def get_valid_folders(self, paths: List[str]) -> List[str]:
        """有効なフォルダパスのみを抽出"""
        valid_folders = []
        
        for path_str in paths:
            try:
                path = Path(path_str).resolve()
                if path.exists() and path.is_dir():
                    valid_folders.append(str(path))
            except Exception:
                continue
        
        return valid_folders