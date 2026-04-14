"""Simple rugby formation direction tool with tracking data playback."""

import json
from os import path
from pathlib import Path
from tkinter import Tk, Canvas, Frame, Button, Label, Scale, messagebox, filedialog
import tkinter.filedialog as fd
from typing import Optional
import pandas as pd
from datetime import datetime


class RugbyDirectionAnnotator:
    """Annotate player directions on a rugby pitch with tracking data playback."""

    def __init__(self, root: Tk):
        self.root = root
        self.root.title("Rugby Direction Annotator")
        self.root.geometry("2000x1400")

        # Rugby pitch dimensions (meters)
        self.pitch_length = 100  # goal line to goal line
        self.pitch_width = 73    # touchline to touchline
        self.scale = 8           # pixels per meter

        # Canvas dimensions
        self.canvas_width = self.pitch_length * self.scale
        self.canvas_height = self.pitch_width * self.scale

        # Tracking data
        self.df: Optional[pd.DataFrame] = None
        self.frame_idx = 0
        self.is_playing = False
        self.player_ids: list[str] = []
        self.player_positions: dict[str, tuple[float, float, float]] = {}  # pid -> (x, y, z) in meters

        # Ball
        self.ball_position = (50.0, 36.5, 1.0)
        self.selected_player: Optional[str] = None

        # Keyframes for animation
        self.keyframes: list[dict] = []  # [{'positions': dict, 'ball': tuple, 'selected_player': str}, ...]
        self.current_time = 0.0
        self.is_recording = False

        self.dragging_player: Optional[str] = None
        self.dragging_ball = False
        self.selected_ball = False

        self.snap_radius = 3.0  # meters
        self.grid_snap = 1.0    # meters (set None to disable)

        self._create_ui()

    def _create_ui(self) -> None:
        """Create the user interface."""
        # Control panel (left)
        control_frame = Frame(self.root, bg="#1e1e1e", padx=15, pady=15)
        control_frame.pack(side="left", fill="y", padx=20, pady=20)

        # File controls
        Label(control_frame, text="Setup:", font=("Arial", 14, "bold"), bg="#1e1e1e", fg="#e0e0e0").pack(anchor="w", pady=10)
        Button(control_frame, text="Lineout Formation", command=self._load_lineout, width=25, height=2, bg="#3498db", fg="black", font=("Arial", 11, "bold"), relief="raised", bd=3).pack(fill="x", pady=5)
        Button(control_frame, text="Load Custom Formation", command=self._load_custom_formation, width=25, height=2, bg="#e74c3c", fg="black", font=("Arial", 11, "bold"), relief="raised", bd=3).pack(fill="x", pady=5)
        self.csv_label = Label(control_frame, text="No data", font=("Arial", 10), fg="#a0a0a0", bg="#1e1e1e")
        self.csv_label.pack(anchor="w", pady=5)

        # Playback controls
        Label(control_frame, text="\nPlayback:", font=("Arial", 14, "bold"), bg="#1e1e1e", fg="#e0e0e0").pack(anchor="w", pady=10)
        button_frame = Frame(control_frame, bg="#1e1e1e")
        button_frame.pack(fill="x", pady=10)
        Button(button_frame, text="◀ Prev", command=self._prev_frame, width=10, height=2, bg="#95a5a6", fg="black", font=("Arial", 10, "bold"), relief="raised", bd=2).pack(side="left", padx=3)
        self.play_btn = Button(button_frame, text="▶ Play", command=self._toggle_play, width=10, height=2, bg="#27ae60", fg="black", font=("Arial", 10, "bold"), relief="raised", bd=2)
        self.play_btn.pack(side="left", padx=3)
        Button(button_frame, text="Next ▶", command=self._next_frame, width=10, height=2, bg="#95a5a6", fg="black", font=("Arial", 10, "bold"), relief="raised", bd=2).pack(side="left", padx=3)

        self.frame_label = Label(control_frame, text="Frame: 0/0", font=("Arial", 12, "bold"), fg="#e0e0e0", bg="#1e1e1e")
        self.frame_label.pack(anchor="w", pady=10)

        # Frame slider
        self.frame_slider = Scale(
            control_frame,
            from_=0,
            to=100,
            orient="horizontal",
            command=self._on_slider_change,
            length=300,
            sliderlength=20,
            troughcolor="#555555",
            bg="#1e1e1e",
            fg="#e0e0e0"
        )
        self.frame_slider.pack(fill="x", pady=10)

        # Recording controls
        Label(control_frame, text="\nRecord Keyframes:", font=("Arial", 14, "bold"), bg="#1e1e1e", fg="#e0e0e0").pack(anchor="w", pady=10)
        self.record_btn = Button(control_frame, text="Start Recording", command=self._toggle_recording, width=25, height=2, bg="#e67e22", fg="black", font=("Arial", 11, "bold"), relief="raised", bd=3)
        self.record_btn.pack(fill="x", pady=5)
        Button(control_frame, text="Capture Keyframe", command=self._capture_frame, width=25, height=2, bg="#f39c12", fg="black", font=("Arial", 11, "bold"), relief="raised", bd=3).pack(fill="x", pady=5)
        Button(control_frame, text="Undo Last Keyframe", command=self._undo_keyframe, width=25, height=2, bg="#d35400", fg="black", font=("Arial", 11, "bold"), relief="raised", bd=3).pack(fill="x", pady=5)
        Label(control_frame, text="(Move players and ball,\nthen capture)", font=("Arial", 9), fg="#a0a0a0", bg="#1e1e1e").pack(anchor="w", pady=5)
        Label(control_frame, text="Scroll wheel on a selected player to raise/lower Z.", font=("Arial", 9), fg="#a0a0a0", bg="#1e1e1e").pack(anchor="w", pady=5)

        self.record_label = Label(control_frame, text="Keyframes: 0", font=("Arial", 11, "bold"), fg="#ff6b6b", bg="#1e1e1e")
        self.record_label.pack(anchor="w", pady=10)

        # Save/load keyframes
        Label(control_frame, text="\nSave/Load:", font=("Arial", 14, "bold"), bg="#1e1e1e", fg="#e0e0e0").pack(anchor="w", pady=10)
        Button(control_frame, text="Save Animation", command=self._save_animation, width=25, height=2, bg="#9b59b6", fg="black", font=("Arial", 11, "bold"), relief="raised", bd=3).pack(fill="x", pady=5)
        Button(control_frame, text="Load Animation", command=self._load_animation, width=25, height=2, bg="#8e44ad", fg="black", font=("Arial", 11, "bold"), relief="raised", bd=3).pack(fill="x", pady=5)

        # Positions section
        Label(control_frame, text="\nPositions:", font=("Arial", 14, "bold"), bg="#1e1e1e", fg="#e0e0e0").pack(anchor="w", pady=15)
        Label(control_frame, text="(Drag players and ball\nwhen recording)", font=("Arial", 9), fg="#a0a0a0", bg="#1e1e1e").pack(anchor="w", pady=5)
        Button(control_frame, text="Export Formation", command=self._export_positions, width=25, height=2, bg="#1abc9c", fg="black", font=("Arial", 11, "bold"), relief="raised", bd=3).pack(fill="x", pady=5)
        Button(control_frame, text="Show Positions", command=self._show_positions, width=25, height=2, bg="#16a085", fg="black", font=("Arial", 11, "bold"), relief="raised", bd=3).pack(fill="x", pady=5)
        Button(control_frame, text="Export Rerun", command=self._export_rerun, width=25, height=2, bg="#2ecc71", fg="black", font=("Arial", 11, "bold"), relief="raised", bd=3).pack(fill="x", pady=5)

        # Canvas (right)
        canvas_frame = Frame(self.root, bg="#2d5016", padx=20, pady=20)
        canvas_frame.pack(side="right", fill="both", expand=True, padx=20, pady=20)

        self.canvas = Canvas(
            canvas_frame,
            width=self.canvas_width,
            height=self.canvas_height,
            bg="#2d5016",
            cursor="arrow",
            highlightthickness=2,
            highlightbackground="#1e3a0f"
        )
        self.canvas.pack()

        # Bind mouse events
        self.canvas.bind("<Button-1>", self._on_canvas_press)
        self.canvas.bind("<B1-Motion>", self._on_canvas_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_canvas_release)
        self.canvas.bind("<MouseWheel>", self._on_canvas_scroll)
        self.canvas.bind("<Button-4>", self._on_canvas_scroll)
        self.canvas.bind("<Button-5>", self._on_canvas_scroll)

    def _draw_pitch(self) -> None:
        """Draw rugby pitch markings."""
        self.canvas.delete("pitch")

        # Boundary
        self.canvas.create_rectangle(
            0, 0, self.canvas_width, self.canvas_height, outline="white", width=3, tags="pitch"
        )

        # Try lines (5m from ends)
        try_line_x1 = 5 * self.scale
        try_line_x2 = (self.pitch_length - 5) * self.scale
        self.canvas.create_line(try_line_x1, 0, try_line_x1, self.canvas_height, fill="white", width=1, tags="pitch")
        self.canvas.create_line(try_line_x2, 0, try_line_x2, self.canvas_height, fill="white", width=1, tags="pitch")

        # 22m line
        line22_x1 = 22 * self.scale
        line22_x2 = (self.pitch_length - 22) * self.scale
        self.canvas.create_line(line22_x1, 0, line22_x1, self.canvas_height, fill="white", width=1, tags="pitch", dash=(4, 4))
        self.canvas.create_line(line22_x2, 0, line22_x2, self.canvas_height, fill="white", width=1, tags="pitch", dash=(4, 4))

        # Halfway line
        mid_x = self.canvas_width / 2
        self.canvas.create_line(mid_x, 0, mid_x, self.canvas_height, fill="white", width=2, tags="pitch")

    def _normalize_position(self, pos) -> tuple[float, float, float]:
        """Normalize a player position to an (x, y, z) tuple."""
        if isinstance(pos, (list, tuple)):
            if len(pos) == 3:
                return float(pos[0]), float(pos[1]), float(pos[2])
            if len(pos) == 2:
                return float(pos[0]), float(pos[1]), 0.0
        raise ValueError(f"Invalid position format: {pos}")

    def _load_lineout(self) -> None:
        """Load a coach-designed lineout formation with forwards and backs."""
        self.df = None
        self.frame_idx = 0
        self.player_positions = self._generate_coach_lineout()
        self.keyframes = []
        self.ball_position = (50.0, 36.5, 1.0)
        self.is_playing = False
        self.play_btn.config(bg="#90EE90", text="▶ Play")
        self.frame_slider.config(to=0)
        self.csv_label.config(text="Coach Lineout Formation", fg="#e0e0e0")
        self._draw_frame()

    def _generate_coach_lineout(self) -> dict[str, tuple[float, float]]:
        """
        Generate coach-designed lineout formation:
        - 1, 2 throwing in
        - 3, 4, 5, 6, 7, 8 in lineout (vertically aligned)
        - Backs: 9 at back of lineout, 11 on wing, 10/12/13/15/14 fanned out
        """
        positions = {}

        # HOME TEAM (left side, attacking right)
        home_lineout_x = 25  # lineout formation x-position
        # Lineout backs (vertically along touchline direction)
        home_lineout_y = [25, 32, 39, 46, 53, 60]  # 6 players in line
        lineout_pids = ["3", "4", "5", "6", "7", "8"]
        for pid, y in zip(lineout_pids, home_lineout_y):
            positions[f"home_{pid}"] = (home_lineout_x, y)

        # 1, 2 at side of lineout (throwing in)
        positions["home_1"] = (home_lineout_x - 3, 25)  # loosehead prop
        positions["home_2"] = (home_lineout_x - 3, 32)  # hooker (next to 3)

        # Backs
        back_x = home_lineout_x + 8  # behind the lineout
        positions["home_9"] = (back_x, 43)  # Scrum-half at back of lineout
        positions["home_11"] = (back_x - 2, 68)  # Left wing on wing

        # Backs fanned out: 10, 12, 13, 15, 14
        positions["home_10"] = (back_x + 2, 55)  # Fly-half
        positions["home_12"] = (back_x + 4, 60)  # Inside centre
        positions["home_13"] = (back_x + 6, 58)  # Outside centre
        positions["home_15"] = (back_x + 8, 36)  # Fullback
        positions["home_14"] = (back_x + 2, 70)  # Right wing

        # AWAY TEAM (right side, attacking left)
        away_lineout_x = self.pitch_length - 25
        # Lineout forwards (same y-positions)
        away_lineout_y = [25, 32, 39, 46, 53, 60]
        for pid, y in zip(lineout_pids, away_lineout_y):
            positions[f"away_{pid}"] = (away_lineout_x, y)

        # 1, 2 at side of lineout
        positions["away_1"] = (away_lineout_x + 3, 25)
        positions["away_2"] = (away_lineout_x + 3, 32)

        # Backs
        back_x_away = away_lineout_x - 8
        positions["away_9"] = (back_x_away, 43)
        positions["away_11"] = (back_x_away + 2, 68)

        positions["away_10"] = (back_x_away - 2, 55)
        positions["away_12"] = (back_x_away - 4, 60)
        positions["away_13"] = (back_x_away - 6, 58)
        positions["away_15"] = (back_x_away - 8, 36)
        positions["away_14"] = (back_x_away - 2, 70)

        return positions

    def _load_custom_formation(self) -> None:
        """Load custom formation from JSON file."""
        path = filedialog.askopenfilename(
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            initialfile="lineout_formation.json",
        )
        if not path:
            return

        try:
            data = json.loads(Path(path).read_text())
            raw_positions = data.get("positions", {})
            self.player_positions = {pid: self._normalize_position(pos) for pid, pos in raw_positions.items()}
            self.keyframes = data.get("keyframes", [])
            ball_pos = data.get("ball", (50.0, 36.5, 1.0))
            # Ensure ball height is at least 1m
            if isinstance(ball_pos, (list, tuple)) and len(ball_pos) >= 3:
                x, y, z = ball_pos
                ball_pos = (x, y, max(1.0, z))
            elif isinstance(ball_pos, (list, tuple)) and len(ball_pos) == 2:
                x, y = ball_pos
                ball_pos = (x, y, 1.0)
            self.ball_position = ball_pos
            self.selected_player = data.get("selected_player")
            self.df = None
            self.frame_idx = 0
            self.is_playing = False
            self.play_btn.config(bg="#27ae60", text="▶ Play")
            self.frame_slider.config(to=max(0, (len(self.keyframes) - 1) * 10) if self.keyframes else 0)
            self.csv_label.config(text=f"Custom: {Path(path).name}", fg="#e0e0e0")
            self._draw_frame()
            messagebox.showinfo("Success", f"Loaded formation from {Path(path).name}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load formation: {e}")

    def _load_csv(self) -> None:
        """Load tracking CSV."""
        path = filedialog.askopenfilename(
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            initialfile="10511_tracking.csv",
        )
        if not path:
            return

        try:
            self.df = pd.read_csv(path, low_memory=False)
            self.frame_idx = 0
            self.player_positions = {}

            # Extract player IDs
            self.player_ids = [c[:-2] for c in self.df.columns if c.endswith("_x") and c != "ball_x"]
            self.player_ids = sorted(self.player_ids, key=lambda s: (s.isdigit(), int(s) if s.isdigit() else s))

            # Update slider
            max_frames = len(self.df)
            self.frame_slider.config(to=max_frames - 1)

            self.csv_label.config(text=f"Loaded: {Path(path).name}", fg="#e0e0e0")
            self._draw_frame()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load CSV: {e}")

    def _draw_frame(self) -> None:
        """Draw current frame with tracking data or static positions."""
        self.canvas.delete("all")
        self._draw_pitch()

        # Handle keyframes and interpolation
        if self.keyframes and not (self.dragging_player or self.dragging_ball):
            self._interpolate_positions()

        if self.df is None:
            # Draw static positions
            if self.player_positions:
                self.frame_label.config(text="Static Formation")
                for pid, pos in self.player_positions.items():
                    x, y, z = self._normalize_position(pos)
                    x_px = x * self.scale
                    y_px = (y - z * 0.5) * self.scale  # Offset y by z height for visual jumping effect
                    if pid.startswith("home_"):
                        color = "#ff9933"
                    else:
                        color = "#ffffff"
                    outline_color = "yellow" if pid == self.selected_player else "black"
                    self.canvas.create_oval(x_px - 4, y_px - 4, x_px + 4, y_px + 4, fill=color, outline=outline_color, width=2)
                    # Draw label and Z height
                    label = pid.split("_")[1]
                    if abs(z) > 0.01:
                        label += f" {z:.1f}m"
                    self.canvas.create_text(x_px, y_px - 10, text=label, fill="white", font=("Arial", 8))

                # Draw ball
                bx, by, bz = self._normalize_position(self.ball_position)
                bx_px = bx * self.scale
                by_px = (by - bz * 0.5) * self.scale  # Offset y by z height for visual effect
                outline_color = "yellow" if self.selected_ball else "orange"
                self.canvas.create_oval(bx_px - 4, by_px - 4, bx_px + 4, by_px + 4, fill="#ffdc00", outline=outline_color, width=2)
                # Draw ball label and Z height
                label = "Ball"
                if abs(bz) > 0.01:
                    label += f" {bz:.1f}m"
                self.canvas.create_text(bx_px, by_px - 10, text=label, fill="white", font=("Arial", 8))
            else:
                self.frame_label.config(text="No Formation Loaded")
            return

        if self.frame_idx >= len(self.df):
            return

        row = self.df.iloc[self.frame_idx]
        self.frame_label.config(text=f"Frame: {self.frame_idx}/{len(self.df) - 1}")

        # Draw ball
        bx, by = row.get("ball_x"), row.get("ball_y")
        if pd.notna(bx) and pd.notna(by):
            bx_px = float(bx) * self.scale
            by_px = float(by) * self.scale
            self.canvas.create_oval(
                bx_px - 4, by_px - 4, bx_px + 4, by_px + 4, fill="#ffdc00", outline="orange", width=2
            )

        # Draw players
        for pid in self.player_ids:
            x_col, y_col = f"{pid}_x", f"{pid}_y"
            if x_col not in self.df.columns or y_col not in self.df.columns:
                continue
            px, py = row.get(x_col), row.get(y_col)
            if pd.isna(px) or pd.isna(py):
                continue
            px_px = float(px) * self.scale
            py_px = float(py) * self.scale
            self.canvas.create_oval(px_px - 3, py_px - 3, px_px + 3, py_px + 3, fill="#cccccc", outline="white", width=1)

    def _interpolate_positions(self) -> None:
        """Interpolate positions between keyframes."""
        if not self.keyframes:
            return

        num_keyframes = len(self.keyframes)

        # If exactly on a keyframe and not playing, show exact positions for editing
        if not self.is_playing and self.current_time == int(self.current_time):
            kf_idx = int(self.current_time)
            if kf_idx < num_keyframes:
                self.player_positions = {pid: self._normalize_position(pos) for pid, pos in self.keyframes[kf_idx]['positions'].items()}
                self.ball_position = tuple(self.keyframes[kf_idx]['ball'])
                self.selected_player = self.keyframes[kf_idx].get('selected_player')
            return

        if num_keyframes == 1:
            self.player_positions = {pid: self._normalize_position(pos) for pid, pos in self.keyframes[0]['positions'].items()}
            self.ball_position = tuple(self.keyframes[0]['ball'])
            self.selected_player = self.keyframes[0].get('selected_player')
            return

        # Find segment
        segment = int(self.current_time)
        if segment >= num_keyframes - 1:
            self.player_positions = {pid: self._normalize_position(pos) for pid, pos in self.keyframes[-1]['positions'].items()}
            self.ball_position = tuple(self.keyframes[-1]['ball'])
            self.selected_player = self.keyframes[-1].get('selected_player')
            return

        t = self.current_time - segment
        pos1 = self.keyframes[segment]['positions']
        pos2 = self.keyframes[segment + 1]['positions']
        ball1 = self.keyframes[segment]['ball']
        ball2 = self.keyframes[segment + 1]['ball']

        # Interpolate positions
        self.player_positions = {}
        all_ids = set(pos1) | set(pos2)
        for pid in all_ids:
            if pid in pos1 and pid in pos2:
                x1, y1, z1 = self._normalize_position(pos1[pid])
                x2, y2, z2 = self._normalize_position(pos2[pid])
                self.player_positions[pid] = (
                    self._lerp(x1, x2, t),
                    self._lerp(y1, y2, t),
                    self._lerp(z1, z2, t),
                )
            elif pid in pos1:
                self.player_positions[pid] = self._normalize_position(pos1[pid])
            else:
                self.player_positions[pid] = self._normalize_position(pos2[pid])

        # Interpolate ball
        b1 = self._normalize_position(ball1 if len(ball1) >= 3 else (ball1[0], ball1[1], 0.0))
        b2 = self._normalize_position(ball2 if len(ball2) >= 3 else (ball2[0], ball2[1], 0.0))
        self.ball_position = (
            self._lerp(b1[0], b2[0], t),
            self._lerp(b1[1], b2[1], t),
            self._lerp(b1[2], b2[2], t),
        )

        # Set selected player to the one from the starting keyframe of the segment
        self.selected_player = self.keyframes[segment].get('selected_player')

    def _update_current_keyframe(self) -> None:
        """Update the current keyframe with current positions if exactly on a keyframe."""
        if self.keyframes and not self.is_playing and self.current_time == int(self.current_time):
            kf_idx = int(self.current_time)
            if kf_idx < len(self.keyframes):
                self.keyframes[kf_idx]['positions'] = dict(self.player_positions)
                self.keyframes[kf_idx]['ball'] = self.ball_position
                self.keyframes[kf_idx]['selected_player'] = self.selected_player

    def _build_interpolated_timeline(self, steps_per_segment: int = 10) -> list[dict]:
        timeline: list[dict] = []
        if not self.keyframes:
            return timeline

        # Start with the first keyframe
        first = self.keyframes[0]
        timeline.append({
            "type": "keyframe",
            "frame": 0.0,
            "positions": first["positions"],
            "ball": first["ball"],
            "selected_player": first.get("selected_player"),
        })

        for idx in range(len(self.keyframes) - 1):
            current = self.keyframes[idx]
            nex = self.keyframes[idx + 1]
            positions0 = current["positions"]
            positions1 = nex["positions"]
            ball0 = current["ball"]
            ball1 = nex["ball"]
            all_ids = set(positions0) | set(positions1)

            for step in range(1, steps_per_segment + 1):
                alpha = step / steps_per_segment
                frame_time = idx + alpha
                positions: dict[str, tuple[float, float, float]] = {}
                for pid in all_ids:
                    if pid in positions0 and pid in positions1:
                        x0, y0, z0 = self._normalize_position(positions0[pid])
                        x1, y1, z1 = self._normalize_position(positions1[pid])
                        positions[pid] = (
                            self._lerp(x0, x1, alpha),
                            self._lerp(y0, y1, alpha),
                            self._lerp(z0, z1, alpha),
                        )
                    elif pid in positions0:
                        positions[pid] = self._normalize_position(positions0[pid])
                    else:
                        positions[pid] = self._normalize_position(positions1[pid])

                b0 = self._normalize_position(ball0 if len(ball0) >= 3 else (ball0[0], ball0[1], 0.0))
                b1 = self._normalize_position(ball1 if len(ball1) >= 3 else (ball1[0], ball1[1], 0.0))
                ball = (
                    self._lerp(b0[0], b1[0], alpha),
                    self._lerp(b0[1], b1[1], alpha),
                    self._lerp(b0[2], b1[2], alpha),
                )
                timeline.append({
                    "type": "keyframe" if alpha == 1.0 else "interpolated",
                    "frame": frame_time,
                    "positions": positions,
                    "ball": ball,
                    "selected_player": nex.get("selected_player") if alpha == 1.0 else None,
                })

        return timeline

    def _toggle_recording(self) -> None:
        """Toggle recording mode for keyframes."""
        if self.df is None and not self.player_positions:
            messagebox.showwarning("Warning", "Load a formation first (Lineout)")
            return

        self.is_recording = not self.is_recording
        if self.is_recording:
            self.keyframes = []
            self._capture_frame()  # Capture initial state
            self.record_btn.config(bg="#ff6666", text="Stop Recording")
        else:
            self.record_btn.config(bg="#ffcccc", text="Start Recording")

    def _capture_frame(self) -> None:
        """Capture current player positions and ball as a keyframe."""
        if not self.player_positions:
            messagebox.showwarning("Warning", "No player positions to capture")
            return

        keyframe = {
            'positions': dict(self.player_positions),
            'ball': self.ball_position,
            'selected_player': self.selected_player
        }
        self.keyframes.append(keyframe)
        self.record_label.config(text=f"Keyframes: {len(self.keyframes)}", fg="#e74c3c")
        messagebox.showinfo("Captured", f"Keyframe {len(self.keyframes)} captured")

        # Update slider
        if len(self.keyframes) > 1:
            self.frame_slider.config(to=(len(self.keyframes) - 1) * 10)

    def _undo_keyframe(self) -> None:
        """Remove the last keyframe."""
        if self.keyframes:
            self.keyframes.pop()
            self.record_label.config(text=f"Keyframes: {len(self.keyframes)}", fg="#e74c3c")
            if self.keyframes:
                # Show previous keyframe
                self.player_positions = dict(self.keyframes[-1]["positions"])
                self.ball_position = self.keyframes[-1]["ball"]
                self.selected_player = self.keyframes[-1].get('selected_player')
                self.frame_slider.config(to=max(0, (len(self.keyframes) - 1) * 10))
            else:
                self.frame_slider.config(to=0)
            self._draw_frame()

    def _toggle_play(self) -> None:
        """Toggle playback."""
        if self.keyframes:
            self.is_playing = not self.is_playing
            self.play_btn.config(bg="#90EE90" if not self.is_playing else "#FFB6C6")
            self.play_btn.config(text="▶ Play" if not self.is_playing else "⏸ Pause")
            self.frame_slider.config(to=max(0, (len(self.keyframes) - 1) * 10))
            if self.is_playing:
                self.current_time = 0.0
                self._play_loop()
            return

        # Otherwise use CSV data if available
        if self.df is None:
            messagebox.showwarning("Warning", "Load a CSV or record keyframes first")
            return

        self.is_playing = not self.is_playing
        self.play_btn.config(bg="#90EE90" if not self.is_playing else "#FFB6C6")
        self.play_btn.config(text="▶ Play" if not self.is_playing else "⏸ Pause")

        if self.is_playing:
            self._play_loop()

    def _play_loop(self) -> None:
        """Play through frames."""
        if not self.is_playing:
            return

        if self.keyframes:
            if self.current_time < len(self.keyframes) - 1:
                self.current_time += 0.1
                self.frame_slider.set(int(self.current_time * 10))
                self._draw_frame()
                self.root.after(1000, self._play_loop)  # ~20 FPS
            else:
                self.is_playing = False
                self.play_btn.config(bg="#90EE90", text="▶ Play")
            return

        # Playing CSV data
        if self.df is None:
            return

        if self.frame_idx < len(self.df) - 1:
            self.frame_idx += 1
            self.frame_slider.set(self.frame_idx)
            self._draw_frame()
            self.root.after(1000, self._play_loop)  # ~20 FPS
        else:
            self.is_playing = False
            self.play_btn.config(bg="#90EE90", text="▶ Play")

    def _next_frame(self) -> None:
        """Go to next frame."""
        if self.keyframes:
            if self.current_time < len(self.keyframes) - 1:
                self.current_time = min(self.current_time + 1, len(self.keyframes) - 1)
                self.frame_slider.set(int(self.current_time * 10))
                self.selected_player = self.keyframes[int(self.current_time)].get('selected_player')
                self._draw_frame()
            return

        if self.df is None:
            return
        if self.frame_idx < len(self.df) - 1:
            self.frame_idx += 1
            self.frame_slider.set(self.frame_idx)
            self._draw_frame()

    def _prev_frame(self) -> None:
        """Go to previous frame."""
        if self.keyframes:
            if self.current_time > 0:
                self.current_time = max(self.current_time - 1, 0)
                self.frame_slider.set(int(self.current_time * 10))
                self.selected_player = self.keyframes[int(self.current_time)].get('selected_player')
                self._draw_frame()
            return

        if self.df is None:
            return
        if self.frame_idx > 0:
            self.frame_idx -= 1
            self.frame_slider.set(self.frame_idx)
            self._draw_frame()

    def _on_slider_change(self, val) -> None:
        """Handle slider change."""
        if self.keyframes:
            self.current_time = float(val) / 10.0
            # Set selected player based on current segment
            segment = int(self.current_time)
            if segment < len(self.keyframes):
                self.selected_player = self.keyframes[segment].get('selected_player')
            self._draw_frame()
            return

        self.frame_idx = int(float(val))
        self._draw_frame()

    def _select_team(self, team: str) -> None:
        """Select active team for annotation."""
        self.current_team = team
        team_name = "Home" if team == "home" else "Away"
        self.team_label.config(text=f"Active: {team_name}")

    def _on_canvas_press(self, event) -> None:
        """Start dragging player or ball."""
        if self.df is None and self.player_positions:
            # Check for ball
            bx, by, bz = self._normalize_position(self.ball_position)
            bx_px = bx * self.scale
            by_px = (by - bz * 0.5) * self.scale  # Use same offset as drawing
            dist_ball = ((event.x - bx_px) ** 2 + (event.y - by_px) ** 2) ** 0.5
            if dist_ball < 10:
                self.dragging_ball = True
                self.selected_ball = True
                self.selected_player = None
                return

            # Check for players
            for pid, pos in self.player_positions.items():
                x, y, _ = self._normalize_position(pos)
                x_px = x * self.scale
                y_px = y * self.scale
                dist = ((event.x - x_px) ** 2 + (event.y - y_px) ** 2) ** 0.5
                if dist < 10:
                    self.dragging_player = pid
                    self.selected_player = pid
                    self.selected_ball = False
                    return

    def _on_canvas_drag(self, event) -> None:
        """Continue dragging player or ball."""
        if self.dragging_ball:
            _, _, z = self._normalize_position(self.ball_position)
            self.ball_position = (event.x / self.scale, event.y / self.scale, z)
            self._draw_frame()
            return

        if self.dragging_player:
            x = event.x / self.scale
            y = event.y / self.scale
            _, _, z = self._normalize_position(self.player_positions[self.dragging_player])
            self.player_positions[self.dragging_player] = (x, y, z)
            self._draw_frame()
            return

    def _on_canvas_scroll(self, event) -> None:
        """Adjust the selected player's or ball's height while scrolling."""
        if hasattr(event, "delta") and event.delta != 0:
            delta_z = (event.delta / 120.0) * 0.1
        elif getattr(event, "num", None) == 4:
            delta_z = 0.1
        elif getattr(event, "num", None) == 5:
            delta_z = -0.1
        else:
            return

        # Prefer ball adjustment if the mouse is over the ball or the ball is selected.
        bx, by, bz = self._normalize_position(self.ball_position)
        bx_px = bx * self.scale
        by_px = (by - bz * 0.5) * self.scale  # Use same offset as drawing
        dist_ball = ((event.x - bx_px) ** 2 + (event.y - by_px) ** 2) ** 0.5
        if self.dragging_ball or self.selected_ball or dist_ball < 12:
            x, y, z = self._normalize_position(self.ball_position)
            z = max(1.0, z + delta_z)  # Minimum height of 1m for ball
            self.ball_position = (x, y, z)
            self.selected_ball = True
            self.selected_player = None
            self._update_current_keyframe()
            self._draw_frame()
            return

        pid = self.dragging_player or self.selected_player
        if not pid or pid not in self.player_positions:
            return

        x, y, z = self._normalize_position(self.player_positions[pid])
        z = max(0.0, z + delta_z)
        self.player_positions[pid] = (x, y, z)
        self._update_current_keyframe()
        self._draw_frame()
        return

    def _on_canvas_release(self, event) -> None:
        """Finish dragging."""
        if self.dragging_ball:
            self.dragging_ball = False
            self.selected_ball = True
            self._update_current_keyframe()
            self._draw_frame()
            return

        if self.dragging_player:
            self.dragging_player = None
            self._update_current_keyframe()
            self._draw_frame()
            return


    def _draw_arrow_path(self, path, color):
        """Draw path with arrow at end."""
        if len(path) < 2:
            return

        coords = [c * self.scale for p in path for c in p]

        self.canvas.create_line(
            *coords,
            fill=color,
            width=3,
            smooth=True,
            arrow="last",
            arrowshape=(12, 14, 6),
        )

    def _clear_frame(self) -> None:
        """Clear annotation for current frame."""
        self.annotations = [a for a in self.annotations if a["frame"] != self.frame_idx]
        self._draw_frame()

    def _save_annotations(self) -> None:
        """Save annotations to JSON."""
        path = fd.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            initialfile="direction_annotations.json",
        )
        if not path:
            return

        data = {"annotations": self.annotations, "scale": self.scale}
        Path(path).write_text(json.dumps(data, indent=2))
        messagebox.showinfo("Success", f"Saved to {path}")

    def _load_annotations(self) -> None:
        """Load annotations from JSON."""
        path = fd.askopenfilename(
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if not path:
            return

        try:
            data = json.loads(Path(path).read_text())
            self.annotations = data.get("annotations", [])
            self._draw_frame()
            messagebox.showinfo("Success", f"Loaded from {path}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load: {e}")

    def _export_positions(self) -> None:
        """Export current player positions to JSON."""
        if not self.player_positions:
            messagebox.showwarning("Warning", "No positions to export")
            return

        path = fd.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            initialfile="rugby_formation.json",
        )
        if not path:
            return

        # Convert positions to serializable format
        data = {
            "positions": self.player_positions,
            "keyframes": self.keyframes,
            "ball": self.ball_position,
            "selected_player": self.selected_player,
            "scale": self.scale,
            "pitch_length": self.pitch_length,
            "pitch_width": self.pitch_width,
        }
        Path(path).write_text(json.dumps(data, indent=2))
        messagebox.showinfo("Success", f"Positions saved to {path}\n\nShare this file at work!")

    def _show_positions(self) -> None:
        """Display current positions in a readable format."""
        if not self.player_positions:
            messagebox.showinfo("Positions", "No positions set")
            return

        # Sort by team, then by player
        home_pos = sorted([(p[5:], self._normalize_position(pos)) for p, pos in self.player_positions.items() if p.startswith("home_")])
        away_pos = sorted([(p[5:], self._normalize_position(pos)) for p, pos in self.player_positions.items() if p.startswith("away_")])

        msg = "HOME TEAM:\n"
        for pid, (x, y, z) in home_pos:
            msg += f"  {pid:<3}: x={x:6.2f}, y={y:6.2f}, z={z:5.2f}\n"

        msg += "\nAWAY TEAM:\n"
        for pid, (x, y, z) in away_pos:
            msg += f"  {pid:<3}: x={x:6.2f}, y={y:6.2f}, z={z:5.2f}\n"

        # Create a window with scrollable text
        from tkinter import Toplevel, Text, Scrollbar
        win = Toplevel(self.root)
        win.title("Current Positions")
        win.geometry("400x500")

        scrollbar = Scrollbar(win)
        scrollbar.pack(side="right", fill="y")

        text_widget = Text(win, yscrollcommand=scrollbar.set, font=("Courier", 9))
        text_widget.pack(fill="both", expand=True, padx=5, pady=5)
        scrollbar.config(command=text_widget.yview)

        text_widget.insert("1.0", msg)
        text_widget.config(state="disabled")

    def _save_animation(self) -> None:
        """Save recorded keyframes to JSON."""
        if not self.keyframes:
            messagebox.showwarning("Warning", "No animation to save")
            return

        path = fd.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            initialfile="rugby_animation.json",
        )
        if not path:
            return

        data = {
            "keyframes": self.keyframes,
            "scale": self.scale,
            "pitch_length": self.pitch_length,
            "pitch_width": self.pitch_width,
        }
        Path(path).write_text(json.dumps(data, indent=2))
        messagebox.showinfo("Success", f"Animation saved to {Path(path).name}")

    def _load_animation(self) -> None:
        """Load animation from JSON."""
        path = fd.askopenfilename(
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            initialfile="rugby_animation.json",
        )
        if not path:
            return

        try:
            data = json.loads(Path(path).read_text())
            self.keyframes = data.get("keyframes", [])
            # Ensure all ball positions in keyframes have minimum 1m height
            for kf in self.keyframes:
                ball_pos = kf.get("ball", (50.0, 36.5, 1.0))
                if isinstance(ball_pos, (list, tuple)) and len(ball_pos) >= 3:
                    x, y, z = ball_pos
                    kf["ball"] = (x, y, max(1.0, z))
                elif isinstance(ball_pos, (list, tuple)) and len(ball_pos) == 2:
                    x, y = ball_pos
                    kf["ball"] = (x, y, 1.0)
            self.df = None
            self.frame_idx = 0
            self.current_time = 0.0
            self.is_playing = False
            self.play_btn.config(bg="#27ae60", text="▶ Play")
            self.frame_slider.config(to=max(0, (len(self.keyframes) - 1) * 10) if self.keyframes else 0)
            self.record_label.config(text=f"Keyframes: {len(self.keyframes)}", fg="#e74c3c")
            if self.keyframes:
                self.player_positions = {pid: self._normalize_position(pos) for pid, pos in self.keyframes[0]["positions"].items()}
                self.ball_position = self.keyframes[0]["ball"]
                self.selected_player = self.keyframes[0].get('selected_player')
            self._draw_frame()
            messagebox.showinfo("Success", f"Loaded animation with {len(self.keyframes)} keyframes")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load animation: {e}")

    def _export_rerun(self):
        """Export keyframes as structured event stream for Rerun."""
        if not self.keyframes:
            messagebox.showwarning("Warning", "No keyframes to export")
            return

        path = fd.asksaveasfilename(
            defaultextension=".json",
            initialfile="rerun_animation.json",
            filetypes=[("JSON files", "*.json")]
        )
        if not path:
            return

        timeline = self._build_interpolated_timeline(steps_per_segment=10)

        data = {
            "metadata": {
                "pitch_length": self.pitch_length,
                "pitch_width": self.pitch_width,
                "scale": self.scale,
            },
            "timeline": timeline,
        }

        Path(path).write_text(json.dumps(data, indent=2))
        messagebox.showinfo("Exported", f"Rerun export saved:\n{path}")

    # Snapping Logic
    def _snap_to_player(self, x: float, y: float) -> tuple[float, float]:
        """Snap a point to nearest player if within radius."""
        closest = None
        best_dist = self.snap_radius

        for px, py in self.player_positions.values():
            d = ((x - px) ** 2 + (y - py) ** 2) ** 0.5
            if d < best_dist:
                best_dist = d
                closest = (px, py)

        return closest if closest else (x, y)


    def _snap_to_grid(self, x: float, y: float) -> tuple[float, float]:
        """Snap to grid."""
        if not self.grid_snap:
            return x, y
        gx = round(x / self.grid_snap) * self.grid_snap
        gy = round(y / self.grid_snap) * self.grid_snap
        return gx, gy


    def _snap_point(self, x: float, y: float) -> tuple[float, float]:
        """Combined snapping."""
        x, y = self._snap_to_player(x, y)
        x, y = self._snap_to_grid(x, y)
        return x, y


if __name__ == "__main__":
    root = Tk()
    app = RugbyDirectionAnnotator(root)
    root.mainloop()
