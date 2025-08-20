"""
設定管理クラス
"""

import json
import os
import uuid
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

from config.models import AppSettings, ProjectSettings, FolderPair, FilterRule, to_dict, from_dict


class ConfigManager:
    """設定管理クラス"""
    
    def __init__(self, data_dir: Optional[Path] = None):
        """初期化"""
        if data_dir is None:
            # 実行ファイルと同じディレクトリのdataフォルダを使用
            current_dir = Path(__file__).parent.parent.parent
            data_dir = current_dir / "data"
        
        self.data_dir = Path(data_dir)
        self.projects_dir = self.data_dir / "projects"
        self.config_file = self.data_dir / "config.json"
        
        # ディレクトリ作成
        self.data_dir.mkdir(exist_ok=True)
        self.projects_dir.mkdir(exist_ok=True)
        
        # 設定ロード
        self.app_settings = self._load_app_settings()
    
    def _load_app_settings(self) -> AppSettings:
        """アプリケーション設定をロード"""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                return from_dict(AppSettings, data)
            except Exception as e:
                print(f"設定ファイル読み込みエラー: {e}")
        
        return AppSettings()
    
    def save_app_settings(self):
        """アプリケーション設定を保存"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(to_dict(self.app_settings), f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"設定ファイル保存エラー: {e}")
    
    def create_project(self, name: str, description: str = "") -> ProjectSettings:
        """新しいプロジェクトを作成"""
        project_id = str(uuid.uuid4())
        project = ProjectSettings(
            id=project_id,
            name=name,
            description=description
        )
        self.save_project(project)
        return project
    
    def load_project(self, project_id: str) -> Optional[ProjectSettings]:
        """プロジェクトをロード"""
        project_file = self.projects_dir / f"{project_id}.json"
        if not project_file.exists():
            return None
        
        try:
            with open(project_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return from_dict(ProjectSettings, data)
        except Exception as e:
            print(f"プロジェクトファイル読み込みエラー: {e}")
            return None
    
    def save_project(self, project: ProjectSettings):
        """プロジェクトを保存"""
        project.updated_at = datetime.now().isoformat()
        project_file = self.projects_dir / f"{project.id}.json"
        
        try:
            with open(project_file, 'w', encoding='utf-8') as f:
                json.dump(to_dict(project), f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"プロジェクトファイル保存エラー: {e}")
    
    def delete_project(self, project_id: str) -> bool:
        """プロジェクトを削除"""
        project_file = self.projects_dir / f"{project_id}.json"
        try:
            if project_file.exists():
                project_file.unlink()
                # 最近使用したプロジェクトからも削除
                if project_id in self.app_settings.recent_projects:
                    self.app_settings.recent_projects.remove(project_id)
                    self.save_app_settings()
                return True
        except Exception as e:
            print(f"プロジェクト削除エラー: {e}")
        return False
    
    def list_projects(self) -> List[Dict[str, str]]:
        """プロジェクト一覧を取得"""
        projects = []
        for project_file in self.projects_dir.glob("*.json"):
            try:
                with open(project_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                projects.append({
                    'id': data.get('id', ''),
                    'name': data.get('name', ''),
                    'description': data.get('description', ''),
                    'created_at': data.get('created_at', ''),
                    'updated_at': data.get('updated_at', '')
                })
            except Exception as e:
                print(f"プロジェクト情報読み込みエラー: {e}")
        
        # 更新日時でソート
        projects.sort(key=lambda x: x.get('updated_at', ''), reverse=True)
        return projects
    
    def add_recent_project(self, project_id: str):
        """最近使用したプロジェクトに追加"""
        if project_id in self.app_settings.recent_projects:
            self.app_settings.recent_projects.remove(project_id)
        
        self.app_settings.recent_projects.insert(0, project_id)
        
        # 最大10件まで保持
        if len(self.app_settings.recent_projects) > 10:
            self.app_settings.recent_projects = self.app_settings.recent_projects[:10]
        
        self.save_app_settings()
    
    def add_recent_folder(self, folder_path: str):
        """最近開いたフォルダに追加"""
        if folder_path in self.app_settings.recent_folders:
            self.app_settings.recent_folders.remove(folder_path)
        
        self.app_settings.recent_folders.insert(0, folder_path)
        
        # 最大20件まで保持
        if len(self.app_settings.recent_folders) > 20:
            self.app_settings.recent_folders = self.app_settings.recent_folders[:20]
        
        self.save_app_settings()
    
    def create_folder_pair(self, project_id: str, name: str, source_path: str, target_path: str) -> Optional[FolderPair]:
        """フォルダペアを作成"""
        project = self.load_project(project_id)
        if not project:
            return None
        
        folder_pair = FolderPair(
            id=str(uuid.uuid4()),
            name=name,
            source_path=source_path,
            target_path=target_path
        )
        
        project.folder_pairs.append(folder_pair)
        self.save_project(project)
        return folder_pair