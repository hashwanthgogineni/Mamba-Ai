"""
CC0 sprite library, sourced from the Kenney mirror on GitHub.

Design decisions that matter:

* ONE PACK PER GENRE. Searching per-asset returns a 512px realistic ghost next
  to a 16px pixel pellet, which looks worse than the flat rectangles it
  replaces. A single Kenney pack is one artist, one grid, one palette.

* THE AI NEVER PICKS A URL. It is handed a manifest of files already on disk
  and may only reference those. An invented path is a broken scene.

* CACHED ON DISK. The first game of a genre downloads a handful of PNGs; every
  game after that is instant and works offline.

Licence: Kenney assets are CC0 1.0 (public domain) — no attribution required,
commercial use fine, safe to redistribute inside generated games.

Every path below was verified to exist in the mirror's git tree.
"""

import asyncio
import logging
from pathlib import Path
from typing import Dict, Optional

import httpx

logger = logging.getLogger(__name__)

RAW = "https://raw.githubusercontent.com/iwenzhou/kenney/master"
ART = "Art (5190 files)"

_PLATFORMER = f"{ART}/Platformer assets (1330 assets)/Base pack (360 assets)"
_SHOOTER = f"{ART}/Space shooter assets (300 assets)"
_RPG = f"{ART}/RPG pack (230 assets)"

GENRE_SPRITES: Dict[str, Dict[str, str]] = {
    "platformer": {
        "player":      f"{_PLATFORMER}/Player/p1_stand.png",
        "player_jump": f"{_PLATFORMER}/Player/p1_jump.png",
        "enemy":       f"{_PLATFORMER}/Enemies/slimeWalk1.png",
        "enemy_fly":   f"{_PLATFORMER}/Enemies/flyFly1.png",
        "collectible": f"{_PLATFORMER}/Items/coinGold.png",
        "platform":    f"{_PLATFORMER}/Tiles/grassMid.png",
        "box":         f"{_PLATFORMER}/Tiles/box.png",
        "background":  f"{_PLATFORMER}/bg.png",
    },
    "maze": {
        "player":      f"{_PLATFORMER}/Player/p1_front.png",
        "enemy":       f"{_PLATFORMER}/Enemies/slimeWalk1.png",
        "collectible": f"{_PLATFORMER}/Items/coinBronze.png",
        "power":       f"{_PLATFORMER}/Items/coinGold.png",
        "wall":        f"{_PLATFORMER}/Tiles/brickWall.png",
    },
    "shooter": {
        "player":    f"{_SHOOTER}/PNG/playerShip1_blue.png",
        "enemy":     f"{_SHOOTER}/PNG/Enemies/enemyBlack1.png",
        "enemy_alt": f"{_SHOOTER}/PNG/Enemies/enemyRed2.png",
        "bullet":    f"{_SHOOTER}/PNG/Lasers/laserBlue01.png",
        "explosion": f"{_SHOOTER}/PNG/Meteors/meteorBrown_big1.png",
    },
    "runner": {
        "player":      f"{_PLATFORMER}/Player/p1_walk/PNG/p1_walk01.png",
        "obstacle":    f"{_PLATFORMER}/Tiles/box.png",
        "collectible": f"{_PLATFORMER}/Items/coinGold.png",
        "platform":    f"{_PLATFORMER}/Tiles/grassMid.png",
        "background":  f"{_PLATFORMER}/bg.png",
    },
    "topdown": {
        "player":      f"{_PLATFORMER}/Player/p1_front.png",
        "enemy":       f"{_PLATFORMER}/Enemies/slimeWalk1.png",
        "collectible": f"{_PLATFORMER}/Items/coinGold.png",
        "wall":        f"{_RPG}/PNG/rpgTile000.png",
        "floor":       f"{_RPG}/PNG/rpgTile001.png",
    },
    "puzzle": {
        "tile_a": f"{_PLATFORMER}/Items/coinGold.png",
        "tile_b": f"{_PLATFORMER}/Items/coinSilver.png",
        "tile_c": f"{_PLATFORMER}/Items/coinBronze.png",
        "tile_d": f"{_PLATFORMER}/Items/gemBlue.png",
    },
}


class AssetLibrary:
    def __init__(self, cache_dir: str = "./asset_cache", timeout: int = 30):
        self.cache = Path(cache_dir)
        self.cache.mkdir(parents=True, exist_ok=True)
        self.timeout = timeout

    def _cache_path(self, repo_path: str) -> Path:
        return self.cache / repo_path.replace("/", "__").replace(" ", "_")

    async def _fetch(self, client: httpx.AsyncClient, repo_path: str) -> Optional[Path]:
        target = self._cache_path(repo_path)
        if target.exists() and target.stat().st_size > 0:
            return target
        try:
            response = await client.get(f"{RAW}/{repo_path}", follow_redirects=True)
            if response.status_code != 200 or not response.content:
                logger.warning(f"Asset fetch {response.status_code}: {repo_path}")
                return None
            target.write_bytes(response.content)
            return target
        except Exception as e:
            logger.warning(f"Asset fetch failed for {repo_path}: {e}")
            return None

    async def provision(self, genre_id: str, project: Path) -> Dict[str, str]:
        """
        Download (or reuse) this genre's sprites and copy them into the
        project's assets/ folder.

        Returns role -> "assets/<file>.png" for roles CONFIRMED on disk.
        Anything that failed is simply absent, so the AI is never told about a
        file it cannot use.
        """
        sprites = GENRE_SPRITES.get(genre_id) or GENRE_SPRITES["platformer"]
        assets_dir = project / "assets"
        assets_dir.mkdir(parents=True, exist_ok=True)

        cached_before = sum(1 for p in sprites.values() if self._cache_path(p).exists())

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            results = await asyncio.gather(
                *[self._fetch(client, path) for path in sprites.values()],
                return_exceptions=True,
            )

        manifest: Dict[str, str] = {}
        for (role, _), cached in zip(sprites.items(), results):
            if isinstance(cached, Exception) or cached is None:
                continue
            try:
                (assets_dir / f"{role}.png").write_bytes(cached.read_bytes())
                manifest[role] = f"assets/{role}.png"
            except Exception as e:
                logger.warning(f"Could not place {role}: {e}")

        logger.info(
            f"🎨 {len(manifest)}/{len(sprites)} sprites ready for '{genre_id}' "
            f"({cached_before} already cached)"
        )
        return manifest


def manifest_block(manifest: Dict[str, str]) -> str:
    """The sprite instruction injected into every file-writing prompt."""
    if not manifest:
        return (
            "NO SPRITE FILES ARE AVAILABLE. Draw everything with Polygon2D using "
            "the palette colours. Do NOT reference any .png path."
        )
    lines = "\n".join(f"  {role:14} res://{path}" for role, path in sorted(manifest.items()))
    return f"""SPRITE FILES AVAILABLE IN THIS PROJECT (these exist on disk right now):
{lines}

USE THEM — this is what makes the game look like a game instead of coloured boxes:
- Use Sprite2D with a texture for the player, enemies, collectibles and tiles.
  Do NOT use Polygon2D for these.
- Declare each texture once per scene:
    [ext_resource type="Texture2D" path="res://assets/player.png" id="tex_player"]
  then on the node:
    [node name="Sprite" type="Sprite2D" parent="Player"]
    texture = ExtResource("tex_player")
- You may ONLY reference paths from the list above. Any other path does not
  exist and will break the scene.
- Keep CollisionShape2D nodes as they are: sprites are visuals, not collision.
- Repeat a tile sprite across a platform's width rather than stretching it."""
