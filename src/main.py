import tkinter as tk
from tkinter import messagebox
import time

BSIZE = 8
EMPTY = 0
BLACK = 1
WHITE = 2
DIRS = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]
board = [[EMPTY] * BSIZE for _ in range(BSIZE)]
current_player = BLACK
game_over = False
ai_thinking = False
move_count = 0
move_history = []

_search_deadline = 0
SEARCH_TIME = 2.0
NODES_SEARCHED = 0

# ========== 开局库 ==========
OPENING_BOOK = {
    0: [(2, 3), (3, 2), (4, 5), (5, 4)],
    1: [(2, 2), (2, 4), (3, 5), (4, 2), (5, 3), (5, 5)],
    2: [(2, 3), (3, 2), (4, 5), (5, 4)],
}

# ========== 基础函数 ==========
def opponent(p):
    return 3 - p


def count_pieces(p):
    return sum(row.count(p) for row in board)


def copy_board(b):
    return [row[:] for row in b]


def set_timeout(ms):
    global _search_deadline
    _search_deadline = time.time() + ms / 1000.0


def time_exceeded():
    return time.time() > _search_deadline


# ========== 棋盘逻辑 ==========
def init():
    global board, current_player, game_over, move_count, move_history
    board = [[EMPTY] * BSIZE for _ in range(BSIZE)]
    board[3][3] = WHITE
    board[4][4] = WHITE
    board[3][4] = BLACK
    board[4][3] = BLACK
    current_player = BLACK
    game_over = False
    move_count = 0
    move_history = []


def get_valid_moves(p):
    opp = opponent(p)
    moves = []
    for i in range(BSIZE):
        for j in range(BSIZE):
            if board[i][j] != EMPTY:
                continue
            for dx, dy in DIRS:
                x, y = i + dx, j + dy
                found_opp = False
                while 0 <= x < BSIZE and 0 <= y < BSIZE and board[x][y] == opp:
                    found_opp = True
                    x += dx
                    y += dy
                if found_opp and 0 <= x < BSIZE and 0 <= y < BSIZE and board[x][y] == p:
                    moves.append((i, j))
                    break
    return moves


def has_valid_moves(p):
    return len(get_valid_moves(p)) > 0


def apply_move(x, y, p):
    opp = opponent(p)
    board[x][y] = p
    for dx, dy in DIRS:
        nx, ny = x + dx, y + dy
        flip = []
        while 0 <= nx < BSIZE and 0 <= ny < BSIZE and board[nx][ny] == opp:
            flip.append((nx, ny))
            nx += dx
            ny += dy
        if 0 <= nx < BSIZE and 0 <= ny < BSIZE and board[nx][ny] == p:
            for fx, fy in flip:
                board[fx][fy] = p


def make_move(x, y):
    global current_player, game_over, move_count, move_history
    move_history.append({
        'x': x, 'y': y,
        'player': current_player,
        'board': copy_board(board)
    })
    apply_move(x, y, current_player)
    move_count += 1
    current_player = opponent(current_player)
    if not has_valid_moves(current_player):
        current_player = opponent(current_player)
        if not has_valid_moves(current_player):
            game_over = True
        else:
            current_player = opponent(current_player)


def undo_move():
    global current_player, game_over, move_count, move_history, board
    if not move_history or ai_thinking:
        return False
    if game_over:
        game_over = False
    last = move_history.pop()
    board = last['board']
    current_player = last['player']
    move_count -= 1
    if current_player == WHITE and move_history:
        last = move_history.pop()
        board = last['board']
        current_player = last['player']
        move_count -= 1
    return True


# ========== 评估函数==========

def get_stable_count(p):
    """计算稳定子（从角扩散）"""
    stable = [[False] * BSIZE for _ in range(BSIZE)]
    corners = [(0, 0), (0, 7), (7, 0), (7, 7)]

    for cx, cy in corners:
        if board[cx][cy] == p:
            # 三个方向扩散
            for dx, dy in [(0, 1), (1, 0), (1, 1)]:
                x, y = cx, cy
                while 0 <= x < BSIZE and 0 <= y < BSIZE and board[x][y] == p:
                    stable[x][y] = True
                    x += dx
                    y += dy

    # 四边检查
    for i in range(BSIZE):
        if board[i][0] == p and board[i][7] == p:
            for j in range(BSIZE):
                if board[i][j] == p:
                    stable[i][j] = True
        if board[0][i] == p and board[7][i] == p:
            for j in range(BSIZE):
                if board[j][i] == p:
                    stable[j][i] = True

    return sum(row.count(True) for row in stable)


def get_frontier_count(p):
    """计算边缘棋子（容易被翻转的）"""
    opp = opponent(p)
    frontier = 0
    for i in range(BSIZE):
        for j in range(BSIZE):
            if board[i][j] == p:
                for dx, dy in DIRS:
                    nx, ny = i + dx, j + dy
                    if 0 <= nx < BSIZE and 0 <= ny < BSIZE and board[nx][ny] == EMPTY:
                        frontier += 1
                        break
    return frontier


def get_parity_score(p):
    """奇偶性（影响终局）"""
    empty = sum(row.count(EMPTY) for row in board)
    return 5 if empty % 2 == 0 else -5


def get_corner_control(p):
    """角落周边控制"""
    opp = opponent(p)
    score = 0
    # 角落直接控制
    corners = [(0, 0), (0, 7), (7, 0), (7, 7)]
    for cx, cy in corners:
        if board[cx][cy] == p:
            score += 30
        elif board[cx][cy] == opp:
            score -= 30

    # 角落周边的"X"位置（坏位置）
    bad = [(1, 1), (1, 6), (6, 1), (6, 6)]
    for x, y in bad:
        if board[x][y] == p:
            score -= 20
        elif board[x][y] == opp:
            score += 10

    return score


def evaluate(p):
    """10维度评估函数"""
    global game_over, NODES_SEARCHED
    NODES_SEARCHED += 1

    if game_over:
        b, w = count_pieces(BLACK), count_pieces(WHITE)
        if p == WHITE:
            return 10000 if w > b else (-10000 if w < b else 0)
        else:
            return 10000 if b > w else (-10000 if b < w else 0)

    opp = opponent(p)
    empty = sum(row.count(EMPTY) for row in board)

    # 1. 棋子数量差（终局权重加大）
    my_count = count_pieces(p)
    opp_count = count_pieces(opp)
    count_weight = 15 if empty < 15 else 6
    score = (my_count - opp_count) * count_weight

    # 2. 角落控制
    score += get_corner_control(p) * 2

    # 3. 稳定子
    my_stable = get_stable_count(p)
    opp_stable = get_stable_count(opp)
    score += (my_stable - opp_stable) * 15

    # 4. 移动性
    my_moves = len(get_valid_moves(p))
    opp_moves = len(get_valid_moves(opp))
    score += (my_moves - opp_moves) * 10

    # 5. 边缘棋子（越少越好）
    my_frontier = get_frontier_count(p)
    opp_frontier = get_frontier_count(opp)
    score -= (my_frontier - opp_frontier) * 5

    # 6. 中心控制
    for i in range(BSIZE):
        for j in range(BSIZE):
            if board[i][j] == p:
                dist = abs(i - 3.5) + abs(j - 3.5)
                score += (7 - dist) * 1.5
            elif board[i][j] == opp:
                dist = abs(i - 3.5) + abs(j - 3.5)
                score -= (7 - dist) * 1.5

    # 7. 奇偶性（残局）
    if empty < 20:
        score += get_parity_score(p) * 3

    # 8. 边控制
    for i in range(BSIZE):
        if board[i][0] == p:
            score += 5
        if board[i][7] == p:
            score += 5
        if board[0][i] == p:
            score += 5
        if board[7][i] == p:
            score += 5

    # 9. 潜在翻转数（模拟一步）
    potential_flips = 0
    for x, y in get_valid_moves(p):
        temp = copy_board(board)
        temp[x][y] = p
        for dx, dy in DIRS:
            nx, ny = x + dx, y + dy
            flips = 0
            while 0 <= nx < BSIZE and 0 <= ny < BSIZE and temp[nx][ny] == opp:
                flips += 1
                nx += dx
                ny += dy
            if 0 <= nx < BSIZE and 0 <= ny < BSIZE and temp[nx][ny] == p:
                potential_flips += flips
    score += potential_flips * 0.5

    # 10. 空位分布（避免下在中间）
    for x, y in get_valid_moves(p):
        dist = abs(x - 3.5) + abs(y - 3.5)
        if dist < 2:
            score += 2

    return int(score)


# ========== 走法排序 ==========
def get_sorted_moves(p):
    moves = get_valid_moves(p)
    opp = opponent(p)
    scored = []

    for x, y in moves:
        pr = 0
        # 角：最高优先级
        if x in (0, 7) and y in (0, 7):
            pr += 10000
        # 边：高优先级
        elif x in (0, 7) or y in (0, 7):
            pr += 100
            # 避开坏位置
            if (x == 0 and y in (1, 6)) or (x == 7 and y in (1, 6)) or \
                    (y == 0 and x in (1, 6)) or (y == 7 and x in (1, 6)):
                pr -= 200

        # 中心：中等
        if 2 <= x <= 5 and 2 <= y <= 5:
            pr += 30

        # 模拟走法评价
        temp = copy_board(board)
        temp[x][y] = p
        flips = 0
        for dx, dy in DIRS:
            nx, ny = x + dx, y + dy
            flip = []
            while 0 <= nx < BSIZE and 0 <= ny < BSIZE and temp[nx][ny] == opp:
                flip.append((nx, ny))
                nx += dx
                ny += dy
            if 0 <= nx < BSIZE and 0 <= ny < BSIZE and temp[nx][ny] == p:
                flips += len(flip)
        pr += flips * 5

        # 走法后的移动性
        temp_board = copy_board(board)
        temp_board[x][y] = p
        # 简化：计算翻转后的移动性
        after_moves = 0
        for i in range(BSIZE):
            for j in range(BSIZE):
                if temp_board[i][j] == EMPTY:
                    for dx, dy in DIRS:
                        nx, ny = i + dx, j + dy
                        found = False
                        while 0 <= nx < BSIZE and 0 <= ny < BSIZE and temp_board[nx][ny] == opp:
                            found = True
                            nx += dx
                            ny += dy
                        if found and 0 <= nx < BSIZE and 0 <= ny < BSIZE and temp_board[nx][ny] == p:
                            after_moves += 1
                            break
        pr += after_moves * 2

        scored.append((pr, (x, y)))

    scored.sort(reverse=True)
    return [m for _, m in scored]


# ========== Alpha-Beta搜索 ==========
def alpha_beta(depth, alpha, beta, p, is_max):
    global board, current_player, game_over

    if time_exceeded() or depth == 0 or game_over or not has_valid_moves(p):
        return evaluate(p), None

    moves = get_sorted_moves(p)
    if not moves:
        opp = opponent(p)
        if not has_valid_moves(opp):
            game_over = True
            return evaluate(p), None
        return alpha_beta(depth - 1, alpha, beta, opp, not is_max)

    # 动态截断：走法太多时只搜前N个
    if len(moves) > 15 and depth > 3:
        moves = moves[:15]

    best_move = moves[0]

    if is_max:
        best_val = -999999
        for x, y in moves:
            if time_exceeded():
                break

            saved = copy_board(board)
            saved_player = current_player
            saved_over = game_over

            apply_move(x, y, p)
            current_player = opponent(p)
            if not has_valid_moves(current_player):
                current_player = opponent(current_player)
                if not has_valid_moves(current_player):
                    game_over = True

            val, _ = alpha_beta(depth - 1, alpha, beta, current_player, False)

            board = saved
            current_player = saved_player
            game_over = saved_over

            if val > best_val:
                best_val = val
                best_move = (x, y)
            alpha = max(alpha, val)
            if beta <= alpha:
                break
        return best_val, best_move
    else:
        best_val = 999999
        for x, y in moves:
            if time_exceeded():
                break

            saved = copy_board(board)
            saved_player = current_player
            saved_over = game_over

            apply_move(x, y, p)
            current_player = opponent(p)
            if not has_valid_moves(current_player):
                current_player = opponent(current_player)
                if not has_valid_moves(current_player):
                    game_over = True

            val, _ = alpha_beta(depth - 1, alpha, beta, current_player, True)

            board = saved
            current_player = saved_player
            game_over = saved_over

            if val < best_val:
                best_val = val
                best_move = (x, y)
            beta = min(beta, val)
            if beta <= alpha:
                break
        return best_val, best_move


# ========== AI决策 ==========
def ai_move():
    global ai_thinking, current_player, game_over, NODES_SEARCHED

    if ai_thinking or game_over or current_player != WHITE:
        return
    if not has_valid_moves(WHITE):
        current_player = BLACK
        if not has_valid_moves(BLACK):
            game_over = True
        return

    ai_thinking = True
    NODES_SEARCHED = 0

    empty = sum(row.count(EMPTY) for row in board)

    # 动态深度
    if empty > 50:
        depth = 6
    elif empty > 40:
        depth = 7
    elif empty > 30:
        depth = 8
    elif empty > 15:
        depth = 9
    else:
        depth = 10  # 残局精确搜索

    # 动态时间分配
    if empty < 10:
        set_timeout(3000)  # 残局给3秒
    elif empty < 20:
        set_timeout(2000)
    else:
        set_timeout(1500)

    # 尝试走角（如果有）
    moves = get_valid_moves(WHITE)
    for x, y in moves:
        if x in (0, 7) and y in (0, 7):
            make_move(x, y)
            ai_thinking = False
            return

    # 正常搜索
    try:
        _, move = alpha_beta(depth, -999999, 999999, WHITE, True)
    except Exception as e:
        move = None

    if move:
        make_move(move[0], move[1])
    else:
        # 备用：选翻转最多的
        moves = get_valid_moves(WHITE)
        if moves:
            best = moves[0]
            best_score = -999
            for x, y in moves:
                temp = copy_board(board)
                temp[x][y] = WHITE
                score = temp.count(WHITE)
                # 角优先
                if x in (0, 7) and y in (0, 7):
                    score += 100
                if score > best_score:
                    best_score = score
                    best = (x, y)
            make_move(best[0], best[1])

    ai_thinking = False


# ========== GUI ==========
class OthelloGUI:
    def __init__(self, root):
        self.root = root
        root.title("黑白棋 - 加强版AI")
        root.geometry("780x620")
        root.resizable(False, False)
        root.configure(bg='#1a2a1a')

        self.colors = {
            'bg': '#1a2a1a',
            'board_bg': '#2d7d3a',
            'grid': '#1a5a2a',
            'panel_bg': '#1e2a1e',
            'text': '#e8dcc8',
            'highlight': '#ffd700',
            'green': '#00cc44',
            'button_bg': '#3a5a3a',
            'button_hover': '#4a7a4a',
            'button_text': '#e8dcc8'
        }

        self.cell = 60
        self.left = 40
        self.top = 40
        self.info_x = 560

        self.canvas = tk.Canvas(root, width=740, height=580, bg=self.colors['board_bg'],
                                highlightthickness=2, highlightbackground='#2a4a2a')
        self.canvas.place(x=20, y=20)
        self.canvas.bind("<Button-1>", self.on_click)

        self.create_buttons()

        self.status_var = tk.StringVar()
        self.status_var.set("黑棋走")
        self.status_label = tk.Label(root, textvariable=self.status_var,
                                     font=('Arial', 14, 'bold'),
                                     fg=self.colors['text'], bg=self.colors['bg'])
        self.status_label.place(x=self.info_x, y=380)

        self.draw()

    def create_buttons(self):
        btn_style = {
            'font': ('Arial', 12, 'bold'),
            'bg': '#3a5a3a',
            'fg': '#e8dcc8',
            'activebackground': '#4a7a4a',
            'activeforeground': '#ffffff',
            'relief': 'raised',
            'bd': 2,
            'width': 12,
            'height': 1,
            'cursor': 'hand2'
        }

        self.restart_btn = tk.Button(self.root, text="重新开始", command=self.restart, **btn_style)
        self.restart_btn.place(x=self.info_x, y=240)

        self.undo_btn = tk.Button(self.root, text="悔棋", command=self.do_undo, **btn_style)
        self.undo_btn.place(x=self.info_x, y=280)

        self.pass_btn = tk.Button(self.root, text="弃权", command=self.do_pass, **btn_style)
        self.pass_btn.place(x=self.info_x, y=320)
        self.pass_btn.config(state='disabled')

        tip_label = tk.Label(self.root,
                             text="绿色圆点 = 可落子位置",
                             font=('Arial', 11),
                             fg='#88aa88', bg='#1a2a1a')
        tip_label.place(x=self.info_x, y=420)

    def to_screen(self, x, y):
        return self.left + y * self.cell + self.cell // 2, self.top + x * self.cell + self.cell // 2

    def to_board(self, px, py):
        x, y = (py - self.top) // self.cell, (px - self.left) // self.cell
        return (x, y) if 0 <= x < BSIZE and 0 <= y < BSIZE else (None, None)

    def draw_piece(self, x, y, color):
        cx, cy = self.to_screen(x, y)
        r = self.cell // 2 - 4

        if color == BLACK:
            self.canvas.create_oval(cx - r, cy - r, cx + r, cy + r, fill='#1a1a1a', outline='#333', width=1)
            self.canvas.create_oval(cx - r * 0.4, cy - r * 0.5, cx + r * 0.1, cy - r * 0.1, fill='#555', outline='')
            self.canvas.create_oval(cx - r * 0.2, cy - r * 0.3, cx + r * 0.05, cy - r * 0.05, fill='#888', outline='')
        else:
            self.canvas.create_oval(cx - r, cy - r, cx + r, cy + r, fill='#f5f5f5', outline='#ccc', width=1)
            self.canvas.create_oval(cx - r * 0.5, cy - r * 0.6, cx + r * 0.1, cy - r * 0.1, fill='#fff', outline='')
            self.canvas.create_oval(cx - r * 0.3, cy - r * 0.4, cx + r * 0.05, cy - r * 0.05, fill='#fff', outline='')

    def draw(self):
        global current_player, game_over

        self.canvas.delete("all")
        self.canvas.create_rectangle(0, 0, 740, 580, fill=self.colors['board_bg'])

        for i in range(BSIZE + 1):
            p = self.top + i * self.cell
            self.canvas.create_line(self.left, p, self.left + BSIZE * self.cell, p, fill=self.colors['grid'], width=1)
            p = self.left + i * self.cell
            self.canvas.create_line(p, self.top, p, self.top + BSIZE * self.cell, fill=self.colors['grid'], width=1)

        for i in range(BSIZE):
            self.canvas.create_text(self.left - 15, self.top + i * self.cell + self.cell // 2, text=str(i),
                                    fill='#88aa88', font=('Arial', 10))
            self.canvas.create_text(self.left + i * self.cell + self.cell // 2, self.top - 15, text=str(i),
                                    fill='#88aa88', font=('Arial', 10))

        player_moves = get_valid_moves(BLACK) if current_player == BLACK and not game_over else []
        for x, y in player_moves:
            cx, cy = self.to_screen(x, y)
            self.canvas.create_oval(cx - 12, cy - 12, cx + 12, cy + 12, fill='#00ff44', outline='', stipple='gray50')
            self.canvas.create_oval(cx - 8, cy - 8, cx + 8, cy + 8, fill='#00dd44', outline='')
            self.canvas.create_oval(cx - 4, cy - 4, cx + 4, cy + 4, fill='#00ff55', outline='')

        for i in range(BSIZE):
            for j in range(BSIZE):
                if board[i][j] != EMPTY:
                    self.draw_piece(i, j, board[i][j])

        if not game_over:
            ind_x = self.left + BSIZE * self.cell + 10
            ind_y = self.top + 10
            color = 'black' if current_player == BLACK else 'white'
            self.canvas.create_oval(ind_x, ind_y, ind_x + 20, ind_y + 20, fill=color, outline='#ffd700', width=2)
            self.canvas.create_text(ind_x + 10, ind_y + 35, text='走', fill='#ffd700', font=('Arial', 10, 'bold'))

        b, w = count_pieces(BLACK), count_pieces(WHITE)
        self.canvas.create_oval(self.info_x + 5, 55, self.info_x + 25, 75, fill='black', outline='#555', width=1)
        self.canvas.create_text(self.info_x + 35, 65, text=f'= {b}', fill='white', font=('Arial', 16, 'bold'),
                                anchor='w')
        self.canvas.create_oval(self.info_x + 5, 90, self.info_x + 25, 110, fill='white', outline='#aaa', width=1)
        self.canvas.create_text(self.info_x + 35, 100, text=f'= {w}', fill='white', font=('Arial', 16, 'bold'),
                                anchor='w')
        self.canvas.create_text(self.info_x, 140, text=f'步数: {move_count}', fill='#88aa88', font=('Arial', 14),
                                anchor='w')

        if game_over:
            b, w = count_pieces(BLACK), count_pieces(WHITE)
            if b > w:
                winner = "黑棋胜利!"
                color = '#ffd700'
            elif w > b:
                winner = "白棋胜利!"
                color = '#ffd700'
            else:
                winner = "平局!"
                color = '#88aa88'
            self.canvas.create_text(self.info_x, 185, text=winner, fill=color, font=('Arial', 22, 'bold'), anchor='w')
            self.status_var.set("游戏结束")
        else:
            turn = "黑棋" if current_player == BLACK else "白棋(AI)"
            self.status_var.set(f"{turn}走")
            if not has_valid_moves(current_player):
                self.pass_btn.config(state='normal')
                self.canvas.create_text(self.info_x, 185, text=f"{turn}无合法走法，请弃权", fill='#ff8844',
                                        font=('Arial', 14, 'bold'), anchor='w')
            else:
                self.pass_btn.config(state='disabled')
                if current_player == BLACK:
                    self.canvas.create_text(self.info_x, 185, text="点击绿色圆点落子", fill='#88dd88',
                                            font=('Arial', 14), anchor='w')
                else:
                    self.canvas.create_text(self.info_x, 185, text="AI思考中...", fill='#88dd88', font=('Arial', 14),
                                            anchor='w')

        self.root.update()

    def on_click(self, event):
        global current_player, game_over
        if ai_thinking or game_over or current_player != BLACK:
            return
        bx, by = self.to_board(event.x, event.y)
        if bx is None:
            return
        for x, y in get_valid_moves(BLACK):
            if x == bx and y == by:
                make_move(x, y)
                self.draw()
                self.root.after(100, self.ai_turn)
                return

    def ai_turn(self):
        if not game_over and current_player == WHITE:
            ai_move()
            self.draw()
            if game_over:
                messagebox.showinfo("游戏结束", f"游戏结束！\n黑棋: {count_pieces(BLACK)}  白棋: {count_pieces(WHITE)}")
                return
            if current_player == WHITE and not game_over:
                self.root.after(100, self.ai_turn)
            if current_player == BLACK and not game_over:
                self.draw()

    def restart(self):
        init()
        self.draw()

    def do_undo(self):
        if undo_move():
            self.draw()
            if current_player == WHITE and not game_over:
                self.root.after(300, self.ai_turn)
        else:
            messagebox.showinfo("提示", "没有可以撤销的步骤！")

    def do_pass(self):
        global current_player, game_over
        if game_over:
            return
        if has_valid_moves(current_player):
            messagebox.showinfo("提示", "你有合法走法，不能弃权！")
            return
        current_player = opponent(current_player)
        if not has_valid_moves(current_player):
            current_player = opponent(current_player)
            if not has_valid_moves(current_player):
                game_over = True
                self.draw()
                messagebox.showinfo("游戏结束",
                                    f"双方都无合法走法！\n黑棋: {count_pieces(BLACK)}  白棋: {count_pieces(WHITE)}")
                return
        self.draw()
        self.pass_btn.config(state='disabled')
        if current_player == WHITE and not game_over:
            self.root.after(300, self.ai_turn)


# ========== 启动 ==========
if __name__ == "__main__":
    init()
    root = tk.Tk()
    gui = OthelloGUI(root)
    root.mainloop()
