# Collision-of-Automata
An experimental 2D cellular automata system exploring emergent complexity, fractal structures and deterministic patterns through the interaction of independent discrete rules.


# Rule N × Rule M — Crossed 2D Mesh with Quadrant Fill Rules

An interactive **2D cellular automaton** simulator that combines two classic 1D automata (Rule X on the horizontal axis and Rule Y on the vertical axis) to generate fractal, geometric, and chaotic patterns that expand through quadrants from a central origin.

The result is a "crossed mesh": a horizontal wavefront (evolved with **Rule X**) and a vertical one (evolved with **Rule Y**) that meet on the diagonals `|x| == |y|`, where they collide and block each other. The remaining quadrants are filled **dynamically and evolutionarily** with the same rules applied locally.

---

## 📋 Table of contents

- [Features](#-features)
- [Requirements](#-requirements)
- [Installation](#-installation)
- [Usage](#-usage)
- [Controls](#-controls)
- [Available rules](#-available-rules)
- [How it works](#-how-it-works)
- [Code architecture](#-code-architecture)
- [Tuning and parameters](#-tuning-and-parameters)
- [Ideas for extension](#-ideas-for-extension)
- [License](#-license)

---

## ✨ Features

- **Dual crossed 1D automaton**: a horizontal automaton (X axis) and a vertical one (Y axis) evolving independently with selectable rules.
- **Diagonal collision**: wavefronts stop when they meet at `|x| == |y|`, preventing crossover.
- **Dynamic quadrant fill**: the four quadrants are NOT static; they are recomputed generation after generation using the horizontal rule (East/West) or the vertical rule (North/South).
- **Full vectorization** of the fill using NumPy (no Python loops over rows/columns).
- **Interactive camera**: cursor-anchored zoom, right-click or arrow-key panning, and an auto-zoom mode that fits the growing pattern.
- **10 classic rules** from elementary cellular automata (30, 45, 60, 90, 102, 110, 126, 150, 184, 225).
- **Real-time speed control** and pause.
- **Adjustable starts** for X and Y (allows offsetting each automaton's start).
- **Rendering** via `pygame.surfarray` (direct blit of scaled NumPy arrays).

---

## 🔧 Requirements

- **Python 3.8+**
- **NumPy**
- **Pygame**

```bash
pip install numpy pygame
```

---

## 🚀 Installation

1. Clone or download the file `rule_xy.py` (or whatever you named it).
2. Make sure the dependencies are installed.
3. Run:

```bash
python rule_xy.py
```

---

## 🎮 Usage

On startup, the simulation begins with **Rule 30** on both axes and the camera in AUTO mode (it adjusts automatically to the pattern's size).

- The first row/column appears according to each axis's `start` parameter.
- The fronts grow from the center and stop at the diagonals.
- The quadrants fill in with patterns derived from the rules.

Press **Space** to pause, try different rules with **Q/W/A/S**, and watch how the pattern changes. Use **F** to toggle between auto and manual zoom.

---

## ⌨️ Controls

| Key / Action | Function |
|---|---|
| `Q` / `W` | Previous / next X rule (restarts) |
| `A` / `S` | Previous / next Y rule (restarts) |
| `Z` | Cycle **both** rules backward (restarts) |
| `X` | Cycle **both** rules forward (restarts) |
| `Space` | Pause / resume |
| `1` / `2` | Decrease / increase `x_start` by ±1 (`Shift` = ±10) |
| `3` / `4` | Decrease / increase `y_start` by ±1 (`Shift` = ±10) |
| `R` | Restart simulation (applies current starts) |
| `F` | Toggle auto-zoom |
| `+` / `=` | Speed up the simulation |
| `-` | Slow down the simulation |
| **Mouse wheel** | Cursor-anchored manual zoom |
| **Right-click** (drag) | Pan |
| **Arrow keys** | Pan |
| `Esc` | Quit |

---

## 📜 Available rules

Each rule corresponds to an **elementary cellular automaton** (Wolfram rules). You can choose the X-axis rule with `Q`/`W` and the Y-axis rule with `A`/`S`.

| # | Name | Description |
|---|---|---|
| 30 | Chaos | Classic chaotic pattern |
| 45 | Fractal | Fractal structure |
| 60 | Sierpinski | Sierpinski triangle |
| 90 | Sierpinski | Sierpinski variant |
| 102 | Triangles | Regular triangles |
| 110 | Turing | Universal (Turing-complete) |
| 126 | Fractal | Fractal structure |
| 150 | XOR | XOR of neighbors |
| 184 | Traffic | Traffic model |
| 225 | Anti-30 | Complement of Rule 30 |

The name is shown in the HUD alongside the rule number.

---

## ⚙️ How it works

### 1. 1D automata on the axes

- **X axis** (horizontal, green): each generation evolves the central row (`grid_state[OFFSET, :]`) according to `RULE_X`.
- **Y axis** (vertical, green in this code; the original comment mentions pink): each generation evolves the central column (`grid_state[:, OFFSET]`) according to `RULE_Y`.

Both automata are **elementary Wolfram rules**: the next state of a cell depends on itself and its two neighbors.

### 2. Quadrant fill evolution

After each step, the contents of the four quadrants are recomputed:

- **East/West quadrants** (`|y| < |x|`): `RULE_X` is applied to the **source column adjacent toward the axis**. The source depends on the sign of `x` (for `x>0`, column `x-1` is used; for `x<0`, column `x+1`).
- **North/South quadrants** (`|x| < |y|`): `RULE_Y` is applied to the **source row adjacent toward the axis**, analogously.
- **Diagonal** (`|x| == |y|`): blocked; it is the collision frontier.

The algorithm is **vectorized with NumPy**, using padded slices to compute neighbors and boolean masks to delimit the domain. The result is O(n²) growth per generation without Python loops over cells.

### 3. Camera

The `Camera` class maintains:

- `cell`: size of each cell in pixels.
- `ox`, `og`: origin in cell coordinates (for panning).
- `auto`: when `True`, the camera re-fits to `(x_gen, y_gen)` every frame.

Zoom is **anchored to the cursor**: the point under the mouse stays under the mouse after the scale factor is applied.

---

## 🏗️ Code architecture

```
rule_xy.py
│
├── CONFIG                 ← constants (RULES, colors, MAX_STEPS, etc.)
├── update_caption()       ← window title
├── set_rule_x / set_rule_y ← per-axis rule change
│
├── advance_1d_axis()      ← evolves a 1D automaton on an axis
├── _evolve_line()         ← helper: applies LUT to a 1D line
├── evolve_fill_quadrants()← vectorized fill of the quadrants
├── step_once()            ← global simulation step
├── restart()              ← resets the state (applies starts)
│
├── Camera                 ← zoom/pan/auto-fit management
│
├── draw_grid_2d()         ← renders the full grid as a texture
├── draw_axes()            ← draws the axes
│
└── main()                 ← main loop (events + update + render)
```

### Main states

- `x_axis`, `y_axis` (`np.uint8[SIZE]`): 1D automata for each axis.
- `grid_state` (`np.uint8[SIZE, SIZE]`): 2D state (0 dead / 1 alive).
- `grid_owner` (`np.uint8[SIZE, SIZE]`): front owner (0 none, 1 X, 2 Y). Resolves conflicts between quadrants.
- `SIZE = 2*MAX_STEPS + 3`, with `MAX_STEPS = 2000`.

### Order of magnitude

- **Maximum cells**: ~4000×4000 states + owners ≈ **~32 MB** of RAM in uint8.
- **Cell scale**: between `MIN_CELL = 1` and `MAX_CELL_MAN = 500`; `MAX_CELL_FIT = 60` for auto-fit.

---

## 🛠️ Tuning and parameters

You can modify at the top of the file:

```python
MAX_STEPS     = 2000   # maximum number of generations
SCREEN_W, SCREEN_H = 1280, 800
FPS           = 60
BG_COLOR      = (10, 12, 18)
CELL_COLOR_X  = (0, 235, 150)   # green (X front)
CELL_COLOR_Y  = (0, 235, 150)   # green (Y front) — the comment says "pink";
                                # change to (235, 60, 200) if you prefer
```

And the initial offsets:

```python
X_INIT_OFFSETS = [0, -1, 1]   # X-axis seed
Y_INIT_OFFSETS = [0]          # Y-axis seed
```

You can also add or reorder rules by editing `RULES` and `RULE_NAMES`.

---

## Examples

### Rule90xRule90
<img width="553" height="547" alt="image" src="https://github.com/user-attachments/assets/f7be6203-5b08-4149-a702-51474e1f0e3d" />

### Rule30xRule30
<img width="656" height="664" alt="image" src="https://github.com/user-attachments/assets/1e418b84-d8fd-4a27-b9a5-a3fa9b0837d7" />


## 💡 Ideas for extension

- **Non-elementary rules**: add 1D automata with a larger radius (5 cells) or totalistic rules.
- **Per-rule palette**: different colors depending on the active rule on each axis.
- **Screenshot saving**: key to export the current view to PNG.
- **GIF/MP4 recording** of the growth.
- **Stereo mode**: two pairs (X₁,Y₁) and (X₂,Y₂) superimposed in RGBA with transparency.
- **Periodic or reflected boundary** instead of diagonal blocking.
- **Multiple seeds** at several points on the plane (not just at the origin).

---

## 📄 License

This project is distributed as free example code. Use it, modify it, and share it as you wish; if you publish it, a mention of the original author is appreciated.

---

**Enjoy exploring the crossing of automata.** Each X/Y rule combination produces a different visual universe: try `Rule 30 × Rule 90` (chaos against fractal), `Rule 110 × Rule 184` (universality against traffic), or `Rule 60 × Rule 60` (Sierpinski in perfect symmetry).
