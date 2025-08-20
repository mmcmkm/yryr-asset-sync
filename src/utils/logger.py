"""
ログシステム - ローテーション付き
"""

import logging
import logging.handlers
import os
from pathlib import Path
from typing import Optional


class ColoredFormatter(logging.Formatter):
    """カラー付きログフォーマッター（コンソール用）"""
    
    # ANSI色コード
    COLORS = {
        'DEBUG': '\033[36m',    # シアン
        'INFO': '\033[32m',     # 緑
        'WARNING': '\033[33m',  # 黄
        'ERROR': '\033[31m',    # 赤
        'CRITICAL': '\033[35m', # マゼンタ
        'RESET': '\033[0m'      # リセット
    }
    
    def format(self, record):
        # 色付きレベル名を作成
        level_name = record.levelname
        if level_name in self.COLORS:
            colored_level = f"{self.COLORS[level_name]}{level_name}{self.COLORS['RESET']}"
            record.levelname = colored_level
        
        return super().format(record)


def setup_logger(
    name: str = "yryr_asset_sync",
    log_dir: Optional[Path] = None,
    log_level: str = "INFO",
    max_size_mb: int = 10,
    max_files: int = 5,
    console_output: bool = True
) -> logging.Logger:
    """
    ログシステムをセットアップ
    
    Args:
        name: ロガー名
        log_dir: ログディレクトリ（None の場合は data/logs を使用）
        log_level: ログレベル
        max_size_mb: 1ファイルあたりの最大サイズ（MB）
        max_files: 保持するログファイル数
        console_output: コンソール出力有効
    
    Returns:
        設定済みロガー
    """
    
    # ログディレクトリの設定
    if log_dir is None:
        current_dir = Path(__file__).parent.parent.parent
        log_dir = current_dir / "data" / "logs"
    
    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # ロガー作成
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    
    # 既存のハンドラーをクリア
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # ファイルハンドラー（ローテーション付き）
    log_file = log_dir / "yryr_asset_sync.log"
    file_handler = logging.handlers.RotatingFileHandler(
        filename=log_file,
        maxBytes=max_size_mb * 1024 * 1024,  # MB to bytes
        backupCount=max_files - 1,
        encoding='utf-8'
    )
    
    # ファイル用フォーマッター
    file_formatter = logging.Formatter(
        fmt='%(asctime)s | %(levelname)-8s | %(name)s | %(funcName)s:%(lineno)d | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)
    
    # コンソールハンドラー
    if console_output:
        console_handler = logging.StreamHandler()
        console_formatter = ColoredFormatter(
            fmt='%(asctime)s | %(levelname)-8s | %(message)s',
            datefmt='%H:%M:%S'
        )
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)
    
    # 初期ログ出力
    logger.info(f"ログシステム初期化完了 - ログファイル: {log_file}")
    logger.info(f"ログ設定 - レベル: {log_level}, 最大サイズ: {max_size_mb}MB, 最大ファイル数: {max_files}")
    
    return logger


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """
    既存のロガーを取得
    
    Args:
        name: ロガー名（None の場合はデフォルトのロガーを使用）
    
    Returns:
        ロガー
    """
    if name is None:
        name = "yryr_asset_sync"
    return logging.getLogger(name)


class LogContext:
    """ログコンテキストマネージャー"""
    
    def __init__(self, logger: logging.Logger, operation: str):
        self.logger = logger
        self.operation = operation
        self.start_time = None
    
    def __enter__(self):
        import time
        self.start_time = time.time()
        self.logger.info(f"開始: {self.operation}")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        import time
        duration = time.time() - self.start_time
        
        if exc_type is None:
            self.logger.info(f"完了: {self.operation} ({duration:.2f}秒)")
        else:
            self.logger.error(f"エラー: {self.operation} - {exc_val} ({duration:.2f}秒)")
    
    def log_progress(self, message: str, level: str = "INFO"):
        """進捗ログを出力"""
        log_func = getattr(self.logger, level.lower(), self.logger.info)
        log_func(f"[{self.operation}] {message}")


# グローバルロガーインスタンス
_global_logger = None


def init_global_logger(**kwargs) -> logging.Logger:
    """グローバルロガーを初期化"""
    global _global_logger
    _global_logger = setup_logger(**kwargs)
    return _global_logger


def log_info(message: str):
    """情報ログを出力"""
    if _global_logger:
        _global_logger.info(message)


def log_warning(message: str):
    """警告ログを出力"""
    if _global_logger:
        _global_logger.warning(message)


def log_error(message: str):
    """エラーログを出力"""
    if _global_logger:
        _global_logger.error(message)


def log_debug(message: str):
    """デバッグログを出力"""
    if _global_logger:
        _global_logger.debug(message)