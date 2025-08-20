"""
データモデル定義
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional
from datetime import datetime
import json


@dataclass
class FilterRule:
    """フィルタ設定"""
    include_patterns: List[str] = field(default_factory=list)  # 包含パターン
    exclude_patterns: List[str] = field(default_factory=list)  # 除外パターン
    enabled: bool = True


@dataclass
class FileMappingRule:
    """ファイル個別マッピングルール"""
    id: str
    pattern: str  # ファイルパターン（*.png, button_*, など）
    target_subpath: str  # ターゲット内のサブパス（ui/buttons, icons, など）
    description: str = ""  # 説明
    enabled: bool = True


@dataclass
class FolderPair:
    """フォルダペア設定"""
    id: str
    name: str  # 表示名
    source_path: str  # ソースフォルダパス
    target_path: str  # ターゲットフォルダパス
    filter_rule: FilterRule = field(default_factory=FilterRule)
    file_mapping_rules: List[FileMappingRule] = field(default_factory=list)  # ファイルマッピングルール
    auto_sync: bool = False  # 自動同期有効
    backup_enabled: bool = True  # バックアップ有効
    last_sync: Optional[str] = None  # 最後の同期日時
    enabled: bool = True


@dataclass
class ProjectSettings:
    """プロジェクト設定"""
    id: str
    name: str  # プロジェクト名
    description: str = ""  # 説明
    folder_pairs: List[FolderPair] = field(default_factory=list)
    global_filter: FilterRule = field(default_factory=FilterRule)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class AppSettings:
    """アプリケーション全体設定"""
    version: str = "1.0.0"
    current_project_id: Optional[str] = None
    recent_projects: List[str] = field(default_factory=list)  # 最近使用したプロジェクトID
    recent_folders: List[str] = field(default_factory=list)  # 最近開いたフォルダ
    window_geometry: Dict[str, int] = field(default_factory=dict)  # ウィンドウサイズ・位置
    log_level: str = "INFO"
    max_log_files: int = 5
    max_log_size_mb: int = 10
    language: str = "ja"


@dataclass
class SyncResult:
    """同期結果"""
    success: bool
    copied_files: List[str] = field(default_factory=list)
    skipped_files: List[str] = field(default_factory=list)
    error_files: List[str] = field(default_factory=list)
    total_size: int = 0
    duration_seconds: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


def to_dict(obj) -> Dict:
    """dataclassをdictに変換"""
    if hasattr(obj, '__dataclass_fields__'):
        result = {}
        for field_name, field_def in obj.__dataclass_fields__.items():
            value = getattr(obj, field_name)
            if hasattr(value, '__dataclass_fields__'):
                result[field_name] = to_dict(value)
            elif isinstance(value, list):
                result[field_name] = [to_dict(item) if hasattr(item, '__dataclass_fields__') else item for item in value]
            else:
                result[field_name] = value
        return result
    return obj


def from_dict(data_class, data: Dict):
    """dictからdataclassを作成"""
    if not isinstance(data, dict):
        return data
    
    field_types = {f.name: f.type for f in data_class.__dataclass_fields__.values()}
    kwargs = {}
    
    for key, value in data.items():
        if key in field_types:
            field_type = field_types[key]
            if hasattr(field_type, '__dataclass_fields__'):
                kwargs[key] = from_dict(field_type, value)
            elif hasattr(field_type, '__origin__') and field_type.__origin__ is list:
                item_type = field_type.__args__[0]
                if hasattr(item_type, '__dataclass_fields__'):
                    kwargs[key] = [from_dict(item_type, item) for item in value]
                else:
                    kwargs[key] = value
            else:
                kwargs[key] = value
    
    return data_class(**kwargs)