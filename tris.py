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
    updated = False
    for entry in scores:
        if entry.get("user_id") == user_id:
            entry["games_played"] = entry.get("games_played", 0) + 1
            entry["total_lines"] = entry.get("total_lines", 0) + lines_cleared
            entry["total_time"] = entry.get("total_time", 0) + game_time
            entry["username"] = username  # update username in case it changed
            entry["avatar_url"] = avatar_url  # update avatar

            # Update data independently
            if score > entry.get("score", 0):
                entry["score"] = score
                entry["timestamp"] = datetime.now().isoformat()

            if lines_cleared > entry.get("best_lines", 0):
                entry["best_lines"] = lines_cleared
                entry["best_lines_timestamp"] = datetime.now().isoformat()

            if game_time > entry.get("best_time", 0):
                entry["best_time"] = game_time
                entry["best_time_timestamp"] = datetime.now().isoformat()

            updated = True
            break
    if not updated:
        score_entry = {
            "username": username,
            "score": score,
            "avatar_url": avatar_url,
            "user_id": user_id,
            "timestamp": datetime.now().isoformat(),
            "games_played": 1,
            "total_lines": lines_cleared,
            "total_time": game_time,
            "best_lines": lines_cleared,
            "best_time": game_time,
            "best_lines_timestamp": datetime.now().isoformat(),
            "best_time_timestamp": datetime.now().isoformat()
        }
        scores.append(score_entry)
    # rewrite all scores
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
                if by >= 0 and board[by][bx]:  # overlap
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
    def __init__(self):  # inits constants
        self.board = empty_board()
        self.score = 0
        self.game_over = False
        self.lines_cleared_total = 0
        self.start_time = time.time()
        self.spawn_piece()

    def spawn_piece(self):
        self.piece = [row[:]
                      for row in PIECES[random.choice(list(PIECES.keys()))]]
        # random rotation
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
            self.score += 2  # points for hard dropping
        self.land_piece()

    def land_piece(self):
        merge_piece(self.board, self.piece, self.px, self.py)
        self.board, lines_cleared = clear_lines(self.board)
        self.lines_cleared_total += lines_cleared
        self.score += (lines_cleared ** 2) * 100
        self.spawn_piece()
        if check_collision(self.board, self.piece, self.px, self.py + 1):
            self.game_over = True

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
bot = commands.Bot(command_prefix="!", intents=intents, case_insensitive=True)

games = {}      # user_id -> TetrisGame instance
messages = {}   # user_id -> discord.Message instance
tasks = {}      # user_id -> asyncio.Task for auto-drop

# reaction controls mapping
REACTION_CONTROLS = {
    '⬅️': 'a',   # Move left
    '➡️': 'd',   # Move right
    '⬇️': 's',   # Hard drop
    '🔄': 'w',   # Rotate
    '❌': 'q'    # Quit
}


async def cleanup_user_game(user_id):
    """Clean up all resources for a specific user's game"""
    # Log final score if game exists and hasn't been logged yet
    game = games.get(user_id)
    if game and game.game_over and game.score > 0:
        if not hasattr(game, "_logged") or not game._logged:
            # try to get user from any available source
            user = bot.get_user(user_id)
            if not user:
                # try to find user in guilds if not in cache
                for guild in bot.guilds:
                    user = guild.get_member(user_id)
                    if user:
                        break

            if user:
                username = getattr(user, "display_name", str(user))
                avatar_url = str(user.avatar.url) if user.avatar else ""
                save_score(
                    username,
                    game.score,
                    avatar_url,
                    user_id,
                    game.lines_cleared_total,
                    game.get_game_time()
                )
                game._logged = True

    # cancel auto-drop task
    if user_id in tasks:
        tasks[user_id].cancel()
        tasks.pop(user_id, None)

    # remove message reactions and delete message
    if user_id in messages:
        try:
            await messages[user_id].clear_reactions()
        except (discord.NotFound, discord.Forbidden):
            pass
        try:
            await messages[user_id].delete()
        except (discord.NotFound, discord.Forbidden):
            pass
        messages.pop(user_id, None)

    # remove game instance
    games.pop(user_id, None)


async def auto_drop(user_id):
    """Auto-drop task - one per user"""
    try:
        while user_id in games and not games[user_id].game_over:
            game = games.get(user_id)
            if not game or game.game_over:
                break

            # store state before drop
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
        # clean up task reference when done
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

    if msg:
        try:
            await msg.edit(content=game.render())
        except (discord.NotFound, discord.HTTPException):
            new_msg = await channel.send(game.render())
            messages[user_id] = new_msg
            await add_game_reactions(new_msg)
    else:
        new_msg = await channel.send(game.render())
        messages[user_id] = new_msg
        await add_game_reactions(new_msg)

    # clear reactions if game is over
    if game and game.game_over and msg:
        try:
            await msg.clear_reactions()
        except (discord.NotFound, discord.Forbidden):
            pass

    # save score to log if game is over and not already saved
    if game and game.game_over and game.score > 0:
        # prevent duplicate log entries for the same game over
        if not hasattr(game, "_logged") or not game._logged:
            # get user information from context or message
            user = None
            if hasattr(ctx_or_msg, 'author'):
                user = ctx_or_msg.author
            elif hasattr(ctx_or_msg, 'channel'):
                # try to get user from bot cache or guilds
                user = bot.get_user(user_id)
                if not user:
                    for guild in bot.guilds:
                        user = guild.get_member(user_id)
                        if user:
                            break

            if user:
                username = getattr(user, "display_name", str(user))
                avatar_url = str(user.avatar.url) if user.avatar else ""
                save_score(
                    username,
                    game.score,
                    avatar_url,
                    user_id,
                    game.lines_cleared_total,
                    game.get_game_time()
                )
                game._logged = True


@bot.event
async def on_ready():
    print(f"{bot.user}")
    print("------")


@bot.command()
async def tris(ctx):
    user_id = ctx.author.id

    # log final score if previous game existed and was completed
    if user_id in games and games[user_id].game_over and games[user_id].score > 0:
        if not hasattr(games[user_id], "_logged") or not games[user_id]._logged:
            save_score(
                ctx.author.display_name,
                games[user_id].score,
                str(ctx.author.avatar.url) if ctx.author.avatar else "",
                user_id,
                games[user_id].lines_cleared_total,
                games[user_id].get_game_time()
            )
            games[user_id]._logged = True

    # clean up any existing game for this user
    await cleanup_user_game(user_id)

    # start new game instance for this specific user
    games[user_id] = TetrisGame()
    await update_display(ctx, user_id)

    # start auto-drop task for this user only
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
    """Display top 10 high scores with detailed statistics"""
    scores = get_highscores(10)

    if not scores:
        await ctx.send("No high scores yet")
        return

    embed = discord.Embed(
        title="🏆 Tris High Scores & Statistics",
        color=0xffd700
    )

    for i, score_entry in enumerate(scores):
        rank = i + 1
        username = score_entry["username"]
        score_val = score_entry["score"]
        date = datetime.fromisoformat(
            score_entry["timestamp"]).strftime("%m/%d")
        avatar_url = score_entry.get("avatar_url", "")

        # get statistics
        games_played = score_entry.get("games_played", 1)
        total_lines = score_entry.get("total_lines", 0)
        total_time = score_entry.get("total_time", 0)
        best_lines = score_entry.get("best_lines", 0)
        best_time = score_entry.get("best_time", 0)

        # get best achievement dates
        best_lines_date = ""
        best_time_date = ""
        if "best_lines_timestamp" in score_entry:
            best_lines_date = f" ({datetime.fromisoformat(score_entry['best_lines_timestamp']).strftime('%m/%d')})"
        if "best_time_timestamp" in score_entry:
            best_time_date = f" ({datetime.fromisoformat(score_entry['best_time_timestamp']).strftime('%m/%d')})"

        # calculate averages
        avg_score = score_val / games_played if games_played > 0 else 0
        avg_lines = total_lines / games_played if games_played > 0 else 0
        avg_time = total_time / games_played if games_played > 0 else 0

        # use avatar as thumbnail for first place
        if i == 0 and avatar_url:
            embed.set_thumbnail(url=avatar_url)

        # format statistics with individual best dates
        stats_text = (
            f"**Best Score:** {score_val:,} pts ({date})\n"
            f"**Games:** {games_played} | **Avg Score:** {avg_score:,.0f}\n"
            f"**Best Lines:** {best_lines}{best_lines_date} | **Total:** {total_lines:,} | **Avg:** {avg_lines:.1f}\n"
            f"**Longest game:** {best_time:.1f}s{best_time_date} | **Avg Time:** {avg_time:.1f}s"
        )

        medal = "🥇" if rank == 1 else "🥈" if rank == 2 else "🥉" if rank == 3 else f"{rank}."
        embed.add_field(
            name=f"{medal} {username}",
            value=stats_text,
            inline=False
        )

    embed.set_footer(text=">w<")
    await ctx.send(embed=embed)


@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    if message.content.startswith("!"):
        commands_str = message.content[1:].lower()
        valid_commands = {'a', 'd', 's', 'w', 'q'}

        # handle compound commands - affects only the sender's game
        if all(c in valid_commands for c in commands_str):
            user_id = message.author.id  # controls only for the user's game
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
                        # ensure score is logged immediately when user quits
                        if game.score > 0 and (not hasattr(game, "_logged") or not game._logged):
                            save_score(
                                message.author.display_name,
                                game.score,
                                str(message.author.avatar.url) if message.author.avatar else "",
                                user_id,
                                game.lines_cleared_total,
                                game.get_game_time()
                            )
                            game._logged = True
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

        # clean up command messages
        if commands_str in ['tris', 'a', 'd', 's', 'w', 'q', 'trishelp', 'highscores']:
            try:
                await message.delete()
            except discord.Forbidden:
                pass

    await bot.process_commands(message)


@bot.event
async def on_reaction_add(reaction, user):
    """Handle reaction-based game controls"""
    if user.bot:
        return

    # check if this is a game message
    user_id = user.id
    if user_id not in messages or messages[user_id].id != reaction.message.id:
        return

    # check if user has an active game
    game = games.get(user_id)
    if not game or game.game_over:
        return

    # get the command from reaction
    emoji = str(reaction.emoji)
    if emoji not in REACTION_CONTROLS:
        return

    command = REACTION_CONTROLS[emoji]

    # store state before action
    prev_state = (game.px, game.py, [row[:] for row in game.piece], [
                  row[:] for row in game.board], game.score)

    # execute
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
        # ensure score is logged immediately when user quits via reaction
        if game.score > 0 and (not hasattr(game, "_logged") or not game._logged):
            save_score(
                user.display_name,
                game.score,
                str(user.avatar.url) if user.avatar else "",
                user_id,
                game.lines_cleared_total,
                game.get_game_time()
            )
            game._logged = True

    # check if state changed
    new_state = (game.px, game.py, [row[:] for row in game.piece], [
                 row[:] for row in game.board], game.score)

    if prev_state != new_state or game.game_over:
        await update_display(reaction.message, user_id)

    # remove the reaction for cleaner UI
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
