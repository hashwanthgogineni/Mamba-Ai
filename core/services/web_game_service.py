import os
import json
import re
import asyncio
import shutil
import zipfile
from pathlib import Path
from typing import Dict, List, Optional, Any
import logging
import base64
from datetime import datetime

logger = logging.getLogger(__name__)


def _public_url_for(storage_service: Any, path: str) -> str:
    """
    Browser-reachable URL for a stored file.

    Local storage knows its own URL shape; the Supabase service does not, so
    fall back to building the public-object URL for it.
    """
    if hasattr(storage_service, "public_url"):
        return storage_service.public_url(path)

    from config.settings import Settings
    settings = Settings()
    base = settings.supabase_url.rstrip("/")
    return f"{base}/storage/v1/object/public/{storage_service.bucket}/{path}"


class WebGameService:
    
    def __init__(
        self,
        projects_dir: str = "./web_projects",
        templates_dir: str = "./web_templates"
    ):
        self.projects_dir = Path(projects_dir)
        self.templates_dir = Path(templates_dir)
        self.projects_dir.mkdir(parents=True, exist_ok=True)
        self.templates_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Web Game Service initialized")
        logger.info(f"   Projects: {projects_dir}")
        logger.info(f"   Templates: {templates_dir}")
    
    async def start(self):
        logger.info("Web Game service started")
    
    async def stop(self):
        logger.info("Web Game service stopped")
    
    async def is_healthy(self) -> bool:
        return True
    
    async def build_game_from_ai_content(
        self,
        project_id: str,
        ai_content: Dict[str, Any],
        storage_service: Any,
        deepseek_client = None
    ) -> Dict[str, Any]:
        
        project_path = self.projects_dir / project_id
        project_path.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Building web game: {project_id}")
        
        try:
            game_design = ai_content.get('game_design', {})
            game_mechanics = ai_content.get('game_mechanics', {})
            game_scripts = ai_content.get('scripts', {})
            
            use_ai_code = game_scripts.get('use_ai', False) or game_scripts.get('scripts_generated_by') == 'ai_deepseek'
            
            if use_ai_code:
                # Detect dimension and use appropriate generator
                dimension = game_design.get('dimension', '2D').upper()
                if dimension == '3D':
                    logger.info("Generating Three.js 3D game code with DeepSeek...")
                else:
                    logger.info("Generating HTML5 Canvas 2D game code with DeepSeek...")
                user_prompt = ai_content.get('user_prompt')
                await self._generate_game_with_ai(project_path, game_design, game_mechanics, deepseek_client, user_prompt, dimension)
            else:
                logger.info("Using pre-built templates...")
                genre = game_design.get('genre', 'platformer').lower()
                template_path = await self._select_template(genre)
                await self._copy_template(template_path, project_path)
                await self._customize_game(project_path, ai_content)
            
            assets = ai_content.get('assets', [])
            await self._process_assets(project_path, assets, game_design)
            
            build_result = await self._process_html5_game(project_path)
            
            deployment_url = None
            if storage_service:
                deployment_url = await self._upload_to_storage(
                    storage_service, 
                    project_path, 
                    project_id,
                    build_result
                )
            
            logger.info(f"Web game built successfully: {project_id}")
            
            # Use direct Supabase Storage URL for preview (better for iframe embedding)
            # The proxy endpoint can have issues with iframe rendering
            preview_url = deployment_url
            if not preview_url and storage_service:
                # Ask the storage backend for the browser-reachable URL rather
                # than assuming Supabase — local mode serves from this backend.
                preview_url = _public_url_for(
                    storage_service, f"web_games/{project_id}/index.html"
                )
                logger.info(f"Preview URL: {preview_url}")
            
            return {
                "success": True,
                "project_id": project_id,
                "project_path": str(project_path),
                "build_path": build_result.get("build_path"),
                "deployment_url": deployment_url,
                "preview_url": preview_url,
                "game_url": preview_url,
                "format": "web",
                "playable": True
            }
            
        except Exception as e:
            logger.error(f"Failed to build web game: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "project_id": project_id
            }
    
    async def _select_template(self, genre: str) -> Path:
        # Selects template based on genre
        genre_templates = {
            'platformer': 'platformer_2d',
            'puzzle': 'puzzle_2d',
            'shooter': 'shooter_2d',
            'rpg': 'rpg_2d',
            'racing': 'racing_2d',
            'match-3': 'match_3',
            'endless-runner': 'endless_runner_2d',
            'tower-defense': 'tower_defense_2d',
            'roguelike': 'roguelike_2d',
            'survival': 'survival_2d',
            'rhythm': 'rhythm_2d',
            'metroidvania': 'metroidvania_2d',
            'farming': 'farming_sim_2d',
            'bullet-hell': 'bullet_hell_2d'
        }
        
        template_name = genre_templates.get(genre, 'platformer_2d')
        template_path = self.templates_dir / template_name
        
        if not template_path.exists():
            logger.warning(f"Template '{template_name}' not found, using platformer as fallback")
            # Try platformer as fallback
            fallback_path = self.templates_dir / "platformer_2d"
            if fallback_path.exists():
                template_path = fallback_path
            else:
                template_path.mkdir(parents=True, exist_ok=True)
        
        return template_path
    
    async def _copy_template(self, template_path: Path, project_path: Path):
        # Copies template files to project
        if not template_path.exists():
            raise FileNotFoundError(f"Template not found: {template_path}")
        
        # Copy all files from template
        shutil.copytree(template_path, project_path, dirs_exist_ok=True)
        logger.info(f"Copied template: {template_path.name}")
    
    async def _process_assets(
        self,
        project_path: Path,
        assets: List[Dict],
        game_design: Dict
    ):
        # Processes assets and embeds in game
        # HTML5 games use root/assets (simpler, no build needed)
        assets_dir = project_path / "assets"
        assets_dir.mkdir(parents=True, exist_ok=True)
        
        # Also keep src/assets for backward compatibility (if React is used)
        src_assets_dir = project_path / "src" / "assets"
        src_assets_dir.mkdir(parents=True, exist_ok=True)
        
        # Create assets manifest
        assets_manifest = {
            "player": None,
            "enemy": None,
            "collectible": None,
            "platform": None,
            "background": None,
            "ui": {}
        }
        
        assets_saved = 0
        for asset in assets:
            asset_type = asset.get('type', '')
            asset_data = asset.get('data')
            asset_path = asset.get('path', '')
            
            if not asset_data:
                logger.warning(f"Asset {asset_type} has no data, skipping")
                continue
            
            try:
                # Save asset file in root/assets (for HTML5 games)
                if asset_type in ['player', 'enemy', 'collectible', 'platform', 'background']:
                    file_path = assets_dir / f"{asset_type}.png"
                    with open(file_path, 'wb') as f:
                        if isinstance(asset_data, bytes):
                            f.write(asset_data)
                        else:
                            f.write(base64.b64decode(asset_data))
                    
                    # Also save to src/assets for backward compatibility (if React is used)
                    src_file_path = src_assets_dir / f"{asset_type}.png"
                    with open(src_file_path, 'wb') as f:
                        if isinstance(asset_data, bytes):
                            f.write(asset_data)
                        else:
                            f.write(base64.b64decode(asset_data))
                    
                    # Store in manifest - use relative path for HTML5 games
                    assets_manifest[asset_type] = f"./assets/{asset_type}.png"
                    assets_saved += 1
                    logger.info(f"Saved {asset_type} asset: {file_path}")
            except Exception as e:
                logger.error(f"Failed to save asset {asset_type}: {e}")
                continue
        
        # Save assets manifest (in root/assets for HTML5)
        manifest_path = assets_dir / "manifest.json"
        try:
            with open(manifest_path, 'w', encoding='utf-8') as f:
                json.dump(assets_manifest, f, indent=2)
            logger.debug("Saved assets manifest")
        except Exception as e:
            logger.error(f"Failed to save assets manifest: {e}")
        
        logger.info(f"Processed {assets_saved}/{len(assets)} assets successfully")
    
    async def _customize_game(self, project_path: Path, ai_content: Dict):
        # Customizes game with AI content
        game_design = ai_content.get('game_design', {})
        game_mechanics = ai_content.get('game_mechanics', {})
        
        game_title = game_design.get('title', 'AI Generated Game')
        player_speed = game_mechanics.get('player_speed', game_mechanics.get('player_movement', {}).get('speed', 5))
        jump_height = game_mechanics.get('jump_height', abs(game_mechanics.get('player_movement', {}).get('jump_force', -10)))
        
        # Update index.html title
        index_path = project_path / "index.html"
        if index_path.exists():
            try:
                index_content = index_path.read_text(encoding='utf-8')
                index_content = index_content.replace('{{GAME_TITLE}}', game_title)
                index_path.write_text(index_content, encoding='utf-8')
                logger.debug("Updated index.html title")
            except Exception as e:
                logger.warning(f"Failed to update index.html: {e}")
        
        # Update game config - ensure config directory exists
        config_dir = project_path / "src" / "config"
        config_dir.mkdir(parents=True, exist_ok=True)
        config_path = config_dir / "gameConfig.js"
        
        if config_path.exists():
            try:
                config_content = config_path.read_text(encoding='utf-8')
                
                # Replace placeholders (handle both string and number formats)
                config_content = config_content.replace('{{GAME_TITLE}}', f"'{game_title}'")
                config_content = config_content.replace('{{PLAYER_SPEED}}', str(player_speed))
                config_content = config_content.replace('{{JUMP_HEIGHT}}', str(jump_height))
                
                config_path.write_text(config_content, encoding='utf-8')
                logger.debug("Updated gameConfig.js")
            except Exception as e:
                logger.warning(f"Failed to update gameConfig.js: {e}")
        else:
            # Create default config if it doesn't exist
            logger.warning(f"gameConfig.js not found at {config_path}, creating default")
            default_config = f"""// Game configuration
const gameConfig = {{
  title: '{game_title}',
  player: {{
    speed: {player_speed},
    jumpHeight: {jump_height},
    width: 64,
    height: 64
  }},
  gravity: 0.8,
  world: {{
    width: 1920,
    height: 1080
  }}
}};

export default gameConfig;
"""
            try:
                config_path.write_text(default_config, encoding='utf-8')
                logger.info("Created default gameConfig.js")
            except Exception as e:
                logger.error(f"Failed to create gameConfig.js: {e}")
        
        logger.info("Customized game with AI content")
    
    def _create_fallback_html5_game(self, game_design: Dict, game_mechanics: Dict) -> Dict[str, str]:
        """Create a production-ready fallback HTML5 Canvas game"""
        
        title = game_design.get('title', 'AI Generated Game')
        genre = game_design.get('genre', 'platformer')
        player_speed = game_mechanics.get('player_speed', game_mechanics.get('player_movement', {}).get('speed', 5))
        jump_force = abs(game_mechanics.get('jump_height', game_mechanics.get('player_movement', {}).get('jump_force', -15)))
        
        # Production-ready HTML5 game template
        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            overflow: hidden;
            background: #1a1a2e;
            font-family: Arial, sans-serif;
        }}
        #gameCanvas {{
            display: block;
            width: 100vw;
            height: 100vh;
        }}
        #ui {{
            position: absolute;
            top: 20px;
            left: 20px;
            color: white;
            font-size: 24px;
            z-index: 100;
        }}
    </style>
</head>
<body>
    <div id="ui">
        <div>Score: <span id="score">0</span></div>
    </div>
    <canvas id="gameCanvas"></canvas>
    
    <script src="https://cdnjs.cloudflare.com/ajax/libs/matter-js/0.19.0/matter.min.js"></script>
    <script>
        const {{ Engine, Render, World, Bodies, Body, Events }} = Matter;
        
        // Game setup
        const canvas = document.getElementById('gameCanvas');
        const ctx = canvas.getContext('2d');
        canvas.width = window.innerWidth;
        canvas.height = window.innerHeight;
        
        // Matter.js engine
        const engine = Engine.create();
        const world = engine.world;
        
        // Game state
        let score = 0;
        const keys = {{}};
        
        // Player
        const player = Bodies.rectangle(100, 300, 50, 50, {{
            frictionAir: 0.01,
            render: {{ fillStyle: '#4A90E2' }}
        }});
        World.add(world, player);
        
        // Ground
        const ground = Bodies.rectangle(canvas.width / 2, canvas.height - 25, canvas.width, 50, {{
            isStatic: true,
            render: {{ fillStyle: '#8B4513' }}
        }});
        World.add(world, ground);
        
        // Input handling
        window.addEventListener('keydown', (e) => {{
            keys[e.key.toLowerCase()] = true;
        }});
        window.addEventListener('keyup', (e) => {{
            keys[e.key.toLowerCase()] = false;
        }});
        
        // Game loop
        function gameLoop() {{
            // Update physics
            Engine.update(engine);
            
            // Handle input
            if (keys['a'] || keys['arrowleft']) {{
                Body.applyForce(player, player.position, {{ x: -0.01, y: 0 }});
            }}
            if (keys['d'] || keys['arrowright']) {{
                Body.applyForce(player, player.position, {{ x: 0.01, y: 0 }});
            }}
            if ((keys['w'] || keys[' '] || keys['arrowup']) && player.position.y > canvas.height - 150) {{
                Body.applyForce(player, player.position, {{ x: 0, y: -0.05 }});
            }}
            
            // Clear canvas
            ctx.fillStyle = '#1a1a2e';
            ctx.fillRect(0, 0, canvas.width, canvas.height);
            
            // Draw all bodies
            world.bodies.forEach(body => {{
                ctx.fillStyle = body.render.fillStyle || '#fff';
                ctx.beginPath();
                ctx.rect(
                    body.position.x - body.bounds.max.x + body.position.x,
                    body.position.y - body.bounds.max.y + body.position.y,
                    body.bounds.max.x - body.bounds.min.x,
                    body.bounds.max.y - body.bounds.min.y
                );
                ctx.fill();
            }});
            
            requestAnimationFrame(gameLoop);
        }}
        
        // Handle resize
        window.addEventListener('resize', () => {{
            canvas.width = window.innerWidth;
            canvas.height = window.innerHeight;
        }});
        
        // Start game
        gameLoop();
    </script>
</body>
</html>"""
        
        return {
            'index.html': html_content
        }
    
    def _create_fallback_threejs_game(self, game_design: Dict, game_mechanics: Dict) -> Dict[str, str]:
        """Create a production-ready fallback Three.js 3D game"""
        
        title = game_design.get('title', 'AI Generated 3D Game')
        
        # Simple Three.js 3D game template
        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            overflow: hidden;
            background: #000;
            font-family: Arial, sans-serif;
        }}
        #ui {{
            position: absolute;
            top: 20px;
            left: 20px;
            color: white;
            font-size: 24px;
            z-index: 100;
        }}
    </style>
</head>
<body>
    <div id="ui">
        <div>Score: <span id="score">0</span></div>
    </div>
    
    <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
    <script>
        // Scene setup
        const scene = new THREE.Scene();
        scene.background = new THREE.Color(0x1a1a2e);
        
        // Camera
        const camera = new THREE.PerspectiveCamera(
            75,
            window.innerWidth / window.innerHeight,
            0.1,
            1000
        );
        camera.position.set(0, 5, 10);
        camera.lookAt(0, 0, 0);
        
        // Renderer
        const renderer = new THREE.WebGLRenderer({{ antialias: true }});
        renderer.setSize(window.innerWidth, window.innerHeight);
        renderer.shadowMap.enabled = true;
        document.body.appendChild(renderer.domElement);
        
        // Lighting
        const ambientLight = new THREE.AmbientLight(0xffffff, 0.5);
        scene.add(ambientLight);
        
        const directionalLight = new THREE.DirectionalLight(0xffffff, 0.8);
        directionalLight.position.set(5, 10, 5);
        directionalLight.castShadow = true;
        scene.add(directionalLight);
        
        // Player (cube)
        const playerGeometry = new THREE.BoxGeometry(1, 1, 1);
        const playerMaterial = new THREE.MeshStandardMaterial({{ color: 0x4A90E2 }});
        const player = new THREE.Mesh(playerGeometry, playerMaterial);
        player.position.set(0, 1, 0);
        player.castShadow = true;
        scene.add(player);
        
        // Ground
        const groundGeometry = new THREE.PlaneGeometry(20, 20);
        const groundMaterial = new THREE.MeshStandardMaterial({{ color: 0x8B4513 }});
        const ground = new THREE.Mesh(groundGeometry, groundMaterial);
        ground.rotation.x = -Math.PI / 2;
        ground.receiveShadow = true;
        scene.add(ground);
        
        // Game state
        let score = 0;
        const keys = {{}};
        const clock = new THREE.Clock();
        
        // Input handling
        window.addEventListener('keydown', (e) => {{
            keys[e.key.toLowerCase()] = true;
        }});
        window.addEventListener('keyup', (e) => {{
            keys[e.key.toLowerCase()] = false;
        }});
        
        // Game loop
        function animate() {{
            requestAnimationFrame(animate);
            
            const deltaTime = Math.min(clock.getDelta(), 0.1);
            if (deltaTime <= 0 || !isFinite(deltaTime)) return;
            
            // Handle input
            if (keys['a'] || keys['arrowleft']) {{
                player.position.x -= 5 * deltaTime;
            }}
            if (keys['d'] || keys['arrowright']) {{
                player.position.x += 5 * deltaTime;
            }}
            if (keys['w'] || keys['arrowup']) {{
                player.position.z -= 5 * deltaTime;
            }}
            if (keys['s'] || keys['arrowdown']) {{
                player.position.z += 5 * deltaTime;
            }}
            if (keys[' ']) {{
                player.position.y += 5 * deltaTime;
            }}
            
            // Rotate player
            player.rotation.y += deltaTime;
            
            // Update camera to follow player
            camera.position.x = player.position.x;
            camera.position.z = player.position.z + 10;
            camera.lookAt(player.position);
            
            // Render
            renderer.render(scene, camera);
        }}
        
        // Handle resize
        window.addEventListener('resize', () => {{
            camera.aspect = window.innerWidth / window.innerHeight;
            camera.updateProjectionMatrix();
            renderer.setSize(window.innerWidth, window.innerHeight);
        }});
        
        // Start game
        animate();
    </script>
</body>
</html>"""
        
        return {
            'index.html': html_content
        }
    
    
    async def _generate_game_with_ai(
        self,
        project_path: Path,
        game_design: Dict,
        game_mechanics: Dict,
        deepseek_client,
        user_prompt: str = None,
        dimension: str = '2D'
    ):
        """Generate complete game from scratch using AI - HTML5 for 2D, Three.js for 3D"""
        
        if not deepseek_client:
            logger.error("DeepSeek client is None, cannot generate AI code")
            raise ValueError("DeepSeek client is required for AI code generation")
        
        dimension_upper = dimension.upper() if dimension else '2D'
        
        try:
            if dimension_upper == '3D':
                # Use Three.js generator for 3D games
                from services.ai_threejs_generator import AIThreeJSGenerator
                generator = AIThreeJSGenerator(deepseek_client)
                logger.info("Using Three.js generator for 3D game")
                files = await generator.generate_complete_game(game_design, game_mechanics, project_path, user_prompt)
            else:
                # Use HTML5 generator for 2D games
                from services.ai_html5_generator import AIHTML5Generator
                generator = AIHTML5Generator(deepseek_client)
                logger.info("Using HTML5 Canvas generator for 2D game")
                files = await generator.generate_complete_game(game_design, game_mechanics, project_path, user_prompt)
        except Exception as e:
            logger.error(f"AI code generation failed: {e}", exc_info=True)
            # Create fallback game based on dimension
            if dimension_upper == '3D':
                logger.info("📝 Creating fallback Three.js 3D game")
                files = self._create_fallback_threejs_game(game_design, game_mechanics)
            else:
                logger.info("📝 Creating fallback HTML5 2D game")
                files = self._create_fallback_html5_game(game_design, game_mechanics)
        
        # Write all files to project
        for file_path, content in files.items():
            try:
                full_path = project_path / file_path
                full_path.parent.mkdir(parents=True, exist_ok=True)
                full_path.write_text(content, encoding='utf-8')
                logger.debug(f"✅ Generated: {file_path}")
            except Exception as e:
                logger.error(f"❌ Failed to write {file_path}: {e}")
                # Continue with other files
        
        # Create assets directory (for HTML5, assets go in root/assets)
        assets_dir = project_path / "assets"
        assets_dir.mkdir(parents=True, exist_ok=True)
        
        manifest = {
            "player": None,
            "enemy": None,
            "collectible": None,
            "platform": None,
            "background": None,
            "ui": {}
        }
        
        manifest_path = assets_dir / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding='utf-8')
        
        logger.info(f"✅ Generated {len(files)} files with AI")
    
    async def _process_html5_game(self, project_path: Path) -> Dict:
        """Process HTML5 game - no build needed, just prepare for upload"""
        
        logger.info("📦 Processing HTML5 game...")
        
        # HTML5 games are already ready - just need to ensure index.html exists
        index_path = project_path / "index.html"
        
        if not index_path.exists():
            logger.error("❌ index.html not found!")
            raise FileNotFoundError("index.html not found in project")
        
        # Create dist directory (for consistency with upload process)
        dist_dir = project_path / "dist"
        dist_dir.mkdir(exist_ok=True)
        
        # Copy index.html to dist
        import shutil
        shutil.copy2(index_path, dist_dir / "index.html")
        
        # Copy assets if they exist
        assets_src = project_path / "assets"
        assets_dst = dist_dir / "assets"
        if assets_src.exists():
            if assets_dst.exists():
                shutil.rmtree(assets_dst)
            shutil.copytree(assets_src, assets_dst)
            logger.info("✅ Copied assets to dist/assets")
        
        logger.info("✅ HTML5 game processed (no build needed!)")
        return {
            "build_path": str(dist_dir),
            "success": True,
            "html5_game": True
        }
    
    
    async def _create_simple_html_game(self, project_path: Path) -> Dict:
        """Create a simple standalone HTML game when React build fails"""
        
        # Create a simple HTML file with embedded game
        html_content = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI Generated Game</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            overflow: hidden;
            background: #1a1a2e;
            font-family: Arial, sans-serif;
        }
        #gameCanvas {
            display: block;
            background: #16213e;
            cursor: crosshair;
        }
        #ui {
            position: absolute;
            top: 10px;
            left: 10px;
            color: #fff;
            font-size: 18px;
            z-index: 10;
        }
    </style>
</head>
<body>
    <div id="ui">
        <div>Score: <span id="score">0</span></div>
        <div style="font-size: 12px; margin-top: 5px;">WASD or Arrow Keys to move</div>
    </div>
    <canvas id="gameCanvas"></canvas>
    <script>
        const canvas = document.getElementById('gameCanvas');
        const ctx = canvas.getContext('2d');
        const scoreEl = document.getElementById('score');
        
        // Set canvas size
        canvas.width = window.innerWidth;
        canvas.height = window.innerHeight;
        
        // Game state
        let score = 0;
        const player = { x: 100, y: 300, width: 50, height: 50, vx: 0, vy: 0, onGround: false };
        const platforms = [
            { x: 0, y: canvas.height - 50, width: canvas.width, height: 50 },
            { x: 400, y: 500, width: 200, height: 20 },
            { x: 700, y: 400, width: 200, height: 20 }
        ];
        const collectibles = [
            { x: 300, y: 250, size: 20, collected: false },
            { x: 500, y: 250, size: 20, collected: false },
            { x: 800, y: 150, size: 20, collected: false }
        ];
        
        const keys = {};
        const gravity = 0.8;
        const jumpPower = 15;
        const speed = 5;
        
        // Input
        window.addEventListener('keydown', (e) => {
            keys[e.key.toLowerCase()] = true;
            if ((e.key === ' ' || e.key === 'w' || e.key === 'ArrowUp') && player.onGround) {
                player.vy = -jumpPower;
                player.onGround = false;
            }
        });
        window.addEventListener('keyup', (e) => {
            keys[e.key.toLowerCase()] = false;
        });
        
        // Game loop
        function update() {
            // Player movement
            if (keys['a'] || keys['arrowleft']) player.vx = -speed;
            else if (keys['d'] || keys['arrowright']) player.vx = speed;
            else player.vx *= 0.9;
            
            // Apply gravity
            player.vy += gravity;
            
            // Update position
            player.x += player.vx;
            player.y += player.vy;
            
            // Collision with platforms
            player.onGround = false;
            for (const platform of platforms) {
                if (player.x < platform.x + platform.width &&
                    player.x + player.width > platform.x &&
                    player.y < platform.y + platform.height &&
                    player.y + player.height > platform.y) {
                    if (player.vy > 0) {
                        player.y = platform.y - player.height;
                        player.vy = 0;
                        player.onGround = true;
                    }
                }
            }
            
            // Collectibles
            collectibles.forEach((col, i) => {
                if (!col.collected &&
                    player.x < col.x + col.size &&
                    player.x + player.width > col.x &&
                    player.y < col.y + col.size &&
                    player.y + player.height > col.y) {
                    col.collected = true;
                    score++;
                    scoreEl.textContent = score;
                }
            });
            
            // Keep player on screen
            if (player.x < 0) player.x = 0;
            if (player.x + player.width > canvas.width) player.x = canvas.width - player.width;
            if (player.y > canvas.height) {
                player.x = 100;
                player.y = 300;
                player.vx = 0;
                player.vy = 0;
            }
        }
        
        function render() {
            // Clear
            ctx.fillStyle = '#1a1a2e';
            ctx.fillRect(0, 0, canvas.width, canvas.height);
            
            // Draw platforms
            ctx.fillStyle = '#8B4513';
            platforms.forEach(p => {
                ctx.fillRect(p.x, p.y, p.width, p.height);
            });
            
            // Draw collectibles
            ctx.fillStyle = '#FFD700';
            collectibles.forEach(col => {
                if (!col.collected) {
                    ctx.beginPath();
                    ctx.arc(col.x + col.size/2, col.y + col.size/2, col.size/2, 0, Math.PI * 2);
                    ctx.fill();
                }
            });
            
            // Draw player
            ctx.fillStyle = '#4A90E2';
            ctx.fillRect(player.x, player.y, player.width, player.height);
        }
        
        function gameLoop() {
            update();
            render();
            requestAnimationFrame(gameLoop);
        }
        
        // Handle resize
        window.addEventListener('resize', () => {
            canvas.width = window.innerWidth;
            canvas.height = window.innerHeight;
        });
        
        // Start game
        gameLoop();
    </script>
</body>
</html>"""
        
        # Create dist directory and save HTML
        dist_dir = project_path / "dist"
        dist_dir.mkdir(exist_ok=True)
        index_path = dist_dir / "index.html"
        index_path.write_text(html_content)
        
        logger.info("✅ Created simple HTML fallback game")
        return {
            "build_path": str(dist_dir),
            "success": True,
            "simple_html": True
        }
    
    async def _create_deployment_package(
        self, 
        project_path: Path, 
        project_id: str
    ) -> Path:
        """Create ZIP package for deployment"""
        
        build_dir = project_path / "dist"
        if not build_dir.exists():
            build_dir = project_path
        
        package_path = self.projects_dir / f"{project_id}.zip"
        
        with zipfile.ZipFile(package_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(build_dir):
                for file in files:
                    file_path = Path(root) / file
                    arcname = file_path.relative_to(build_dir)
                    zipf.write(file_path, arcname)
        
        logger.info(f"✅ Created deployment package: {package_path}")
        return package_path
    
    async def _upload_to_storage(
        self, 
        storage_service: Any, 
        project_path: Path, 
        project_id: str,
        build_result: Dict = None
    ) -> Optional[str]:
        """Upload game files to Supabase Storage and return preview URL"""
        
        try:
            # Determine which directory to upload
            if build_result and build_result.get('build_path'):
                build_dir = Path(build_result['build_path'])
                if not build_dir.exists():
                    logger.warning(f"Build path doesn't exist: {build_dir}, trying alternatives")
                    build_dir = None
            else:
                build_dir = None
            
            # Try to find the correct build directory
            if not build_dir or not build_dir.exists():
                # Priority: dist > src > project root
                if (project_path / "dist").exists():
                    build_dir = project_path / "dist"
                    logger.info(f"📁 Using dist directory: {build_dir}")
                elif (project_path / "src").exists():
                    build_dir = project_path / "src"
                    logger.info(f"📁 Using src directory: {build_dir}")
                else:
                    build_dir = project_path
                    logger.warning(f"📁 Using project root as build directory: {build_dir}")
            
            if not build_dir.exists():
                logger.error(f"❌ No build directory found: {build_dir}")
                # Create a minimal index.html in project root as last resort
                logger.info("📝 Creating minimal index.html as last resort")
                minimal_html = """<!DOCTYPE html>
<html><head><title>Game</title></head>
<body><h1>Game Loading...</h1><p>Game files are being processed.</p></body>
</html>"""
                (project_path / "index.html").write_text(minimal_html)
                build_dir = project_path
            
            # Ensure index.html exists (create minimal one if missing)
            index_html = build_dir / "index.html"
            if not index_html.exists():
                logger.warning(f"⚠️  index.html not found in {build_dir}, creating minimal one")
                minimal_html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI Generated Game</title>
    <style>
        body { margin: 0; padding: 20px; background: #1a1a2e; color: #fff; font-family: Arial; }
        h1 { color: #4A90E2; }
    </style>
</head>
<body>
    <h1>🎮 Your Game is Loading...</h1>
    <p>Game files are being processed. Please wait a moment.</p>
    <p>If this message persists, the game may still be generating.</p>
</body>
</html>"""
                index_html.write_text(minimal_html, encoding='utf-8')
                logger.info(f"✅ Created minimal index.html at {index_html}")
            
            # Upload all files from build directory to Supabase
            uploaded_files = []
            failed_uploads = []
            
            for root, dirs, files in os.walk(build_dir):
                for file in files:
                    file_path = Path(root) / file
                    relative_path = file_path.relative_to(build_dir)
                    
                    # Skip node_modules and other build artifacts
                    if 'node_modules' in str(relative_path) or '.git' in str(relative_path):
                        continue
                    
                    try:
                        # Create storage path - ensure index.html goes to root
                        if relative_path.name == "index.html" and relative_path.parent == Path("."):
                            storage_path = f"web_games/{project_id}/index.html"
                        else:
                            storage_path = f"web_games/{project_id}/{relative_path.as_posix()}"
                        
                        # Determine content type
                        content_type = self._get_content_type(file_path)
                        
                        # Read and upload file
                        with open(file_path, 'rb') as f:
                            file_data = f.read()
                        
                        # Check file size (Supabase has limits)
                        max_size = 50 * 1024 * 1024  # 50MB
                        if len(file_data) > max_size:
                            logger.warning(f"⚠️  File too large to upload: {storage_path} ({len(file_data)} bytes)")
                            failed_uploads.append(storage_path)
                            continue
                        
                        # Upload to Supabase (public for web games)
                        await storage_service.upload_file(
                            storage_path,
                            file_data,
                            content_type=content_type,
                            public=True
                        )
                        uploaded_files.append(storage_path)
                        logger.debug(f"✅ Uploaded: {storage_path}")
                    except Exception as e:
                        logger.error(f"❌ Failed to upload {file_path}: {e}")
                        failed_uploads.append(str(relative_path))
                        # Continue with other files
                        continue
            
            if failed_uploads:
                logger.warning(f"⚠️  {len(failed_uploads)} files failed to upload: {failed_uploads[:5]}")
            
            if not uploaded_files:
                logger.error("❌ No files uploaded to Supabase!")
                return None
            
            # Verify index.html was uploaded
            index_uploaded = any('index.html' in f for f in uploaded_files)
            if not index_uploaded:
                logger.warning("⚠️  index.html was not uploaded! Trying to upload it now...")
                # Try to upload index.html directly
                index_path = build_dir / "index.html"
                if index_path.exists():
                    try:
                        with open(index_path, 'rb') as f:
                            index_data = f.read()
                        await storage_service.upload_file(
                            f"web_games/{project_id}/index.html",
                            index_data,
                            content_type='text/html',
                            public=True
                        )
                        logger.info("✅ Uploaded index.html directly")
                        index_uploaded = True
                    except Exception as e:
                        logger.error(f"❌ Failed to upload index.html: {e}")
            
            # Get public URL for index.html (preview URL)
            preview_url = _public_url_for(
                storage_service, f"web_games/{project_id}/index.html"
            )
            
            logger.info(f"✅ Uploaded {len(uploaded_files)} files to Supabase")
            if index_uploaded:
                logger.info(f"✅ Preview URL: {preview_url}")
            else:
                logger.warning(f"⚠️  Preview URL may not work (index.html not uploaded): {preview_url}")
            
            return preview_url
            
        except Exception as e:
            logger.error(f"Failed to upload to storage: {e}", exc_info=True)
            return None
    
    def _get_content_type(self, file_path: Path) -> str:
        """Get MIME type for file"""
        import mimetypes
        content_type, _ = mimetypes.guess_type(str(file_path))
        if not content_type:
            # Default content types
            if file_path.suffix == '.js':
                return 'application/javascript'
            elif file_path.suffix == '.css':
                return 'text/css'
            elif file_path.suffix == '.html':
                return 'text/html'
            elif file_path.suffix == '.json':
                return 'application/json'
            elif file_path.suffix == '.png':
                return 'image/png'
            elif file_path.suffix == '.jpg' or file_path.suffix == '.jpeg':
                return 'image/jpeg'
            elif file_path.suffix == '.svg':
                return 'image/svg+xml'
            else:
                return 'application/octet-stream'
        return content_type
    

