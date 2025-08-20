"""
ファイル監視機能
"""

import time
from pathlib import Path
from typing import Dict, List, Callable, Optional, Set
from threading import Thread, Lock
from datetime import datetime, timedelta

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler, FileModifiedEvent, FileCreatedEvent, FileDeletedEvent
    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False
    Observer = None
    FileSystemEventHandler = None
    FileModifiedEvent = None
    FileCreatedEvent = None
    FileDeletedEvent = None

from config.models import FolderPair
from utils.logger import get_logger
from utils.file_utils import match_patterns


class WatchEvent:
    """監視イベント"""
    
    def __init__(self, event_type: str, file_path: str, folder_pair_id: str):
        self.event_type = event_type  # 'created', 'modified', 'deleted'
        self.file_path = file_path
        self.folder_pair_id = folder_pair_id
        self.timestamp = datetime.now()


if WATCHDOG_AVAILABLE:
    class SyncEventHandler(FileSystemEventHandler):
        """同期用ファイルシステムイベントハンドラー"""
        
        def __init__(self, file_watcher: 'FileWatcher', folder_pair: FolderPair):
            super().__init__()
            self.file_watcher = file_watcher
            self.folder_pair = folder_pair
            self.logger = get_logger()
            
            # デバウンス用
            self._recent_events: Dict[str, datetime] = {}
            self._debounce_seconds = 2.0
            self._lock = Lock()
        
        def _should_process_file(self, file_path: str) -> bool:
            """ファイルを処理対象とするかチェック"""
            path = Path(file_path)
            
            # ディレクトリは無視
            if path.is_dir():
                return False
            
            # フィルタチェック
            if not match_patterns(
                path,
                self.folder_pair.filter_rule.include_patterns,
                self.folder_pair.filter_rule.exclude_patterns
            ):
                return False
            
            return True
        
        def _debounce_event(self, file_path: str) -> bool:
            """デバウンス処理（短時間の重複イベントを除去）"""
            with self._lock:
                now = datetime.now()
                
                # 最近の同じファイルのイベントをチェック
                if file_path in self._recent_events:
                    last_event = self._recent_events[file_path]
                    if (now - last_event).total_seconds() < self._debounce_seconds:
                        return False  # デバウンス期間内なのでスキップ
                
                self._recent_events[file_path] = now
                
                # 古いエントリを清理
                cutoff_time = now - timedelta(seconds=self._debounce_seconds * 2)
                keys_to_remove = [
                    key for key, timestamp in self._recent_events.items()
                    if timestamp < cutoff_time
                ]
                for key in keys_to_remove:
                    del self._recent_events[key]
                
                return True
        
        def on_created(self, event):
            """ファイル作成イベント"""
            if not self._should_process_file(event.src_path):
                return
            
            if not self._debounce_event(event.src_path):
                return
            
            self.logger.debug(f"ファイル作成検出: {event.src_path}")
            
            watch_event = WatchEvent('created', event.src_path, self.folder_pair.id)
            self.file_watcher._add_event(watch_event)
        
        def on_modified(self, event):
            """ファイル変更イベント"""
            if not self._should_process_file(event.src_path):
                return
            
            if not self._debounce_event(event.src_path):
                return
            
            self.logger.debug(f"ファイル変更検出: {event.src_path}")
            
            watch_event = WatchEvent('modified', event.src_path, self.folder_pair.id)
            self.file_watcher._add_event(watch_event)
        
        def on_deleted(self, event):
            """ファイル削除イベント"""
            if Path(event.src_path).is_dir():
                return
            
            self.logger.debug(f"ファイル削除検出: {event.src_path}")
            
            watch_event = WatchEvent('deleted', event.src_path, self.folder_pair.id)
            self.file_watcher._add_event(watch_event)
else:
    # watchdog が利用できない場合のダミークラス
    class SyncEventHandler:
        """同期用ファイルシステムイベントハンドラー（ダミー）"""
        def __init__(self, file_watcher, folder_pair):
            pass


class FileWatcher:
    """ファイル監視クラス"""
    
    def __init__(self):
        self.logger = get_logger()
        self._observers: Dict[str, Observer] = {}  # folder_pair_id -> Observer
        self._event_handlers: Dict[str, SyncEventHandler] = {}  # folder_pair_id -> Handler
        self._event_queue: List[WatchEvent] = []
        self._event_lock = Lock()
        self._callbacks: List[Callable[[WatchEvent], None]] = []
        self._is_running = False
        self._processor_thread: Optional[Thread] = None
        
        if not WATCHDOG_AVAILABLE:
            self.logger.warning("watchdogライブラリが利用できません。ファイル監視機能は無効です。")
    
    def is_available(self) -> bool:
        """ファイル監視機能が利用可能かチェック"""
        return WATCHDOG_AVAILABLE
    
    def add_callback(self, callback: Callable[[WatchEvent], None]):
        """イベントコールバックを追加"""
        self._callbacks.append(callback)
    
    def remove_callback(self, callback: Callable[[WatchEvent], None]):
        """イベントコールバックを削除"""
        if callback in self._callbacks:
            self._callbacks.remove(callback)
    
    def start_watching(self, folder_pairs: List[FolderPair]):
        """フォルダペア監視を開始"""
        if not WATCHDOG_AVAILABLE:
            self.logger.error("watchdogライブラリが利用できないため、監視を開始できません")
            return False
        
        self.logger.info(f"{len(folder_pairs)}個のフォルダペアの監視を開始します")
        
        try:
            # 既存の監視を停止
            self.stop_watching()
            
            # 各フォルダペアの監視を設定
            for folder_pair in folder_pairs:
                if not folder_pair.enabled or not folder_pair.auto_sync:
                    continue
                
                source_path = Path(folder_pair.source_path)
                if not source_path.exists() or not source_path.is_dir():
                    self.logger.warning(f"監視対象フォルダが存在しません: {source_path}")
                    continue
                
                # Observer作成
                observer = Observer()
                event_handler = SyncEventHandler(self, folder_pair)
                
                observer.schedule(event_handler, str(source_path), recursive=True)
                
                # 保存
                self._observers[folder_pair.id] = observer
                self._event_handlers[folder_pair.id] = event_handler
                
                self.logger.info(f"監視設定: {folder_pair.name} - {source_path}")
            
            # Observerを開始
            for observer in self._observers.values():
                observer.start()
            
            # イベント処理スレッドを開始
            self._is_running = True
            self._processor_thread = Thread(target=self._process_events, daemon=True)
            self._processor_thread.start()
            
            self.logger.info("ファイル監視を開始しました")
            return True
            
        except Exception as e:
            self.logger.error(f"監視開始エラー: {e}")
            return False
    
    def stop_watching(self):
        """監視を停止"""
        self.logger.info("ファイル監視を停止します")
        
        # イベント処理を停止
        self._is_running = False
        
        # Observerを停止
        for folder_pair_id, observer in self._observers.items():
            try:
                observer.stop()
                observer.join(timeout=5.0)
            except Exception as e:
                self.logger.error(f"Observer停止エラー [{folder_pair_id}]: {e}")
        
        # リソースクリア
        self._observers.clear()
        self._event_handlers.clear()
        
        # イベントキューをクリア
        with self._event_lock:
            self._event_queue.clear()
        
        # プロセッサスレッド終了を待機
        if self._processor_thread and self._processor_thread.is_alive():
            self._processor_thread.join(timeout=5.0)
        
        self.logger.info("ファイル監視を停止しました")
    
    def is_watching(self) -> bool:
        """監視中かチェック"""
        return self._is_running and len(self._observers) > 0
    
    def get_watched_folders(self) -> List[str]:
        """監視中のフォルダ一覧を取得"""
        return list(self._observers.keys())
    
    def _add_event(self, event: WatchEvent):
        """イベントをキューに追加"""
        with self._event_lock:
            self._event_queue.append(event)
    
    def _process_events(self):
        """イベント処理ループ"""
        self.logger.info("イベント処理スレッド開始")
        
        while self._is_running:
            try:
                # イベントを取得
                events_to_process = []
                with self._event_lock:
                    if self._event_queue:
                        events_to_process = self._event_queue.copy()
                        self._event_queue.clear()
                
                # イベントを処理
                for event in events_to_process:
                    for callback in self._callbacks:
                        try:
                            callback(event)
                        except Exception as e:
                            self.logger.error(f"イベントコールバックエラー: {e}")
                
                # 少し待機
                time.sleep(0.5)
                
            except Exception as e:
                self.logger.error(f"イベント処理エラー: {e}")
                time.sleep(1.0)
        
        self.logger.info("イベント処理スレッド終了")
    
    def get_event_statistics(self) -> Dict[str, int]:
        """イベント統計を取得"""
        stats = {
            'watchers_count': len(self._observers),
            'queue_size': len(self._event_queue),
            'callbacks_count': len(self._callbacks)
        }
        return stats