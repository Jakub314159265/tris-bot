import discord
from discord.ext import commands
import random
import asyncio
import json
import os
from datetime import datetime
import time

# define pieces
WIDTH, HEIGHT = 7, 12
PIECES = {
    'I': [[1, 1, 1]],
    'L': [[1, 1], [1, 0]]
}
EMOJI_MAP = {0: "⬛", 1: "🟦", 2: "🟥"}


def rotate_piece(piece):
    return [list(row) for row in zip(*piece[::-1])]


def rotate_i_piece_center(piece):
    """Special rotation for 3-cell I piece to rotate around center"""
    if len(piece) == 1 and len(piece[0]) == 3:  # horizontal I
        return [[1], [1], [1]]  # vertical I
    elif len(piece) == 3 and len(piece[0]) == 1:  # vertical I
        return [[1, 1, 1]]  # horizontal I
    else:
        return piece  # fallback


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


def save_score(username, score, avatar_url, user_id, lines_cleared=0, game_time=0):
    """Save a score to tris.log file, updating individual bests independently"""
    scores = load_scores()
    for entry in scores:
        if entry.get("user_id") == user_id:
            entry.update({
                "games_played": entry.get("games_played", 0) + 1,
                "total_lines": entry.get("total_lines", 0) + lines_cleared,
                "total_time": entry.get("total_time", 0) + game_time,
                "username": username,
                "avatar_url": avatar_url
            })

            # Update bests independently
            if score > entry.get("score", 0):
                entry.update(
                    {"score": score, "timestamp": datetime.now().isoformat()})
            if lines_cleared > entry.get("best_lines", 0):
                entry.update({"best_lines": lines_cleared,
                             "best_lines_timestamp": datetime.now().isoformat()})
            if game_time > entry.get("best_time", 0):
                entry.update(
                    {"best_time": game_time, "best_time_timestamp": datetime.now().isoformat()})
            break
    else:
        scores.append({
            "username": username, "score": score, "avatar_url": avatar_url, "user_id": user_id,
            "timestamp": datetime.now().isoformat(), "games_played": 1, "total_lines": lines_cleared,
            "total_time": game_time, "best_lines": lines_cleared, "best_time": game_time,
            "best_lines_timestamp": datetime.now().isoformat(), "best_time_timestamp": datetime.now().isoformat()
        })

    with open("tris.log", "w") as f:
        for entry in scores:
            f.write(json.dumps(entry) + "\n")


def get_highscores(limit=10):
    """Get top scores from log file"""
    scores = load_scores()
    # sort looking at score, and timestamp if tie
    scores.sort(key=lambda x: (-x["score"], x["timestamp"]))
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
            line.append(EMOJI_MAP[cell])  # change to emojis
        lines.append(''.join(line))
    return '\n'.join(lines)


def check_collision(board, piece, px, py):
    for y, row in enumerate(piece):
        for x, cell in enumerate(row):
            if cell:    # only check parts of the piece
                bx, by = px + x, py + y  # to board coords
                if bx < 0 or bx >= WIDTH or by >= HEIGHT:  # out of bounds
                    return True
                # Only check board collision if piece is within visible area
                if by >= 0 and board[by][bx]:  # overlap with existing pieces
                    return True
    return False


def merge_piece(board, piece, px, py):  # adds piece to board
    for y, row in enumerate(piece):
        for x, cell in enumerate(row):
            if cell:
                bx, by = px + x, py + y
                if 0 <= bx < WIDTH and 0 <= by < HEIGHT:
                    board[by][bx] = 1


def clear_lines(board):
    new_board = [row for row in board if not all(row)]  # removes full lines
    lines_cleared = HEIGHT - len(new_board)
    for _ in range(lines_cleared):
        new_board.insert(0, [0] * WIDTH)  # adds removed lines
    return new_board, lines_cleared


class TetrisGame:
    def __init__(self):
        self.board = empty_board()
        self.score = 0
        self.game_over = False
        self.lines_cleared_total = 0
        self.start_time = time.time()
        self.current_piece_type = None
        self._logged = False
        self.spawn_piece()

    def spawn_piece(self):
        piece_type = random.choice(list(PIECES.keys()))
        self.current_piece_type = piece_type
        self.piece = [row[:] for row in PIECES[piece_type]]
        # random rotation
        for _ in range(random.randint(0, 3)):
            if piece_type == 'I':
                self.piece = rotate_i_piece_center(self.piece)
            else:
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

        if self.current_piece_type == 'I':
            rotated_piece = rotate_i_piece_center(self.piece)
            # calculate offset to keep piece centered
            if len(self.piece) == 1 and len(rotated_piece) == 3:  # horizontal to vertical
                new_px, new_py = self.px + 1, self.py - 1
                wall_kicks = [(0, 0), (-1, 0), (1, 0), (0, -1), (0, 1), (-2, 0), (2, 0)]
            elif len(self.piece) == 3 and len(rotated_piece) == 1:  # vertical to horizontal
                new_px, new_py = self.px - 1, self.py + 1
                wall_kicks = [(0, 0), (-1, 0), (1, 0), (0, 1), (0, -1), (-2, 0), (2, 0)]
            else:
                new_px, new_py = self.px, self.py
                wall_kicks = [(0, 0)]

            for kick_x, kick_y in wall_kicks:
                test_px, test_py = new_px + kick_x, new_py + kick_y
                if not check_collision(self.board, rotated_piece, test_px, test_py):
                    self.piece, self.px, self.py = rotated_piece, test_px, test_py
                    return
            # if no valid position found, just don't rotate
        else:
            rotated_piece = rotate_piece(self.piece)
            # try basic rotation first
            if not check_collision(self.board, rotated_piece, self.px, self.py):
                self.piece = rotated_piece
                return
            
            # try wall kicks for L piece
            wall_kicks = [(0, 0), (-1, 0), (1, 0), (0, -1), (-1, -1), (1, -1)]
            for kick_x, kick_y in wall_kicks:
                test_px, test_py = self.px + kick_x, self.py + kick_y
                if not check_collision(self.board, rotated_piece, test_px, test_py):
                    self.piece, self.px, self.py = rotated_piece, test_px, test_py
                    return
            # if no valid position found, just don't rotate

    def drop(self):
        if self.game_over:
            return False
        if not check_collision(self.board, self.piece, self.px, self.py + 1):
            self.py += 1
            return True
        else:
            self.land_piece()
            return False

    def hard_drop(self):
        if self.game_over:
            return
        while not check_collision(self.board, self.piece, self.px, self.py + 1):
            self.py += 1
            self.score += 2  # points for hard dropping
        self.land_piece()

    def land_piece(self):
        merge_piece(self.board, self.piece, self.px, self.py)
        self.board, lines_cleared = clear_lines(self.board)
        self.lines_cleared_total += lines_cleared
        self.score += (lines_cleared ** 2) * 100
        
        # Generate the actual next piece that would spawn
        next_piece_type = random.choice(list(PIECES.keys()))
        next_piece = [row[:] for row in PIECES[next_piece_type]]
        # Apply random rotation like in spawn_piece
        for _ in range(random.randint(0, 3)):
            if next_piece_type == 'I':
                next_piece = rotate_i_piece_center(next_piece)
            else:
                next_piece = rotate_piece(next_piece)
        
        next_px = WIDTH // 2 - len(next_piece[0]) // 2
        next_py = 0
        
        # Check if this actual next piece can spawn
        if check_collision(self.board, next_piece, next_px, next_py):
            self.game_over = True
            return
            
        # If no collision, spawn the piece we just generated
        self.current_piece_type = next_piece_type
        self.piece = next_piece
        self.px = next_px
        self.py = next_py

    def get_game_time(self):
        return time.time() - self.start_time

    def render(self):
        if self.game_over:
            game_time = self.get_game_time()
            return f"GAME OVER!\nScore: {self.score}\nLines: {self.lines_cleared_total}\nTime: {game_time:.1f}s\n\nUse `!tris` to start a new game"
        return f"Tris\nScore: {self.score}\nLines: {self.lines_cleared_total}\n\n{render_board(self.board, self.piece, self.px, self.py)}"
        # previous line looks like hell but it works so i wont change it


# bot setup
intents = discord.Intents.default()
intents.message_content = True
intents.reactions = True
bot = commands.Bot(command_prefix="!", intents=intents, case_insensitive=True, help_command=None)
# Custom !help command to redirect to !trishelp
@bot.command(name="help")
async def help_command(ctx):
    """Show the Tris Bot help menu (same as !trishelp)"""
    await trishelp_command(ctx)

games = {}
messages = {}
tasks = {}

REACTION_CONTROLS = {'⬅️': 'a', '➡️': 'd', '⬇️': 's', '🔄': 'w', '❌': 'q'}


def log_game_score(game, user_id, user):
    """Helper function to log game score"""
    if game.score > 0 and not game._logged:
        username = getattr(user, "display_name", str(user))
        avatar_url = str(user.avatar.url) if user.avatar else ""
        save_score(username, game.score, avatar_url, user_id,
                   game.lines_cleared_total, game.get_game_time())
        game._logged = True


async def cleanup_user_game(user_id):
    """Clean up all resources for a specific user's game"""
    game = games.get(user_id)
    if game and game.game_over:
        user = bot.get_user(user_id) or next((guild.get_member(user_id)
                                              for guild in bot.guilds if guild.get_member(user_id)), None)
        if user:
            log_game_score(game, user_id, user)

    # Cancel task and clean up
    if user_id in tasks:
        tasks[user_id].cancel()
        tasks.pop(user_id, None)

    # Clean up message
    if user_id in messages:
        try:
            await messages[user_id].clear_reactions()
            await messages[user_id].delete()
        except (discord.NotFound, discord.Forbidden):
            pass
        messages.pop(user_id, None)

    games.pop(user_id, None)


async def auto_drop(user_id):
    """Auto-drop task - smoother with reduced interval"""
    try:
        while user_id in games:
            game = games.get(user_id)
            if not game or game.game_over:
                break

            prev_score = game.score
            prev_game_over = game.game_over
            
            moved = game.drop()

            # Check if game state changed (score, game over, or piece moved)
            if moved or game.score != prev_score or game.game_over != prev_game_over:
                msg = messages.get(user_id)
                if msg:
                    try:
                        await msg.edit(content=game.render())
                    except (discord.NotFound, discord.HTTPException):
                        break
                        
            # Exit if game is over
            if game.game_over:
                break
                
            await asyncio.sleep(0.7)  # Smoother autodrop
    except asyncio.CancelledError:
        pass
    finally:
        # Clean up when task ends
        if user_id in tasks:
            tasks.pop(user_id, None)


async def add_game_reactions(message):
    """Add control reactions to the game message"""
    try:
        for reaction in REACTION_CONTROLS.keys():
            await message.add_reaction(reaction)
    except (discord.NotFound, discord.Forbidden):
        pass


async def update_display(ctx_or_msg, user_id):
    game = games.get(user_id)
    if not game:
        return

    msg = messages.get(user_id)
    channel = ctx_or_msg.channel if hasattr(
        ctx_or_msg, 'channel') else ctx_or_msg

    try:
        if msg:
            await msg.edit(content=game.render())
        else:
            new_msg = await channel.send(game.render())
            messages[user_id] = new_msg
            await add_game_reactions(new_msg)
    except (discord.NotFound, discord.HTTPException):
        new_msg = await channel.send(game.render())
        messages[user_id] = new_msg
        await add_game_reactions(new_msg)

    # Handle game over - clear reactions immediately and log score
    if game.game_over:
        # Clear reactions immediately when game over is detected
        if msg:
            try:
                await msg.clear_reactions()
            except (discord.NotFound, discord.Forbidden):
                pass

        # Log score
        user = getattr(ctx_or_msg, 'author', None) or bot.get_user(user_id) or next(
            (guild.get_member(user_id) for guild in bot.guilds if guild.get_member(user_id)), None)
        if user:
            log_game_score(game, user_id, user)

        # Cancel the auto-drop task to prevent further updates
        if user_id in tasks:
            tasks[user_id].cancel()
            tasks.pop(user_id, None)


@bot.event
async def on_ready():
    print(f"{bot.user}")
    print("------")


@bot.command()
async def tris(ctx):
    """Start the game >w<"""
    user_id = ctx.author.id

    # Log previous game if completed
    if user_id in games and games[user_id].game_over:
        log_game_score(games[user_id], user_id, ctx.author)

    await cleanup_user_game(user_id)
    games[user_id] = TetrisGame()
    await update_display(ctx, user_id)
    tasks[user_id] = bot.loop.create_task(auto_drop(user_id))


@bot.command(name="trishelp")
async def trishelp_command(ctx):
    """Display detailed help"""
    help_text = """
TRIS BOT COMMANDS

Game Controls:
!tris - Start new game
!a    - Move left 
!d    - Move right
!s    - Hard drop (instant fall)
!w    - Rotate piece
!q    - End current game

**Reaction Controls:**
⬅️ - Move left
➡️ - Move right  
⬇️ - Hard drop
🔄 - Rotate piece
❌ - Quit game

• You can combine commands: !aaa (move left 3x), !wd (rotate + move right)
• Clearing lines gives 100 points each
• Hard drop gives 2 points per cell dropped

Stats:
!score   - View top 10 scores
!trishelp     - Show this help menu
    """
    embed = discord.Embed(
        title="Tris Bot Help",
        description=help_text,
        color=0x00ffa0
    )
    embed.set_footer(text="uwu")
    await ctx.send(embed=embed)


@bot.command()
async def score(ctx, *, user: discord.Member = None):
    """Display top 10 high scores, or stats for a mentioned user."""
    scores = load_scores()
    if user:
        # Try to match by user_id
        entry = next((s for s in scores if s.get("user_id") == user.id), None)
        if not entry:
            await ctx.send(f"No stats found for {user.display_name}.")
            return
        embed = discord.Embed(
            title=f"Stats for {entry['username']}",
            color=0x00bfff
        )
        avatar_url = entry.get("avatar_url", "")
        if avatar_url:
            embed.set_thumbnail(url=avatar_url)
        date = datetime.fromisoformat(entry["timestamp"]).strftime("%m/%d")
        games_played = entry.get("games_played", 1)
        total_lines = entry.get("total_lines", 0)
        total_time = entry.get("total_time", 0)
        best_lines = entry.get("best_lines", 0)
        best_time = entry.get("best_time", 0)
        best_lines_date = f" ({datetime.fromisoformat(entry['best_lines_timestamp']).strftime('%m/%d')})" if "best_lines_timestamp" in entry else ""
        best_time_date = f" ({datetime.fromisoformat(entry['best_time_timestamp']).strftime('%m/%d')})" if "best_time_timestamp" in entry else ""
        avg_score = entry["score"] / games_played if games_played > 0 else 0
        avg_lines = total_lines / games_played if games_played > 0 else 0
        avg_time = total_time / games_played if games_played > 0 else 0
        stats_text = (
            f"**Best Score:** {entry['score']:,} pts ({date})\n"
            f"**Games:** {games_played} | **Avg Score:** {avg_score:,.0f}\n"
            f"**Best Lines:** {best_lines}{best_lines_date} | **Total:** {total_lines:,} | **Avg:** {avg_lines:.1f}\n"
            f"**Longest game:** {best_time:.1f}s{best_time_date} | **Avg Time:** {avg_time:.1f}s\n"
            f"**Total Time:** {total_time:.1f}s"
        )
        embed.add_field(name="Statistics", value=stats_text, inline=False)
        embed.set_footer(text=">w<")
        await ctx.send(embed=embed)
    else:
        # Show top 10 scores as before
        top_scores = get_highscores(10)
        if not top_scores:
            await ctx.send("No high scores yet")
            return
        for i, score_entry in enumerate(top_scores):
            rank = i + 1
            username = score_entry["username"]
            score_val = score_entry["score"]
            date = datetime.fromisoformat(score_entry["timestamp"]).strftime("%m/%d")
            avatar_url = score_entry.get("avatar_url", "")
            games_played = score_entry.get("games_played", 1)
            total_lines = score_entry.get("total_lines", 0)
            total_time = score_entry.get("total_time", 0)
            best_lines = score_entry.get("best_lines", 0)
            best_time = score_entry.get("best_time", 0)
            best_lines_date = f" ({datetime.fromisoformat(score_entry['best_lines_timestamp']).strftime('%m/%d')})" if "best_lines_timestamp" in score_entry else ""
            best_time_date = f" ({datetime.fromisoformat(score_entry['best_time_timestamp']).strftime('%m/%d')})" if "best_time_timestamp" in score_entry else ""
            avg_score = score_val / games_played if games_played > 0 else 0
            avg_lines = total_lines / games_played if games_played > 0 else 0
            avg_time = total_time / games_played if games_played > 0 else 0
            stats_text = (
                f"**Best Score:** {score_val:,} pts ({date})\n"
                f"**Games:** {games_played} | **Avg Score:** {avg_score:,.0f}\n"
                f"**Best Lines:** {best_lines}{best_lines_date} | **Total:** {total_lines:,} | **Avg:** {avg_lines:.1f}\n"
                f"**Longest game:** {best_time:.1f}s{best_time_date} | **Avg Time:** {avg_time:.1f}s\n"
                f"**Total Time:** {total_time:.1f}s"
            )
            medal = "🥇" if rank == 1 else "🥈" if rank == 2 else "🥉" if rank == 3 else f"{rank}."
            embed = discord.Embed(
                title=f"{medal} {username}",
                description=stats_text,
                color=0xffd700
            )
            if avatar_url:
                embed.set_thumbnail(url=avatar_url)
            embed.set_footer(text=">w<")
            await ctx.send(embed=embed)


@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    if message.content.startswith("!"):
        commands_str = message.content[1:].lower()
        valid_commands = {'a', 'd', 's', 'w', 'q'}

        # Handle compound commands
        if all(c in valid_commands for c in commands_str):
            user_id = message.author.id
            game = games.get(user_id)
            if game and not game.game_over:
                prev_score = game.score
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
                        log_game_score(game, user_id, message.author)
                        break

                if game.score != prev_score or game.game_over:
                    await update_display(message, user_id)
                try:
                    await message.delete()
                except discord.Forbidden:
                    pass
                return

        # Clean up command messages
        if commands_str in ['tris', 'a', 'd', 's', 'w', 'q', 'trishelp', 'score']:
            try:
                await message.delete()
            except discord.Forbidden:
                pass

    if "uwu" in message.content.lower():
        await message.channel.send("owo")
    if "owo" in message.content.lower():
        await message.channel.send("uwu")

    await bot.process_commands(message)


@bot.event
async def on_reaction_add(reaction, user):
    """Handle reaction-based game controls"""
    if user.bot or user.id not in messages or messages[user.id].id != reaction.message.id:
        return

    game = games.get(user.id)
    if not game or game.game_over:
        return

    command = REACTION_CONTROLS.get(str(reaction.emoji))
    if not command:
        return

    prev_score = game.score

    if command == 'a':
        game.move_left()
    elif command == 'd':
        game.move_right()
    elif command == 's':
        game.hard_drop()
    elif command == 'w':
        game.rotate()
    elif command == 'q':
        game.game_over = True
        log_game_score(game, user.id, user)

    if game.score != prev_score or game.game_over:
        await update_display(reaction.message, user.id)

    try:
        await reaction.remove(user)
    except (discord.NotFound, discord.Forbidden):
        pass


@bot.event
async def on_member_remove(member):
    """Clean up games when users leave the server"""
    await cleanup_user_game(member.id)


@bot.command()
async def delall(ctx):
    """Delete all messages sent by this bot and all command messages to this bot in the current channel"""
    deleted_count = 0
    status_msg = await ctx.send("Deleting all bot and command messages from this channel...")
    # list of recognized command prefixes for this bot
    command_prefixes = [
        "!tris", "!a", "!d", "!s", "!w", "!q", "!trishelp", "!highscores", "!delall"
    ]
    try:
        # only current channel
        channel = ctx.channel
        if not channel.permissions_for(ctx.guild.me).read_message_history:
            await status_msg.edit(content="No permission to read message history in this channel.")
            return

        async for message in channel.history(limit=1000):
            # skip the current delall command message and status message
            if message.id == ctx.message.id or message.id == status_msg.id:
                continue

            # delete if message is from the bot
            if message.author == bot.user:
                try:
                    await message.delete()
                    deleted_count += 1
                    if deleted_count % 20 == 0:
                        try:
                            await status_msg.edit(content=f"Deleted {deleted_count} messages...")
                        except (discord.NotFound, discord.HTTPException):
                            pass
                    await asyncio.sleep(0.1)
                except (discord.NotFound, discord.Forbidden):
                    pass
            # delete if message is a command to the bot
            elif (
                message.content.startswith("!")
                and any(message.content.lower().startswith(cmd) for cmd in command_prefixes)
            ):
                try:
                    await message.delete()
                    deleted_count += 1
                    if deleted_count % 20 == 0:
                        try:
                            await status_msg.edit(content=f"Deleted {deleted_count} messages...")
                        except (discord.NotFound, discord.HTTPException):
                            pass
                    await asyncio.sleep(0.1)
                except (discord.NotFound, discord.Forbidden):
                    pass

        try:
            await status_msg.edit(content=f"Deleted {deleted_count} bot and command messages from this channel.")
            await asyncio.sleep(5)
            await status_msg.delete()
        except (discord.NotFound, discord.HTTPException):
            pass
    except Exception as e:
        try:
            await status_msg.edit(content=f"Error: {str(e)}")
            await asyncio.sleep(5)
            await status_msg.delete()
        except (discord.NotFound, discord.HTTPException):
            pass

with open("token.txt", "r") as f:
    bot.run(f.read().strip())