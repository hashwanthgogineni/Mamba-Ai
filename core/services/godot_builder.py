"""
Godot build pipeline.

    prompt -> plan -> files -> gates -> repair loop -> --import -> export -> dist/

The repair loop is the point. Godot reports the failing file and line, so a
failure regenerates only that file and re-runs the gates. Whole-project
regeneration is slower and can break files that already pass.
"""

import asyncio
import json
import logging
import shutil
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from services.ai_godot_generator import AIGodotGenerator
from services.asset_library import AssetLibrary
from services.godot_emitter import GodotPlan, scaffold, write_ai_files
from services.godot_runtime import GodotRuntime, expected_content
from services.godot_validator import GodotValidator

logger = logging.getLogger(__name__)


class GodotBuilder:
    def __init__(
        self,
        deepseek_client,
        godot_path: str = "godot",
        projects_dir: str = "./godot_projects",
        max_repair_rounds: int = 3,
    ):
        self.generator = AIGodotGenerator(deepseek_client)
        self.assets = AssetLibrary()
        self.validator = GodotValidator(godot_path)
        self.runtime = GodotRuntime(godot_path)
        self.godot = godot_path
        self.projects_dir = Path(projects_dir)
        self.projects_dir.mkdir(parents=True, exist_ok=True)
        self.max_repair_rounds = max_repair_rounds

    async def is_available(self) -> bool:
        try:
            proc = await asyncio.create_subprocess_exec(
                self.godot, "--version",
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
            )
            out, _ = await proc.communicate()
            logger.info(f"🎮 Godot: {out.decode(errors='replace').strip().splitlines()[-1]}")
            return proc.returncode == 0
        except Exception as e:
            logger.error(f"Godot unavailable at '{self.godot}': {e}")
            return False

    async def build(
        self,
        project_id: str,
        user_prompt: str,
        progress: Optional[Callable] = None,
        genre_id: Optional[str] = None,
        brief: Optional[str] = None,
    ) -> Dict[str, Any]:
        project = self.projects_dir / project_id
        if project.exists():
            shutil.rmtree(project)
        project.mkdir(parents=True)

        async def say(message: str):
            logger.info(f"[{project_id}] {message}")
            if progress:
                await progress(message)

        try:
            # ---- 1. plan ----
            await say("Designing your game...")
            plan_data = await self.generator.generate_plan(
                user_prompt, genre_id=genre_id, brief=brief
            )
            plan_data.setdefault("genre", genre_id or "platformer")
            plan = GodotPlan.from_dict(plan_data)

            specs = self._spec_index(plan_data)

            # Persist the plan: a follow-up request edits this project rather
            # than generating a new game from scratch.
            project.mkdir(parents=True, exist_ok=True)
            (project / "mamba_plan.json").write_text(
                json.dumps(plan_data, indent=2), encoding="utf-8"
            )

            # ---- 2. scaffold config first ----
            # project.godot must exist before any file can be checked in-engine.
            scaffold(project, plan, {})

            # ---- 2b. real sprites, before any file is written ----
            # The AI can only reference art that is already on disk, so this
            # must happen before the scenes are generated.
            await say("Fetching game art...")
            self.generator.sprites = await self.assets.provision(
                plan_data.get("genre") or "platformer", project
            )

            # ---- 3. scripts, each checked as it lands ----
            # Scripts are independent, so they stay concurrent while each one
            # loops on its own lint + compile check until green.
            script_specs = [s for s in plan_data.get("scripts", []) or [] if s.get("path")]
            await say(f"Writing {len(script_specs)} scripts...")

            script_results = await asyncio.gather(*[
                self.generator.generate_checked(
                    plan_data, spec["path"], spec, self._script_checker(project, plan)
                )
                for spec in script_specs
            ], return_exceptions=True)

            files: Dict[str, str] = {}
            for result in script_results:
                if isinstance(result, Exception):
                    logger.error(f"Script generation failed: {result}")
                    continue
                path, content, remaining = result
                if content:
                    files[path] = content
                    write_ai_files(project, {path: content})
                if remaining:
                    logger.warning(f"{path} shipped with {len(remaining)} unresolved issue(s)")

            # ---- 4. scenes, checked once the scripts they reference exist ----
            scene_specs = [s for s in plan_data.get("scenes", []) or [] if s.get("path")]
            await say(f"Building {len(scene_specs)} scenes...")

            scene_results = await asyncio.gather(*[
                self.generator.generate_checked(
                    plan_data, spec["path"], spec, self._scene_checker(project)
                )
                for spec in scene_specs
            ], return_exceptions=True)

            for result in scene_results:
                if isinstance(result, Exception):
                    logger.error(f"Scene generation failed: {result}")
                    continue
                path, content, remaining = result
                if content:
                    files[path] = content
                    write_ai_files(project, {path: content})

            if not files:
                raise ValueError("The AI produced no files")

            # Every file the plan promised must exist. Shipping without one is
            # how a game ends up with a Player node and no player.gd — an inert
            # box that passes every other gate because it never throws.
            promised = [s["path"] for s in script_specs] + [s["path"] for s in scene_specs]
            missing = [rel for rel in promised if not (project / rel).exists()]
            if missing:
                logger.warning(f"Missing after generation: {missing} — retrying those")
                retry = await asyncio.gather(*[
                    self.generator.generate_checked(
                        plan_data, rel, specs.get(rel, {}),
                        self._script_checker(project, plan) if rel.endswith(".gd")
                        else self._scene_checker(project),
                    )
                    for rel in missing
                ], return_exceptions=True)
                for result in retry:
                    if isinstance(result, Exception) or not result:
                        continue
                    rel, content, _ = result
                    if content:
                        files[rel] = content
                        write_ai_files(project, {rel: content})

                still = [rel for rel in promised if not (project / rel).exists()]
                if still:
                    raise ValueError(
                        f"These files could not be generated: {still}. "
                        f"The game would be incomplete, so the build is being failed "
                        f"rather than shipping something broken."
                    )

            # ---- 5. whole-project gates ----
            result = None
            for round_no in range(self.max_repair_rounds + 1):
                await say(
                    "Checking your game in Godot..." if round_no == 0
                    else f"Fixing issues (round {round_no})..."
                )
                result = await self.validator.validate_all(
                    project, plan.scripts, self._asserted_nodes(plan),
                    list(plan.autoloads.keys())
                )
                if result.ok:
                    break
                if round_no == self.max_repair_rounds:
                    logger.error(
                        f"Still {len(result.issues)} issue(s) after "
                        f"{self.max_repair_rounds} repair round(s)"
                    )
                    break

                repaired = await self._repair_round(project, plan_data, specs, result)
                if not repaired:
                    logger.warning("Nothing could be repaired; stopping early")
                    break

            validation_ok = bool(result and result.ok)

            # ---- 6. import (assets must be imported or they miss the .pck) ----
            await say("Importing game resources...")
            await self.validator.import_project(project)

            # ---- 7. runtime smoke test: does it actually RUN? ----
            await say("Play-testing your game...")
            runtime = await self.runtime.smoke_test(project, plan.main_scene, autoloads=plan.autoloads,
                                                expect=expected_content(plan_data))
            if not runtime.ok:
                repaired = await self._repair_round(project, plan_data, specs, runtime)
                if repaired:
                    await say("Fixing what the play-test found...")
                    runtime = await self.runtime.smoke_test(project, plan.main_scene, autoloads=plan.autoloads,
                                                expect=expected_content(plan_data))
            runtime_ok = runtime.ok

            # ---- 8. refuse to ship something that is not a game ----
            # The pipeline used to export unconditionally and report success
            # based on whether files appeared on disk. Every gate result was
            # computed, logged and then ignored — which is how an inert player
            # and an empty level both reached a user.
            blocking = (result.blocking() if result else []) + runtime.blocking()
            if blocking:
                reasons = [i.as_prompt_line() for i in blocking]
                logger.error(f"❌ Refusing to ship: {len(blocking)} blocking issue(s)")
                for line in reasons[:6]:
                    logger.error(f"   {line}")
                return {
                    "success": False,
                    "project_id": project_id,
                    "project_path": str(project),
                    "files": sorted(files.keys()),
                    "plan": plan_data,
                    "validation_passed": False,
                    "runtime_passed": False,
                    "issues": reasons,
                    "error": "The generated game is not playable: " + reasons[0],
                }

            # ---- 9. export ----
            await say("Building the playable version...")
            export = await self._export_web(project)

            return {
                "success": export["success"],
                "project_id": project_id,
                "project_path": str(project),
                "dist_path": export.get("dist"),
                "files": sorted(files.keys()),
                "plan": plan_data,
                "validation_passed": validation_ok,
                "runtime_passed": runtime_ok,
                "issues": [i.as_prompt_line() for i in (result.issues if result else [])],
                "error": export.get("error"),
            }

        except Exception as e:
            logger.error(f"Godot build failed for {project_id}: {e}", exc_info=True)
            return {
                "success": False,
                "project_id": project_id,
                "project_path": str(project),
                "error": str(e),
            }

    async def iterate(
        self,
        project_id: str,
        change_request: str,
        progress: Optional[Callable] = None,
    ) -> Dict[str, Any]:
        """
        Apply a change to an EXISTING game.

        Only the files that need to change are rewritten; everything else is
        left alone. Rebuilding from scratch would throw away a game that already
        passed every gate, and would ignore what the user actually asked for.
        """
        project = self.projects_dir / project_id

        async def say(message: str):
            logger.info(f"[{project_id}] {message}")
            if progress:
                await progress(message)

        plan_file = project / "mamba_plan.json"
        if not project.exists() or not plan_file.exists():
            return {"success": False, "project_id": project_id,
                    "error": "No previous build found for this project; generating fresh."}

        try:
            plan_data = json.loads(plan_file.read_text(encoding="utf-8"))
            plan = GodotPlan.from_dict(plan_data)
            specs = self._spec_index(plan_data)

            # Current contents, so the AI edits rather than reinvents.
            current: Dict[str, str] = {}
            for rel in list(plan.scripts) + list(plan.scenes.keys()):
                f = project / rel
                if f.exists():
                    current[rel] = f.read_text(encoding="utf-8")

            self.generator.sprites = await self.assets.provision(
                plan_data.get("genre") or "platformer", project
            )

            await say("Working out what to change...")
            targets = await self.generator.plan_edit(plan_data, change_request, current)
            if not targets:
                return {"success": False, "project_id": project_id,
                        "error": "Could not work out which files to change."}

            await say(f"Updating {len(targets)} file(s)...")
            results = await asyncio.gather(*[
                self.generator.edit_file(
                    plan_data, path, specs.get(path, {}),
                    current.get(path, ""), change_request,
                    self._script_checker(project, plan) if path.endswith(".gd")
                    else self._scene_checker(project),
                )
                for path in targets
            ], return_exceptions=True)

            changed = []
            for path, result in zip(targets, results):
                if isinstance(result, Exception) or not result:
                    logger.warning(f"Edit failed for {path}: {result}")
                    continue
                write_ai_files(project, {path: result})
                changed.append(path)

            if not changed:
                return {"success": False, "project_id": project_id,
                        "error": "No files could be updated."}

            await say("Checking your changes in Godot...")
            result = await self.validator.validate_all(
                project, plan.scripts, self._asserted_nodes(plan), list(plan.autoloads.keys())
            )
            if not result.ok:
                await self._repair_round(project, plan_data, specs, result)
                result = await self.validator.validate_all(
                    project, plan.scripts, self._asserted_nodes(plan),
                    list(plan.autoloads.keys())
                )

            await self.validator.import_project(project)

            await say("Play-testing your changes...")
            runtime = await self.runtime.smoke_test(
                project, plan.main_scene, autoloads=plan.autoloads,
                expect=expected_content(plan_data),
            )
            if not runtime.ok:
                if await self._repair_round(project, plan_data, specs, runtime):
                    runtime = await self.runtime.smoke_test(
                        project, plan.main_scene, autoloads=plan.autoloads,
                        expect=expected_content(plan_data),
                    )

            await say("Rebuilding the playable version...")
            export = await self._export_web(project)

            return {
                "success": export["success"],
                "project_id": project_id,
                "project_path": str(project),
                "dist_path": export.get("dist"),
                "files": changed,
                "plan": plan_data,
                "validation_passed": result.ok,
                "runtime_passed": runtime.ok,
                "iterated": True,
                "error": export.get("error"),
            }

        except Exception as e:
            logger.error(f"Iteration failed for {project_id}: {e}", exc_info=True)
            return {"success": False, "project_id": project_id, "error": str(e)}

    # ---------- per-file checkers ----------

    def _script_checker(self, project: Path, plan):
        """lint (instant) then Godot's real parser (~1.5s). Every script."""
        async def check(path: str, content: str) -> List[str]:
            from services.gdscript_lint import lint_gdscript

            problems = [i.as_prompt_line() for i in
                        lint_gdscript(content, list(plan.input_actions.keys()))]
            if problems:
                return problems

            # Only pay for the engine once the cheap checks are clean.
            write_ai_files(project, {path: content})
            result = await self.validator.check_scripts(
                project, [path], list(plan.autoloads.keys())
            )
            return [i.as_prompt_line() for i in result.issues]

        return check

    def _scene_checker(self, project: Path):
        """Structural lint, then load+instantiate inside Godot."""
        async def check(path: str, content: str) -> List[str]:
            from services.gdscript_lint import lint_tscn

            problems = [i.as_prompt_line() for i in lint_tscn(content)]
            if problems:
                return problems

            write_ai_files(project, {path: content})
            result = await self.validator.check_scenes(project, {path: []})
            return [i.as_prompt_line() for i in result.issues]

        return check

    # ---------- helpers ----------

    def _asserted_nodes(self, plan) -> Dict[str, List[str]]:
        """
        Which declared node paths are worth asserting.

        Only the MAIN scene's, because the level script looks those containers
        up by name — getting them wrong genuinely breaks the game.

        Entity scenes (Coin, Enemy, Player) are excluded on purpose: the planner
        invents names before the file is written and the file-writer reasonably
        picks different ones. Asserting a name one call guessed for another to
        implement fails perfectly good scenes. What actually matters about an
        entity scene — that it draws something and has a script — is covered by
        the NO_VISUAL and NO_SCRIPT gates instead.
        """
        return {
            scene: (nodes if scene == plan.main_scene else [])
            for scene, nodes in plan.scenes.items()
        }

    def _spec_index(self, plan_data: Dict) -> Dict[str, Dict]:
        specs: Dict[str, Dict] = {}
        for entry in plan_data.get("scenes", []) or []:
            if entry.get("path"):
                specs[entry["path"]] = entry
        for entry in plan_data.get("scripts", []) or []:
            if entry.get("path"):
                specs[entry["path"]] = entry
        return specs

    async def _repair_round(
        self,
        project: Path,
        plan_data: Dict,
        specs: Dict[str, Dict],
        result,
    ) -> bool:
        """Regenerate only the files Godot complained about."""
        repaired_any = False
        tasks = []

        for file_path, issues in result.by_file().items():
            target = project / file_path
            if not target.exists():
                # An issue attributed to 'project' or an unknown path is not
                # something we can rewrite file-by-file.
                logger.debug(f"No rewritable file for issue group '{file_path}'")
                continue
            tasks.append((
                file_path,
                self.generator.repair_file(
                    plan_data,
                    file_path,
                    specs.get(file_path, {}),
                    target.read_text(encoding="utf-8"),
                    [i.message if not i.line else f"line {i.line}: {i.message}" for i in issues],
                )
            ))

        if not tasks:
            return False

        results = await asyncio.gather(*(t[1] for t in tasks), return_exceptions=True)
        updates: Dict[str, str] = {}
        for (file_path, _), fixed in zip(tasks, results):
            if isinstance(fixed, Exception) or not fixed:
                logger.warning(f"Repair failed for {file_path}")
                continue
            updates[file_path] = fixed
            repaired_any = True

        if updates:
            write_ai_files(project, updates)

        return repaired_any

    async def _export_web(self, project: Path) -> Dict[str, Any]:
        """
        Export the Web preset. The target directory must already exist or the
        export fails, and the preset name must match export_presets.cfg exactly.
        """
        # Godot resolves the export path relative to the project directory it
        # was given with --path, so a relative target silently points somewhere
        # that does not exist. Both must be absolute.
        project = project.resolve()
        dist = project / "dist"
        dist.mkdir(parents=True, exist_ok=True)

        cmd = [
            self.godot, "--headless", "--path", str(project),
            "--export-release", "Web", str((dist / "index.html").resolve()),
        ]
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
            )
            out, _ = await asyncio.wait_for(proc.communicate(), timeout=600)
            text = out.decode("utf-8", errors="replace")
        except asyncio.TimeoutError:
            return {"success": False, "error": "Godot export timed out after 600s"}
        except FileNotFoundError:
            return {"success": False, "error": f"Godot not found at '{self.godot}'"}

        index = dist / "index.html"
        wasm = dist / "index.wasm"

        if not index.exists() or not wasm.exists():
            tail = "\n".join(text.strip().splitlines()[-8:])
            logger.error(f"Export produced no artifacts:\n{tail}")
            return {"success": False, "error": f"Export produced no artifacts. {tail}"}

        size_mb = sum(f.stat().st_size for f in dist.rglob("*") if f.is_file()) / 1_048_576
        logger.info(f"✅ Exported web build: {size_mb:.1f} MB -> {dist}")
        return {"success": True, "dist": str(dist), "size_mb": round(size_mb, 1)}
