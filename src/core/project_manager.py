"""
プロジェクト管理機能
"""

import json
import uuid
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime

from config.models import ProjectSettings, FolderPair, FilterRule, SyncResult, FileMappingRule
from config.config_manager import ConfigManager
from utils.logger import get_logger


class ProjectManager:
    """プロジェクト管理クラス"""
    
    def __init__(self, config_manager: ConfigManager = None):
        """初期化"""
        self.logger = get_logger()
        self.config_manager = config_manager or ConfigManager()
        self._current_project = None
    
    @property
    def current_project(self) -> Optional[ProjectSettings]:
        """現在のプロジェクト"""
        return self._current_project
    
    def create_new_project(self, name: str, description: str = "") -> ProjectSettings:
        """
        新しいプロジェクトを作成
        
        Args:
            name: プロジェクト名
            description: 説明
        
        Returns:
            作成されたプロジェクト
        """
        self.logger.info(f"新しいプロジェクト作成: {name}")
        
        project = self.config_manager.create_project(name, description)
        self.config_manager.add_recent_project(project.id)
        
        self.logger.info(f"プロジェクト作成完了: {project.id}")
        return project
    
    def load_project(self, project_id: str) -> bool:
        """
        プロジェクトを読み込み
        
        Args:
            project_id: プロジェクトID
        
        Returns:
            成功した場合 True
        """
        self.logger.info(f"プロジェクト読み込み: {project_id}")
        
        project = self.config_manager.load_project(project_id)
        if not project:
            self.logger.error(f"プロジェクト読み込み失敗: {project_id}")
            return False
        
        self._current_project = project
        self.config_manager.app_settings.current_project_id = project_id
        self.config_manager.add_recent_project(project_id)
        self.config_manager.save_app_settings()
        
        self.logger.info(f"プロジェクト読み込み完了: {project.name}")
        return True
    
    def save_current_project(self) -> bool:
        """
        現在のプロジェクトを保存
        
        Returns:
            成功した場合 True
        """
        if not self._current_project:
            self.logger.warning("保存するプロジェクトがありません")
            return False
        
        try:
            self.config_manager.save_project(self._current_project)
            self.logger.info(f"プロジェクト保存完了: {self._current_project.name}")
            return True
        except Exception as e:
            self.logger.error(f"プロジェクト保存エラー: {e}")
            return False
    
    def delete_project(self, project_id: str) -> bool:
        """
        プロジェクトを削除
        
        Args:
            project_id: プロジェクトID
        
        Returns:
            成功した場合 True
        """
        self.logger.info(f"プロジェクト削除: {project_id}")
        
        success = self.config_manager.delete_project(project_id)
        
        # 現在のプロジェクトが削除された場合はクリア
        if success and self._current_project and self._current_project.id == project_id:
            self._current_project = None
            self.config_manager.app_settings.current_project_id = None
            self.config_manager.save_app_settings()
        
        if success:
            self.logger.info(f"プロジェクト削除完了: {project_id}")
        else:
            self.logger.error(f"プロジェクト削除失敗: {project_id}")
        
        return success
    
    def list_all_projects(self) -> List[Dict[str, str]]:
        """
        全プロジェクト一覧を取得
        
        Returns:
            プロジェクト情報のリスト
        """
        return self.config_manager.list_projects()
    
    def get_recent_projects(self, limit: int = 5) -> List[Dict[str, str]]:
        """
        最近使用したプロジェクト一覧を取得
        
        Args:
            limit: 取得件数上限
        
        Returns:
            プロジェクト情報のリスト
        """
        recent_ids = self.config_manager.app_settings.recent_projects[:limit]
        recent_projects = []
        
        for project_id in recent_ids:
            project = self.config_manager.load_project(project_id)
            if project:
                recent_projects.append({
                    'id': project.id,
                    'name': project.name,
                    'description': project.description,
                    'created_at': project.created_at,
                    'updated_at': project.updated_at
                })
        
        return recent_projects
    
    def add_folder_pair(
        self,
        name: str,
        source_path: str,
        target_path: str,
        include_patterns: List[str] = None,
        exclude_patterns: List[str] = None
    ) -> Optional[FolderPair]:
        """
        フォルダペアを追加
        
        Args:
            name: 表示名
            source_path: ソースフォルダパス
            target_path: ターゲットフォルダパス
            include_patterns: 含むパターン
            exclude_patterns: 除外パターン
        
        Returns:
            作成されたフォルダペア
        """
        if not self._current_project:
            self.logger.warning("プロジェクトが選択されていません")
            return None
        
        self.logger.info(f"フォルダペア追加: {name}")
        
        # フィルタルール作成
        filter_rule = FilterRule(
            include_patterns=include_patterns or [],
            exclude_patterns=exclude_patterns or []
        )
        
        # フォルダペア作成
        folder_pair = FolderPair(
            id=str(uuid.uuid4()),
            name=name,
            source_path=source_path,
            target_path=target_path,
            filter_rule=filter_rule
        )
        
        self._current_project.folder_pairs.append(folder_pair)
        self.save_current_project()
        
        # 最近使用したフォルダに追加
        self.config_manager.add_recent_folder(source_path)
        self.config_manager.add_recent_folder(target_path)
        
        self.logger.info(f"フォルダペア追加完了: {folder_pair.id}")
        return folder_pair
    
    def remove_folder_pair(self, folder_pair_id: str) -> bool:
        """
        フォルダペアを削除
        
        Args:
            folder_pair_id: フォルダペアID
        
        Returns:
            成功した場合 True
        """
        if not self._current_project:
            self.logger.warning("プロジェクトが選択されていません")
            return False
        
        self.logger.info(f"フォルダペア削除: {folder_pair_id}")
        
        # 該当フォルダペアを検索・削除
        for i, folder_pair in enumerate(self._current_project.folder_pairs):
            if folder_pair.id == folder_pair_id:
                del self._current_project.folder_pairs[i]
                self.save_current_project()
                self.logger.info(f"フォルダペア削除完了: {folder_pair_id}")
                return True
        
        self.logger.warning(f"フォルダペアが見つかりません: {folder_pair_id}")
        return False
    
    def update_folder_pair(self, folder_pair_id: str, **kwargs) -> bool:
        """
        フォルダペアを更新
        
        Args:
            folder_pair_id: フォルダペアID
            **kwargs: 更新する属性
        
        Returns:
            成功した場合 True
        """
        if not self._current_project:
            self.logger.warning("プロジェクトが選択されていません")
            return False
        
        # 該当フォルダペアを検索・更新
        for folder_pair in self._current_project.folder_pairs:
            if folder_pair.id == folder_pair_id:
                for key, value in kwargs.items():
                    if hasattr(folder_pair, key):
                        setattr(folder_pair, key, value)
                
                self.save_current_project()
                self.logger.info(f"フォルダペア更新完了: {folder_pair_id}")
                return True
        
        self.logger.warning(f"フォルダペアが見つかりません: {folder_pair_id}")
        return False
    
    def get_folder_pair(self, folder_pair_id: str) -> Optional[FolderPair]:
        """
        フォルダペアを取得
        
        Args:
            folder_pair_id: フォルダペアID
        
        Returns:
            フォルダペア（見つからない場合は None）
        """
        if not self._current_project:
            return None
        
        for folder_pair in self._current_project.folder_pairs:
            if folder_pair.id == folder_pair_id:
                return folder_pair
        
        return None
    
    def get_all_folder_pairs(self) -> List[FolderPair]:
        """
        全フォルダペアを取得
        
        Returns:
            フォルダペアのリスト
        """
        if not self._current_project:
            return []
        
        return self._current_project.folder_pairs.copy()
    
    def update_sync_timestamp(self, folder_pair_id: str, timestamp: str = None) -> bool:
        """
        フォルダペアの最終同期日時を更新
        
        Args:
            folder_pair_id: フォルダペアID
            timestamp: タイムスタンプ（None の場合は現在時刻）
        
        Returns:
            成功した場合 True
        """
        if timestamp is None:
            timestamp = datetime.now().isoformat()
        
        return self.update_folder_pair(folder_pair_id, last_sync=timestamp)
    
    def export_project(self, project_id: str, export_path: str) -> bool:
        """
        プロジェクトをエクスポート
        
        Args:
            project_id: プロジェクトID
            export_path: エクスポート先パス
        
        Returns:
            成功した場合 True
        """
        try:
            project = self.config_manager.load_project(project_id)
            if not project:
                return False
            
            export_data = {
                'project': project,
                'export_version': '1.0',
                'exported_at': datetime.now().isoformat()
            }
            
            with open(export_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, ensure_ascii=False, indent=2, default=str)
            
            self.logger.info(f"プロジェクトエクスポート完了: {export_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"プロジェクトエクスポートエラー: {e}")
            return False
    
    def import_project(self, import_path: str) -> Optional[ProjectSettings]:
        """
        プロジェクトをインポート
        
        Args:
            import_path: インポート元パス
        
        Returns:
            インポートされたプロジェクト
        """
        try:
            with open(import_path, 'r', encoding='utf-8') as f:
                export_data = json.load(f)
            
            # 新しいIDを生成
            project_data = export_data['project']
            project_data['id'] = str(uuid.uuid4())
            project_data['created_at'] = datetime.now().isoformat()
            project_data['updated_at'] = datetime.now().isoformat()
            
            # フォルダペアのIDも再生成
            for folder_pair in project_data.get('folder_pairs', []):
                folder_pair['id'] = str(uuid.uuid4())
            
            # プロジェクト保存
            from config.models import from_dict
            project = from_dict(ProjectSettings, project_data)
            self.config_manager.save_project(project)
            
            self.logger.info(f"プロジェクトインポート完了: {project.name}")
            return project
            
        except Exception as e:
            self.logger.error(f"プロジェクトインポートエラー: {e}")
            return None