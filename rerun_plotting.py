"""Replay rugby animation JSON on a rugby pitch in Rerun."""

import json
import math
import subprocess
import sys
from pathlib import Path
from typing import Union

import rerun as rr



def _rugby_pitch_entities(
    half_length_m: float,
    half_width_m: float,
) -> None:
    """Log static rugby pitch: grass + full rugby markings."""
    z_line = 0.02
    white = (255, 255, 255)
    hl, hw = half_length_m, half_width_m

    # Grass slab
    rr.log(
        "world/pitch/ground",
        rr.Boxes3D(
            centers=[(0.0, 0.0, -0.08)],
            half_sizes=[(hl, hw, 0.08)],
            colors=[(34, 100, 34)],
            fill_mode="solid",
        ),
        static=True,
    )

    # Boundary lines
    boundary = [[(-hl, -hw, z_line), (hl, -hw, z_line), (hl, hw, z_line), (-hl, hw, z_line), (-hl, -hw, z_line)]]
    rr.log("world/pitch/markings/boundary", rr.LineStrips3D(boundary, radii=0.08, colors=white), static=True)

    # Halfway line
    rr.log(
        "world/pitch/markings/halfway",
        rr.LineStrips3D([[(0.0, -hw, z_line), (0.0, hw, z_line)]], radii=0.06, colors=white),
        static=True,
    )

    # Try lines (5m from deadball/boundary)
    for x in (-hl + 5.0, hl - 5.0):
        rr.log(
            f"world/pitch/markings/try_line_{'left' if x < 0 else 'right'}",
            rr.LineStrips3D([[(x, -hw, z_line), (x, hw, z_line)]], radii=0.06, colors=white),
            static=True,
        )

    # 22m lines
    for x in (-22.0, 22.0):
        rr.log(
            f"world/pitch/markings/22m_line_{'left' if x < 0 else 'right'}",
            rr.LineStrips3D([[(x, -hw, z_line), (x, hw, z_line)]], radii=0.05, colors=white),
            static=True,
        )

    # 10m lines
    for x in (-10.0, 10.0):
        rr.log(
            f"world/pitch/markings/10m_line_{'left' if x < 0 else 'right'}",
            rr.LineStrips3D([[(x, -hw, z_line), (x, hw, z_line)]], radii=0.05, colors=white),
            static=True,
        )


def _open_viewer(rrd_path: Path) -> None:
    """Open the bundled Rerun viewer (avoids relying on a ``rerun`` executable on PATH / pyenv)."""
    rrd_path = rrd_path.resolve()
    kwargs: dict = {}
    if sys.platform != "win32":
        kwargs["start_new_session"] = True
    subprocess.Popen([sys.executable, "-m", "rerun_cli", str(rrd_path)], **kwargs)


def _animator_to_world(x: float, y: float, pitch_length: float = 100.0, pitch_width: float = 73.0) -> tuple[float, float]:
    """Convert animator canvas coordinates to centered Rerun world coordinates."""
    return x - pitch_length / 2.0, y - pitch_width / 2.0


def _player_body_dimensions(player_id: str) -> tuple[float, float]:
    """Return height and body radius for a player based on position id."""
    base_id = player_id.split("_")[-1]
    try:
        num = int(base_id)
    except ValueError:
        return 1.83, 0.36

    if num in (1, 2, 3):
        return 1.78, 0.45
    if num in (4, 5):
        return 2.04, 0.30
    if num in (6, 7):
        return 1.83, 0.36
    if num == 8:
        return 1.88, 0.36
    if num == 9:
        return 1.70, 0.36
    if 10 <= num <= 15:
        return 1.83, 0.36

    return 1.83, 0.36


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def _interpolate_keyframes(
    timeline: list,
    steps_per_segment: int,
) -> list:
    interpolated = []
    if not timeline:
        return interpolated

    for idx in range(len(timeline) - 1):
        current = timeline[idx]
        next_key = timeline[idx + 1]
        t0 = float(current.get("frame", idx))
        t1 = float(next_key.get("frame", idx + 1))
        delta_t = t1 - t0
        positions0 = current.get("positions", {})
        positions1 = next_key.get("positions", {})
        ball0 = tuple(current.get("ball", [50.0, 36.5]))
        ball1 = tuple(next_key.get("ball", [50.0, 36.5]))

        for step in range(steps_per_segment):
            alpha = step / steps_per_segment
            frame_time = t0 + alpha * delta_t
            positions = {}
            all_ids = set(positions0) | set(positions1)
            for pid in all_ids:
                if pid in positions0 and pid in positions1:
                    x0, y0 = positions0[pid][:2]
                    x1, y1 = positions1[pid][:2]
                    z0 = positions0[pid][2] if len(positions0[pid]) >= 3 else 0.0
                    z1 = positions1[pid][2] if len(positions1[pid]) >= 3 else 0.0
                    positions[pid] = (_lerp(x0, x1, alpha), _lerp(y0, y1, alpha), _lerp(z0, z1, alpha))
                elif pid in positions0:
                    positions[pid] = tuple(positions0[pid])
                else:
                    positions[pid] = tuple(positions1[pid])

            ball_z0 = ball0[2] if len(ball0) >= 3 else 0.0
            ball_z1 = ball1[2] if len(ball1) >= 3 else 0.0
            ball = (_lerp(ball0[0], ball1[0], alpha), _lerp(ball0[1], ball1[1], alpha), _lerp(ball_z0, ball_z1, alpha))
            interpolated.append((frame_time, positions, ball))

    last = timeline[-1]
    interpolated.append(
        (
            float(last.get("frame", len(timeline) - 1)),
            {pid: tuple(pos) for pid, pos in last.get("positions", {}).items()},
            tuple(last.get("ball", [50.0, 36.5])),
        )
    )
    return interpolated


def plot_animation_json(
    json_path: Union[str, Path],
    *,
    app_name: str = "rugby_animation",
    rrd_path: Union[str, Path, None] = None,
    spawn_viewer: bool = True,
    realtime: bool = False,
    steps_per_segment: int = 10,
    cylinder_height_m: float = 1.85,
    cylinder_radius_m: float = 0.38,
    ball_radius_m: float = 0.24,
    ball_height_m: float = 1.2,
    viewpoint: str = "ball",
) -> Path:
    """
    Load a rugby animation JSON and log a 3D scene to Rerun: rugby pitch, ball, and players as cylinders.

    Supports both formats:
    - Timeline format: metadata with pitch dimensions, timeline of keyframes with positions and ball.
    - Keyframes format: keyframes array with positions and ball (from rugby_direction_annotator.py).

    Data is written to an ``.rrd`` file. The viewer is opened via ``python -m rerun_cli``.

    Parameters
    ----------
    json_path
        Path to the animation JSON (e.g. ``rerun_animation.json``).
    rrd_path
        Output recording path. Default: ``<json_stem>_rerun.rrd`` beside the JSON.
    spawn_viewer
        If True, launch the Rerun viewer on the written ``.rrd`` after logging finishes.
    realtime
        If True, sleep between keyframes.
    viewpoint
        Camera viewpoint: 'ball' or player ID (e.g., 'home_9').
    """
    path = Path(json_path)
    out_rrd = Path(rrd_path) if rrd_path is not None else (path.parent / f"{path.stem}_rerun.rrd")
    out_rrd = out_rrd.resolve()

    with open(path, 'r') as f:
        data = json.load(f)

    metadata = data.get('metadata', {})
    pitch_length = metadata.get('pitch_length', data.get('pitch_length', 100))
    pitch_width = metadata.get('pitch_width', data.get('pitch_width', 73))
    scale = metadata.get('scale', data.get('scale', 8))
    
    # Handle both timeline and keyframes formats
    timeline = data.get('timeline')
    if timeline is None:
        # Convert keyframes format to timeline format
        keyframes = data.get('keyframes', [])
        if keyframes:
            timeline = []
            for idx, keyframe in enumerate(keyframes):
                timeline.append({
                    "type": "keyframe",
                    "frame": float(idx),
                    "positions": keyframe.get("positions", {}),
                    "ball": keyframe.get("ball", [50.0, 36.5]),
                })
            # Interpolate between keyframes
            interpolated = _interpolate_keyframes(timeline, steps_per_segment=10)
            timeline = []
            for frame_time, positions, ball in interpolated:
                timeline.append({
                    "type": "interpolated",
                    "frame": frame_time,
                    "positions": positions,
                    "ball": ball,
                })
        else:
            timeline = []

    # Ensure all ball positions have minimum height of 1m
    for frame in timeline:
        ball = frame.get('ball', [50.0, 36.5])
        if isinstance(ball, (list, tuple)):
            if len(ball) >= 3:
                x, y, z = ball
                frame['ball'] = (x, y, max(1.0, z))
            elif len(ball) == 2:
                x, y = ball
                frame['ball'] = (x, y, 1.0)

    rr.init(app_name, spawn=False)
    rr.save(out_rrd)
    _rugby_pitch_entities(pitch_length / 2, pitch_width / 2)

    import time

    for keyframe in timeline:
        frame = keyframe.get('frame', 0)
        positions = keyframe.get('positions', {})
        ball = keyframe.get('ball', [50.0, 36.5])

        rr.set_time("frame", timestamp=frame)

        # Calculate ball position
        bx, by = _animator_to_world(ball[0], ball[1], pitch_length=pitch_length, pitch_width=pitch_width)
        ball_z = ball[2] if len(ball) >= 3 else ball_height_m

        # Center the view based on viewpoint
        if viewpoint == "ball":
            vx, vy, vz = bx, by, ball_z
        elif viewpoint in positions:
            pos = positions[viewpoint]
            vx, vy = _animator_to_world(pos[0], pos[1], pitch_length=pitch_length, pitch_width=pitch_width)
            vz = pos[2] if len(pos) >= 3 else 0.0
        else:
            # Default to ball if invalid viewpoint
            vx, vy, vz = bx, by, ball_z
        
        rr.log("world", rr.Transform3D(translation=[-vx, -vy, -vz + 2.0], scale=[1.4, 1.4, 1.4]))

        ball_z = ball[2] if len(ball) >= 3 else ball_height_m
        # Rugby ball shape using ellipsoid (approx 30cm x 60cm x 30cm)
        rr.log(
            "world/ball",
            rr.Ellipsoids3D(
                centers=[(bx, by, ball_z)],
                half_sizes=[(0.3, 0.6, 0.3)],
                colors=[(255, 220, 40)],
            ),
        )

        # Players
        centers = []
        colors = []
        radii = []
        lengths = []
        for pid, pos in positions.items():
            if len(pos) >= 2:
                height_m, radius_m = _player_body_dimensions(pid)
                x, y = _animator_to_world(pos[0], pos[1], pitch_length=pitch_length, pitch_width=pitch_width)
                z = pos[2] if len(pos) >= 3 else 0.0
                centers.append((x, y, z + height_m * 0.5))
                lengths.append(height_m)
                radii.append(radius_m)
                # Color based on team
                if pid.startswith('home_'):
                    colors.append((255, 153, 51))  # orange
                else:
                    colors.append((255, 255, 255))  # white

        if centers:
            rr.log(
                "world/players",
                rr.Cylinders3D(
                    centers=centers,
                    radii=radii,
                    lengths=lengths,
                    colors=colors,
                ),
            )

        if realtime:
            time.sleep(0.1)  # Adjust as needed

    if spawn_viewer:
        _open_viewer(out_rrd)
    return out_rrd


def main() -> None:
    import argparse

    p = argparse.ArgumentParser(description="Replay rugby animation JSON in Rerun (3D rugby pitch + player cylinders).")
    p.add_argument("json", nargs="?", default="rerun_animation.json", type=Path)
    p.add_argument(
        "--rrd",
        type=Path,
        default=None,
        help="Output .rrd path (default: <json_stem>_rerun.rrd next to the JSON).",
    )
    p.add_argument("--no-spawn", action="store_true", help="Do not open the Rerun viewer after export.")
    p.add_argument("--realtime", action="store_true", help="Sleep between keyframes.")
    p.add_argument("--viewpoint", default="ball", help="Camera viewpoint: 'ball' or player ID (e.g., 'home_9')")
    args = p.parse_args()
    out = plot_animation_json(
        args.json,
        rrd_path=args.rrd,
        spawn_viewer=not args.no_spawn,
        realtime=args.realtime,
        viewpoint=args.viewpoint,
    )
    print(f"Wrote Rerun recording: {out}")
    if not args.no_spawn:
        print("Opened viewer (python -m rerun_cli). If it did not appear, run:")
        print(f"  python -m rerun_cli {out}")


if __name__ == "__main__":
    main()
