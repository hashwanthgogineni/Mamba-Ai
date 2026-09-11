import json
import re
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class AIThreeJSGenerator:
    # Generates Three.js 3D game code
    def __init__(self, deepseek_client):
        self.deepseek = deepseek_client
    
    async def generate_complete_game(
        self,
        game_design: Dict[str, Any],
        game_mechanics: Dict[str, Any],
        project_path: Any,
        user_prompt: str = None
    ) -> Dict[str, str]:
        # Generates complete Three.js 3D game
        
        logger.info("Generating complete Three.js 3D game with AI...")
        if user_prompt:
            logger.info(f"AI will interpret and create 3D game based on: {user_prompt[:100]}...")
        
        # Generate the complete HTML file with embedded 3D game
        html_content = await self._generate_threejs_game(game_design, game_mechanics, user_prompt)
        
        return {
            'index.html': html_content
        }
    
    async def _generate_threejs_game(self, game_design: Dict, game_mechanics: Dict, user_prompt: str = None) -> str:
        # Generates Three.js 3D game code with AI
        
        # If user_prompt is provided, let AI decide everything
        if user_prompt:
            initial_prompt = f"""You are an EXPERT Three.js/WebGL 3D game developer with 10+ years of experience. Generate a COMPLETE, POLISHED, PRODUCTION-READY Three.js 3D game based on the user's request.

USER REQUEST:
{user_prompt}

YOUR MISSION: CREATE A HIGH-QUALITY, FUN, WORKING 3D GAME
- Interpret the user's request and create a 3D game that matches their vision
- Decide on the game style, mechanics, levels, and features yourself
- The game MUST be playable, polished, and engaging
- Every mechanic must work perfectly
- Code must be clean, organized, and maintainable
- Game must feel responsive and satisfying
- NO broken features, NO placeholder code, NO errors

YOU DECIDE:
- Game genre (first-person shooter, racing, platformer, etc.)
- Game mechanics (movement, jumping, shooting, etc.)
- Level design and 3D layout
- Art style and colors
- Game features and objectives
- Scoring system
- Win/lose conditions
- Camera controls (first-person, third-person, etc.)
- Everything else needed for a complete 3D game

Make creative decisions that best match the user's request. Be creative and make the game fun!

CRITICAL REQUIREMENTS - READ EVERYTHING CAREFULLY:

1. HTML STRUCTURE:
   - MUST start with <!DOCTYPE html>
   - MUST include complete <html>, <head>, <body> tags
   - Title tag: <title>Your 3D Game Title</title>
   - Viewport meta: <meta name="viewport" content="width=device-width, initial-scale=1.0">

2. CSS STYLING:
   - Reset styles: * {{ margin: 0; padding: 0; box-sizing: border-box; }}
   - Body: overflow: hidden; background: #000; font-family: Arial, sans-serif;
   - Canvas: display: block; width: 100vw; height: 100vh;
   - UI overlay: position: absolute; top: 20px; left: 20px; color: white; z-index: 100;

3. THREE.JS SETUP (CRITICAL - REQUIRED):
   - MUST include this EXACT line in <head> section:
     <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
   - OR use import map for ES modules (if using modules)
   - This MUST be present - the game will NOT work without it
   - Load BEFORE any game script that uses Three.js
   - Verify Three is loaded: if (typeof THREE === 'undefined') {{ console.error('Three.js not loaded!'); }}

4. CANVAS SETUP:
   - Create canvas element: <canvas id="gameCanvas"></canvas>
   - OR create canvas programmatically with Three.js renderer
   - Set size: renderer.setSize(window.innerWidth, window.innerHeight);
   - Handle resize: window.addEventListener('resize', onWindowResize);

5. THREE.JS SCENE SETUP (CRITICAL):
   - Create scene: const scene = new THREE.Scene();
   - Create camera: const camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 1000);
   - Create renderer: const renderer = new THREE.WebGLRenderer({{ antialias: true }});
   - Set background: scene.background = new THREE.Color(0x1a1a2e);
   - Add renderer to DOM: document.body.appendChild(renderer.domElement);
   - Set camera position: camera.position.set(0, 5, 10);

6. GAME LOOP (CRITICAL - NO DIVISION BY ZERO):
   - MUST use requestAnimationFrame
   - Structure: function animate() {{
       requestAnimationFrame(animate);
       const deltaTime = clock.getDelta();
       if (deltaTime <= 0 || !isFinite(deltaTime)) return; // Skip invalid frames
       update(deltaTime);
       renderer.render(scene, camera);
     }}
   - Use Clock for deltaTime: const clock = new THREE.Clock();
   - ALWAYS cap deltaTime: Math.min(clock.getDelta(), 0.1)
   - ALWAYS check deltaTime > 0 AND isFinite(deltaTime) before using it
   - NEVER divide by deltaTime without checking: if (deltaTime > 0) {{ value = x / deltaTime; }}
   - NEVER divide by zero: ALWAYS check denominator > 0 before any division
   - Start loop: animate();

7. INPUT HANDLING:
   - Track keys: const keys = {{}};
   - keydown: keys[e.key.toLowerCase()] = true;
   - keyup: keys[e.key.toLowerCase()] = false;
   - Support: WASD, Arrow keys, Space, Mouse for camera controls

8. CAMERA CONTROLS:
   - For first-person: Use OrbitControls or PointerLockControls
   - Include OrbitControls: <script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/controls/OrbitControls.js"></script>
   - Setup: const controls = new THREE.OrbitControls(camera, renderer.domElement);
   - Update in loop: controls.update();
   - OR implement custom camera controls based on game needs

9. 3D OBJECTS & GEOMETRY:
   - Create geometries: new THREE.BoxGeometry(), new THREE.SphereGeometry(), etc.
   - Create materials: new THREE.MeshStandardMaterial({{ color: 0x00ff00 }})
   - Create meshes: new THREE.Mesh(geometry, material)
   - Add to scene: scene.add(mesh)
   - Use proper lighting: AmbientLight, DirectionalLight, PointLight

10. LIGHTING (CRITICAL FOR 3D):
    - Ambient light: const ambientLight = new THREE.AmbientLight(0xffffff, 0.5); scene.add(ambientLight);
    - Directional light: const directionalLight = new THREE.DirectionalLight(0xffffff, 0.8); scene.add(directionalLight);
    - Point lights for dynamic lighting
    - Shadows: renderer.shadowMap.enabled = true; renderer.shadowMap.type = THREE.PCFSoftShadowMap;

11. PHYSICS (OPTIONAL BUT RECOMMENDED):
    - Use Cannon.js or Rapier.js for 3D physics
    - Cannon.js: <script src="https://cdnjs.cloudflare.com/ajax/libs/cannon.js/0.20.0/cannon.min.js"></script>
    - Setup world: const world = new CANNON.World();
    - Update in loop: world.step(1/60);
    - OR implement simple custom physics

12. CODE QUALITY & CORRECTNESS (CRITICAL):
    - DIVISION BY ZERO PROTECTION: Every division MUST check denominator first
      Example: if (deltaTime > 0 && isFinite(deltaTime)) {{ speed = distance / deltaTime; }}
      Example: if (value !== 0) {{ result = x / value; }}
    - NEVER write: x / 0, x / deltaTime (without check), or any division without guard
    - Use proper JavaScript ES6+ syntax
    - Handle edge cases (player out of bounds, division by zero, etc.)
    - NO syntax errors - test every bracket, brace, parenthesis

FINAL CHECKLIST:
1. Three.js CDN script tag is in <head>
2. Scene, camera, and renderer are created
3. Game loop uses requestAnimationFrame
4. Clock is used for deltaTime
5. All HTML tags are properly closed
6. All JavaScript brackets/braces/parentheses are balanced
7. Lighting is set up (game will be dark without it)
8. Camera controls are implemented
9. Game is playable and fun!

Generate complete, working Three.js 3D game code. Make it fun and engaging!
"""
        else:
            # Fallback to structured approach if no user prompt
            genre = game_design.get('genre', 'platformer')
            title = game_design.get('title', 'AI Generated 3D Game')
            
            initial_prompt = f"""You are an EXPERT Three.js/WebGL 3D game developer. Generate a COMPLETE, POLISHED, PRODUCTION-READY Three.js 3D game.

MISSION: CREATE A HIGH-QUALITY, FUN, WORKING 3D GAME
- The game MUST be playable, polished, and engaging
- Every mechanic must work perfectly
- Code must be clean, organized, and maintainable
- Game must feel responsive and satisfying
- NO broken features, NO placeholder code, NO errors

GAME SPECIFICATIONS:
Title: {title}
Genre: {genre}
Game Design: {json.dumps(game_design, indent=2)}
Game Mechanics: {json.dumps(game_mechanics, indent=2)}

[Include all the same critical requirements as above...]

Generate complete, working Three.js 3D game code. Make it fun and engaging!
"""
        
        return await self._generate_with_validation(
            initial_prompt,
            "index.html",
            "Three.js 3D game",
            game_design,
            game_mechanics
        )
    
    async def _generate_with_validation(
        self,
        initial_prompt: str,
        file_name: str,
        component_type: str,
        game_design: Dict,
        game_mechanics: Dict,
        max_retries: int = 3
    ) -> str:
        # Generates code with validation and retry logic
        messages = [{"role": "user", "content": initial_prompt}]
        last_code = None
        last_errors = []
        
        for attempt in range(max_retries):
            try:
                logger.info(f"Generating {component_type} (attempt {attempt + 1}/{max_retries})...")
                
                # Low temperature for consistent, high-quality code.
                # V4.1-Flash allows up to 384K output. Thinking mode spends
                # part of this budget on reasoning before writing any code,
                # so the cap has to cover both the reasoning and the game.
                response = await self.deepseek.generate(messages, temperature=0.05, max_tokens=65536)
                content = response.get('content', '')
                
                # Check for empty content
                if not content or not content.strip():
                    logger.warning(f"Empty content from DeepSeek for {component_type}")
                    if attempt < max_retries - 1:
                        improved_prompt = f"""{initial_prompt}

CRITICAL: The previous attempt returned empty content. Please generate complete HTML code this time."""
                        messages = [{"role": "user", "content": improved_prompt}]
                        continue
                    raise ValueError("Empty content from DeepSeek API")
                
                # Extract HTML from markdown if present
                code = self._extract_html_from_markdown(content)
                
                if not code or not code.strip():
                    logger.warning("Empty code generated, retrying...")
                    if attempt < max_retries - 1:
                        improved_prompt = f"""{initial_prompt}

IMPORTANT: The previous attempt returned empty code. Please generate complete HTML code this time."""
                        messages = [{"role": "user", "content": improved_prompt}]
                        continue
                    raise ValueError("Empty code generated")
                
                # Basic validation - only check for critical syntax errors
                basic_errors = self._basic_validation(code)
                if basic_errors:
                    logger.warning(f"Found {len(basic_errors)} basic issues:")
                    for error in basic_errors[:3]:
                        logger.warning(f"   - {error}")
                    # Only retry on critical structural errors (unclosed tags)
                    if any('tag' in e.lower() or 'script' in e.lower() for e in basic_errors) and attempt < max_retries - 1:
                        logger.info(f"Retrying due to structural errors...")
                        continue
                
                # Final validation check - check if game is broken
                if not basic_errors:
                    final_issues = self._check_game_issues(code)
                    if final_issues and attempt < max_retries - 1:
                        logger.warning(f"Found {len(final_issues)} issues in generated game:")
                        for issue in final_issues[:3]:
                            logger.warning(f"   - {issue}")
                        fix_prompt = self._create_fix_prompt(initial_prompt, code, final_issues)
                        messages = [{"role": "user", "content": fix_prompt}]
                        logger.info(f"Retrying with fix prompt to address issues...")
                        continue
                
                # Code looks good - return it
                logger.info(f"{component_type} generated successfully")
                return code
                        
            except Exception as e:
                logger.warning(f"Generation attempt {attempt + 1} failed: {e}")
                if attempt == max_retries - 1:
                    raise
        
        raise ValueError(f"Failed to generate {component_type}")
    
    def _extract_html_from_markdown(self, content: str) -> str:
        # Extracts HTML from markdown code blocks
        if not content or not content.strip():
            return ""
        
        try:
            # Try html first
            if "```html" in content:
                parts = content.split("```html", 1)
                if len(parts) >= 2:
                    code_part = parts[1]
                    if "```" in code_part:
                        code_part = code_part.split("```", 1)[0]
                    return code_part.strip()
            
            # Try generic code blocks
            if "```" in content:
                parts = content.split("```")
                if len(parts) >= 3:
                    # Get the code part (usually index 1)
                    code_part = parts[1]
                    # Skip language identifier if present
                    if code_part.startswith("html") or code_part.startswith("HTML"):
                        code_part = code_part[4:].strip()
                    return code_part.strip()
            
            # No markdown, return as-is
            return content.strip()
        except Exception as e:
            logger.warning(f"Error extracting HTML from markdown: {e}")
            return content.strip()
    
    def _basic_validation(self, code: str) -> List[str]:
        # Basic validation for critical syntax errors
        errors = []
        code_lower = code.lower()
        
        # Check for unclosed HTML tags
        script_count = code.count("<script")
        script_close_count = code.count("</script>")
        if script_count != script_close_count:
            errors.append(f"Unbalanced script tags: {script_count} open, {script_close_count} close")
        
        # Check for basic HTML structure
        if not code.strip().startswith("<!doctype"):
            errors.append("Missing DOCTYPE declaration")
        
        return errors
    
    def _check_game_issues(self, code: str) -> List[str]:
        # Checks for critical issues in generated 3D game code
        issues = []
        code_lower = code.lower()
        
        # Check for critical missing components
        if "three.js" not in code_lower and "three" not in code_lower:
            issues.append("Three.js library not included - 3D rendering will not work")
        
        if "requestanimationframe" not in code_lower:
            issues.append("Game loop missing (no requestAnimationFrame) - game will not run")
        
        if "scene" not in code_lower or "new three.scene" not in code_lower:
            issues.append("Three.js scene not created - game cannot render")
        
        if "camera" not in code_lower or "perspectivecamera" not in code_lower:
            issues.append("Three.js camera not initialized - game cannot render")
        
        if "renderer" not in code_lower or "webglrenderer" not in code_lower:
            issues.append("Three.js renderer not initialized - game cannot render")
        
        # Check for syntax errors
        open_braces = code.count('{')
        close_braces = code.count('}')
        if open_braces != close_braces:
            issues.append(f"Unbalanced JavaScript braces: {open_braces} open, {close_braces} close")
        
        open_parens = code.count('(')
        close_parens = code.count(')')
        if open_parens != close_parens:
            issues.append(f"Unbalanced parentheses: {open_parens} open, {close_parens} close")
        
        return issues
    
    def _create_fix_prompt(self, original_prompt: str, broken_code: str, issues: List[str]) -> str:
        # Creates fix prompt for issues found in code
        issues_text = "\n".join([f"- {issue}" for issue in issues[:5]])
        
        return f"""{original_prompt}

ISSUES FOUND IN GENERATED CODE:
{issues_text}

Please fix these issues and regenerate the complete HTML code. The 3D game must work properly.
Make sure to:
1. Include Three.js library (CDN link)
2. Initialize scene, camera, and renderer properly
3. Fix any syntax errors (unbalanced braces, parentheses, etc.)
4. Ensure the game loop is working with requestAnimationFrame
5. Add proper lighting (game will be dark without it)
6. Test that the game will run without errors

Return the complete fixed HTML code."""

