#!/usr/bin/env python3
"""
Regression suite for the validation gates. Uses NO AI and costs nothing.

Every generated project on disk is a fixture. Some are known-good, several are
known-broken in specific ways, and each broken one is a bug that once reached a
user. Running the gates over all of them proves the gates still catch what they
were built to catch.

    python core/scripts/check_gates.py            # report on every project
    python core/scripts/check_gates.py --expect   # assert known bugs are caught

Add a case to EXPECTED whenever a new class of bug is found, so it can never
silently come back.
"""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "core"))

from services.godot_runtime import GodotRuntime, expected_content  # noqa: E402
from services.godot_validator import GodotValidator, is_blocking  # noqa: E402

GODOT = os.getenv("GODOT_PATH", "/opt/homebrew/bin/godot")
PROJECTS = ROOT / "core" / "godot_projects"
FIXTURES = ROOT / "core" / "tests" / "fixtures"

GREEN, RED, YELLOW, DIM, RESET = "\033[32m", "\033[31m", "\033[33m", "\033[2m", "\033[0m"

# project id prefix -> the marker its known bug must still produce.
# These are real failures that shipped to a user before the gate existed.
# Hand-built minimal projects, committed to the repo, each reproducing one
# real bug that once reached a user. They live here rather than pointing at
# generated output because generated projects get pruned — and a suite whose
# fixtures have vanished will happily report success having tested nothing.
EXPECTED = {
    "no_script":   "NO_SCRIPT",      # CharacterBody2D with no script: inert, silent
    "no_visual":   "NO_VISUAL",      # entity scene with collision but nothing drawn
    "empty_level": "TOO_FEW_ENEMY",  # plan declares enemies, level contains none
}


def scan(project: Path) -> dict:
    """Cheap facts about a project, no engine needed."""
    scenes = sorted(p for p in (project / "scenes").glob("*.tscn")) if (project / "scenes").exists() else []
    scripts = sorted(p for p in (project / "scripts").glob("*.gd")) if (project / "scripts").exists() else []
    plan_file = project / "mamba_plan.json"
    plan = json.loads(plan_file.read_text()) if plan_file.exists() else {}
    return {
        "scenes": [str(p.relative_to(project)) for p in scenes],
        "scripts": [str(p.relative_to(project)) for p in scripts],
        "plan": plan,
        "sprites": len(list((project / "assets").glob("*.png"))) if (project / "assets").exists() else 0,
    }


async def run_gates(project: Path) -> list:
    info = scan(project)
    if not info["scenes"]:
        return []

    validator = GodotValidator(GODOT)
    runtime = GodotRuntime(GODOT)
    plan = info["plan"]

    autoloads = plan.get("autoloads") or {"GameManager": "res://scripts/game_manager.gd"}
    main_scene = (plan.get("main_scene") or "scenes/Main.tscn").replace("res://", "")

    issues = []
    static = await validator.validate_all(
        project, info["scripts"], {s: [] for s in info["scenes"]}, list(autoloads.keys())
    )
    issues += static.issues

    if (project / main_scene).exists():
        live = await runtime.smoke_test(
            project, main_scene, frames=200,
            autoloads=autoloads, expect=expected_content(plan) if plan else None,
        )
        issues += live.issues

    return issues


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expect", action="store_true",
                        help="fail unless every known bug is still detected")
    args = parser.parse_args()


    fixtures = sorted(p for p in FIXTURES.iterdir() if p.is_dir()) if FIXTURES.exists() else []
    generated = sorted(p for p in PROJECTS.iterdir() if p.is_dir()) if PROJECTS.exists() else []
    projects = fixtures + generated
    print(f"{DIM}{len(projects)} project(s) · godot={GODOT} · no AI calls{RESET}\n")

    caught: dict = {}
    for project in projects:
        info = scan(project)
        if not info["scenes"]:
            print(f"  {DIM}{project.name[:12]}  (no scenes, skipped){RESET}")
            continue

        issues = await run_gates(project)
        blocking = [i for i in issues if is_blocking(i)]
        caught[project.name] = " ".join(i.message for i in issues)

        status = f"{GREEN}clean{RESET}" if not blocking else f"{RED}{len(blocking)} blocking{RESET}"
        print(f"  {project.name[:12]}  sprites={info['sprites']:<2} "
              f"scenes={len(info['scenes'])} scripts={len(info['scripts'])}  {status}")
        for issue in blocking[:3]:
            print(f"      {YELLOW}{issue.as_prompt_line()[:110]}{RESET}")

    if not args.expect:
        return 0

    print(f"\n{DIM}--- regression check: known bugs must still be caught ---{RESET}")
    failures = 0
    for prefix, marker in EXPECTED.items():
        messages = next((v for k, v in caught.items() if k.startswith(prefix)), None)
        if messages is None:
            print(f"  {RED}FAIL{RESET}  {prefix}: FIXTURE MISSING — this gate was not tested at all")
            failures += 1
            continue
        if marker in messages:
            print(f"  {GREEN}PASS{RESET}  {prefix} still detected as {marker}")
        else:
            print(f"  {RED}FAIL{RESET}  {prefix}: {marker} is NO LONGER detected — a gate regressed")
            failures += 1

    print()
    if failures:
        print(f"{RED}{failures} gate(s) regressed.{RESET}")
        return 1
    print(f"{GREEN}All known bugs still caught.{RESET}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
