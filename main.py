#!/usr/bin/env python3
"""
YrYr Asset Sync - メインアプリケーション
ゲーム開発用リソース同期ツール
"""

import sys
import os
from pathlib import Path

# src ディレクトリをパスに追加
current_dir = Path(__file__).parent
src_dir = current_dir / "src"
sys.path.insert(0, str(src_dir))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTranslator, QLocale
from ui.main_window import MainWindow
from utils.logger import setup_logger

def main():
    """メインアプリケーション"""
    app = QApplication(sys.argv)
    
    # 日本語ロケール設定
    translator = QTranslator()
    locale = QLocale.system()
    app.installTranslator(translator)
    
    # ログシステム初期化
    logger = setup_logger()
    logger.info("YrYr Asset Sync アプリケーション開始")
    
    # メインウィンドウ作成・表示
    main_window = MainWindow()
    main_window.show()
    
    try:
        sys.exit(app.exec())
    except Exception as e:
        logger.error(f"アプリケーション実行エラー: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()