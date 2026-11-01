"""
Rule N × Rule M — Malla Bidimensional Cruzada con Reglas de Relleno por Cuadrantes

- Eje X / Cuadrantes Este-Oeste: Evolucionan horizontalmente con RULE_X (Verde)
- Eje Y / Cuadrantes Norte-Sur: Evolucionan verticalmente con RULE_Y (Rosa)
- Colisión: Detención en las diagonales (|x| == |y|) impidiendo el cruce de frentes.
- Los rellenos de cuadrantes EVOLUCIONAN en cada generación (no son estáticos).

Controles:
  Q / W         rule X anterior / siguiente   (reinicia)
  A / S         rule Y anterior / siguiente   (reinicia)
  Z / X         ciclar AMBAS rules a la vez   (reinicia)
  Espacio       pausa / reanuda
  1 / 2         X start -1 / +1   (Shift = ±10)
  3 / 4         Y start -1 / +1   (Shift = ±10)
  R             reiniciar (aplica starts)
  Rueda         zoom manual (anclado al cursor)
  Clic dcho.    paneo (también flechas)
  F             auto-zoom
  +/-           velocidad
  Esc           salir
"""

import numpy as np
import pygame

# ==========================================================
#  CONFIG
# ==========================================================
RULES = [30, 45, 60, 90, 102, 110, 126, 150, 184, 225]
RULE_NAMES = {
    30:  "Caos",
    45:  "Fractal",
    60:  "Sierpinski",
    90:  "Sierpinski",
    102: "Triángulos",
    110: "Turing",
    126: "Fractal",
    150: "XOR",
    184: "Tráfico",
    225: "Anti-30",
}

rule_idx_x = 0
rule_idx_y = 0

def _lut_for(idx):
    return np.array([(RULES[idx] >> i) & 1 for i in range(8)], dtype=np.uint8)

RULE_LUT_X = _lut_for(rule_idx_x)
RULE_LUT_Y = _lut_for(rule_idx_y)

SCREEN_W, SCREEN_H = 1280, 800
FPS = 60

BG_COLOR     = (10, 12, 18)
CELL_COLOR_X = (0, 235, 150)   # Cuadrantes E-W (Verde)
CELL_COLOR_Y = (0, 235, 150) # Cuadrantes N-S (Rosa)
HUD_COLOR    = (200, 220, 245)
AXIS_COLOR   = (32, 40, 55)

MAX_STEPS    = 2000
OFFSET       = MAX_STEPS + 1
SIZE         = 2 * MAX_STEPS + 3

MAX_CELL_FIT = 60
MIN_CELL     = 1
MAX_CELL_MAN = 500

# Ejes 1D primarios
x_axis = np.zeros(SIZE, dtype=np.uint8)
y_axis = np.zeros(SIZE, dtype=np.uint8)

# Grilla de estados 2D (0: Muerta, 1: Activa)
grid_state = np.zeros((SIZE, SIZE), dtype=np.uint8)
# Grilla de propiedad de frente (0: Ninguno, 1: Frente X, 2: Frente Y)
grid_owner = np.zeros((SIZE, SIZE), dtype=np.uint8)

gen = 0
x_gen = 0
y_gen = 0
x_start = 0
y_start = 0

X_INIT_OFFSETS = [0, -1, 1]
Y_INIT_OFFSETS = [0]

# ==========================================================
#  CAMBIO DE RULE (por eje)
# ==========================================================
def update_caption():
    try:
        pygame.display.set_caption(
            f"X: Rule {RULES[rule_idx_x]}   Y: Rule {RULES[rule_idx_y]}   ×2"
        )
    except pygame.error:
        pass


def set_rule_x(idx):
    global rule_idx_x, RULE_LUT_X
    rule_idx_x = idx % len(RULES)
    RULE_LUT_X = _lut_for(rule_idx_x)
    update_caption()


def set_rule_y(idx):
    global rule_idx_y, RULE_LUT_Y
    rule_idx_y = idx % len(RULES)
    RULE_LUT_Y = _lut_for(rule_idx_y)
    update_caption()

# ==========================================================
#  SIMULACIÓN Y EVOLUCIÓN DE RELLENO
# ==========================================================
def advance_1d_axis(axis_array, g, lut):
    """Evoluciona los autómatas 1D principales sobre los ejes centrados."""
    if g >= MAX_STEPS:
        return
    lo = OFFSET - g - 2
    hi = OFFSET + g + 3
    prev = axis_array[lo:hi]
    idx = (prev[:-2] << 2) | (prev[1:-1] << 1) | prev[2:]
    axis_array[lo + 1:hi - 1] = lut[idx]


def _evolve_line(src_vals, lut, valid_mask):
    """
    Dada una línea 1D (src_vals) de longitud SIZE, calcula la siguiente
    generación CA 1D y devuelve un array de longitud SIZE con los valores
    nuevos (0 fuera del rango válido).
    """
    idx = (src_vals[:-2] << 2) | (src_vals[1:-1] << 1) | src_vals[2:]
    nxt = lut[idx]
    out = np.zeros(SIZE, dtype=np.uint8)
    out[1:-1] = nxt
    out &= valid_mask.astype(np.uint8)
    return out


def evolve_fill_quadrants(d, lut_x, lut_y):
    """
    Recalcula TODO el dominio de relleno de cada cuadrante de forma
    vectorizada (sin bucles Python sobre filas/columnas).

    - Cuadrantes Este/Oeste (|y| < |x|): RULE_X sobre la columna fuente
      adyacente hacia el eje.
    - Cuadrantes Norte/Sur (|x| < |y|): RULE_Y sobre la fila fuente
      adyacente hacia el eje.
    - Diagonal |x| == |y| queda bloqueada.
    """
    if d <= 0 or d >= MAX_STEPS:
        return

    d = min(d, MAX_STEPS - 1)

    # Región activa: cuadrado [-d, d]² alrededor del origen
    lo = OFFSET - d
    hi = OFFSET + d + 1          # exclusivo
    n  = hi - lo                 # lado del cuadrado (2d+1)

    state = grid_state[lo:hi, lo:hi]   # vista (n, n)
    owner = grid_owner[lo:hi, lo:hi]   # vista (n, n)

    # Coordenadas relativas al centro del cuadrado
    coords = np.arange(n) - d          # de -d a +d
    yy = coords[:, None]               # (n, 1)  filas
    xx = coords[None, :]               # (1, n)  columnas

    # ============================================================
    #  1. RELLENO HORIZONTAL (RULE_X) — shift en X
    # ============================================================
    # Dominio estricto: |y| < |x|  (excluye eje Y y diagonal)
    dom_h = np.abs(yy) < np.abs(xx)    # (n, n) bool

    if dom_h.any():
        # Construir un "snapshot" desplazado en X:
        # Para columnas a la derecha (x>0): fuente = columna x-1
        # Para columnas a la izquierda (x<0): fuente = columna x+1
        # Lo hacemos con padding y dos slices, luego elegimos por signo.
        pad = np.zeros((n, n + 2), dtype=np.uint8)
        pad[:, 1:-1] = state

        # src_right[y, x] = state[y, x-1]  (fuente hacia el centro para x>0)
        src_right = pad[:, :-2]   # (n, n) -> columna fuente x-1
        # src_left[y, x]  = state[y, x+1]  (fuente hacia el centro para x<0)
        src_left  = pad[:, 2:]    # (n, n) -> columna fuente x+1

        # Elegir fuente según el signo de x
        src_h = np.where(xx > 0, src_right, src_left)

        # Aplicar LUT_X de forma vectorizada:
        # índice = (izq << 2) | (centro << 1) | der  sobre la COLUMNA
        # Como trabajamos por columnas, la vecindad es en Y.
        # Para cada celda (y, x) queremos la evolución de la COLUMNA x
        # evaluada en la fila y. Eso requiere vecindad vertical de la
        # columna fuente -> shift en Y sobre src_h.
        # Pero src_h ya es la columna fuente desplazada; ahora necesitamos
        # sus vecinos verticales:
        src_h_pad = np.zeros((n + 2, n), dtype=np.uint8)
        src_h_pad[1:-1, :] = src_h
        up    = src_h_pad[:-2, :]
        mid   = src_h_pad[1:-1, :]
        down  = src_h_pad[2:, :]

        idx_h = (up << 2) | (mid << 1) | down
        new_h = lut_x[idx_h]

        # Escribir solo donde dominio horizontal y dueño != Y
        write_h = dom_h & (owner != 2)
        state[write_h] = new_h[write_h]
        owner[write_h] = 1

    # Refrescar vistas (state/owner son vistas, ya reflejan cambios)
    # ============================================================
    #  2. RELLENO VERTICAL (RULE_Y) — shift en Y
    # ============================================================
    dom_v = np.abs(xx) < np.abs(yy)    # estricto, excluye eje X y diagonal

    if dom_v.any():
        pad_v = np.zeros((n + 2, n), dtype=np.uint8)
        pad_v[1:-1, :] = state

        src_down = pad_v[:-2, :]   # fila fuente y-1 (para y>0)
        src_up   = pad_v[2:, :]    # fila fuente y+1 (para y<0)

        src_v = np.where(yy > 0, src_down, src_up)

        # Vecindad horizontal sobre la fila fuente
        src_v_pad = np.zeros((n, n + 2), dtype=np.uint8)
        src_v_pad[:, 1:-1] = src_v
        left  = src_v_pad[:, :-2]
        mid   = src_v_pad[:, 1:-1]
        right = src_v_pad[:, 2:]

        idx_v = (left << 2) | (mid << 1) | right
        new_v = lut_y[idx_v]

        write_v = dom_v & (owner != 1)
        state[write_v] = new_v[write_v]
        owner[write_v] = 2


def step_once():
    global gen, x_gen, y_gen
    nxt = gen + 1

    # Inicialización / Evolución del Eje X
    if nxt == x_start:
        for o in X_INIT_OFFSETS:
            x_axis[OFFSET + o] = 1
            grid_state[OFFSET, OFFSET + o] = 1
            grid_owner[OFFSET, OFFSET + o] = 1
    elif nxt > x_start:
        advance_1d_axis(x_axis, x_gen, RULE_LUT_X)
        grid_state[OFFSET, :] = x_axis
        grid_owner[OFFSET, x_axis > 0] = 1
        x_gen += 1

    # Inicialización / Evolución del Eje Y
    if nxt == y_start:
        for o in Y_INIT_OFFSETS:
            y_axis[OFFSET + o] = 1
            grid_state[OFFSET + o, OFFSET] = 1
            grid_owner[OFFSET + o, OFFSET] = 2
    elif nxt > y_start:
        advance_1d_axis(y_axis, y_gen, RULE_LUT_Y)
        grid_state[:, OFFSET] = y_axis
        grid_owner[y_axis > 0, OFFSET] = 2
        y_gen += 1

    # Relleno Progresivo por Cuadrantes (AHORA EVOLUCIONA CADA GEN)
    if x_gen > 0 and y_gen >= 0:
        evolve_fill_quadrants(gen + 1, RULE_LUT_X, RULE_LUT_Y)

    gen = nxt


def restart():
    global gen, x_gen, y_gen
    gen = x_gen = y_gen = 0
    x_axis[:] = 0
    y_axis[:] = 0
    grid_state[:] = 0
    grid_owner[:] = 0

    if x_start == 0:
        for o in X_INIT_OFFSETS:
            x_axis[OFFSET + o] = 1
            grid_state[OFFSET, OFFSET + o] = 1
            grid_owner[OFFSET, OFFSET + o] = 1
    if y_start == 0:
        for o in Y_INIT_OFFSETS:
            y_axis[OFFSET + o] = 1
            grid_state[OFFSET + o, OFFSET] = 1
            grid_owner[OFFSET + o, OFFSET] = 2

# ==========================================================
#  CÁMARA
# ==========================================================
class Camera:
    def __init__(self):
        self.cell = 20
        self.ox = 0.0
        self.og = 0.0
        self.auto = True

    def fit(self, xg, yg):
        margin = 10
        w_cells = 2 * max(xg, 0) + 1 + 2 * margin
        h_cells = 2 * max(yg, 0) + 1 + 2 * margin
        cs = min(SCREEN_W / max(w_cells, 1),
                 SCREEN_H / max(h_cells, 1),
                 MAX_CELL_FIT)
        self.cell = max(MIN_CELL, int(cs))
        self.ox = -(SCREEN_W / self.cell) / 2
        self.og = -(SCREEN_H / self.cell) / 2

    def zoom_at(self, sx, sy, factor):
        ox = round(self.ox); og = round(self.og)
        wx = ox + sx / self.cell
        wy = og + sy / self.cell
        new_cell = int(round(self.cell * factor))
        new_cell = max(MIN_CELL, min(MAX_CELL_MAN, new_cell))
        if new_cell == self.cell:
            new_cell = self.cell + (1 if factor > 1 else -1)
            new_cell = max(MIN_CELL, min(MAX_CELL_MAN, new_cell))
        self.cell = new_cell
        self.ox = wx - sx / self.cell
        self.og = wy - sy / self.cell
        self.auto = False

# ==========================================================
#  RENDER
# ==========================================================
def draw_grid_2d(screen, cam):
    cs = int(cam.cell)
    ox = round(cam.ox)
    og = round(cam.og)

    num_cols = SCREEN_W // cs + 3
    num_rows = SCREEN_H // cs + 3

    x_start_idx = ox + OFFSET
    y_start_idx = og + OFFSET

    x_end_idx = x_start_idx + num_cols
    y_end_idx = y_start_idx + num_rows

    x_s = max(0, x_start_idx); x_e = min(SIZE, x_end_idx)
    y_s = max(0, y_start_idx); y_e = min(SIZE, y_end_idx)

    sub_state = np.zeros((num_rows, num_cols), dtype=np.uint8)
    sub_owner = np.zeros((num_rows, num_cols), dtype=np.uint8)

    if x_e > x_s and y_e > y_s:
        target_y_s = y_s - y_start_idx
        target_y_e = target_y_s + (y_e - y_s)
        target_x_s = x_s - x_start_idx
        target_x_e = target_x_s + (x_e - x_s)

        sub_state[target_y_s:target_y_e, target_x_s:target_x_e] = grid_state[y_s:y_e, x_s:x_e]
        sub_owner[target_y_s:target_y_e, target_x_s:target_x_e] = grid_owner[y_s:y_e, x_s:x_e]

    img = np.full((num_rows, num_cols, 3), BG_COLOR, dtype=np.uint8)

    mask_x = (sub_state == 1) & (sub_owner == 1)
    mask_y = (sub_state == 1) & (sub_owner == 2)

    img[mask_x] = CELL_COLOR_X
    img[mask_y] = CELL_COLOR_Y

    surf = pygame.surfarray.make_surface(img.swapaxes(0, 1))
    scaled = pygame.transform.scale(surf, (num_cols * cs, num_rows * cs))

    sx = (ox - cam.ox) * cs
    sy = (og - cam.og) * cs
    screen.blit(scaled, (sx, sy))


def draw_axes(screen, cam):
    cs = int(cam.cell)
    ox = round(cam.ox); og = round(cam.og)
    sy = (0 - og) * cs
    sx = (0 - ox) * cs
    pygame.draw.line(screen, AXIS_COLOR, (0, sy), (SCREEN_W, sy), 1)
    pygame.draw.line(screen, AXIS_COLOR, (sx, 0), (sx, SCREEN_H), 1)

# ==========================================================
#  MAIN
# ==========================================================
def main():
    global gen, x_gen, y_gen, x_start, y_start

    pygame.init()
    screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
    update_caption()
    clock = pygame.time.Clock()
    font  = pygame.font.SysFont("consolas", 17)

    cam = Camera()
    restart()
    cam.fit(x_gen, y_gen)

    paused = False
    speed  = 8.0
    acc    = 0.0
    dragging = False

    def _restart_cam():
        nonlocal acc
        restart()
        cam.auto = True
        cam.fit(x_gen, y_gen)
        acc = 0.0

    running = True
    while running:
        dt = min(clock.tick(FPS) / 1000.0, 0.05)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_SPACE:
                    paused = not paused

                elif event.key == pygame.K_q:
                    set_rule_x(rule_idx_x - 1); _restart_cam()
                elif event.key == pygame.K_w:
                    set_rule_x(rule_idx_x + 1); _restart_cam()
                elif event.key == pygame.K_a:
                    set_rule_y(rule_idx_y - 1); _restart_cam()
                elif event.key == pygame.K_s:
                    set_rule_y(rule_idx_y + 1); _restart_cam()

                elif event.key == pygame.K_z:
                    set_rule_x(rule_idx_x - 1)
                    set_rule_y(rule_idx_y - 1)
                    _restart_cam()
                elif event.key == pygame.K_x:
                    set_rule_x(rule_idx_x + 1)
                    set_rule_y(rule_idx_y + 1)
                    _restart_cam()

                elif event.key == pygame.K_r:
                    _restart_cam()
                elif event.key == pygame.K_f:
                    cam.auto = not cam.auto
                    if cam.auto:
                        cam.fit(x_gen, y_gen)
                elif event.key in (pygame.K_PLUS, pygame.K_EQUALS,
                                   pygame.K_KP_PLUS):
                    speed = min(120.0, speed * 1.5)
                elif event.key in (pygame.K_MINUS, pygame.K_KP_MINUS):
                    speed = max(0.5, speed / 1.5)
                elif event.key in (pygame.K_1, pygame.K_2,
                                   pygame.K_3, pygame.K_4):
                    shift = bool(pygame.key.get_mods() & pygame.KMOD_SHIFT)
                    d = 10 if shift else 1
                    if   event.key == pygame.K_1: x_start = max(0, x_start - d)
                    elif event.key == pygame.K_2: x_start = min(MAX_STEPS, x_start + d)
                    elif event.key == pygame.K_3: y_start = max(0, y_start - d)
                    elif event.key == pygame.K_4: y_start = min(MAX_STEPS, y_start + d)

            elif event.type == pygame.MOUSEWHEEL:
                mx, my = pygame.mouse.get_pos()
                cam.zoom_at(mx, my, 1.15 ** event.y)

            elif event.type == pygame.MOUSEBUTTONDOWN and event.button in (2, 3):
                dragging = True
            elif event.type == pygame.MOUSEBUTTONUP and event.button in (2, 3):
                dragging = False
            elif event.type == pygame.MOUSEMOTION and dragging:
                cam.ox -= event.rel[0] / cam.cell
                cam.og -= event.rel[1] / cam.cell
                cam.auto = False

        keys = pygame.key.get_pressed()
        pdx = pdy = 0
        if keys[pygame.K_LEFT]:  pdx -= 1
        if keys[pygame.K_RIGHT]: pdx += 1
        if keys[pygame.K_UP]:    pdy -= 1
        if keys[pygame.K_DOWN]:  pdy += 1
        if pdx or pdy:
            cam.auto = False
            pan = 600 * dt / cam.cell
            cam.ox += pdx * pan
            cam.og += pdy * pan

        if not paused and gen < MAX_STEPS:
            acc += dt * speed
            n = 0
            while acc >= 1.0 and gen < MAX_STEPS and n < 300:
                step_once()
                acc -= 1.0
                n += 1

        if cam.auto:
            cam.fit(x_gen, y_gen)

        screen.fill(BG_COLOR)
        draw_grid_2d(screen, cam)
        draw_axes(screen, cam)

        rx = RULES[rule_idx_x]
        ry = RULES[rule_idx_y]
        nx = RULE_NAMES.get(rx, "")
        ny = RULE_NAMES.get(ry, "")

        mode = "AUTO" if cam.auto else "MANUAL"
        st   = "  [PAUSA]" if paused else ("" if gen < MAX_STEPS else "  [FIN]")

        l1 = (f"X: Rule {rx:3d} [{rule_idx_x+1:2d}/{len(RULES)}] {nx:<10s}   "
              f"Y: Rule {ry:3d} [{rule_idx_y+1:2d}/{len(RULES)}] {ny:<10s}   "
              f"Gen {gen:5d}   cell{cam.cell:3d}px  v{speed:4.1f}  {mode}{st}")
        l2 = (f"Xst {x_start:5d}(g{x_gen:5d})  Yst {y_start:5d}(g{y_gen:5d})   "
              f"Q/W rule X | A/S rule Y | Z/X ambas | Espacio pausa")
        l3 = ("1/2 Xst±1 | 3/4 Yst±1 (Shift=±10) | R reiniciar | "
              "Rueda zoom | Clic dcho./flechas mover | F auto-zoom | +/- vel | Esc salir")

        for i, txt in enumerate((l1, l2, l3)):
            s  = font.render(txt, True, HUD_COLOR)
            sh = font.render(txt, True, (0, 0, 0))
            p  = (12, 10 + i * 20)
            screen.blit(sh, (p[0] + 1, p[1] + 1))
            screen.blit(s, p)

        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    main()
