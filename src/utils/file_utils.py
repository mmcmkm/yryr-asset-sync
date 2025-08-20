"""
ファイルユーティリティ
"""

import os
import shutil
import fnmatch
import re
from pathlib import Path
from typing import List, Optional, Tuple, Generator
from datetime import datetime


def get_file_info(file_path: Path) -> dict:
    """
    ファイル情報を取得
    
    Args:
        file_path: ファイルパス
    
    Returns:
        ファイル情報辞書
    """
    if not file_path.exists():
        return {}
    
    stat = file_path.stat()
    return {
        'path': str(file_path),
        'name': file_path.name,
        'size': stat.st_size,
        'modified': datetime.fromtimestamp(stat.st_mtime),
        'created': datetime.fromtimestamp(stat.st_ctime),
        'is_file': file_path.is_file(),
        'is_dir': file_path.is_dir(),
        'extension': file_path.suffix.lower()
    }


def format_file_size(size_bytes: int) -> str:
    """
    ファイルサイズを人間が読みやすい形式に変換
    
    Args:
        size_bytes: サイズ（バイト）
    
    Returns:
        フォーマット済みサイズ文字列
    """
    if size_bytes == 0:
        return "0 B"
    
    size_units = ['B', 'KB', 'MB', 'GB', 'TB']
    i = 0
    while size_bytes >= 1024.0 and i < len(size_units) - 1:
        size_bytes /= 1024.0
        i += 1
    
    return f"{size_bytes:.1f} {size_units[i]}"


def is_file_newer(source_path: Path, target_path: Path) -> bool:
    """
    ソースファイルがターゲットファイルより新しいかチェック
    
    Args:
        source_path: ソースファイルパス
        target_path: ターゲットファイルパス
    
    Returns:
        True if ソースが新しい or ターゲットが存在しない
    """
    if not source_path.exists():
        return False
    
    if not target_path.exists():
        return True
    
    source_mtime = source_path.stat().st_mtime
    target_mtime = target_path.stat().st_mtime
    
    return source_mtime > target_mtime


def copy_file_with_metadata(source_path: Path, target_path: Path, preserve_timestamp: bool = True) -> bool:
    """
    ファイルをメタデータ付きでコピー
    
    Args:
        source_path: ソースファイルパス
        target_path: ターゲットファイルパス
        preserve_timestamp: タイムスタンプ保持
    
    Returns:
        成功した場合 True
    """
    try:
        # ターゲットディレクトリを作成
        target_path.parent.mkdir(parents=True, exist_ok=True)
        
        # ファイルコピー
        shutil.copy2(source_path, target_path)
        
        # タイムスタンプ保持
        if preserve_timestamp:
            stat = source_path.stat()
            os.utime(target_path, (stat.st_atime, stat.st_mtime))
        
        return True
    except Exception:
        return False


def backup_file(file_path: Path, backup_dir: Optional[Path] = None) -> Optional[Path]:
    """
    ファイルをバックアップ
    
    Args:
        file_path: バックアップするファイルパス
        backup_dir: バックアップディレクトリ
    
    Returns:
        バックアップファイルパス（失敗時は None）
    """
    if not file_path.exists():
        return None
    
    try:
        if backup_dir is None:
            backup_dir = file_path.parent / "backup"
        
        backup_dir.mkdir(parents=True, exist_ok=True)
        
        # タイムスタンプ付きバックアップファイル名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"{file_path.stem}_{timestamp}{file_path.suffix}"
        backup_path = backup_dir / backup_name
        
        shutil.copy2(file_path, backup_path)
        return backup_path
    except Exception:
        return None


def match_patterns(file_path: Path, include_patterns: List[str], exclude_patterns: List[str]) -> bool:
    """
    ファイルがパターンにマッチするかチェック
    
    Args:
        file_path: ファイルパス
        include_patterns: 含むパターンリスト
        exclude_patterns: 除外パターンリスト
    
    Returns:
        True if マッチ（コピー対象）
    """
    file_name = file_path.name
    file_path_str = str(file_path)
    
    # 除外パターンチェック（優先）
    for pattern in exclude_patterns:
        if pattern.startswith('regex:'):
            # 正規表現パターン
            regex_pattern = pattern[6:]  # "regex:" を除去
            if re.search(regex_pattern, file_name, re.IGNORECASE):
                return False
        else:
            # Globパターン
            if fnmatch.fnmatch(file_name, pattern):
                return False
    
    # 含むパターンが指定されていない場合は全て含む
    if not include_patterns:
        return True
    
    # 含むパターンチェック
    for pattern in include_patterns:
        if pattern.startswith('regex:'):
            # 正規表現パターン
            regex_pattern = pattern[6:]  # "regex:" を除去
            if re.search(regex_pattern, file_name, re.IGNORECASE):
                return True
        else:
            # Globパターン
            if fnmatch.fnmatch(file_name, pattern):
                return True
    
    return False


def scan_directory(
    directory: Path,
    include_patterns: List[str] = None,
    exclude_patterns: List[str] = None,
    recursive: bool = True
) -> Generator[Path, None, None]:
    """
    ディレクトリをスキャンしてマッチするファイルを列挙
    
    Args:
        directory: スキャンするディレクトリ
        include_patterns: 含むパターンリスト
        exclude_patterns: 除外パターンリスト
        recursive: 再帰的スキャン
    
    Yields:
        マッチするファイルパス
    """
    if not directory.exists() or not directory.is_dir():
        return
    
    if include_patterns is None:
        include_patterns = []
    if exclude_patterns is None:
        exclude_patterns = []
    
    try:
        if recursive:
            for file_path in directory.rglob("*"):
                if file_path.is_file():
                    if match_patterns(file_path, include_patterns, exclude_patterns):
                        yield file_path
        else:
            for file_path in directory.iterdir():
                if file_path.is_file():
                    if match_patterns(file_path, include_patterns, exclude_patterns):
                        yield file_path
    except PermissionError:
        pass  # アクセス権限のないディレクトリはスキップ


def calculate_directory_size(directory: Path) -> Tuple[int, int]:
    """
    ディレクトリの合計サイズとファイル数を計算
    
    Args:
        directory: ディレクトリパス
    
    Returns:
        (合計サイズ, ファイル数)
    """
    total_size = 0
    file_count = 0
    
    try:
        for file_path in directory.rglob("*"):
            if file_path.is_file():
                total_size += file_path.stat().st_size
                file_count += 1
    except PermissionError:
        pass  # アクセス権限のないファイルはスキップ
    
    return total_size, file_count


def ensure_directory(directory: Path) -> bool:
    """
    ディレクトリの存在を確認し、必要に応じて作成
    
    Args:
        directory: ディレクトリパス
    
    Returns:
        成功した場合 True
    """
    try:
        directory.mkdir(parents=True, exist_ok=True)
        return True
    except Exception:
        return False


def safe_delete_file(file_path: Path) -> bool:
    """
    ファイルを安全に削除
    
    Args:
        file_path: 削除するファイルパス
    
    Returns:
        成功した場合 True
    """
    try:
        if file_path.exists():
            file_path.unlink()
        return True
    except Exception:
        return False