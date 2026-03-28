"""Pixel Boat Cleanup V0.

- Boat automatically moves toward trash
- Boat has a 10-second fuel tank
- When fuel runs out, it returns to base ship to refuel, then resumes cleanup
- Scrollable world with click-drag camera
- Left sidebar HUD (does not cover the map)
- Ocean uses tiled asset from assets/ocean.jpeg
- Boat uses speedboat sprite (assets/smallboat.png currently) with 8-direction facing
- Wake particles trail behind the moving boat
"""

from __future__ import annotations

import asyncio
import math
import random
import sys
from pathlib import Path

import pygame

from intro import play_intro


# Window layout
WINDOW_WIDTH = 1440
WINDOW_HEIGHT = 820
SIDEBAR_WIDTH = 390
PIXELATE_SCALE = 2
WORLD_ENTITY_SCALE = 0.78
VIEWPORT_RECT = pygame.Rect(SIDEBAR_WIDTH, 0, WINDOW_WIDTH - SIDEBAR_WIDTH, WINDOW_HEIGHT)

# World settings
FPS = 60
WORLD_WIDTH = 5200
WORLD_HEIGHT = 3600
WORLD_RECT = pygame.Rect(0, 0, WORLD_WIDTH, WORLD_HEIGHT)

# Gameplay settings
BOAT_SIZE = (38, 24)
BOAT_SPEED = 165.0
STARTING_TRASH_COUNT = 120
INITIAL_PATCH_COUNT = 22
INITIAL_PATCH_MIN = 12
INITIAL_PATCH_MAX = 24
INITIAL_SCATTER_EXTRA = 90
MAX_TRASH_ITEMS = 700
OFFSCREEN_SPAWN_INTERVAL = 1.15
OFFSCREEN_PATCH_MIN = 8
OFFSCREEN_PATCH_MAX = 18
MAX_FUEL_SECONDS = 20.0
REFUEL_SECONDS = 2.0
MIN_REFUEL_SECONDS = 1.5
BARGE_FUEL_CAPACITY = 1800.0
BARGE_FUEL_START = 1100.0
BARGE_FUEL_UNITS_PER_BOAT_FUEL_SEC = 6.0
BARGE_FUEL_BUY_PRICE = 1.6
HEAVY_SELL_FUEL_REBUY_UNITS = 240.0

# Big base ship in world corner
BASE_RECT = pygame.Rect(WORLD_WIDTH // 2 - 330, WORLD_HEIGHT // 2 - 195, 660, 390)

# Assets
ASSETS_DIR = Path(__file__).resolve().parent / "assets"
OCEAN_TILE_PATH = ASSETS_DIR / "ocean.jpeg"
OCEAN_TILE_SCALE = 0.4
SPEEDBOAT_SPRITE_PATH = ASSETS_DIR / "smallboat.png"
SAILBOAT_SPRITE_PATH = ASSETS_DIR / "sailboat.png"
TUGBOAT_SPRITE_PATH = ASSETS_DIR / "tuboat.png"
HOVERBOAT_SPRITE_PATH = ASSETS_DIR / "hoverboat.png"
HEAVYBOAT_SPRITE_PATH = ASSETS_DIR / "heavyboat.png"
BOAT_SPRITE_SCALE = 1.0 * WORLD_ENTITY_SCALE
BOAT_SPRITE_ANGLE_OFFSET = 90.0  # sprite defaults to facing up; offset aligns it to movement
SPEEDBOAT_DIRECT_SCALE = 1.12
MOTHERSHIP_SPRITE_PATH = ASSETS_DIR / "mothership.png"
MOTHERSHIP_SPRITE_SCALE = 0.90 * WORLD_ENTITY_SCALE

# Colors
BOAT_FILL = (245, 192, 50)
BOAT_OUTLINE = (74, 54, 22)
BASE_FILL = (62, 79, 110)
BASE_DECK = (95, 120, 156)
BASE_OUTLINE = (23, 35, 52)
TEXT_COLOR = (255, 255, 255)
MUTED_TEXT = (255, 255, 255)
SIDEBAR_BG = (168, 128, 82)
SIDEBAR_BORDER = (124, 91, 56)
FUEL_BG = (132, 101, 67)
FUEL_FILL = (102, 221, 132)
FUEL_LOW = (241, 118, 104)
FALLBACK_OCEAN_TOP = (25, 110, 184)
FALLBACK_OCEAN_BOTTOM = (16, 69, 132)
TRASH_DIR = ASSETS_DIR / "trash"
CLEAR_CLOUDS_DIR = ASSETS_DIR / "clouds on clear day"
CLEAR_CLOUD_COUNT = 6
CLEAR_CLOUD_MIN_SPEED = 3.5
CLEAR_CLOUD_MAX_SPEED = 8.0
TRASH_BASE_SPRITE_SCALE = 0.09
TRASH_SPRITE_SCALE = TRASH_BASE_SPRITE_SCALE * WORLD_ENTITY_SCALE
TRASH_DRIFT_MIN_SPEED = 2.5
TRASH_DRIFT_MAX_SPEED = 7.0
TRASH_DRIFT_WOBBLE = 1.2
FALLBACK_TRASH_COLOR = (210, 228, 236)
STATE_COLLECTING = "collecting"
STATE_RETURNING = "returning"
STATE_REFUELING = "refueling"

MODE_COLLECT = "collect"
MODE_STOP = "stop"
MODE_SELL = "sell"
SELL_EXIT_POINT = (WORLD_WIDTH - 46, WORLD_HEIGHT // 2)
SELL_TRIP_SECONDS = 3.5
SELL_DOCK_SECONDS = 1.2
PLASTIC_SELL_PRICE = 2.4

BOAT_TYPE = "Speedboat"
# Real-world inspired references (scaled down for gameplay):
# - Speedboat length/persons from Boston Whaler 170 Montauk (17'4", 7 persons).
# - Tugboat speed/crew from Damen Stan Tug class sheets (around 10-11 knots, small crew).
# - Heavy workboat speed/crew from multicat workboat profiles (~9 knots, multi-crew).
# - Hovercraft dimensions from Griffon commercial hovercraft class specs.
BOAT_CAPACITY_BY_TYPE = {
    "Speedboat": 12,
    "Sailboat": 16,
    "Heavy Boat": 36,
    "Tugboat": 28,
    "Hoverboat": 20,
}
BOAT_CREW_MIN_BY_TYPE = {
    "Speedboat": 1,
    "Sailboat": 2,
    "Heavy Boat": 4,
    "Tugboat": 2,
    "Hoverboat": 2,
}
BOAT_CREW_MAX_BY_TYPE = {
    "Speedboat": 2,
    "Sailboat": 4,
    "Heavy Boat": 8,
    "Tugboat": 4,
    "Hoverboat": 3,
}
BOAT_REFUEL_SECONDS_BY_TYPE = {
    "Speedboat": 3.2,
    "Sailboat": 4.0,
    "Heavy Boat": 7.0,
    "Tugboat": 6.0,
    "Hoverboat": 4.5,
}

# Speeds are scaled to in-game pixels/sec from approximate knot classes.
BOAT_SPEED_BY_TYPE = {
    "Speedboat": 145.0,
    "Sailboat": 34.0,
    "Heavy Boat": 44.0,
    "Tugboat": 52.0,
    "Hoverboat": 165.0,
}

# In-game hull sizes use the same global world scale for all boats.
BOAT_BASE_SIZE_BY_TYPE = {
    "Speedboat": (18, 10),
    "Sailboat": (22, 11),
    "Heavy Boat": (30, 14),
    "Tugboat": (32, 15),
    "Hoverboat": (24, 12),
}
BOAT_SIZE_BY_TYPE = {
    boat_type: (
        max(10, int(size[0] * WORLD_ENTITY_SCALE)),
        max(6, int(size[1] * WORLD_ENTITY_SCALE)),
    )
    for boat_type, size in BOAT_BASE_SIZE_BY_TYPE.items()
}

# Sprite display multipliers (applied to BOAT_SIZE_BY_TYPE for visual tuning).
BOAT_SPRITE_SIZE_MULT_BY_TYPE = {
    "Speedboat": 1.0,
    "Sailboat": 7.2,
    "Heavy Boat": 8.0,
    "Tugboat": 8.2,
    "Hoverboat": 7.0,
}

BOAT_COLOR_BY_TYPE = {
    "Sailboat": (238, 226, 188),
    "Speedboat": (245, 192, 50),
    "Heavy Boat": (188, 122, 84),
    "Tugboat": (208, 142, 76),
    "Hoverboat": (166, 220, 214),
}

# Vehicle catalog from info.rtf (for progression/planning UI).
VEHICLE_TYPES = [
    {"name": "Sailboat", "category": "Boat", "crew_min": 2, "crew_max": 4},
    {"name": "Speedboat", "category": "Boat", "crew_min": 1, "crew_max": 2},
    {"name": "Heavy Boat", "category": "Boat", "crew_min": 4, "crew_max": 8},
    {"name": "Hoverboat", "category": "Boat", "crew_min": 2, "crew_max": 3},
    {"name": "Tugboat", "category": "Boat", "crew_min": 2, "crew_max": 4},
    {"name": "Helicopter", "category": "Vehicle", "crew_min": 1, "crew_max": 4},
]


def clamp_camera(camera_x: float, camera_y: float) -> tuple[float, float]:
    max_x = max(0, WORLD_WIDTH - VIEWPORT_RECT.width)
    max_y = max(0, WORLD_HEIGHT - VIEWPORT_RECT.height)
    return max(0.0, min(camera_x, max_x)), max(0.0, min(camera_y, max_y))


def world_to_screen(x: int, y: int, camera_x: float, camera_y: float) -> tuple[int, int]:
    return int(VIEWPORT_RECT.x + x - camera_x), int(y - camera_y)


def world_rect_to_screen(rect: pygame.Rect, camera_x: float, camera_y: float) -> pygame.Rect:
    return pygame.Rect(
        int(VIEWPORT_RECT.x + rect.x - camera_x),
        int(rect.y - camera_y),
        rect.width,
        rect.height,
    )


def draw_offscreen_target_indicator(
    surface: pygame.Surface,
    font: pygame.font.Font,
    camera_x: float,
    camera_y: float,
    target_x: int,
    target_y: int,
    label: str,
    color: tuple[int, int, int],
) -> None:
    sx, sy = world_to_screen(target_x, target_y, camera_x, camera_y)
    if VIEWPORT_RECT.collidepoint(sx, sy):
        return

    cx = VIEWPORT_RECT.centerx
    cy = VIEWPORT_RECT.centery
    dx = sx - cx
    dy = sy - cy
    if abs(dx) < 1e-5 and abs(dy) < 1e-5:
        return

    edge = VIEWPORT_RECT.inflate(-36, -36)
    if edge.width <= 0 or edge.height <= 0:
        return

    tx = (edge.width * 0.5) / max(1e-5, abs(dx))
    ty = (edge.height * 0.5) / max(1e-5, abs(dy))
    t = min(tx, ty)

    px = cx + dx * t
    py = cy + dy * t
    angle = math.atan2(dy, dx)

    tip = (px + math.cos(angle) * 10, py + math.sin(angle) * 10)
    left = (px + math.cos(angle + 2.45) * 8, py + math.sin(angle + 2.45) * 8)
    right = (px + math.cos(angle - 2.45) * 8, py + math.sin(angle - 2.45) * 8)

    pygame.draw.polygon(surface, color, [tip, left, right])
    pygame.draw.polygon(surface, (35, 26, 18), [tip, left, right], width=1)

    label_surf = font.render(label, True, (255, 255, 255))
    lx = int(px + math.cos(angle) * 16 - label_surf.get_width() / 2)
    ly = int(py + math.sin(angle) * 16 - label_surf.get_height() / 2)
    lx = max(VIEWPORT_RECT.left + 4, min(lx, VIEWPORT_RECT.right - label_surf.get_width() - 4))
    ly = max(VIEWPORT_RECT.top + 4, min(ly, VIEWPORT_RECT.bottom - label_surf.get_height() - 4))
    surface.blit(label_surf, (lx, ly))


def load_ocean_tile() -> pygame.Surface | None:
    if not OCEAN_TILE_PATH.exists():
        return None
    try:
        tile = pygame.image.load(str(OCEAN_TILE_PATH)).convert()
        scaled_w = max(8, int(tile.get_width() * OCEAN_TILE_SCALE))
        scaled_h = max(8, int(tile.get_height() * OCEAN_TILE_SCALE))
        return pygame.transform.scale(tile, (scaled_w, scaled_h))
    except pygame.error:
        return None


def load_boat_sprite() -> pygame.Surface | None:
    if not SPEEDBOAT_SPRITE_PATH.exists():
        return None
    try:
        sprite = pygame.image.load(str(SPEEDBOAT_SPRITE_PATH)).convert_alpha()
        scaled_w = max(8, int(sprite.get_width() * BOAT_SPRITE_SCALE))
        scaled_h = max(8, int(sprite.get_height() * BOAT_SPRITE_SCALE))
        return pygame.transform.scale(sprite, (scaled_w, scaled_h))
    except pygame.error:
        return None


def load_boat_sprites() -> dict[str, pygame.Surface]:
    path_map = {
        "Speedboat": SPEEDBOAT_SPRITE_PATH,
        "Sailboat": SAILBOAT_SPRITE_PATH,
        "Heavy Boat": HEAVYBOAT_SPRITE_PATH,
        "Tugboat": TUGBOAT_SPRITE_PATH,
        "Hoverboat": HOVERBOAT_SPRITE_PATH,
    }
    sprites: dict[str, pygame.Surface] = {}
    for boat_type, path in path_map.items():
        if not path.exists():
            continue
        try:
            sprite = pygame.image.load(str(path)).convert_alpha()
        except pygame.error:
            continue

        if boat_type == "Speedboat":
            # Use the authored asset directly, with only a slight resize.
            target_w = max(12, int(sprite.get_width() * SPEEDBOAT_DIRECT_SCALE))
            target_h = max(10, int(sprite.get_height() * SPEEDBOAT_DIRECT_SCALE))
            sprites[boat_type] = pygame.transform.scale(sprite, (target_w, target_h))
            continue

        target = BOAT_SIZE_BY_TYPE.get(boat_type, BOAT_SIZE)
        sprite_mult = BOAT_SPRITE_SIZE_MULT_BY_TYPE.get(boat_type, 1.2)
        target_w = max(10, int(target[0] * sprite_mult))
        target_h = max(8, int(target[1] * sprite_mult))
        sprites[boat_type] = pygame.transform.scale(sprite, (target_w, target_h))
    return sprites


def load_mothership_sprite() -> pygame.Surface | None:
    if not MOTHERSHIP_SPRITE_PATH.exists():
        return None
    try:
        sprite = pygame.image.load(str(MOTHERSHIP_SPRITE_PATH)).convert_alpha()
        scaled_w = max(48, int(sprite.get_width() * MOTHERSHIP_SPRITE_SCALE))
        scaled_h = max(32, int(sprite.get_height() * MOTHERSHIP_SPRITE_SCALE))
        return pygame.transform.scale(sprite, (scaled_w, scaled_h))
    except pygame.error:
        return None

def load_trash_sprites() -> list[pygame.Surface]:
    sprites: list[pygame.Surface] = []
    if not TRASH_DIR.exists():
        return sprites
    for path in sorted(TRASH_DIR.glob("*.png")):
        try:
            sprite = pygame.image.load(str(path)).convert_alpha()
            scaled_w = max(3, int(sprite.get_width() * TRASH_SPRITE_SCALE))
            scaled_h = max(3, int(sprite.get_height() * TRASH_SPRITE_SCALE))
            sprites.append(pygame.transform.scale(sprite, (scaled_w, scaled_h)))
        except pygame.error:
            continue
    return sprites


def load_clear_cloud_sprites() -> list[pygame.Surface]:
    sprites: list[pygame.Surface] = []
    if not CLEAR_CLOUDS_DIR.exists():
        return sprites
    for path in sorted(CLEAR_CLOUDS_DIR.glob("*.png")):
        try:
            sprites.append(pygame.image.load(str(path)).convert_alpha())
        except pygame.error:
            continue
    return sprites


def build_clear_clouds(cloud_sprites: list[pygame.Surface], count: int) -> list[dict[str, object]]:
    clouds: list[dict[str, object]] = []
    if not cloud_sprites:
        return clouds

    for _ in range(max(1, count)):
        sprite = random.choice(cloud_sprites)
        w = sprite.get_width()
        h = sprite.get_height()
        clouds.append({
            "sprite": sprite,
            "x": random.uniform(0, WORLD_WIDTH),
            "y": random.uniform(30, WORLD_HEIGHT - 30),
            "vx": random.uniform(CLEAR_CLOUD_MIN_SPEED, CLEAR_CLOUD_MAX_SPEED),
            "vy": random.uniform(-0.8, 0.8),
            "w": w,
            "h": h,
        })
    return clouds


def update_clear_clouds(clouds: list[dict[str, object]], dt: float) -> None:
    for cloud in clouds:
        x = float(cloud["x"]) + float(cloud["vx"]) * dt
        y = float(cloud["y"]) + float(cloud["vy"]) * dt
        w = int(cloud["w"])
        h = int(cloud["h"])

        if x > WORLD_WIDTH + w:
            x = -w
        elif x < -w:
            x = WORLD_WIDTH + w

        if y < 20:
            y = 20
            cloud["vy"] = abs(float(cloud["vy"]))
        elif y > WORLD_HEIGHT - 20:
            y = WORLD_HEIGHT - 20
            cloud["vy"] = -abs(float(cloud["vy"]))

        cloud["x"] = x
        cloud["y"] = y


def draw_clear_clouds(surface: pygame.Surface, clouds: list[dict[str, object]], camera_x: float, camera_y: float) -> None:
    for cloud in clouds:
        sprite = cloud.get("sprite")
        if not isinstance(sprite, pygame.Surface):
            continue
        cx = int(float(cloud["x"]))
        cy = int(float(cloud["y"]))
        sx, sy = world_to_screen(cx, cy, camera_x, camera_y)
        rect = sprite.get_rect(center=(sx, sy))
        if rect.right < VIEWPORT_RECT.x - 40 or rect.left > WINDOW_WIDTH + 40 or rect.bottom < -40 or rect.top > WINDOW_HEIGHT + 40:
            continue
        surface.blit(sprite, rect)


def quantize_angle_to_8(angle_degrees: float) -> float:
    """Quantize angle to 8 directions (every 45 degrees)."""
    return round(angle_degrees / 45.0) * 45.0
def draw_fallback_ocean_gradient(surface: pygame.Surface) -> None:
    height = surface.get_height()
    width = surface.get_width()
    for y in range(height):
        t = y / max(1, height - 1)
        color = (
            int(FALLBACK_OCEAN_TOP[0] + (FALLBACK_OCEAN_BOTTOM[0] - FALLBACK_OCEAN_TOP[0]) * t),
            int(FALLBACK_OCEAN_TOP[1] + (FALLBACK_OCEAN_BOTTOM[1] - FALLBACK_OCEAN_TOP[1]) * t),
            int(FALLBACK_OCEAN_TOP[2] + (FALLBACK_OCEAN_BOTTOM[2] - FALLBACK_OCEAN_TOP[2]) * t),
        )
        pygame.draw.line(surface, color, (0, y), (width, y))


class TrashItem:
    def __init__(self, sprite: pygame.Surface | None) -> None:
        self.sprite = pygame.transform.rotate(sprite, random.choice([0, 45, 90, 135, 180, 225, 270, 315])) if sprite is not None else None
        if self.sprite is not None:
            self.width = self.sprite.get_width()
            self.height = self.sprite.get_height()
            self.size = max(self.width, self.height)
        else:
            self.size = random.randint(7, 12)
            self.width = self.size
            self.height = self.size

        self.score = random.choice([8, 10, 12, 15])
        size_metric = math.sqrt(float(self.width * self.height))
        self.sell_value = round(max(0.8, 0.35 + size_metric * 0.42), 2)

        while True:
            self.x = float(random.randint(24, WORLD_RECT.width - 24))
            self.y = float(random.randint(24, WORLD_RECT.height - 24))
            item_rect = pygame.Rect(int(self.x) - self.width // 2, int(self.y) - self.height // 2, self.width, self.height)
            if not item_rect.colliderect(BASE_RECT.inflate(30, 30)):
                break

        angle = random.uniform(0.0, math.tau)
        speed = random.uniform(TRASH_DRIFT_MIN_SPEED, TRASH_DRIFT_MAX_SPEED)
        self.drift_vx = math.cos(angle) * speed
        self.drift_vy = math.sin(angle) * speed

    def update(self, dt: float) -> None:
        # Very slow drift with slight random wobble so trash feels alive but predictable.
        self.drift_vx += random.uniform(-TRASH_DRIFT_WOBBLE, TRASH_DRIFT_WOBBLE) * dt
        self.drift_vy += random.uniform(-TRASH_DRIFT_WOBBLE, TRASH_DRIFT_WOBBLE) * dt

        speed = math.hypot(self.drift_vx, self.drift_vy)
        if speed > TRASH_DRIFT_MAX_SPEED:
            scale = TRASH_DRIFT_MAX_SPEED / max(1e-6, speed)
            self.drift_vx *= scale
            self.drift_vy *= scale

        nx = self.x + self.drift_vx * dt
        ny = self.y + self.drift_vy * dt

        margin = 24
        if nx < margin or nx > WORLD_RECT.width - margin:
            self.drift_vx *= -1.0
            nx = max(margin, min(nx, WORLD_RECT.width - margin))
        if ny < margin or ny > WORLD_RECT.height - margin:
            self.drift_vy *= -1.0
            ny = max(margin, min(ny, WORLD_RECT.height - margin))

        next_rect = pygame.Rect(int(nx) - self.width // 2, int(ny) - self.height // 2, self.width, self.height)
        if next_rect.colliderect(BASE_RECT.inflate(20, 20)):
            self.drift_vx *= -1.0
            self.drift_vy *= -1.0
        else:
            self.x = nx
            self.y = ny

    def draw(self, surface: pygame.Surface, camera_x: float, camera_y: float) -> None:
        sx, sy = world_to_screen(int(self.x), int(self.y), camera_x, camera_y)
        if self.sprite is not None:
            rect = self.sprite.get_rect(center=(sx, sy))
            surface.blit(self.sprite, rect)
        else:
            rect = pygame.Rect(sx - self.size // 2, sy - self.size // 2, self.size, self.size)
            pygame.draw.rect(surface, FALLBACK_TRASH_COLOR, rect, border_radius=2)

    def collides_with_boat(self, boat_rect: pygame.Rect) -> bool:
        item_rect = pygame.Rect(int(self.x) - self.width // 2, int(self.y) - self.height // 2, self.width, self.height)
        return boat_rect.colliderect(item_rect)
def world_view_rect(camera_x: float, camera_y: float, padding: int = 0) -> pygame.Rect:
    x = max(0, int(camera_x) - padding)
    y = max(0, int(camera_y) - padding)
    w = min(WORLD_RECT.width - x, VIEWPORT_RECT.width + padding * 2)
    h = min(WORLD_RECT.height - y, VIEWPORT_RECT.height + padding * 2)
    return pygame.Rect(x, y, max(1, w), max(1, h))


def create_trash_item(trash_sprites: list[pygame.Surface]) -> TrashItem:
    return TrashItem(random.choice(trash_sprites) if trash_sprites else None)


def try_place_trash(item: TrashItem, x: int, y: int) -> bool:
    item.x = float(max(24, min(WORLD_RECT.width - 24, int(x))))
    item.y = float(max(24, min(WORLD_RECT.height - 24, int(y))))
    item_rect = pygame.Rect(int(item.x) - item.width // 2, int(item.y) - item.height // 2, item.width, item.height)
    return not item_rect.colliderect(BASE_RECT.inflate(40, 40))


def random_offscreen_point(camera_x: float, camera_y: float, padding: int = 120) -> tuple[int, int] | None:
    visible = world_view_rect(camera_x, camera_y, padding)
    for _ in range(80):
        x = random.randint(24, WORLD_RECT.width - 24)
        y = random.randint(24, WORLD_RECT.height - 24)
        if visible.collidepoint(x, y):
            continue
        if BASE_RECT.inflate(50, 50).collidepoint(x, y):
            continue
        return x, y
    return None


def spawn_trash_patch(
    trash_items: list[TrashItem],
    trash_sprites: list[pygame.Surface],
    camera_x: float,
    camera_y: float,
    patch_size: int,
    spread: int,
) -> int:
    if len(trash_items) >= MAX_TRASH_ITEMS:
        return 0

    center = random_offscreen_point(camera_x, camera_y, padding=140)
    if center is None:
        return 0

    visible = world_view_rect(camera_x, camera_y, 90)
    added = 0
    target = min(patch_size, MAX_TRASH_ITEMS - len(trash_items))

    for i in range(target):
        if i == 0:
            cx, cy = center
        else:
            cx = center[0] + random.randint(-spread, spread)
            cy = center[1] + random.randint(-spread, spread)

        item = create_trash_item(trash_sprites)
        if not try_place_trash(item, cx, cy):
            continue
        if visible.collidepoint(item.x, item.y):
            continue
        trash_items.append(item)
        added += 1

    return added


def spawn_offscreen_trash(
    trash_items: list[TrashItem],
    trash_sprites: list[pygame.Surface],
    camera_x: float,
    camera_y: float,
    count: int,
) -> int:
    if len(trash_items) >= MAX_TRASH_ITEMS:
        return 0

    visible = world_view_rect(camera_x, camera_y, 100)
    added = 0
    target = min(count, MAX_TRASH_ITEMS - len(trash_items))

    for _ in range(target * 4):
        if added >= target:
            break
        point = random_offscreen_point(camera_x, camera_y, padding=120)
        if point is None:
            break

        item = create_trash_item(trash_sprites)
        if not try_place_trash(item, point[0], point[1]):
            continue
        if visible.collidepoint(item.x, item.y):
            continue
        trash_items.append(item)
        added += 1

    return added


def build_initial_trash(trash_sprites: list[pygame.Surface]) -> list[TrashItem]:
    items: list[TrashItem] = []

    # Start with larger offscreen patches to create dense garbage zones.
    for _ in range(INITIAL_PATCH_COUNT):
        size = random.randint(INITIAL_PATCH_MIN, INITIAL_PATCH_MAX)
        spawn_trash_patch(items, trash_sprites, 0.0, 0.0, size, spread=random.randint(90, 180))

    # Add extra scattered trash so map still has singles between patches.
    spawn_offscreen_trash(items, trash_sprites, 0.0, 0.0, STARTING_TRASH_COUNT + INITIAL_SCATTER_EXTRA)
    return items


class WakeParticle:
    def __init__(self, x: float, y: float, vx: float, vy: float, lifetime: float) -> None:
        self.x = x
        self.y = y
        self.vx = vx
        self.vy = vy
        self.lifetime = lifetime
        self.max_lifetime = lifetime

    def update(self, dt: float) -> None:
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.lifetime -= dt

    def alive(self) -> bool:
        return self.lifetime > 0.0

    def draw(self, surface: pygame.Surface, camera_x: float, camera_y: float) -> None:
        if self.max_lifetime <= 0:
            return
        ratio = max(0.0, min(1.0, self.lifetime / self.max_lifetime))
        radius = max(2, int(7 * ratio))
        alpha = int(230 * ratio)

        sx, sy = world_to_screen(int(self.x), int(self.y), camera_x, camera_y)
        if sx < VIEWPORT_RECT.x - 10 or sx > WINDOW_WIDTH + 10 or sy < -10 or sy > WINDOW_HEIGHT + 10:
            return

        particle_surf = pygame.Surface((radius * 2 + 2, radius * 2 + 2), pygame.SRCALPHA)
        pygame.draw.circle(particle_surf, (245, 250, 255, alpha), (radius + 1, radius + 1), radius)
        surface.blit(particle_surf, (sx - radius - 1, sy - radius - 1))


def draw_tiled_ocean(surface: pygame.Surface, tile: pygame.Surface, camera_x: float, camera_y: float) -> None:
    tile_w, tile_h = tile.get_width(), tile.get_height()
    start_x = VIEWPORT_RECT.x - (int(camera_x) % tile_w)
    start_y = -(int(camera_y) % tile_h)

    x = start_x
    while x < WINDOW_WIDTH:
        y = start_y
        while y < VIEWPORT_RECT.height:
            surface.blit(tile, (x, y))
            y += tile_h
        x += tile_w


def draw_base_ship(
    surface: pygame.Surface,
    base_font: pygame.font.Font,
    camera_x: float,
    camera_y: float,
    mothership_sprite: pygame.Surface | None,
) -> None:
    base_screen = world_rect_to_screen(BASE_RECT, camera_x, camera_y)

    if mothership_sprite is not None:
        sprite_rect = mothership_sprite.get_rect(center=base_screen.center)
        surface.blit(mothership_sprite, sprite_rect)
        return

    pygame.draw.rect(surface, BASE_FILL, base_screen, border_radius=10)
    pygame.draw.rect(surface, BASE_OUTLINE, base_screen, width=3, border_radius=10)
    deck = base_screen.inflate(-34, -44)
    pygame.draw.rect(surface, BASE_DECK, deck, border_radius=8)
    pygame.draw.rect(surface, BASE_OUTLINE, deck, width=2, border_radius=8)
    label = base_font.render("MOTHERSHIP", True, TEXT_COLOR)
    surface.blit(label, (base_screen.x + 18, base_screen.y + 10))

def draw_boat(
    surface: pygame.Surface,
    boat_rect: pygame.Rect,
    camera_x: float,
    camera_y: float,
    boat_sprite: pygame.Surface | None,
    facing_angle_degrees: float,
    boat_type: str = "Speedboat",
) -> None:
    boat_screen = world_rect_to_screen(boat_rect, camera_x, camera_y)

    if boat_sprite is None:
        fill = BOAT_COLOR_BY_TYPE.get(boat_type, BOAT_FILL)
        pygame.draw.rect(surface, fill, boat_screen, border_radius=6)
        pygame.draw.rect(surface, BOAT_OUTLINE, boat_screen, width=2, border_radius=6)
        prow = [
            (boat_screen.right, boat_screen.centery),
            (boat_screen.right + 10, boat_screen.centery - 6),
            (boat_screen.right + 10, boat_screen.centery + 6),
        ]
        pygame.draw.polygon(surface, fill, prow)
        pygame.draw.polygon(surface, BOAT_OUTLINE, prow, width=2)
        return

    snapped_angle = quantize_angle_to_8(facing_angle_degrees + BOAT_SPRITE_ANGLE_OFFSET)
    rotated = pygame.transform.rotate(boat_sprite, -snapped_angle)
    rot_rect = rotated.get_rect(center=boat_screen.center)
    surface.blit(rotated, rot_rect)


def apply_pixelation(surface: pygame.Surface, area: pygame.Rect | None = None) -> None:
    if PIXELATE_SCALE <= 1:
        return

    target = area if area is not None else surface.get_rect()
    if target.width <= 0 or target.height <= 0:
        return

    region = surface.subsurface(target).copy()
    low_w = max(1, target.width // PIXELATE_SCALE)
    low_h = max(1, target.height // PIXELATE_SCALE)
    low = pygame.transform.scale(region, (low_w, low_h))
    pix = pygame.transform.scale(low, (target.width, target.height))
    surface.blit(pix, target.topleft)


def draw_sidebar(
    surface: pygame.Surface,
    body_font: pygame.font.Font,
    company_name: str,
    collected: int,
    remaining: int,
    score: int,
    money: float,
    fame: float,
    crew_total: int,
    crew_available: int,
    morale: float,
    trash_stored: int,
    recycling_inventory: int,
    barge_fuel_storage: float,
    barge_fuel_capacity: float,
    manpower_cost_per_min: float,
    fuel_cost_per_min: float,
    general_cost_per_min: float,
    total_cost_per_min: float,
    collection_rate: float,
    transactions: list[str],
    menu_scroll: float,
    fleet_boats: list[dict[str, object]],
) -> tuple[float, dict[str, pygame.Rect]]:
    panel = pygame.Rect(0, 0, SIDEBAR_WIDTH, WINDOW_HEIGHT)

    base = (170, 130, 84)
    tone_light = (182, 142, 94)
    tone_dark = (156, 118, 75)
    pygame.draw.rect(surface, base, panel)

    x = 10
    i = 0
    while x < SIDEBAR_WIDTH - 8:
        w = 2 if i % 3 else 3
        y0 = 10 + (i * 11) % 34
        h = WINDOW_HEIGHT - y0 - (14 + (i * 7) % 40)
        c = tone_light if i % 2 == 0 else tone_dark
        pygame.draw.rect(surface, c, (x, y0, w, max(40, h)))
        x += 12
        i += 1

    pygame.draw.rect(surface, (186, 149, 102), panel, width=2)
    inner = panel.inflate(-6, -6)
    pygame.draw.rect(surface, SIDEBAR_BORDER, inner, width=2)

    content_x = 12
    content_y = 12
    content_w = SIDEBAR_WIDTH - 24
    visible_h = WINDOW_HEIGHT - 24
    content = pygame.Surface((content_w, 2800), pygame.SRCALPHA)

    card_colors = [(149, 111, 70), (141, 104, 64), (156, 118, 76), (137, 100, 61)]
    border = (103, 75, 45)

    mode_buttons_content: dict[str, pygame.Rect] = {}
    mode_buttons_screen: dict[str, pygame.Rect] = {}

    def wrap_line(text_line: str, max_width: int) -> list[str]:
        words = text_line.split(" ")
        if not words:
            return [""]

        result: list[str] = []
        current = ""
        for word in words:
            candidate = word if not current else f"{current} {word}"
            if body_font.size(candidate)[0] <= max_width:
                current = candidate
                continue
            if current:
                result.append(current)
            if body_font.size(word)[0] > max_width:
                chunk = ""
                for ch in word:
                    trial = chunk + ch
                    if body_font.size(trial)[0] <= max_width:
                        chunk = trial
                    else:
                        if chunk:
                            result.append(chunk)
                        chunk = ch
                current = chunk
            else:
                current = word
        if current:
            result.append(current)
        return result

    def draw_card(y: int, title: str, lines: list[str], idx: int) -> tuple[int, pygame.Rect]:
        max_line_width = content_w - 24
        wrapped_lines: list[str] = []
        for line in lines:
            wrapped_lines.extend(wrap_line(line, max_line_width))

        h = 36 + len(wrapped_lines) * 20
        rect = pygame.Rect(0, y, content_w, h)
        pygame.draw.rect(content, card_colors[idx % len(card_colors)], rect)
        pygame.draw.rect(content, border, rect, width=2)

        title_surf = body_font.render(title, True, TEXT_COLOR)
        content.blit(title_surf, (10, y + 8))

        ly = y + 30
        for line in wrapped_lines:
            surf = body_font.render(line, True, MUTED_TEXT)
            content.blit(surf, (12, ly))
            ly += 20
        return y + h + 10, rect

    y = 0
    y, _ = draw_card(y, company_name, [
    ], 2)

    y, _ = draw_card(y, "Overview", [
        f"Money: ${int(money)}",
        f"Fame: {fame:.1f}",
        f"Score: {score}",
        f"Total Trash Collected: {collected}",
    ], 0)

    y, _ = draw_card(y, "Barge", [
        f"Crew At Barge: {crew_available}/{crew_total}",
        f"Trash Stock: {recycling_inventory}",
        f"Ops Spend/min: ${total_cost_per_min:.1f}",
        f"Fuel Spend/min: ${fuel_cost_per_min:.1f}",
        f"Barge Fuel: {int(barge_fuel_storage)}/{int(barge_fuel_capacity)}",
    ], 1)

    y, _ = draw_card(y, "Control Key", [
        "C = Collect",
        "S = Sell",
        "R = Return To Barge",
        "- / + = Crew Allocate",
    ], 2)

    # Fleet panel: one row per boat + action buttons
    fleet_top = y
    row_h = 90
    row_gap = 12
    row_count = max(1, len(fleet_boats))
    fleet_h = 38 + row_count * (row_h + row_gap) + 8
    fleet_rect = pygame.Rect(0, fleet_top, content_w, fleet_h)
    pygame.draw.rect(content, card_colors[2], fleet_rect)
    pygame.draw.rect(content, border, fleet_rect, width=2)
    fleet_title = body_font.render("Fleet", True, TEXT_COLOR)
    content.blit(fleet_title, (10, fleet_top + 8))

    for i, boat in enumerate(fleet_boats):
        row_y = fleet_top + 34 + i * (row_h + row_gap)
        row_rect = pygame.Rect(8, row_y, content_w - 16, row_h)
        pygame.draw.rect(content, (126, 93, 60), row_rect)
        pygame.draw.rect(content, (170, 136, 95), row_rect, width=1)

        boat_id = int(boat.get("id", i + 1))
        boat_type = str(boat.get("type", "Boat"))
        status = str(boat.get("status", "Idle"))
        mode = str(boat.get("mode", MODE_COLLECT))
        crew_assigned = int(boat.get("crew_assigned", 0))
        crew_min = int(boat.get("crew_min", 0))
        crew_max = int(boat.get("crew_max", crew_min))

        actions = [("collect", "C"), ("sell", "S"), ("return", "R")]
        can_sell = boat_type == "Heavy Boat"
        at_barge_for_crew = bool(boat.get("docked", False))
        btn_w = 24
        btn_h = 20
        crew_btns = [("crew_minus", "-"), ("crew_plus", "+")]
        crew_btn_w = 18
        crew_gap = 3
        action_w = len(actions) * (btn_w + 4)
        crew_w = len(crew_btns) * (crew_btn_w + crew_gap)
        start_x = row_rect.right - action_w - crew_w - 12

        name_surf = body_font.render(f"B{boat_id} {boat_type}", True, (255, 255, 255))
        content.blit(name_surf, (row_rect.x + 6, row_rect.y + 3))

        crew_surf = body_font.render(f"Crew {crew_assigned} [{crew_min}-{crew_max}]", True, (240, 232, 220))
        content.blit(crew_surf, (row_rect.x + 6, row_rect.y + 20))

        # Controls stay beside the boat row header, not below it.
        controls_y = row_rect.y + 12

        crew_start_x = start_x
        for j, (action, short) in enumerate(crew_btns):
            bx = crew_start_x + j * (crew_btn_w + crew_gap)
            by = controls_y
            brect = pygame.Rect(bx, by, crew_btn_w, btn_h)
            crew_fill = (102, 75, 50) if at_barge_for_crew else (86, 68, 49)
            crew_outline = (154, 122, 86) if at_barge_for_crew else (122, 96, 70)
            txt_color = (255, 255, 255) if at_barge_for_crew else (200, 188, 170)
            pygame.draw.rect(content, crew_fill, brect)
            pygame.draw.rect(content, crew_outline, brect, width=1)
            txt = body_font.render(short, True, txt_color)
            content.blit(txt, (brect.x + 5, brect.y + 2))
            if at_barge_for_crew:
                mode_buttons_content[f"{boat_id}:{action}"] = brect

        action_start_x = crew_start_x + crew_w + 6
        for j, (action, short) in enumerate(actions):
            bx = action_start_x + j * (btn_w + 4)
            by = controls_y
            brect = pygame.Rect(bx, by, btn_w, btn_h)
            enabled = not (action == "sell" and not can_sell)
            selected = ((mode == MODE_COLLECT and action == "collect") or (mode == MODE_SELL and action == "sell") or (mode == MODE_STOP and action == "return")) and enabled
            if enabled:
                fill = (213, 177, 126) if selected else (102, 75, 50)
                outline = (245, 220, 180) if selected else (154, 122, 86)
                txt_color = (255, 255, 255)
            else:
                fill = (86, 68, 49)
                outline = (122, 96, 70)
                txt_color = (200, 188, 170)
            pygame.draw.rect(content, fill, brect)
            pygame.draw.rect(content, outline, brect, width=1)
            txt = body_font.render(short, True, txt_color)
            content.blit(txt, (brect.x + 6, brect.y + 2))
            if enabled:
                mode_buttons_content[f"{boat_id}:{action}"] = brect

        text_max_w = max(30, start_x - (row_rect.x + 8) - 8)
        status_lines = wrap_line(status, text_max_w)[:2]
        for s_idx, s_line in enumerate(status_lines):
            status_surf = body_font.render(s_line, True, (240, 232, 220))
            content.blit(status_surf, (row_rect.x + 6, row_rect.y + 47 + s_idx * 16))

        if i < row_count - 1:
            line_y = row_rect.bottom + (row_gap // 2)
            px = 14
            while px < content_w - 14:
                pygame.draw.line(content, (181, 148, 110), (px, line_y), (min(px + 6, content_w - 14), line_y), 1)
                px += 12

    y = fleet_top + fleet_h + 10

    # Per-boat detail panels
    for i, boat in enumerate(fleet_boats):
        boat_id = int(boat.get("id", i + 1))
        boat_type = str(boat.get("type", "Boat"))
        status = str(boat.get("status", "Idle"))
        fuel_seconds = float(boat.get("fuel_seconds", 0.0))
        max_fuel = float(boat.get("max_fuel", MAX_FUEL_SECONDS))
        refuel_left = float(boat.get("refuel_seconds_left", 0.0))
        refuel_total = float(boat.get("refuel_total", REFUEL_SECONDS))
        is_refueling = bool(boat.get("is_refueling", False))
        crew_min = int(boat.get("crew_min", 1))
        crew_max = int(boat.get("crew_max", crew_min))
        crew_assigned = int(boat.get("crew_assigned", 0))
        cargo = int(boat.get("cargo", 0))
        capacity = int(boat.get("capacity", 0))
        collected_by_boat = int(boat.get("collected", collected))

        status_lines = wrap_line(f"Status: {status}", content_w - 24)[:3]
        trash_lines = wrap_line(f"Trash Collected: {cargo}/{capacity}", content_w - 24)[:2]

        info_lines = 2 + len(status_lines) + len(trash_lines)
        detail_h = 48 + info_lines * 18 + 28
        detail_rect = pygame.Rect(0, y, content_w, detail_h)
        pygame.draw.rect(content, card_colors[(i + 1) % len(card_colors)], detail_rect)
        pygame.draw.rect(content, border, detail_rect, width=2)

        title = body_font.render(f"Boat {boat_id} Panel", True, TEXT_COLOR)
        content.blit(title, (10, y + 8))

        ty = y + 30
        l1 = body_font.render(f"Type: {boat_type}", True, MUTED_TEXT)
        l3 = body_font.render(f"Crew: {crew_assigned} (min {crew_min}, max {crew_max})", True, MUTED_TEXT)
        content.blit(l1, (10, ty))
        ty += 18
        content.blit(l3, (10, ty))
        ty += 18

        for line in status_lines:
            surf = body_font.render(line, True, MUTED_TEXT)
            content.blit(surf, (10, ty))
            ty += 18

        for line in trash_lines:
            surf = body_font.render(line, True, MUTED_TEXT)
            content.blit(surf, (10, ty))
            ty += 18

        bar_x = 10
        bar_w = content_w - 20
        bar_h = 14
        bar_y = y + detail_h - (bar_h + 10)
        pygame.draw.rect(content, (82, 60, 40), (bar_x, bar_y, bar_w, bar_h))

        if is_refueling:
            ratio = 1.0 - (max(0.0, refuel_left) / max(0.001, refuel_total))
            fill_color = (120, 190, 255)
        else:
            ratio = max(0.0, min(1.0, fuel_seconds / max(0.001, max_fuel)))
            fill_color = (110, 224, 132) if ratio > 0.25 else (240, 132, 108)

        fill_w = int(bar_w * max(0.0, min(1.0, ratio)))
        if fill_w > 0:
            pygame.draw.rect(content, fill_color, (bar_x, bar_y, fill_w, bar_h))
        pygame.draw.rect(content, (210, 180, 140), (bar_x, bar_y, bar_w, bar_h), width=1)

        y += detail_h + 10

    y, _ = draw_card(y, "Crew", [
        f"Morale: {morale:.1f}%",
        "Hiring panel next",
    ], 3)

    y, _ = draw_card(y, "Costs", [
        f"Manpower/min: ${manpower_cost_per_min:.1f}",
        f"Fuel/min: ${fuel_cost_per_min:.1f}",
        f"General/min: ${general_cost_per_min:.1f}",
        f"Total/min: ${total_cost_per_min:.1f}",
    ], 1)

    txns = transactions[:7] if transactions else ["No transactions yet"]
    y, _ = draw_card(y, "Transactions", txns, 0)

    max_scroll = max(0, y - visible_h)
    clamped_scroll = max(0, min(int(menu_scroll), max_scroll))

    src = pygame.Rect(0, clamped_scroll, content_w, visible_h)
    surface.blit(content, (content_x, content_y), src)

    for mode_key, rect in mode_buttons_content.items():
        sr = pygame.Rect(content_x + rect.x, content_y + rect.y - clamped_scroll, rect.width, rect.height)
        if sr.bottom >= content_y and sr.top <= content_y + visible_h:
            mode_buttons_screen[mode_key] = sr

    if max_scroll > 0:
        track = pygame.Rect(SIDEBAR_WIDTH - 7, content_y, 4, visible_h)
        pygame.draw.rect(surface, (120, 88, 54), track)
        thumb_h = max(22, int(visible_h * (visible_h / max(y, visible_h + 1))))
        thumb_y = content_y + int((visible_h - thumb_h) * (clamped_scroll / max(1, max_scroll)))
        thumb = pygame.Rect(track.x, thumb_y, track.width, thumb_h)
        pygame.draw.rect(surface, (198, 161, 114), thumb)

    return float(max_scroll), mode_buttons_screen
def collect_on_contact(boat_rect: pygame.Rect, trash_items: list[TrashItem], max_pickups: int | None = None) -> tuple[int, int, float]:
    kept_items: list[TrashItem] = []
    collected_count = 0
    score_gained = 0
    sale_value_gained = 0.0
    for item in trash_items:
        if item.collides_with_boat(boat_rect) and (max_pickups is None or collected_count < max_pickups):
            collected_count += 1
            score_gained += item.score
            sale_value_gained += item.sell_value
        else:
            kept_items.append(item)
    trash_items[:] = kept_items
    return collected_count, score_gained, sale_value_gained


def move_boat_toward_point(boat_rect: pygame.Rect, target_x: int, target_y: int, dt: float) -> tuple[bool, float, float]:
    """Move boat toward point.

    Returns:
        reached_target, move_dx, move_dy
    """
    bx, by = boat_rect.center
    dx = target_x - bx
    dy = target_y - by
    distance = math.hypot(dx, dy)
    if distance <= 1.0:
        return True, 0.0, 0.0

    step = BOAT_SPEED * dt
    if step >= distance:
        boat_rect.center = (target_x, target_y)
        boat_rect.clamp_ip(WORLD_RECT)
        return True, float(dx), float(dy)

    move_dx = (dx / distance) * step
    move_dy = (dy / distance) * step
    boat_rect.center = (int(bx + move_dx), int(by + move_dy))
    boat_rect.clamp_ip(WORLD_RECT)
    return False, float(move_dx), float(move_dy)


def move_boat_toward_point_speed(
    boat_rect: pygame.Rect,
    target_x: int,
    target_y: int,
    dt: float,
    speed: float,
) -> tuple[bool, float, float]:
    bx, by = boat_rect.center
    dx = target_x - bx
    dy = target_y - by
    distance = math.hypot(dx, dy)
    if distance <= 1.0:
        return True, 0.0, 0.0

    step = max(1e-4, speed) * dt
    if step >= distance:
        boat_rect.center = (target_x, target_y)
        boat_rect.clamp_ip(WORLD_RECT)
        return True, float(dx), float(dy)

    move_dx = (dx / distance) * step
    move_dy = (dy / distance) * step
    boat_rect.center = (int(bx + move_dx), int(by + move_dy))
    boat_rect.clamp_ip(WORLD_RECT)
    return False, float(move_dx), float(move_dy)


def move_boat_to_nearest_trash(boat_rect: pygame.Rect, trash_items: list[TrashItem], dt: float) -> tuple[float, float]:
    if not trash_items:
        return 0.0, 0.0
    bx, by = boat_rect.center
    nearest = min(trash_items, key=lambda item: (item.x - bx) ** 2 + (item.y - by) ** 2)
    _, move_dx, move_dy = move_boat_toward_point(boat_rect, int(nearest.x), int(nearest.y), dt)
    return move_dx, move_dy


def move_boat_to_nearest_trash_speed(
    boat_rect: pygame.Rect,
    trash_items: list[TrashItem],
    dt: float,
    speed: float,
) -> tuple[float, float]:
    if not trash_items:
        return 0.0, 0.0
    bx, by = boat_rect.center
    nearest = min(trash_items, key=lambda item: (item.x - bx) ** 2 + (item.y - by) ** 2)
    _, move_dx, move_dy = move_boat_toward_point_speed(boat_rect, int(nearest.x), int(nearest.y), dt, speed)
    return move_dx, move_dy


def get_barge_dock_spots() -> list[dict[str, float]]:
    # Three legal docking points: stern + port side + starboard side.
    return [
        {"x": float(BASE_RECT.centerx), "y": float(BASE_RECT.bottom + 34), "angle": 180.0},
        {"x": float(BASE_RECT.left - 34), "y": float(BASE_RECT.centery - 88), "angle": 90.0},
        {"x": float(BASE_RECT.right + 34), "y": float(BASE_RECT.centery + 88), "angle": -90.0},
    ]


def get_or_assign_dock_slot(boat: dict[str, object], boats: list[dict[str, object]]) -> int | None:
    spots = get_barge_dock_spots()
    occupied: set[int] = set()
    for other in boats:
        if other is boat:
            continue
        slot = other.get("dock_slot")
        if isinstance(slot, int):
            occupied.add(slot)

    current = boat.get("dock_slot")
    if isinstance(current, int) and 0 <= current < len(spots) and current not in occupied:
        return current

    free_slots = [i for i in range(len(spots)) if i not in occupied]
    if not free_slots:
        boat["dock_slot"] = None
        return None

    boat_rect = boat.get("rect")
    if not isinstance(boat_rect, pygame.Rect):
        slot = free_slots[0]
        boat["dock_slot"] = slot
        return slot

    bx, by = boat_rect.center
    slot = min(free_slots, key=lambda i: (spots[i]["x"] - bx) ** 2 + (spots[i]["y"] - by) ** 2)
    boat["dock_slot"] = slot
    return slot


def maybe_spawn_wake(
    wake_particles: list[WakeParticle],
    boat_rect: pygame.Rect,
    move_dx: float,
    move_dy: float,
    dt: float,
) -> None:
    speed = math.hypot(move_dx, move_dy)
    if speed < 0.2:
        return

    # Spawn a few particles based on movement amount.
    spawn_count = max(6, int(speed / 0.8))
    cx, cy = boat_rect.center
    direction_x = move_dx / max(speed, 1e-6)
    direction_y = move_dy / max(speed, 1e-6)

    # Trail starts behind the boat.
    base_x = cx - direction_x * (boat_rect.width * 0.5)
    base_y = cy - direction_y * (boat_rect.height * 0.5)

    for _ in range(min(spawn_count, 16)):
        jitter_x = random.uniform(-6.0, 6.0)
        jitter_y = random.uniform(-6.0, 6.0)
        vx = -direction_x * random.uniform(24.0, 62.0) + random.uniform(-10.0, 10.0)
        vy = -direction_y * random.uniform(24.0, 62.0) + random.uniform(-10.0, 10.0)
        life = random.uniform(0.65, 1.15)
        wake_particles.append(WakeParticle(base_x + jitter_x, base_y + jitter_y, vx, vy, life))


def update_wake(wake_particles: list[WakeParticle], dt: float) -> None:
    alive: list[WakeParticle] = []
    for p in wake_particles:
        p.update(dt)
        if p.alive():
            alive.append(p)
    wake_particles[:] = alive


async def run_game() -> None:
    pygame.init()
    screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
    pygame.display.set_caption("MVHacks - Cleanup Fleet")
    clock = pygame.time.Clock()

    captain_name = play_intro(screen, clock)
    if captain_name is None:
        pygame.quit()
        return

    intro_fade_alpha = 255.0
    company_name = f"{captain_name}'s Ocean Cleanup Co."

    body_font = pygame.font.SysFont("Courier New", 18, bold=True)
    base_font = pygame.font.SysFont("Courier New", 18, bold=True)

    ocean_tile = load_ocean_tile()
    boat_sprites = load_boat_sprites()
    mothership_sprite = load_mothership_sprite()
    trash_sprites = load_trash_sprites()
    clear_cloud_sprites = load_clear_cloud_sprites()

    trash_items = build_initial_trash(trash_sprites)
    clear_clouds = build_clear_clouds(clear_cloud_sprites, CLEAR_CLOUD_COUNT)
    wake_particles: list[WakeParticle] = []

    trash_collected = 0
    score = 0

    # Economy + management
    money = 1200.0
    fame = 8.0
    crew_total = 5
    morale = 74.0
    manpower_cost_per_min = 24.0
    fuel_cost_per_min = 12.0
    general_cost_per_min = 6.0
    total_cost_per_min = manpower_cost_per_min + fuel_cost_per_min + general_cost_per_min
    cost_transaction_interval = 8.0
    cost_transaction_timer = 0.0
    pending_cost_total = 0.0

    collection_rate = 0.0
    elapsed_seconds = 0.0
    event_log: list[str] = [f"[00:00] Captain {captain_name} online"]
    transactions: list[str] = ["[00:00] Starting balance +$1200.0"]

    camera_x = float(BASE_RECT.centerx - VIEWPORT_RECT.width // 2)
    camera_y = float(BASE_RECT.centery - VIEWPORT_RECT.height // 2)
    camera_x, camera_y = clamp_camera(camera_x, camera_y)
    dragging = False
    last_mouse = (0, 0)

    menu_scroll = 0.0
    menu_max_scroll = 0.0
    mode_button_rects: dict[str, pygame.Rect] = {}

    offscreen_spawn_timer = 0.0

    recycling_inventory = 0
    recycling_stock_value = 0.0
    barge_fuel_storage = BARGE_FUEL_START

    boat_layout = [
        ("Speedboat", (95, -70)),
    ]

    boats: list[dict[str, object]] = []
    for idx, (boat_type, offset) in enumerate(boat_layout, start=1):
        bw, bh = BOAT_SIZE_BY_TYPE.get(boat_type, BOAT_SIZE)

        boat_rect = pygame.Rect(0, 0, bw, bh)
        boat_rect.center = (BASE_RECT.centerx + offset[0], BASE_RECT.centery + offset[1])
        boat_rect.clamp_ip(WORLD_RECT)

        crew_min = BOAT_CREW_MIN_BY_TYPE.get(boat_type, 1)
        crew_max = BOAT_CREW_MAX_BY_TYPE.get(boat_type, max(1, crew_min))

        boats.append({
            "id": idx,
            "type": boat_type,
            "rect": boat_rect,
            "mode": MODE_COLLECT,
            "pending_mode": MODE_COLLECT,
            "refuel_lock": True,
            "state": STATE_COLLECTING,
            "status": "Initializing",
            "speed": BOAT_SPEED_BY_TYPE.get(boat_type, BOAT_SPEED),
            "fuel": MAX_FUEL_SECONDS,
            "refuel_left": 0.0,
            "refuel_total": max(MIN_REFUEL_SECONDS, BOAT_REFUEL_SECONDS_BY_TYPE.get(boat_type, REFUEL_SECONDS)),
            "capacity": BOAT_CAPACITY_BY_TYPE.get(boat_type, 20),
            "crew_min": crew_min,
            "crew_max": crew_max,
            "crew_assigned": 1 if (idx == 1 and crew_min <= 1) else (crew_min if idx == 1 else 0),
            "trash_stored": 0,
            "cargo_sale_value": 0.0,
            "collected_total": 0,
            "visible": True,
            "facing_angle": 0.0,
            "sell_phase": "idle",
            "sell_timer": 0.0,
            "pending_sale_revenue": 0.0,
            "pending_sale_units": 0,
            "dock_slot": None,
            "docked": False,
        })

    def add_log(msg: str) -> None:
        nonlocal event_log, elapsed_seconds
        mm = int(elapsed_seconds // 60)
        ss = int(elapsed_seconds % 60)
        event_log.insert(0, f"[{mm:02d}:{ss:02d}] {msg}")
        if len(event_log) > 12:
            event_log = event_log[:12]

    def add_transaction(msg: str) -> None:
        nonlocal transactions, elapsed_seconds
        mm = int(elapsed_seconds // 60)
        ss = int(elapsed_seconds % 60)
        transactions.insert(0, f"[{mm:02d}:{ss:02d}] {msg}")
        if len(transactions) > 20:
            transactions = transactions[:20]

    running = True
    while running:
        dt = clock.tick(FPS) / 1000.0
        elapsed_seconds += dt

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                running = False
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if event.pos[0] < SIDEBAR_WIDTH:
                    for button_key, rect in mode_button_rects.items():
                        if not rect.collidepoint(event.pos):
                            continue
                        try:
                            boat_id_str, action = button_key.split(":", 1)
                            boat_id = int(boat_id_str)
                        except ValueError:
                            continue

                        boat = next((b for b in boats if int(b["id"]) == boat_id), None)
                        if boat is None:
                            continue

                        assigned_total = sum(int(b["crew_assigned"]) for b in boats)

                        at_barge_for_crew = bool(boat.get("docked", False))

                        if action == "crew_minus":
                            if not at_barge_for_crew:
                                add_log(f"Boat {boat_id} must be at barge to change crew")
                                break
                            if int(boat["crew_assigned"]) > 0:
                                boat["crew_assigned"] = int(boat["crew_assigned"]) - 1
                                add_log(f"Boat {boat_id} crew decreased to {boat['crew_assigned']}")
                            break

                        if action == "crew_plus":
                            if not at_barge_for_crew:
                                add_log(f"Boat {boat_id} must be at barge to change crew")
                                break
                            if int(boat["crew_assigned"]) < int(boat["crew_max"]) and assigned_total < crew_total:
                                boat["crew_assigned"] = int(boat["crew_assigned"]) + 1
                                add_log(f"Boat {boat_id} crew increased to {boat['crew_assigned']}")
                            break

                        if action == "sell" and str(boat.get("type", "")) != "Heavy Boat":
                            add_log(f"Boat {boat_id}: sell mode is transfer-boat only")
                            break

                        requested_mode = MODE_COLLECT if action == "collect" else (MODE_SELL if action == "sell" else MODE_STOP)
                        boat["pending_mode"] = requested_mode
                        boat["refuel_lock"] = True
                        boat["mode"] = requested_mode
                        boat["sell_phase"] = "idle"
                        boat["visible"] = True
                        label = "Return" if requested_mode == MODE_STOP else requested_mode.title()
                        add_log(f"Boat {boat_id} command queued: {label} (refuel first)")
                        add_transaction(f"Boat {boat_id} queued -> {label} (refuel)")
                        break
                elif VIEWPORT_RECT.collidepoint(event.pos):
                    dragging = True
                    last_mouse = event.pos
            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                dragging = False
            elif event.type == pygame.MOUSEMOTION and dragging:
                dx = event.pos[0] - last_mouse[0]
                dy = event.pos[1] - last_mouse[1]
                camera_x -= dx
                camera_y -= dy
                camera_x, camera_y = clamp_camera(camera_x, camera_y)
                last_mouse = event.pos
            elif event.type == pygame.MOUSEWHEEL:
                mx, _ = pygame.mouse.get_pos()
                if mx < SIDEBAR_WIDTH:
                    menu_scroll -= event.y * 26
                    menu_scroll = max(0.0, min(menu_scroll, menu_max_scroll))

        offscreen_spawn_timer += dt
        if offscreen_spawn_timer >= OFFSCREEN_SPAWN_INTERVAL:
            offscreen_spawn_timer = 0.0
            if len(trash_items) < MAX_TRASH_ITEMS:
                if random.random() < 0.72:
                    patch_size = random.randint(OFFSCREEN_PATCH_MIN, OFFSCREEN_PATCH_MAX)
                    spawn_trash_patch(
                        trash_items,
                        trash_sprites,
                        camera_x,
                        camera_y,
                        patch_size,
                        spread=random.randint(75, 145),
                    )
                else:
                    spawn_offscreen_trash(
                        trash_items,
                        trash_sprites,
                        camera_x,
                        camera_y,
                        random.randint(2, 5),
                    )

        for item in trash_items:
            item.update(dt)
        update_clear_clouds(clear_clouds, dt)

        returning_count = 0
        fleet_boats: list[dict[str, object]] = []

        for boat in boats:
            boat_rect = boat["rect"]
            assert isinstance(boat_rect, pygame.Rect)

            boat_id = int(boat["id"])
            boat_type = str(boat["type"])
            boat_mode = str(boat["mode"])
            pending_mode = str(boat["pending_mode"])
            boat_state = str(boat["state"])
            boat_speed = float(boat["speed"])
            fuel_seconds = float(boat["fuel"])
            refuel_seconds_left = float(boat["refuel_left"])
            boat_refuel_seconds = float(boat["refuel_total"])
            boat_capacity = int(boat["capacity"])
            crew_min = int(boat["crew_min"])
            crew_max = int(boat["crew_max"])
            crew_assigned = int(boat["crew_assigned"])
            trash_stored = int(boat["trash_stored"])
            cargo_sale_value = float(boat["cargo_sale_value"])
            collected_total = int(boat["collected_total"])
            boat_visible = bool(boat["visible"])
            facing_angle = float(boat["facing_angle"])
            sell_phase = str(boat["sell_phase"])
            sell_timer = float(boat["sell_timer"])
            pending_sale_revenue = float(boat["pending_sale_revenue"])
            pending_sale_units = int(boat["pending_sale_units"])
            refuel_lock_active = bool(boat["refuel_lock"])
            dock_slot = boat.get("dock_slot") if isinstance(boat.get("dock_slot"), int) else None
            docked = False

            move_dx = 0.0
            move_dy = 0.0
            boat_status = "Idle"
            newly_collected = 0
            gained_score = 0
            gained_sale_value = 0.0

            has_operating_crew = crew_assigned >= crew_min

            if not has_operating_crew:
                boat_visible = True
                sell_phase = "idle"
                if refuel_seconds_left > 0.0:
                    refuel_seconds_left = 0.0
                boat_state = STATE_COLLECTING
                boat_status = f"Need crew ({crew_assigned}/{crew_min})"

            elif refuel_lock_active:
                boat_visible = True
                sell_phase = "idle"
                slot = get_or_assign_dock_slot(boat, boats)
                mode_label = "Return" if pending_mode == MODE_STOP else pending_mode.title()

                if slot is None:
                    at_base, move_dx, move_dy = move_boat_toward_point_speed(boat_rect, BASE_RECT.centerx, BASE_RECT.bottom + 120, dt, boat_speed)
                    boat_status = f"Command {mode_label}: waiting dock slot"
                else:
                    spot = get_barge_dock_spots()[slot]
                    at_base, move_dx, move_dy = move_boat_toward_point_speed(boat_rect, int(spot["x"]), int(spot["y"]), dt, boat_speed)
                    if at_base:
                        docked = True
                        facing_angle = float(spot["angle"])

                if not at_base:
                    if slot is not None:
                        boat_status = f"Command {mode_label}: docking"
                else:
                    if fuel_seconds < (MAX_FUEL_SECONDS - 1e-3):
                        if boat_state != STATE_REFUELING and refuel_seconds_left <= 0.0:
                            boat_state = STATE_REFUELING
                            refuel_seconds_left = boat_refuel_seconds
                            add_log(f"Boat {boat_id} docked, refueling before command")

                        boat_status = f"Refueling before {mode_label} ({max(0.0, refuel_seconds_left):.1f}s)"
                        refuel_seconds_left -= dt
                        if refuel_seconds_left <= 0.0:
                            required_units = max(0.0, (MAX_FUEL_SECONDS - fuel_seconds) * BARGE_FUEL_UNITS_PER_BOAT_FUEL_SEC)
                            if barge_fuel_storage + 1e-6 >= required_units:
                                barge_fuel_storage = max(0.0, barge_fuel_storage - required_units)
                                fuel_seconds = MAX_FUEL_SECONDS
                                refuel_seconds_left = 0.0
                                boat_state = STATE_COLLECTING
                                refuel_lock_active = False
                                boat_mode = pending_mode
                                add_log(f"Boat {boat_id} refuel complete, executing {mode_label}")
                            else:
                                boat_status = "Waiting barge fuel"
                                refuel_seconds_left = 0.0
                    else:
                        boat_state = STATE_COLLECTING
                        refuel_seconds_left = 0.0
                        refuel_lock_active = False
                        boat_mode = pending_mode
                        boat_status = f"Fuel ready, executing {mode_label}"

            elif boat_mode == MODE_COLLECT:
                boat_visible = True
                sell_phase = "idle"

                if boat_state == STATE_COLLECTING:
                    bx, by = boat_rect.center
                    dist_to_barge = math.hypot(BASE_RECT.centerx - bx, BASE_RECT.centery - by)
                    fuel_needed_to_barge = (dist_to_barge / max(1e-6, boat_speed)) + 0.35

                    if fuel_seconds <= fuel_needed_to_barge:
                        boat_state = STATE_RETURNING
                        boat_status = "Returning To Base (fuel reserve)"
                    else:
                        boat["dock_slot"] = None
                        boat_status = "Collecting"
                        move_dx, move_dy = move_boat_to_nearest_trash_speed(boat_rect, trash_items, dt, boat_speed)
                        available_capacity = max(0, boat_capacity - trash_stored)
                        if available_capacity > 0:
                            newly_collected, gained_score, gained_sale_value = collect_on_contact(boat_rect, trash_items, available_capacity)
                            if newly_collected > 0:
                                trash_stored += newly_collected
                                cargo_sale_value += gained_sale_value
                                fame_multiplier = 1.0 + (fame / 100.0)
                                score += max(1, int(round(gained_score * fame_multiplier)))
                                fame = min(100.0, fame + newly_collected * 0.04)
                                collected_total += newly_collected
                        else:
                            boat_state = STATE_RETURNING
                            boat_status = "Returning To Base (cargo full)"

                elif boat_state == STATE_RETURNING:
                    returning_count += 1
                    boat_status = "Returning To Base"
                    slot = get_or_assign_dock_slot(boat, boats)
                    if slot is None:
                        at_base, move_dx, move_dy = move_boat_toward_point_speed(boat_rect, BASE_RECT.centerx, BASE_RECT.bottom + 120, dt, boat_speed)
                        boat_status = "Waiting dock slot"
                    else:
                        spot = get_barge_dock_spots()[slot]
                        at_base, move_dx, move_dy = move_boat_toward_point_speed(boat_rect, int(spot["x"]), int(spot["y"]), dt, boat_speed)
                        if at_base:
                            docked = True
                            facing_angle = float(spot["angle"])
                    if at_base:
                        dropped_off = trash_stored
                        if dropped_off > 0:
                            trash_collected += dropped_off
                            trash_stored = 0
                            recycling_inventory += dropped_off
                            recycling_stock_value += cargo_sale_value
                            cargo_sale_value = 0.0
                            add_transaction(f"Boat {boat_id} stocked +{dropped_off} units")

                        boat_state = STATE_REFUELING
                        refuel_seconds_left = boat_refuel_seconds

                else:
                    boat_status = f"Refueling ({max(0.0, refuel_seconds_left):.1f}s)"
                    refuel_seconds_left -= dt
                    if refuel_seconds_left <= 0.0:
                        required_units = max(0.0, (MAX_FUEL_SECONDS - fuel_seconds) * BARGE_FUEL_UNITS_PER_BOAT_FUEL_SEC)
                        if barge_fuel_storage + 1e-6 >= required_units:
                            barge_fuel_storage = max(0.0, barge_fuel_storage - required_units)
                            fuel_seconds = MAX_FUEL_SECONDS
                            refuel_seconds_left = 0.0
                            boat_state = STATE_COLLECTING
                        else:
                            boat_status = "Waiting barge fuel"
                            refuel_seconds_left = 0.0

            elif boat_mode == MODE_SELL and boat_type != "Heavy Boat":
                boat_mode = MODE_COLLECT
                boat_status = "Sell reserved for Heavy Boat"

            elif boat_mode == MODE_STOP:
                boat_visible = True
                sell_phase = "idle"
                slot = get_or_assign_dock_slot(boat, boats)
                if slot is None:
                    at_base, move_dx, move_dy = move_boat_toward_point_speed(boat_rect, BASE_RECT.centerx, BASE_RECT.bottom + 120, dt, boat_speed)
                    boat_status = "Waiting dock slot"
                else:
                    spot = get_barge_dock_spots()[slot]
                    at_base, move_dx, move_dy = move_boat_toward_point_speed(boat_rect, int(spot["x"]), int(spot["y"]), dt, boat_speed)
                    if at_base:
                        docked = True
                        facing_angle = float(spot["angle"])
                    boat_status = "Stopped at barge" if at_base else "Returning to dock"

            else:  # MODE_SELL
                boat_state = STATE_COLLECTING
                refuel_seconds_left = 0.0

                if sell_phase == "idle":
                    slot = get_or_assign_dock_slot(boat, boats)
                    if slot is None:
                        at_base, move_dx, move_dy = move_boat_toward_point_speed(boat_rect, BASE_RECT.centerx, BASE_RECT.bottom + 120, dt, boat_speed)
                        boat_status = "Sell mode: waiting dock slot"
                    else:
                        spot = get_barge_dock_spots()[slot]
                        at_base, move_dx, move_dy = move_boat_toward_point_speed(boat_rect, int(spot["x"]), int(spot["y"]), dt, boat_speed)
                        if at_base:
                            docked = True
                            facing_angle = float(spot["angle"])
                    boat_visible = True
                    if not at_base:
                        if slot is not None:
                            boat_status = "Sell mode: docking"
                    else:
                        if trash_stored > 0:
                            recycling_inventory += trash_stored
                            recycling_stock_value += cargo_sale_value
                            trash_stored = 0
                            cargo_sale_value = 0.0

                        if recycling_inventory <= 0:
                            boat_status = "Sell mode: waiting stock"
                        else:
                            load_units = min(boat_capacity, recycling_inventory)
                            stock_units_before = recycling_inventory
                            unit_value = (recycling_stock_value / stock_units_before) if stock_units_before > 0 else 0.0
                            load_value = unit_value * load_units
                            recycling_inventory -= load_units
                            recycling_stock_value = max(0.0, recycling_stock_value - load_value)
                            trash_stored = load_units
                            cargo_sale_value = load_value
                            sell_phase = "to_exit"
                            boat_status = f"Sell mode: loaded {load_units}"

                elif sell_phase == "to_exit":
                    boat["dock_slot"] = None
                    boat_status = "Sell mode: outbound"
                    at_exit, move_dx, move_dy = move_boat_toward_point_speed(boat_rect, SELL_EXIT_POINT[0], SELL_EXIT_POINT[1], dt, boat_speed)
                    if at_exit:
                        sell_phase = "selling"
                        sell_timer = SELL_TRIP_SECONDS
                        boat_visible = False

                elif sell_phase == "selling":
                    boat["dock_slot"] = None
                    sell_timer = max(0.0, sell_timer - dt)
                    boat_status = f"Selling offshore ({sell_timer:.1f}s)"
                    boat_visible = False
                    if sell_timer <= 0.0:
                        sold_units = trash_stored
                        if sold_units > 0:
                            sell_multiplier = 1.0 + (fame / 200.0)
                            pending_sale_revenue = cargo_sale_value * sell_multiplier
                            pending_sale_units = sold_units
                            trash_stored = 0
                            cargo_sale_value = 0.0
                        boat_rect.center = SELL_EXIT_POINT
                        sell_phase = "to_base"
                        boat_visible = True

                elif sell_phase == "to_base":
                    boat_status = "Returning from sale"
                    slot = get_or_assign_dock_slot(boat, boats)
                    if slot is None:
                        at_base, move_dx, move_dy = move_boat_toward_point_speed(boat_rect, BASE_RECT.centerx, BASE_RECT.bottom + 120, dt, boat_speed)
                        boat_status = "Returning from sale (queue)"
                    else:
                        spot = get_barge_dock_spots()[slot]
                        at_base, move_dx, move_dy = move_boat_toward_point_speed(boat_rect, int(spot["x"]), int(spot["y"]), dt, boat_speed)
                        if at_base:
                            docked = True
                            facing_angle = float(spot["angle"])
                    boat_visible = True
                    if at_base:
                        if pending_sale_revenue > 0.0 and pending_sale_units > 0:
                            money += pending_sale_revenue
                            add_transaction(f"Boat {boat_id} sale +${pending_sale_revenue:.1f} ({pending_sale_units} units)")
                            pending_sale_revenue = 0.0
                            pending_sale_units = 0

                        if boat_type == "Heavy Boat":
                            fuel_room = max(0.0, BARGE_FUEL_CAPACITY - barge_fuel_storage)
                            buy_units = min(HEAVY_SELL_FUEL_REBUY_UNITS, fuel_room, money / max(1e-6, BARGE_FUEL_BUY_PRICE))
                            if buy_units > 0.1:
                                buy_cost = buy_units * BARGE_FUEL_BUY_PRICE
                                money -= buy_cost
                                barge_fuel_storage = min(BARGE_FUEL_CAPACITY, barge_fuel_storage + buy_units)
                                add_transaction(f"Heavy Boat fuel load +{int(buy_units)} (cost ${buy_cost:.1f})")

                        sell_phase = "dock_wait"
                        sell_timer = SELL_DOCK_SECONDS

                else:
                    sell_timer = max(0.0, sell_timer - dt)
                    boat_status = f"Docking at barge ({sell_timer:.1f}s)"
                    boat_visible = True
                    if sell_timer <= 0.0:
                        sell_phase = "idle"

            if math.hypot(move_dx, move_dy) > 1e-3:
                fuel_seconds = max(0.0, fuel_seconds - dt)

            if abs(move_dx) > 1e-4 or abs(move_dy) > 1e-4:
                facing_angle = math.degrees(math.atan2(move_dy, move_dx))
                maybe_spawn_wake(wake_particles, boat_rect, move_dx, move_dy, dt)

            boat["mode"] = boat_mode
            boat["pending_mode"] = pending_mode
            boat["state"] = boat_state
            boat["fuel"] = fuel_seconds
            boat["refuel_left"] = max(0.0, refuel_seconds_left)
            boat["trash_stored"] = trash_stored
            boat["cargo_sale_value"] = cargo_sale_value
            boat["collected_total"] = collected_total
            boat["visible"] = boat_visible
            boat["facing_angle"] = facing_angle
            boat["sell_phase"] = sell_phase
            boat["sell_timer"] = sell_timer
            boat["pending_sale_revenue"] = pending_sale_revenue
            boat["pending_sale_units"] = pending_sale_units
            boat["status"] = boat_status
            boat["refuel_lock"] = refuel_lock_active
            boat["dock_slot"] = dock_slot if isinstance(boat.get("dock_slot"), int) else boat.get("dock_slot")
            boat["docked"] = docked

            fleet_boats.append({
                "id": boat_id,
                "type": boat_type,
                "mode": boat_mode,
                "status": boat_status,
                "state": boat_state,
                "fuel_seconds": fuel_seconds,
                "max_fuel": MAX_FUEL_SECONDS,
                "refuel_seconds_left": float(boat["refuel_left"]),
                "refuel_total": boat_refuel_seconds,
                "is_refueling": boat_state == STATE_REFUELING,
                "crew_min": crew_min,
                "crew_max": crew_max,
                "crew_assigned": crew_assigned,
                "cargo": trash_stored,
                "capacity": boat_capacity,
                "collected": collected_total,
                "world_x": boat_rect.centerx,
                "world_y": boat_rect.centery,
                "docked": docked,
            })

        # economy + derived stats
        assigned_total = sum(int(b["crew_assigned"]) for b in boats)
        manpower_cost = ((manpower_cost_per_min + assigned_total * 1.4) / 60.0) * dt
        fuel_cost = ((fuel_cost_per_min + len(boats) * 1.1) / 60.0) * dt
        general_cost = (general_cost_per_min / 60.0) * dt
        frame_cost = manpower_cost + fuel_cost + general_cost
        money -= frame_cost

        pending_cost_total += frame_cost
        cost_transaction_timer += dt
        if cost_transaction_timer >= cost_transaction_interval:
            add_transaction(
                f"Ops costs -${pending_cost_total:.1f} "
                f"(crew -${((manpower_cost_per_min + assigned_total * 1.4) / 60.0 * cost_transaction_timer):.1f}, "
                f"fuel -${((fuel_cost_per_min + len(boats) * 1.1) / 60.0 * cost_transaction_timer):.1f}, "
                f"general -${(general_cost_per_min / 60.0 * cost_transaction_timer):.1f})"
            )
            cost_transaction_timer = 0.0
            pending_cost_total = 0.0

        collection_rate = (trash_collected / max(1.0, elapsed_seconds)) * 60.0
        morale_penalty = 3.0 * returning_count
        morale = max(40.0, min(96.0, 68.0 + fame * 0.25 - morale_penalty))

        update_wake(wake_particles, dt)

        if ocean_tile is not None:
            draw_tiled_ocean(screen, ocean_tile, camera_x, camera_y)
        else:
            map_surface = screen.subsurface(VIEWPORT_RECT)
            draw_fallback_ocean_gradient(map_surface)

        for item in trash_items:
            item.draw(screen, camera_x, camera_y)

        for p in wake_particles:
            p.draw(screen, camera_x, camera_y)

        draw_base_ship(screen, base_font, camera_x, camera_y, mothership_sprite)

        for boat in boats:
            if not bool(boat["visible"]):
                continue
            boat_type = str(boat["type"])
            sprite = boat_sprites.get(boat_type)
            draw_boat(
                screen,
                boat["rect"],
                camera_x,
                camera_y,
                sprite,
                float(boat["facing_angle"]),
                boat_type,
            )

        draw_offscreen_target_indicator(
            screen,
            body_font,
            camera_x,
            camera_y,
            BASE_RECT.centerx,
            BASE_RECT.centery,
            "Barge",
            (245, 220, 140),
        )

        for boat in fleet_boats:
            bx = int(boat.get("world_x", BASE_RECT.centerx))
            by = int(boat.get("world_y", BASE_RECT.centery))
            label = f"{boat.get('type', 'Boat')} {boat.get('id', '?')}"
            draw_offscreen_target_indicator(
                screen,
                body_font,
                camera_x,
                camera_y,
                bx,
                by,
                label,
                (150, 215, 255),
            )

        # Clear-day clouds should be the top world layer.
        draw_clear_clouds(screen, clear_clouds, camera_x, camera_y)

        total_trash_stored = sum(int(b["trash_stored"]) for b in boats)
        crew_available = max(0, crew_total - assigned_total)

        menu_max_scroll, mode_button_rects = draw_sidebar(
            screen,
            body_font,
            company_name,
            trash_collected,
            len(trash_items),
            score,
            money,
            fame,
            crew_total,
            crew_available,
            morale,
            total_trash_stored,
            recycling_inventory,
            barge_fuel_storage,
            BARGE_FUEL_CAPACITY,
            manpower_cost_per_min + assigned_total * 1.4,
            fuel_cost_per_min + len(boats) * 1.1,
            general_cost_per_min,
            (manpower_cost_per_min + assigned_total * 1.4) + (fuel_cost_per_min + len(boats) * 1.1) + general_cost_per_min,
            collection_rate,
            transactions,
            menu_scroll,
            fleet_boats,
        )
        menu_scroll = max(0.0, min(menu_scroll, menu_max_scroll))

        if intro_fade_alpha > 0.0:
            fade_overlay = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.SRCALPHA)
            fade_overlay.fill((0, 0, 0, int(max(0.0, min(255.0, intro_fade_alpha)))))
            screen.blit(fade_overlay, (0, 0))
            intro_fade_alpha = max(0.0, intro_fade_alpha - 220.0 * dt)

        apply_pixelation(screen, VIEWPORT_RECT)
        pygame.display.flip()
        await asyncio.sleep(0)

    pygame.quit()


async def main() -> None:
    await run_game()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pygame.quit()
        sys.exit(0)
