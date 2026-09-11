import json
import re
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class AIHTML5Generator:
    # Generates HTML5 Canvas game code
    def __init__(self, deepseek_client):
        self.deepseek = deepseek_client
    
    async def generate_complete_game(
        self,
        game_design: Dict[str, Any],
        game_mechanics: Dict[str, Any],
        project_path: Any,
        user_prompt: str = None
    ) -> Dict[str, str]:
        # Generates complete HTML5 game from scratch
        
        logger.info("Generating complete HTML5 Canvas game with AI...")
        if user_prompt:
            logger.info(f"AI will interpret and create game based on: {user_prompt[:100]}...")
        
        # Generate the complete HTML file with embedded game
        html_content = await self._generate_html_game(game_design, game_mechanics, user_prompt)
        
        return {
            'index.html': html_content
        }
    
    async def _generate_html_game(self, game_design: Dict, game_mechanics: Dict, user_prompt: str = None) -> str:
        # Generates HTML5 game code with AI
        
        # If user_prompt is provided, let AI decide everything
        if user_prompt:
            initial_prompt = f"""You are an EXPERT HTML5 Canvas game developer with 10+ years of experience. Generate a COMPLETE, POLISHED, PRODUCTION-READY HTML5 Canvas game based on the user's request.

USER REQUEST:
{user_prompt}

YOUR MISSION: CREATE A HIGH-QUALITY, FUN, WORKING GAME
- Interpret the user's request and create a game that matches their vision
- Decide on the game style, mechanics, levels, and features yourself
- The game MUST be playable, polished, and engaging
- Every mechanic must work perfectly
- Code must be clean, organized, and maintainable
- Game must feel responsive and satisfying
- NO broken features, NO placeholder code, NO errors

YOU DECIDE:
- Game genre (platformer, shooter, puzzle, etc.)
- Game mechanics (movement, jumping, shooting, etc.)
- Level design and layout
- Art style and colors
- Game features and objectives
- Scoring system
- Win/lose conditions
- Everything else needed for a complete game

Make creative decisions that best match the user's request. Be creative and make the game fun!

CRITICAL REQUIREMENTS - READ EVERYTHING CAREFULLY:

1. HTML STRUCTURE:
   - MUST start with <!DOCTYPE html>
   - MUST include complete <html>, <head>, <body> tags
   - Title tag: <title>Your Game Title</title>
   - Viewport meta: <meta name="viewport" content="width=device-width, initial-scale=1.0">

2. CSS STYLING:
   - Reset styles: * {{ margin: 0; padding: 0; box-sizing: border-box; }}
   - Body: overflow: hidden; background: #1a1a2e; font-family: Arial, sans-serif;
   - Canvas: display: block; width: 100vw; height: 100vh;
   - UI overlay: position: absolute; top: 20px; left: 20px; color: white; z-index: 100;

3. MATTER.JS SETUP (CRITICAL - REQUIRED):
   - MUST include this EXACT line in <head> section:
     <script src="https://cdnjs.cloudflare.com/ajax/libs/matter-js/0.19.0/matter.min.js"></script>
   - This MUST be present - the game will NOT work without it
   - Load BEFORE any game script that uses Matter.js
   - Use destructuring: const {{ Engine, Render, World, Bodies, Body, Events }} = Matter;
   - Verify Matter is loaded: if (typeof Matter === 'undefined') {{ console.error('Matter.js not loaded!'); }}

4. CANVAS SETUP:
   - Create canvas element: <canvas id="gameCanvas"></canvas>
   - Get context: const canvas = document.getElementById('gameCanvas'); const ctx = canvas.getContext('2d');
   - Set size: canvas.width = window.innerWidth; canvas.height = window.innerHeight;
   - Handle resize: window.addEventListener('resize', () => {{ canvas.width = window.innerWidth; canvas.height = window.innerHeight; }});

5. GAME LOOP (CRITICAL - NO DIVISION BY ZERO):
   - MUST use requestAnimationFrame
   - Structure: function gameLoop(currentTime) {{
       const deltaTime = Math.min((currentTime - lastTime) / 1000, 0.1);
       lastTime = currentTime;
       if (deltaTime <= 0 || !isFinite(deltaTime)) return; // Skip invalid frames
       update(deltaTime);
       render();
       requestAnimationFrame(gameLoop);
     }}
   - ALWAYS cap deltaTime: Math.min((currentTime - lastTime) / 1000, 0.1)
   - ALWAYS check deltaTime > 0 AND isFinite(deltaTime) before using it
   - NEVER divide by deltaTime without checking: if (deltaTime > 0) {{ value = x / deltaTime; }}
   - NEVER divide by zero: ALWAYS check denominator > 0 before any division
   - For all divisions, use: if (denominator !== 0 && isFinite(denominator)) {{ result = numerator / denominator; }}
   - Start loop: gameLoop(performance.now());

6. CODE QUALITY & CORRECTNESS (CRITICAL):
   - DIVISION BY ZERO PROTECTION: Every division MUST check denominator first
     Example: if (deltaTime > 0 && isFinite(deltaTime)) {{ speed = distance / deltaTime; }}
     Example: if (value !== 0) {{ result = x / value; }}
   - NEVER write: x / 0, x / deltaTime (without check), or any division without guard
   - Use proper JavaScript ES6+ syntax
   - Handle edge cases (player out of bounds, division by zero, etc.)
   - NO syntax errors - test every bracket, brace, parenthesis

FINAL CHECKLIST:
1. ✅ Matter.js CDN script tag is in <head>
2. ✅ Matter.js engine is created and updated in game loop
3. ✅ Game loop uses requestAnimationFrame
4. ✅ All HTML tags are properly closed
5. ✅ All JavaScript brackets/braces/parentheses are balanced
6. ✅ Game is playable and fun!

Generate complete, working HTML5 Canvas game code. Make it fun and engaging!
"""
        else:
            # Fallback to structured approach if no user prompt
            genre = game_design.get('genre', 'platformer')
            title = game_design.get('title', 'AI Generated Game')
            
            # Validate and sanitize mechanics before generating code
            validated_mechanics = self._validate_and_fix_mechanics(game_mechanics)
            
            level_design = game_design.get('level_design', {})
            levels = level_design.get('levels', [])
            
            initial_prompt = f"""You are an EXPERT HTML5 Canvas game developer with 10+ years of experience. Generate a COMPLETE, POLISHED, PRODUCTION-READY HTML5 Canvas game.

MISSION: CREATE A HIGH-QUALITY, FUN, WORKING GAME
- The game MUST be playable, polished, and engaging
- Every mechanic must work perfectly
- Code must be clean, organized, and maintainable
- Game must feel responsive and satisfying
- NO broken features, NO placeholder code, NO errors

GAME SPECIFICATIONS:
Title: {title}
Genre: {genre}
Game Design: {json.dumps(game_design, indent=2)}
Game Mechanics (VALIDATED): {json.dumps(validated_mechanics, indent=2)}
Level Design: {json.dumps(level_design, indent=2) if level_design else 'Not provided'}

CRITICAL VALUES - USE THESE EXACT NUMBERS:
- Player Speed: {validated_mechanics.get('player_movement', {}).get('speed', 300.0)} pixels/second
- Jump Force: {validated_mechanics.get('player_movement', {}).get('jump_force', -400.0)} (NEGATIVE = upward)
- Gravity: {validated_mechanics.get('physics', {}).get('gravity', 0.8)} pixels/frame²
- FPS: {validated_mechanics.get('game_loop', {}).get('fps', 60)} frames per second
- Acceleration: {validated_mechanics.get('player_movement', {}).get('acceleration', 1500.0)}
- Friction: {validated_mechanics.get('player_movement', {}).get('friction', 1200.0)}

CRITICAL REQUIREMENTS - READ EVERYTHING CAREFULLY:

1. HTML STRUCTURE:
   - MUST start with <!DOCTYPE html>
   - MUST include complete <html>, <head>, <body> tags
   - Title tag: <title>{title}</title>
   - Viewport meta: <meta name="viewport" content="width=device-width, initial-scale=1.0">

2. CSS STYLING:
   - Reset styles: * {{ margin: 0; padding: 0; box-sizing: border-box; }}
   - Body: overflow: hidden; background: #1a1a2e; font-family: Arial, sans-serif;
   - Canvas: display: block; width: 100vw; height: 100vh;
   - UI overlay: position: absolute; top: 20px; left: 20px; color: white; z-index: 100;

3. MATTER.JS SETUP (CRITICAL - REQUIRED):
   - MUST include this EXACT line in <head> section:
     <script src="https://cdnjs.cloudflare.com/ajax/libs/matter-js/0.19.0/matter.min.js"></script>
   - This MUST be present - the game will NOT work without it
   - Load BEFORE any game script that uses Matter.js
   - Use destructuring: const {{ Engine, Render, World, Bodies, Body, Events }} = Matter;
   - Verify Matter is loaded: if (typeof Matter === 'undefined') {{ console.error('Matter.js not loaded!'); }}

4. CANVAS SETUP:
   - Create canvas element: <canvas id="gameCanvas"></canvas>
   - Get context: const canvas = document.getElementById('gameCanvas'); const ctx = canvas.getContext('2d');
   - Set size: canvas.width = window.innerWidth; canvas.height = window.innerHeight;
   - Handle resize: window.addEventListener('resize', () => {{ canvas.width = window.innerWidth; canvas.height = window.innerHeight; }});

5. GAME LOOP (CRITICAL - NO DIVISION BY ZERO):
   - MUST use requestAnimationFrame
   - Structure: function gameLoop(currentTime) {{
       const deltaTime = Math.min((currentTime - lastTime) / 1000, 0.1);
       lastTime = currentTime;
       if (deltaTime <= 0 || !isFinite(deltaTime)) return; // Skip invalid frames
       update(deltaTime);
       render();
       requestAnimationFrame(gameLoop);
     }}
   - ALWAYS cap deltaTime: Math.min((currentTime - lastTime) / 1000, 0.1)
   - ALWAYS check deltaTime > 0 AND isFinite(deltaTime) before using it
   - NEVER divide by deltaTime without checking: if (deltaTime > 0) {{ value = x / deltaTime; }}
   - NEVER divide by zero: ALWAYS check denominator > 0 before any division
   - For all divisions, use: if (denominator !== 0 && isFinite(denominator)) {{ result = numerator / denominator; }}
   - Start loop: gameLoop(performance.now());

6. INPUT HANDLING:
   - Track keys: const keys = {{}};
   - keydown: keys[e.key.toLowerCase()] = true;
   - keyup: keys[e.key.toLowerCase()] = false;
   - Support: WASD, Arrow keys, Space

7. PHYSICS (CRITICAL - REQUIRED - VERIFY THIS IS IN YOUR CODE):
   - MUST create Matter.js engine: const engine = Engine.create();
   - MUST update engine in game loop: Engine.update(engine);
   - This MUST be called every frame in the game loop
   - Create bodies with Bodies.rectangle() or Bodies.circle()
   - Add to world: World.add(world, body);
   - Example game loop structure (COPY THIS PATTERN):
     function gameLoop() {{
       Engine.update(engine);  // MUST be called every frame - DO NOT FORGET THIS
       // ... rest of game logic
       requestAnimationFrame(gameLoop);
     }}
   - VERIFY: Search your code for "Engine.update" - it MUST be inside the game loop function
   - VERIFY: Search your code for "Engine.create" or "engine = Engine.create" - it MUST exist

8. GAME FEATURES (MUST implement based on genre and level design):
   - Player character: Responsive controls, smooth movement, proper physics
   - Enemies: AI behavior, collision, proper placement from level design
   - Collectibles: Spawn at level design positions, collision detection, score updates
   - Platforms: Use EXACT positions from level design, proper collision
   - Score system: Real-time updates, persistent display, clear feedback
   - Collision detection: Precise, responsive, handles all entity types
   - Level progression: Use level design data, implement level switching
   - Win/lose conditions: Clear game over states, restart functionality
   - Visual feedback: Particle effects, screen shake, animations
   - Audio feedback: Sound effects for actions (optional, can use console.log for now)

9. CODE QUALITY & CORRECTNESS (CRITICAL):
   - Use proper JavaScript ES6+ syntax
   - Organize code in classes or functions
   - Add comments for complex logic
   - Handle edge cases (player out of bounds, division by zero, etc.)
   - NO syntax errors - test every bracket, brace, parenthesis
   - All brackets, braces, parentheses MUST be balanced
   - All variables MUST be declared before use
   - All functions MUST be called correctly
   - All physics calculations MUST be correct
   - DIVISION BY ZERO PROTECTION: Every division MUST check denominator first
     Example: if (deltaTime > 0 && isFinite(deltaTime)) {{ speed = distance / deltaTime; }}
     Example: if (value !== 0) {{ result = x / value; }}
   - NEVER write: x / 0, x / deltaTime (without check), or any division without guard

10. GAME LOGIC CORRECTNESS (CRITICAL - VERIFY EACH):
    - Player movement: Use EXACT speed {validated_mechanics.get('player_movement', {}).get('speed', 300.0)} pixels/second
    - Jump: Use EXACT jump force {validated_mechanics.get('player_movement', {}).get('jump_force', -400.0)} (negative = up)
    - Gravity: Apply {validated_mechanics.get('physics', {}).get('gravity', 0.8)} every frame
    - Acceleration: {validated_mechanics.get('player_movement', {}).get('acceleration', 1500.0)} for smooth movement
    - Friction: {validated_mechanics.get('player_movement', {}).get('friction', 1200.0)} for natural stopping
    - Collision: Matter.js collision events, proper callbacks, handle all entity types
    - Score: Update immediately on collectible pickup, display prominently
    - Game loop: 60 FPS with requestAnimationFrame, delta time for consistency
    - Input: Immediate response, no lag, support WASD + Arrow keys + Space
    - Physics: Matter.js Engine.update() every frame, proper body creation
    - Level data: Use level design positions for platforms, enemies, collectibles
    - Boundaries: Prevent player from going off-screen, wrap or clamp position
    - Game state: Proper initialization, cleanup on restart, state management

11. RENDERING:
    - Clear canvas: ctx.fillStyle = '#1a1a2e'; ctx.fillRect(0, 0, canvas.width, canvas.height);
    - Draw shapes: ctx.fillRect(), ctx.arc(), ctx.drawImage()
    - Use colors from game design
    - Render in correct order: background → platforms → collectibles → enemies → player → UI

12. TESTING REQUIREMENTS:
    - Before returning code, mentally test:
      * Does the game start without errors?
      * Can the player move left/right?
      * Can the player jump?
      * Do collisions work?
      * Does the score update?
      * Is the game loop running?
    - If ANY of these fail, fix the code before returning

CRITICAL SYNTAX RULES:
- All JavaScript code must be inside <script> tags
- No React, no JSX, no imports/exports
- Pure vanilla JavaScript only
- All code must be valid JavaScript
- No TypeScript syntax
- Use const/let, not var
- Use arrow functions where appropriate

OUTPUT FORMAT:
- Return ONLY the complete HTML code
- NO markdown code blocks (no ```html or ```)
- NO explanations before or after
- NO comments outside the HTML
- Just the raw HTML code starting with <!DOCTYPE html>

FINAL CHECKLIST:
1. ✅ Matter.js CDN script tag is in <head>
2. ✅ Matter.js engine is created and updated in game loop
3. ✅ Game loop uses requestAnimationFrame
4. ✅ All HTML tags are properly closed
5. ✅ All JavaScript brackets/braces/parentheses are balanced
6. ✅ Game is playable and fun!

Generate complete, working HTML5 Canvas game code. Make it fun and engaging!
"""

        return await self._generate_with_validation(
            initial_prompt,
            "index.html",
            "HTML5 Canvas game",
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
                if attempt == max_retries - 1 or not basic_errors:
                    # Last attempt or no basic errors - do final validation
                    final_issues = self._check_game_issues(code)
                    if final_issues and attempt < max_retries - 1:
                        logger.warning(f"Found {len(final_issues)} issues in generated game, fixing...")
                        fix_prompt = self._create_fix_prompt(initial_prompt, code, final_issues)
                        messages = [{"role": "user", "content": fix_prompt}]
                        logger.info(f"Retrying with fix prompt...")
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
                    code_part = parts[1].strip()
                    # Remove language identifier if present
                    if code_part.lower().startswith(("html", "htm")):
                        lines = code_part.split("\n")
                        if len(lines) > 1:
                            code_part = "\n".join(lines[1:])
                        else:
                            code_part = ""
                    return code_part.strip()
                elif len(parts) >= 2:
                    code_part = parts[1].strip()
                    if code_part.lower().startswith(("html", "htm")):
                        lines = code_part.split("\n")
                        if len(lines) > 1:
                            code_part = "\n".join(lines[1:])
                        else:
                            code_part = ""
                    return code_part.strip()
            
            # Check if it's already HTML (starts with <!DOCTYPE or <html)
            content_stripped = content.strip()
            if content_stripped.startswith("<!DOCTYPE") or content_stripped.startswith("<html"):
                return content_stripped
            
            # No code blocks found, return content as-is
            return content.strip()
            
        except (IndexError, AttributeError, ValueError) as e:
            logger.error(f"Error extracting HTML: {e}")
            logger.debug(f"Content preview: {content[:500] if content else 'None'}")
            # Try to return as-is if it looks like HTML
            if content and ("<!DOCTYPE" in content or "<html" in content):
                return content.strip()
            return ""
    
    def _validate_and_fix_mechanics(self, game_mechanics: Dict) -> Dict:
        # Validates and fixes game mechanics
        validated = game_mechanics.copy() if game_mechanics else {}
        
        # Ensure player_movement exists and is valid
        player_movement = validated.get('player_movement', {})
        if not player_movement:
            player_movement = {}
        speed = player_movement.get('speed', 0)
        if speed <= 0 or speed > 1000:
            player_movement['speed'] = 300.0 if speed <= 0 else min(600.0, speed)
        jump_force = player_movement.get('jump_force', 0)
        if jump_force == 0 or jump_force > 0:
            player_movement['jump_force'] = -400.0 if jump_force == 0 else -abs(jump_force)
        elif jump_force < -800:
            player_movement['jump_force'] = -600.0
        elif jump_force > -100:
            player_movement['jump_force'] = -200.0
        validated['player_movement'] = player_movement
        
        # Ensure physics exists and is valid
        physics = validated.get('physics', {})
        if not physics:
            physics = {}
        gravity = physics.get('gravity', 0)
        if gravity <= 0 or gravity > 5:
            physics['gravity'] = 0.8 if gravity <= 0 else min(2.0, gravity)
        if 'friction' not in physics:
            physics['friction'] = 0.1
        validated['physics'] = physics
        
        # Ensure game_loop exists
        if 'game_loop' not in validated:
            validated['game_loop'] = {'fps': 60, 'use_requestAnimationFrame': True}
        
        # Ensure scoring exists
        if 'scoring' not in validated:
            validated['scoring'] = {'points_per_collectible': 10, 'points_per_enemy': 50}
        
        # Ensure collision exists
        if 'collision' not in validated:
            validated['collision'] = {'enabled': True, 'type': 'aabb'}
        
        return validated
    
    def _validate_html_code_basic(self, code: str) -> Dict[str, Any]:
        # Basic validation for critical structural issues
        errors = []
        warnings = []
        code_lower = code.lower()
        
        # Only check for critical structural issues
        if not code or not code.strip():
            errors.append("Empty code")
            return {"is_valid": False, "errors": errors, "warnings": warnings}
        
        # Check for basic HTML structure
        if "<!doctype html>" not in code_lower and "<html" not in code_lower:
            errors.append("Missing HTML structure")
        
        # Check for balanced script tags (critical)
        script_count = code.count("<script")
        script_close_count = code.count("</script>")
        if script_count != script_close_count:
            errors.append(f"Unbalanced script tags: {script_count} open, {script_close_count} close")
        
        # Check for balanced brackets/braces (critical)
        open_braces = code.count("{")
        close_braces = code.count("}")
        if open_braces != close_braces:
            errors.append(f"Unbalanced braces: {open_braces} open, {close_braces} close")
        
        open_parens = code.count("(")
        close_parens = code.count(")")
        if open_parens != close_parens:
            errors.append(f"Unbalanced parentheses: {open_parens} open, {close_parens} close")
        
        is_valid = len(errors) == 0
        return {
            "is_valid": is_valid,
            "errors": errors,
            "warnings": warnings
        }
    
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
        """
        Check if the generated game has critical issues that would break it
        Returns list of issues found
        """
        issues = []
        code_lower = code.lower()
        
        # Check for critical missing components
        if "matter-js" not in code_lower and "matter.js" not in code_lower:
            issues.append("Matter.js library not included - physics will not work")
        
        if "requestanimationframe" not in code_lower:
            issues.append("Game loop missing (no requestAnimationFrame) - game will not run")
        
        if "<canvas" not in code_lower:
            issues.append("Canvas element missing - game cannot render")
        
        if "getcontext" not in code_lower:
            issues.append("Canvas context not initialized - game cannot draw")
        
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
        """
        Create a prompt to fix specific issues found in the generated code
        """
        issues_text = "\n".join([f"- {issue}" for issue in issues[:5]])
        
        return f"""{original_prompt}

🚨 ISSUES FOUND IN GENERATED CODE:
{issues_text}

Please fix these issues and regenerate the complete HTML code. The game must work properly.
Make sure to:
1. Include all required libraries (Matter.js if needed)
2. Initialize all components properly
3. Fix any syntax errors (unbalanced braces, parentheses, etc.)
4. Ensure the game loop is working
5. Test that the game will run without errors

Return the complete fixed HTML code."""
    
    def _check_game_issues(self, code: str) -> List[str]:
        """
        Check if the generated game has critical issues that would break it
        Returns list of issues found
        """
        issues = []
        code_lower = code.lower()
        
        # Check for critical missing components
        if "matter-js" not in code_lower and "matter.js" not in code_lower:
            issues.append("Matter.js library not included - physics will not work")
        
        if "requestanimationframe" not in code_lower:
            issues.append("Game loop missing (no requestAnimationFrame) - game will not run")
        
        if "<canvas" not in code_lower:
            issues.append("Canvas element missing - game cannot render")
        
        if "getcontext" not in code_lower:
            issues.append("Canvas context not initialized - game cannot draw")
        
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
        """
        Create a prompt to fix specific issues found in the generated code
        """
        issues_text = "\n".join([f"- {issue}" for issue in issues[:5]])
        
        return f"""{original_prompt}

🚨 ISSUES FOUND IN GENERATED CODE:
{issues_text}

Please fix these issues and regenerate the complete HTML code. The game must work properly.
Make sure to:
1. Include all required libraries (Matter.js if needed)
2. Initialize all components properly
3. Fix any syntax errors (unbalanced braces, parentheses, etc.)
4. Ensure the game loop is working
5. Test that the game will run without errors

Return the complete fixed HTML code."""
    
    def _validate_html_code(self, code: str) -> Dict[str, Any]:
        # Validates HTML code for common issues
        errors = []
        warnings = []
        
        if not code or not code.strip():
            errors.append("Code is empty")
            return {"is_valid": False, "errors": errors, "warnings": warnings}
        
        code_lower = code.lower()
        
        # Check for required HTML structure
        if "<!doctype" not in code_lower:
            errors.append("Missing <!DOCTYPE html> declaration")
        
        if "<html" not in code_lower:
            errors.append("Missing <html> tag")
        
        if "<head" not in code_lower:
            errors.append("Missing <head> tag")
        
        if "<body" not in code_lower:
            errors.append("Missing <body> tag")
        
        # Check for canvas
        if "<canvas" not in code_lower:
            errors.append("Missing <canvas> element")
        else:
            if "getcontext" not in code_lower or "getcontext('2d')" not in code_lower:
                errors.append("Missing canvas.getContext('2d') call")
        
        # Check for Matter.js
        if "matter-js" not in code_lower and "matter.js" not in code_lower:
            errors.append("Matter.js CDN not found - physics required")
        else:
            if "engine.create" not in code_lower and "engine" not in code_lower:
                warnings.append("Matter.js engine not initialized")
        
        # Check for game loop
        if "requestanimationframe" not in code_lower:
            errors.append("requestAnimationFrame not found - game loop required")
        else:
            if "gameloop" not in code_lower and "game_loop" not in code_lower:
                warnings.append("Game loop function may be missing")
        
        # Check for input handling
        if "addeventlistener" not in code_lower or "keydown" not in code_lower:
            warnings.append("Keyboard input handling may be missing")
        
        # Check for balanced HTML tags
        open_html = code.count("<html")
        close_html = code.count("</html>")
        if open_html != close_html:
            errors.append(f"Unbalanced html tags: {open_html} open, {close_html} close")
        
        open_head = code.count("<head")
        close_head = code.count("</head>")
        if open_head != close_head:
            errors.append(f"Unbalanced head tags: {open_head} open, {close_head} close")
        
        open_body = code.count("<body")
        close_body = code.count("</body>")
        if open_body != close_body:
            errors.append(f"Unbalanced body tags: {open_body} open, {close_body} close")
        
        open_canvas = code.count("<canvas")
        close_canvas = code.count("</canvas>")
        if open_canvas != close_canvas:
            errors.append(f"Unbalanced canvas tags: {open_canvas} open, {close_canvas} close")
        
        # Check for balanced JavaScript syntax
        open_braces = code.count('{')
        close_braces = code.count('}')
        if open_braces != close_braces:
            errors.append(f"Unbalanced braces: {open_braces} open, {close_braces} close")
        
        open_parens = code.count('(')
        close_parens = code.count(')')
        if open_parens != close_parens:
            errors.append(f"Unbalanced parentheses: {open_parens} open, {close_parens} close")
        
        open_brackets = code.count('[')
        close_brackets = code.count(']')
        if open_brackets != close_brackets:
            errors.append(f"Unbalanced brackets: {open_brackets} open, {close_brackets} close")
        
        # Check for common JavaScript errors
        if "react" in code_lower or "jsx" in code_lower:
            errors.append("React/JSX found - must use pure HTML5/JavaScript only")
        
        if "import " in code or "export " in code:
            errors.append("ES6 imports/exports found - must use inline scripts only")
        
        # Check for canvas size setup
        if "innerwidth" not in code_lower or "innerheight" not in code_lower:
            warnings.append("Canvas size may not be set correctly")
        
        # Check for proper script tags
        script_count = code.count("<script")
        script_close_count = code.count("</script>")
        if script_count != script_close_count:
            errors.append(f"Unbalanced script tags: {script_count} open, {script_close_count} close")
        
        # GAME LOGIC VALIDATION - CRITICAL CHECKS
        # Check for player movement implementation
        if "player" in code_lower:
            if "speed" not in code_lower and "velocity" not in code_lower:
                warnings.append("Player movement may not be implemented correctly")
            if "keydown" in code_lower or "keyup" in code_lower:
                if "keys[" not in code_lower and "keys." not in code_lower:
                    warnings.append("Input handling may not track keys correctly")
        
        # Check for physics implementation
        if "matter" in code_lower or "engine" in code_lower:
            if "engine.create" not in code_lower and "engine = " not in code_lower:
                errors.append("Matter.js engine not created - physics will not work")
            if "engine.update" not in code_lower and "engine.run" not in code_lower:
                errors.append("Physics engine not updated in game loop - physics will not work")
            if "world.add" not in code_lower and "world.create" not in code_lower:
                warnings.append("Physics bodies may not be added to world")
        
        # Check for collision detection
        if "collision" in code_lower or "collide" in code_lower:
            if "events.on" not in code_lower and "collision" not in code_lower:
                warnings.append("Collision detection may not be implemented")
        else:
            warnings.append("No collision detection found - game may not detect interactions")
        
        # Check for game loop structure
        if "requestanimationframe" in code_lower:
            if "function gameloop" not in code_lower and "const gameloop" not in code_lower and "let gameloop" not in code_lower:
                if "gameloop()" in code_lower:
                    warnings.append("Game loop function may not be defined before calling")
        else:
            errors.append("requestAnimationFrame not found - game loop missing")
        
        # Check for score system
        if "score" in code_lower:
            if "score++" not in code_lower and "score +=" not in code_lower and "score = score +" not in code_lower:
                warnings.append("Score may not be updating correctly")
        
        # Check for proper variable declarations
        if "var " in code:
            warnings.append("Using 'var' instead of 'const' or 'let' - may cause scope issues")
        
        # Check for common JavaScript errors
        if "undefined" in code_lower and "typeof" not in code_lower:
            warnings.append("Potential undefined variable usage without checks")
        
        # Check for division by zero - ENHANCED DETECTION
        division_patterns = [
            "/ 0", "/0", "/0)", "/0,", "/0;", "/0 ",  # Direct division by zero
            " / deltaTime", "/ deltaTime", "/deltaTime",  # Division by deltaTime (could be 0)
            " / dt", "/ dt", "/dt",  # Division by dt (could be 0)
            " / speed", "/ speed", "/speed",  # Division by speed (could be 0)
            " / width", "/ width", "/width",  # Division by width (could be 0)
            " / height", "/ height", "/height",  # Division by height (could be 0)
        ]
        for pattern in division_patterns:
            if pattern in code:
                # Check if there's a guard (like "if (deltaTime > 0)" or "deltaTime || 1")
                pattern_var = pattern.replace("/", "").strip()
                if pattern_var in ["0", "deltaTime", "dt", "speed", "width", "height"]:
                    # Look for guards nearby
                    pattern_index = code.find(pattern)
                    if pattern_index != -1:
                        # Check 50 chars before for guards
                        context_before = code[max(0, pattern_index - 50):pattern_index]
                        has_guard = (
                            f"if ({pattern_var}" in context_before or
                            f"{pattern_var} ||" in context_before or
                            f"{pattern_var} ?" in context_before or
                            f"({pattern_var} &&" in context_before or
                            f"{pattern_var} > 0" in context_before or
                            f"{pattern_var} !== 0" in context_before
                        )
                        if not has_guard:
                            errors.append(f"Division by zero risk: '{pattern}' without guard - add check like 'if ({pattern_var} > 0)' or '{pattern_var} || 1'")
                else:
                    errors.append(f"Division by zero detected: '{pattern}' - will cause runtime error")
        
        # Check for proper canvas context usage
        if "getcontext" in code_lower:
            if "ctx." not in code_lower and "context." not in code_lower:
                warnings.append("Canvas context may not be used for rendering")
        
        # Check for proper initialization order
        if "window.innerwidth" in code_lower or "window.innerheight" in code_lower:
            if "addeventlistener('resize'" not in code_lower:
                warnings.append("Canvas resize handling may be missing")
        
        is_valid = len(errors) == 0
        
        return {
            "is_valid": is_valid,
            "errors": errors,
            "warnings": warnings
        }
    
    def _create_error_fix_prompt(
        self,
        original_prompt: str,
        broken_code: str,
        errors: List[str],
        warnings: List[str],
        component_type: str,
        attempt_number: int,
        max_retries: int = 3
    ) -> str:
        """Create improved prompt with specific error fixes"""
        
        # Special handling for division by zero
        division_errors = [e for e in errors if "division" in e.lower() or "zero" in e.lower()]
        if division_errors:
            error_context = f"""
🚨 CRITICAL ERROR: Division by zero detected!

The generated code has division by zero errors. This MUST be fixed immediately.

COMMON FIXES FOR DIVISION BY ZERO:
1. For deltaTime (MOST COMMON):
   const deltaTime = Math.min((currentTime - this.lastTime) / 1000, 0.1);
   this.lastTime = currentTime;
   if (deltaTime <= 0) return; // Skip frame if invalid

2. For any division by variable:
   if (denominator > 0) {{
     result = numerator / denominator;
   }} else {{
     result = defaultValue; // or skip calculation
   }}

3. Use safe division operator:
   const result = denominator ? numerator / denominator : defaultValue;

4. Cap values before division:
   const safeValue = Math.max(value, 0.001);
   const result = numerator / safeValue;

EXAMPLE SAFE DELTATIME IN GAME LOOP:
function gameLoop(currentTime) {{
  const deltaTime = Math.min((currentTime - lastTime) / 1000, 0.1);
  lastTime = currentTime;
  
  if (deltaTime <= 0 || deltaTime > 0.1) return; // Skip invalid frames
  
  update(deltaTime);
  render();
  requestAnimationFrame(gameLoop);
}}

Specific errors found:
{chr(10).join(f"- {e}" for e in division_errors)}

YOU MUST FIX ALL DIVISION BY ZERO ERRORS BEFORE RETURNING CODE!
"""
        else:
            error_context = f"""
Errors found:
{chr(10).join(f"- {e}" for e in errors[:10])}
"""
        
        error_summary = error_context
        warning_summary = "\n".join([f"- {w}" for w in warnings[:5]]) if warnings else "None"
        
        # Extract mechanics from original prompt if available
        mechanics_hint = ""
        if "Player Speed:" in original_prompt:
            import re
            speed_match = re.search(r"Player Speed: ([\d.]+)", original_prompt)
            jump_match = re.search(r"Jump Force: ([\d.-]+)", original_prompt)
            gravity_match = re.search(r"Gravity: ([\d.]+)", original_prompt)
            if speed_match and jump_match and gravity_match:
                mechanics_hint = f"""
CRITICAL MECHANICS VALUES (USE THESE EXACT VALUES):
- Player Speed: {speed_match.group(1)} pixels/second
- Jump Force: {jump_match.group(1)} (negative = upward)
- Gravity: {gravity_match.group(1)} pixels/frame²
"""
        
        return f"""🚨 CRITICAL: The previous attempt to generate {component_type} failed with errors. 
You MUST fix ALL errors. This is attempt {attempt_number} of {max_retries} - the code MUST be perfect.

{mechanics_hint}

ORIGINAL REQUIREMENTS:
{original_prompt[:2000]}...

ORIGINAL REQUIREMENTS:
{original_prompt}

BROKEN CODE (that has errors):
```html
{broken_code[:3000]}
```

ERRORS FOUND:
{error_summary}

WARNINGS:
{warning_summary}

CRITICAL FIXES NEEDED:
1. Fix ALL errors listed above - NO EXCEPTIONS
2. Fix ALL warnings if possible - they indicate potential issues
3. Ensure HTML structure is complete (<!DOCTYPE html>, <html>, <head>, <body>)
4. Include canvas element with proper ID
5. Load Matter.js from CDN in <head>
6. Create Matter.js engine: const engine = Engine.create();
7. Update physics in game loop: Engine.update(engine);
8. Implement game loop with requestAnimationFrame
9. Ensure all brackets, braces, and parentheses are balanced
10. Make sure JavaScript is properly formatted
11. Verify player movement uses correct speed value
12. Verify jump uses correct force value
13. Verify gravity is applied correctly
14. Ensure collision detection works
15. Ensure score updates correctly

CRITICAL INSTRUCTIONS:
- This is attempt {attempt_number} of {max_retries} - the code MUST be perfect
- CORRECTNESS > FEATURES - a simple working game is better than a broken complex game
- Return ONLY the complete, corrected HTML code
- NO markdown code blocks (no ```html or ```)
- NO explanations before or after
- NO comments outside the HTML
- Start directly with <!DOCTYPE html>
- End with </html>
- The code must be syntactically perfect, balanced, and ready to run
- Test every bracket, brace, and parenthesis before returning
- Ensure all required elements are present (DOCTYPE, html, head, body, canvas, script)
- Make sure Matter.js is loaded correctly and engine is created
- Ensure game loop is properly implemented and calls Engine.update()
- Verify player can move, jump, and interact with game world
- MENTALLY TEST the code before returning - does it work?"""
    
    def _aggressive_fix_code(self, code: str, errors: List[str]) -> str:
        """Apply aggressive automatic fixes to HTML code - MULTIPLE PASSES"""
        fixed = code
        max_passes = 3
        
        for pass_num in range(max_passes):
            original = fixed
            
            # Pass 1: Fix unbalanced braces
            open_braces = fixed.count('{')
            close_braces = fixed.count('}')
            if open_braces > close_braces:
                # Try to add closing braces before </script> tags
                if "</script>" in fixed:
                    fixed = fixed.replace("</script>", "}" * (open_braces - close_braces) + "\n</script>", 1)
                else:
                    fixed += '\n' + '}' * (open_braces - close_braces)
            elif close_braces > open_braces:
                logger.warning(f"More closing braces than opening: {close_braces - open_braces}")
            
            # Pass 2: Ensure Matter.js is loaded
            if "matter-js" not in fixed.lower() and "matter.js" not in fixed.lower():
                matter_script = '<script src="https://cdnjs.cloudflare.com/ajax/libs/matter-js/0.19.0/matter.min.js"></script>'
                if "</head>" in fixed:
                    fixed = fixed.replace("</head>", f"    {matter_script}\n</head>")
                elif "<body>" in fixed:
                    # Add head if missing
                    if "<head>" not in fixed.lower():
                        fixed = fixed.replace("<body>", f"<head>\n    {matter_script}\n</head>\n<body>")
                    else:
                        fixed = fixed.replace("<body>", f"    {matter_script}\n<body>")
            
            # Pass 3: Ensure canvas exists
            if "<canvas" not in fixed.lower():
                canvas_html = '<canvas id="gameCanvas"></canvas>'
                if "</body>" in fixed:
                    fixed = fixed.replace("</body>", f"    {canvas_html}\n</body>")
                else:
                    fixed += f"\n{canvas_html}"
            
            # Pass 4: Ensure DOCTYPE
            if "<!doctype" not in fixed.lower():
                if fixed.strip().startswith("<html"):
                    fixed = "<!DOCTYPE html>\n" + fixed
                else:
                    fixed = "<!DOCTYPE html>\n<html>\n" + fixed
            
            # Pass 5: Fix missing closing tags
            if "<html" in fixed.lower() and "</html>" not in fixed.lower():
                fixed += "\n</html>"
            
            if "<head" in fixed.lower() and "</head>" not in fixed.lower():
                if "<body" in fixed.lower():
                    # Insert </head> before <body>
                    fixed = fixed.replace("<body", "</head>\n<body", 1)
                else:
                    fixed += "\n</head>"
            
            if "<body" in fixed.lower() and "</body>" not in fixed.lower():
                fixed += "\n</body>"
            
            # If no changes made, break early
            if fixed == original:
                break
        
        return fixed

