"""
Local, dependency-free stand-ins for the Supabase database and storage
services, used when LOCAL_MODE=true.

They implement the same method surface the rest of the app already calls, so
nothing downstream needs to know which backend it is talking to:

  LocalDatabaseManager  <- DatabaseManager   (services/database.py)
  LocalStorageService   <- StorageService    (services/storage.py)

Project state is held in memory and is lost on restart. Game files are written
under local_storage_dir and served back by the /api/v1/generate/preview route.
"""

import asyncio
import logging
import mimetypes
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class LocalDatabaseManager:
    """In-memory replacement for DatabaseManager."""

    def __init__(self):
        self.projects: Dict[str, Dict] = {}
        self.builds: Dict[str, List[Dict]] = {}
        self.logs: Dict[str, List[Dict]] = {}
        self._lock = asyncio.Lock()

    async def connect(self):
        logger.info("🗃️  Local database ready (in memory, not persisted)")

    async def disconnect(self):
        self.projects.clear()
        self.builds.clear()
        self.logs.clear()
        logger.info("🛑 Local database cleared")

    async def create_tables(self):
        # Nothing to create — dictionaries.
        pass

    async def is_healthy(self) -> bool:
        return True

    async def get_stats(self) -> Dict[str, Any]:
        return {
            "total_projects": len(self.projects),
            "total_builds": sum(len(b) for b in self.builds.values()),
            "total_users": 0,
            "mode": "local",
        }

    # ---------- projects ----------

    async def create_project(
        self,
        project_id: str,
        user_id: str,
        title: str,
        prompt: str,
        **kwargs
    ) -> Dict:
        async with self._lock:
            now = datetime.utcnow().isoformat()
            project = {
                "id": project_id,
                "user_id": user_id,
                "title": title,
                "prompt": prompt,
                "description": kwargs.get("description"),
                "genre": kwargs.get("genre"),
                "status": "generating",
                "metadata": kwargs.get("metadata", {}),
                # ISO strings, matching what Supabase returns, so callers that
                # handle one handle the other.
                "created_at": now,
                "updated_at": now,
            }
            self.projects[project_id] = project
            logger.info(f"🗃️  Project created locally: {project_id}")
            return project

    async def get_project(self, project_id: str) -> Optional[Dict]:
        return self.projects.get(project_id)

    async def update_project(self, project_id: str, **updates) -> bool:
        async with self._lock:
            project = self.projects.get(project_id)
            if not project:
                return False
            for key, value in updates.items():
                if isinstance(value, datetime):
                    value = value.isoformat()
                elif isinstance(value, bytes):
                    continue  # never store binary in the project record
                project[key] = value
            project["updated_at"] = datetime.utcnow().isoformat()
            return True

    async def get_user_projects(
        self, user_id: str, limit: int = 50, offset: int = 0
    ) -> List[Dict]:
        rows = [p for p in self.projects.values() if p.get("user_id") == user_id]
        rows.sort(key=lambda p: p.get("created_at", ""), reverse=True)
        return rows[offset: offset + limit]

    async def list_projects(
        self,
        user_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict]:
        rows = list(self.projects.values())
        if user_id:
            rows = [p for p in rows if p.get("user_id") == user_id]
        if status:
            rows = [p for p in rows if p.get("status") == status]
        rows.sort(key=lambda p: p.get("created_at", ""), reverse=True)
        return rows[offset: offset + limit]

    # ---------- builds ----------

    async def create_build(
        self, project_id: str, platform: str, build_url: str, **kwargs
    ) -> str:
        async with self._lock:
            build_id = f"{project_id}:{platform}"
            record = {
                "id": build_id,
                "project_id": project_id,
                "platform": platform,
                "build_url": build_url,
                "web_preview_url": kwargs.get("web_preview_url"),
                "status": kwargs.get("status", "completed"),
                "created_at": datetime.utcnow().isoformat(),
            }
            self.builds.setdefault(project_id, []).append(record)
            return build_id

    async def get_builds(self, project_id: str) -> List[Dict]:
        return self.builds.get(project_id, [])

    async def update_build(self, build_id: str, **updates) -> bool:
        for records in self.builds.values():
            for record in records:
                if record["id"] == build_id:
                    record.update(updates)
                    return True
        return False

    # ---------- logs ----------

    async def log_generation_step(
        self, project_id: str, step: str, status: str, **kwargs
    ):
        self.logs.setdefault(project_id, []).append({
            "project_id": project_id,
            "step": step,
            "status": status,
            "ai_model": kwargs.get("ai_model"),
            "error": kwargs.get("error"),
            "metadata": kwargs.get("metadata", {}),
            "created_at": datetime.utcnow().isoformat(),
        })

    async def get_project_logs(self, project_id: str) -> List[Dict]:
        return self.logs.get(project_id, [])


class LocalStorageService:
    """Disk-backed replacement for StorageService."""

    def __init__(self, root_dir: str = "./local_storage", public_base_url: str = "http://localhost:8000"):
        self.root = Path(root_dir)
        self.public_base_url = public_base_url.rstrip("/")
        # Kept so code that reads storage_service.bucket still works.
        self.bucket = "local"
        self.root.mkdir(parents=True, exist_ok=True)
        logger.info(f"📦 Local storage at {self.root.resolve()}")

    async def connect(self):
        self.root.mkdir(parents=True, exist_ok=True)
        logger.info("✅ Local storage ready")

    async def disconnect(self):
        logger.info("🛑 Local storage released")

    async def is_healthy(self) -> bool:
        return self.root.exists()

    def _safe_path(self, path: str) -> Path:
        """Resolve a storage key to a path, refusing to escape the root."""
        target = (self.root / path).resolve()
        root = self.root.resolve()
        if root not in target.parents and target != root:
            raise ValueError(f"Refusing to access path outside storage root: {path}")
        return target

    def public_url(self, path: str) -> str:
        """
        Browser-reachable URL for a stored file. Game previews are served by
        this backend rather than a CDN, so point at the preview route.
        """
        parts = Path(path).parts
        if len(parts) >= 2 and parts[0] == "web_games":
            # /play serves any file in the game directory, which a Godot web
            # export needs (.wasm, .pck, .js) and a single-file HTML5 game
            # tolerates just as well.
            rest = "/".join(parts[2:]) or "index.html"
            return f"{self.public_base_url}/api/v1/generate/play/{parts[1]}/{rest}"
        return f"{self.public_base_url}/api/v1/generate/file/{path}"

    async def upload_file(
        self,
        path: str,
        data: bytes,
        content_type: str = "application/octet-stream",
        public: bool = False,
        metadata: Optional[Dict[str, str]] = None,
    ) -> str:
        target = self._safe_path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        logger.debug(f"💾 Wrote {len(data)} bytes -> {target}")
        return self.public_url(path)

    async def download_file(self, path: str) -> bytes:
        target = self._safe_path(path)
        if not target.exists():
            raise FileNotFoundError(f"Not found in local storage: {path}")
        return target.read_bytes()

    async def delete_file(self, path: str) -> bool:
        try:
            target = self._safe_path(path)
            if target.is_dir():
                shutil.rmtree(target)
            elif target.exists():
                target.unlink()
            return True
        except Exception as e:
            logger.error(f"Local delete failed for {path}: {e}")
            return False

    async def list_files(self, prefix: str = "") -> list:
        base = self._safe_path(prefix) if prefix else self.root
        if not base.exists():
            return []
        return [
            {"name": str(p.relative_to(self.root)), "size": p.stat().st_size}
            for p in base.rglob("*") if p.is_file()
        ]

    async def get_file_url(self, path: str, public: bool = False, expires_in: int = 3600) -> str:
        return self.public_url(path)

    def _guess_content_type(self, filename: str) -> str:
        content_type, _ = mimetypes.guess_type(filename)
        return content_type or "application/octet-stream"
