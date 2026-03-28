# MVHacks - Pixel Boat Cleanup V0

Minimal Python 3 + Pygame prototype where your boat automatically collects floating trash.

## Setup

```bash
cd /Users/andrew/Downloads/MVHacks
python3 -m venv .venv
source .venv/bin/activate
pip install pygame
```

## Run

```bash
cd /Users/andrew/Downloads/MVHacks
source .venv/bin/activate
python3 game/main.py
```

## Controls

- Boat movement and collection are fully automatic
- Drag with left mouse on the map area to pan camera
- `ESC` or close window: Quit

## Current Behavior

- Left sidebar HUD (no longer covers map/base ship)
- Ocean is tiled from `assets/ocean.jpeg`
- Large world map with more trash
- A large base ship sits in the top-left world corner
- Small collection boat has 10 seconds of fuel
- When fuel reaches zero, it automatically returns to base
- It refuels for 2 seconds, then resumes trash collection

## Notes

- No timer, weather, or economy systems yet.
- Uses placeholder shapes for non-ocean assets.
