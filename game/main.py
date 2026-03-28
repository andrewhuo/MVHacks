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
PROJECT_ROOT = Path(__file__).resolve().parents[1]
OCEAN_TILE_PATH = PROJECT_ROOT / "assets" / "ocean.jpeg"
OCEAN_TILE_SCALE = 0.4
BOAT_SPRITE_PATH = PROJECT_ROOT / "assets" / "smallboat.png"
BOAT_SPRITE_SCALE = 1.0
BOAT_SPRITE_ANGLE_OFFSET = 0.0  # adjust if sprite's default facing is not rightward

# Colors
BOAT_FILL = (245, 192, 50)
BOAT_OUTLINE = (74, 54, 22)
BASE_FILL = (62, 79, 110)
BASE_DECK = (95, 120, 156)
BASE_OUTLINE = (23, 35, 52)
TEXT_COLOR = (238, 247, 255)
MUTED_TEXT = (192, 212, 233)
SIDEBAR_BG = (16, 27, 41)
SIDEBAR_BORDER = (38, 58, 82)
FUEL_BG = (42, 55, 75)
FUEL_FILL = (102, 221, 132)
FUEL_LOW = (241, 118, 104)
FALLBACK_OCEAN_TOP = (25, 110, 184)
FALLBACK_OCEAN_BOTTOM = (16, 69, 132)
TRASH_COLORS = [
    (230, 232, 238),
    (177, 201, 218),
    (206, 220, 230),
]

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
    def __init__(self) -> None:
        self.size = random.randint(7, 12)
        self.shape = random.choice(["circle", "square"])
        self.color = random.choice(TRASH_COLORS)
        self.score = random.choice([8, 10, 12, 15])

        while True:
            self.x = random.randint(24, WORLD_RECT.width - 24)
            self.y = random.randint(24, WORLD_RECT.height - 24)
            item_rect = pygame.Rect(self.x - self.size // 2, self.y - self.size // 2, self.size, self.size)
            if not item_rect.colliderect(BASE_RECT.inflate(30, 30)):
                break

    def draw(self, surface: pygame.Surface, camera_x: float, camera_y: float) -> None:
        sx, sy = world_to_screen(self.x, self.y, camera_x, camera_y)
        if self.shape == "circle":
            pygame.draw.circle(surface, self.color, (sx, sy), self.size // 2)
        else:
            rect = pygame.Rect(sx - self.size // 2, sy - self.size // 2, self.size, self.size)
            pygame.draw.rect(surface, self.color, rect, border_radius=2)

    def collides_with_boat(self, boat_rect: pygame.Rect) -> bool:
        item_rect = pygame.Rect(self.x - self.size // 2, self.y - self.size // 2, self.size, self.size)
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


def draw_base_ship(surface: pygame.Surface, base_font: pygame.font.Font, camera_x: float, camera_y: float) -> None:
    base_screen = world_rect_to_screen(BASE_RECT, camera_x, camera_y)
    pygame.draw.rect(surface, BASE_FILL, base_screen, border_radius=10)
    pygame.draw.rect(surface, BASE_OUTLINE, base_screen, width=3, border_radius=10)
    deck = base_screen.inflate(-34, -44)
    pygame.draw.rect(surface, BASE_DECK, deck, border_radius=8)
    pygame.draw.rect(surface, BASE_OUTLINE, deck, width=2, border_radius=8)
    label = base_font.render("BASE SHIP", True, TEXT_COLOR)
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


def draw_sidebar(
    surface: pygame.Surface,
    body_font: pygame.font.Font,
    collected: int,
    remaining: int,
    score: int,
    boat_state: str,
    fuel_seconds: float,
    refuel_seconds_left: float,
) -> None:
    panel = pygame.Rect(0, 0, SIDEBAR_WIDTH, WINDOW_HEIGHT)
    pygame.draw.rect(surface, SIDEBAR_BG, panel)
    pygame.draw.line(surface, SIDEBAR_BORDER, (SIDEBAR_WIDTH - 1, 0), (SIDEBAR_WIDTH - 1, WINDOW_HEIGHT), 2)

    if boat_state == STATE_COLLECTING:
        status = "Collecting"
    elif boat_state == STATE_RETURNING:
        status = "Returning To Base"
    else:
        status = f"Refueling ({max(0.0, refuel_seconds_left):.1f}s)"

    lines = [
        f"Boat AI: {status}",
        f"Trash Collected: {collected}",
        f"Trash Remaining: {remaining}",
        f"Score: {score}",
        "Camera: drag on map",
        "ESC: quit",
    ]

    y = 18
    for i, line in enumerate(lines):
        color = TEXT_COLOR if i < 4 else MUTED_TEXT
        label = body_font.render(line, True, color)
        surface.blit(label, (14, y))
        y += 26

    bar_outer = pygame.Rect(16, 190, SIDEBAR_WIDTH - 32, 16)
    pygame.draw.rect(surface, FUEL_BG, bar_outer, border_radius=7)
    fuel_ratio = max(0.0, min(1.0, fuel_seconds / MAX_FUEL_SECONDS))
    fill_width = max(0, int((bar_outer.width - 2) * fuel_ratio))
    bar_inner = pygame.Rect(bar_outer.x + 1, bar_outer.y + 1, fill_width, bar_outer.height - 2)
    fuel_color = FUEL_FILL if fuel_ratio > 0.25 else FUEL_LOW
    if bar_inner.width > 0:
        pygame.draw.rect(surface, fuel_color, bar_inner, border_radius=6)


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

    boat_rect = pygame.Rect(BASE_RECT.centerx + 20, BASE_RECT.centery + 6, BOAT_SIZE[0], BOAT_SIZE[1])
    trash_items = [TrashItem() for _ in range(STARTING_TRASH_COUNT)]
    wake_particles: list[WakeParticle] = []

    trash_collected = 0
    score = 0
    boat_state = STATE_COLLECTING
    fuel_seconds = MAX_FUEL_SECONDS
    refuel_seconds_left = 0.0

    facing_angle = 0.0

    camera_x = 0.0
    camera_y = 0.0
    dragging = False
    last_mouse = (0, 0)
    running = True

    while running:
        dt = clock.tick(FPS) / 1000.0

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

        move_dx = 0.0
        move_dy = 0.0

        if boat_state == STATE_COLLECTING:
            move_dx, move_dy = move_boat_to_nearest_trash(boat_rect, trash_items, dt)
            fuel_seconds = max(0.0, fuel_seconds - dt)
            if fuel_seconds <= 0.0:
                boat_state = STATE_RETURNING
            newly_collected, gained_score = collect_on_contact(boat_rect, trash_items)
            trash_collected += newly_collected
            score += gained_score
        elif boat_state == STATE_RETURNING:
            at_base, move_dx, move_dy = move_boat_toward_point(boat_rect, BASE_RECT.centerx, BASE_RECT.centery, dt)
            if at_base:
                boat_state = STATE_REFUELING
                refuel_seconds_left = REFUEL_SECONDS
        else:
            refuel_seconds_left -= dt
            if refuel_seconds_left <= 0.0:
                fuel_seconds = MAX_FUEL_SECONDS
                refuel_seconds_left = 0.0
                boat_state = STATE_COLLECTING

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

        draw_base_ship(screen, base_font, camera_x, camera_y)
        draw_boat(screen, boat_rect, camera_x, camera_y, boat_sprite, facing_angle)

        draw_sidebar(
            screen,
            body_font,
            trash_collected,
            len(trash_items),
            score,
            boat_state,
            fuel_seconds,
            refuel_seconds_left,
        )

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
