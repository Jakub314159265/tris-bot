import discord
from discord.ext import commands
import random
import asyncio
import json
import os
from datetime import datetime

# define pieces
WIDTH, HEIGHT = 7, 12
PIECES = {
    'I': [[1, 1, 1]],
    'L': [[1, 1], [1, 0]]
}
EMOJI_MAP = {0: "⬛", 1: "🟦", 2: "🟥"}


def rotate_piece(piece):
    return [list(row) for row in zip(*piece[::-1])]


def empty_board():
    return [[0] * WIDTH for _ in range(HEIGHT)]


def load_scores():
    """Load scores from tris.log file"""
    if os.path.exists("tris.log"):
        try:
            with open("tris.log", "r") as f:
                return [json.loads(line) for line in f if line.strip()]
        except:
            return []
    return []


def save_score(username, score, avatar_url, user_id):
    """Save a score to tris.log file, only when its best score per user"""
    scores = load_scores()
    updated = False
    for entry in scores:
        if entry.get("user_id") == user_id:
            if score > entry.get("score", 0):
                entry["score"] = score
                entry["username"] = username
                entry["avatar_url"] = avatar_url
                entry["timestamp"] = datetime.now().isoformat()
            updated = True
            break
    if not updated:
        score_entry = {
            "username": username,
            "score": score,
            "avatar_url": avatar_url,
            "user_id": user_id,
            "timestamp": datetime.now().isoformat()
        }
        scores.append(score_entry)
    # rewrite all scores
    with open("tris.log", "w") as f:
        for entry in scores:
            f.write(json.dumps(entry) + "\n")


def get_highscores(limit=10):
    """Get top scores from log file"""
    scores = load_scores()
    scores.sort(key=lambda x: (-x["score"], x["timestamp"])) # sort looking at score, and timestamp if tie
    return scores[:limit]


def render_board(board, piece=None, px=0, py=0):
    lines = []
    for y in range(HEIGHT):
        line = []
        for x in range(WIDTH):
            cell = board[y][x]
            # check piece overlap
            if (piece and py <= y < py + len(piece) and
                px <= x < px + len(piece[0]) and
                    piece[y - py][x - px]):
                cell = 2
            line.append(EMOJI_MAP[cell]) # change to emojis
        lines.append(''.join(line))
    return '\n'.join(lines)


def check_collision(board, piece, px, py):
    for y, row in enumerate(piece):
        for x, cell in enumerate(row):
            if cell:    # only check parts of the piece
                bx, by = px + x, py + y # to board coords
                if bx < 0 or bx >= WIDTH or by >= HEIGHT: # out of bounds
                    return True
                if by >= 0 and board[by][bx]: # overlap
                    return True
    return False


def merge_piece(board, piece, px, py): # adds piece to board
    for y, row in enumerate(piece):
        for x, cell in enumerate(row):
            if cell:
                bx, by = px + x, py + y
                if 0 <= bx < WIDTH and 0 <= by < HEIGHT:
                    board[by][bx] = 1


def clear_lines(board):
    new_board = [row for row in board if not all(row)] # removes full lines
    lines_cleared = HEIGHT - len(new_board)
    for _ in range(lines_cleared):
        new_board.insert(0, [0] * WIDTH) # adds removed lines
    return new_board, lines_cleared


class TetrisGame:
    def __init__(self): # inits constants
        self.board = empty_board()
        self.score = 0
        self.game_over = False
        self.spawn_piece()

    def spawn_piece(self):
        self.piece = [row[:]
                      for row in PIECES[random.choice(list(PIECES.keys()))]]
        # Random rotation
        for _ in range(random.randint(0, 3)):
            self.piece = rotate_piece(self.piece)
        self.px = WIDTH // 2 - len(self.piece[0]) // 2
        self.py = 0

    def move_left(self):
        if not self.game_over and not check_collision(self.board, self.piece, self.px - 1, self.py):
            self.px -= 1

    def move_right(self):
        if not self.game_over and not check_collision(self.board, self.piece, self.px + 1, self.py):
            self.px += 1

    def rotate(self):
        if self.game_over:
            return
        rotated_piece = rotate_piece(self.piece)
        if not check_collision(self.board, rotated_piece, self.px, self.py):
            self.piece = rotated_piece

    def drop(self):
        if self.game_over:
            return False
        if not check_collision(self.board, self.piece, self.px, self.py + 1):
            self.py += 1
            return True
        self.land_piece()
        return False

    def hard_drop(self):
        if self.game_over:
            return
        while not check_collision(self.board, self.piece, self.px, self.py + 1):
            self.py += 1
            self.score += 2 # points for hard dropping
        self.land_piece()

    def land_piece(self):
        merge_piece(self.board, self.piece, self.px, self.py)
        self.board, lines_cleared = clear_lines(self.board)
        self.score += (lines_cleared ** 2) * 100
        self.spawn_piece()
        if check_collision(self.board, self.piece, self.px, self.py + 1):
            self.game_over = True

    def render(self):
        if self.game_over:
            return f"GAME OVER!\nScore: {self.score}\n\nUse `!tris` to start a new game"
        return f"Tris\nScore: {self.score}\n\n{render_board(self.board, self.piece, self.px, self.py)}"


# Bot setup
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents, case_insensitive=True)

games = {}
messages = {}
tasks = {}


async def auto_drop(user_id):
    try:
        while user_id in games and not games[user_id].game_over:
            game = games.get(user_id)
            if not game or game.game_over:
                break

            # Store state before drop
            prev_state = (game.px, game.py, [row[:] for row in game.piece], [
                          row[:] for row in game.board], game.score)
            moved = game.drop()
            new_state = (game.px, game.py, [row[:] for row in game.piece], [
                         row[:] for row in game.board], game.score)

            if moved or prev_state != new_state:
                msg = messages.get(user_id)
                if msg:
                    try:
                        await msg.edit(content=game.render())
                    except (discord.NotFound, discord.HTTPException):
                        break
            await asyncio.sleep(1.0)
    except asyncio.CancelledError:
        pass
    finally:
        tasks.pop(user_id, None)


async def update_display(ctx_or_msg, user_id):
    game = games.get(user_id)
    if not game:
        return

    msg = messages.get(user_id)
    channel = ctx_or_msg.channel if hasattr(
        ctx_or_msg, 'channel') else ctx_or_msg

    if msg:
        try:
            await msg.edit(content=game.render())
        except (discord.NotFound, discord.HTTPException):
            messages[user_id] = await channel.send(game.render())
    else:
        messages[user_id] = await channel.send(game.render())

    # Save score to log if game is over and not already saved
    if game and game.game_over and game.score > 0:
        # Prevent duplicate log entries for the same game over
        if not hasattr(game, "_logged") or not game._logged:
            author = None
            # Try to get author from ctx or message
            if hasattr(ctx_or_msg, "author"):
                author = ctx_or_msg.author
            elif hasattr(ctx_or_msg, "user"):
                author = ctx_or_msg.user
            if author:
                save_score(
                    getattr(author, "display_name", str(author)),
                    game.score,
                    str(getattr(getattr(author, "avatar", None), "url", "")) if getattr(author, "avatar", None) else "",
                    getattr(author, "id", 0)
                )
                game._logged = True


@bot.event
async def on_ready():
    print(f"{bot.user}")
    print("------")


@bot.command()
async def tris(ctx):
    user_id = ctx.author.id

    # Log final score if previous game existed
    if user_id in games and games[user_id].game_over and games[user_id].score > 0:
        # Prevent duplicate log entries for the same game over
        if not hasattr(games[user_id], "_logged") or not games[user_id]._logged:
            save_score(
                ctx.author.display_name,
                games[user_id].score,
                str(ctx.author.avatar.url) if ctx.author.avatar else "",
                user_id
            )
            games[user_id]._logged = True

    # Cancel existing task
    if user_id in tasks:
        tasks[user_id].cancel()

    # Remove old message if previous game existed and was over
    if user_id in messages:
        try:
            await messages[user_id].delete()
        except (discord.NotFound, discord.Forbidden):
            pass
        messages.pop(user_id, None)

    # Start new game
    games[user_id] = TetrisGame()
    await update_display(ctx, user_id)
    tasks[user_id] = bot.loop.create_task(auto_drop(user_id))

@bot.command(name="trishelp")
async def trishelp_command(ctx):
    help_text = """
TRIS BOT COMMANDS

Game Controls:
!tris - Start new game
!a    - Move left 
!d    - Move right
!s    - Hard drop (instant fall)
!w    - Rotate piece
!q    - End current game

• You can combine commands: !aaa (move left 3x), !wd (rotate + move right)
• Clearing lines gives 100 points each
• Hard drop gives 2 points per cell dropped

Stats:
!highscores   - View top 10 scores
!trishelp     - Show this help menu
    """
    embed = discord.Embed(
        title="Tris Bot Help",
        description=help_text,
        color=0x00ff00
    )
    embed.set_footer(text="uwu")
    await ctx.send(embed=embed)


@bot.command()
async def highscores(ctx):
    """Display top 10 high scores"""
    scores = get_highscores(10)

    if not scores:
        await ctx.send("No high scores yet")
        return

    description = ""
    embed = discord.Embed(
        title="Tris High Scores",
        color=0xffd700
    )
    for i, score_entry in enumerate(scores):
        rank = i + 1
        username = score_entry["username"]
        score_val = score_entry["score"]
        date = datetime.fromisoformat(score_entry["timestamp"]).strftime("%m/%d")
        avatar_url = score_entry.get("avatar_url", "")
        # Use avatar as thumbnail for first place, as icon for others
        if i == 0 and avatar_url:
            embed.set_thumbnail(url=avatar_url)
        # Add each user as a field with avatar inline
        name_line = f"{rank}. {username}"
        value_line = f"{score_val:,} pts ({date})"
        embed.add_field(name=name_line, value=value_line, inline=False)
    embed.set_footer(text=":3")
    await ctx.send(embed=embed)


@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    if message.content.startswith("!"):
        commands_str = message.content[1:].lower()
        valid_commands = {'a', 'd', 's', 'w', 'q'}

        # Compound commands: only if all are valid and more than one
        if all(c in valid_commands for c in commands_str):
            user_id = message.author.id
            game = games.get(user_id)
            if game and not game.game_over:
                prev_state = (game.px, game.py, [row[:] for row in game.piece], [
                              row[:] for row in game.board], game.score)
                for cmd in commands_str:
                    if cmd == 'a':
                        game.move_left()
                    elif cmd == 'd':
                        game.move_right()
                    elif cmd == 's':
                        game.hard_drop()
                    elif cmd == 'w':
                        game.rotate()
                    elif cmd == 'q':
                        game.game_over = True
                        break
                new_state = (game.px, game.py, [row[:] for row in game.piece], [
                             row[:] for row in game.board], game.score)
                if prev_state != new_state or game.game_over:
                    await update_display(message, user_id)
                try:
                    await message.delete()
                except discord.Forbidden:
                    pass
                return

        # Clean up single commands
        if commands_str in ['tris', 'a', 'd', 's', 'w', 'q', 'trishelp', 'highscores']:
            try:
                await message.delete()
            except discord.Forbidden:
                pass

    await bot.process_commands(message)

with open("token.txt", "r") as f:
    bot.run(f.read().strip())
