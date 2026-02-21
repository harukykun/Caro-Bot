import discord
from discord.ext import commands
from discord import app_commands
import random
import asyncio
import os

EMPTY = 0
PLAYER_X = 1
PLAYER_O = 2

EMOJI_EMPTY = "⬜"
EMOJI_X = "❌"
EMOJI_O = "⭕"


MAX_PIECES = 3
CATEGORY_ID = 1474844901882466475
BOT_GOES_FIRST = True


class CaroGame:
    def __init__(self, player_x, player_o, is_pvp=True):
        self.board = [[EMPTY] * 3 for _ in range(3)]
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
        if len(history) >= MAX_PIECES:
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
        for i in range(3):
            if b[i][0] == b[i][1] == b[i][2] == player:
                return True
            if b[0][i] == b[1][i] == b[2][i] == player:
                return True
        if b[0][0] == b[1][1] == b[2][2] == player:
            return True
        if b[0][2] == b[1][1] == b[2][0] == player:
            return True
        return False

    def ai_move(self):
        best_score = float('-inf')
        best_move = None
        alpha = float('-inf')
        beta = float('inf')
        for r in range(3):
            for c in range(3):
                if self.board[r][c] == EMPTY:
                    removed = None
                    if len(self.history_o) >= MAX_PIECES:
                        old_r, old_c = self.history_o[0]
                        removed = (old_r, old_c)
                        self.board[old_r][old_c] = EMPTY
                        self.history_o.pop(0)
                    self.board[r][c] = PLAYER_O
                    self.history_o.append((r, c))
                    score = self.minimax(False, 9, alpha, beta)
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
        if self.check_win(PLAYER_O):
            return 10 - (9 - depth)
        if self.check_win(PLAYER_X):
            return -10 + (9 - depth)
        if depth <= 0:
            return self.evaluate()

        player = PLAYER_O if is_ai_turn else PLAYER_X
        history = self.get_history(player)

        if is_ai_turn:
            best = float('-inf')
            for r in range(3):
                for c in range(3):
                    if self.board[r][c] == EMPTY:
                        removed = None
                        if len(history) >= MAX_PIECES:
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
            for r in range(3):
                for c in range(3):
                    if self.board[r][c] == EMPTY:
                        removed = None
                        if len(history) >= MAX_PIECES:
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
        for i in range(3):
            lines.append([(i, 0), (i, 1), (i, 2)])
            lines.append([(0, i), (1, i), (2, i)])
        lines.append([(0, 0), (1, 1), (2, 2)])
        lines.append([(0, 2), (1, 1), (2, 0)])

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
        super().__init__(timeout=300)
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
            if len(history) >= MAX_PIECES:
                if turn == PLAYER_X:
                    will_remove_x = history[0]
                else:
                    will_remove_o = history[0]
        for r in range(3):
            for c in range(3):
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

            if not self.game.finished and not self.game.is_pvp and self.game.current_turn == PLAYER_O:
                ai_pos = self.game.ai_move()
                if ai_pos:
                    self.game.place(ai_pos[0], ai_pos[1])

            self.build_buttons()
            embed = self.cog.make_embed(self.game)
            await interaction.response.edit_message(embed=embed, view=self)

            if self.game.finished:
                if self.game.game_channel:
                    if self.game.announce_message:
                        result_embed = self.cog.make_embed(self.game)
                        try:
                            await self.game.announce_message.edit(embed=result_embed)
                        except discord.NotFound:
                            pass
                    await asyncio.sleep(10)
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
        super().__init__(timeout=60)
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
        if CATEGORY_ID:
            category = guild.get_channel(int(CATEGORY_ID))
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
        if BOT_GOES_FIRST:
            ai_pos = game.ai_move()
            if ai_pos:
                game.place(ai_pos[0], ai_pos[1])
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
            await asyncio.sleep(5)
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
