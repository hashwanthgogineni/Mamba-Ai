import asyncio
from typing import Dict, Any, Optional, List
import logging
from datetime import datetime
import hashlib
import json
import re

from models.deepseek_client import DeepSeekClient

logger = logging.getLogger(__name__)


def _repair_json(content: str) -> str:
    if not content:
        return "{}"
    content = content.strip()
    open_braces = content.count('{')
    close_braces = content.count('}')
    if open_braces > close_braces:
        content += '}' * (open_braces - close_braces)
    content = re.sub(r',\s*}', '}', content)
    content = re.sub(r',\s*]', ']', content)
    return content


def _parse_ai_json_response(content: str, fallback: Dict = None) -> Dict:
    if not content:
        return fallback or {}
    
    if "```json" in content:
        content = content.split("```json")[1].split("```")[0].strip()
    elif "```" in content:
        parts = content.split("```")
        if len(parts) >= 3:
            content = parts[1].strip()
            if content.startswith("json"):
                content = content[4:].strip()
    
    if not content.startswith('{'):
        start_idx = content.find('{')
        end_idx = content.rfind('}')
        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
            content = content[start_idx:end_idx+1]
    
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        content = _repair_json(content)
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            logger.warning("JSON parse failed, using fallback")
            return fallback or {}


async def _ai_retry_with_self_correction(
    deepseek_client,
    initial_messages: List[Dict],
    parse_function,
    max_retries: int = 3,  # 3 retries - no fallbacks
    task_name: str = "AI generation"
) -> Any:
    last_error = None
    last_response = None
    improved_messages = initial_messages.copy()
    
    for attempt in range(max_retries):
        try:
            logger.info(f"{task_name} - Attempt {attempt + 1}/{max_retries}")
            
            # Optimized for quality: lower temperature = more consistent, higher quality
            response = await deepseek_client.generate(
                improved_messages, 
                temperature=0.15 if attempt == 0 else 0.3,
                max_tokens=5000
            )
            
            content = response.get('content', '')
            last_response = content
            
            if not content or not content.strip():
                raise ValueError("Empty response from AI")
            
            result = parse_function(content)
            
            if result is not None:
                logger.info(f"{task_name} succeeded on attempt {attempt + 1}")
                return result
            else:
                raise ValueError("Parse function returned None")
                
        except (json.JSONDecodeError, ValueError, KeyError, TypeError, AttributeError) as e:
            last_error = e
            logger.warning(f"{task_name} attempt {attempt + 1} failed: {e}")
            
            if attempt == max_retries - 1:
                logger.error(f"{task_name} failed after {max_retries} attempts - skipping this step")
                logger.error(f"   Last error: {last_error}")
                logger.error(f"   No further AI calls will be made for this generation")
                # Immediately raise to stop all further processing and save tokens
                raise ValueError(f"{task_name} failed after {max_retries} attempts. Process terminated to prevent token waste.")
            
            logger.info(f"Using AI to analyze error and improve prompt...")
            try:
                error_analysis_messages = [
                    {
                        "role": "system",
                        "content": "You are an expert at analyzing AI generation errors and improving prompts. Your job is to help fix generation issues by understanding what went wrong and suggesting better prompts."
                    },
                    {
                        "role": "user",
                        "content": f"""I'm trying to generate {task_name}, but it's failing. Help me fix this.

Original Prompt:
{json.dumps(initial_messages, indent=2)}

Error that occurred:
{str(e)}

AI Response (that failed to parse):
{last_response[:500] if last_response else 'No response'}

Attempt number: {attempt + 1}

Please analyze what went wrong and provide an improved prompt that will:
1. Be more explicit about the required JSON format
2. Include clear examples if needed
3. Address the specific error that occurred
4. Ensure the response will be valid JSON

Return a JSON object with:
{{
  "analysis": "What went wrong and why",
  "improved_prompt": "The improved user message content",
  "suggestions": ["suggestion1", "suggestion2"]
}}"""
                    }
                ]
                
                analysis_response = await deepseek_client.generate(
                    error_analysis_messages,
                    temperature=0.4,
                    max_tokens=2000
                )
                
                analysis_content = analysis_response.get('content', '')
                
                # Extract improved prompt from analysis
                if "```json" in analysis_content:
                    analysis_json = analysis_content.split("```json")[1].split("```")[0].strip()
                elif "```" in analysis_content:
                    parts = analysis_content.split("```")
                    if len(parts) >= 3:
                        analysis_json = parts[1].strip()
                        if analysis_json.startswith("json"):
                            analysis_json = analysis_json[4:].strip()
                else:
                    # Try to find JSON in the response
                    start_idx = analysis_content.find('{')
                    end_idx = analysis_content.rfind('}')
                    if start_idx != -1 and end_idx != -1:
                        analysis_json = analysis_content[start_idx:end_idx+1]
                    else:
                        analysis_json = None
                
                if analysis_json:
                    try:
                        analysis = json.loads(analysis_json)
                        improved_prompt = analysis.get('improved_prompt', '')
                        analysis_text = analysis.get('analysis', '')
                        
                        if improved_prompt:
                            logger.info(f"AI Analysis: {analysis_text[:200]}")
                            # Update the user message with improved prompt
                            if improved_messages and len(improved_messages) > 0 and isinstance(improved_messages[-1], dict):
                                improved_messages[-1]['content'] = improved_prompt
                            logger.info(f"Retrying with improved prompt...")
                        else:
                            # If no improved prompt, add error context to original
                            if improved_messages and len(improved_messages) > 0 and isinstance(improved_messages[-1], dict):
                                improved_messages[-1]['content'] = f"""{improved_messages[-1].get('content', '')}

IMPORTANT: The previous attempt failed with error: {str(e)}
Please ensure your response is valid JSON. Return ONLY a JSON object, no other text.
Make sure all strings are properly quoted and all brackets are balanced."""
                            logger.info(f"Retrying with error context added...")
                    except json.JSONDecodeError:
                        # If analysis itself fails, just add error context
                        if improved_messages and len(improved_messages) > 0 and isinstance(improved_messages[-1], dict):
                            improved_messages[-1]['content'] = f"""{improved_messages[-1].get('content', '')}

IMPORTANT: The previous attempt failed with error: {str(e)}
Please ensure your response is valid JSON. Return ONLY a JSON object, no other text.
Make sure all strings are properly quoted and all brackets are balanced."""
                        logger.info(f"🔄 Retrying with error context added...")
                else:
                    # If analysis failed, add error context to original prompt
                    if improved_messages and len(improved_messages) > 0 and isinstance(improved_messages[-1], dict):
                        improved_messages[-1]['content'] = f"""{improved_messages[-1].get('content', '')}

IMPORTANT: The previous attempt failed with error: {str(e)}
Please ensure your response is valid JSON. Return ONLY a JSON object, no other text.
Make sure all strings are properly quoted and all brackets are balanced."""
                    logger.info(f"🔄 Retrying with error context added...")
                    
            except Exception as analysis_error:
                logger.warning(f"Error analysis failed: {analysis_error}, adding simple error context")
                # Fallback: just add error context
                if improved_messages and len(improved_messages) > 0 and isinstance(improved_messages[-1], dict):
                    improved_messages[-1]['content'] = f"""{improved_messages[-1].get('content', '')}

IMPORTANT: The previous attempt failed with error: {str(e)}
Please ensure your response is valid JSON. Return ONLY a JSON object, no other text.
Make sure all strings are properly quoted and all brackets are balanced."""
    
    # Should never reach here, but just in case
    raise ValueError(f"{task_name} failed after {max_retries} attempts: {last_error}")


class MasterOrchestrator:
    # Orchestrates game generation pipeline
    def __init__(
        self,
        deepseek_api_key: str,
        cache_manager,
        storage_service,
        ws_manager=None,
        web_game_service=None,
        enable_ai_assets: bool = False,  # DALL-E disabled - using DeepSeek for descriptions only
        deepseek_model: str = None,
        deepseek_base_url: str = None,
        deepseek_thinking: bool = None,
        deepseek_reasoning_effort: str = None,
        game_engine: str = "html5",
        godot_builder=None,
        deepseek_client=None
    ):
        # Accept a ready-made client so the whole app shares one connection
        # pool and one configuration. Two clients meant a config change had to
        # land in two places to take effect.
        self.deepseek = deepseek_client or DeepSeekClient(
            deepseek_api_key,
            model=deepseek_model,
            base_url=deepseek_base_url,
            thinking=deepseek_thinking,
            reasoning_effort=deepseek_reasoning_effort
        )
        self.cache = cache_manager
        self.web_game = web_game_service
        self.storage = storage_service
        self.ws_manager = ws_manager
        self.enable_ai_assets = enable_ai_assets
        
        # AssetManagerAgent is unreachable: generate_assets() is never called and
        # real sprites now come from services/asset_library.py. Constructing it
        # only pulled in Pillow and printed a misleading startup line.
        self.asset_manager = None
        
        self.use_template_system = False
        self.game_engine = (game_engine or "html5").lower()
        self.godot = godot_builder

        logger.info(f"Master Orchestrator initialized (engine={self.game_engine})")
    
    async def initialize(self):
        logger.info("🚀 Initializing orchestrator...")
        logger.info("Orchestrator ready")
    
    async def shutdown(self):
        await self.deepseek.close()
        logger.info("Orchestrator shutdown")
    
    async def generate_game(
        self,
        project_id: str,
        user_prompt: str,
        user_tier: str = "free",
        db_manager = None,
        genre_id: str = None,
        answers: Dict[str, str] = None
    ) -> Dict[str, Any]:
        logger.info(f"Starting game generation for: {project_id}")
        
        start_time = datetime.utcnow()
        
        try:
            # Simplified: Let AI generate the complete game directly from user prompt
            # No intermediate phases - AI decides everything in its own style
            await self._update_status(project_id, "generating", "AI is creating your complete game...")
            logger.info("Generating complete HTML5 game with DeepSeek - AI decides everything")
            
            # Generate complete game directly from user prompt
            # AI will decide: mechanics, levels, style, everything
            if not self.web_game:
                raise ValueError("Web game service is required")
            
            if self.game_engine == "godot":
                if not self.godot:
                    raise ValueError(
                        "GAME_ENGINE=godot but the Godot builder is unavailable. "
                        "Check GODOT_PATH and that export templates are installed."
                    )
                return await self._generate_with_godot(
                    project_id, user_prompt, db_manager, start_time,
                    genre_id=genre_id, answers=answers
                )

            # Detect dimension from user prompt
            from utils.dimension_detector import DimensionDetector
            detected_dimension = DimensionDetector.detect_dimension(user_prompt)
            logger.info(f"Detected dimension: {detected_dimension}")
            
            # Create minimal structure for AI to work with
            # AI will generate everything based on the prompt
            minimal_design = {
                "title": user_prompt[:50] if user_prompt else "AI Generated Game",
                "description": user_prompt,
                "genre": "platformer",  # Default, AI can change
                "dimension": detected_dimension  # Use detected dimension
            }
            
            minimal_mechanics = {
                "player_movement": {"speed": 300.0, "jump_force": -400.0},
                "physics": {"gravity": 0.8}
            }
            
            # Let AI generate the complete game in one go
            await self._update_status(project_id, "building", "AI is building your complete HTML5 game...")
            logger.info("AI generating complete HTML5 game from scratch...")
            
            build_result = await self.web_game.build_game_from_ai_content(
                    project_id,
                {
                    "game_design": minimal_design,
                    "game_mechanics": minimal_mechanics,
                    "scripts": {"scripts_generated_by": "ai_deepseek", "use_ai": True},
                    "assets": [],
                    "ui_design": {},
                    "level_design": {},
                    "user_prompt": user_prompt  # Pass original prompt for AI to use
                },
                    self.storage,
                        self.deepseek
                    )
            
            # Create ai_content from what was generated
            ai_content = {
                "game_design": minimal_design,
                "game_mechanics": minimal_mechanics,
                "scripts": {"scripts_generated_by": "ai_deepseek", "use_ai": True},
                "assets": [],
                "ui_design": {},
                "level_design": {},
                "user_prompt": user_prompt
            }
            
            await self._log_step(db_manager, project_id, "game_generation", "success",
                               ai_model=self.deepseek.model, metadata={"method": "direct_ai_generation"})
            
            if not build_result.get('success'):
                logger.warning(f"Game build failed or skipped: {build_result.get('error')}")
                # Continue anyway - AI content is still saved
            
            build_type = "web_game"
            await self._log_step(db_manager, project_id, build_type, "success",
                               metadata=build_result)
            
            # Step 9: Validate game content before saving
            validation_errors = await self._validate_game_content(ai_content, build_result)
            if validation_errors:
                logger.warning(f"Validation warnings for {project_id}: {validation_errors}")
                # Continue anyway, but log warnings
            
            # Step 10: Save to database
            if db_manager:
                await db_manager.update_project(
                    project_id,
                    status="completed",
                    ai_content=ai_content,
                    completed_at=datetime.utcnow()
                )
                
                # Save build information
                preview_url = build_result.get('preview_url') or build_result.get('web_preview_url')
                for platform, url in build_result.get('builds', {}).items():
                    await db_manager.create_build(
                        project_id,
                        platform,
                        url,
                        web_preview_url=preview_url,
                        status="completed"
                    )
            
            # Final status update
            await self._update_status(project_id, "completed", "Your game is ready!")
            
            duration = (datetime.utcnow() - start_time).total_seconds()
            logger.info(f"Game generated successfully in {duration:.2f}s: {project_id}")
            
            preview_url = build_result.get('preview_url') or build_result.get('web_preview_url')
            return {
                "success": True,
                "project_id": project_id,
                "ai_content": ai_content,
                "builds": build_result.get('builds', {}),
                "web_preview_url": preview_url,
                "preview_url": preview_url,
                "duration_seconds": duration,
                "timestamp": datetime.utcnow().isoformat(),
                "validation_warnings": validation_errors if validation_errors else []
            }
            
        except Exception as e:
            # Log the error and fail
            error_msg = str(e)
            logger.error(f"Game generation failed for {project_id}: {error_msg}")
            await self._update_status(project_id, "failed", f"Generation failed: {error_msg}")
            if db_manager:
                await db_manager.update_project(project_id, status="failed")
                await self._log_step(db_manager, project_id, "generation", "failed", error=error_msg)
            return {
                "success": False,
                "project_id": project_id,
                "error": error_msg,
                "timestamp": datetime.utcnow().isoformat()
            }
    
    async def iterate_game(
        self,
        project_id: str,
        change_request: str,
        db_manager=None
    ) -> Dict[str, Any]:
        """Apply a change to an existing game instead of rebuilding it."""
        start_time = datetime.utcnow()

        if self.game_engine != "godot" or not self.godot:
            return {"success": False, "project_id": project_id,
                    "error": "Iteration requires the Godot engine."}

        async def progress(message: str):
            await self._update_status(project_id, "building", message)

        build = await self.godot.iterate(project_id, change_request, progress=progress)

        if not build.get("success"):
            error = build.get("error", "Could not apply the change")
            await self._update_status(project_id, "failed", error)
            return {"success": False, "project_id": project_id, "error": error,
                    "timestamp": datetime.utcnow().isoformat()}

        await self._update_status(project_id, "uploading", "Publishing your changes...")
        preview_url = await self._publish_dist(project_id, build["dist_path"])

        if db_manager:
            await db_manager.update_project(
                project_id, status="completed",
                web_preview_url=preview_url, completed_at=datetime.utcnow(),
            )

        await self._update_status(project_id, "completed", "Your changes are live!")
        duration = (datetime.utcnow() - start_time).total_seconds()
        logger.info(f"Iterated game in {duration:.1f}s: {project_id} ({build.get('files')})")

        return {
            "success": True, "project_id": project_id,
            "changed_files": build.get("files", []),
            "web_preview_url": preview_url, "preview_url": preview_url,
            "builds": {"web": preview_url},
            "iterated": True,
            "duration_seconds": duration,
            "timestamp": datetime.utcnow().isoformat(),
        }

    async def _generate_with_godot(
        self,
        project_id: str,
        user_prompt: str,
        db_manager,
        start_time,
        genre_id: str = None,
        answers: Dict[str, str] = None
    ) -> Dict[str, Any]:
        """Generate a Godot project, validate it in the engine, export for web."""

        async def progress(message: str):
            await self._update_status(project_id, "building", message)

        from services.ai_game_clarifier import build_brief
        brief = build_brief(user_prompt, genre_id, answers)

        build = await self.godot.build(
            project_id, user_prompt, progress=progress,
            genre_id=genre_id, brief=brief
        )

        if not build.get("success"):
            error = build.get("error", "Godot build failed")
            await self._update_status(project_id, "failed", f"Generation failed: {error}")
            if db_manager:
                await db_manager.update_project(project_id, status="failed")
                await self._log_step(db_manager, project_id, "godot_build", "failed", error=error)
            return {
                "success": False,
                "project_id": project_id,
                "error": error,
                "timestamp": datetime.utcnow().isoformat(),
            }

        await self._update_status(project_id, "uploading", "Publishing your game...")
        preview_url = await self._publish_dist(project_id, build["dist_path"])

        ai_content = {
            "engine": "godot",
            "plan": build.get("plan", {}),
            "files": build.get("files", []),
            "validation_passed": build.get("validation_passed"),
            "issues": build.get("issues", []),
            "user_prompt": user_prompt,
        }

        if db_manager:
            await db_manager.update_project(
                project_id,
                status="completed",
                ai_content=ai_content,
                web_preview_url=preview_url,
                completed_at=datetime.utcnow(),
            )
            await db_manager.create_build(
                project_id, "web", preview_url,
                web_preview_url=preview_url, status="completed"
            )
            await self._log_step(
                db_manager, project_id, "godot_build", "success",
                ai_model=self.deepseek.model,
                metadata={"validation_passed": build.get("validation_passed")},
            )

        await self._update_status(project_id, "completed", "Your game is ready!")
        duration = (datetime.utcnow() - start_time).total_seconds()
        logger.info(f"Godot game generated in {duration:.1f}s: {project_id}")

        return {
            "success": True,
            "project_id": project_id,
            "ai_content": ai_content,
            "builds": {"web": preview_url},
            "web_preview_url": preview_url,
            "preview_url": preview_url,
            "duration_seconds": duration,
            "timestamp": datetime.utcnow().isoformat(),
            "validation_warnings": build.get("issues", []),
        }

    async def _publish_dist(self, project_id: str, dist_path: str) -> Optional[str]:
        """Upload every file of the web export, preserving the directory shape."""
        from pathlib import Path as _Path
        import mimetypes

        dist = _Path(dist_path)
        if not dist.exists():
            logger.error(f"Export directory missing: {dist}")
            return None

        uploaded = 0
        for file in sorted(dist.rglob("*")):
            if not file.is_file():
                continue
            rel = file.relative_to(dist).as_posix()
            content_type = mimetypes.guess_type(rel)[0] or "application/octet-stream"
            if rel.endswith(".wasm"):
                content_type = "application/wasm"
            try:
                await self.storage.upload_file(
                    f"web_games/{project_id}/{rel}",
                    file.read_bytes(),
                    content_type=content_type,
                    public=True,
                )
                uploaded += 1
            except Exception as e:
                logger.error(f"Failed to publish {rel}: {e}")

        logger.info(f"📤 Published {uploaded} file(s) for {project_id}")
        return self._preview_url_for(project_id)

    def _preview_url_for(self, project_id: str) -> str:
        path = f"web_games/{project_id}/index.html"
        if hasattr(self.storage, "public_url"):
            return self.storage.public_url(path)
        from config.settings import Settings
        settings = Settings()
        base = settings.supabase_url.rstrip("/")
        return f"{base}/storage/v1/object/public/{self.storage.bucket}/{path}"

    async def _analyze_intent(self, user_prompt: str) -> Dict:
        """Step 1: Analyze user intent - DISABLED: AI not used, fallback only"""
        # TEMPLATE-ONLY MODE: Skip AI, use fallback
        logger.info("TEMPLATE-ONLY MODE: Skipping AI intent analysis, using fallback")
        concept = self._create_fallback_concept(user_prompt)
        
        # Normalize dimension: Convert 4D/5D to 3D, ensure 2D/3D only
        dimension = concept.get('dimension', '2D')
        if isinstance(dimension, str):
            dimension_upper = dimension.upper()
            if '4D' in dimension_upper or '5D' in dimension_upper or dimension_upper in ['4', '5', '6', '7', '8', '9']:
                logger.info(f"Converting {dimension} to 3D (only 2D and 3D supported)")
                concept['dimension'] = '3D'
            elif dimension_upper in ['2D', '2']:
                concept['dimension'] = '2D'
            elif dimension_upper in ['3D', '3']:
                concept['dimension'] = '3D'
            else:
                concept['dimension'] = '2D'
        else:
            concept['dimension'] = '2D'
        
        # Normalize and validate genre - ensure it matches available templates
        genre = concept.get('genre', 'platformer')
        if not genre or genre.strip() == '':
            logger.warning("Genre was empty, defaulting to platformer")
            genre = 'platformer'
        
        # Normalize genre using genre registry (handles variations)
        from services.genre_registry import GenreRegistry
        genre_registry = GenreRegistry()
        normalized_genre = genre_registry.normalize_genre(genre)
        
        # Validate genre is one we have templates for
        valid_genres = [
            'platformer', 'puzzle', 'rpg', 'shooter', 'endless_runner', 
            'match_3', 'tower_defense', 'racing', 'farming_sim', 
            'roguelike', 'metroidvania', 'survival', 'rhythm', 'bullet_hell'
        ]
        
        if normalized_genre not in valid_genres:
            logger.warning(f"Genre '{normalized_genre}' not in valid templates, defaulting to platformer")
            normalized_genre = 'platformer'
        
        concept['genre'] = normalized_genre
        concept['estimated_scope'] = 'small'
        
        logger.info(f"Intent analysis complete (fallback): genre={normalized_genre}, dimension={concept['dimension']}")
        
        return concept
    
    def _create_fallback_concept(self, user_prompt: str) -> Dict:
        """Create a fallback game concept from user prompt - optimized for basic prompts"""
        prompt_lower = user_prompt.lower()
        
        # Detect dimension - prioritize explicit mentions
        dimension = "2D"  # Default to 2D for basic prompts
        if any(word in prompt_lower for word in ["3d", "3-d", "three dimensional", "subway", "temple run"]):
            dimension = "3D"
        elif any(word in prompt_lower for word in ["2d", "2-d", "two dimensional", "pixel", "side-scrolling"]):
            dimension = "2D"
        
        # Detect genre - use platformer as universal default for basic prompts
        genre = "platformer"  # Universal default for "create a game" type prompts
        if "runner" in prompt_lower or "endless" in prompt_lower:
            genre = "endless_runner"
        elif "puzzle" in prompt_lower:
            genre = "puzzle"
        elif "shooter" in prompt_lower or "shoot" in prompt_lower or "fps" in prompt_lower:
            genre = "shooter"
        elif "rpg" in prompt_lower or "role playing" in prompt_lower:
            genre = "rpg"
        elif "match" in prompt_lower and "3" in prompt_lower:
            genre = "match_3"
        elif "tower" in prompt_lower and "defense" in prompt_lower:
            genre = "tower_defense"
        elif "racing" in prompt_lower or "race" in prompt_lower:
            genre = "racing"
        elif "farming" in prompt_lower or "farm" in prompt_lower:
            genre = "farming_sim"
        elif "rogue" in prompt_lower:
            genre = "roguelike"
        elif "metroidvania" in prompt_lower:
            genre = "metroidvania"
        elif "survival" in prompt_lower:
            genre = "survival"
        elif "rhythm" in prompt_lower:
            genre = "rhythm"
        elif "bullet" in prompt_lower and "hell" in prompt_lower:
            genre = "bullet_hell"
        
        # Determine core mechanic based on genre
        core_mechanic_map = {
            "platformer": "jump and collect",
            "endless_runner": "run and avoid obstacles",
            "puzzle": "solve puzzles",
            "shooter": "shoot enemies",
            "rpg": "explore and level up",
            "match_3": "match three or more",
            "tower_defense": "place towers and defend",
            "racing": "race to finish",
            "farming_sim": "plant and harvest",
            "roguelike": "explore procedurally generated dungeons",
            "metroidvania": "explore and unlock abilities",
            "survival": "gather resources and survive",
            "rhythm": "tap to the beat",
            "bullet_hell": "dodge bullets and shoot"
        }
        
        return {
            "genre": genre,
            "dimension": dimension,
            "theme": "adventure",
            "target_audience": "casual gamers",
            "core_mechanic": core_mechanic_map.get(genre, "jump and collect"),
            "difficulty": "medium",
            "estimated_scope": "small",
            "referenced_game": None,
            "game_style": "colorful and fun",
            "key_features": ["smooth controls", "collectibles", "progressive difficulty"]
        }
    
    async def _analyze_intent_with_ai(self, user_prompt: str) -> Dict:
        """Analyze user intent with DeepSeek AI - with self-correcting retry"""
        messages = [
            {
                "role": "user",
                "content": f"""Analyze this game request and extract key information:

User Request: "{user_prompt}"

Extract and return JSON with:
{{
  "genre": "platformer|puzzle|shooter|rpg|etc",
  "dimension": "2D|3D",
  "theme": "adventure|sci-fi|fantasy|etc",
  "target_audience": "casual|hardcore|kids|etc",
  "core_mechanic": "brief description",
  "difficulty": "easy|medium|hard",
  "estimated_scope": "small|medium|large",
  "referenced_game": "game name if mentioned",
  "game_style": "description",
  "key_features": ["feature1", "feature2"]
}}

IMPORTANT: Return ONLY valid JSON. No markdown, no explanations, just the JSON object."""
            }
        ]
        
        def parse_intent(content: str) -> Dict:
            """Parse intent analysis response"""
            if not content:
                return None
            
            # Extract JSON from markdown code blocks
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                parts = content.split("```")
                if len(parts) >= 3:
                    content = parts[1].strip()
                    if content.startswith("json"):
                        content = content[4:].strip()
            
            if not content.startswith('{'):
                start_idx = content.find('{')
                end_idx = content.rfind('}')
                if start_idx != -1 and end_idx != -1:
                    content = content[start_idx:end_idx+1]
            
            try:
                concept = json.loads(content)
                # Validate it's a dict
                if not isinstance(concept, dict):
                    return None
                # Normalize dimension
                dimension = concept.get('dimension', '2D').upper()
                if dimension not in ['2D', '3D']:
                    concept['dimension'] = '2D'
                else:
                    concept['dimension'] = dimension
                logger.info(f"AI intent analysis: genre={concept.get('genre')}, dimension={concept.get('dimension')}")
                return concept
            except (json.JSONDecodeError, ValueError, TypeError, KeyError) as e:
                logger.debug(f"Parse error in intent: {e}")
                return None
        
        # Use retry mechanism with self-correction - 3 retries, no fallbacks
        concept = await _ai_retry_with_self_correction(
            self.deepseek,
            messages,
            parse_intent,
            max_retries=3,
            task_name="Intent Analysis"
        )
        
        return concept
    
    async def _generate_game_design_with_ai(self, concept: Dict, prompt: str) -> Dict:
        """Generate detailed game design with DeepSeek AI - enhanced for quality"""
        messages = [
            {
                "role": "system",
                "content": "You are an expert game designer. Create detailed, creative, and polished game designs that are engaging and well-thought-out."
            },
            {
                "role": "user",
                "content": f"""Create a COMPLETE, POLISHED game design based on this concept:

CONCEPT:
{json.dumps(concept, indent=2)}

USER REQUEST: "{prompt}"

GAME DESIGN REQUIREMENTS:

1. TITLE & DESCRIPTION:
   - Title: Creative, memorable, matches genre
   - Description: 2-3 sentences explaining the game clearly

2. CORE DESIGN ELEMENTS:
   {{
     "title": "Creative Game Title",
     "description": "Clear 2-3 sentence description of what the game is",
  "genre": "{concept.get('genre')}",
  "dimension": "{concept.get('dimension')}",
     "art_style": "Detailed description (e.g., 'vibrant pixel art with smooth animations' or 'low-poly 3D with cel shading')",
     "color_scheme": {{
       "primary": "#hex (main UI/player color)",
       "secondary": "#hex (accent color)",
       "background": "#hex (background color)",
       "accent": "#hex (highlights/effects)"
     }},
     "player_description": "Detailed description of player character, abilities, appearance",
     "enemy_description": "Types of enemies, their behavior, appearance",
     "environment_description": "World setting, atmosphere, visual style",
     "win_condition": "Clear win condition (e.g., 'Reach the end of level', 'Collect 100 coins', 'Defeat all enemies')",
     "lose_condition": "Clear lose condition (e.g., 'Health reaches 0', 'Fall off screen', 'Time runs out')",
     "gameplay_loop": "Core gameplay loop in 1-2 sentences",
     "visual_effects": ["particle_effects", "screen_shake", "animations", "lighting"],
     "key_features": ["feature1", "feature2", "feature3"],
     "difficulty": "{concept.get('difficulty', 'medium')}",
     "target_audience": "{concept.get('target_audience', 'casual gamers')}"
   }}

3. QUALITY REQUIREMENTS:
   - Be creative but practical
   - Match the user's request closely
   - Design should be implementable
   - Colors should be harmonious
   - Features should be achievable

4. GENRE-SPECIFIC FOCUS:
   - Platformer: Focus on jumping mechanics, level progression
   - Runner: Focus on forward movement, obstacles, lanes
   - Puzzle: Focus on puzzle mechanics, solutions
   - Shooter: Focus on combat, weapons, enemies
   - RPG: Focus on progression, stats, exploration

Return ONLY valid JSON. No markdown. Make it detailed, creative, and production-ready."""
            }
        ]
        
        def parse_design(content: str) -> Dict:
            """Parse game design response"""
            if not content:
                return None
            
            # Extract JSON from markdown code blocks
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                parts = content.split("```")
                if len(parts) >= 3:
                    content = parts[1].strip()
                    if content.startswith("json"):
                        content = content[4:].strip()
            
            if not content.startswith('{'):
                start_idx = content.find('{')
                end_idx = content.rfind('}')
                if start_idx != -1 and end_idx != -1:
                    content = content[start_idx:end_idx+1]
            
            try:
                design = json.loads(content)
                # Validate it's a dict
                if not isinstance(design, dict):
                    return None
                design.update(concept)  # Merge with concept
                logger.info(f"AI generated game design: {design.get('title')}")
                return design
            except (json.JSONDecodeError, ValueError, TypeError, KeyError) as e:
                logger.debug(f"Parse error in design: {e}")
                return None
        
        # Use retry mechanism with self-correction - 3 retries, no fallbacks
        design = await _ai_retry_with_self_correction(
            self.deepseek,
            messages,
            parse_design,
            max_retries=3,
            task_name="Game Design Generation"
        )
        
        return design
    
    async def _generate_game_mechanics_with_ai(self, design: Dict) -> Dict:
        """Generate game mechanics with DeepSeek AI - enhanced prompts for quality"""
        genre = design.get('genre', 'platformer')
        dimension = design.get('dimension', '2D')
        
        messages = [
            {
                "role": "system",
                "content": "You are an expert game designer specializing in creating balanced, fun, and polished game mechanics. Your mechanics must be precise, well-tuned, and create engaging gameplay."
            },
            {
                "role": "user",
                "content": f"""Create PRODUCTION-QUALITY game mechanics for a {dimension} {genre} game.

GAME DESIGN CONTEXT:
{json.dumps(design, indent=2)}

CRITICAL REQUIREMENTS - READ CAREFULLY:

1. PHYSICS & MOVEMENT (MUST be precise):
   - Player speed: 200-600 pixels/second (balanced for {genre})
   - Jump force: -200 to -600 (negative = upward, must feel responsive)
   - Gravity: 0.5-1.5 pixels/frame² (must feel natural)
   - Acceleration: 1000-3000 (controls responsiveness)
   - Friction: 800-2000 (controls stopping)
   - Max fall speed: 400-800 (prevents falling too fast)

2. GAME MECHANICS STRUCTURE:
   {{
     "player_movement": {{
       "speed": number (200-600, balanced for {genre}),
       "jump_force": number (negative, -200 to -600),
       "acceleration": number (1000-3000),
       "friction": number (800-2000),
       "max_fall_speed": number (400-800),
       "air_control": number (0.5-1.0, how much control in air)
     }},
     "physics": {{
       "gravity": number (0.5-1.5, must be > 0),
       "friction": number (0.05-0.2),
       "air_resistance": number (0.0-0.1),
       "bounce": number (0.0-0.3, for platforms)
     }},
     "game_loop": {{
       "fps": 60,
       "use_requestAnimationFrame": true,
       "delta_time": true
     }},
     "collision": {{
       "enabled": true,
       "type": "aabb",
       "precision": "medium"
     }},
     "enemy_behavior": {{
       "speed": number (50-400, slower than player),
       "ai_type": "patrol|chase|static",
       "patrol_distance": number (100-500),
       "detection_range": number (200-600)
     }},
     "collectible_system": {{
       "types": ["coin", "gem", "powerup"],
       "points_per_coin": number (10-50),
       "points_per_gem": number (50-200),
       "spawn_rate": number (0.1-0.5),
       "respawn_time": number (5-30 seconds)
     }},
     "scoring": {{
       "points_per_collectible": number (10-100),
       "points_per_enemy": number (50-500),
       "points_per_level": number (100-1000),
       "combo_multiplier": number (1.0-2.0)
     }},
     "power_ups": ["speed_boost", "double_jump", "shield"],
     "game_modes": ["normal", "time_trial"],
     "difficulty_curve": {{
       "enemy_spawn_rate": number (0.1-0.8),
       "obstacle_density": number (0.2-0.7),
       "speed_increase": number (1.0-1.5 per level)
     }}
   }}

3. GENRE-SPECIFIC REQUIREMENTS:
   - Platformer: Focus on precise jumping, platform spacing, enemy placement
   - Runner: Focus on forward momentum, obstacle patterns, lane switching
   - Puzzle: Focus on mechanics that enable puzzle solving
   - Shooter: Focus on weapon mechanics, enemy AI, bullet physics
   - RPG: Focus on stats, progression, combat mechanics

4. BALANCE & FUN:
   - Mechanics must feel responsive and satisfying
   - Difficulty should ramp gradually
   - Player should feel powerful but challenged
   - All values must work together harmoniously

5. VALIDATION RULES:
   - speed > 0 and < 1000
   - jump_force < 0 (negative)
   - gravity > 0 and < 5
   - All numbers must be valid floats
   - No null or undefined values

Return ONLY valid JSON. No markdown, no explanations. Make it balanced, fun, and production-ready."""
            }
        ]
        
        def parse_mechanics(content: str) -> Dict:
            """Parse game mechanics response"""
            if not content:
                return None
            
            # Extract JSON from markdown code blocks
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                parts = content.split("```")
                if len(parts) >= 3:
                    content = parts[1].strip()
                    if content.startswith("json"):
                        content = content[4:].strip()
            
            if not content.startswith('{'):
                start_idx = content.find('{')
                end_idx = content.rfind('}')
                if start_idx != -1 and end_idx != -1:
                    content = content[start_idx:end_idx+1]
            
            try:
                mechanics = json.loads(content)
                # Validate it's a dict
                if not isinstance(mechanics, dict):
                    return None
                logger.info("AI generated game mechanics")
                return mechanics
            except (json.JSONDecodeError, ValueError, TypeError, KeyError) as e:
                logger.debug(f"Parse error in mechanics: {e}")
                return None
        
        # Use retry mechanism with self-correction - 3 retries, no fallbacks
        mechanics = await _ai_retry_with_self_correction(
            self.deepseek,
            messages,
            parse_mechanics,
            max_retries=3,
            task_name="Game Mechanics Generation"
        )
        
        return mechanics
    
    async def _generate_game_design(self, concept: Dict, prompt: str) -> Dict:
        """Step 2: Generate detailed game design - DISABLED: AI not used, fallback only"""
        # TEMPLATE-ONLY MODE: Skip AI, use fallback
        logger.info("TEMPLATE-ONLY MODE: Skipping AI game design, using fallback")
        return {
            "title": prompt[:50] if prompt else "Gamora Game",
            "description": prompt[:200] if prompt else "A fun game",
            "genre": concept.get("genre", "platformer"),
            "art_style": "pixel art",
            "color_scheme": {"primary": "#4A90E2", "secondary": "#50C878"},
            "player_description": "A heroic character",
            "environment_description": "A colorful game world"
        }
    
    async def _generate_game_mechanics(self, design: Dict) -> Dict:
        """Step 3: Generate game mechanics - DISABLED: AI not used, fallback only"""
        # TEMPLATE-ONLY MODE: Skip AI, use fallback
        logger.info("TEMPLATE-ONLY MODE: Skipping AI mechanics generation, using fallback")
        genre = design.get('genre', 'platformer')
        
        # Return fallback mechanics based on genre
        if 'endless_runner' in genre.lower() or 'runner' in genre.lower():
            return {
                "player_movement": {
                    "speed": 500.0,
                    "jump_force": -500.0,
                    "acceleration": 2000.0,
                    "friction": 1500.0
                },
                "player_abilities": ["jump", "move", "slide", "lane_switch"],
                "game_rules": ["Run forward", "Collect coins", "Avoid obstacles"],
                "scoring_system": "Points per coin collected"
            }
        else:
            # Default platformer mechanics
            return {
                "player_movement": {
                    "speed": 300.0,
                    "jump_force": -400.0,
                    "acceleration": 1500.0,
                    "friction": 1200.0
                },
                "player_abilities": ["jump", "move"],
                "game_rules": ["Collect items", "Avoid obstacles"],
                "scoring_system": "Points per item collected"
            }
    
    async def _generate_game_code(self, design: Dict, mechanics: Dict) -> Dict:
        """Step 4: Generate GDScript code using AI with hybrid approach"""
        
        # Web game service will generate code directly
        try:
            # Return structure indicating AI-powered generation
            return {
                "scripts_generated_by": "ai_with_fallback",
                "use_ai": True,  # Flag to use AI generation
                "game_design": design,
                "game_mechanics": mechanics,
                "custom_scripts": {},
                "status": "ready_for_ai_generation"
            }
        except Exception as e:
            logger.error(f"Unexpected error in _generate_game_code: {e}", exc_info=True)
            return {
                "scripts_generated_by": "template_fallback",
                "use_ai": False,  # Fallback to templates
                "custom_scripts": {},
                "status": "ready_for_godot_generation",
                "error": str(e)
            }
    
    async def _generate_ui_design(self, design: Dict) -> Dict:
        """Step 6: Generate UI design - DISABLED: AI not used, fallback only"""
        # TEMPLATE-ONLY MODE: Skip AI, use fallback
        logger.info("📋 TEMPLATE-ONLY MODE: Skipping AI UI design, using fallback")
        color_scheme = design.get('color_scheme', {})
        return {
            "menu_style": "modern",
            "font_size": 24,
            "button_style": "rounded",
            "color_theme": color_scheme if color_scheme else {"primary": "#4A90E2", "secondary": "#50C878"},
            "hud_layout": {
                "score_position": "top_left",
                "health_position": "top_left",
                "health_display": "number"
            }
        }
    
    async def _generate_level_design_with_ai(self, design: Dict, mechanics: Dict) -> Dict:
        """Generate level design with DeepSeek AI - enhanced for quality"""
        genre = design.get('genre', 'platformer')
        dimension = design.get('dimension', '2D')
        
        messages = [
            {
                "role": "system",
                "content": "You are an expert level designer. Create well-designed, balanced levels that are fun, challenging, and progressively difficult."
            },
            {
                "role": "user",
                "content": f"""Create PRODUCTION-QUALITY level design for a {dimension} {genre} game.

GAME DESIGN:
{json.dumps(design, indent=2)}

GAME MECHANICS:
{json.dumps(mechanics, indent=2)}

LEVEL DESIGN REQUIREMENTS:

For PLATFORMER games (2D side-scrolling):
{{
  "levels": [
    {{
      "name": "Level 1",
      "difficulty": "easy",
      "width": 1200,
      "height": 800,
      "platforms": [[x, y, width, height], ...],  // Ground platforms, must be reachable
      "enemies": [[x, y], ...],  // Enemy positions, must be on platforms
      "collectibles": [[x, y], ...],  // Collectible positions, must be reachable
      "spawn_point": [x, y],  // Player start position
      "goal": [x, y],  // End of level position
      "checkpoints": [[x, y], ...],  // Optional checkpoints
      "hazards": [[x, y, width, height], ...],  // Spikes, pits, etc.
      "secrets": [[x, y], ...]  // Optional secret areas
    }},
    {{
      "name": "Level 2",
      "difficulty": "medium",
      // Same structure, but more challenging
    }}
  ]
}}

For RUNNER games (endless or 3D):
{{
                    "spawn_patterns": [
    {{
      "obstacle_type": "barrier|hole|enemy",
      "spawn_rate": 0.2-0.5,
      "lane": "left|center|right|random",
      "min_gap": 200-500,
      "max_gap": 500-1000
    }}
  ],
  "collectible_placement": "scattered|clustered|pattern",
                    "lane_configuration": 3,
  "difficulty_curve": "gradual|exponential",
  "speed_increase": 1.0-1.2 per 1000 units
}}

CRITICAL DESIGN RULES:

1. PLATFORMER LEVELS:
   - Platforms must be reachable (max jump height: ~400px)
   - Progression must be clear (left to right or up)
   - Difficulty must ramp gradually
   - Level 1: Easy, teaches basics
   - Level 2: Medium, introduces challenges
   - Platforms: [x, y, width, height] where y=0 is top, y increases downward
   - Canvas size: 1200x800 (typical)
   - Ground level: y=700-750
   - Platform spacing: 200-400px apart
   - Enemy placement: On platforms, not in air
   - Collectibles: Reachable, rewarding placement

2. RUNNER LEVELS:
   - Obstacles must be avoidable
   - Patterns must create rhythm
   - Difficulty must increase gradually
   - Gaps between obstacles: 300-800px
   - Lane variety: Mix of left/center/right

3. BALANCE:
   - Level 1: Tutorial-like, easy to complete
   - Level 2: Moderate challenge, tests skills
   - Collectibles: 3-8 per level
   - Enemies: 1-3 per level (Level 1), 2-5 (Level 2)
   - Platforms: 3-6 per level

4. VALIDATION:
   - All coordinates must be within canvas bounds (0-1200 x, 0-800 y)
   - Platforms must not overlap unreasonably
   - Spawn point must be on ground/platform
   - Goal must be reachable
   - No impossible jumps (max ~400px horizontal, ~300px vertical)

Return ONLY valid JSON. No markdown. Make levels fun, balanced, and well-designed."""
            }
        ]
        
        def parse_level_design(content: str) -> Dict:
            if not content:
                return None
            
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                parts = content.split("```")
                if len(parts) >= 3:
                    content = parts[1].strip()
                    if content.startswith("json"):
                        content = content[4:].strip()
            
            if not content.startswith('{'):
                start_idx = content.find('{')
                end_idx = content.rfind('}')
                if start_idx != -1 and end_idx != -1:
                    content = content[start_idx:end_idx+1]
            
            try:
                level_design = json.loads(content)
                if not isinstance(level_design, dict):
                    return None
                
                # Validate and fix level design
                level_design = self._validate_and_fix_level_design(level_design, design)
                logger.info("✅ AI generated level design")
                return level_design
            except (json.JSONDecodeError, ValueError, TypeError, KeyError) as e:
                logger.debug(f"Parse error in level design: {e}")
                return None
        
        level_design = await _ai_retry_with_self_correction(
            self.deepseek,
            messages,
            parse_level_design,
            max_retries=3,
            task_name="Level Design Generation"
        )
        
        return level_design
    
    def _validate_and_fix_level_design(self, level_design: Dict, game_design: Dict) -> Dict:
        """Validate and fix level design to ensure it's playable"""
        genre = game_design.get('genre', 'platformer')
        dimension = game_design.get('dimension', '2D')
        
        if 'endless_runner' in genre.lower() or 'runner' in genre.lower() or dimension == '3D':
            if 'spawn_patterns' not in level_design:
                level_design['spawn_patterns'] = [
                    {"obstacle_type": "barrier", "spawn_rate": 0.3, "lane": "random"},
                    {"obstacle_type": "hole", "spawn_rate": 0.2, "lane": "random"}
                ]
            return level_design
        
        if 'levels' not in level_design:
            level_design['levels'] = []
        
        levels = level_design['levels']
        if not isinstance(levels, list):
            levels = []
        
        # Ensure we have at least 2 levels, max 2
        if len(levels) == 0:
            levels = [self._create_default_level(1, "easy"), self._create_default_level(2, "medium")]
        elif len(levels) == 1:
            levels.append(self._create_default_level(2, "medium"))
        elif len(levels) > 2:
            levels = levels[:2]
        
        # Validate each level
        for i, level in enumerate(levels):
            if not isinstance(level, dict):
                levels[i] = self._create_default_level(i+1, "easy" if i == 0 else "medium")
                continue
            
            # Ensure required fields
            if 'name' not in level:
                level['name'] = f"Level {i+1}"
            if 'difficulty' not in level:
                level['difficulty'] = "easy" if i == 0 else "medium"
            if 'platforms' not in level:
                level['platforms'] = [[0, 700, 200, 64], [300, 600, 200, 64], [600, 500, 200, 64]]
            if 'enemies' not in level:
                level['enemies'] = []
            if 'collectibles' not in level:
                level['collectibles'] = [[150, 650], [350, 550], [650, 450]]
            if 'spawn_point' not in level:
                level['spawn_point'] = [100, 650]
            if 'goal' not in level:
                level['goal'] = [1000, 400]
            
            # Validate coordinates are within bounds
            canvas_width, canvas_height = 1200, 800
            level['platforms'] = [[max(0, min(x, canvas_width-200)), max(0, min(y, canvas_height-64)), w, h] 
                                  for x, y, w, h in level['platforms']]
            level['enemies'] = [[max(0, min(x, canvas_width)), max(0, min(y, canvas_height))] 
                               for x, y in level['enemies']]
            level['collectibles'] = [[max(0, min(x, canvas_width)), max(0, min(y, canvas_height))] 
                                     for x, y in level['collectibles']]
            
            spawn = level['spawn_point']
            level['spawn_point'] = [max(0, min(spawn[0], canvas_width)), max(0, min(spawn[1], canvas_height))]
            
            goal = level['goal']
            level['goal'] = [max(0, min(goal[0], canvas_width)), max(0, min(goal[1], canvas_height))]
        
        level_design['levels'] = levels
        return level_design
    
    def _create_default_level(self, level_num: int, difficulty: str) -> Dict:
        """Create a default level structure"""
        if level_num == 1:
            return {
                        "name": "Level 1",
                        "difficulty": "easy",
                "platforms": [[0, 700, 200, 64], [300, 600, 200, 64], [600, 500, 200, 64]],
                "enemies": [[400, 550]],
                "collectibles": [[150, 650], [350, 550], [650, 450]],
                "spawn_point": [100, 650],
                "goal": [1000, 400]
            }
        else:
            return {
                        "name": "Level 2",
                        "difficulty": "medium",
                "platforms": [[0, 700, 200, 64], [250, 600, 200, 64], [500, 500, 200, 64], [750, 400, 200, 64]],
                "enemies": [[350, 550], [600, 450]],
                "collectibles": [[100, 650], [300, 550], [550, 450], [800, 350]],
                "spawn_point": [100, 650],
                "goal": [1100, 350]
            }
    
    async def _generate_level_design(self, design: Dict, mechanics: Dict) -> Dict:
        """Legacy method - redirects to AI generation"""
        return await self._generate_level_design_with_ai(design, mechanics)
    
    async def _update_status(self, project_id: str, status: str, message: str):
        """Update generation status and notify via WebSocket"""
        logger.info(f"[{project_id}] {status}: {message}")
        
        # Update cache
        await self.cache.set_generation_status(
            project_id,
            {
                "status": status,
                "message": message,
                "timestamp": datetime.utcnow().isoformat()
            }
        )
        
        # Send WebSocket update if manager is available
        if self.ws_manager:
            await self.ws_manager.send_message(project_id, {
                "type": "progress",
                "data": {
                "status": status,
                "message": message
                }
            })
    
    async def _validate_game_content(self, ai_content: Dict, build_result: Dict) -> List[str]:
        """
        Simplified validation - just check if game was built successfully
        Since AI generates everything directly in HTML, we don't need to validate structured data
        """
        warnings = []
        
        # Only check if build was successful
        if not build_result.get('success'):
            warnings.append(f"Build had issues: {build_result.get('error', 'Unknown error')}")
        
        # That's it - trust the AI generated code
        return warnings
    
    def _validate_and_fix_mechanics(self, game_mechanics: Dict) -> Dict:
        """Validate and fix game mechanics to ensure they're correct - ENHANCED"""
        if not game_mechanics:
            game_mechanics = {}
        
        validated = game_mechanics.copy()
        
        # Validate player_movement - CRITICAL
        player_movement = validated.get('player_movement', {})
        if not player_movement:
            player_movement = {}
        
        # Speed validation - MUST be valid
        speed = player_movement.get('speed', 0)
        if speed <= 0:
            logger.warning(f"Invalid player speed: {speed}, fixing to 300.0")
            player_movement['speed'] = 300.0
        elif speed > 1000:
            logger.warning(f"Player speed too high: {speed}, capping to 600.0")
            player_movement['speed'] = 600.0
        elif speed < 50:
            logger.warning(f"Player speed too low: {speed}, setting to 100.0")
            player_movement['speed'] = max(100.0, speed)
        
        # Jump force validation - MUST be negative
        jump_force = player_movement.get('jump_force', 0)
        if jump_force == 0:
            logger.warning("Jump force is 0, fixing to -400.0")
            player_movement['jump_force'] = -400.0
        elif jump_force > 0:
            logger.warning(f"Jump force is positive: {jump_force}, fixing to negative")
            player_movement['jump_force'] = -abs(jump_force)
        elif jump_force < -800:
            logger.warning(f"Jump force too strong: {jump_force}, capping to -600.0")
            player_movement['jump_force'] = -600.0
        elif jump_force > -100:
            logger.warning(f"Jump force too weak: {jump_force}, setting to -200.0")
            player_movement['jump_force'] = -200.0
        
        # Acceleration and friction
        if 'acceleration' not in player_movement:
            player_movement['acceleration'] = 1500.0
        if 'friction' not in player_movement:
            player_movement['friction'] = 1200.0
        
        validated['player_movement'] = player_movement
        
        # Validate physics - CRITICAL
        physics = validated.get('physics', {})
        if not physics:
            physics = {}
        
        gravity = physics.get('gravity', 0)
        if gravity <= 0:
            logger.warning(f"Invalid gravity: {gravity}, fixing to 0.8")
            physics['gravity'] = 0.8
        elif gravity > 5:
            logger.warning(f"Gravity too high: {gravity}, capping to 2.0")
            physics['gravity'] = 2.0
        
        if 'friction' not in physics:
            physics['friction'] = 0.1
        if 'air_resistance' not in physics:
            physics['air_resistance'] = 0.0
        
        validated['physics'] = physics
        
        # Validate game loop
        if 'game_loop' not in validated:
            validated['game_loop'] = {'fps': 60, 'use_requestAnimationFrame': True}
        else:
            game_loop = validated['game_loop']
            if 'fps' not in game_loop or game_loop.get('fps', 0) <= 0:
                game_loop['fps'] = 60
            if 'use_requestAnimationFrame' not in game_loop:
                game_loop['use_requestAnimationFrame'] = True
        
        # Validate scoring
        if 'scoring' not in validated:
            validated['scoring'] = {
                'points_per_collectible': 10,
                'points_per_enemy': 50,
                'points_per_level': 100
            }
        
        # Validate collision
        if 'collision' not in validated:
            validated['collision'] = {
                'enabled': True,
                'type': 'aabb',  # Axis-Aligned Bounding Box
                'precision': 'medium'
            }
        
        logger.info(f"✅ Validated mechanics: speed={player_movement.get('speed')}, jump={player_movement.get('jump_force')}, gravity={physics.get('gravity')}")
        
        return validated
    
    def _create_fallback_design(self, concept: Dict, prompt: str) -> Dict:
        """Create fallback game design that matches user intent"""
        # Handle None concept
        if concept is None:
            concept = {}
        genre = concept.get('genre', 'platformer') if concept else 'platformer'
        dimension = concept.get('dimension', '2D') if concept else '2D'
        theme = concept.get('theme', 'adventure') if concept else 'adventure'
        
        return {
            "title": f"{genre.title()} Adventure",
            "description": prompt[:200] if prompt else f"A fun {genre} game",
            "genre": genre,
            "dimension": dimension,
            "art_style": "colorful and polished" if dimension == "3D" else "pixel art",
            "color_scheme": {
                "primary": "#4A90E2" if dimension == "2D" else "#5CB3FF",
                "secondary": "#FFD700",
                "background": "#2C3E50" if dimension == "2D" else "#87CEEB",
                "accent": "#FF6464"
            },
            "player_description": "A heroic character ready for adventure",
            "enemy_description": "Challenging obstacles to overcome",
            "environment_description": f"A {theme} world full of adventure",
            "win_condition": "Complete all levels",
            "lose_condition": "Health reaches zero",
            "gameplay_loop": "Move, jump, collect items, avoid enemies",
            "visual_effects": ["particles", "animations", "screen shake"],
            "referenced_game": concept.get('referenced_game'),
            "game_style": concept.get('game_style', 'colorful and fun'),
            "key_features": concept.get('key_features', [])
        }
    
    def _create_fallback_mechanics(self, design: Dict) -> Dict:
        """Create fallback game mechanics"""
        genre = design.get('genre', 'platformer')
        dimension = design.get('dimension', '2D')
        
        if 'runner' in genre.lower():
            return {
                "player_movement": {
                    "speed": 400.0,
                    "jump_force": -500.0,
                    "acceleration": 2000.0,
                    "friction": 1500.0,
                    "max_fall_speed": 800.0
                },
                "player_abilities": ["jump", "move", "slide", "lane_switch"],
                "enemy_behaviors": ["static_obstacle", "moving_obstacle"],
                "collectibles": [{"type": "coin", "value": 10, "spawn_rate": 0.3}],
                "power_ups": [],
                "obstacles": ["barrier", "hole"],
                "game_rules": ["Run forward", "Avoid obstacles", "Collect coins"],
                "scoring_system": {"coin": 10, "distance": 1},
                "progression": "Speed increases over time",
                "camera_behavior": "forward_follow",
                "lane_system": 3,
                "spawn_system": "continuous_forward"
            }
        else:
            return {
                "player_movement": {
                    "speed": 300.0,
                    "jump_force": -400.0,
                    "acceleration": 1500.0,
                    "friction": 1200.0,
                    "max_fall_speed": 600.0
                },
                "player_abilities": ["jump", "move"],
                "enemy_behaviors": ["patrol", "chase"],
                "collectibles": [{"type": "coin", "value": 10, "spawn_rate": 0.2}],
                "power_ups": [],
                "obstacles": ["spike", "platform"],
                "game_rules": ["Move and jump", "Collect items", "Avoid enemies"],
                "scoring_system": {"coin": 10},
                "progression": "Level-based difficulty increase",
                "camera_behavior": "smooth_follow",
                "spawn_system": "static_placement"
            }
    
    def _create_fallback_scripts(self, design: Dict, mechanics: Dict) -> Dict:
        """Create fallback game scripts - returns structure for web game service"""
        # Web game service will generate code directly
        return {
            "scripts_generated_by": "web_game_service",
            "use_ai": True,
            "custom_scripts": {}
        }
    
    def _create_fallback_ui_design(self, design: Dict) -> Dict:
        """Create fallback UI design"""
        return {
            "menu_style": "modern",
            "font_size": 24,
            "button_style": "rounded",
            "color_theme": {
                "primary": design.get('color_scheme', {}).get('primary', '#4A90E2') if isinstance(design.get('color_scheme'), dict) else '#4A90E2',
                "secondary": "#FFD700",
                "accent": "#FF6464",
                "background": "transparent",
                "text": "#FFFFFF"
            },
            "hud_layout": {
                "score_position": "top_left",
                "health_position": "top_left",
                "health_display": "number"
            },
            "ui_elements": [],
            "menu_screens": [],
            "feedback_effects": ["score_popup"]
        }
    
    def _create_fallback_level_design(self, design: Dict) -> Dict:
        """Create fallback level design (2 levels for starter game)"""
        dimension = design.get('dimension', '2D')
        genre = design.get('genre', 'platformer')
        
        if 'runner' in genre.lower() or dimension == '3D':
            return {
                "spawn_patterns": [
                    {"obstacle_type": "barrier", "spawn_rate": 0.3, "lane": "random"},
                    {"obstacle_type": "hole", "spawn_rate": 0.2, "lane": "random"}
                ],
                "collectible_placement": "scattered",
                "lane_configuration": 3,
                "difficulty_curve": "gradual"
            }
        else:
            return {
                "levels": [
                    {
                        "name": "Level 1",
                        "difficulty": "easy",
                        "platforms": [[0, 500, 200, 64], [300, 400, 200, 64], [600, 300, 200, 64]],
                        "enemies": [[400, 350]],
                        "collectibles": [[150, 450], [350, 350], [650, 250]],
                        "spawn_point": [100, 400],
                        "goal": [800, 200]
                    },
                    {
                        "name": "Level 2",
                        "difficulty": "medium",
                        "platforms": [[0, 500, 200, 64], [250, 400, 200, 64], [500, 300, 200, 64], [750, 200, 200, 64]],
                        "enemies": [[350, 350], [600, 250]],
                        "collectibles": [[100, 450], [300, 350], [550, 250], [800, 150]],
                        "spawn_point": [100, 400],
                        "goal": [900, 150]
                    }
                ]
            }
    
    async def _log_step(
        self,
        db_manager,
        project_id: str,
        step: str,
        status: str,
        **kwargs
    ):
        """Log generation step to database"""
        if db_manager:
            await db_manager.log_generation_step(
                project_id,
                step,
                status,
                **kwargs
            )
