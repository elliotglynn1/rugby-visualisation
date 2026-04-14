"""Rugby Formation Annotation and Rerun Visualization App - PyQt6."""

import json
import subprocess
import sys
from pathlib import Path
from typing import Optional
import math

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QPushButton,
    QSlider, QLabel, QFileDialog, QMessageBox, QApplication, QListWidget,
    QListWidgetItem, QSpinBox
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QPoint
from PyQt6.QtGui import QPainter, QPen, QColor, QFont, QBrush, QMouseEvent, QWheelEvent


class RugbyPitchCanvas(QWidget):
    """Custom widget for drawing and interacting with rugby pitch and players."""

    player_moved = pyqtSignal()
    ball_moved = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)

        # Pitch dimensions
        self.pitch_length = 100
        self.pitch_width = 73
        self.scale = 10  # Increased from 8 to make pitch bigger

        self.canvas_width = int(self.pitch_length * self.scale)
        self.canvas_height = int(self.pitch_width * self.scale)
        self.setMinimumSize(self.canvas_width + 40, self.canvas_height + 40)
        self.setStyleSheet("background-color: white;")  # White background instead of green

        # Player and ball state
        self.player_positions = {}
        self.ball_position = (50.0, 36.5, 1.0)
        self.selected_player = None
        self.selected_ball = False

        # Dragging state
        self.dragging_player = None
        self.dragging_ball = False
        self.offset_x = 20
        self.offset_y = 20
        
        # Camera follow mode
        self.follow_target = None  # None, "ball", or player id like "home_1"
        self.camera_distance = 15  # pixels from center when following

        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def set_player_positions(self, positions):
        self.player_positions = positions
        self.update()

    def set_ball_position(self, pos):
        self.ball_position = pos
        self.update()

    def set_selected_player(self, pid):
        self.selected_player = pid
        self.follow_target = pid  # Follow the selected player
        self.update()
    
    def set_follow_target(self, target):
        """Set follow target: None (full pitch), 'ball', or player id."""
        self.follow_target = target
        self.selected_player = target if target and target != "ball" else None
        self.selected_ball = (target == "ball")
        self.update()

    def get_canvas_pos(self, x, y):
        """Screen to canvas coordinates."""
        return (x - self.offset_x) / self.scale, (y - self.offset_y) / self.scale
    
    def get_event_pos(self, event):
        """Get mouse position from QMouseEvent."""
        pos = event.position()
        return int(pos.x()), int(pos.y())

    def paintEvent(self, event):
        """Draw the rugby pitch and elements."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # White background
        painter.fillRect(self.rect(), QColor(255, 255, 255))

        # Calculate camera offset based on follow target
        if self.follow_target == "ball":
            bx, by, bz = self.ball_position if len(self.ball_position) >= 3 else (self.ball_position[0], self.ball_position[1], 1.0)
            by_offset = by - bz * 0.5
            self.offset_x = int(self.width() / 2 - bx * self.scale)
            self.offset_y = int(self.height() / 2 - by_offset * self.scale)
        elif self.follow_target and self.follow_target in self.player_positions:
            pos = self.player_positions[self.follow_target]
            x, y, z = pos if len(pos) >= 3 else (pos[0], pos[1], 0.0)
            y_offset = y - z * 0.5
            self.offset_x = int(self.width() / 2 - x * self.scale)
            self.offset_y = int(self.height() / 2 - y_offset * self.scale)
        else:
            # Full field view
            self.offset_x = 20
            self.offset_y = 20

        # Green pitch
        painter.fillRect(
            int(self.offset_x), int(self.offset_y),
            int(self.canvas_width), int(self.canvas_height),
            QBrush(QColor(34, 139, 34))
        )
        painter.drawRect(
            self.offset_x, self.offset_y,
            self.canvas_width, self.canvas_height
        )

        # Try lines
        try_x = int(5 * self.scale)
        painter.setPen(QPen(QColor(255, 255, 255), 1))
        painter.drawLine(int(self.offset_x + try_x), int(self.offset_y), int(self.offset_x + try_x), int(self.offset_y + self.canvas_height))
        painter.drawLine(int(self.offset_x + self.canvas_width - try_x), int(self.offset_y), int(self.offset_x + self.canvas_width - try_x), int(self.offset_y + self.canvas_height))

        # 22m lines
        line22_x = int(22 * self.scale)
        painter.setPen(QPen(QColor(255, 255, 255), 1, Qt.PenStyle.DashLine))
        painter.drawLine(int(self.offset_x + line22_x), int(self.offset_y), int(self.offset_x + line22_x), int(self.offset_y + self.canvas_height))
        painter.drawLine(int(self.offset_x + self.canvas_width - line22_x), int(self.offset_y), int(self.offset_x + self.canvas_width - line22_x), int(self.offset_y + self.canvas_height))

        # Halfway line
        mid_x = int(self.offset_x + self.canvas_width / 2)
        painter.setPen(QPen(QColor(255, 255, 255), 2))
        painter.drawLine(mid_x, int(self.offset_y), mid_x, int(self.offset_y + self.canvas_height))

        # Draw players
        for pid, pos in self.player_positions.items():
            x, y, z = pos if len(pos) >= 3 else (pos[0], pos[1], 0.0)
            x_px = int(x * self.scale + self.offset_x)
            y_px = int((y - z * 0.5) * self.scale + self.offset_y)

            color = QColor(255, 153, 51) if pid.startswith("home_") else QColor(255, 255, 255)
            outline = QColor(255, 255, 0) if pid == self.selected_player else QColor(0, 0, 0)

            painter.setBrush(QBrush(color))
            painter.setPen(QPen(outline, 2))
            painter.drawEllipse(x_px - 4, y_px - 4, 8, 8)

            label = pid.split("_")[1]
            if abs(z) > 0.01:
                label += f" {z:.1f}m"
            painter.setPen(QColor(255, 255, 255))
            painter.setFont(QFont("Arial", 8))
            painter.drawText(x_px - 10, y_px - 15, 30, 15, Qt.AlignmentFlag.AlignCenter, label)

        # Draw ball
        bx, by, bz = self.ball_position if len(self.ball_position) >= 3 else (self.ball_position[0], self.ball_position[1], 1.0)
        bx_px = int(bx * self.scale + self.offset_x)
        by_px = int((by - bz * 0.5) * self.scale + self.offset_y)

        outline = QColor(255, 255, 0) if self.selected_ball else QColor(255, 165, 0)
        painter.setBrush(QBrush(QColor(255, 220, 0)))
        painter.setPen(QPen(outline, 2))
        painter.drawEllipse(bx_px - 4, by_px - 4, 8, 8)

        label = "Ball"
        if abs(bz) > 0.01:
            label += f" {bz:.1f}m"
        painter.setPen(QColor(255, 255, 255))
        painter.setFont(QFont("Arial", 8))
        painter.drawText(bx_px - 15, by_px - 15, 35, 15, Qt.AlignmentFlag.AlignCenter, label)

    def mousePressEvent(self, event: QMouseEvent):
        """Handle mouse press."""
        try:
            x, y = self.get_event_pos(event)
            cx, cy = self.get_canvas_pos(x, y)

            # Check ball
            bx = self.ball_position[0]
            by = self.ball_position[1]
            bz = self.ball_position[2] if len(self.ball_position) >= 3 else 1.0
            by_offset = by - bz * 0.5
            dist_ball = math.sqrt((cx - bx) ** 2 + (cy - by_offset) ** 2)
            if dist_ball < 1.5:
                self.dragging_ball = True
                self.selected_ball = True
                self.selected_player = None
                self.update()
                return

            # Check players
            for pid, pos in self.player_positions.items():
                x = pos[0]
                y = pos[1]
                z = pos[2] if len(pos) >= 3 else 0.0
                y_offset = y - z * 0.5
                dist = math.sqrt((cx - x) ** 2 + (cy - y_offset) ** 2)
                if dist < 1.5:
                    self.dragging_player = pid
                    self.selected_player = pid
                    self.selected_ball = False
                    self.update()
                    return
        except Exception as e:
            print(f"Error in mousePressEvent: {e}")

    def mouseMoveEvent(self, event: QMouseEvent):
        """Handle mouse drag."""
        try:
            # Get canvas position safely
            if event is None:
                return
            
            x, y = self.get_event_pos(event)
            cx, cy = self.get_canvas_pos(x, y)
            
            # Handle ball dragging
            if self.dragging_ball:
                if self.ball_position and len(self.ball_position) >= 2:
                    try:
                        bz = self.ball_position[2] if len(self.ball_position) >= 3 else 1.0
                        self.ball_position = (cx, cy, bz)
                        self.ball_moved.emit()
                        self.update()
                    except Exception as e:
                        print(f"Error updating ball position: {e}")
            
            # Handle player dragging
            elif self.dragging_player:
                if (self.player_positions and 
                    isinstance(self.player_positions, dict) and 
                    self.dragging_player in self.player_positions):
                    try:
                        pos = self.player_positions[self.dragging_player]
                        if pos and len(pos) >= 2:
                            z = pos[2] if len(pos) >= 3 else 0.0
                            self.player_positions[self.dragging_player] = (cx, cy, z)
                            self.player_moved.emit()
                            self.update()
                    except Exception as e:
                        print(f"Error updating player position: {e}")
        except Exception as e:
            print(f"Error in mouseMoveEvent: {e}")
            import traceback
            traceback.print_exc()

    def mouseReleaseEvent(self, event: QMouseEvent):
        """Handle mouse release."""
        try:
            self.dragging_player = None
            self.dragging_ball = False
        except Exception as e:
            print(f"Error in mouseReleaseEvent: {e}")

    def wheelEvent(self, event: QWheelEvent):
        """Handle scroll for height adjustment."""
        try:
            delta = event.angleDelta().y() / 120.0 * 0.1

            bx = self.ball_position[0]
            by = self.ball_position[1]
            bz = self.ball_position[2] if len(self.ball_position) >= 3 else 1.0
            by_offset = by - bz * 0.5
            x, y = self.get_event_pos(event)
            cx, cy = self.get_canvas_pos(x, y)

            dist_ball = math.sqrt((cx - bx) ** 2 + (cy - by_offset) ** 2)

            if self.selected_ball or dist_ball < 1.5:
                bz = max(1.0, bz + delta)
                self.ball_position = (bx, by, bz)
                self.ball_moved.emit()
                self.update()
                return

            if self.selected_player and self.selected_player in self.player_positions:
                pos = self.player_positions[self.selected_player]
                x = pos[0]
                y = pos[1]
                z = pos[2] if len(pos) >= 3 else 0.0
                z = max(0.0, z + delta)
                self.player_positions[self.selected_player] = (x, y, z)
                self.player_moved.emit()
                self.update()
        except Exception as e:
            print(f"Error in wheelEvent: {e}")


class AnnotationTab(QWidget):
    """Main annotation interface with pitch and controls."""

    def __init__(self):
        super().__init__()
        layout = QHBoxLayout()

        # Left side: Canvas (takes up most of the space)
        self.canvas = RugbyPitchCanvas()
        layout.addWidget(self.canvas, stretch=4)

        # Right side: Controls panel
        controls_layout = QVBoxLayout()
        controls_layout.setSpacing(8)

        # Section 1: Formations
        form_label = QLabel("Formations")
        form_label.setStyleSheet("font-weight: bold; font-size: 12px;")
        controls_layout.addWidget(form_label)

        self.load_formation_btn = QPushButton("Load Formation")
        self.load_formation_btn.clicked.connect(self.load_formation)
        controls_layout.addWidget(self.load_formation_btn)

        self.save_formation_btn = QPushButton("Save Formation")
        self.save_formation_btn.clicked.connect(self.save_formation)
        controls_layout.addWidget(self.save_formation_btn)

        self.load_anim_btn = QPushButton("Load Animation")
        self.load_anim_btn.clicked.connect(self.load_animation)
        controls_layout.addWidget(self.load_anim_btn)

        self.save_btn = QPushButton("Save Animation")
        self.save_btn.clicked.connect(self.save_animation)
        controls_layout.addWidget(self.save_btn)

        # Section 2: Animations
        anim_label = QLabel("Animations")
        anim_label.setStyleSheet("font-weight: bold; font-size: 12px; margin-top: 15px;")
        controls_layout.addWidget(anim_label)

        # Section 3: Recording
        rec_label = QLabel("Recording")
        rec_label.setStyleSheet("font-weight: bold; font-size: 12px; margin-top: 15px;")
        controls_layout.addWidget(rec_label)

        self.record_btn = QPushButton("Record Keyframes")
        self.record_btn.clicked.connect(self.toggle_recording)
        controls_layout.addWidget(self.record_btn)

        self.capture_btn = QPushButton("Capture Frame")
        self.capture_btn.clicked.connect(self.capture_frame)
        controls_layout.addWidget(self.capture_btn)

        self.undo_btn = QPushButton("Undo")
        self.undo_btn.clicked.connect(self.undo_frame)
        controls_layout.addWidget(self.undo_btn)

        # Section 3: Rerun/Export
        rerun_label = QLabel("Rerun Export")
        rerun_label.setStyleSheet("font-weight: bold; font-size: 12px; margin-top: 15px;")
        controls_layout.addWidget(rerun_label)

        self.export_btn = QPushButton("Export to Rerun")
        self.export_btn.clicked.connect(self.export_rerun_dialog)
        controls_layout.addWidget(self.export_btn)

        # Viewpoint selection
        viewpoint_label = QLabel("Viewpoints")
        viewpoint_label.setStyleSheet("font-weight: bold; font-size: 10px; margin-top: 10px;")
        controls_layout.addWidget(viewpoint_label)

        # Full pitch button
        full_pitch_btn = QPushButton("Full Pitch")
        full_pitch_btn.clicked.connect(lambda: self.canvas.set_follow_target(None))
        controls_layout.addWidget(full_pitch_btn)

        self.viewpoint_buttons = []
        viewpoints = ["ball"] + [f"home_{i}" for i in range(1, 16)] + [f"away_{i}" for i in range(1, 16)]

        self.current_frame_index = 0
        self.play_timer = QTimer()
        self.play_timer.timeout.connect(self.next_frame)
        self.is_playing = False
                
        for i, viewpoint in enumerate(viewpoints):
            if i % 3 == 0:
                vp_row = QHBoxLayout()
            
            btn = QPushButton(viewpoint.replace("_", "\n"))
            btn.setMaximumWidth(60)
            btn.setMaximumHeight(40)
            btn.setStyleSheet("font-size: 8px;")
            btn.clicked.connect(lambda checked, vp=viewpoint: self.focus_and_view(vp))
            vp_row.addWidget(btn)
            self.viewpoint_buttons.append(btn)
            
            if (i + 1) % 3 == 0 or i == len(viewpoints) - 1:
                controls_layout.addLayout(vp_row)

        # Status
        controls_layout.addSpacing(15)
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("border: 1px solid #ccc; padding: 8px; background: #f0f0f0;")
        self.status_label.setWordWrap(True)
        controls_layout.addWidget(self.status_label)

        controls_layout.addStretch()

        # Add controls to main layout
        layout.addLayout(controls_layout, stretch=1)

        self.setLayout(layout)

        # State
        self.keyframes = []
        self.is_recording = False
        self.animation_path = None
        self.last_export_path = None

        self.play_btn = QPushButton("Play")
        self.play_btn.clicked.connect(self.toggle_playback)
        controls_layout.addWidget(self.play_btn)

        self.prev_btn = QPushButton("Prev Frame")
        self.prev_btn.clicked.connect(self.prev_frame)
        controls_layout.addWidget(self.prev_btn)

        self.next_btn = QPushButton("Next Frame")
        self.next_btn.clicked.connect(self.next_frame)
        controls_layout.addWidget(self.next_btn)

    def load_formation(self):
        """Load formation from JSON file."""
        path, _ = QFileDialog.getOpenFileName(self, "Load Formation", "", "JSON (*.json)")
        if not path:
            return
        
        data = json.loads(Path(path).read_text())
        positions = {}
        
        for pid, pos in data.get("positions", {}).items():
            positions[pid] = (pos[0], pos[1], 0.0)
        
        self.canvas.set_player_positions(positions)
        self.keyframes = []
        self.canvas.set_ball_position((50.0, 36.5, 1.0))
        self.status_label.setText(f"Loaded: {Path(path).stem} ({len(positions)} players)")
    
    def save_formation(self):
        """Save current formation to JSON file."""
        if not self.canvas.player_positions:
            QMessageBox.warning(self, "Warning", "No players to save")
            return
        
        path, _ = QFileDialog.getSaveFileName(self, "Save Formation", "", "JSON (*.json)")
        if not path:
            return
        
        data = {
            "positions": {pid: [pos[0], pos[1]] for pid, pos in self.canvas.player_positions.items()},
            "scale": 5,
            "pitch_length": 100,
            "pitch_width": 73
        }
        
        Path(path).write_text(json.dumps(data, indent=2))
        self.status_label.setText(f"Saved: {Path(path).name}")

    def toggle_recording(self):
        """Toggle recording mode."""
        self.is_recording = not self.is_recording
        if self.is_recording:
            self.keyframes = []
            self.record_btn.setStyleSheet("background-color: red;")
            self.status_label.setText("Recording...")
        else:
            self.current_frame_index = 0
            self.record_btn.setStyleSheet("")
            self.status_label.setText(f"Recorded: {len(self.keyframes)} keyframes")

    def toggle_playback(self):
        if not self.keyframes:
            QMessageBox.warning(self, "Warning", "No keyframes to play")
            return

        self.is_playing = not self.is_playing

        if self.is_playing:
            self.play_btn.setText("Pause")
            self.play_timer.start(100)  # 100ms per frame (~10 FPS)
        else:
            self.play_btn.setText("Play")
            self.play_timer.stop()

    def next_frame(self):
        if not self.keyframes:
            return

        self.current_frame_index += 1
        if self.current_frame_index >= len(self.keyframes):
            self.current_frame_index = 0  # loop

        self.show_frame(self.current_frame_index)

    def prev_frame(self):
        if not self.keyframes:
            return

        self.current_frame_index -= 1
        if self.current_frame_index < 0:
            self.current_frame_index = len(self.keyframes) - 1

        self.show_frame(self.current_frame_index)

    def show_frame(self, index):
        if not (0 <= index < len(self.keyframes)):
            return

        frame = self.keyframes[index]

        self.canvas.set_player_positions(frame.get("positions", {}))
        self.canvas.set_ball_position(frame.get("ball", (50.0, 36.5, 1.0)))

        self.status_label.setText(f"Frame {index + 1}/{len(self.keyframes)}")

    def capture_frame(self):
        """Capture current state as keyframe."""
        if not self.canvas.player_positions:
            QMessageBox.warning(self, "Warning", "No players to capture")
            return

        keyframe = {
            "positions": dict(self.canvas.player_positions),
            "ball": self.canvas.ball_position,
            "selected_player": self.canvas.selected_player
        }
        self.keyframes.append(keyframe)
        self.status_label.setText(f"Keyframes: {len(self.keyframes)}")

    def undo_frame(self):
        """Remove last keyframe."""
        if self.keyframes:
            self.keyframes.pop()
            self.status_label.setText(f"Keyframes: {len(self.keyframes)}")

    def save_animation(self):
        """Save animation to JSON."""
        if not self.keyframes:
            QMessageBox.warning(self, "Warning", "No keyframes to save")
            return

        path, _ = QFileDialog.getSaveFileName(self, "Save Animation", "", "JSON (*.json)")
        if not path:
            return

        data = {
            "keyframes": self.keyframes,
            "scale": 8,
            "pitch_length": 100,
            "pitch_width": 73,
        }

        Path(path).write_text(json.dumps(data, indent=2))
        self.animation_path = path
        QMessageBox.information(self, "Saved", f"Animation saved to {Path(path).name}")

    def load_animation(self):
        """Load animation from JSON."""
        path, _ = QFileDialog.getOpenFileName(self, "Load Animation", "", "JSON (*.json)")
        if not path:
            return

        try:
            data = json.loads(Path(path).read_text())
            self.keyframes = data.get("keyframes", [])
            self.animation_path = path
            self.current_frame_index = 0 

            if self.keyframes:
                kf = self.keyframes[0]
                self.canvas.set_player_positions(kf.get("positions", {}))
                ball = kf.get("ball", (50.0, 36.5, 1.0))
                self.canvas.set_ball_position(ball)

            self.status_label.setText(f"Loaded: {len(self.keyframes)} keyframes from {Path(path).name}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load: {e}")

    def export_rerun_dialog(self):
        """Export animation to Rerun format."""
        if not self.keyframes:
            QMessageBox.warning(self, "Warning", "No keyframes to export")
            return

        path, _ = QFileDialog.getSaveFileName(self, "Export Rerun", "", "JSON (*.json)")
        if not path:
            return

        # Build interpolated timeline
        timeline = self._build_interpolated_timeline()

        data = {
            "metadata": {"pitch_length": 100, "pitch_width": 73, "scale": 10},
            "timeline": timeline,
        }

        Path(path).write_text(json.dumps(data, indent=2))
        self.last_export_path = path
        QMessageBox.information(self, "Exported", f"Rerun export saved")

    def focus_and_view(self, viewpoint):
        """Center canvas on viewpoint."""
        # Set canvas to follow this viewpoint
        self.canvas.set_follow_target(viewpoint)
        self.status_label.setText(f"Following: {viewpoint}")

    def view_with_viewpoint(self, viewpoint):
        """View animation with specific viewpoint."""
        if not self.keyframes:
            QMessageBox.warning(self, "Warning", "No animation to view")
            return

        if not self.last_export_path:
            # First export it
            path, _ = QFileDialog.getSaveFileName(self, "Export Rerun", "", "JSON (*.json)")
            if not path:
                return
            timeline = self._build_interpolated_timeline()
            data = {
                "metadata": {"pitch_length": 100, "pitch_width": 73, "scale": 10},
                "timeline": timeline,
            }
            Path(path).write_text(json.dumps(data, indent=2))
            self.last_export_path = path

        if not Path(self.last_export_path).exists():
            QMessageBox.critical(self, "Error", "Animation file not found")
            return

        try:
            cmd = [
                "python3",
                str(Path(__file__).parent / "rerun_plotting.py"),
                str(self.last_export_path),
                "--viewpoint", viewpoint
            ]
            subprocess.Popen(cmd)
            self.status_label.setText(f"Viewing from: {viewpoint}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to open Rerun: {e}")

    def _build_interpolated_timeline(self, steps_per_segment=10):
        """Build interpolated timeline from keyframes."""
        timeline = []
        if not self.keyframes:
            return timeline

        first = self.keyframes[0]
        timeline.append({
            "type": "keyframe",
            "frame": 0.0,
            "positions": first["positions"],
            "ball": first["ball"],
        })

        for idx in range(len(self.keyframes) - 1):
            current = self.keyframes[idx]
            nex = self.keyframes[idx + 1]

            pos0 = current["positions"]
            pos1 = nex["positions"]
            ball0 = current["ball"]
            ball1 = nex["ball"]

            for step in range(1, steps_per_segment + 1):
                alpha = step / steps_per_segment
                frame_time = idx + alpha
                positions = {}

                all_ids = set(pos0) | set(pos1)
                for pid in all_ids:
                    if pid in pos0 and pid in pos1:
                        x0, y0, z0 = pos0[pid] if len(pos0[pid]) >= 3 else (pos0[pid][0], pos0[pid][1], 0.0)
                        x1, y1, z1 = pos1[pid] if len(pos1[pid]) >= 3 else (pos1[pid][0], pos1[pid][1], 0.0)
                        positions[pid] = (
                            self._lerp(x0, x1, alpha),
                            self._lerp(y0, y1, alpha),
                            self._lerp(z0, z1, alpha),
                        )
                    elif pid in pos0:
                        positions[pid] = pos0[pid]
                    else:
                        positions[pid] = pos1[pid]

                b0 = ball0 if len(ball0) >= 3 else (ball0[0], ball0[1], 1.0)
                b1 = ball1 if len(ball1) >= 3 else (ball1[0], ball1[1], 1.0)
                ball = (
                    self._lerp(b0[0], b1[0], alpha),
                    self._lerp(b0[1], b1[1], alpha),
                    max(1.0, self._lerp(b0[2], b1[2], alpha)),
                )

                timeline.append({
                    "type": "interpolated",
                    "frame": frame_time,
                    "positions": positions,
                    "ball": ball,
                })

        return timeline

    @staticmethod
    def _lerp(a, b, t):
        """Linear interpolation."""
        return a + (b - a) * t


class RugbyApp(QMainWindow):
    """Main application window."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Rugby Formation Annotation Tool")
        self.setGeometry(100, 100, 1600, 900)

        # Set main widget to annotation tab
        self.annotation_tab = AnnotationTab()
        self.setCentralWidget(self.annotation_tab)

        # Status bar
        self.statusBar().showMessage("Ready")


def main():
    """Run the application."""
    app = QApplication(sys.argv)
    window = RugbyApp()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()