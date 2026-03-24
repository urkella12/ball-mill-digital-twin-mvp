import math
import os
import random
from collections import deque
from datetime import datetime

import numpy as np
import pygame
import pymunk

# =========================
# Конфигурация окна / UI
# =========================
WIDTH, HEIGHT = 1500, 600
# Левая и центральная секции по 450px, правая (КА) - 600px для крупного вида
DEM_W, BRIDGE_W, CA_W = 450, 450, 600

FPS = 60
BG_COLOR = (18, 20, 26)
TEXT_COLOR = (220, 220, 220)
SEPARATOR_COLOR = (70, 70, 80)

# =========================
# DEM (макро-уровень)
# =========================
GRAVITY = (0, 900)
DRUM_RADIUS = 180
DRUM_SEGMENTS = 36
DRUM_ANGULAR_VELOCITY = 0.9
DRUM_SPEED_MIN = 0.1
DRUM_SPEED_MAX = 3.0
DRUM_SPEED_STEP = 0.1

BALL_COUNT = 8
BALL_RADIUS = 12

STRONG_IMPACT_THRESHOLD = 150.0
ENERGY_DECAY = 0.985
ENERGY_FROM_IMPULSE = 0.00003
ENERGY_FROM_STRONG_HIT = 0.08
ENERGY_HISTORY_LEN = 160

FRACTURE_ENERGY_THRESHOLD = 0.4

# =========================
# CA (мезо-уровень)
# =========================
GRID_SIZE = 100
CELL_SIZE = 5  # Увеличили ячейки (поле будет 500x500 px)
CA_ORIGIN_X = DEM_W + BRIDGE_W + 50
CA_ORIGIN_Y = 50

FRACTURE_RATE = 0.12
WELD_RATE = 0.10
EROSION_RATE = 0.004

class Simulation:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("Digital Twin MVP v6: Экономика Помола")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("consolas", 20, bold=True)
        self.small_font = pygame.font.SysFont("consolas", 14)
        self.medium_font = pygame.font.SysFont("consolas", 16)

        self.script_dir = os.path.dirname(os.path.abspath(__file__))

        self.paused = False
        self.drum_speed = DRUM_ANGULAR_VELOCITY
        self.dragging_speed_slider = False
        self.surfactant_mode = False

        self.slider_track_rect = pygame.Rect(30, HEIGHT - 40, DEM_W - 60, 10)
        self.slider_knob_radius = 12

        self.system_energy = 0.0
        self.total_energy_cost = 0.0
        
        # Точки для графика "Выход vs Энергия"
        self.yield_points = [] 

        self.frame_impulse_sum = 0.0
        self.frame_strong_hits = 0
        self.last_strong_hits = 0
        self.frame_count = 0

        self.color_map = {0: (0, 0, 0)}
        self.next_color_id = 1

        self.space = pymunk.Space()
        self.space.gravity = GRAVITY
        self._init_dem()
        
        self.grid = np.zeros((GRID_SIZE, GRID_SIZE), dtype=np.int32)
        self.initial_mass = 0
        self._init_ca_cluster()

    # ---------- DEM ----------
    def _init_dem(self):
        center = (DEM_W // 2, HEIGHT // 2 - 30)
        self.drum_body = pymunk.Body(body_type=pymunk.Body.KINEMATIC)
        self.drum_body.position = center
        self.drum_body.angular_velocity = self.drum_speed

        self.drum_segments = []
        for i in range(DRUM_SEGMENTS):
            a0 = 2 * math.pi * i / DRUM_SEGMENTS
            a1 = 2 * math.pi * (i + 1) / DRUM_SEGMENTS
            p0 = (DRUM_RADIUS * math.cos(a0), DRUM_RADIUS * math.sin(a0))
            p1 = (DRUM_RADIUS * math.cos(a1), DRUM_RADIUS * math.sin(a1))
            seg = pymunk.Segment(self.drum_body, p0, p1, 5)
            seg.elasticity = 0.95
            seg.friction = 0.8
            seg.collision_type = 2
            self.drum_segments.append(seg)
        self.space.add(self.drum_body, *self.drum_segments)

        self.balls = []
        self._create_balls()
        self.space.on_collision(1, 1, post_solve=self._on_collision_post_solve)
        self.space.on_collision(1, 2, post_solve=self._on_collision_post_solve)

    def _create_balls(self):
        for _ in range(BALL_COUNT):
            mass = 1.0
            moment = pymunk.moment_for_circle(mass, 0, BALL_RADIUS)
            body = pymunk.Body(mass, moment)
            angle = random.uniform(0, 2 * math.pi)
            r = random.uniform(10, DRUM_RADIUS - 30)
            body.position = (self.drum_body.position.x + r * math.cos(angle), 
                             self.drum_body.position.y + r * math.sin(angle))
            shape = pymunk.Circle(body, BALL_RADIUS)
            shape.elasticity = 0.9
            shape.friction = 0.7
            shape.collision_type = 1
            self.space.add(body, shape)
            self.balls.append(shape)

    def _reset_dem(self):
        for ball in self.balls:
            self.space.remove(ball, ball.body)
        self.balls.clear()
        self.drum_body.angle = 0.0
        self._create_balls()

    def _set_drum_speed(self, new_speed):
        self.drum_speed = max(DRUM_SPEED_MIN, min(DRUM_SPEED_MAX, new_speed))
        self.drum_body.angular_velocity = self.drum_speed

    def _set_speed_from_slider_x(self, mouse_x):
        t = (mouse_x - self.slider_track_rect.left) / max(1, self.slider_track_rect.width)
        t = max(0.0, min(1.0, t))
        speed = DRUM_SPEED_MIN + t * (DRUM_SPEED_MAX - DRUM_SPEED_MIN)
        self._set_drum_speed(speed)

    def _speed_to_norm(self): 
        return (self.drum_speed - DRUM_SPEED_MIN) / (DRUM_SPEED_MAX - DRUM_SPEED_MIN)

    def _on_collision_post_solve(self, arbiter, _space, _data):
        impulse = arbiter.total_impulse.length
        self.frame_impulse_sum += impulse
        if impulse > STRONG_IMPACT_THRESHOLD: 
            self.frame_strong_hits += 1
        return True

    # ---------- CA ----------
    def _new_color(self):
        color_id = self.next_color_id
        self.next_color_id += 1
        self.color_map[color_id] = (random.randint(50, 255), random.randint(50, 255), random.randint(50, 255))
        return color_id

    def _init_ca_cluster(self):
        main_color = self._new_color()
        cy, cx = GRID_SIZE // 2, GRID_SIZE // 2
        radius = GRID_SIZE // 3.5
        yy, xx = np.ogrid[:GRID_SIZE, :GRID_SIZE]
        self.grid[(yy - cy) ** 2 + (xx - cx) ** 2 <= radius ** 2] = main_color
        self.initial_mass = np.count_nonzero(self.grid)

    def _neighbors4(self, y, x):
        if y > 0: yield y - 1, x
        if y < GRID_SIZE - 1: yield y + 1, x
        if x > 0: yield y, x - 1
        if x < GRID_SIZE - 1: yield y, x + 1

    def _component_from(self, start_y, start_x, color):
        q = deque([(start_y, start_x)])
        visited = {(start_y, start_x)}
        cells = []
        while q:
            y, x = q.popleft()
            cells.append((y, x))
            for ny, nx in self._neighbors4(y, x):
                if (ny, nx) not in visited and self.grid[ny, nx] == color:
                    visited.add((ny, nx))
                    q.append((ny, nx))
        return cells

    def _nonzero_components(self):
        visited = np.zeros((GRID_SIZE, GRID_SIZE), dtype=bool)
        components = []
        for y, x in np.argwhere(self.grid > 0):
            if visited[y, x]: continue
            q = deque([(y, x)])
            visited[y, x] = True
            comp = []
            while q:
                cy, cx = q.popleft()
                comp.append((cy, cx))
                for ny, nx in self._neighbors4(cy, cx):
                    if not visited[ny, nx] and self.grid[ny, nx] > 0:
                        visited[ny, nx] = True
                        q.append((ny, nx))
            components.append(comp)
        return components

    def _carve_crack(self, start_y, start_x):
        dx, dy = math.cos(random.uniform(0, 2 * math.pi)), math.sin(random.uniform(0, 2 * math.pi))
        moves = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]
        def walk(seed_y, seed_x, steps):
            x, y, local_dx, local_dy = seed_x, seed_y, dx, dy
            for _ in range(steps):
                if not (0 <= y < GRID_SIZE and 0 <= x < GRID_SIZE): break
                self.grid[y, x] = 0
                a = math.atan2(local_dy, local_dx) + random.uniform(-0.35, 0.35)
                local_dx, local_dy = math.cos(a), math.sin(a)
                best_score, best_move = -1e9, None
                for my, mx in moves:
                    ny, nx = y + my, x + mx
                    if not (0 <= ny < GRID_SIZE and 0 <= nx < GRID_SIZE): continue
                    mag = max(1e-6, math.hypot(mx, my))
                    score = ((mx * local_dx + my * local_dy) / mag) + (0.35 if self.grid[ny, nx] > 0 else -0.1) + random.uniform(-0.25, 0.25)
                    if score > best_score: best_score, best_move = score, (my, mx)
                if not best_move: break
                y += best_move[0]; x += best_move[1]
        walk(start_y, start_x, random.randint(GRID_SIZE // 2, GRID_SIZE))

    def _fracture_step(self, p_fracture):
        if p_fracture <= 0.0 or random.random() > p_fracture * FRACTURE_RATE: return
        occupied = np.argwhere(self.grid > 0)
        if len(occupied) < 30: return
        sy, sx = occupied[random.randint(0, len(occupied) - 1)]
        self._carve_crack(int(sy), int(sx))
        comps = self._nonzero_components()
        if len(comps) > 1:
            candidates = [c for c in sorted(comps, key=len, reverse=True)[1:] if len(c) > 5]
            if candidates:
                new_c = self._new_color()
                for y, x in min(candidates, key=len): self.grid[y, x] = new_c

    def _weld_step(self, p_weld):
        if random.random() > p_weld * WELD_RATE: return
        ys, xs = np.where(self.grid > 0)
        if len(ys) == 0: return
        idxs = list(range(len(ys)))
        random.shuffle(idxs)
        pair = None
        for i in idxs[:4000]:
            y, x = ys[i], xs[i]
            c1 = self.grid[y, x]
            for ny, nx in self._neighbors4(y, x):
                c2 = self.grid[ny, nx]
                if c2 > 0 and c2 != c1:
                    pair = ((y, x, c1), (ny, nx, c2))
                    break
            if pair: break
        if not pair: return
        comp1 = self._component_from(pair[0][0], pair[0][1], pair[0][2])
        comp2 = self._component_from(pair[1][0], pair[1][1], pair[1][2])
        small, target_c = (comp1, pair[1][2]) if len(comp1) < len(comp2) else (comp2, pair[0][2])
        for y, x in small: self.grid[y, x] = target_c

    def _erosion_step(self):
        local_rate = EROSION_RATE * (0.5 + self.system_energy)
        targets = []
        for y, x in zip(*np.where(self.grid > 0)):
            empty, same = sum(1 for ny, nx in self._neighbors4(y, x) if self.grid[ny, nx] == 0), sum(1 for ny, nx in self._neighbors4(y, x) if self.grid[ny, nx] == self.grid[y, x])
            if empty >= 1 and same <= 2 and random.random() < local_rate: targets.append((y, x))
        for y, x in targets[:100]: self.grid[y, x] = self._new_color()

    def _apply_gravity(self):
        comps = self._nonzero_components()
        if len(comps) < 2: return
        comps.sort(key=len, reverse=True)
        for comp in comps[1:]:
            can_move = True
            for y, x in comp:
                if y >= GRID_SIZE - 1 or (self.grid[y+1, x] > 0 and (y+1, x) not in comp):
                    can_move = False; break
            if can_move:
                for y, x in sorted(comp, key=lambda p: p[0], reverse=True):
                    self.grid[y+1, x] = self.grid[y, x]
                    self.grid[y, x] = 0

    def _update_ca(self, p_fracture, p_weld):
        self._fracture_step(p_fracture)
        self._weld_step(p_weld)
        self._erosion_step()
        if self.frame_count % 4 == 0: self._apply_gravity()

    def _compute_stats(self):
        """Возвращает: кол-во крупных, кол-во пыли, средний размер крупных, массу крупных"""
        unique, counts = np.unique(self.grid, return_counts=True)
        if len(unique) > 1:
            all_sizes = counts[1:]
            valid_sizes = all_sizes[all_sizes > 2]
            dust_sizes = all_sizes[all_sizes <= 2]
            
            major_parts = len(valid_sizes)
            dust_parts = len(dust_sizes)
            avg_size = np.mean(valid_sizes) if major_parts > 0 else 0.0
            major_mass = np.sum(valid_sizes) if major_parts > 0 else 0
            return major_parts, dust_parts, avg_size, major_mass
        return 0, 0, 0.0, 0

    # ---------- Мост ----------
    def _update_energy(self, dt):
        increase = (self.frame_strong_hits * ENERGY_FROM_STRONG_HIT + self.frame_impulse_sum * ENERGY_FROM_IMPULSE)
        self.system_energy = max(0.0, min(1.0, (self.system_energy + increase) * ENERGY_DECAY))
        
        cost_rate = (self.drum_speed ** 2.5) * 5.0
        self.total_energy_cost += cost_rate * dt

        self.last_strong_hits = self.frame_strong_hits
        self.frame_impulse_sum, self.frame_strong_hits = 0.0, 0

    def _compute_bridge_probs(self):
        e = self.system_energy
        p_fracture = e if (e >= FRACTURE_ENERGY_THRESHOLD and self.last_strong_hits > 0) else 0.0
        p_weld = 0.0 if self.surfactant_mode else max(0.0, 1.0 - abs(2.0 * e - 1.0))
        return p_fracture, p_weld

    # ---------- Отрисовка ----------
    def _draw_dem(self):
        pygame.draw.rect(self.screen, (24, 26, 34), (0, 0, DEM_W, HEIGHT))
        for seg in self.drum_segments:
            a, b = self.drum_body.local_to_world(seg.a), self.drum_body.local_to_world(seg.b)
            pygame.draw.line(self.screen, (190, 190, 210), (int(a.x), int(a.y)), (int(b.x), int(b.y)), 4)
        for ball in self.balls:
            p, vel = ball.body.position, min(1.0, ball.body.velocity.length / 600.0)
            color = (int(50 + 205 * vel), int(210 - 160 * vel), int(255 - 205 * vel))
            pygame.draw.circle(self.screen, color, (int(p.x), int(p.y)), int(ball.radius))
            pygame.draw.circle(self.screen, (255, 255, 255), (int(p.x), int(p.y)), int(ball.radius), 1)

        self.screen.blit(self.font.render("DEM (Макро-Кинематика)", True, TEXT_COLOR), (20, 15))
        
        cost_txt = self.medium_font.render(f"Затраты энергии: {int(self.total_energy_cost)} кДж", True, (255, 200, 100))
        self.screen.blit(cost_txt, (30, HEIGHT - 100))
        self.screen.blit(self.medium_font.render(f"Скорость ротора: {self.drum_speed:.2f} рад/с", True, (235, 235, 245)), (30, HEIGHT - 75))
        
        track = self.slider_track_rect
        pygame.draw.rect(self.screen, (45, 48, 58), track, border_radius=5)
        fill_w = int(track.width * self._speed_to_norm())
        if fill_w > 0: pygame.draw.rect(self.screen, (120, 200, 255), (track.left, track.top, fill_w, track.height), border_radius=5)
        kx, ky = track.left + fill_w, track.centery
        pygame.draw.circle(self.screen, (225, 245, 255), (kx, ky), self.slider_knob_radius)
        pygame.draw.circle(self.screen, (100, 125, 145), (kx, ky), self.slider_knob_radius, 2)

    def _draw_bridge(self, p_fracture, p_weld, yield_pct):
        x0 = DEM_W
        pygame.draw.rect(self.screen, (22, 25, 33), (x0, 0, BRIDGE_W, HEIGHT))
        self.screen.blit(self.font.render("Мост Масштабов & Экономика", True, TEXT_COLOR), (x0 + 20, 15))

        regime = "Катарактирование (Раскол)" if self.drum_speed >= 1.3 else "Каскадирование (Истирание)"
        self.screen.blit(self.medium_font.render(f"Режим: {regime}", True, (255, 100, 100) if self.drum_speed >= 1.3 else (100, 200, 255)), (x0 + 20, 50))
        
        pav_color = (100, 255, 100) if self.surfactant_mode else (150, 150, 150)
        pav_text = "ВКЛЮЧЕН (Сварка = 0)" if self.surfactant_mode else "ВЫКЛЮЧЕН (Нажмите 'P')"
        self.screen.blit(self.medium_font.render(f"ПАВ: {pav_text}", True, pav_color), (x0 + 20, 80))

        # График точечный: Энергия vs Выход продукта
        plot_y = 120
        plot_h = 160
        plot_w = BRIDGE_W - 40
        pygame.draw.rect(self.screen, (30, 32, 40), (x0 + 20, plot_y, plot_w, plot_h), border_radius=6)
        pygame.draw.rect(self.screen, (100, 100, 110), (x0 + 20, plot_y, plot_w, plot_h), 2, border_radius=6)
        
        self.screen.blit(self.small_font.render("Ось Y: Выход нано-пыли (%)", True, (150, 150, 160)), (x0 + 25, plot_y + 5))
        self.screen.blit(self.small_font.render("Ось X: Затраты энергии (кДж)", True, (150, 150, 160)), (x0 + 25, plot_y + plot_h - 20))

        # Отрисовка точек графика
        max_energy = max(5000.0, self.total_energy_cost)
        for e_cost, y_pct in self.yield_points:
            px = x0 + 20 + int((e_cost / max_energy) * plot_w)
            py = plot_y + plot_h - int((y_pct / 100.0) * plot_h)
            # Ограничиваем отрисовку внутри рамки
            px = min(max(px, x0 + 22), x0 + 20 + plot_w - 2)
            py = min(max(py, plot_y + 2), plot_y + plot_h - 2)
            pygame.draw.circle(self.screen, (255, 200, 50), (px, py), 2)

        # Вероятности (Бары)
        for y_offset, val, col, lbl in [(330, p_fracture, (255, 90, 90), "P_fracture (Раскол)"), (390, p_weld, (90, 230, 120), "P_weld (Сварка)")]:
            pygame.draw.rect(self.screen, (40, 40, 48), (x0 + 20, y_offset, BRIDGE_W - 40, 24), border_radius=6)
            pygame.draw.rect(self.screen, col, (x0 + 20, y_offset, int((BRIDGE_W - 40) * val), 24), border_radius=6)
            self.screen.blit(self.medium_font.render(f"{lbl}: {val:.2f}", True, TEXT_COLOR), (x0 + 20, y_offset - 22))
            
        # Текущий выход продукта крупно
        yield_txt = self.font.render(f"Выход продукта: {yield_pct:.1f}%", True, (255, 215, 0))
        self.screen.blit(yield_txt, (x0 + 20, HEIGHT - 50))

    def _draw_ca(self, major_parts, dust_parts, avg_size):
        x0 = DEM_W + BRIDGE_W
        pygame.draw.rect(self.screen, (15, 15, 18), (x0, 0, CA_W, HEIGHT))
        self.screen.blit(self.font.render("CA (Микроструктура порошка)", True, TEXT_COLOR), (x0 + 20, 15))

        # Сетка КА (теперь крупная)
        for y, x in zip(*np.where(self.grid > 0)):
            pygame.draw.rect(self.screen, self.color_map.get(self.grid[y, x], (255, 255, 255)), 
                             (CA_ORIGIN_X + x * CELL_SIZE, CA_ORIGIN_Y + y * CELL_SIZE, CELL_SIZE, CELL_SIZE))

        stat_text = f"Крупных кусков: {major_parts} | Пыли: {dust_parts} | Сред. размер: {avg_size:.0f} px"
        self.screen.blit(self.medium_font.render(stat_text, True, (150, 255, 150)), (x0 + 20, HEIGHT - 35))

    def run(self):
        running = True
        while running:
            dt = self.clock.tick(FPS) / 1000.0
            self.frame_count += 1
            for event in pygame.event.get():
                if event.type == pygame.QUIT: running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_SPACE: self.paused = not self.paused
                    elif event.key == pygame.K_p: self.surfactant_mode = not self.surfactant_mode
                    elif event.key == pygame.K_r:
                        self.total_energy_cost, self.system_energy, self.frame_count = 0.0, 0.0, 0
                        self.yield_points.clear()
                        self._reset_dem(); self.grid.fill(0); self.color_map = {0: (0, 0, 0)}
                        self.next_color_id = 1; self._init_ca_cluster()
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if self.slider_track_rect.collidepoint(event.pos) or self.slider_track_rect.collidepoint(event.pos[0], self.slider_track_rect.centery):
                        self.dragging_speed_slider = True
                        self._set_speed_from_slider_x(event.pos[0])
                elif event.type == pygame.MOUSEBUTTONUP and event.button == 1: self.dragging_speed_slider = False
                elif event.type == pygame.MOUSEMOTION and self.dragging_speed_slider: self._set_speed_from_slider_x(event.pos[0])

            if not self.paused:
                for _ in range(2): self.space.step(dt / 2)
                self._update_energy(dt)
                pf, pw = self._compute_bridge_probs()
                self._update_ca(pf, pw)
            else:
                self.frame_impulse_sum, self.frame_strong_hits, self.last_strong_hits = 0.0, 0, 0
                pf, pw = self._compute_bridge_probs()

            # Получаем актуальную статистику КА
            major_parts, dust_parts, avg_size, major_mass = self._compute_stats()
            
            # Расчет процента выхода пыли (то, что не является крупными кусками)
            yield_pct = 0.0
            if self.initial_mass > 0:
                yield_pct = max(0.0, min(100.0, (self.initial_mass - major_mass) / self.initial_mass * 100.0))

            # Запись точки графика раз в секунду (60 кадров)
            if not self.paused and self.frame_count % FPS == 0:
                self.yield_points.append((self.total_energy_cost, yield_pct))

            self.screen.fill(BG_COLOR)
            self._draw_dem()
            self._draw_bridge(pf, pw, yield_pct)
            self._draw_ca(major_parts, dust_parts, avg_size)
            
            pygame.draw.line(self.screen, SEPARATOR_COLOR, (DEM_W, 0), (DEM_W, HEIGHT), 3)
            pygame.draw.line(self.screen, SEPARATOR_COLOR, (DEM_W + BRIDGE_W, 0), (DEM_W + BRIDGE_W, HEIGHT), 3)
            pygame.display.flip()
            
        pygame.quit()

if __name__ == "__main__":
    Simulation().run()
