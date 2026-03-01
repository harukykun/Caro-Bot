import discord
from discord.ext import commands
from discord import app_commands
import random
import asyncio
import os
import json

CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "caro_config.json")
_config_cache = {}
_config_mtime = 0

def load_config():
    global _config_cache, _config_mtime
    try:
        mt = os.path.getmtime(CONFIG_PATH)
    except OSError:
        return _config_cache
    if mt != _config_mtime:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            _config_cache = json.load(f)
        _config_mtime = mt
    return _config_cache

def cfg(key):
    return load_config()[key]

EMPTY = 0
PLAYER_X = 1
PLAYER_O = 2


class CaroGame:
    def __init__(self, player_x, player_o, is_pvp=True):
        self.board = [[EMPTY] * cfg("board_size") for _ in range(cfg("board_size"))]
        self.player_x = player_x
        self.player_o = player_o
        self.is_pvp = is_pvp
        self.current_turn = PLAYER_X
        self.history_x = []
        self.history_o = []
        self.finished = False
        self.game_channel = None
        self.announce_message = None
        self.winner = None

    def current_player(self):
        return self.player_x if self.current_turn == PLAYER_X else self.player_o

    def get_history(self, player):
        return self.history_x if player == PLAYER_X else self.history_o

    def place(self, row, col):
        if self.board[row][col] != EMPTY:
            return False
        history = self.get_history(self.current_turn)
        if len(history) >= cfg("max_pieces"):
            old_r, old_c = history.pop(0)
            self.board[old_r][old_c] = EMPTY
        self.board[row][col] = self.current_turn
        history.append((row, col))
        if self.check_win(self.current_turn):
            self.finished = True
            self.winner = self.current_turn
        else:
            self.current_turn = PLAYER_O if self.current_turn == PLAYER_X else PLAYER_X
        return True

    def check_win(self, player):
        b = self.board
        size = cfg("board_size")
        for i in range(size):
            if all(b[i][c] == player for c in range(size)):
                return True
            if all(b[r][i] == player for r in range(size)):
                return True
        if all(b[i][i] == player for i in range(size)):
            return True
        if all(b[i][size - 1 - i] == player for i in range(size)):
            return True
        return False

    def ai_move(self):
        config = load_config()
        size = config["board_size"]
        if config["bot_mistake_enabled"] and random.randint(1, 100) <= config["bot_mistake_chance"]:
            empty_cells = [
                (r, c)
                for r in range(size)
                for c in range(size)
                if self.board[r][c] == EMPTY
            ]
            if empty_cells:
                return random.choice(empty_cells)

        best_score = float('-inf')
        best_move = None
        alpha = float('-inf')
        beta = float('inf')
        for r in range(size):
            for c in range(size):
                if self.board[r][c] == EMPTY:
                    removed = None
                    if len(self.history_o) >= config["max_pieces"]:
                        old_r, old_c = self.history_o[0]
                        removed = (old_r, old_c)
                        self.board[old_r][old_c] = EMPTY
                        self.history_o.pop(0)
                    self.board[r][c] = PLAYER_O
                    self.history_o.append((r, c))
                    score = self.minimax(False, config["minimax_depth"], alpha, beta)
                    self.history_o.pop()
                    self.board[r][c] = EMPTY
                    if removed:
                        self.board[removed[0]][removed[1]] = PLAYER_O
                        self.history_o.insert(0, removed)
                    if score > best_score:
                        best_score = score
                        best_move = (r, c)
                    alpha = max(alpha, best_score)
        return best_move

    def minimax(self, is_ai_turn, depth, alpha, beta):
        md = cfg("minimax_depth")
        if self.check_win(PLAYER_O):
            return 10 - (md + 3 - depth)
        if self.check_win(PLAYER_X):
            return -10 + (md + 3 - depth)
        if depth <= 0:
            return self.evaluate()

        player = PLAYER_O if is_ai_turn else PLAYER_X
        history = self.get_history(player)

        size = cfg("board_size")
        mp = cfg("max_pieces")
        if is_ai_turn:
            best = float('-inf')
            for r in range(size):
                for c in range(size):
                    if self.board[r][c] == EMPTY:
                        removed = None
                        if len(history) >= mp:
                            old_r, old_c = history[0]
                            removed = (old_r, old_c)
                            self.board[old_r][old_c] = EMPTY
                            history.pop(0)
                        self.board[r][c] = player
                        history.append((r, c))
                        best = max(best, self.minimax(False, depth - 1, alpha, beta))
                        history.pop()
                        self.board[r][c] = EMPTY
                        if removed:
                            self.board[removed[0]][removed[1]] = player
                            history.insert(0, removed)
                        alpha = max(alpha, best)
                        if beta <= alpha:
                            return best
            return best
        else:
            best = float('inf')
            for r in range(size):
                for c in range(size):
                    if self.board[r][c] == EMPTY:
                        removed = None
                        if len(history) >= mp:
                            old_r, old_c = history[0]
                            removed = (old_r, old_c)
                            self.board[old_r][old_c] = EMPTY
                            history.pop(0)
                        self.board[r][c] = player
                        history.append((r, c))
                        best = min(best, self.minimax(True, depth - 1, alpha, beta))
                        history.pop()
                        self.board[r][c] = EMPTY
                        if removed:
                            self.board[removed[0]][removed[1]] = player
                            history.insert(0, removed)
                        beta = min(beta, best)
                        if beta <= alpha:
                            return best
            return best

    def evaluate(self):
        lines = []
        size = cfg("board_size")
        for i in range(size):
            lines.append([(i, c) for c in range(size)])
            lines.append([(r, i) for r in range(size)])
        lines.append([(i, i) for i in range(size)])
        lines.append([(i, size - 1 - i) for i in range(size)])

        score = 0
        for line in lines:
            values = [self.board[r][c] for r, c in line]
            ai_count = values.count(PLAYER_O)
            player_count = values.count(PLAYER_X)
            if ai_count > 0 and player_count == 0:
                score += ai_count
            elif player_count > 0 and ai_count == 0:
                score -= player_count
        return score


class BoardView(discord.ui.View):
    def __init__(self, game, cog, game_key):
        super().__init__(timeout=cfg("game_timeout"))
        self.game = game
        self.cog = cog
        self.game_key = game_key
        self.build_buttons()

    def build_buttons(self):
        self.clear_items()
        will_remove_x = None
        will_remove_o = None
        if not self.game.finished:
            turn = self.game.current_turn
            history = self.game.get_history(turn)
            if len(history) >= cfg("max_pieces"):
                if turn == PLAYER_X:
                    will_remove_x = history[0]
                else:
                    will_remove_o = history[0]
        for r in range(cfg("board_size")):
            for c in range(cfg("board_size")):
                val = self.game.board[r][c]
                if val == PLAYER_X:
                    if will_remove_x == (r, c):
                        label = "❌"
                        style = discord.ButtonStyle.red
                    else:
                        label = "❌"
                        style = discord.ButtonStyle.red
                    disabled = True
                elif val == PLAYER_O:
                    if will_remove_o == (r, c):
                        label = "⭕"
                        style = discord.ButtonStyle.blurple
                    else:
                        label = "⭕"
                        style = discord.ButtonStyle.blurple
                    disabled = True
                else:
                    label = "⠀"
                    style = discord.ButtonStyle.secondary
                    disabled = self.game.finished
                button = discord.ui.Button(
                    label=label,
                    style=style,
                    disabled=disabled,
                    row=r,
                    custom_id=f"caro_{self.game_key}_{r}_{c}"
                )
                button.callback = self.make_callback(r, c)
                self.add_item(button)

    def make_callback(self, row, col):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.game.current_player().id:
                await interaction.response.send_message("Chưa đến lượt bạn!", ephemeral=True)
                return

            self.game.place(row, col)
            self.build_buttons()
            embed = self.cog.make_embed(self.game)
            await interaction.response.edit_message(embed=embed, view=self)

            if not self.game.finished and not self.game.is_pvp and self.game.current_turn == PLAYER_O:
                delay = cfg("bot_move_delay")
                if delay > 0:
                    await asyncio.sleep(delay)
                ai_pos = self.game.ai_move()
                if ai_pos:
                    self.game.place(ai_pos[0], ai_pos[1])
                self.build_buttons()
                embed = self.cog.make_embed(self.game)
                await interaction.message.edit(embed=embed, view=self)

            if self.game.finished:
                if self.game.game_channel:
                    if self.game.announce_message:
                        result_embed = self.cog.make_embed(self.game)
                        try:
                            await self.game.announce_message.edit(embed=result_embed)
                        except discord.NotFound:
                            pass
                    await asyncio.sleep(cfg("channel_delete_delay"))
                    try:
                        await self.game.game_channel.delete()
                    except discord.NotFound:
                        pass
                self.cog.games.pop(self.game_key, None)

        return callback

    async def on_timeout(self):
        self.game.finished = True
        for item in self.children:
            item.disabled = True


class ChallengeView(discord.ui.View):
    def __init__(self, challenger, challenged, cog):
        super().__init__(timeout=cfg("challenge_timeout"))
        self.challenger = challenger
        self.challenged = challenged
        self.cog = cog

    @discord.ui.button(label="Chấp nhận", style=discord.ButtonStyle.green, emoji="✅")
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.challenged.id:
            await interaction.response.send_message("Không phải lượt của bạn!", ephemeral=True)
            return

        self.stop()
        await interaction.response.edit_message(
            embed=discord.Embed(title="Đang tạo phòng đấu...", color=discord.Color.blue()),
            view=None
        )

        guild = interaction.guild
        category = None
        if cfg("category_id"):
            category = guild.get_channel(int(cfg("category_id")))
        if not category:
            category = await guild.create_category("Tic-Tac-Toe")

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=True, send_messages=False),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True),
            self.challenger: discord.PermissionOverwrite(view_channel=True, send_messages=True),
            self.challenged: discord.PermissionOverwrite(view_channel=True, send_messages=True),
        }
        channel_name = f"{self.challenger.display_name}-vs-{self.challenged.display_name}"
        game_channel = await category.create_text_channel(channel_name, overwrites=overwrites)

        game = CaroGame(self.challenged, self.challenger, is_pvp=True)
        game.game_channel = game_channel
        key = game_channel.id
        self.cog.games[key] = game

        board_view = BoardView(game, self.cog, key)
        embed = self.cog.make_embed(game)
        await game_channel.send(embed=embed, view=board_view)

        announce_msg = await interaction.followup.send(
            embed=discord.Embed(
                title="Phòng đấu đã tạo!",
                description=f"Vào {game_channel.mention} để thi đấu!",
                color=discord.Color.green()
            )
        )
        game.announce_message = announce_msg

    @discord.ui.button(label="Từ chối", style=discord.ButtonStyle.red, emoji="❌")
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.challenged.id:
            await interaction.response.send_message("Không phải lượt của bạn!", ephemeral=True)
            return

        self.stop()
        embed = discord.Embed(
            title="❌ Thách đấu bị từ chối",
            description=f"{self.challenged.mention} đã từ chối lời thách đấu.",
            color=discord.Color.red()
        )
        await interaction.response.edit_message(embed=embed, view=None)


class CaroCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.games = {}

    def make_embed(self, game):
        if game.finished:
            if game.winner:
                winner = game.player_x if game.winner == PLAYER_X else game.player_o
                winner_emoji = "❌" if game.winner == PLAYER_X else "⭕"
                winner_name = "AI" if winner.bot else winner.mention
                return discord.Embed(
                    title="Trận đấu kết thúc!",
                    description=f"Người thắng: {winner_name} ({winner_emoji})",
                    color=discord.Color.gold()
                )
            return discord.Embed(
                title="Hòa!",
                description="Không ai thắng!",
                color=discord.Color.greyple()
            )

        player_emoji = "❌" if game.current_turn == PLAYER_X else "⭕"
        current = game.current_player()
        current_name = "AI" if current.bot else current.mention
        return discord.Embed(
            title="🎮 Tic-Tac-Toe",
            description=f"Lượt: {current_name} ({player_emoji})",
            color=discord.Color.green() if not game.is_pvp else discord.Color.gold()
        )

    caro_group = app_commands.Group(name="caro", description="Chơi Tic-Tac-Toe")

    @caro_group.command(name="pvp", description="Thách đấu với người chơi khác")
    @app_commands.describe(opponent="Người chơi bạn muốn thách đấu")
    async def caro_pvp(self, interaction: discord.Interaction, opponent: discord.Member):
        if opponent.bot:
            await interaction.response.send_message("❌ Không thể thách đấu bot!", ephemeral=True)
            return
        if opponent.id == interaction.user.id:
            await interaction.response.send_message("❌ Không thể tự thách đấu!", ephemeral=True)
            return

        key = interaction.channel_id
        if key in self.games and not self.games[key].finished:
            await interaction.response.send_message("❌ Kênh này đang có trận đấu!", ephemeral=True)
            return

        view = ChallengeView(interaction.user, opponent, self)
        embed = discord.Embed(
            title="⚔️ Thách đấu Tic-Tac-Toe!",
            description=f"{interaction.user.mention} thách đấu {opponent.mention}!\n\n"
                        f"{opponent.mention}, bạn có chấp nhận không?",
            color=discord.Color.blue()
        )
        await interaction.response.send_message(embed=embed, view=view)

    @caro_group.command(name="bot", description="Chơi với AI")
    async def caro_bot(self, interaction: discord.Interaction):
        key = f"bot_{interaction.user.id}"
        if key in self.games and not self.games[key].finished:
            await interaction.response.send_message("❌ Bạn đang có trận đấu với bot!", ephemeral=True)
            return

        game = CaroGame(interaction.user, self.bot.user, is_pvp=False)
        bot_first = cfg("bot_goes_first")
        if bot_first == "random":
            bot_first = random.choice([True, False])
        if bot_first:
            game.current_turn = PLAYER_O
            r, c = random.randint(0, cfg("board_size") - 1), random.randint(0, cfg("board_size") - 1)
            game.place(r, c)
        self.games[key] = game

        board_view = BoardView(game, self, key)
        embed = self.make_embed(game)
        await interaction.response.send_message(embed=embed, view=board_view)

    @caro_group.command(name="reset", description="Hủy trận đấu hiện tại")
    async def caro_reset(self, interaction: discord.Interaction):
        key = interaction.channel_id
        game = self.games.get(key)
        if not game:
            await interaction.response.send_message("Không có trận đấu nào!", ephemeral=True)
            return

        game_channel = game.game_channel
        del self.games[key]

        if game_channel and game_channel.id == interaction.channel_id:
            await interaction.response.send_message("Trận đấu đã bị hủy. Xóa phòng trong 5s...")
            await asyncio.sleep(cfg("channel_reset_delay"))
            try:
                await game_channel.delete()
            except discord.NotFound:
                pass
        else:
            embed = discord.Embed(
                title="Trận đấu đã bị hủy",
                description=f"{interaction.user.mention} đã hủy trận đấu.",
                color=discord.Color.greyple()
            )
            await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(CaroCog(bot))
