from __future__ import annotations

import asyncio

import pygame

TITLE_TEXT = "Mission Clean Ocean"
BG_COLOR = (0, 0, 0)
TEXT_COLOR = (255, 255, 255)
PROMPT_COLOR = (215, 215, 215)

# TODO: Devika, add the intro paragraphs here:
INTRO_PARAGRAPHS = [
    """
In the year 2050, ocean trash formed floating islands the size of cities.
Your crew is humanity's last line of defense against rising tides and lost coastline.
""",
    """
You are in command of Mission Clean Ocean.
Navigate, collect waste, and upgrade your fleet to restore blue waters worldwide.
""",
]


def _draw_center_text(surface: pygame.Surface, font: pygame.font.Font, text: str, alpha: int) -> None:
    txt = font.render(text, True, TEXT_COLOR)
    txt = txt.convert_alpha()
    txt.set_alpha(max(0, min(255, alpha)))
    rect = txt.get_rect(center=(surface.get_width() // 2, surface.get_height() // 2))
    surface.blit(txt, rect)


async def _run_title_sequence(screen: pygame.Surface, clock: pygame.time.Clock) -> bool:
    font = pygame.font.SysFont("Courier New", 64, bold=True)

    pre_wait = 0.55
    fade_in = 1.0
    hold = 0.7
    fade_out = 1.0
    post_wait = 0.55

    t = 0.0
    stage = "pre"
    running = True

    while running:
        dt = clock.tick(60) / 1000.0
        t += dt

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                return False

        screen.fill(BG_COLOR)

        if stage == "pre":
            if t >= pre_wait:
                stage = "in"
                t = 0.0
        elif stage == "in":
            alpha = int(255.0 * min(1.0, t / fade_in))
            _draw_center_text(screen, font, TITLE_TEXT, alpha)
            if t >= fade_in:
                stage = "hold"
                t = 0.0
        elif stage == "hold":
            _draw_center_text(screen, font, TITLE_TEXT, 255)
            if t >= hold:
                stage = "out"
                t = 0.0
        elif stage == "out":
            alpha = int(255.0 * max(0.0, 1.0 - (t / fade_out)))
            _draw_center_text(screen, font, TITLE_TEXT, alpha)
            if t >= fade_out:
                stage = "post"
                t = 0.0
        else:  # post
            if t >= post_wait:
                running = False

        pygame.display.flip()
        await asyncio.sleep(0)

    return True


async def _show_paragraph_step(screen: pygame.Surface, clock: pygame.time.Clock, text: str) -> bool:
    body_font = pygame.font.SysFont("Courier New", 26, bold=True)
    hint_font = pygame.font.SysFont("Courier New", 18, bold=True)
    lines = [line.strip() for line in text.strip().splitlines() if line.strip()]

    while True:
        dt = clock.tick(60) / 1000.0

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return False
                if event.key in (pygame.K_RETURN, pygame.K_SPACE):
                    return True

        screen.fill(BG_COLOR)

        y_start = screen.get_height() // 2 - (len(lines) * 22)
        for i, line in enumerate(lines):
            text_surf = body_font.render(line, True, TEXT_COLOR)
            text_rect = text_surf.get_rect(center=(screen.get_width() // 2, y_start + i * 45))
            screen.blit(text_surf, text_rect)

        hint = hint_font.render("Press ENTER or SPACE to continue", True, PROMPT_COLOR)
        hint_rect = hint.get_rect(center=(screen.get_width() // 2, screen.get_height() - 64))
        screen.blit(hint, hint_rect)

        pygame.display.flip()
        await asyncio.sleep(0)


async def _show_paragraphs(screen: pygame.Surface, clock: pygame.time.Clock, paragraphs: list[str]) -> bool:
    for paragraph in paragraphs:
        if not await _show_paragraph_step(screen, clock, paragraph):
            return False
    return True


async def _prompt_name(screen: pygame.Surface, clock: pygame.time.Clock) -> str | None:
    title_font = pygame.font.SysFont("Courier New", 38, bold=True)
    body_font = pygame.font.SysFont("Courier New", 30, bold=True)
    hint_font = pygame.font.SysFont("Courier New", 20, bold=True)

    prompt = "Enter Your In-Game Name:"
    value = ""
    cursor_timer = 0.0

    while True:
        dt = clock.tick(60) / 1000.0
        cursor_timer += dt

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return None
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return None
                if event.key == pygame.K_RETURN:
                    v = value.strip()
                    return v if v else "Captain"
                if event.key == pygame.K_BACKSPACE:
                    value = value[:-1]
                elif event.unicode and event.unicode.isprintable() and len(value) < 20:
                    value += event.unicode

        screen.fill(BG_COLOR)

        title = title_font.render(TITLE_TEXT, True, TEXT_COLOR)
        title_rect = title.get_rect(center=(screen.get_width() // 2, screen.get_height() // 2 - 120))
        screen.blit(title, title_rect)

        p = body_font.render(prompt, True, PROMPT_COLOR)
        p_rect = p.get_rect(center=(screen.get_width() // 2, screen.get_height() // 2 - 10))
        screen.blit(p, p_rect)

        cursor_on = (cursor_timer % 1.0) < 0.5
        text_line = value + ("_" if cursor_on else "")
        v = body_font.render(text_line, True, TEXT_COLOR)
        v_rect = v.get_rect(center=(screen.get_width() // 2, screen.get_height() // 2 + 45))
        screen.blit(v, v_rect)

        hint = hint_font.render("Press ENTER to continue", True, (170, 170, 170))
        hint_rect = hint.get_rect(center=(screen.get_width() // 2, screen.get_height() // 2 + 95))
        screen.blit(hint, hint_rect)

        pygame.display.flip()
        await asyncio.sleep(0)


async def play_intro(screen: pygame.Surface, clock: pygame.time.Clock) -> str | None:
    if not await _run_title_sequence(screen, clock):
        return None

    if not await _show_paragraphs(screen, clock, INTRO_PARAGRAPHS):
        return None

    return await _prompt_name(screen, clock)
