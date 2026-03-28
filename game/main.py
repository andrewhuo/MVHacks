"""Pixel Boat Cleanup V0.

Minimal Pygame prototype:
- Boat automatically moves toward trash
- Trash is collected automatically on boat contact
- ESC or close window to quit
"""

from __future__ import annotations

import math
import random
import sys

import pygame


# Window and world settings
WINDOW_WIDTH = 960
WINDOW_HEIGHT = 600
FPS = 60
OCEAN_RECT = pygame.Rect(0, 0, WINDOW_WIDTH, WINDOW_HEIGHT)

# Gameplay settings
BOAT_SIZE = (38, 24)
BOAT_SPEED = 210.0
STARTING_TRASH_COUNT = 35

# Colors
OCEAN_TOP = (25, 110, 184)
OCEAN_BOTTOM = (16, 69, 132)
WAVE_COLOR = (199, 229, 255)
BOAT_FILL = (245, 192, 50)
BOAT_OUTLINE = (74, 54, 22)
TEXT_COLOR = (238, 247, 255)
MUTED_TEXT = (192, 212, 233)
TRASH_COLORS = [
    (230, 232, 238),
    (177, 201, 218),
    (206, 220, 230),
]


def draw_vertical_gradient(surface: pygame.Surface, top: tuple[int, int, int], bottom: tuple[int, int, int]) -> None:
    """Draw a simple ocean gradient background."""
    height = surface.get_height()
    width = surface.get_width()
    for y in range(height):
        t = y / max(1, height - 1)
        color = (
            int(top[0] + (bottom[0] - top[0]) * t),
            int(top[1] + (bottom[1] - top[1]) * t),
            int(top[2] + (bottom[2] - top[2]) * t),
        )
        pygame.draw.line(surface, color, (0, y), (width, y))


class TrashItem:
    def __init__(self) -> None:
        self.x = random.randint(24, OCEAN_RECT.width - 24)
        self.y = random.randint(24, OCEAN_RECT.height - 24)
        self.size = random.randint(7, 12)
        self.shape = random.choice(["circle", "square"])
        self.color = random.choice(TRASH_COLORS)
        self.score = random.choice([8, 10, 12, 15])

    def draw(self, surface: pygame.Surface) -> None:
        if self.shape == "circle":
            pygame.draw.circle(surface, self.color, (self.x, self.y), self.size // 2)
        else:
            rect = pygame.Rect(self.x - self.size // 2, self.y - self.size // 2, self.size, self.size)
            pygame.draw.rect(surface, self.color, rect, border_radius=2)

    def collides_with_boat(self, boat_rect: pygame.Rect) -> bool:
        """Treat each trash item as a small square hitbox for contact pickup."""
        item_rect = pygame.Rect(self.x - self.size // 2, self.y - self.size // 2, self.size, self.size)
        return boat_rect.colliderect(item_rect)


def draw_waves(surface: pygame.Surface) -> None:
    """Overlay simple wave lines to make the ocean feel alive."""
    spacing = 44
    for y in range(20, WINDOW_HEIGHT, spacing):
        for x in range(0, WINDOW_WIDTH, 90):
            pygame.draw.arc(surface, WAVE_COLOR, (x, y, 34, 14), 0, math.pi, 1)


def draw_boat(surface: pygame.Surface, boat_rect: pygame.Rect) -> None:
    pygame.draw.rect(surface, BOAT_FILL, boat_rect, border_radius=6)
    pygame.draw.rect(surface, BOAT_OUTLINE, boat_rect, width=2, border_radius=6)

    prow = [
        (boat_rect.right, boat_rect.centery),
        (boat_rect.right + 10, boat_rect.centery - 6),
        (boat_rect.right + 10, boat_rect.centery + 6),
    ]
    pygame.draw.polygon(surface, BOAT_FILL, prow)
    pygame.draw.polygon(surface, BOAT_OUTLINE, prow, width=2)


def draw_hud(
    surface: pygame.Surface,
    title_font: pygame.font.Font,
    body_font: pygame.font.Font,
    collected: int,
    remaining: int,
    score: int,
) -> None:
    title = title_font.render("Pixel Boat Cleanup V0", True, TEXT_COLOR)
    surface.blit(title, (16, 12))

    hud_lines = [
        "Boat AI: ACTIVE",
        f"Trash Collected: {collected}",
        f"Trash Remaining: {remaining}",
        f"Score: {score}",
        "The boat automatically seeks nearest trash",
        "ESC = quit",
    ]

    y = 48
    for idx, line in enumerate(hud_lines):
        color = TEXT_COLOR if idx < 4 else MUTED_TEXT
        label = body_font.render(line, True, color)
        surface.blit(label, (16, y))
        y += 24


def collect_on_contact(boat_rect: pygame.Rect, trash_items: list[TrashItem]) -> tuple[int, int]:
    """Collect every trash item currently touching the boat.

    Returns:
        (number_collected, score_gained)
    """
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


def move_boat_to_nearest_trash(boat_rect: pygame.Rect, trash_items: list[TrashItem], dt: float) -> None:
    """Autopilot the boat toward the nearest trash item."""
    if not trash_items:
        return

    bx, by = boat_rect.center
    nearest = min(trash_items, key=lambda item: (item.x - bx) ** 2 + (item.y - by) ** 2)

    dx = nearest.x - bx
    dy = nearest.y - by
    distance = math.hypot(dx, dy)
    if distance <= 0.001:
        return

    step = BOAT_SPEED * dt
    if step >= distance:
        new_x, new_y = nearest.x, nearest.y
    else:
        new_x = bx + (dx / distance) * step
        new_y = by + (dy / distance) * step

    boat_rect.center = (int(new_x), int(new_y))
    boat_rect.clamp_ip(OCEAN_RECT)


def run_game() -> None:
    pygame.init()
    screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
    pygame.display.set_caption("Pixel Boat Cleanup V0")
    clock = pygame.time.Clock()

    title_font = pygame.font.SysFont("couriernew", 24, bold=True)
    body_font = pygame.font.SysFont("couriernew", 20)

    boat_rect = pygame.Rect(120, 120, BOAT_SIZE[0], BOAT_SIZE[1])
    trash_items = [TrashItem() for _ in range(STARTING_TRASH_COUNT)]

    trash_collected = 0
    score = 0
    running = True

    while running:
        dt = clock.tick(FPS) / 1000.0

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                running = False

        move_boat_to_nearest_trash(boat_rect, trash_items, dt)

        newly_collected, gained_score = collect_on_contact(boat_rect, trash_items)
        trash_collected += newly_collected
        score += gained_score

        draw_vertical_gradient(screen, OCEAN_TOP, OCEAN_BOTTOM)
        draw_waves(screen)

        for item in trash_items:
            item.draw(screen)

        draw_boat(screen, boat_rect)
        draw_hud(screen, title_font, body_font, trash_collected, len(trash_items), score)

        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    try:
        run_game()
    except KeyboardInterrupt:
        pygame.quit()
        sys.exit(0)
