"""Pixel Boat Cleanup V0.

- Boat automatically moves toward trash
- Boat has a 10-second fuel tank
- When fuel runs out, it returns to base ship to refuel, then resumes cleanup
- Scrollable world with click-drag camera
- Left sidebar HUD (does not cover the map)
- Ocean uses tiled asset from assets/ocean.jpeg
- Boat uses assets/smallboat.png with 8-direction facing
- Wake particles trail behind the moving boat
"""

from __future__ import annotations

import asyncio
import math
import random
import sys
from pathlib import Path

import pygame


# Window layout
WINDOW_WIDTH = 1080
WINDOW_HEIGHT = 620
SIDEBAR_WIDTH = 290
PIXELATE_SCALE = 2
VIEWPORT_RECT = pygame.Rect(SIDEBAR_WIDTH, 0, WINDOW_WIDTH - SIDEBAR_WIDTH, WINDOW_HEIGHT)

# World settings
FPS = 60
WORLD_WIDTH = 2600
WORLD_HEIGHT = 1800
WORLD_RECT = pygame.Rect(0, 0, WORLD_WIDTH, WORLD_HEIGHT)

# Gameplay settings
BOAT_SIZE = (38, 24)
BOAT_SPEED = 210.0
STARTING_TRASH_COUNT = 120
MAX_FUEL_SECONDS = 10.0
REFUEL_SECONDS = 2.0

# Big base ship in world corner
BASE_RECT = pygame.Rect(32, 32, 220, 130)

# Assets
ASSETS_DIR = Path(__file__).resolve().parent / "assets"
OCEAN_TILE_PATH = ASSETS_DIR / "ocean.jpeg"
OCEAN_TILE_SCALE = 0.4
BOAT_SPRITE_PATH = ASSETS_DIR / "smallboat.png"
BOAT_SPRITE_SCALE = 1.0
BOAT_SPRITE_ANGLE_OFFSET = 90.0  # sprite defaults to facing up; offset aligns it to movement
MOTHERSHIP_SPRITE_PATH = ASSETS_DIR / "mothership.png"
MOTHERSHIP_SPRITE_SCALE = 0.45

# Colors
BOAT_FILL = (245, 192, 50)
BOAT_OUTLINE = (74, 54, 22)
BASE_FILL = (62, 79, 110)
BASE_DECK = (95, 120, 156)
BASE_OUTLINE = (23, 35, 52)
TEXT_COLOR = (248, 236, 210)
MUTED_TEXT = (230, 212, 182)
SIDEBAR_BG = (168, 128, 82)
SIDEBAR_BORDER = (124, 91, 56)
FUEL_BG = (132, 101, 67)
FUEL_FILL = (102, 221, 132)
FUEL_LOW = (241, 118, 104)
FALLBACK_OCEAN_TOP = (25, 110, 184)
FALLBACK_OCEAN_BOTTOM = (16, 69, 132)
TRASH_DIR = ASSETS_DIR / "trash"
TRASH_SPRITE_SCALE = 0.09
FALLBACK_TRASH_COLOR = (210, 228, 236)
STATE_COLLECTING = "collecting"
STATE_RETURNING = "returning"
STATE_REFUELING = "refueling"


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
    if not BOAT_SPRITE_PATH.exists():
        return None
    try:
        sprite = pygame.image.load(str(BOAT_SPRITE_PATH)).convert_alpha()
        scaled_w = max(8, int(sprite.get_width() * BOAT_SPRITE_SCALE))
        scaled_h = max(8, int(sprite.get_height() * BOAT_SPRITE_SCALE))
        return pygame.transform.scale(sprite, (scaled_w, scaled_h))
    except pygame.error:
        return None


    sprites: list[pygame.Surface] = []
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

        while True:
            self.x = random.randint(24, WORLD_RECT.width - 24)
            self.y = random.randint(24, WORLD_RECT.height - 24)
            item_rect = pygame.Rect(self.x - self.width // 2, self.y - self.height // 2, self.width, self.height)
            if not item_rect.colliderect(BASE_RECT.inflate(30, 30)):
                break

    def draw(self, surface: pygame.Surface, camera_x: float, camera_y: float) -> None:
        sx, sy = world_to_screen(self.x, self.y, camera_x, camera_y)
        if self.sprite is not None:
            rect = self.sprite.get_rect(center=(sx, sy))
            surface.blit(self.sprite, rect)
        else:
            rect = pygame.Rect(sx - self.size // 2, sy - self.size // 2, self.size, self.size)
            pygame.draw.rect(surface, FALLBACK_TRASH_COLOR, rect, border_radius=2)

    def collides_with_boat(self, boat_rect: pygame.Rect) -> bool:
        item_rect = pygame.Rect(self.x - self.width // 2, self.y - self.height // 2, self.width, self.height)
        return boat_rect.colliderect(item_rect)
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
        radius = max(1, int(3 * ratio))
        alpha = int(180 * ratio)

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
) -> None:
    boat_screen = world_rect_to_screen(boat_rect, camera_x, camera_y)

    if boat_sprite is None:
        pygame.draw.rect(surface, BOAT_FILL, boat_screen, border_radius=6)
        pygame.draw.rect(surface, BOAT_OUTLINE, boat_screen, width=2, border_radius=6)
        prow = [
            (boat_screen.right, boat_screen.centery),
            (boat_screen.right + 10, boat_screen.centery - 6),
            (boat_screen.right + 10, boat_screen.centery + 6),
        ]
        pygame.draw.polygon(surface, BOAT_FILL, prow)
        pygame.draw.polygon(surface, BOAT_OUTLINE, prow, width=2)
        return

    snapped_angle = quantize_angle_to_8(facing_angle_degrees + BOAT_SPRITE_ANGLE_OFFSET)
    rotated = pygame.transform.rotate(boat_sprite, -snapped_angle)
    rot_rect = rotated.get_rect(center=boat_screen.center)
    surface.blit(rotated, rot_rect)


def apply_pixelation(surface: pygame.Surface) -> None:
    if PIXELATE_SCALE <= 1:
        return
    w, h = surface.get_size()
    low_w = max(1, w // PIXELATE_SCALE)
    low_h = max(1, h // PIXELATE_SCALE)
    low = pygame.transform.scale(surface, (low_w, low_h))
    pix = pygame.transform.scale(low, (w, h))
    surface.blit(pix, (0, 0))


def draw_sidebar(
    surface: pygame.Surface,
    body_font: pygame.font.Font,
    collected: int,
    remaining: int,
    score: int,
    boat_state: str,
    fuel_seconds: float,
    refuel_seconds_left: float,
    money: float,
    fame: float,
    crew_count: int,
    morale: float,
    ships_total: int,
    trash_stored: int,
    operating_cost_per_min: float,
    collection_rate: float,
    event_log: list[str],
    menu_scroll: float,
) -> float:
    panel = pygame.Rect(0, 0, SIDEBAR_WIDTH, WINDOW_HEIGHT)

    # Plain warm wood panel + subtle vertical tonal accents
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

    # Scrollable content area
    content_x = 12
    content_y = 12
    content_w = SIDEBAR_WIDTH - 24
    visible_h = WINDOW_HEIGHT - 24
    content = pygame.Surface((content_w, 980), pygame.SRCALPHA)

    card_colors = [(149, 111, 70), (141, 104, 64), (156, 118, 76), (137, 100, 61)]
    border = (103, 75, 45)

    if boat_state == STATE_COLLECTING:
        status = "Collecting"
    elif boat_state == STATE_RETURNING:
        status = "Returning To Base"
    else:
        status = f"Refueling ({max(0.0, refuel_seconds_left):.1f}s)"

    def draw_card(y: int, title: str, lines: list[str], idx: int) -> int:
        h = 36 + len(lines) * 20
        rect = pygame.Rect(0, y, content_w, h)
        pygame.draw.rect(content, card_colors[idx % len(card_colors)], rect)
        pygame.draw.rect(content, border, rect, width=2)

        title_surf = body_font.render(title, True, TEXT_COLOR)
        content.blit(title_surf, (10, y + 8))

        ly = y + 30
        for line in lines:
            surf = body_font.render(line, True, MUTED_TEXT)
            content.blit(surf, (12, ly))
            ly += 20
        return y + h + 10

    y = 0
    y = draw_card(y, "Overview", [
        f"Money: ${int(money)}",
        f"Fame: {fame:.1f}",
        f"Score: {score}",
        f"Net Cost/min: ${operating_cost_per_min:.1f}",
    ], 0)

    y = draw_card(y, "Cleanup", [
        f"Trash Collected: {collected}",
        f"Trash Stored: {trash_stored}",
        f"Trash Remaining: {remaining}",
        f"Rate/min: {collection_rate:.1f}",
    ], 1)

    y = draw_card(y, "Fleet", [
        f"Ships: {ships_total}",
        f"Status: {status}",
        f"Fuel: {max(0.0, fuel_seconds):.1f}s",
        "Use mouse drag on map to pan",
    ], 2)

    y = draw_card(y, "Crew", [
        f"Crew Count: {crew_count}",
        f"Morale: {morale:.1f}%",
        "Morale impacts efficiency (next)",
    ], 3)

    logs = event_log[:6] if event_log else ["No events yet"]
    y = draw_card(y, "Log", logs, 0)

    max_scroll = max(0, y - visible_h)
    clamped_scroll = max(0, min(int(menu_scroll), max_scroll))

    src = pygame.Rect(0, clamped_scroll, content_w, visible_h)
    surface.blit(content, (content_x, content_y), src)

    if max_scroll > 0:
        track = pygame.Rect(SIDEBAR_WIDTH - 7, content_y, 4, visible_h)
        pygame.draw.rect(surface, (120, 88, 54), track)
        thumb_h = max(22, int(visible_h * (visible_h / max(y, visible_h + 1))))
        thumb_y = content_y + int((visible_h - thumb_h) * (clamped_scroll / max(1, max_scroll)))
        thumb = pygame.Rect(track.x, thumb_y, track.width, thumb_h)
        pygame.draw.rect(surface, (198, 161, 114), thumb)

    return float(max_scroll)

def collect_on_contact(boat_rect: pygame.Rect, trash_items: list[TrashItem]) -> tuple[int, int]:
    kept_items: list[TrashItem] = []
    collected_count = 0
    score_gained = 0
    for item in trash_items:
        if item.collides_with_boat(boat_rect):
            collected_count += 1
            score_gained += item.score
        else:
            kept_items.append(item)
    trash_items[:] = kept_items
    return collected_count, score_gained


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


def move_boat_to_nearest_trash(boat_rect: pygame.Rect, trash_items: list[TrashItem], dt: float) -> tuple[float, float]:
    if not trash_items:
        return 0.0, 0.0
    bx, by = boat_rect.center
    nearest = min(trash_items, key=lambda item: (item.x - bx) ** 2 + (item.y - by) ** 2)
    _, move_dx, move_dy = move_boat_toward_point(boat_rect, nearest.x, nearest.y, dt)
    return move_dx, move_dy


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
    spawn_count = max(1, int(speed / 2.2))
    cx, cy = boat_rect.center
    direction_x = move_dx / max(speed, 1e-6)
    direction_y = move_dy / max(speed, 1e-6)

    # Trail starts behind the boat.
    base_x = cx - direction_x * (boat_rect.width * 0.5)
    base_y = cy - direction_y * (boat_rect.height * 0.5)

    for _ in range(min(spawn_count, 3)):
        jitter_x = random.uniform(-2.0, 2.0)
        jitter_y = random.uniform(-2.0, 2.0)
        vx = -direction_x * random.uniform(20.0, 50.0) + random.uniform(-8.0, 8.0)
        vy = -direction_y * random.uniform(20.0, 50.0) + random.uniform(-8.0, 8.0)
        life = random.uniform(0.35, 0.7)
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
    pygame.display.set_caption("Pixel Boat Cleanup V0")
    clock = pygame.time.Clock()

    body_font = pygame.font.SysFont("couriernew", 20)
    base_font = pygame.font.SysFont("couriernew", 20, bold=True)

    ocean_tile = load_ocean_tile()
    boat_sprite = load_boat_sprite()
    mothership_sprite = load_mothership_sprite()
    trash_sprites = load_trash_sprites()

    boat_rect = pygame.Rect(BASE_RECT.centerx + 20, BASE_RECT.centery + 6, BOAT_SIZE[0], BOAT_SIZE[1])
    trash_items = [TrashItem(random.choice(trash_sprites) if trash_sprites else None) for _ in range(STARTING_TRASH_COUNT)]
    wake_particles: list[WakeParticle] = []

    trash_collected = 0
    score = 0
    boat_state = STATE_COLLECTING
    fuel_seconds = MAX_FUEL_SECONDS
    refuel_seconds_left = 0.0

    # V1.9 management stats
    money = 1200.0
    fame = 8.0
    crew_count = 14
    morale = 74.0
    ships_total = 1
    trash_stored = 0
    operating_cost_per_min = 42.0
    collection_rate = 0.0
    elapsed_seconds = 0.0
    event_log: list[str] = ["[00:00] Operations online"]

    facing_angle = 0.0
    camera_x = 0.0
    camera_y = 0.0
    dragging = False
    last_mouse = (0, 0)

    menu_scroll = 0.0
    menu_max_scroll = 0.0

    def add_log(msg: str) -> None:
        nonlocal event_log, elapsed_seconds
        mm = int(elapsed_seconds // 60)
        ss = int(elapsed_seconds % 60)
        event_log.insert(0, f"[{mm:02d}:{ss:02d}] {msg}")
        if len(event_log) > 12:
            event_log = event_log[:12]

    running = True
    while running:
        dt = clock.tick(FPS) / 1000.0
        elapsed_seconds += dt

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                running = False
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and VIEWPORT_RECT.collidepoint(event.pos):
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

        move_dx = 0.0
        move_dy = 0.0
        newly_collected = 0
        gained_score = 0

        if boat_state == STATE_COLLECTING:
            move_dx, move_dy = move_boat_to_nearest_trash(boat_rect, trash_items, dt)
            fuel_seconds = max(0.0, fuel_seconds - dt)
            if fuel_seconds <= 0.0:
                boat_state = STATE_RETURNING
                add_log("Boat low fuel, returning to mothership")

            newly_collected, gained_score = collect_on_contact(boat_rect, trash_items)
            if newly_collected > 0:
                trash_collected += newly_collected
                trash_stored += newly_collected
                score += gained_score
                money += gained_score * 0.8
                fame = min(100.0, fame + newly_collected * 0.06)
                if trash_collected % 10 == 0:
                    add_log(f"Collected {trash_collected} total trash")

        elif boat_state == STATE_RETURNING:
            at_base, move_dx, move_dy = move_boat_toward_point(boat_rect, BASE_RECT.centerx, BASE_RECT.centery, dt)
            if at_base:
                boat_state = STATE_REFUELING
                refuel_seconds_left = REFUEL_SECONDS
                add_log("Docked at mothership, refueling")

        else:
            refuel_seconds_left -= dt
            if refuel_seconds_left <= 0.0:
                fuel_seconds = MAX_FUEL_SECONDS
                refuel_seconds_left = 0.0
                boat_state = STATE_COLLECTING
                add_log("Refuel complete, redeploying")

        # economy + derived stats
        money -= (operating_cost_per_min / 60.0) * dt
        collection_rate = (trash_collected / max(1.0, elapsed_seconds)) * 60.0
        morale = max(40.0, min(96.0, 68.0 + fame * 0.25 - (8.0 if boat_state == STATE_RETURNING else 0.0)))

        if abs(move_dx) > 1e-4 or abs(move_dy) > 1e-4:
            facing_angle = math.degrees(math.atan2(move_dy, move_dx))
            maybe_spawn_wake(wake_particles, boat_rect, move_dx, move_dy, dt)

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
        draw_boat(screen, boat_rect, camera_x, camera_y, boat_sprite, facing_angle)

        menu_max_scroll = draw_sidebar(
            screen,
            body_font,
            trash_collected,
            len(trash_items),
            score,
            boat_state,
            fuel_seconds,
            refuel_seconds_left,
            money,
            fame,
            crew_count,
            morale,
            ships_total,
            trash_stored,
            operating_cost_per_min,
            collection_rate,
            event_log,
            menu_scroll,
        )
        menu_scroll = max(0.0, min(menu_scroll, menu_max_scroll))

        apply_pixelation(screen)
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
