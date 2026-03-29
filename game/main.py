"""Pixel Boat Cleanup V0.

- Boat automatically moves toward trash
- Boat has a 10-second fuel tank
- When fuel runs out, it returns to base ship to refuel, then resumes cleanup
- Scrollable world with click-drag camera
- Left sidebar HUD (does not cover the map)
- Ocean uses tiled asset from assets/ocean.jpeg
- Boat uses speedboat sprite (assets/smallboat.png currently) with 8-direction facing
- Wave particles trail behind the moving boat
"""

from __future__ import annotations

import asyncio
import math
import random
import sys
from collections import deque
from pathlib import Path

import pygame

try:
    from .intro import play_intro
except ImportError:
    from intro import play_intro

try:
    from .services import (
        generate_ocean_cleanup_quiz_async,
        generate_ocean_fact_async,
        generate_ocean_tip_async,
        choose_fallback_quiz,
        choose_fallback_fact,
        choose_fallback_tip,
    )
except ImportError:
    try:
        from services import (
            generate_ocean_cleanup_quiz_async,
            generate_ocean_fact_async,
            generate_ocean_tip_async,
            choose_fallback_quiz,
            choose_fallback_fact,
            choose_fallback_tip,
        )
    except ImportError:
        generate_ocean_cleanup_quiz_async = None
        generate_ocean_fact_async = None
        generate_ocean_tip_async = None
        choose_fallback_quiz = None
        choose_fallback_fact = None
        choose_fallback_tip = None


# Window layout
WINDOW_WIDTH = 1440
WINDOW_HEIGHT = 820
SIDEBAR_WIDTH = 390
PIXELATE_SCALE = 2
WORLD_ENTITY_SCALE = 0.78
SKIP_INTRO_FOR_TESTING = False
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
EDUCATION_PROMPT_INTERVAL_SECONDS = 30.0
DONATION_MIN_INTERVAL = 48.0
DONATION_MAX_INTERVAL = 92.0
DONATION_MIN_AMOUNT = 260
DONATION_MAX_AMOUNT = 1150
MAX_FUEL_SECONDS = 20.0
REFUEL_SECONDS = 2.0
MIN_REFUEL_SECONDS = 1.5
BARGE_FUEL_CAPACITY = 1800.0
BARGE_FUEL_START = BARGE_FUEL_CAPACITY
BARGE_FUEL_UNITS_PER_BOAT_FUEL_SEC = 6.0
BARGE_FUEL_BUY_PRICE = 1.6
HEAVY_SELL_FUEL_REBUY_UNITS = 240.0
SPEEDBOAT_PURCHASE_COST = 650.0

# Big base ship in world corner
BASE_RECT = pygame.Rect(WORLD_WIDTH // 2 - 330, WORLD_HEIGHT // 2 - 195, 660, 390)

# Fast, deterministic dock lines relative to barge center (hackathon-stable mode).
# Tweak these if you want to shift where boats park.
SHOW_DOCK_DEBUG_DEFAULT = True

DOCK_SEGMENTS_FROM_CENTER = [
    # Left side (vertical segment)
    {"x1": -206.0, "y1": -60.0, "x2": -206.0, "y2": 60.0, "nx": -1.0, "ny": 0.0, "angle": 90.0},
    # Top side (horizontal segment)
    {"x1": -118.0, "y1": -95.0, "x2": -18.0, "y2": -95.0, "nx": 0.0, "ny": -1.0, "angle": 180.0},
    # Bottom side (horizontal segment)
    {"x1": -82.0, "y1": 95.0, "x2": 58.0, "y2": 95.0, "nx": 0.0, "ny": 1.0, "angle": 180.0},
]

# Assets
ASSETS_DIR = Path(__file__).resolve().parent / "assets"
OCEAN_TILE_PATH = ASSETS_DIR / "ocean.jpeg"
OCEAN_TILE_SCALE = 0.4
SPEEDBOAT_SPRITE_PATH = ASSETS_DIR / "smallboat.png"
TUGBOAT_SPRITE_PATH = ASSETS_DIR / "tuboat.png"
BOAT_GUIDE_PATH_BY_TYPE = {
    "Speedboat": ASSETS_DIR / "smallboat_guide.png",
    "Tugboat": ASSETS_DIR / "tuboat_guide.png",
}
MOTHERSHIP_GUIDE_PATH = ASSETS_DIR / "mothership_guide.png"
BOAT_SPRITE_SCALE = 1.0 * WORLD_ENTITY_SCALE
BOAT_SPRITE_ANGLE_OFFSET = 90.0  # default offset
BOAT_SPRITE_ANGLE_OFFSET_BY_TYPE = {
    "Speedboat": 90.0,
    "Tugboat": 0.0,
}
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
BARGE_TRASH_CAPACITY = 220
BARGE_TRIP_SPEED = 175.0
BARGE_SELL_TIME = 2.4
HEAVY_TRANSPORT_SPEED = 150.0
HEAVY_TRANSPORT_DOCK_TIME = 1.4
BARGE_FUEL_RESTOCK_UNITS = 280.0
BARGE_MIN_SELL_PRICE_PER_UNIT = 3.2
BARGE_RESTOCK_BUDGET_RATIO = 0.30
TRANSPORTER_FUEL_BUY_UNITS = 420.0

BOAT_TYPE = "Speedboat"
# Real-world inspired references (scaled down for gameplay):
# - Speedboat length/persons from Boston Whaler 170 Montauk (17'4", 7 persons).
# - Tugboat speed/crew from Damen Stan Tug class sheets (around 10-11 knots, small crew).
# - Heavy workboat speed/crew from multicat workboat profiles (~9 knots, multi-crew).
# - Hovercraft dimensions from Griffon commercial hovercraft class specs.
BOAT_CAPACITY_BY_TYPE = {
    "Speedboat": 64,
    "Tugboat": 28,
}
BOAT_CREW_MIN_BY_TYPE = {
    "Speedboat": 0,
    "Tugboat": 2,
}
BOAT_CREW_MAX_BY_TYPE = {
    "Speedboat": 0,
    "Tugboat": 4,
}
BOAT_REFUEL_SECONDS_BY_TYPE = {
    "Speedboat": 4.8,
    "Tugboat": 6.0,
}

# Speeds are scaled to in-game pixels/sec from approximate knot classes.
BOAT_SPEED_BY_TYPE = {
    "Speedboat": 145.0,
    "Tugboat": 52.0,
}

# In-game hull sizes use the same global world scale for all boats.
BOAT_BASE_SIZE_BY_TYPE = {
    "Speedboat": (18, 10),
    "Tugboat": (32, 15),
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
    "Tugboat": 8.2,
}

BOAT_COLOR_BY_TYPE = {
    "Speedboat": (245, 192, 50),
    "Tugboat": (208, 142, 76),
}

VEHICLE_TYPES = [
    {"name": "Speedboat", "category": "Boat", "crew_min": 0, "crew_max": 0},
    {"name": "Tugboat", "category": "Boat", "crew_min": 2, "crew_max": 4},
]


def display_boat_type(boat_type: str) -> str:
    if boat_type == "Speedboat":
        return "Boat"
    return boat_type


def required_speedboat_fuel_seconds(speed: float) -> float:
    points = [
        (0, 0),
        (WORLD_WIDTH // 2, 0),
        (WORLD_WIDTH - 1, 0),
        (0, WORLD_HEIGHT // 2),
        (WORLD_WIDTH - 1, WORLD_HEIGHT // 2),
        (0, WORLD_HEIGHT - 1),
        (WORLD_WIDTH // 2, WORLD_HEIGHT - 1),
        (WORLD_WIDTH - 1, WORLD_HEIGHT - 1),
    ]
    max_dist = 0.0
    for px, py in points:
        max_dist = max(max_dist, math.hypot(BASE_RECT.centerx - px, BASE_RECT.centery - py))
    return (max_dist / max(1e-6, speed)) + 2.0


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
        "Tugboat": TUGBOAT_SPRITE_PATH,
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


def _extract_color_points(surface: pygame.Surface, color: str) -> list[tuple[int, int]]:
    pts: list[tuple[int, int]] = []
    w, h = surface.get_size()
    for y in range(h):
        for x in range(w):
            r, g, b, a = surface.get_at((x, y))
            if a < 120:
                continue
            if color == "magenta":
                if r > 220 and b > 220 and g < 130:
                    pts.append((x, y))
            elif color == "cyan":
                if g > 220 and b > 220 and r < 130:
                    pts.append((x, y))
            elif color == "green":
                if g > 220 and r < 130 and b < 130:
                    pts.append((x, y))
    return pts


def _connected_components(points: list[tuple[int, int]]) -> list[list[tuple[int, int]]]:
    if not points:
        return []
    point_set = set(points)
    components: list[list[tuple[int, int]]] = []

    while point_set:
        sx, sy = point_set.pop()
        comp = [(sx, sy)]
        q: deque[tuple[int, int]] = deque([(sx, sy)])

        while q:
            x, y = q.popleft()
            for nx in (x - 1, x, x + 1):
                for ny in (y - 1, y, y + 1):
                    if nx == x and ny == y:
                        continue
                    if (nx, ny) in point_set:
                        point_set.remove((nx, ny))
                        q.append((nx, ny))
                        comp.append((nx, ny))

        components.append(comp)
    return components


def _segment_from_component(component: list[tuple[int, int]]) -> dict[str, float] | None:
    if len(component) < 8:
        return None
    xs = [p[0] for p in component]
    ys = [p[1] for p in component]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)

    span_x = max_x - min_x
    span_y = max_y - min_y

    if span_x >= span_y:
        y = sum(ys) / len(ys)
        return {"x1": float(min_x), "y1": float(y), "x2": float(max_x), "y2": float(y), "axis": 0.0, "cx": float(sum(xs) / len(xs)), "cy": float(y)}

    x = sum(xs) / len(xs)
    return {"x1": float(x), "y1": float(min_y), "x2": float(x), "y2": float(max_y), "axis": 90.0, "cx": float(x), "cy": float(sum(ys) / len(ys))}


def load_boat_dock_guides(boat_sprites: dict[str, pygame.Surface]) -> dict[str, dict[str, object]]:
    guides: dict[str, dict[str, object]] = {}

    for boat_type, sprite in boat_sprites.items():
        guide_path = BOAT_GUIDE_PATH_BY_TYPE.get(boat_type)
        if guide_path is None or not guide_path.exists():
            continue

        try:
            raw = pygame.image.load(str(guide_path)).convert_alpha()
        except pygame.error:
            continue

        guide = pygame.transform.scale(raw, sprite.get_size())
        sides: list[dict[str, float]] = []
        for color in ("magenta",):
            pts = _extract_color_points(guide, color)
            comps = _connected_components(pts)
            if not comps:
                continue
            comp = max(comps, key=len)
            seg = _segment_from_component(comp)
            if seg is None:
                continue
            seg["color"] = color
            seg["offset_x"] = float(seg["cx"] - (guide.get_width() * 0.5))
            seg["offset_y"] = float(seg["cy"] - (guide.get_height() * 0.5))
            sides.append(seg)

        if sides:
            guides[boat_type] = {"sides": sides}

    return guides


def _fallback_barge_dock_spots() -> list[dict[str, float]]:
    return [
        {"x1": float(BASE_RECT.left - 20), "y1": float(BASE_RECT.centery - 70), "x2": float(BASE_RECT.left - 20), "y2": float(BASE_RECT.centery + 70), "nx": -1.0, "ny": 0.0, "angle": 90.0},
        {"x1": float(BASE_RECT.left + 80), "y1": float(BASE_RECT.top - 14), "x2": float(BASE_RECT.left + 210), "y2": float(BASE_RECT.top - 14), "nx": 0.0, "ny": -1.0, "angle": 180.0},
        {"x1": float(BASE_RECT.left + 165), "y1": float(BASE_RECT.bottom + 14), "x2": float(BASE_RECT.left + 300), "y2": float(BASE_RECT.bottom + 14), "nx": 0.0, "ny": 1.0, "angle": 180.0},
    ]

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


class WaveParticle:
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
    barge_angle_degrees: float = 0.0,
) -> None:
    base_screen = world_rect_to_screen(BASE_RECT, camera_x, camera_y)

    if mothership_sprite is not None:
        snapped = quantize_angle_to_8(barge_angle_degrees)
        rotated = pygame.transform.rotate(mothership_sprite, -snapped)
        sprite_rect = rotated.get_rect(center=base_screen.center)
        surface.blit(rotated, sprite_rect)
        return

    pygame.draw.rect(surface, BASE_FILL, base_screen, border_radius=10)
    pygame.draw.rect(surface, BASE_OUTLINE, base_screen, width=3, border_radius=10)
    deck = base_screen.inflate(-34, -44)
    pygame.draw.rect(surface, BASE_DECK, deck, border_radius=8)
    pygame.draw.rect(surface, BASE_OUTLINE, deck, width=2, border_radius=8)
    label = base_font.render("MOTHERSHIP", True, TEXT_COLOR)
    surface.blit(label, (base_screen.x + 18, base_screen.y + 10))

def draw_dock_debug_overlay(
    surface: pygame.Surface,
    font: pygame.font.Font,
    camera_x: float,
    camera_y: float,
    dock_spots: list[dict[str, float]],
) -> None:
    # Visual tuning overlay for dock segments and normals.
    for i, spot in enumerate(dock_spots, start=1):
        x1 = int(spot.get("x1", BASE_RECT.centerx))
        y1 = int(spot.get("y1", BASE_RECT.centery))
        x2 = int(spot.get("x2", BASE_RECT.centerx))
        y2 = int(spot.get("y2", BASE_RECT.centery))

        sx1, sy1 = world_to_screen(x1, y1, camera_x, camera_y)
        sx2, sy2 = world_to_screen(x2, y2, camera_x, camera_y)

        color = (255, 90, 90) if i == 1 else ((90, 255, 120) if i == 2 else (90, 170, 255))
        pygame.draw.line(surface, color, (sx1, sy1), (sx2, sy2), 3)
        pygame.draw.circle(surface, color, (sx1, sy1), 4)
        pygame.draw.circle(surface, color, (sx2, sy2), 4)

        mx = int((x1 + x2) * 0.5)
        my = int((y1 + y2) * 0.5)
        nx = float(spot.get("nx", 0.0))
        ny = float(spot.get("ny", 0.0))
        ex = int(mx + nx * 26.0)
        ey = int(my + ny * 26.0)
        smx, smy = world_to_screen(mx, my, camera_x, camera_y)
        sex, sey = world_to_screen(ex, ey, camera_x, camera_y)
        pygame.draw.line(surface, (255, 245, 160), (smx, smy), (sex, sey), 2)

        label = font.render(f"D{i}", True, (255, 255, 255))
        surface.blit(label, (smx + 6, smy - 10))

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

    angle_offset = BOAT_SPRITE_ANGLE_OFFSET_BY_TYPE.get(boat_type or "", BOAT_SPRITE_ANGLE_OFFSET)
    draw_angle = facing_angle_degrees + angle_offset
    if boat_type == "Tugboat":
        snapped_angle = draw_angle
    else:
        snapped_angle = quantize_angle_to_8(draw_angle)
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
    barge_trip_phase: str,
    boat_purchase_cost: float,
    can_buy_boat: bool,
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

        title_surf = body_font.render(title, False, TEXT_COLOR)
        content.blit(title_surf, (10, y + 8))

        ly = y + 30
        for line in wrapped_lines:
            surf = body_font.render(line, False, MUTED_TEXT)
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

    y, barge_card_rect = draw_card(y, "Barge", [
        f"Trash Stock: {recycling_inventory}/{BARGE_TRASH_CAPACITY}",
        f"Ops Spend/min: ${total_cost_per_min:.1f}",
        f"Fuel Spend/min: ${fuel_cost_per_min:.1f}",
        f"Barge Fuel: {int(barge_fuel_storage)}/{int(barge_fuel_capacity)}",
        ".",
        ".",
    ], 1)

    sell_enabled = (barge_trip_phase == "idle") and (recycling_inventory > 0)
    fuel_room = max(0.0, barge_fuel_capacity - barge_fuel_storage)
    buy_enabled = (barge_trip_phase == "idle") and (fuel_room > 2.0)

    btn_h = 20
    row_gap = 6

    sell_txt = body_font.render("Sell Trash", False, (255, 255, 255))
    buy_txt = body_font.render("Buy Fuel", False, (255, 255, 255))
    btn_w = min(content_w - 22, max(sell_txt.get_width(), buy_txt.get_width()) + 26)
    # Left-side aligned and moved slightly lower to avoid overlap glitches.
    btn_x = barge_card_rect.x + 12

    buy_y = barge_card_rect.bottom - (btn_h * 2 + row_gap + 4) + 5
    sell_y = buy_y + btn_h + row_gap

    buy_btn = pygame.Rect(btn_x, buy_y, btn_w, btn_h)
    sell_btn = pygame.Rect(btn_x, sell_y, btn_w, btn_h)

    buy_fill = (102, 75, 50) if buy_enabled else (86, 68, 49)
    buy_border = (154, 122, 86) if buy_enabled else (122, 96, 70)
    buy_color = (255, 255, 255) if buy_enabled else (200, 188, 170)
    pygame.draw.rect(content, buy_fill, buy_btn)
    pygame.draw.rect(content, buy_border, buy_btn, width=1)
    buy_lbl = body_font.render("Buy Fuel", False, buy_color)
    content.blit(buy_lbl, (buy_btn.x + (buy_btn.width - buy_lbl.get_width()) // 2, buy_btn.y + 2))
    if buy_enabled:
        mode_buttons_content["barge:buyfuel"] = buy_btn

    sell_fill = (102, 75, 50) if sell_enabled else (86, 68, 49)
    sell_border = (154, 122, 86) if sell_enabled else (122, 96, 70)
    sell_color = (255, 255, 255) if sell_enabled else (200, 188, 170)
    sell_lbl = body_font.render("Sell Trash", False, sell_color)
    pygame.draw.rect(content, sell_fill, sell_btn)
    pygame.draw.rect(content, sell_border, sell_btn, width=1)
    content.blit(sell_lbl, (sell_btn.x + (sell_btn.width - sell_lbl.get_width()) // 2, sell_btn.y + 2))
    if sell_enabled:
        mode_buttons_content["barge:selltrash"] = sell_btn

    y, buy_boat_card = draw_card(y, "Buy More Boats", [
        "Add 1 Boat",
        f"Cost: ${int(boat_purchase_cost)}",
    ], 3)

    buy_boat_btn = pygame.Rect(buy_boat_card.x + 12, buy_boat_card.bottom - 30, min(content_w - 24, 152), 20)
    buy_fill = (102, 75, 50) if can_buy_boat else (86, 68, 49)
    buy_border = (154, 122, 86) if can_buy_boat else (122, 96, 70)
    buy_color = (255, 255, 255) if can_buy_boat else (200, 188, 170)
    pygame.draw.rect(content, buy_fill, buy_boat_btn)
    pygame.draw.rect(content, buy_border, buy_boat_btn, width=1)
    buy_boat_lbl = body_font.render(f"Buy Boat (${int(boat_purchase_cost)})", False, buy_color)
    content.blit(buy_boat_lbl, (buy_boat_btn.x + (buy_boat_btn.width - buy_boat_lbl.get_width()) // 2, buy_boat_btn.y + 2))
    if can_buy_boat:
        mode_buttons_content["fleet:buyboat"] = buy_boat_btn

    y, _ = draw_card(y, "Control Key", [
        "C = Collect",
        "S = Sell",
        "R = Return To Barge",
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
    fleet_title = body_font.render("Fleet", False, TEXT_COLOR)
    content.blit(fleet_title, (10, fleet_top + 8))

    for i, boat in enumerate(fleet_boats):
        row_y = fleet_top + 34 + i * (row_h + row_gap)
        row_rect = pygame.Rect(8, row_y, content_w - 16, row_h)
        pygame.draw.rect(content, (126, 93, 60), row_rect)
        pygame.draw.rect(content, (170, 136, 95), row_rect, width=1)

        boat_id = int(boat.get("id", i + 1))
        boat_type = str(boat.get("type", "Boat"))
        boat_display_type = display_boat_type(boat_type)
        status = str(boat.get("status", "Idle"))
        mode = str(boat.get("mode", MODE_COLLECT))
        actions = [("collect", "C"), ("return", "R")]
        btn_w = 24
        btn_h = 20
        action_w = len(actions) * (btn_w + 4)
        start_x = row_rect.right - action_w - 12

        name_surf = body_font.render(f"B{boat_id} {boat_display_type}", False, (255, 255, 255))
        content.blit(name_surf, (row_rect.x + 6, row_rect.y + 3))

        # Controls stay beside the boat row header, not below it.
        controls_y = row_rect.y + 12

        action_start_x = start_x
        for j, (action, short) in enumerate(actions):
            bx = action_start_x + j * (btn_w + 4)
            by = controls_y
            brect = pygame.Rect(bx, by, btn_w, btn_h)
            enabled = True
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
            txt = body_font.render(short, False, txt_color)
            content.blit(txt, (brect.x + 6, brect.y + 2))
            if enabled:
                mode_buttons_content[f"{boat_id}:{action}"] = brect

        text_max_w = max(30, start_x - (row_rect.x + 8) - 8)
        status_lines = wrap_line(status, text_max_w)[:2]
        for s_idx, s_line in enumerate(status_lines):
            status_surf = body_font.render(s_line, False, (240, 232, 220))
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
        boat_display_type = display_boat_type(boat_type)
        status = str(boat.get("status", "Idle"))
        fuel_seconds = float(boat.get("fuel_seconds", 0.0))
        max_fuel = float(boat.get("max_fuel", MAX_FUEL_SECONDS))
        refuel_left = float(boat.get("refuel_seconds_left", 0.0))
        refuel_total = float(boat.get("refuel_total", REFUEL_SECONDS))
        is_refueling = bool(boat.get("is_refueling", False))
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

        title = body_font.render(f"Boat {boat_id} Panel", False, TEXT_COLOR)
        content.blit(title, (10, y + 8))

        ty = y + 30
        l1 = body_font.render(f"Type: {boat_display_type}", False, MUTED_TEXT)
        content.blit(l1, (10, ty))
        ty += 18

        for line in status_lines:
            surf = body_font.render(line, False, MUTED_TEXT)
            content.blit(surf, (10, ty))
            ty += 18

        for line in trash_lines:
            surf = body_font.render(line, False, MUTED_TEXT)
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

    y, _ = draw_card(y, "Costs", [
        f"Manpower/min: ${manpower_cost_per_min:.1f}",
        f"Fuel/min: ${fuel_cost_per_min:.1f}",
        f"General/min: ${general_cost_per_min:.1f}",
        f"Boat Purchase: ${int(boat_purchase_cost)}",
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


def move_rect_center_toward(
    rect: pygame.Rect,
    target_x: int,
    target_y: int,
    dt: float,
    speed: float,
    clamp_world: bool = True,
) -> tuple[bool, float, float]:
    cx, cy = rect.center
    dx = target_x - cx
    dy = target_y - cy
    dist = math.hypot(dx, dy)
    if dist <= 1.0:
        rect.center = (target_x, target_y)
        if clamp_world:
            rect.clamp_ip(WORLD_RECT)
        return True, 0.0, 0.0

    step = max(1e-4, speed) * dt
    if step >= dist:
        rect.center = (target_x, target_y)
        if clamp_world:
            rect.clamp_ip(WORLD_RECT)
        return True, float(dx), float(dy)

    nx = dx / dist
    ny = dy / dist
    move_dx = nx * step
    move_dy = ny * step
    rect.center = (int(cx + move_dx), int(cy + move_dy))
    if clamp_world:
        rect.clamp_ip(WORLD_RECT)
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


def get_barge_dock_spots(mothership_sprite: pygame.Surface | None) -> list[dict[str, float]]:
    # Simple mode: all boats dock to barge center.
    return [{"x": float(BASE_RECT.centerx), "y": float(BASE_RECT.centery), "angle": 180.0}]


def keep_boat_out_of_barge(boat_rect: pygame.Rect) -> None:
    # Simple mode: allow boats to pass through/into barge area.
    return


def get_spot_anchor(spot: dict[str, float]) -> tuple[float, float]:
    return (float(spot.get("x", BASE_RECT.centerx)), float(spot.get("y", BASE_RECT.centery)))


def resolve_dock_target_for_boat(
    boat_rect: pygame.Rect,
    spot: dict[str, float],
    boat_type: str | None = None,
    dock_guide: dict[str, object] | None = None,
    visual_size: tuple[int, int] | None = None,
) -> tuple[int, int, float]:
    return (
        int(spot.get("x", BASE_RECT.centerx)),
        int(spot.get("y", BASE_RECT.centery)),
        float(spot.get("angle", 180.0)),
    )


def get_or_assign_dock_slot(boat: dict[str, object], boats: list[dict[str, object]], spots: list[dict[str, float]]) -> int | None:
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
    slot = min(free_slots, key=lambda i: (get_spot_anchor(spots[i])[0] - bx) ** 2 + (get_spot_anchor(spots[i])[1] - by) ** 2)
    boat["dock_slot"] = slot
    return slot


def get_nearest_dock_queue_point(boat_rect: pygame.Rect, spots: list[dict[str, float]]) -> tuple[int, int]:
    if not spots:
        return BASE_RECT.left - 80, BASE_RECT.centery

    bx, by = boat_rect.center
    nearest = min(spots, key=lambda spot: (get_spot_anchor(spot)[0] - bx) ** 2 + (get_spot_anchor(spot)[1] - by) ** 2)
    near_x, near_y = get_spot_anchor(nearest)
    dx = near_x - BASE_RECT.centerx
    dy = near_y - BASE_RECT.centery
    margin = 84

    if abs(dx) >= abs(dy):
        qx = BASE_RECT.left - margin if dx < 0 else BASE_RECT.right + margin
        qy = int(max(BASE_RECT.top - margin, min(BASE_RECT.bottom + margin, by)))
    else:
        qx = int(max(BASE_RECT.left - margin, min(BASE_RECT.right + margin, bx)))
        qy = BASE_RECT.top - margin if dy < 0 else BASE_RECT.bottom + margin

    return int(qx), int(qy)


def move_boat_toward_dock_spot(
    boat_rect: pygame.Rect,
    spot: dict[str, float],
    dt: float,
    speed: float,
    boat_type: str | None = None,
    dock_guide: dict[str, object] | None = None,
    visual_size: tuple[int, int] | None = None,
) -> tuple[bool, float, float]:
    target_x, target_y, _ = resolve_dock_target_for_boat(boat_rect, spot, boat_type, dock_guide, visual_size)
    return move_boat_toward_point_speed(boat_rect, target_x, target_y, dt, speed)


def maybe_spawn_wave(
    wave_particles: list[WaveParticle],
    boat_rect: pygame.Rect,
    move_dx: float,
    move_dy: float,
    dt: float,
    centered: bool = False,
) -> None:
    speed = math.hypot(move_dx, move_dy)
    if speed < 0.2:
        return

    # Spawn a few particles based on movement amount.
    spawn_count = max(6, int(speed / 0.8))
    cx, cy = boat_rect.center
    direction_x = move_dx / max(speed, 1e-6)
    direction_y = move_dy / max(speed, 1e-6)

    if centered:
        base_x = cx
        base_y = cy
    else:
        # Trail starts behind the boat.
        base_x = cx - direction_x * (boat_rect.width * 0.5)
        base_y = cy - direction_y * (boat_rect.height * 0.5)

    for _ in range(min(spawn_count, 16)):
        jitter_x = random.uniform(-6.0, 6.0)
        jitter_y = random.uniform(-6.0, 6.0)
        vx = -direction_x * random.uniform(24.0, 62.0) + random.uniform(-10.0, 10.0)
        vy = -direction_y * random.uniform(24.0, 62.0) + random.uniform(-10.0, 10.0)
        life = random.uniform(0.65, 1.15)
        wave_particles.append(WaveParticle(base_x + jitter_x, base_y + jitter_y, vx, vy, life))


def update_wave(wave_particles: list[WaveParticle], dt: float) -> None:
    alive: list[WaveParticle] = []
    for p in wave_particles:
        p.update(dt)
        if p.alive():
            alive.append(p)
    wave_particles[:] = alive


def wrap_lines(font: pygame.font.Font, text: str, max_width: int) -> list[str]:
    words = text.split()
    if not words:
        return [""]

    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        test = f"{current} {word}"
        if font.size(test)[0] <= max_width:
            current = test
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


async def fetch_random_education_prompt(
    previous_fact: str = "",
    previous_fallback_fact: str = "",
    previous_fallback_quiz_key: str = "",
    previous_tip: str = "",
    previous_fallback_tip: str = "",
) -> dict[str, object]:
    mode = random.choice(["quiz", "fact", "tip"])

    if mode == "quiz" and callable(generate_ocean_cleanup_quiz_async):
        q_count = 1
        try:
            questions = await generate_ocean_cleanup_quiz_async(q_count)
        except Exception:
            questions = []

        cleaned: list[dict[str, object]] = []
        for q in questions[:q_count]:
            question = str(q.get("question", "")).strip()
            options = q.get("options", [])
            if not isinstance(options, list):
                continue
            options = [str(o).strip() for o in options][:4]
            correct = str(q.get("correct", "")).strip().upper()[:1]
            if question and len(options) == 4 and correct in {"A", "B", "C", "D"}:
                cleaned.append({"question": question, "options": options, "correct": correct})

        if len(cleaned) >= 1:
            return {
                "kind": "quiz",
                "title": "Ocean Knowledge Check",
                "questions": cleaned,
                "selected": [None for _ in cleaned],
                "submitted": False,
                "score": 0,
                "_fallback_fact": "",
                "_fallback_quiz_key": "",
                "_fallback_tip": "",
            }

        if callable(choose_fallback_quiz):
            cleaned_fb, key = choose_fallback_quiz(1, previous_fallback_quiz_key)
            return {
                "kind": "quiz",
                "title": "Ocean Knowledge Check",
                "questions": cleaned_fb[:1],
                "selected": [None for _ in cleaned_fb[:1]],
                "submitted": False,
                "score": 0,
                "_fallback_fact": "",
                "_fallback_quiz_key": key,
                "_fallback_tip": "",
            }

    if mode == "tip":
        tip_text = ""
        if callable(generate_ocean_tip_async):
            try:
                tip_text = (await generate_ocean_tip_async(previous_tip)).strip()
            except Exception:
                tip_text = ""

        fallback_tip_used = ""
        if not tip_text and callable(choose_fallback_tip):
            tip_text, fallback_tip_used = choose_fallback_tip(previous_fallback_tip, previous_tip)

        if not tip_text:
            tip_text = "Use reusables and pick up litter before it reaches drains."

        return {
            "kind": "tip",
            "title": "Ocean Action Tip",
            "text": tip_text,
            "_fallback_fact": "",
            "_fallback_quiz_key": "",
            "_fallback_tip": fallback_tip_used,
        }

    fact_text = ""
    if callable(generate_ocean_fact_async):
        try:
            fact_text = (await generate_ocean_fact_async(previous_fact)).strip()
        except Exception:
            fact_text = ""

    fact_fallback_used = ""
    if not fact_text and callable(choose_fallback_fact):
        fact_text, fact_fallback_used = choose_fallback_fact(previous_fallback_fact, previous_fact)

    if not fact_text:
        fact_text = "Small cleanup actions add up and protect marine habitats over time."

    return {
        "kind": "fact",
        "title": "Ocean Fact",
        "text": fact_text,
        "_fallback_fact": fact_fallback_used,
        "_fallback_quiz_key": "",
        "_fallback_tip": "",
    }


def draw_education_modal(
    surface: pygame.Surface,
    body_font: pygame.font.Font,
    modal: dict[str, object] | None,
) -> dict[str, pygame.Rect]:
    button_rects: dict[str, pygame.Rect] = {}
    if not modal:
        return button_rects

    overlay = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 165))
    surface.blit(overlay, (0, 0))

    modal_w = min(760, VIEWPORT_RECT.width - 40)
    modal_h = min(560, WINDOW_HEIGHT - 60)
    modal_rect = pygame.Rect(
        VIEWPORT_RECT.x + (VIEWPORT_RECT.width - modal_w) // 2,
        (WINDOW_HEIGHT - modal_h) // 2,
        modal_w,
        modal_h,
    )

    pygame.draw.rect(surface, (186, 147, 96), modal_rect, border_radius=8)
    pygame.draw.rect(surface, (104, 75, 45), modal_rect, width=4, border_radius=8)

    title_font = pygame.font.SysFont("Courier New", 24, bold=True)
    title = str(modal.get("title", "Ocean Prompt"))
    t_surf = title_font.render(title, False, (255, 255, 255))
    surface.blit(t_surf, (modal_rect.x + 18, modal_rect.y + 14))

    y = modal_rect.y + 58
    kind = str(modal.get("kind", "fact"))

    if kind == "quiz":
        questions = modal.get("questions", [])
        selected = modal.get("selected", [])
        if not isinstance(questions, list):
            questions = []
        if not isinstance(selected, list):
            selected = []

        for qi, q in enumerate(questions):
            if y > modal_rect.bottom - 120:
                break
            if not isinstance(q, dict):
                continue

            q_text = str(q.get("question", "")).strip()
            q_lines = wrap_lines(body_font, f"{qi + 1}. {q_text}", modal_rect.width - 40)[:2]
            for line in q_lines:
                line_surf = body_font.render(line, False, (255, 255, 255))
                surface.blit(line_surf, (modal_rect.x + 18, y))
                y += 22

            options = q.get("options", [])
            if not isinstance(options, list):
                options = []
            option_w = (modal_rect.width - 58) // 2
            option_h = 28

            for oi, opt in enumerate(options[:4]):
                letter = chr(65 + oi)
                col = oi % 2
                row = oi // 2
                bx = modal_rect.x + 18 + col * (option_w + 10)
                by = y + row * (option_h + 8)
                brect = pygame.Rect(bx, by, option_w, option_h)
                chosen = qi < len(selected) and selected[qi] == letter
                bg = (218, 185, 130) if chosen else (158, 121, 80)
                pygame.draw.rect(surface, bg, brect, border_radius=5)
                pygame.draw.rect(surface, (92, 67, 42), brect, width=2, border_radius=5)
                txt = body_font.render(f"{letter}) {str(opt)}", False, (255, 255, 255))
                surface.blit(txt, (brect.x + 8, brect.y + 5))
                button_rects[f"q{qi}:{letter}"] = brect

            y += option_h * 2 + 14

        submitted = bool(modal.get("submitted", False))
        if submitted:
            score = int(modal.get("score", 0))
            total = len(questions)
            result = body_font.render(f"Score: {score}/{total}", False, (255, 255, 255))
            surface.blit(result, (modal_rect.x + 18, modal_rect.bottom - 78))

            done_rect = pygame.Rect(modal_rect.right - 130, modal_rect.bottom - 46, 104, 30)
            pygame.draw.rect(surface, (99, 152, 95), done_rect, border_radius=5)
            pygame.draw.rect(surface, (58, 91, 54), done_rect, width=2, border_radius=5)
            done_lbl = body_font.render("Done", False, (255, 255, 255))
            surface.blit(done_lbl, (done_rect.x + 28, done_rect.y + 5))
            button_rects["done"] = done_rect
        else:
            submit_rect = pygame.Rect(modal_rect.right - 150, modal_rect.bottom - 46, 124, 30)
            pygame.draw.rect(surface, (209, 178, 120), submit_rect, border_radius=5)
            pygame.draw.rect(surface, (92, 67, 42), submit_rect, width=2, border_radius=5)
            submit_lbl = body_font.render("Submit Quiz", False, (255, 255, 255))
            surface.blit(submit_lbl, (submit_rect.x + 10, submit_rect.y + 5))
            button_rects["submit"] = submit_rect

    else:
        fact = str(modal.get("text", ""))
        lines = wrap_lines(body_font, fact, modal_rect.width - 40)
        for line in lines[:14]:
            line_surf = body_font.render(line, False, (255, 255, 255))
            surface.blit(line_surf, (modal_rect.x + 18, y))
            y += 24

        done_rect = pygame.Rect(modal_rect.right - 120, modal_rect.bottom - 46, 94, 30)
        pygame.draw.rect(surface, (99, 152, 95), done_rect, border_radius=5)
        pygame.draw.rect(surface, (58, 91, 54), done_rect, width=2, border_radius=5)
        done_lbl = body_font.render("Done", False, (255, 255, 255))
        surface.blit(done_lbl, (done_rect.x + 22, done_rect.y + 5))
        button_rects["done"] = done_rect

    return button_rects


def draw_notifications(surface: pygame.Surface, body_font: pygame.font.Font, notices: list[dict[str, object]]) -> None:
    if not notices:
        return

    x = VIEWPORT_RECT.x + 28
    y = 18
    max_w = min(560, VIEWPORT_RECT.width - 56)

    for notice in notices[:3]:
        text = str(notice.get("text", "")).strip()
        if not text:
            continue

        pad_x = 10
        pad_y = 7
        tw, th = body_font.size(text)
        w = min(max_w, tw + pad_x * 2)
        h = th + pad_y * 2
        rect = pygame.Rect(x, y, w, h)

        pygame.draw.rect(surface, (45, 34, 25, 225), rect, border_radius=6)
        pygame.draw.rect(surface, (214, 186, 138), rect, width=2, border_radius=6)

        label = text
        if body_font.size(label)[0] > w - pad_x * 2:
            while label and body_font.size(label + "...")[0] > w - pad_x * 2:
                label = label[:-1]
            label = label + "..." if label else text[:16]

        surf = body_font.render(label, False, (255, 255, 255))
        surface.blit(surf, (rect.x + pad_x, rect.y + pad_y))
        y += h + 8


async def run_game() -> None:
    pygame.init()
    screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
    pygame.display.set_caption("MVHacks - Cleanup Fleet")
    clock = pygame.time.Clock()

    if SKIP_INTRO_FOR_TESTING:
        captain_name = "Captain"
        intro_fade_alpha = 0.0
    else:
        captain_name = await play_intro(screen, clock)
        if captain_name is None:
            pygame.quit()
            return
        intro_fade_alpha = 255.0

    company_name = f"{captain_name}'s Ocean Cleanup Co."

    body_font = pygame.font.SysFont("Courier New", 20, bold=True)
    base_font = pygame.font.SysFont("Courier New", 20, bold=True)

    ocean_tile = load_ocean_tile()
    boat_sprites = load_boat_sprites()
    boat_dock_guides = load_boat_dock_guides(boat_sprites)
    mothership_sprite = load_mothership_sprite()
    trash_sprites = load_trash_sprites()
    clear_cloud_sprites = load_clear_cloud_sprites()

    trash_items = build_initial_trash(trash_sprites)
    clear_clouds = build_clear_clouds(clear_cloud_sprites, CLEAR_CLOUD_COUNT)
    wave_particles: list[WaveParticle] = []

    trash_collected = 0
    score = 0

    # Economy + management
    money = 1200.0
    fame = 8.0
    crew_total = 0
    manpower_cost_per_min = 24.0
    fuel_cost_per_min = 12.0
    general_cost_per_min = 6.0
    total_cost_per_min = manpower_cost_per_min + fuel_cost_per_min + general_cost_per_min
    cost_transaction_interval = 8.0
    cost_transaction_timer = 0.0
    pending_cost_total = 0.0

    collection_rate = 0.0
    elapsed_seconds = 0.0
    event_log: list[str] = [f"[00:00] Captain {captain_name} online", "[00:00] Press F2: dock debug"]
    transactions: list[str] = ["[00:00] Starting balance +$1200.0"]

    camera_x = float(BASE_RECT.centerx - VIEWPORT_RECT.width // 2)
    camera_y = float(BASE_RECT.centery - VIEWPORT_RECT.height // 2)
    camera_x, camera_y = clamp_camera(camera_x, camera_y)
    dragging = False
    last_mouse = (0, 0)

    menu_scroll = 0.0
    menu_max_scroll = 0.0
    mode_button_rects: dict[str, pygame.Rect] = {}
    education_button_rects: dict[str, pygame.Rect] = {}
    education_modal: dict[str, object] | None = None
    education_task: asyncio.Task | None = None
    education_timer = 0.0
    last_education_fact = ""
    last_fallback_fact = ""
    last_fallback_quiz_key = ""
    last_education_tip = ""
    last_fallback_tip = ""

    notifications: list[dict[str, object]] = []
    donation_timer = random.uniform(DONATION_MIN_INTERVAL, DONATION_MAX_INTERVAL)
    donor_names = [
        "NOAA Grant Program",
        "Japan Marine Agency",
        "EU Ocean Fund",
        "Australia Reef Council",
        "Canada Blue Futures",
        "UN Ocean Action",
        "Norway Coast Initiative",
        "South Korea Sea Trust",
    ]

    show_dock_debug = SHOW_DOCK_DEBUG_DEFAULT

    offscreen_spawn_timer = 0.0
    win_active = False
    win_fade_alpha = 0.0

    recycling_inventory = 0
    recycling_stock_value = 0.0
    barge_fuel_storage = BARGE_FUEL_START

    barge_trip_phase = "idle"
    barge_sell_requested = False
    barge_buy_fuel_requested = False
    barge_facing_angle = 0.0

    transport_sprite = None
    if TUGBOAT_SPRITE_PATH.exists():
        try:
            tug_raw = pygame.image.load(str(TUGBOAT_SPRITE_PATH)).convert_alpha()
            tw = max(16, int(tug_raw.get_width() * 0.2))
            th = max(10, int(tug_raw.get_height() * 0.2))
            transport_sprite = pygame.transform.scale(tug_raw, (tw, th))
        except pygame.error:
            transport_sprite = boat_sprites.get("Tugboat")
    else:
        transport_sprite = boat_sprites.get("Tugboat")

    if transport_sprite is not None:
        hs_w, hs_h = transport_sprite.get_size()
    else:
        hs_w, hs_h = BOAT_SIZE_BY_TYPE.get("Tugboat", (64, 32))
        hs_w = max(hs_w, 44)
        hs_h = max(hs_h, 24)

    heavy_transport = {
        "active": False,
        "visible": False,
        "phase": "idle",
        "rect": pygame.Rect(-200, -200, hs_w, hs_h),
        "entry_vec": (1, 0),
        "exit_target": (WORLD_WIDTH + 220, WORLD_HEIGHT // 2),
        "timer": 0.0,
        "facing_angle": 0.0,
        "mission": "sell",
    }

    speedboat_max_fuel = max(
        MAX_FUEL_SECONDS * 3.0,
        required_speedboat_fuel_seconds(BOAT_SPEED_BY_TYPE.get("Speedboat", BOAT_SPEED)) * 2.0,
    )

    boat_layout = [
        ("Speedboat", (95, -70)),
    ]

    boats: list[dict[str, object]] = []
    for idx, (boat_type, offset) in enumerate(boat_layout, start=1):
        bw, bh = BOAT_SIZE_BY_TYPE.get(boat_type, BOAT_SIZE)

        boat_rect = pygame.Rect(0, 0, bw, bh)
        boat_rect.center = (BASE_RECT.centerx + offset[0], BASE_RECT.centery + offset[1])
        boat_rect.clamp_ip(WORLD_RECT)

        crew_min = 0
        crew_max = 0

        boats.append({
            "id": idx,
            "type": boat_type,
            "rect": boat_rect,
            "mode": MODE_COLLECT,
            "pending_mode": MODE_COLLECT,
            "refuel_lock": (idx != 1),
            "state": STATE_COLLECTING,
            "status": "Initializing",
            "speed": BOAT_SPEED_BY_TYPE.get(boat_type, BOAT_SPEED),
            "fuel": speedboat_max_fuel if boat_type == "Speedboat" else MAX_FUEL_SECONDS,
            "refuel_left": 0.0,
            "refuel_total": max(MIN_REFUEL_SECONDS, BOAT_REFUEL_SECONDS_BY_TYPE.get(boat_type, REFUEL_SECONDS)),
            "capacity": BOAT_CAPACITY_BY_TYPE.get(boat_type, 20),
            "max_fuel": speedboat_max_fuel if boat_type == "Speedboat" else MAX_FUEL_SECONDS,
            "crew_min": crew_min,
            "crew_max": crew_max,
            "crew_assigned": 0,
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
            "dock_guide": boat_dock_guides.get(boat_type),
            "visual_size": boat_sprites.get(boat_type).get_size() if boat_sprites.get(boat_type) is not None else (bw, bh),
        })

    def add_speedboat() -> bool:
        nonlocal money, boats
        if money + 1e-6 < SPEEDBOAT_PURCHASE_COST:
            return False

        next_id = (max((int(b.get("id", 0)) for b in boats), default=0) + 1)
        bw, bh = BOAT_SIZE_BY_TYPE.get("Speedboat", BOAT_SIZE)
        spawn_r = 130 + (next_id % 3) * 26
        spawn_theta = (next_id * 0.95) % (2.0 * math.pi)
        boat_rect = pygame.Rect(0, 0, bw, bh)
        boat_rect.center = (
            int(BASE_RECT.centerx + math.cos(spawn_theta) * spawn_r),
            int(BASE_RECT.centery + math.sin(spawn_theta) * spawn_r),
        )
        boat_rect.clamp_ip(WORLD_RECT)

        boats.append({
            "id": next_id,
            "type": "Speedboat",
            "rect": boat_rect,
            "mode": MODE_COLLECT,
            "pending_mode": MODE_COLLECT,
            "refuel_lock": False,
            "state": STATE_COLLECTING,
            "status": "Collecting",
            "speed": BOAT_SPEED_BY_TYPE.get("Speedboat", BOAT_SPEED),
            "fuel": speedboat_max_fuel,
            "max_fuel": speedboat_max_fuel,
            "refuel_left": 0.0,
            "refuel_total": max(MIN_REFUEL_SECONDS, BOAT_REFUEL_SECONDS_BY_TYPE.get("Speedboat", REFUEL_SECONDS)),
            "capacity": BOAT_CAPACITY_BY_TYPE.get("Speedboat", 20),
            "crew_min": 0,
            "crew_max": 0,
            "crew_assigned": 0,
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
            "dock_guide": boat_dock_guides.get("Speedboat"),
            "visual_size": boat_sprites.get("Speedboat").get_size() if boat_sprites.get("Speedboat") is not None else (bw, bh),
        })
        money -= SPEEDBOAT_PURCHASE_COST
        add_log(f"Boat {next_id} purchased")
        add_transaction(f"Bought Boat {next_id} -${SPEEDBOAT_PURCHASE_COST:.1f}")
        return True

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

    def add_notification(msg: str, ttl: float = 3.8) -> None:
        notifications.insert(0, {"text": msg, "ttl": max(1.2, ttl)})
        if len(notifications) > 6:
            del notifications[6:]

    def random_transport_route() -> tuple[tuple[float, float], tuple[int, int], tuple[int, int]]:
        dirs = [
            (-1, -1), (0, -1), (1, -1),
            (-1, 0),            (1, 0),
            (-1, 1),  (0, 1),   (1, 1),
        ]
        vx, vy = random.choice(dirs)
        norm = math.hypot(vx, vy)
        ux = vx / max(1e-6, norm)
        uy = vy / max(1e-6, norm)

        radius = int(max(WORLD_WIDTH, WORLD_HEIGHT) * 0.75) + 520
        entry_x = int(BASE_RECT.centerx + ux * radius)
        entry_y = int(BASE_RECT.centery + uy * radius)
        exit_x = int(BASE_RECT.centerx - ux * radius)
        exit_y = int(BASE_RECT.centery - uy * radius)

        return (ux, uy), (entry_x, entry_y), (exit_x, exit_y)

    running = True
    while running:
        frame_dt = clock.tick(FPS) / 1000.0

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_F2:
                show_dock_debug = not show_dock_debug
                add_log(f"Dock Debug {'ON' if show_dock_debug else 'OFF'}")
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if education_modal is not None:
                    for action, rect in education_button_rects.items():
                        if not rect.collidepoint(event.pos):
                            continue

                        if action == "done":
                            education_modal = None
                            education_button_rects = {}
                            add_log("Education prompt closed")
                            break

                        if action == "submit" and str(education_modal.get("kind", "")) == "quiz":
                            questions = education_modal.get("questions", [])
                            selected = education_modal.get("selected", [])
                            if isinstance(questions, list) and isinstance(selected, list):
                                score_count = 0
                                for qi, q in enumerate(questions):
                                    if not isinstance(q, dict):
                                        continue
                                    correct = str(q.get("correct", "")).upper()[:1]
                                    guess = selected[qi] if qi < len(selected) else None
                                    if guess == correct:
                                        score_count += 1
                                education_modal["submitted"] = True
                                education_modal["score"] = score_count
                            break

                        if action.startswith("q") and ":" in action and str(education_modal.get("kind", "")) == "quiz":
                            prefix, letter = action.split(":", 1)
                            try:
                                q_idx = int(prefix[1:])
                            except ValueError:
                                continue
                            selected = education_modal.get("selected", [])
                            submitted = bool(education_modal.get("submitted", False))
                            if isinstance(selected, list) and not submitted and 0 <= q_idx < len(selected):
                                selected[q_idx] = letter
                                education_modal["selected"] = selected
                            break
                    continue

                if event.pos[0] < SIDEBAR_WIDTH:
                    for button_key, rect in mode_button_rects.items():
                        if not rect.collidepoint(event.pos):
                            continue

                        if button_key == "barge:selltrash":
                            barge_sell_requested = True
                            add_log("Tugboat transport sell requested")
                            add_transaction("Sell request queued")
                            break

                        if button_key == "fleet:buyboat":
                            if add_speedboat():
                                pass
                            else:
                                add_log("Not enough money to buy a boat")
                            break

                        if button_key == "barge:buyfuel":
                            barge_buy_fuel_requested = True
                            add_log("Tugboat transport fuel buy requested")
                            add_transaction("Fuel purchase request queued")
                            break

                        try:
                            boat_id_str, action = button_key.split(":", 1)
                            boat_id = int(boat_id_str)
                        except ValueError:
                            continue

                        boat = next((b for b in boats if int(b["id"]) == boat_id), None)
                        if boat is None:
                            continue

                        if action == "sell" and str(boat.get("type", "")) != "Tugboat":
                            add_log(f"Boat {boat_id}: sell mode is transfer-boat only")
                            break

                        requested_mode = MODE_COLLECT if action == "collect" else (MODE_SELL if action == "sell" else MODE_STOP)
                        boat["pending_mode"] = requested_mode
                        boat["refuel_lock"] = True
                        boat["mode"] = requested_mode
                        boat["sell_phase"] = "idle"
                        boat["dock_slot"] = None
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

        if education_task is not None and education_task.done():
            try:
                education_modal = education_task.result()
                if education_modal:
                    if str(education_modal.get("kind", "")) == "fact":
                        last_education_fact = str(education_modal.get("text", "")).strip()
                    fb_fact = str(education_modal.get("_fallback_fact", "")).strip()
                    fb_quiz = str(education_modal.get("_fallback_quiz_key", "")).strip()
                    fb_tip = str(education_modal.get("_fallback_tip", "")).strip()
                    if fb_fact:
                        last_fallback_fact = fb_fact
                    if fb_quiz:
                        last_fallback_quiz_key = fb_quiz
                    if fb_tip:
                        last_fallback_tip = fb_tip
                    if str(education_modal.get("kind", "")) == "tip":
                        last_education_tip = str(education_modal.get("text", "")).strip()
                    add_log("Education prompt opened")
            except Exception:
                education_modal = {
                    "kind": "fact",
                    "title": "Ocean Fact",
                    "text": "Small cleanup actions add up and protect marine habitats over time.",
                }
            education_task = None

        if education_modal is None and education_task is None:
            education_timer += frame_dt
            if education_timer >= EDUCATION_PROMPT_INTERVAL_SECONDS:
                education_timer = 0.0
                education_task = asyncio.create_task(
                    fetch_random_education_prompt(
                        last_education_fact,
                        last_fallback_fact,
                        last_fallback_quiz_key,
                        last_education_tip,
                        last_fallback_tip,
                    )
                )
                add_log("Fetching ocean fact/quiz...")

        dt = 0.0 if education_modal is not None else frame_dt
        elapsed_seconds += dt

        donation_timer -= frame_dt
        if donation_timer <= 0.0:
            donor = random.choice(donor_names)
            donation_amount = random.randint(DONATION_MIN_AMOUNT, DONATION_MAX_AMOUNT)
            money += donation_amount
            fame = min(100.0, fame + random.uniform(0.15, 0.55))
            add_transaction(f"{donor} donation +${donation_amount}")
            add_notification(f"Donation: {donor} +${donation_amount}", ttl=4.5)
            donation_timer = random.uniform(DONATION_MIN_INTERVAL, DONATION_MAX_INTERVAL)

        # update notification lifetimes
        alive_notices: list[dict[str, object]] = []
        for n in notifications:
            ttl = float(n.get("ttl", 0.0)) - frame_dt
            if ttl > 0.0:
                n["ttl"] = ttl
                alive_notices.append(n)
        notifications[:] = alive_notices

        if barge_trip_phase == "idle" and (barge_sell_requested or barge_buy_fuel_requested):
            mission = "sell" if barge_sell_requested else "buy_fuel"
            barge_sell_requested = False
            barge_buy_fuel_requested = False

            if mission == "sell" and recycling_inventory <= 0:
                add_log("No barge trash to sell")
            else:
                route_vec, entry_point, exit_point = random_transport_route()
                transport_rect = heavy_transport["rect"]
                assert isinstance(transport_rect, pygame.Rect)
                transport_rect.center = entry_point
                heavy_transport["entry_vec"] = route_vec
                heavy_transport["exit_target"] = exit_point
                heavy_transport["phase"] = "inbound"
                heavy_transport["active"] = True
                heavy_transport["visible"] = True
                heavy_transport["timer"] = 0.0
                heavy_transport["mission"] = mission
                heavy_transport["facing_angle"] = math.degrees(math.atan2(-route_vec[1], -route_vec[0]))
                barge_trip_phase = "inbound"
                if mission == "sell":
                    add_log("Tugboat inbound for barge pickup")
                    add_transaction("Tugboat dispatch")
                else:
                    add_log("Tugboat inbound to buy fuel")
                    add_transaction("Tugboat fuel dispatch")

        for item in trash_items:
            item.update(dt)
        update_clear_clouds(clear_clouds, dt)

        returning_count = 0
        fleet_boats: list[dict[str, object]] = []
        dock_spots = get_barge_dock_spots(mothership_sprite)

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
            boat_max_fuel = float(boat.get("max_fuel", MAX_FUEL_SECONDS))
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
            dock_guide = boat.get("dock_guide") if isinstance(boat.get("dock_guide"), dict) else None
            visual_size = boat.get("visual_size") if isinstance(boat.get("visual_size"), tuple) else None
            docked = False

            move_dx = 0.0
            move_dy = 0.0
            boat_status = "Idle"
            newly_collected = 0
            gained_score = 0
            gained_sale_value = 0.0

            has_operating_crew = True

            if refuel_lock_active:
                boat_visible = True
                sell_phase = "idle"
                slot = get_or_assign_dock_slot(boat, boats, dock_spots)
                mode_label = "Return" if pending_mode == MODE_STOP else pending_mode.title()

                if slot is None:
                    at_base, move_dx, move_dy = move_boat_toward_point_speed(boat_rect, *get_nearest_dock_queue_point(boat_rect, dock_spots), dt, boat_speed)
                    boat_status = f"Command {mode_label}: waiting dock slot"
                else:
                    spot = dock_spots[slot]
                    at_base, move_dx, move_dy = move_boat_toward_dock_spot(boat_rect, spot, dt, boat_speed, boat_type, dock_guide, visual_size)
                    if at_base:
                        tx, ty, dock_angle = resolve_dock_target_for_boat(boat_rect, spot, boat_type, dock_guide, visual_size)
                        boat_rect.center = (tx, ty)
                        docked = True
                        facing_angle = dock_angle

                if not at_base:
                    if slot is not None:
                        boat_status = f"Command {mode_label}: docking"
                else:
                    dropped_off = trash_stored
                    if dropped_off > 0:
                        trash_collected += dropped_off
                        trash_stored = 0
                        recycling_inventory += dropped_off
                        recycling_stock_value += cargo_sale_value
                        cargo_sale_value = 0.0
                        add_transaction(f"Boat {boat_id} stocked +{dropped_off} units")

                    if fuel_seconds < (boat_max_fuel - 1e-3):
                        if boat_state != STATE_REFUELING and refuel_seconds_left <= 0.0:
                            boat_state = STATE_REFUELING
                            refuel_seconds_left = boat_refuel_seconds
                            add_log(f"Boat {boat_id} docked, refueling before command")

                        boat_status = f"Refueling before {mode_label} ({max(0.0, refuel_seconds_left):.1f}s)"
                        refuel_seconds_left -= dt
                        if refuel_seconds_left <= 0.0:
                            required_units = max(0.0, (boat_max_fuel - fuel_seconds) * BARGE_FUEL_UNITS_PER_BOAT_FUEL_SEC)
                            if barge_fuel_storage + 1e-6 >= required_units:
                                barge_fuel_storage = max(0.0, barge_fuel_storage - required_units)
                                fuel_seconds = boat_max_fuel
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
                        boat["dock_slot"] = None
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
                            boat["dock_slot"] = None
                            boat_status = "Returning To Base (cargo full)"

                elif boat_state == STATE_RETURNING:
                    returning_count += 1
                    boat_status = "Returning To Base"
                    slot = get_or_assign_dock_slot(boat, boats, dock_spots)
                    if slot is None:
                        at_base, move_dx, move_dy = move_boat_toward_point_speed(boat_rect, *get_nearest_dock_queue_point(boat_rect, dock_spots), dt, boat_speed)
                        boat_status = "Waiting dock slot"
                    else:
                        spot = dock_spots[slot]
                        at_base, move_dx, move_dy = move_boat_toward_dock_spot(boat_rect, spot, dt, boat_speed, boat_type, dock_guide, visual_size)
                        if at_base:
                            tx, ty, dock_angle = resolve_dock_target_for_boat(boat_rect, spot, boat_type, dock_guide, visual_size)
                            boat_rect.center = (tx, ty)
                            docked = True
                            facing_angle = dock_angle
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
                        required_units = max(0.0, (boat_max_fuel - fuel_seconds) * BARGE_FUEL_UNITS_PER_BOAT_FUEL_SEC)
                        if barge_fuel_storage + 1e-6 >= required_units:
                            barge_fuel_storage = max(0.0, barge_fuel_storage - required_units)
                            fuel_seconds = boat_max_fuel
                            refuel_seconds_left = 0.0
                            boat_state = STATE_COLLECTING
                        else:
                            boat_status = "Waiting barge fuel"
                            refuel_seconds_left = 0.0

            elif boat_mode == MODE_SELL and boat_type != "Tugboat":
                boat_mode = MODE_COLLECT
                boat_status = "Sell reserved for Tugboat"

            elif boat_mode == MODE_STOP:
                boat_visible = True
                sell_phase = "idle"
                slot = get_or_assign_dock_slot(boat, boats, dock_spots)
                if slot is None:
                    at_base, move_dx, move_dy = move_boat_toward_point_speed(boat_rect, *get_nearest_dock_queue_point(boat_rect, dock_spots), dt, boat_speed)
                    boat_status = "Waiting dock slot"
                else:
                    spot = dock_spots[slot]
                    at_base, move_dx, move_dy = move_boat_toward_dock_spot(boat_rect, spot, dt, boat_speed, boat_type, dock_guide, visual_size)
                    if at_base:
                        tx, ty, dock_angle = resolve_dock_target_for_boat(boat_rect, spot, boat_type, dock_guide, visual_size)
                        boat_rect.center = (tx, ty)
                        docked = True
                        facing_angle = dock_angle

                        dropped_off = trash_stored
                        if dropped_off > 0:
                            trash_collected += dropped_off
                            trash_stored = 0
                            recycling_inventory += dropped_off
                            recycling_stock_value += cargo_sale_value
                            cargo_sale_value = 0.0
                            add_transaction(f"Boat {boat_id} stocked +{dropped_off} units")
                    boat_status = "Stopped at barge" if at_base else "Returning to dock"

            else:  # MODE_SELL
                boat_state = STATE_COLLECTING
                refuel_seconds_left = 0.0

                if sell_phase == "idle":
                    slot = get_or_assign_dock_slot(boat, boats, dock_spots)
                    if slot is None:
                        at_base, move_dx, move_dy = move_boat_toward_point_speed(boat_rect, *get_nearest_dock_queue_point(boat_rect, dock_spots), dt, boat_speed)
                        boat_status = "Sell mode: waiting dock slot"
                    else:
                        spot = dock_spots[slot]
                        at_base, move_dx, move_dy = move_boat_toward_dock_spot(boat_rect, spot, dt, boat_speed, boat_type, dock_guide, visual_size)
                        if at_base:
                            docked = True
                            tx, ty, dock_angle = resolve_dock_target_for_boat(boat_rect, spot, boat_type, dock_guide, visual_size)
                            boat_rect.center = (tx, ty)
                            facing_angle = dock_angle
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
                    slot = get_or_assign_dock_slot(boat, boats, dock_spots)
                    if slot is None:
                        at_base, move_dx, move_dy = move_boat_toward_point_speed(boat_rect, *get_nearest_dock_queue_point(boat_rect, dock_spots), dt, boat_speed)
                        boat_status = "Returning from sale (queue)"
                    else:
                        spot = dock_spots[slot]
                        at_base, move_dx, move_dy = move_boat_toward_dock_spot(boat_rect, spot, dt, boat_speed, boat_type, dock_guide, visual_size)
                        if at_base:
                            docked = True
                            tx, ty, dock_angle = resolve_dock_target_for_boat(boat_rect, spot, boat_type, dock_guide, visual_size)
                            boat_rect.center = (tx, ty)
                            facing_angle = dock_angle
                    boat_visible = True
                    if at_base:
                        if pending_sale_revenue > 0.0 and pending_sale_units > 0:
                            money += pending_sale_revenue
                            add_transaction(f"Boat {boat_id} sale +${pending_sale_revenue:.1f} ({pending_sale_units} units)")
                            pending_sale_revenue = 0.0
                            pending_sale_units = 0

                        if boat_type == "Tugboat":
                            fuel_room = max(0.0, BARGE_FUEL_CAPACITY - barge_fuel_storage)
                            buy_units = min(HEAVY_SELL_FUEL_REBUY_UNITS, fuel_room, money / max(1e-6, BARGE_FUEL_BUY_PRICE))
                            if buy_units > 0.1:
                                buy_cost = buy_units * BARGE_FUEL_BUY_PRICE
                                money -= buy_cost
                                barge_fuel_storage = min(BARGE_FUEL_CAPACITY, barge_fuel_storage + buy_units)
                                add_transaction(f"Tugboat fuel load +{int(buy_units)} (cost ${buy_cost:.1f})")

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

            keep_boat_out_of_barge(boat_rect)

            if abs(move_dx) > 1e-4 or abs(move_dy) > 1e-4:
                facing_angle = math.degrees(math.atan2(move_dy, move_dx))
                maybe_spawn_wave(wave_particles, boat_rect, move_dx, move_dy, dt)

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
            boat["dock_slot"] = boat.get("dock_slot") if isinstance(boat.get("dock_slot"), int) else None
            boat["docked"] = docked

            fleet_boats.append({
                "id": boat_id,
                "type": boat_type,
                "mode": boat_mode,
                "status": boat_status,
                "state": boat_state,
                "fuel_seconds": fuel_seconds,
                "max_fuel": boat_max_fuel,
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

        # Tugboat transport sell-trip state machine.
        transport_move_dx = 0.0
        transport_move_dy = 0.0

        if heavy_transport["active"]:
            tr = heavy_transport["rect"]
            assert isinstance(tr, pygame.Rect)
            phase = str(heavy_transport.get("phase", "idle"))

            if phase == "inbound":
                reached, transport_move_dx, transport_move_dy = move_rect_center_toward(
                    tr, BASE_RECT.centerx, BASE_RECT.centery, dt, HEAVY_TRANSPORT_SPEED, clamp_world=False
                )
                if abs(transport_move_dx) > 1e-4 or abs(transport_move_dy) > 1e-4:
                    heavy_transport["facing_angle"] = math.degrees(math.atan2(transport_move_dy, transport_move_dx))
                if reached:
                    tr.center = BASE_RECT.center
                    mission = str(heavy_transport.get("mission", "sell"))

                    if mission == "sell":
                        sold_units = recycling_inventory
                        base_value = recycling_stock_value if recycling_stock_value > 0 else (sold_units * PLASTIC_SELL_PRICE)
                        guaranteed_floor = sold_units * BARGE_MIN_SELL_PRICE_PER_UNIT
                        sale_multiplier = 1.0 + (fame / 200.0)
                        sold_value = max(base_value, guaranteed_floor) * sale_multiplier

                        if sold_units > 0:
                            money += sold_value
                            add_transaction(f"Tugboat loaded {sold_units} trash (+${sold_value:.1f})")

                        recycling_inventory = 0
                        recycling_stock_value = 0.0

                        fuel_room = max(0.0, BARGE_FUEL_CAPACITY - barge_fuel_storage)
                        restock_budget = sold_value * BARGE_RESTOCK_BUDGET_RATIO
                        buy_units = min(BARGE_FUEL_RESTOCK_UNITS, fuel_room, restock_budget / max(1e-6, BARGE_FUEL_BUY_PRICE))
                        if buy_units > 0.1:
                            buy_cost = buy_units * BARGE_FUEL_BUY_PRICE
                            money -= buy_cost
                            barge_fuel_storage = min(BARGE_FUEL_CAPACITY, barge_fuel_storage + buy_units)
                            add_transaction(f"Barge fuel restock +{int(buy_units)} (cost ${buy_cost:.1f})")
                    else:
                        fuel_room = max(0.0, BARGE_FUEL_CAPACITY - barge_fuel_storage)
                        buy_units = min(TRANSPORTER_FUEL_BUY_UNITS, fuel_room)
                        buy_cost = buy_units * BARGE_FUEL_BUY_PRICE
                        affordable_units = min(buy_units, money / max(1e-6, BARGE_FUEL_BUY_PRICE))
                        if affordable_units > 0.1:
                            spend = affordable_units * BARGE_FUEL_BUY_PRICE
                            money -= spend
                            barge_fuel_storage = min(BARGE_FUEL_CAPACITY, barge_fuel_storage + affordable_units)
                            add_transaction(f"Fuel delivery +{int(affordable_units)} (cost ${spend:.1f})")
                        else:
                            add_transaction("Fuel delivery skipped (insufficient funds)")

                    heavy_transport["phase"] = "loading"
                    heavy_transport["timer"] = HEAVY_TRANSPORT_DOCK_TIME
                    barge_trip_phase = "loading"
                    add_log("Tugboat loading complete")

            elif phase == "loading":
                heavy_transport["timer"] = max(0.0, float(heavy_transport.get("timer", 0.0)) - dt)
                if heavy_transport["timer"] <= 0.0:
                    heavy_transport["phase"] = "outbound"
                    barge_trip_phase = "outbound"
                    add_log("Tugboat outbound to market")

            elif phase == "outbound":
                exit_x, exit_y = heavy_transport.get("exit_target", (WORLD_WIDTH + 220, WORLD_HEIGHT // 2))
                reached, transport_move_dx, transport_move_dy = move_rect_center_toward(
                    tr, int(exit_x), int(exit_y), dt, HEAVY_TRANSPORT_SPEED, clamp_world=False
                )
                if abs(transport_move_dx) > 1e-4 or abs(transport_move_dy) > 1e-4:
                    heavy_transport["facing_angle"] = math.degrees(math.atan2(transport_move_dy, transport_move_dx))
                if reached:
                    heavy_transport["phase"] = "idle"
                    heavy_transport["active"] = False
                    heavy_transport["visible"] = False
                    barge_trip_phase = "idle"
                    add_log("Tugboat completed sale route")
                    add_transaction("Tugboat cycle complete")

        else:
            barge_trip_phase = "idle"
        # economy + derived stats
        assigned_total = 0
        manpower_cost = (manpower_cost_per_min / 60.0) * dt
        fuel_cost = ((fuel_cost_per_min + len(boats) * 1.1) / 60.0) * dt
        general_cost = (general_cost_per_min / 60.0) * dt
        frame_cost = manpower_cost + fuel_cost + general_cost
        money -= frame_cost

        pending_cost_total += frame_cost
        cost_transaction_timer += dt
        if cost_transaction_timer >= cost_transaction_interval:
            add_transaction(
                f"Ops costs -${pending_cost_total:.1f} "
                f"(crew -${(manpower_cost_per_min / 60.0 * cost_transaction_timer):.1f}, "
                f"fuel -${((fuel_cost_per_min + len(boats) * 1.1) / 60.0 * cost_transaction_timer):.1f}, "
                f"general -${(general_cost_per_min / 60.0 * cost_transaction_timer):.1f})"
            )
            cost_transaction_timer = 0.0
            pending_cost_total = 0.0

        collection_rate = (trash_collected / max(1.0, elapsed_seconds)) * 60.0
        if abs(transport_move_dx) > 1e-4 or abs(transport_move_dy) > 1e-4:
            tr = heavy_transport["rect"]
            assert isinstance(tr, pygame.Rect)
            maybe_spawn_wave(wave_particles, tr, transport_move_dx, transport_move_dy, dt, centered=True)

        update_wave(wave_particles, dt)

        if ocean_tile is not None:
            draw_tiled_ocean(screen, ocean_tile, camera_x, camera_y)
        else:
            map_surface = screen.subsurface(VIEWPORT_RECT)
            draw_fallback_ocean_gradient(map_surface)

        for item in trash_items:
            item.draw(screen, camera_x, camera_y)

        for p in wave_particles:
            p.draw(screen, camera_x, camera_y)

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

        if bool(heavy_transport.get("visible", False)):
            tr = heavy_transport["rect"]
            assert isinstance(tr, pygame.Rect)
            draw_boat(
                screen,
                tr,
                camera_x,
                camera_y,
                transport_sprite,
                float(heavy_transport.get("facing_angle", 0.0)),
                "Tugboat",
            )

        draw_base_ship(screen, base_font, camera_x, camera_y, mothership_sprite, 0.0)
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
            label = f"{display_boat_type(str(boat.get('type', 'Boat')))} {boat.get('id', '?')}"
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
        crew_available = 0

        if (
            (not win_active)
            and len(trash_items) == 0
            and total_trash_stored <= 0
            and recycling_inventory <= 0
            and (not bool(heavy_transport.get("active", False)))
        ):
            win_active = True
            add_log("All trash cleared - mission complete")
            add_transaction("Victory: Ocean cleaned")

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
            barge_trip_phase,
            SPEEDBOAT_PURCHASE_COST,
            money + 1e-6 >= SPEEDBOAT_PURCHASE_COST,
        )
        menu_scroll = max(0.0, min(menu_scroll, menu_max_scroll))

        if education_modal is not None:
            education_button_rects = draw_education_modal(screen, body_font, education_modal)
        else:
            education_button_rects = {}

        draw_notifications(screen, body_font, notifications)

        if intro_fade_alpha > 0.0:
            fade_overlay = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.SRCALPHA)
            fade_overlay.fill((0, 0, 0, int(max(0.0, min(255.0, intro_fade_alpha)))))
            screen.blit(fade_overlay, (0, 0))
            intro_fade_alpha = max(0.0, intro_fade_alpha - 220.0 * dt)

        if win_active:
            win_fade_alpha = min(255.0, win_fade_alpha + 145.0 * frame_dt)
            win_overlay = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.SRCALPHA)
            win_overlay.fill((0, 0, 0, int(win_fade_alpha)))
            screen.blit(win_overlay, (0, 0))
            if win_fade_alpha >= 185.0:
                win_text = body_font.render("You Won!", False, (255, 255, 255))
                screen.blit(win_text, (WINDOW_WIDTH // 2 - win_text.get_width() // 2, WINDOW_HEIGHT // 2 - win_text.get_height() // 2))

        apply_pixelation(screen, VIEWPORT_RECT)
        pygame.display.flip()
        await asyncio.sleep(0)

    pygame.quit()


async def main() -> None:
    await run_game()


if __name__ == "__main__":
    try:
        if sys.platform == "emscripten":
            asyncio.ensure_future(main())
        else:
            asyncio.run(main())
    except KeyboardInterrupt:
        pygame.quit()
        sys.exit(0)
