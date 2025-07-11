# Tris Bot

A simple Discord bot for playing a Tetris-like game in chat.

## Features

- Play Tetris with emoji graphics directly in Discord
- Move, rotate, and hard drop pieces using chat commands
- Automatic piece dropping
- High score tracking and leaderboard
- User avatars shown in high scores

## Commands

- `!tris` — Start a new game
- `!a` — Move left
- `!d` — Move right
- `!w` — Rotate piece
- `!s` — Hard drop
- `!q` — End current game
- `!score` — show top scores and statistics
    - `!score @<user>` — show score and data about this player
- `!trishelp` — show help
- `!setspeed` — set game speed serverwide

Combine commands (e.g., `!aad`) for quick moves.

## Setup

1. Install dependencies: `pip install discord.py`
2. Place your Discord api in `token.txt` file in the same directory as tris.py
3. Run the bot: `python tris.py`

Or invite with https://discord.com/oauth2/authorize?client_id=1389591768273518664&permissions=551903422528&integration_type=0&scope=bot
