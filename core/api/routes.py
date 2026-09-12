"""API Routes"""

import asyncio
from fastapi import APIRouter, HTTPException, Depends, WebSocket, WebSocketDisconnect, Header, Query, Request
from fastapi.responses import Response, StreamingResponse, HTMLResponse
import zipfile
import io
from pathlib import Path
from pydantic import BaseModel, EmailStr
from typing import Optional, List
import logging
import uuid
from datetime import datetime
import httpx
import re

logger = logging.getLogger(__name__)

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class AuthResponse(BaseModel):
    user_id: int
    email: str
    token: str

class GenerateGameRequest(BaseModel):
    prompt: str
    title: Optional[str] = None
    description: Optional[str] = None
    genre: Optional[str] = None
    answers: Optional[dict] = None


class ClarifyRequest(BaseModel):
    prompt: str


class IterateRequest(BaseModel):
    project_id: str
    prompt: str

class ProjectResponse(BaseModel):
    project_id: str
    title: str
    description: Optional[str]
    status: str
    web_preview_url: Optional[str]
    builds: Optional[dict]
    created_at: str

auth_router = APIRouter()
projects_router = APIRouter()
generation_router = APIRouter()


def get_components():
    from main import components
    return components


def get_component(components: dict, key: str, required: bool = True):
    from services.code_validator import validate_component_keys
    
    if key not in components:
        if required:
            missing = validate_component_keys(components, [key])
            if missing:
                logger.error(f"❌ Missing required component: '{key}'")
                raise HTTPException(
                    status_code=500,
                    detail=f"Server configuration error: Missing component '{key}'"
                )
        return None
    return components[key]


# Identity used for every request while AUTH_ENABLED is false, so projects
# still get a stable owner and the DB's user_id column stays satisfied.
DEV_USER = {
    "user_id": "00000000-0000-0000-0000-000000000000",
    "email": "dev@localhost",
    "role": "authenticated"
}


def auth_is_enabled(components: dict) -> bool:
    settings = components.get('settings')
    return getattr(settings, 'auth_enabled', True) if settings else True


async def get_current_user(
    authorization: Optional[str] = Header(None),
    components = Depends(get_components)
):
    auth_manager = components['auth']
    token = authorization.replace("Bearer ", "") if (
        authorization and authorization.startswith("Bearer ")
    ) else None

    if not auth_is_enabled(components):
        # Still honour a real token when one is present, so that signing in
        # keeps showing you your own projects rather than the dev user's.
        if token:
            user = auth_manager.get_current_user(token)
            if user:
                return user
        return DEV_USER

    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    user = auth_manager.get_current_user(token)

    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    return user


@auth_router.post("/register", response_model=AuthResponse)
async def register(request: RegisterRequest, components = Depends(get_components)):
    try:
        auth_manager = components['auth']
        result = await auth_manager.register_user(request.email, request.password)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Registration error: {e}")
        raise HTTPException(status_code=500, detail="Registration failed")


@auth_router.post("/login", response_model=AuthResponse)
async def login(request: LoginRequest, components = Depends(get_components)):
    try:
        auth_manager = components['auth']
        result = await auth_manager.login_user(request.email, request.password)
        return result
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        logger.error(f"Login error: {e}")
        raise HTTPException(status_code=500, detail="Login failed")


@auth_router.get("/me")
async def get_me(current_user = Depends(get_current_user)):
    return current_user


def _iso(value) -> str:
    """created_at may be a datetime or an ISO string depending on backend."""
    if value is None:
        return ""
    return value.isoformat() if hasattr(value, "isoformat") else str(value)


@projects_router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: str,
    current_user = Depends(get_current_user),
    components = Depends(get_components)
):
    db = components['db']
    project = await db.get_project(project_id)
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Check ownership
    if project['user_id'] != current_user['user_id']:
        raise HTTPException(status_code=403, detail="Access denied")
    
    return {
        "project_id": project['id'],
        "title": project['title'],
        "description": project['description'],
        "status": project['status'],
        "web_preview_url": project.get('web_preview_url'),  # May not exist if generation failed
        "builds": project.get('builds', {}),
        "created_at": _iso(project.get('created_at'))
    }


@projects_router.get("/", response_model=List[ProjectResponse])
async def list_projects(
    limit: int = 50,
    offset: int = 0,
    current_user = Depends(get_current_user),
    components = Depends(get_components)
):
    db = components['db']
    projects = await db.get_user_projects(
        user_id=current_user['user_id'],
        limit=limit,
        offset=offset
    )
    
    return [
        {
            "project_id": p['id'],
            "title": p['title'],
            "description": p['description'],
            "status": p['status'],
            "web_preview_url": p.get('web_preview_url'),  # May not exist if generation failed
            "builds": p.get('builds', {}),
            "created_at": _iso(p.get('created_at'))
        }
        for p in projects
    ]


@generation_router.post("/clarify")
async def clarify_game(
    request: ClarifyRequest,
    current_user = Depends(get_current_user),
    components = Depends(get_components)
):
    """
    Classify the request and return any questions worth asking first.

    Usually returns zero questions — the bar is that two plausible answers
    would produce materially different games. Naming a known game clears it.
    """
    try:
        from services.ai_game_clarifier import GameClarifier
        orchestrator = components['orchestrator']
        result = await GameClarifier(orchestrator.deepseek).clarify(request.prompt)
        return result
    except Exception as e:
        logger.error(f"Clarify failed: {e}", exc_info=True)
        from services import game_genres
        return {
            "genre": game_genres.DEFAULT_GENRE,
            "confidence": "low",
            "summary": "",
            "questions": [],
            "options": game_genres.options(),
        }


@generation_router.post("/game")
async def generate_game(
    request: GenerateGameRequest,
    current_user = Depends(get_current_user),
    components = Depends(get_components)
):
    try:
        # Rate limiting
        rate_limiter = components['rate_limiter']
        allowed, remaining = await rate_limiter.check_rate_limit(
            f"user:{current_user['user_id']}",
            limit=10,  # 10 games per hour
            window=3600
        )
        
        if not allowed:
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded. Try again later."
            )
        
        project_id = str(uuid.uuid4())
        db = components['db']
        user_id = str(current_user['user_id'])
        
        await db.create_project(
            project_id=project_id,
            user_id=user_id,
            title=request.title or "AI Generated Game",
            description=request.description or "",
            prompt=request.prompt
        )
        
        import asyncio
        orchestrator = components['orchestrator']
        ws_manager = components['ws_manager']
        
        async def generation_task():
            try:
                async def progress_callback(progress_data):
                    await ws_manager.send_message(project_id, {
                        "type": "progress",
                        "data": progress_data
                    })
                
                result = await orchestrator.generate_game(
                    project_id=project_id,
                    user_prompt=request.prompt,
                    user_tier="free",
                    db_manager=db,
                    genre_id=request.genre,
                    answers=request.answers
                )
                
                if result['success']:
                    ai_content = result.get('ai_content', {})
                    if isinstance(ai_content, dict):
                        if 'assets' in ai_content and isinstance(ai_content['assets'], list):
                            cleaned_assets = []
                            for asset in ai_content['assets']:
                                if isinstance(asset, dict):
                                    cleaned_asset = {k: v for k, v in asset.items() if not isinstance(v, bytes)}
                                    cleaned_assets.append(cleaned_asset)
                                else:
                                    cleaned_assets.append(asset)
                            ai_content['assets'] = cleaned_assets
                    
                    await db.update_project(
                        project_id=project_id,
                        ai_content=ai_content,
                        status='completed',
                        completed_at=datetime.utcnow()
                    )
                    
                    builds_dict = result.get('builds', {})
                    for platform, url in builds_dict.items():
                        await db.create_build(
                            project_id=project_id,
                            platform=platform,
                            build_url=url,
                            web_preview_url=result.get('web_preview_url'),
                            status='completed'
                        )
                    
                    preview_url = result.get('preview_url') or result.get('web_preview_url')
                    await ws_manager.send_message(project_id, {
                        "type": "complete",
                        "data": {
                            "project_id": project_id,
                            "preview_url": preview_url,
                            "web_preview_url": preview_url,
                            "builds": builds_dict
                        }
                    })
                else:
                    await db.update_project(
                        project_id=project_id,
                        status='failed'
                    )
                    
                    await ws_manager.send_message(project_id, {
                        "type": "error",
                        "data": {"error": result.get('error')}
                    })
                    
            except Exception as e:
                logger.error(f"Generation task failed: {e}", exc_info=True)
                await db.update_project(project_id=project_id, status='failed')
                await ws_manager.send_message(project_id, {
                    "type": "error",
                    "data": {"error": str(e)}
                })
        
        asyncio.create_task(generation_task())
        
        return {
            "project_id": project_id,
            "status": "processing",
            "message": "Game generation started. Connect to WebSocket for progress updates.",
            "websocket_url": f"/api/v1/generate/ws/{project_id}"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Generation start error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to start generation")


@generation_router.post("/iterate")
async def iterate_game(
    request: IterateRequest,
    current_user = Depends(get_current_user),
    components = Depends(get_components)
):
    """Apply a change to an existing game, reusing its files and its project id."""
    try:
        orchestrator = components['orchestrator']
        ws_manager = components['ws_manager']
        db = components['db']
        project_id = request.project_id

        async def iteration_task():
            try:
                result = await orchestrator.iterate_game(project_id, request.prompt, db_manager=db)
                if result.get('success'):
                    preview = result.get('preview_url')
                    await ws_manager.send_message(project_id, {
                        "type": "complete",
                        "data": {"project_id": project_id, "preview_url": preview,
                                 "web_preview_url": preview, "iterated": True,
                                 "changed_files": result.get('changed_files', [])},
                    })
                else:
                    await ws_manager.send_message(project_id, {
                        "type": "error", "data": {"error": result.get('error')}})
            except Exception as e:
                logger.error(f"Iteration task failed: {e}", exc_info=True)
                await ws_manager.send_message(project_id, {
                    "type": "error", "data": {"error": str(e)}})

        asyncio.create_task(iteration_task())
        return {"project_id": project_id, "status": "processing",
                "message": "Applying your change.",
                "websocket_url": f"/api/v1/generate/ws/{project_id}"}
    except Exception as e:
        logger.error(f"Iterate start error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to start iteration")


@generation_router.websocket("/ws/{project_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    project_id: str,
    token: Optional[str] = Query(None),
    components = Depends(get_components)
):
    if token and auth_is_enabled(components):
        auth_manager = components['auth']
        user = auth_manager.get_current_user(token)
        if not user:
            await websocket.close(code=1008, reason="Invalid token")
            return
    
    ws_manager = components['ws_manager']
    await ws_manager.connect(websocket, project_id)

    try:
        await websocket.send_json({
            "type": "connected",
            "data": {
                "project_id": project_id,
                "message": "Connected to generation progress stream"
            }
        })

        # Replay the last known state immediately.
        #
        # send_message() drops anything published while nobody is connected, so
        # a client that attaches late — a refresh, a reconnect, StrictMode
        # remounting the effect — used to miss the terminal message and hang on
        # a stale "Building..." forever. The status is already cached; send it.
        try:
            cache = components.get('cache')
            status = await cache.get_generation_status(project_id) if cache else None
            if status:
                state = status.get("status")
                if state == "completed":
                    db = components.get('db')
                    project = await db.get_project(project_id) if db else None
                    preview = (project or {}).get("web_preview_url")
                    await websocket.send_json({
                        "type": "complete",
                        "data": {"project_id": project_id,
                                 "preview_url": preview,
                                 "web_preview_url": preview,
                                 "replayed": True},
                    })
                elif state == "failed":
                    await websocket.send_json({
                        "type": "error",
                        "data": {"error": status.get("message", "Generation failed"),
                                 "replayed": True},
                    })
                else:
                    await websocket.send_json({
                        "type": "progress",
                        "data": {"status": state, "message": status.get("message", "")},
                    })
        except Exception as e:
            logger.debug(f"Could not replay status for {project_id}: {e}")
        
        while True:
            try:
                data = await websocket.receive_text()
                await websocket.send_json({
                    "type": "echo",
                    "data": {"received": data}
                })
            except:
                break
            
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, project_id)
        logger.info(f"WebSocket disconnected: {project_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        ws_manager.disconnect(websocket, project_id)


# Content types that matter for a Godot web export. A .wasm served as
# octet-stream fails WebAssembly streaming compilation in every browser.
_PLAY_MIME = {
    ".html": "text/html; charset=utf-8",
    ".js":   "text/javascript; charset=utf-8",
    ".wasm": "application/wasm",
    ".pck":  "application/octet-stream",
    ".png":  "image/png",
    ".jpg":  "image/jpeg",
    ".svg":  "image/svg+xml",
    ".json": "application/json",
    ".css":  "text/css; charset=utf-8",
    ".ogg":  "audio/ogg",
    ".wav":  "audio/wav",
}


@generation_router.get("/play/{project_id}/{file_path:path}")
async def play_game_file(
    project_id: str,
    file_path: str = "",
    components = Depends(get_components)
):
    """
    Serve any file from a generated game.

    A Godot web export is a directory (index.html + .wasm + .pck + .js), not a
    single file, so the preview cannot be injected via srcDoc the way the HTML5
    build was. Serving it from a real path also means the iframe no longer needs
    allow-same-origin.
    """
    storage_service = components['storage']
    rel = (file_path or "index.html").lstrip("/")
    if ".." in rel:
        raise HTTPException(status_code=400, detail="Invalid path")

    storage_path = f"web_games/{project_id}/{rel}"

    try:
        data = await storage_service.download_file(storage_path)
    except Exception:
        logger.debug(f"Not found: {storage_path}")
        raise HTTPException(status_code=404, detail=f"Not found: {rel}")

    suffix = Path(rel).suffix.lower()
    media_type = _PLAY_MIME.get(suffix, "application/octet-stream")

    return Response(
        content=data,
        media_type=media_type,
        headers={
            "Access-Control-Allow-Origin": "*",
            # Godot loads its own .wasm/.pck from this origin.
            "Cross-Origin-Resource-Policy": "cross-origin",
            "Cache-Control": "public, max-age=300",
        },
    )


@generation_router.get("/preview/{project_id}")
async def proxy_game_preview(
    project_id: str,
    components = Depends(get_components)
):
    try:
        storage_service = components['storage']
        
        logger.info(f"🔍 Attempting to load preview for project: {project_id}")
        
        web_storage_path = f"web_games/{project_id}/index.html"
        
        html_content = None
        asset_base_url = None
        
        # Try web game first (HTML5 games are in web_games/{project_id}/index.html)
        try:
            html_content_bytes = await storage_service.download_file(web_storage_path)
            html_content = html_content_bytes.decode('utf-8')
            logger.info(f"✅ Found HTML5 game preview at {web_storage_path} ({len(html_content)} bytes)")
            
            # Only rewrite the asset base when the files live somewhere else
            # (Supabase). In local mode they are served from this same origin,
            # so relative paths already resolve and a <base> tag would break them.
            if not hasattr(storage_service, 'public_url'):
                from config.settings import Settings
                settings = Settings()
                supabase_url = settings.supabase_url.rstrip('/')
                bucket = storage_service.bucket
                asset_base_url = f"{supabase_url}/storage/v1/object/public/{bucket}/web_games/{project_id}"

                if '<head>' in html_content and 'base href' not in html_content.lower():
                    base_tag = f'<base href="{asset_base_url}/">'
                    html_content = html_content.replace('<head>', f'<head>\n    {base_tag}', 1)
                    logger.info("Added base tag for HTML5 asset loading")
            
        except Exception as web_error:
            logger.debug(f"Web game not found at {web_storage_path}: {web_error}")
            # Try src/index.html if dist doesn't exist
            try:
                src_storage_path = f"web_games/{project_id}/src/index.html"
                html_content_bytes = await storage_service.download_file(src_storage_path)
                html_content = html_content_bytes.decode('utf-8')
                logger.info(f"Found web game in src directory ({len(html_content)} bytes)")
                
                asset_base_url = None
            except Exception as src_error:
                logger.debug(f"Web game not found in dist or src: {web_error}, {src_error}")
                html_content = None
        
        
        if not html_content:
            raise HTTPException(
                status_code=404,
                detail="Game preview not found. It may still be generating."
            )

        # Serve with headers that allow inline styles/scripts and iframe embedding
        # Note: Removed X-Frame-Options to allow cross-origin embedding (frontend on 8080, backend on 8000)
        # Using CSP frame-ancestors instead for better control
        # Use HTMLResponse to ensure proper HTML rendering
        return HTMLResponse(
            content=html_content,
            headers={
                "Content-Security-Policy": "default-src 'self' 'unsafe-inline' 'unsafe-eval' data: blob: *; script-src 'self' 'unsafe-inline' 'unsafe-eval' *; style-src 'self' 'unsafe-inline' *; img-src 'self' data: blob: *; font-src 'self' data: *; connect-src 'self' *; worker-src 'self' blob: *; frame-ancestors *;",
                "X-Content-Type-Options": "nosniff",
                "Access-Control-Allow-Origin": "*",  # Allow CORS for asset loading
                # Note: X-Frame-Options is omitted to allow iframe embedding (CSP frame-ancestors handles this)
            }
        )
    except Exception as e:
        logger.error(f"Preview proxy error: {e}", exc_info=True)
        raise HTTPException(status_code=404, detail=f"Game preview not found: {str(e)}")


@generation_router.get("/download/{project_id}")
async def download_game(
    project_id: str,
    request: Request,
    platform: Optional[str] = Query("windows", description="Platform: windows (prototype mode - only Windows builds)"),
    current_user = Depends(get_current_user),
    components = Depends(get_components)
):
    """
    Download game build for a project.
    PROTOTYPE MODE: Only Windows builds are available.
    Defaults to 'windows' if not specified.
    """
    try:
        # PROTOTYPE: Force Windows platform
        if not platform or platform.lower() != "windows":
            logger.info(f"📥 PROTOTYPE MODE: Requested platform '{platform}' not available, using Windows")
            platform = "windows"
        
        logger.info(f"📥 Download request: project_id={project_id}, platform={platform} (PROTOTYPE: Windows only)")
        
        # Safely get components with validation
        db = get_component(components, 'db')
        storage_service = get_component(components, 'storage')
        
        # Get builds for this project
        try:
            builds = await db.get_builds(project_id)
            logger.info(f"📦 Found {len(builds)} builds for project {project_id}")
            if builds:
                logger.info(f"📦 Build platforms: {[b.get('platform') for b in builds]}")
        except Exception as e:
            logger.error(f"❌ Failed to get builds from database: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
        
        if not builds:
            logger.warning(f"⚠️  No builds found for project {project_id}")
            raise HTTPException(status_code=404, detail="No builds found for this project. The game may still be generating.")
        
        # PROTOTYPE: Only look for Windows build
        build_url = None
        filename = None
        selected_platform = "windows"
        
        # Look for Windows build
        for build in builds:
            build_platform = build.get('platform', '').lower()
            logger.info(f"🔍 Checking build platform: {build_platform}")
            if build_platform == "windows":
                build_url = build.get('build_url')
                filename = f"{project_id}_windows.exe"
                logger.info(f"✅ Found Windows build: {build_url}")
                break
        
        if not build_url:
            available_platforms = [b.get('platform', 'unknown') for b in builds]
            logger.error(f"❌ Windows build not found. Available builds: {available_platforms}")
            error_detail = (
                f"Windows build not found for this project. "
                f"Available platforms: {', '.join(available_platforms) if available_platforms else 'none'}. "
                f"The game may still be generating. Please wait and try again."
            )
            raise HTTPException(status_code=404, detail=error_detail)
        
        logger.info(f"📥 Using build URL: {build_url}")
        
        # Extract storage path from Supabase URL
        # URL format: https://{project}.supabase.co/storage/v1/object/public/{bucket}/{path}
        storage_path = _extract_storage_path(build_url)
        
        file_data = None
        download_method = None
        
        # Method 1: Try downloading from storage using path (most reliable)
        if storage_path:
            logger.info(f"📁 Storage path extracted: {storage_path}")
            try:
                file_data = await storage_service.download_file(storage_path)
                if file_data and len(file_data) > 0:
                    download_method = "storage_path"
                    logger.info(f"✅ Downloaded build from storage path: {storage_path} ({len(file_data)} bytes)")
                else:
                    logger.warning(f"⚠️  Storage path download returned empty data")
                    file_data = None
            except Exception as download_error:
                logger.warning(f"⚠️  Failed to download from storage path: {download_error}")
                file_data = None
        
        # Method 2: Try downloading directly from URL (fallback)
        if not file_data:
            logger.info(f"🔄 Attempting direct download from URL: {build_url}")
            try:
                import httpx
                async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
                    response = await client.get(build_url)
                    if response.status_code == 200:
                        file_data = response.content
                        if file_data and len(file_data) > 0:
                            download_method = "direct_url"
                            logger.info(f"✅ Downloaded build directly from URL ({len(file_data)} bytes)")
                        else:
                            logger.error(f"❌ Direct URL download returned empty data")
                            file_data = None
                    else:
                        logger.error(f"❌ Direct URL download failed: HTTP {response.status_code}")
                        file_data = None
            except httpx.TimeoutException:
                logger.error(f"❌ Download timeout after 120 seconds")
                raise HTTPException(
                    status_code=504,
                    detail="Download timeout. The file may be too large or the server is slow. Please try again."
                )
            except httpx.RequestError as e:
                logger.error(f"❌ HTTP request failed: {e}")
                file_data = None
            except Exception as e:
                logger.error(f"❌ Direct download failed: {e}", exc_info=True)
                file_data = None
        
        # Method 3: Try reading from local project directory (last resort for prototype)
        if not file_data:
            logger.info(f"🔄 Attempting to read from local project directory...")
            try:
                from pathlib import Path
                projects_dir = Path("./core/projects")
                local_build_path = projects_dir / project_id / "exports" / f"{project_id}_windows.exe"
                
                if local_build_path.exists():
                    with open(local_build_path, 'rb') as f:
                        file_data = f.read()
                    if file_data and len(file_data) > 0:
                        download_method = "local_file"
                        logger.info(f"✅ Read build from local file: {local_build_path} ({len(file_data)} bytes)")
                    else:
                        logger.error(f"❌ Local file is empty")
                        file_data = None
                else:
                    logger.warning(f"⚠️  Local build file not found: {local_build_path}")
            except Exception as e:
                logger.error(f"❌ Failed to read local file: {e}")
                file_data = None
        
        # CRITICAL: If all methods failed, return detailed error
        if not file_data or len(file_data) == 0:
            error_details = {
                "storage_path": storage_path,
                "build_url": build_url,
                "download_method": download_method,
                "available_builds": [b.get('platform') for b in builds]
            }
            logger.error(f"❌ CRITICAL: All download methods failed! Details: {error_details}")
            raise HTTPException(
                status_code=404,
                detail=(
                    f"Failed to download Windows build. "
                    f"Storage path: {storage_path or 'N/A'}, "
                    f"URL: {build_url or 'N/A'}. "
                    f"The build may not be ready yet. Please wait and try again."
                )
            )
        
        # PROTOTYPE: Windows EXE only - set proper content type
        content_type = 'application/x-msdownload'  # Windows EXE MIME type
        if not filename:
            filename = f"{project_id}_windows.exe"
        
        # Return file as download
        logger.info(f"✅ Returning file download: {filename} ({len(file_data)} bytes, type: {content_type})")
        return Response(
            content=file_data,
            media_type=content_type,
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Content-Length": str(len(file_data)),
                "Access-Control-Allow-Origin": "*"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Download error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Download failed: {str(e)}")


@generation_router.get("/download-web/{project_id}")
async def download_web_game(
    project_id: str,
    current_user = Depends(get_current_user),
    components = Depends(get_components)
):
    """
    Download HTML5 web game as ZIP file for local use
    """
    try:
        logger.info(f"📥 Download request for HTML5 game: project_id={project_id}")
        
        storage_service = components['storage']
        
        # Create ZIP file in memory
        zip_buffer = io.BytesIO()
        
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # Download and add index.html
            try:
                index_path = f"web_games/{project_id}/index.html"
                index_content = await storage_service.download_file(index_path)
                zipf.writestr("index.html", index_content)
                logger.info(f"✅ Added index.html to ZIP")
            except Exception as e:
                logger.error(f"❌ Failed to download index.html: {e}")
                raise HTTPException(status_code=404, detail="Game files not found. The game may still be generating.")
            
            # Download and add all assets
            try:
                # List all files in web_games/{project_id}/ directory
                assets_path = f"web_games/{project_id}/assets"
                
                # Try to download common asset files
                asset_types = ['player', 'enemy', 'collectible', 'platform', 'background']
                for asset_type in asset_types:
                    try:
                        asset_path = f"{assets_path}/{asset_type}.png"
                        asset_content = await storage_service.download_file(asset_path)
                        zipf.writestr(f"assets/{asset_type}.png", asset_content)
                        logger.info(f"✅ Added {asset_type}.png to ZIP")
                    except Exception as e:
                        logger.debug(f"Asset {asset_type}.png not found, skipping: {e}")
                
                # Try to download manifest.json
                try:
                    manifest_path = f"{assets_path}/manifest.json"
                    manifest_content = await storage_service.download_file(manifest_path)
                    zipf.writestr("assets/manifest.json", manifest_content)
                    logger.info(f"✅ Added manifest.json to ZIP")
                except Exception as e:
                    logger.debug(f"manifest.json not found, skipping: {e}")
                    
            except Exception as e:
                logger.warning(f"⚠️  Some assets may be missing: {e}")
                # Continue anyway - at least index.html is included
        
        zip_buffer.seek(0)
        zip_data = zip_buffer.read()
        
        if not zip_data or len(zip_data) == 0:
            raise HTTPException(status_code=500, detail="Failed to create ZIP file")
        
        filename = f"game_{project_id}.zip"
        logger.info(f"✅ Created ZIP file: {filename} ({len(zip_data)} bytes)")
        
        return Response(
            content=zip_data,
            media_type='application/zip',
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Content-Length": str(len(zip_data)),
                "Access-Control-Allow-Origin": "*"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Download error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Download failed: {str(e)}")


def _get_file_extension(platform: str) -> str:
    """Get file extension for platform"""
    extensions = {
        'windows': 'exe',
        'macos': 'zip',  # macOS .app bundle zipped
        'linux': 'x86_64',  # Linux executable
        'android': 'apk',
        'ios': 'ipa',
        'web': 'zip'  # Web builds are zipped with launcher
    }
    return extensions.get(platform.lower(), 'zip')


def _get_content_type(platform: str) -> str:
    """Get content type for platform"""
    content_types = {
        'windows': 'application/x-msdownload',
        'macos': 'application/zip',
        'linux': 'application/x-executable',
        'android': 'application/vnd.android.package-archive',
        'ios': 'application/octet-stream',
        'web': 'application/zip'
    }
    return content_types.get(platform.lower(), 'application/octet-stream')


def _extract_storage_path(url: str) -> Optional[str]:
    """Extract storage path from Supabase URL (public or signed)"""
    try:
        import urllib.parse
        parsed = urllib.parse.urlparse(url)
        
        # Handle public URLs: /storage/v1/object/public/{bucket}/{path}
        if '/storage/v1/object/public/' in parsed.path:
            path_part = parsed.path.split('/storage/v1/object/public/')[1]
            return path_part
        
        # Handle signed URLs: /storage/v1/object/sign/{bucket}/{path}?token=...
        elif '/storage/v1/object/sign/' in parsed.path:
            path_part = parsed.path.split('/storage/v1/object/sign/')[1]
            # Remove any query parameters (token, signature, etc.)
            if '?' in path_part:
                path_part = path_part.split('?')[0]
            return path_part
        
        # If URL is already just a path (bucket/path format), return as-is
        elif not url.startswith('http'):
            return url
        
        return None
    except Exception as e:
        logger.error(f"Failed to extract storage path from URL: {e}")
        return None


# ============= CLEANUP ROUTES =============

@projects_router.post("/cleanup")
async def cleanup_projects(
    dry_run: bool = Query(False, description="If true, only show what would be deleted"),
    current_user = Depends(get_current_user),
    components = Depends(get_components)
):
    """Clean up old projects to save disk space"""
    cleanup_service = get_component(components, 'cleanup', required=False)
    
    if not cleanup_service:
        raise HTTPException(
            status_code=503,
            detail="Cleanup service not available"
        )
    
    try:
        stats = await cleanup_service.cleanup_old_projects(dry_run=dry_run)
        return {
            "success": True,
            "dry_run": dry_run,
            "stats": stats,
            "message": f"Cleanup {'simulation' if dry_run else 'completed'}: {stats['deleted']} projects deleted, {stats['space_freed_mb']:.2f} MB freed"
        }
    except Exception as e:
        logger.error(f"Cleanup error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Cleanup failed: {str(e)}")


@projects_router.get("/cleanup/stats")
async def get_cleanup_stats(
    current_user = Depends(get_current_user),
    components = Depends(get_components)
):
    """Get statistics about projects that could be cleaned up"""
    cleanup_service = get_component(components, 'cleanup', required=False)
    
    if not cleanup_service:
        raise HTTPException(
            status_code=503,
            detail="Cleanup service not available"
        )
    
    try:
        stats = await cleanup_service.get_cleanup_stats()
        return {
            "success": True,
            "stats": stats
        }
    except Exception as e:
        logger.error(f"Cleanup stats error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get cleanup stats: {str(e)}")
