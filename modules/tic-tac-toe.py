import discord
from discord.ext import commands
import asyncio
import random

class TicTacToeAI:
    def __init__(self):
        self.best_move = None

    def minimax(self, board, depth, is_maximizing, player, opponent):
        score = self.evaluate(board, player, opponent)
        if score == 10:
            return score - depth
        if score == -10:
            return score + depth
        if not any(' ' in row for row in board):
            return 0
        if is_maximizing:
            best = -1000
            for i in range(3):
                for j in range(3):
                    if board[i][j] == ' ':
                        board[i][j] = player
                        value = self.minimax(board, depth + 1, not is_maximizing, player, opponent)
                        board[i][j] = ' '
                        if value > best:
                            best = value
                            if depth == 0:
                                self.best_move = (i, j)
            return best
        else:
            best = 1000
            for i in range(3):
                for j in range(3):
                    if board[i][j] == ' ':
                        board[i][j] = opponent
                        value = self.minimax(board, depth + 1, not is_maximizing, player, opponent)
                        board[i][j] = ' '
                        if value < best:
                            best = value
                            if depth == 0:
                                self.best_move = (i, j)
            return best

    def evaluate(self, b, player, opponent):
        for row in range(3):
            if b[row][0] == b[row][1] == b[row][2]:
                if b[row][0] == player:
                    return 10
                elif b[row][0] == opponent:
                    return -10
        for col in range(3):
            if b[0][col] == b[1][col] == b[2][col]:
                if b[0][col] == player:
                    return 10
                elif b[0][col] == opponent:
                    return -10
        if b[0][0] == b[1][1] == b[2][2] or b[0][2] == b[1][1] == b[2][0]:
            if b[1][1] == player:
                return 10
            elif b[1][1] == opponent:
                return -10
        return 0

    def find_best_move(self, board, player, opponent):
        self.minimax(board, 0, True, player, opponent)
        return self.best_move if self.best_move else (random.randint(0, 2), random.randint(0, 2))

class TicTacToe:
    def __init__(self, player_x, player_o, message):
        self.board = [[" " for _ in range(3)] for _ in range(3)]
        self.player_x = player_x
        self.player_o = player_o
        self.current_turn = player_x
        self.game_over = False
        self.winner = None
        self.message = message
        self.ai = TicTacToeAI() if player_o.bot else None
        self.message_sent = False

    def get_board_str(self):
        board_str = "```\n"
        for i in range(3):
            for j in range(3):
                cell = self.board[i][j]
                board_str += f"{cell if cell != ' ' else i * 3 + j + 1} "
                if j < 2:
                    board_str += "|"
            if i < 2:
                board_str += "\n---------\n"
        board_str += "\n```"
        return board_str

    def make_move(self, player, move):
        if player != self.current_turn or self.game_over:
            return False, "It's not your turn or the game is already over."
        row, col = divmod(move - 1, 3)
        if self.board[row][col] != " ":
            return False, "Invalid move, the cell is already occupied."
        self.board[row][col] = 'X' if player == self.player_x else 'O'
        if self.check_winner(player, row, col):
            self.game_over = True
            self.winner = player
            return True, f"Game Over! {player.mention} wins!"
        elif all(self.board[i][j] != ' ' for i in range(3) for j in range(3)):
            self.game_over = True
            return True, "Game Over! It's a draw!"
        self.current_turn = self.player_o if self.current_turn == self.player_x else self.player_x
        next_player_mention = self.player_o.mention if self.current_turn == self.player_o else self.player_x.mention
        return True, f"{self.get_board_str()}\n{next_player_mention}, it's your turn!"

    def check_winner(self, player, row, col):
        if all(self.board[row][i] == self.board[row][col] for i in range(3)):
            return True
        if all(self.board[i][col] == self.board[row][col] for i in range(3)):
            return True
        if row == col and all(self.board[i][i] == self.board[row][col] for i in range(3)):
            return True
        if row + col == 2 and all(self.board[i][2-i] == self.board[row][col] for i in range(3)):
            return True
        return False

games = {}

@commands.command(name='ttt_start')
async def start_game(ctx, player_x: discord.Member, player_o: discord.Member):
    initial_board = "```\n1 | 2 | 3\n---+---+---\n4 | 5 | 6\n---+---+---\n7 | 8 | 9\n```"
    message = await ctx.send(f"{player_x.mention} (X) vs {player_o.mention} (O)\n{initial_board}\nReact with the number you want to place your mark on!")
    for emoji in ('1️⃣', '2️⃣', '3️⃣', '4️⃣', '5️⃣', '6️⃣', '7️⃣', '8️⃣', '9️⃣'):
        await message.add_reaction(emoji)
    game = TicTacToe(player_x, player_o, message)
    games[message.id] = game
    asyncio.create_task(game_timeout(ctx, message.id, 3600))

async def game_timeout(ctx, message_id, timeout):
    await asyncio.sleep(timeout)
    game = games.get(message_id)
    if game and not game.game_over:
        await ctx.send(f"Game timed out! {game.player_x.mention} vs {game.player_o.mention}")
        del games[message_id]

async def on_reaction_add(reaction, user):
    message_id = reaction.message.id
    game = games.get(message_id)
    if not game or game.game_over or user == reaction.message.author.bot:
        return
    emoji_to_num = {
        '1️⃣': 1, '2️⃣': 2, '3️⃣': 3,
        '4️⃣': 4, '5️⃣': 5, '6️⃣': 6,
        '7️⃣': 7, '8️⃣': 8, '9️⃣': 9
    }
    move = emoji_to_num.get(str(reaction.emoji))
    if move is None or user.id not in [game.player_x.id, game.player_o.id]:
        return
    result, response = game.make_move(user, move)
    if result:
        await reaction.message.edit(content=f"{game.player_x.mention} (X) vs {game.player_o.mention} (O)\n{response}")
        if game.game_over and not game.message_sent:
            await reaction.message.channel.send(f"Game Over!\n{response}")
            game.message_sent = True
            del games[message_id]
        else:
            # If it's AI's turn and the game is not over, let the AI make a move.
            if game.current_turn.bot and not game.game_over:
                row, col = game.ai.find_best_move(game.board, 'O', 'X')
                result, response = game.make_move(game.current_turn, row * 3 + col + 1)
                if result:
                    await reaction.message.edit(content=f"{game.player_x.mention} (X) vs {game.player_o.mention} (O)\n{response}")
                    if game.game_over and not game.message_sent:
                        await reaction.message.channel.send(f"Game Over!\n{response}")
                        game.message_sent = True
                        del games[message_id]

def setup(client):
    client.add_command(start_game)
    client.add_listener(on_reaction_add, 'on_reaction_add')