"""
ファイル同期エンジン
"""

import time
from pathlib import Path
from typing import List, Optional, Callable, Dict, Any
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass

from config.models import FolderPair, SyncResult, FilterRule, FileRenameRule
from utils.logger import get_logger
from utils.file_utils import (
    get_file_info, is_file_newer, copy_file_with_metadata,
    backup_file, match_patterns, scan_directory,
    format_file_size, ensure_directory
)


@dataclass
class SyncOptions:
    """同期オプション"""
    force_copy: bool = False  # 強制コピー（日付無視）
    create_backup: bool = True  # バックアップ作成
    preserve_timestamp: bool = True  # タイムスタンプ保持
    max_workers: int = 4  # 並行処理数
    dry_run: bool = False  # ドライラン（実際にコピーしない）


class SyncProgressCallback:
    """同期進捗コールバック"""
    
    def on_start(self, total_files: int):
        """同期開始時"""
        pass
    
    def on_file_progress(self, current: int, total: int, file_path: str, status: str):
        """ファイル処理進捗"""
        pass
    
    def on_complete(self, result: SyncResult):
        """同期完了時"""
        pass
    
    def on_error(self, error: str):
        """エラー発生時"""
        pass


class SyncEngine:
    """ファイル同期エンジン"""
    
    def __init__(self):
        self.logger = get_logger()
        self._cancelled = False
    
    def cancel(self):
        """同期をキャンセル"""
        self._cancelled = True
        self.logger.info("同期がキャンセルされました")
    
    def is_cancelled(self) -> bool:
        """キャンセル状態確認"""
        return self._cancelled
    
    def sync_folder_pair(
        self,
        folder_pair: FolderPair,
        options: SyncOptions = None,
        callback: SyncProgressCallback = None
    ) -> SyncResult:
        """
        フォルダペア同期を実行
        
        Args:
            folder_pair: フォルダペア設定
            options: 同期オプション
            callback: 進捗コールバック
        
        Returns:
            同期結果
        """
        if options is None:
            options = SyncOptions()
        
        if callback is None:
            callback = SyncProgressCallback()
        
        self._cancelled = False
        start_time = time.time()
        
        self.logger.info(f"フォルダペア同期開始: {folder_pair.name}")
        self.logger.info(f"ソース: {folder_pair.source_path}")
        self.logger.info(f"ターゲット: {folder_pair.target_path}")
        
        result = SyncResult(success=False)
        
        try:
            # パス検証
            source_path = Path(folder_pair.source_path)
            target_path = Path(folder_pair.target_path)
            
            if not source_path.exists():
                error_msg = f"ソースフォルダが存在しません: {source_path}"
                self.logger.error(error_msg)
                callback.on_error(error_msg)
                return result
            
            # ターゲットディレクトリ作成
            if not ensure_directory(target_path):
                error_msg = f"ターゲットディレクトリの作成に失敗: {target_path}"
                self.logger.error(error_msg)
                callback.on_error(error_msg)
                return result
            
            # 同期対象ファイル収集
            self.logger.info("同期対象ファイルをスキャンしています...")
            sync_files = list(self._collect_sync_files(source_path, folder_pair.filter_rule))
            
            if not sync_files:
                self.logger.warning("同期対象ファイルが見つかりませんでした")
                result.success = True
                result.duration_seconds = time.time() - start_time
                callback.on_complete(result)
                return result
            
            self.logger.info(f"同期対象ファイル数: {len(sync_files)}")
            callback.on_start(len(sync_files))
            
            # ファイル同期実行
            if options.max_workers > 1:
                result = self._sync_files_parallel(
                    sync_files, source_path, target_path, options, callback, folder_pair
                )
            else:
                result = self._sync_files_sequential(
                    sync_files, source_path, target_path, options, callback, folder_pair
                )
            
            result.duration_seconds = time.time() - start_time
            
            if not self._cancelled:
                self.logger.info(f"同期完了 - コピー: {len(result.copied_files)}, "
                               f"スキップ: {len(result.skipped_files)}, "
                               f"エラー: {len(result.error_files)}, "
                               f"時間: {result.duration_seconds:.2f}秒")
                callback.on_complete(result)
            
            return result
            
        except Exception as e:
            error_msg = f"同期エラー: {e}"
            self.logger.error(error_msg)
            callback.on_error(error_msg)
            result.duration_seconds = time.time() - start_time
            return result
    
    def _collect_sync_files(self, source_path: Path, filter_rule: FilterRule) -> List[Path]:
        """同期対象ファイルを収集"""
        if not filter_rule.enabled:
            # フィルタ無効の場合は全ファイル
            return list(scan_directory(source_path, [], []))
        
        return list(scan_directory(
            source_path,
            filter_rule.include_patterns,
            filter_rule.exclude_patterns
        ))
    
    def _sync_files_sequential(
        self,
        files: List[Path],
        source_base: Path,
        target_base: Path,
        options: SyncOptions,
        callback: SyncProgressCallback,
        folder_pair: FolderPair = None
    ) -> SyncResult:
        """ファイルを順次同期"""
        result = SyncResult(success=True)
        
        for i, source_file in enumerate(files):
            if self._cancelled:
                break
            
            try:
                # 相対パスを計算
                rel_path = source_file.relative_to(source_base)
                target_file = target_base / rel_path
                
                # リネームルールがある場合は適用
                if folder_pair and folder_pair.file_rename_rules:
                    target_file = self._apply_rename_rules(
                        source_file, target_file, folder_pair.file_rename_rules
                    )
                
                callback.on_file_progress(i + 1, len(files), str(rel_path), "処理中")
                
                sync_result = self._sync_single_file(source_file, target_file, options)
                
                if sync_result == "copied":
                    result.copied_files.append(str(rel_path))
                    result.total_size += source_file.stat().st_size
                    callback.on_file_progress(i + 1, len(files), str(rel_path), "コピー完了")
                elif sync_result == "skipped":
                    result.skipped_files.append(str(rel_path))
                    callback.on_file_progress(i + 1, len(files), str(rel_path), "スキップ")
                else:
                    result.error_files.append(str(rel_path))
                    callback.on_file_progress(i + 1, len(files), str(rel_path), "エラー")
                    
            except Exception as e:
                self.logger.error(f"ファイル同期エラー {source_file}: {e}")
                result.error_files.append(str(source_file))
        
        return result
    
    def _sync_files_parallel(
        self,
        files: List[Path],
        source_base: Path,
        target_base: Path,
        options: SyncOptions,
        callback: SyncProgressCallback,
        folder_pair: FolderPair = None
    ) -> SyncResult:
        """ファイルを並行同期"""
        result = SyncResult(success=True)
        completed_count = 0
        
        with ThreadPoolExecutor(max_workers=options.max_workers) as executor:
            # タスク提出
            future_to_file = {}
            for source_file in files:
                if self._cancelled:
                    break
                
                rel_path = source_file.relative_to(source_base)
                target_file = target_base / rel_path
                
                # リネームルールがある場合は適用
                if folder_pair and folder_pair.file_rename_rules:
                    target_file = self._apply_rename_rules(
                        source_file, target_file, folder_pair.file_rename_rules
                    )
                
                future = executor.submit(self._sync_single_file, source_file, target_file, options)
                future_to_file[future] = (source_file, rel_path)
            
            # 結果収集
            for future in as_completed(future_to_file.keys()):
                if self._cancelled:
                    break
                
                source_file, rel_path = future_to_file[future]
                completed_count += 1
                
                try:
                    sync_result = future.result()
                    
                    if sync_result == "copied":
                        result.copied_files.append(str(rel_path))
                        result.total_size += source_file.stat().st_size
                        callback.on_file_progress(completed_count, len(files), str(rel_path), "コピー完了")
                    elif sync_result == "skipped":
                        result.skipped_files.append(str(rel_path))
                        callback.on_file_progress(completed_count, len(files), str(rel_path), "スキップ")
                    else:
                        result.error_files.append(str(rel_path))
                        callback.on_file_progress(completed_count, len(files), str(rel_path), "エラー")
                        
                except Exception as e:
                    self.logger.error(f"並行同期エラー {source_file}: {e}")
                    result.error_files.append(str(rel_path))
                    callback.on_file_progress(completed_count, len(files), str(rel_path), "エラー")
        
        return result
    
    def _apply_rename_rules(
        self, 
        source_file: Path, 
        target_file: Path, 
        rename_rules: List[FileRenameRule]
    ) -> Path:
        """
        リネームルールを適用してターゲットファイルパスを更新
        
        Args:
            source_file: ソースファイルパス
            target_file: 元のターゲットファイルパス
            rename_rules: リネームルールリスト
        
        Returns:
            更新されたターゲットファイルパス
        """
        source_filename = source_file.name
        
        for rule in rename_rules:
            if not rule.enabled:
                continue
            
            # 完全一致でファイル名をチェック
            if source_filename == rule.source_filename:
                # ターゲットファイル名を変更
                new_target = target_file.parent / rule.target_filename
                self.logger.debug(f"リネームルール適用: {source_filename} -> {rule.target_filename}")
                return new_target
        
        # マッチするルールがない場合は元のパスを返す
        return target_file
    
    def _sync_single_file(self, source_file: Path, target_file: Path, options: SyncOptions) -> str:
        """
        単一ファイル同期
        
        Returns:
            "copied", "skipped", "error"
        """
        try:
            # ドライラン
            if options.dry_run:
                self.logger.debug(f"[DRY RUN] {source_file} -> {target_file}")
                return "copied"
            
            # コピー必要性チェック
            if not options.force_copy and target_file.exists():
                if not is_file_newer(source_file, target_file):
                    self.logger.debug(f"スキップ（更新不要）: {source_file}")
                    return "skipped"
            
            # バックアップ作成
            if options.create_backup and target_file.exists():
                backup_path = backup_file(target_file)
                if backup_path:
                    self.logger.debug(f"バックアップ作成: {backup_path}")
            
            # ファイルコピー
            if copy_file_with_metadata(source_file, target_file, options.preserve_timestamp):
                self.logger.debug(f"コピー完了: {source_file} -> {target_file}")
                return "copied"
            else:
                self.logger.error(f"コピー失敗: {source_file}")
                return "error"
                
        except Exception as e:
            self.logger.error(f"ファイル同期エラー {source_file}: {e}")
            return "error"
    
    def get_sync_preview(self, folder_pair: FolderPair) -> Dict[str, Any]:
        """
        同期プレビューを取得
        
        Args:
            folder_pair: フォルダペア設定
        
        Returns:
            プレビュー情報辞書
        """
        source_path = Path(folder_pair.source_path)
        target_path = Path(folder_pair.target_path)
        
        if not source_path.exists():
            return {"error": "ソースフォルダが存在しません"}
        
        try:
            # 同期対象ファイル収集
            sync_files = list(self._collect_sync_files(source_path, folder_pair.filter_rule))
            
            # 分析
            files_to_copy = []
            files_to_skip = []
            total_size = 0
            
            for source_file in sync_files:
                rel_path = source_file.relative_to(source_path)
                target_file = target_path / rel_path
                
                file_info = get_file_info(source_file)
                file_info['relative_path'] = str(rel_path)
                file_info['target_exists'] = target_file.exists()
                
                if target_file.exists() and not is_file_newer(source_file, target_file):
                    files_to_skip.append(file_info)
                else:
                    files_to_copy.append(file_info)
                    total_size += file_info['size']
            
            return {
                "files_to_copy": files_to_copy,
                "files_to_skip": files_to_skip,
                "copy_count": len(files_to_copy),
                "skip_count": len(files_to_skip),
                "total_size": total_size,
                "total_size_formatted": format_file_size(total_size)
            }
            
        except Exception as e:
            return {"error": f"プレビュー取得エラー: {e}"}
    
    def sync_multiple_folder_pairs(
        self,
        folder_pairs: List[FolderPair],
        options: SyncOptions = None,
        callback: SyncProgressCallback = None
    ) -> SyncResult:
        """
        複数フォルダペア同期を実行
        
        Args:
            folder_pairs: フォルダペア設定リスト
            options: 同期オプション
            callback: 進捗コールバック
        
        Returns:
            同期結果
        """
        if options is None:
            options = SyncOptions()
        
        if callback is None:
            callback = SyncProgressCallback()
        
        self._cancelled = False
        start_time = time.time()
        
        self.logger.info(f"複数フォルダペア同期開始: {len(folder_pairs)}個")
        
        result = SyncResult(success=False)
        total_files = 0
        processed_files = 0
        copied_files = 0
        skipped_files = 0
        error_files = 0
        
        try:
            # 全フォルダペアのファイル数を事前計算
            for folder_pair in folder_pairs:
                if not folder_pair.enabled:
                    continue
                
                source_path = Path(folder_pair.source_path)
                if source_path.exists():
                    sync_files = list(self._collect_sync_files(source_path, folder_pair.filter_rule))
                    total_files += len(sync_files)
            
            if total_files == 0:
                self.logger.warning("同期対象ファイルが見つかりませんでした")
                result.success = True
                result.duration_seconds = time.time() - start_time
                callback.on_complete(result)
                return result
            
            callback.on_start(total_files)
            
            # 各フォルダペアを順次処理
            for folder_pair in folder_pairs:
                if self._cancelled:
                    break
                
                if not folder_pair.enabled:
                    self.logger.info(f"スキップ（無効）: {folder_pair.name}")
                    continue
                
                self.logger.info(f"フォルダペア処理開始: {folder_pair.name}")
                
                # 単一フォルダペア同期
                single_result = self.sync_folder_pair(folder_pair, options, callback)
                
                if single_result.success:
                    copied_files += len(single_result.copied_files)
                    skipped_files += len(single_result.skipped_files)
                    error_files += len(single_result.error_files)
                else:
                    error_files += 1
                
                processed_files += len(single_result.copied_files) + len(single_result.skipped_files) + len(single_result.error_files)
            
            result.success = not self._cancelled and error_files == 0
            result.copied_files = [f"複数同期: {copied_files}ファイル"]
            result.skipped_files = [f"複数同期: {skipped_files}ファイル"]
            result.error_files = [f"複数同期: {error_files}ファイル"] if error_files > 0 else []
            result.duration_seconds = time.time() - start_time
            
            if not self._cancelled:
                self.logger.info(f"複数同期完了: コピー={copied_files}, スキップ={skipped_files}, エラー={error_files}")
                callback.on_complete(result)
            else:
                self.logger.info("複数同期がキャンセルされました")
            
            return result
            
        except Exception as e:
            error_msg = f"複数同期エラー: {e}"
            self.logger.error(error_msg)
            callback.on_error(error_msg)
            result.success = False
            result.duration_seconds = time.time() - start_time
            return result