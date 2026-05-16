from __future__ import annotations

import sys
import time

from rich.align import Align
from rich.console import Console, Group
from rich.live import Live
from rich.text import Text

# -----------------------------------------------------------------------------
# ASCII WORDMARK
# -----------------------------------------------------------------------------

_WORDMARK = [
    "███╗   ██╗██╗   ██╗ ██████╗██╗     ███████╗██╗   ██╗███████╗",
    "████╗  ██║██║   ██║██╔════╝██║     ██╔════╝██║   ██║██╔════╝",
    "██╔██╗ ██║██║   ██║██║     ██║     █████╗  ██║   ██║███████╗",
    "██║╚██╗██║██║   ██║██║     ██║     ██╔══╝  ██║   ██║╚════██║",
    "██║ ╚████║╚██████╔╝╚██████╗███████╗███████╗╚██████╔╝███████║",
    "╚═╝  ╚═══╝ ╚═════╝  ╚═════╝╚══════╝╚══════╝ ╚═════╝ ╚══════╝",
]

_MAX_LEN = max(len(line) for line in _WORDMARK)

# -----------------------------------------------------------------------------
# BRAND GRADIENT (Brightened for high terminal contrast)
# -----------------------------------------------------------------------------

_GRADIENT = [
    "#1E4FD9",  # Lifted Deep Blue (High visibility starting color)
    "#2E65DD",  # Medium Royal Blue
    "#1E60F2",  # Vibrant Electric Blue
    "#3B82F6",  # Bright Blue
    "#6AA0F6",  # Light Cornflower Blue
    "#F26A36",  # Distinctive Orange Accent (Matches top-right logo piece)
    "#E95D2B",  # Deep Orange Tail
]

# Shimmer effect colors (Laser white pass)
_SHIMMER_COLORS = ["#6AA0F6", "#FFFFFF", "#FFFFFF", "#6AA0F6"]


# -----------------------------------------------------------------------------
# GRADIENT & EFFECTS RENDERING
# -----------------------------------------------------------------------------

def _apply_gradient_with_effects(
    line: str, 
    gradient: list[str], 
    reveal_progress: float = 1.0, 
    shimmer_pos: int | None = None, 
    shimmer_width: int = 10
) -> Text:
    """
    Applies brand-accurate horizontal gradient mapping alongside
    smooth reveal and moving shimmer states.
    """
    text = Text()
    line_len = len(line)
    visible_chars = int(line_len * reveal_progress)

    for i, char in enumerate(line):
        if i >= visible_chars:
            break
            
        if not char.strip():
            text.append(char)
            continue

        # 1. Map brand gradient from left to right smoothly
        gradient_pos = (i / max(line_len - 1, 1)) ** 0.95 
        color_idx = round(gradient_pos * (len(gradient) - 1))
        color_idx = max(0, min(color_idx, len(gradient) - 1))
        color = gradient[color_idx]

        # 2. Overlay Shimmer Wave if active
        if shimmer_pos is not None:
            if shimmer_pos <= i < shimmer_pos + shimmer_width:
                shimmer_idx = i - shimmer_pos
                shm_color_idx = round((shimmer_idx / (shimmer_width - 1)) * (len(_SHIMMER_COLORS) - 1))
                color = _SHIMMER_COLORS[max(0, min(shm_color_idx, len(_SHIMMER_COLORS) - 1))]

        text.append(char, style=color)

    return text


# -----------------------------------------------------------------------------
# ANIMATION ENGINE
# -----------------------------------------------------------------------------

def _render_animated_wordmark(console: Console) -> None:
    """
    Runs the modern CLI startup orchestration sequence.
    """
    with Live(
        "",
        console=console,
        refresh_per_second=60,
        transient=False,
        screen=False,
    ) as live:

        # Phase 1 — Clean Diagonal Reveal Sweep
        steps = 25
        for step in range(steps + 1):
            renderables = []
            progress = step / steps
            
            for line_idx, line in enumerate(_WORDMARK):
                line_delay = (line_idx / len(_WORDMARK)) * 0.35
                line_progress = max(0.0, min(1.0, (progress - line_delay) / (1.0 - line_delay + 1e-5)))
                
                if line_progress > 0:
                    renderables.append(_apply_gradient_with_effects(line, _GRADIENT, reveal_progress=line_progress))
            
            live.update(Group(*renderables))
            time.sleep(0.02)

        # Phase 2 — Brief Hold 
        time.sleep(0.12)

        # Phase 3 — High-speed Shimmer Pass across the brand colors
        shimmer_width = 14
        start_pos = -shimmer_width
        end_pos = _MAX_LEN
        step_size = 4  
        
        for pos in range(start_pos, end_pos, step_size):
            shimmer_renderables = [
                _apply_gradient_with_effects(line, _GRADIENT, shimmer_pos=pos, shimmer_width=shimmer_width)
                for line in _WORDMARK
            ]
            live.update(Group(*shimmer_renderables))
            time.sleep(0.015)

        # Phase 4 — Finalize on the static brand-accurate layout
        normal_renderables = [
            _apply_gradient_with_effects(line, _GRADIENT)
            for line in _WORDMARK
        ]
        live.update(Group(*normal_renderables))


# -----------------------------------------------------------------------------
# PUBLIC API & ENTRYPOINT
# -----------------------------------------------------------------------------

def print_startup_banner() -> None:
    """Render Nucleus startup banner with color corrections."""
    if not sys.stdout.isatty():
        print("NUCLEUS")
        return

    console = Console(highlight=False)
    _render_animated_wordmark(console)
    
    time.sleep(0.05)
    console.print()
    console.print(Text("ship data products from a laptop", style="dim"))
    console.print()


if __name__ == "__main__":
    print_startup_banner()