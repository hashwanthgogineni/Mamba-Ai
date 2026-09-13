#!/usr/bin/env python3
"""
Build and run every genre template in Godot. NO AI calls, costs nothing.

Each template is assembled into a throwaway project exactly the way the builder
assembles a real game — emitted scenes, real sprites, the hand-written scripts —
then booted for 300 frames and asserted on.

    python core/scripts/check_templates.py
    python core/scripts/check_templates.py platformer      # just one

A template that fails here would fail for a user, so this must be green before
a genre is offered.
"""

import asyncio
import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "core"))

from services import level_data, scene_templates as st  # noqa: E402
from services.asset_library import AssetLibrary  # noqa: E402
from services.godot_emitter import (  # noqa: E402
    GodotPlan, write_export_presets, write_icon, write_project_godot,
)
from services.godot_runtime import GodotRuntime  # noqa: E402
from services.godot_validator import GodotValidator  # noqa: E402

GODOT = os.getenv("GODOT_PATH", "/opt/homebrew/bin/godot")
TEMPLATES = ROOT / "core" / "templates"

GREEN, RED, DIM, RESET = "\033[32m", "\033[31m", "\033[2m", "\033[0m"


async def build_project(genre: str, into: Path) -> tuple[Path, dict]:
    """Assemble a template into a runnable project, as the builder would."""
    project = into / genre
    (project / "scripts").mkdir(parents=True)
    (project / "assets").mkdir(parents=True)

    for script in (TEMPLATES / genre / "scripts").glob("*.gd"):
        if script.name == "level_data.gd":
            continue  # rendered below, exactly as the builder does it
        shutil.copy(script, project / "scripts" / script.name)

    # Render level_data.gd from an empty plan, so this exercises the same code
    # path a real build uses — and proves the per-genre defaults are playable.
    level_data.write(project, {"title": f"{genre} template", "mechanics": {}, "level": {}}, genre)

    sprites = await AssetLibrary(cache_dir=str(ROOT / "core" / "asset_cache")).provision(
        genre, project
    )

    st.emit_all(project, genre, sprites)

    plan = GodotPlan(
        title=f"{genre.title()} Template",
        main_scene="scenes/Main.tscn",
        autoloads={"GameManager": "scripts/game_manager.gd"},
    )
    write_project_godot(project, plan)
    write_export_presets(project)
    write_icon(project)
    return project, sprites


async def check(genre: str) -> bool:
    with tempfile.TemporaryDirectory() as tmp:
        project, sprites = await build_project(genre, Path(tmp))

        scripts = [f"scripts/{p.name}" for p in (project / "scripts").glob("*.gd")]
        scenes = {f"scenes/{p.name}": [] for p in (project / "scenes").glob("*.tscn")}

        validator = GodotValidator(GODOT)
        static = await validator.validate_all(project, scripts, scenes, ["GameManager"])

        runtime = await GodotRuntime(GODOT).smoke_test(
            project, "scenes/Main.tscn", frames=300,
            autoloads={"GameManager": "res://scripts/game_manager.gd"},
            genre=genre,
        )

        ok = static.ok and runtime.ok
        mark = f"{GREEN}PASS{RESET}" if ok else f"{RED}FAIL{RESET}"
        print(f"  {genre:12} {mark}   scripts={len(scripts)} scenes={len(scenes)} sprites={len(sprites)}")
        for issue in (static.issues + runtime.issues)[:5]:
            print(f"      {RED}{issue.as_prompt_line()[:110]}{RESET}")
        return ok


async def main() -> int:
    wanted = sys.argv[1:]
    genres = sorted(p.name for p in TEMPLATES.iterdir() if (p / "scripts").is_dir())
    if wanted:
        genres = [g for g in genres if g in wanted]

    if not genres:
        print(f"{RED}No templates found in {TEMPLATES}{RESET}")
        return 2

    print(f"{DIM}{len(genres)} template(s) · godot={GODOT} · no AI calls{RESET}\n")

    results = [await check(g) for g in genres]

    print()
    failed = results.count(False)
    if failed:
        print(f"{RED}{failed} of {len(results)} template(s) failed.{RESET}")
        return 1
    print(f"{GREEN}All {len(results)} template(s) build, compile and run.{RESET}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
