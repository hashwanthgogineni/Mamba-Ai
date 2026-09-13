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
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger(__name__)

RAW = "https://raw.githubusercontent.com/iwenzhou/kenney/master"
ART = "Art (5190 files)"

# The whole CC0 library is vendored in the repo, so sprite resolution is a local
# file lookup: instant, offline, and free. 4,006 PNGs, 39 MB.
LOCAL_ART = Path(__file__).resolve().parent.parent / "asset_library_raw" / ART

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

    async def _fetch(self, client, repo_path: str) -> Optional[Path]:
        """
        Resolve a sprite. The whole CC0 library is vendored on disk, so this is
        a local lookup; the network is only a fallback for a path the vendored
        copy somehow lacks.
        """
        local = LOCAL_ART / repo_path.replace(f"{ART}/", "")
        if local.exists() and local.stat().st_size > 0:
            return local

        target = self._cache_path(repo_path)
        if target.exists() and target.stat().st_size > 0:
            return target

        if client is None:
            logger.warning(f"Sprite not in the local library: {repo_path}")
            return None
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

    async def provision(
        self, genre_id: str, project: Path, prompt: str = "", seed: int = 0
    ) -> Dict[str, str]:
        """
        Download (or reuse) this genre's sprites and copy them into the
        project's assets/ folder.

        Returns role -> "assets/<file>.png" for roles CONFIRMED on disk.
        Anything that failed is simply absent, so the AI is never told about a
        file it cannot use.
        """
        sprites = variant_sprites(genre_id, prompt, seed)
        assets_dir = project / "assets"
        assets_dir.mkdir(parents=True, exist_ok=True)

        needs_network = any(
            not (LOCAL_ART / path.replace(f"{ART}/", "")).exists()
            and not self._cache_path(path).exists()
            for path in sprites.values()
        )

        if needs_network:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                results = await asyncio.gather(
                    *[self._fetch(client, path) for path in sprites.values()],
                    return_exceptions=True,
                )
        else:
            results = await asyncio.gather(
                *[self._fetch(None, path) for path in sprites.values()],
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
            f"🎨 {len(manifest)}/{len(sprites)} sprites ready for '{genre_id}'"
            + ("" if needs_network else " (all local)")
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

# ---------------------------------------------------------------------------
# Theme variants
#
# A fixed sprite set per genre meant every platformer looked identical no matter
# what was asked for. Kenney ships themed tile packs and several character and
# pickup variants, so the prompt can choose. Only art changes — the template and
# its logic stay fixed, which is what keeps generation reliable.
# ---------------------------------------------------------------------------

_ICE = f"{ART}/Platformer assets (1330 assets)/Ice pack (100 assets)"
_CANDY = f"{ART}/Platformer assets (1330 assets)/Candy pack (95 assets)"
_SHROOM = f"{ART}/Platformer assets (1330 assets)/Mushroom pack (50 assets)"

# keyword -> overrides applied on top of the genre's default sprite set.
THEMES: Dict[str, Dict[str, Any]] = {
    "ice": {
        "words": ("ice", "icy", "snow", "snowy", "frozen", "winter", "arctic",
                  "frost", "glacier", "tundra", "cold"),
        "sprites": {
            "platform": f"{_ICE}/PNG/snowMid.png",
            "box":      f"{_PLATFORMER}/Tiles/snowCenter.png",
            "enemy":    f"{_PLATFORMER}/Enemies/flyFly1.png",
            "background": f"{_PLATFORMER}/bg.png",
        },
    },
    "candy": {
        "words": ("candy", "sweet", "cake", "sugar", "dessert", "chocolate",
                  "lolli", "bakery", "donut"),
        "sprites": {
            "platform": f"{_CANDY}/PNG/cakeMid.png",
            "box":      f"{_CANDY}/PNG/cakeCenter.png",
            "collectible": f"{_PLATFORMER}/Items/gemRed.png",
            "enemy":    f"{_PLATFORMER}/Enemies/snailWalk1.png",
        },
    },
    "forest": {
        "words": ("forest", "mushroom", "jungle", "woods", "wood", "nature",
                  "shroom", "swamp", "garden"),
        "sprites": {
            "platform": f"{_PLATFORMER}/Tiles/grassMid.png",
            "background": f"{_SHROOM}/Backgrounds/bg_shroom.png",
            "enemy":    f"{_PLATFORMER}/Enemies/snailWalk1.png",
            "collectible": f"{_PLATFORMER}/Items/gemGreen.png",
        },
    },
    "desert": {
        "words": ("desert", "sand", "sandy", "dune", "egypt", "pyramid",
                  "oasis", "wasteland"),
        "sprites": {
            "platform": f"{_PLATFORMER}/Tiles/sandMid.png",
            "background": f"{_SHROOM}/Backgrounds/bg_desert.png",
            "enemy":    f"{_PLATFORMER}/Enemies/pokerMad.png",
        },
    },
    "castle": {
        "words": ("castle", "dungeon", "stone", "medieval", "knight", "fortress",
                  "crypt", "tower", "ruins", "cave"),
        "sprites": {
            "platform": f"{_PLATFORMER}/Tiles/stoneMid.png",
            "background": f"{_PLATFORMER}/bg_castle.png",
            "enemy":     f"{_PLATFORMER}/Enemies/blockerMad.png",
            "collectible": f"{_PLATFORMER}/Items/gemBlue.png",
        },
    },
}

# Character and pickup variants, rotated so two runs of the same prompt differ.
CHARACTERS = [
    f"{_PLATFORMER}/Player/p1_front.png",
    f"{_PLATFORMER}/Player/p2_front.png",
    f"{_PLATFORMER}/Player/p3_front.png",
]
PICKUPS = [
    f"{_PLATFORMER}/Items/coinGold.png",
    f"{_PLATFORMER}/Items/coinSilver.png",
    f"{_PLATFORMER}/Items/gemBlue.png",
    f"{_PLATFORMER}/Items/gemGreen.png",
    f"{_PLATFORMER}/Items/gemYellow.png",
]
ENEMIES = [
    f"{_PLATFORMER}/Enemies/slimeWalk1.png",
    f"{_PLATFORMER}/Enemies/flyFly1.png",
    f"{_PLATFORMER}/Enemies/snailWalk1.png",
    f"{_PLATFORMER}/Enemies/blockerMad.png",
    f"{_PLATFORMER}/Enemies/pokerMad.png",
]


def theme_for(prompt: str) -> Optional[str]:
    """First theme whose keywords appear in the prompt."""
    text = (prompt or "").lower()
    for name, spec in THEMES.items():
        if any(word in text for word in spec["words"]):
            return name
    return None


def variant_sprites(genre_id: str, prompt: str = "", seed: int = 0) -> Dict[str, str]:
    """
    The genre's sprite set, with a theme applied when the prompt asks for one
    and the character/pickup/enemy rotated by `seed` otherwise.

    Two identical prompts still differ, because the seed varies per project —
    without that, every platformer looked like every other platformer.
    """
    sprites = dict(GENRE_SPRITES.get(genre_id) or GENRE_SPRITES["platformer"])

    theme = theme_for(prompt)
    if theme:
        sprites.update(THEMES[theme]["sprites"])
        logger.info(f"🎨 Theme '{theme}' matched the prompt")

    # Only the platformer-family genres share this art; the others have their
    # own packs where rotating would mix styles.
    if genre_id in ("platformer", "runner", "topdown", "maze"):
        if "player" in sprites:
            sprites["player"] = CHARACTERS[seed % len(CHARACTERS)]
        if "collectible" in sprites and not theme:
            sprites["collectible"] = PICKUPS[seed % len(PICKUPS)]
        if "enemy" in sprites and not theme:
            sprites["enemy"] = ENEMIES[seed % len(ENEMIES)]

    return sprites
