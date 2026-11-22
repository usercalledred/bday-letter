"""
❄  Glacier Birthday Letter  ❄
A snowy tkinter birthday card with falling snow, waddling penguins,
a reveal-able letter and optional winter music.

Requirements:  pip install pillow
Setup:         put "Untitled Design.png" (your penguin sheet) next to this file.
Run:           python birthday_letter.py
"""

import math
import os
import random
import struct
import sys
import tempfile
import threading
import wave
import tkinter as tk
import tkinter.font as tkfont
from tkinter import messagebox

from PIL import Image, ImageDraw, ImageTk

# ───────────────────────── EDIT THESE ─────────────────────────
RECIPIENT = "Loot"          # who the letter is for
SENDER = "Sabs"        # who it is from
LETTER_BODY = (
    "Happy Birthday, Lilith! I hope di ka mag bago and you always carry that kindness with you.  "
    "Thank you so much for all the help na binigay mo saakin, kayo dalawa ni suave.\n\n"
    "Without you, I don't think na kinaya ko ang 1st year ng College, "
    "I'm always thankful na meet ko kayo, and I hope na maging safe and healty ka palagi and your family.\n\n"
    "Stay strong kayo ni Suave and please continue being a weirdo, armani loves your weirdness. Your weirdness is what makes you special. "
)
# Optional: your own music file (needs `pip install pygame`). Leave "" to use
# the built-in soft music-box melody.
CUSTOM_MUSIC = ""
# ───────────────────────────────────────────────────────────────

# Icy palette
DEEP_NAVY = "#04102a"
NAVY = "#0a1f44"
GLACIER = "#2f86c2"
GLACIER_LIGHT = "#7cc4e8"
CYAN = "#9ff3ff"
SILVER = "#c0cbd8"
WHITE = "#ffffff"
ICE = "#e8f6fd"

W, H = 1000, 700
FPS_MS = 33

# Crop boxes of the 5 penguins in the 1024x1024 sheet (left, top, right, bottom)
PENGUIN_BOXES = [
    (60, 40, 255, 280),    # 0 black cutie, top-left
    (665, 50, 880, 300),   # 1 emperor, top-right
    (350, 270, 560, 535),  # 2 watercolor, centre  (the walker)
    (100, 625, 295, 885),  # 3 grey chick, bottom-left
    (640, 545, 900, 860),  # 4 blue happy, bottom-right
]


# ───────────────────────── helpers ─────────────────────────
def find_asset(names, extra=None):
    here = os.path.dirname(os.path.abspath(__file__))
    paths = [os.path.join(here, n) for n in names]
    paths += [os.path.join(os.getcwd(), n) for n in names]
    if extra:
        paths.append(extra)
    for p in paths:
        if os.path.exists(p):
            return p
    return None


def find_image():
    return find_asset(["Untitled Design.png", "Untitled_Design.png", "penguins.png"],
                      r"D:\Untitled Design.png")


def find_mail():
    return find_asset(["mail.png", "Mail.png"], r"D:\mail.png")


PAPER_INSET = 48      # corner size kept un-stretched when the paper is resized
ENV_W = 250           # on-screen width of the envelope


def nine_slice(src, w, h, inset):
    """Resize a framed picture without distorting its corners or border."""
    sw, sh = src.size
    w, h = max(w, 2 * inset + 2), max(h, 2 * inset + 2)
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    xs, xd = [0, inset, sw - inset, sw], [0, inset, w - inset, w]
    ys, yd = [0, inset, sh - inset, sh], [0, inset, h - inset, h]
    for j in range(3):
        for i in range(3):
            part = src.crop((xs[i], ys[j], xs[i + 1], ys[j + 1]))
            size = (xd[i + 1] - xd[i], yd[j + 1] - yd[j])
            if part.size != size:
                part = part.resize(size, Image.BILINEAR)
            out.paste(part, (xd[i], yd[j]))
    return out


def _crop_object(sheet, box, scale):
    crop = cut_out(sheet.crop(tuple(int(v * scale) for v in box)))
    bbox = crop.getchannel("A").getbbox()
    return crop.crop(bbox) if bbox else crop


def load_mail_assets(path):
    """Returns (envelope, paper) as RGBA images. Uses mail.png when present,
    otherwise draws simple stand-ins so the app still runs."""
    if path:
        sheet = Image.open(path).convert("RGBA")
        scale = sheet.width / 1024
        env = _crop_object(sheet, (10, 100, 510, 540), scale)
        paper = _crop_object(sheet, (590, 75, 955, 625), scale)
    else:
        env = Image.new("RGBA", (500, 440), (0, 0, 0, 0))
        d = ImageDraw.Draw(env)
        d.rectangle((20, 60, 470, 420), fill="#c3e3fb", outline="#111111", width=6)
        d.line([(20, 60), (245, 260), (470, 60)], fill="#111111", width=6)
        d.ellipse((218, 232, 272, 286), fill="#0a1f44", outline="#9ff3ff", width=3)
        paper = Image.new("RGBA", (350, 535), (0, 0, 0, 0))
        d = ImageDraw.Draw(paper)
        d.rounded_rectangle((0, 0, 349, 534), radius=28, fill="#4a6a9a")
        d.rounded_rectangle((10, 10, 339, 524), radius=24, fill="#f3ecd0")
    env = env.resize((ENV_W, max(1, int(env.height * ENV_W / env.width))), Image.LANCZOS)
    paper = paper.resize((350, max(1, int(paper.height * 350 / paper.width))), Image.LANCZOS)
    return env, paper


def lerp_color(c1, c2, t):
    a = [int(c1[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(c2[i:i + 2], 16) for i in (1, 3, 5)]
    return "#%02x%02x%02x" % tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def rrect(x1, y1, x2, y2, r):
    return [x1 + r, y1, x1 + r, y1, x2 - r, y1, x2 - r, y1, x2, y1, x2, y1 + r,
            x2, y1 + r, x2, y2 - r, x2, y2 - r, x2, y2, x2 - r, y2, x2 - r, y2,
            x1 + r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y2 - r, x1, y1 + r,
            x1, y1 + r, x1, y1]


def ease(p):
    p = max(0.0, min(1.0, p))
    return p * p * (3 - 2 * p)


def ease_out_back(x):
    x = max(0.0, min(1.0, x))
    c1 = 1.70158
    c3 = c1 + 1
    return 1 + c3 * (x - 1) ** 3 + c1 * (x - 1) ** 2


def ease_out_bounce(x):
    x = max(0.0, min(1.0, x))
    n1, d1 = 7.5625, 2.75
    if x < 1 / d1:
        return n1 * x * x
    if x < 2 / d1:
        x -= 1.5 / d1
        return n1 * x * x + 0.75
    if x < 2.5 / d1:
        x -= 2.25 / d1
        return n1 * x * x + 0.9375
    x -= 2.625 / d1
    return n1 * x * x + 0.984375


def star_pts(x, y, s):
    k = s * 0.28
    return [x, y - s, x + k, y - k, x + s, y, x + k, y + k,
            x, y + s, x - k, y + k, x - s, y, x - k, y - k]


def cut_out(img):
    """Make sure a crop has a transparent background."""
    img = img.convert("RGBA")
    if img.getchannel("A").getextrema()[0] < 250:
        return img  # already transparent
    rgb = img.convert("RGB")
    key = (255, 0, 255)
    w, h = rgb.size
    for corner in [(0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)]:
        ImageDraw.floodfill(rgb, corner, key, thresh=28)
    out = [(r, g, b, 0) if (r, g, b) == key else (r, g, b, 255)
           for (r, g, b) in rgb.getdata()]
    img.putdata(out)
    return img


# ───────────────────────── music ─────────────────────────
class Music:
    """Soft synthesized music-box loop (Windows: winsound, else pygame)."""

    def __init__(self):
        self.enabled = True
        self.ready = False
        self.playing = False
        self.path = None
        self.mode = None
        threading.Thread(target=self._prepare, daemon=True).start()

    def _prepare(self):
        try:
            if CUSTOM_MUSIC and os.path.exists(CUSTOM_MUSIC):
                import pygame
                pygame.mixer.init()
                pygame.mixer.music.load(CUSTOM_MUSIC)
                self.mode = "pygame_file"
            else:
                self.path = os.path.join(tempfile.gettempdir(), "glacier_bday_loop.wav")
                if not os.path.exists(self.path):
                    self._synth(self.path)
                if sys.platform.startswith("win"):
                    self.mode = "winsound"
                else:
                    import pygame
                    pygame.mixer.init()
                    self.mode = "pygame_wav"
            self.ready = True
            if self.enabled:
                self.play()
        except Exception as exc:  # no audio available
            print("Music disabled:", exc)

    @staticmethod
    def _synth(path):
        sr = 16000
        chords = [
            (220.00, 261.63, 329.63, 440.00),   # Am
            (174.61, 220.00, 261.63, 349.23),   # F
            (261.63, 329.63, 392.00, 523.25),   # C
            (196.00, 246.94, 293.66, 392.00),   # G
            (220.00, 261.63, 329.63, 440.00),   # Am
            (174.61, 220.00, 261.63, 349.23),   # F
            (196.00, 246.94, 293.66, 392.00),   # G
            (261.63, 329.63, 392.00, 523.25),   # C
        ]
        pattern = [0, 1, 2, 3, 2, 1, 2, 1]
        eighth = 0.275
        bar_len = int(sr * eighth * 8)
        n = bar_len * len(chords)
        buf = [0.0] * n

        def add(freq, start, dur, vol):
            length = int(sr * dur)
            for i in range(length):
                t = i / sr
                env = math.exp(-t * 3.2) * min(1.0, i / 80)
                s = (math.sin(6.2832 * freq * t)
                     + 0.28 * math.sin(12.5664 * freq * t)
                     + 0.08 * math.sin(18.8496 * freq * t))
                buf[(start + i) % n] += s * env * vol   # circular => seamless loop

        for b, chord in enumerate(chords):
            base = b * bar_len
            for k, idx in enumerate(pattern):
                add(chord[idx], base + int(k * eighth * sr), 1.2, 0.30)
            add(chord[2] * 2, base, 1.6, 0.35)
            add(chord[3], base + int(4 * eighth * sr), 1.6, 0.30)

        peak = max(abs(v) for v in buf) or 1.0
        with wave.open(path, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sr)
            wf.writeframes(b"".join(struct.pack("<h", int(v / peak * 14000)) for v in buf))

    def play(self):
        if not self.ready or self.playing:
            return
        try:
            if self.mode == "winsound":
                import winsound
                winsound.PlaySound(self.path, winsound.SND_FILENAME |
                                   winsound.SND_ASYNC | winsound.SND_LOOP)
            elif self.mode == "pygame_wav":
                import pygame
                pygame.mixer.music.load(self.path)
                pygame.mixer.music.play(-1)
            elif self.mode == "pygame_file":
                import pygame
                pygame.mixer.music.play(-1)
            self.playing = True
        except Exception as exc:
            print("Could not play music:", exc)

    def stop(self):
        try:
            if self.mode == "winsound":
                import winsound
                winsound.PlaySound(None, winsound.SND_PURGE)
            elif self.mode and self.mode.startswith("pygame"):
                import pygame
                pygame.mixer.music.stop()
        except Exception:
            pass
        self.playing = False

    def toggle(self):
        self.enabled = not self.enabled
        if self.enabled:
            self.play()
        else:
            self.stop()
        return self.enabled


# ───────────────────────── penguin ─────────────────────────
class Penguin:
    """A penguin with a little personality: it idles, jumps (with squash &
    stretch), dances, and the centre one also waddles and belly-slides.
    Click a penguin to make it jump!"""

    BOUND_L, BOUND_R = 240, 760

    def __init__(self, canvas, sheet, box, x, feet_y, height, walker=False, emit=None):
        self.c = canvas
        self.x, self.feet_y, self.height = x, feet_y, height
        self.walker, self.emit = walker, emit
        scale = sheet.width / 1024
        crop = cut_out(sheet.crop(tuple(int(v * scale) for v in box)))
        bbox = crop.getbbox()
        if bbox:
            crop = crop.crop(bbox)
        ratio = height / crop.height
        base = crop.resize((max(1, int(crop.width * ratio)), height), Image.LANCZOS)

        self.sets = {1: self._make_set(base, 1)}
        if walker:
            self.sets[-1] = self._make_set(base, -1)

        self.dir = 1
        self.phase = random.uniform(0, 6.28)
        self.jump_h, self.jump_len = 40, 28
        self.celebrate_left = 0
        self.delay = 0
        self.age = 0
        self.timer = 0
        self.state = "idle"
        self.item = canvas.create_image(x, feet_y, image=self.sets[1]["rot"][4], anchor="s")
        canvas.tag_bind(self.item, "<Button-1>", lambda e: self.poke())
        canvas.tag_bind(self.item, "<Enter>", lambda e: canvas.config(cursor="hand2"))
        canvas.tag_bind(self.item, "<Leave>", lambda e: canvas.config(cursor=""))
        if walker:
            self.start_walk()
        else:
            self.set_state("idle", random.randint(20, 90))

    @staticmethod
    def _make_set(base, d):
        img = base if d == 1 else base.transpose(Image.FLIP_LEFT_RIGHT)
        w, h = img.size
        angles = [-10 + 20 * i / 8 for i in range(9)]
        return {
            "rot": [ImageTk.PhotoImage(img.rotate(a, resample=Image.BICUBIC, expand=True))
                    for a in angles],
            "squash": ImageTk.PhotoImage(img.resize((int(w * 1.16), max(1, int(h * 0.82))), Image.LANCZOS)),
            "stretch": ImageTk.PhotoImage(img.resize((int(w * 0.88), int(h * 1.12)), Image.LANCZOS)),
            "slide": ImageTk.PhotoImage(base.rotate(-82 * d, resample=Image.BICUBIC, expand=True)),
        }

    # ----- state helpers -----
    def set_state(self, state, timer=0):
        self.state, self.age, self.timer = state, 0, timer

    def start_jump(self, h=None):
        h = h or random.randint(30, 46)
        self.jump_h = min(h, max(10, self.feet_y - self.height - 4))
        self.jump_len = 28
        self.set_state("jump")

    def start_walk(self):
        d = random.choice([1, -1])
        if self.x > self.BOUND_R - 80:
            d = -1
        elif self.x < self.BOUND_L + 80:
            d = 1
        self.dir = d
        self.set_state("walk", random.randint(90, 200))

    def start_slide(self):
        d = 1 if self.x < (self.BOUND_L + self.BOUND_R) / 2 else -1
        if random.random() < 0.25:
            d = -d
        room = (self.BOUND_R - self.x) if d == 1 else (self.x - self.BOUND_L)
        if room < 160:
            return self.start_walk()
        self.dir = d
        self.set_state("slide", min(int(room / 4.8), 75))

    def poke(self):
        if self.state != "slide":
            self.start_jump(random.randint(40, 55))
            if self.emit:
                self.emit(self.x, self.feet_y)

    def celebrate(self):
        self.celebrate_left = 200
        self.delay = random.randint(0, 14)
        self.start_jump(random.randint(40, 60))

    def next_action(self):
        r = random.random()
        if self.celebrate_left > 0:
            return self.start_jump(random.randint(40, 60)) if r < 0.6 else self.set_state("dance", 45)
        if self.walker:
            if r < 0.45:
                self.start_walk()
            elif r < 0.68:
                self.start_slide()
            elif r < 0.84:
                self.start_jump()
            else:
                self.set_state("dance", 50)
        else:
            if r < 0.45:
                self.start_jump()
            elif r < 0.85:
                self.set_state("dance", random.randint(45, 75))
            else:
                self.set_state("idle", random.randint(50, 130))

    def after_jump(self):
        if self.celebrate_left > 0:
            self.start_jump(random.randint(40, 60))
        elif random.random() < 0.2:
            self.start_jump()
        else:
            self.set_state("idle", random.randint(40, 120))

    # ----- per-frame update -----
    def update(self):
        if self.celebrate_left > 0:
            self.celebrate_left -= 1
        if self.delay > 0:
            self.delay -= 1
            return
        self.age += 1
        S = self.sets[self.dir]
        img, lift = S["rot"][4], 0.0
        st = self.state

        if st == "idle":
            s = math.sin(self.age * 0.08 + self.phase)
            img = S["rot"][int(3 + (s + 1) / 2 * 2.99)]
            lift = (math.sin(self.age * 0.2 + self.phase) + 1) * 1.2
            if self.age > self.timer:
                self.next_action()

        elif st == "jump":
            k, n = self.age, self.jump_len
            if k <= 4:
                img = S["squash"]
            elif k < n - 4:
                u = (k - 4) / (n - 8)
                lift = 4 * u * (1 - u) * self.jump_h
                img = S["stretch"] if (u < 0.3 or u > 0.7) else S["rot"][4]
            else:
                img = S["squash"]
                if k == n - 3 and self.emit:
                    self.emit(self.x, self.feet_y)
            if k >= n:
                self.after_jump()

        elif st == "dance":
            s = math.sin(self.age * 0.55)
            img = S["rot"][int((s + 1) / 2 * 8.99)]
            lift = abs(s) * 7
            if self.age > self.timer:
                self.set_state("idle", random.randint(30, 90))

        elif st == "walk":
            self.x += 1.3 * self.dir
            if self.x > self.BOUND_R:
                self.x, self.dir = self.BOUND_R, -1
            elif self.x < self.BOUND_L:
                self.x, self.dir = self.BOUND_L, 1
            s = math.sin(self.age * 0.45)
            img = self.sets[self.dir]["rot"][int((s + 1) / 2 * 8.99)]
            lift = abs(s) * 5
            if self.age > self.timer:
                self.set_state("idle", random.randint(25, 70))

        elif st == "slide":
            self.x += 4.8 * self.dir
            img = S["slide"]
            if self.age % 3 == 0 and self.emit:
                self.emit(self.x - self.dir * 34, self.feet_y)
            if self.age > self.timer or not (self.BOUND_L - 20 < self.x < self.BOUND_R + 20):
                self.x = max(self.BOUND_L, min(self.BOUND_R, self.x))
                self.set_state("idle", random.randint(35, 70))

        self.c.itemconfigure(self.item, image=img)
        self.c.coords(self.item, self.x, self.feet_y - lift)


# ───────────────────────── glass button ─────────────────────────
class GlassButton:
    """Pill-shaped canvas button with a frosted-glass look: a thin bright rim,
    a tinted body, a glossy upper sheen and a highlight line. Hover brightens it,
    pressing nudges it down."""

    VARIANTS = {
        "ice":  dict(border="#dff8ff", top="#4aa8dc", bot="#1c6ca8", htop="#6cc6f2", hbot="#2c8acb"),
        "deep": dict(border="#a8e2f7", top="#245a9c", bot="#0d2c60", htop="#3674bd", hbot="#173f80"),
        "aqua": dict(border="#e8fcff", top="#3cc2e6", bot="#1585b6", htop="#63dcf5", hbot="#229ccc"),
    }

    def __init__(self, canvas, cx, cy, text, command, w, h=42, variant="ice", size=12):
        c = self.c = canvas
        self.cmd, self.v = command, self.VARIANTS[variant]
        x1, x2, y1, y2 = cx - w / 2, cx + w / 2, cy - h / 2, cy + h / 2
        r = h / 2
        self.tag = f"glass{id(self)}"
        t = (self.tag,)
        v = self.v
        self.border = c.create_polygon(rrect(x1, y1, x2, y2, r), smooth=True, fill=v["border"],
                                       outline="", tags=t, state="hidden")
        self.body = c.create_polygon(rrect(x1 + 2, y1 + 2, x2 - 2, y2 - 2, r - 2), smooth=True,
                                     fill=v["bot"], outline="", tags=t, state="hidden")
        self.sheen = c.create_polygon(rrect(x1 + 5, y1 + 4, x2 - 5, cy, (cy - y1 - 4) / 2),
                                      smooth=True, fill=v["top"], outline="", tags=t, state="hidden")
        self.hl = c.create_line(x1 + r, y1 + 4, x2 - r, y1 + 4, fill="#f2fdff", width=1,
                                tags=t, state="hidden")
        self.label = c.create_text(cx, cy, text=text, fill="white",
                                   font=("Segoe UI", size, "bold"), tags=t, state="hidden")
        self.hover = self.pressed = False
        c.tag_bind(self.tag, "<Enter>", self._enter)
        c.tag_bind(self.tag, "<Leave>", self._leave)
        c.tag_bind(self.tag, "<ButtonPress-1>", self._press)
        c.tag_bind(self.tag, "<ButtonRelease-1>", self._release)

    def _paint(self):
        v = self.v
        self.c.itemconfigure(self.sheen, fill=v["htop"] if self.hover else v["top"])
        self.c.itemconfigure(self.body, fill=v["hbot"] if self.hover else v["bot"])

    def _enter(self, _e):
        self.hover = True
        self.c.config(cursor="hand2")
        self._paint()

    def _leave(self, _e):
        self.hover = False
        if self.pressed:
            self.pressed = False
            self.c.move(self.tag, 0, -1)
        self.c.config(cursor="")
        self._paint()

    def _press(self, _e):
        if not self.pressed:
            self.pressed = True
            self.c.move(self.tag, 0, 1)

    def _release(self, _e):
        if self.pressed:
            self.pressed = False
            self.c.move(self.tag, 0, -1)
            if self.hover:
                self.cmd()

    def show(self, visible):
        if not visible:
            if self.pressed:
                self.pressed = False
                self.c.move(self.tag, 0, -1)
            if self.hover:
                self.hover = False
                self.c.config(cursor="")
                self._paint()
        self.c.itemconfigure(self.tag, state="normal" if visible else "hidden")

    def set_text(self, text):
        self.c.itemconfigure(self.label, text=text)

    def raise_(self):
        self.c.tag_raise(self.tag)


# ───────────────────────── main app ─────────────────────────
class BirthdayApp:
    CARD_W, CARD_H, CARD_CY = 560, 440, 325
    EX1, EX2, EY1, EY2 = 375, 625, 328, 552      # envelope bounds
    ENV_CY = 440
    CX = 500
    DROP = 400

    def __init__(self, root, sheet, mail_path=None):
        self.root = root
        self.sheet = sheet
        root.title("❄ BALOOTLOOT DAY ❄")
        root.geometry(f"{W}x{H}")
        root.resizable(False, False)
        root.configure(bg=DEEP_NAVY)

        self.canvas = tk.Canvas(root, width=W, height=H, highlightthickness=0, bg=DEEP_NAVY)
        self.canvas.pack()

        env_src, self.paper = load_mail_assets(mail_path)
        self.env_frames = [ImageTk.PhotoImage(env_src.rotate(a, resample=Image.BICUBIC, expand=True))
                           for a in [-5 + 10 * i / 8 for i in range(9)]]
        px = self.paper.getpixel((self.paper.width // 2, self.paper.height // 2))
        self.card_bg = "#%02x%02x%02x" % px[:3]
        self.card_key, self.card_photo, self.env_dx, self.rock = None, None, 0.0, 0.0

        families = set(tkfont.families(root))

        def pick(names, fallback):
            return next((n for n in names if n in families), fallback)

        self.display_font = pick(["Segoe Script", "Lucida Handwriting", "Snell Roundhand",
                                  "Apple Chancery", "Monotype Corsiva", "Brush Script MT",
                                  "Palatino Linotype"], "Georgia")
        self.text_font = pick(["Palatino Linotype", "Georgia"], "Georgia")

        self.t = 0
        self.t0 = 0
        self.state = "envin"
        self.parts = []
        self.letter_ids, self.card_ids, self.env_ids = [], [], []
        self.bob_prev = 0.0
        self.home_visible = True
        self.home_t0 = 0

        self.music = Music()

        self.draw_scenery()
        self.make_penguins()
        self.make_snow()
        self.make_home_text()
        self.make_buttons()
        self.prepare_letter_text()
        self.go_envin(initial=True)

        root.protocol("WM_DELETE_WINDOW", self.on_quit)
        self.tick()

    # ---------- scenery ----------
    def draw_scenery(self):
        c = self.canvas
        bands = 70
        for i in range(bands):
            y1, y2 = i * H / bands, (i + 1) * H / bands + 1
            c.create_rectangle(0, y1, W, y2, outline="",
                               fill=lerp_color(DEEP_NAVY, GLACIER, (i / bands) ** 1.4))
        random.seed(7)
        for _ in range(55):
            x, y, r = random.randint(0, W), random.randint(0, 330), random.choice([1, 1, 2])
            c.create_oval(x - r, y - r, x + r, y + r, fill=lerp_color(CYAN, WHITE, random.random()),
                          outline="")
        random.seed()
        c.create_polygon(0, 700, 0, 470, 90, 420, 170, 490, 260, 380, 380, 500, 470, 430,
                         560, 520, 680, 400, 780, 490, 880, 410, 1000, 470, 1000, 700,
                         fill="#3b7fb5", outline="")
        for pts in [(260, 380, 235, 420, 285, 418), (680, 400, 650, 445, 712, 440),
                    (880, 410, 855, 448, 905, 446), (90, 420, 68, 455, 112, 452)]:
            c.create_polygon(*pts, fill=ICE, outline="")
        c.create_polygon(0, 700, 0, 540, 120, 500, 230, 560, 340, 515, 450, 575, 560, 540,
                         690, 585, 800, 520, 910, 570, 1000, 530, 1000, 700,
                         fill=GLACIER_LIGHT, outline="")
        c.create_polygon(120, 500, 90, 540, 160, 545, fill=CYAN, outline="")
        c.create_polygon(800, 520, 765, 560, 845, 560, fill=CYAN, outline="")
        c.create_polygon(0, 700, 0, 612, 160, 600, 380, 618, 620, 604, 840, 616, 1000, 602,
                         1000, 700, fill=ICE, outline=SILVER, width=2)
        c.create_polygon(0, 700, 0, 668, 250, 660, 520, 676, 760, 662, 1000, 672, 1000, 700,
                         fill=SILVER, outline="")

    def make_penguins(self):
        mk = lambda *a, **k: Penguin(self.canvas, self.sheet, *a, emit=self.spawn_puff, **k)
        self.penguins = [
            mk(PENGUIN_BOXES[3], 115, 628, 150),
            mk(PENGUIN_BOXES[4], 885, 634, 165),
            mk(PENGUIN_BOXES[2], 500, 668, 140, walker=True),
        ]

    def make_snow(self):
        self.flakes = []
        for _ in range(150):
            r = random.choice([1.5, 2, 2.5, 3, 4])
            x, y = random.uniform(0, W), random.uniform(0, H)
            item = self.canvas.create_oval(x - r, y - r, x + r, y + r, outline="",
                                           fill=random.choice([WHITE, WHITE, ICE, CYAN]))
            self.flakes.append({"id": item, "x": x, "y": y, "r": r,
                                "v": 0.6 + r * 0.45, "ph": random.uniform(0, 6.28)})

    def update_snow(self):
        for f in self.flakes:
            f["y"] += f["v"]
            f["x"] += math.sin(self.t * 0.03 + f["ph"]) * 0.6 + 0.25
            if f["y"] > H + 6:
                f["y"], f["x"] = -6, random.uniform(0, W)
            if f["x"] > W + 6:
                f["x"] = -6
            r = f["r"]
            self.canvas.coords(f["id"], f["x"] - r, f["y"] - r, f["x"] + r, f["y"] + r)

    # ---------- particles (sparkles + snow puffs) ----------
    def spawn(self, kind, x, y, vx, vy, life, size, color, g=0.0):
        c = self.canvas
        if kind == "star":
            item = c.create_polygon(star_pts(x, y, size), fill=color, outline="")
        else:
            item = c.create_oval(x - size, y - size, x + size, y + size, fill=color, outline="")
        self.parts.append(dict(id=item, kind=kind, x=x, y=y, vx=vx, vy=vy, life=life,
                               max=life, size=size, g=g))

    def spawn_puff(self, x, y):
        for _ in range(5):
            self.spawn("puff", x + random.uniform(-14, 14), y - random.uniform(0, 8),
                       random.uniform(-1.2, 1.2), random.uniform(-1.1, -0.2),
                       random.randint(16, 26), random.uniform(3, 6), WHITE, g=-0.02)

    def spawn_burst(self, x, y, n=40):
        for _ in range(n):
            a = random.uniform(0, 6.283)
            sp = random.uniform(2, 9)
            self.spawn("star", x, y, math.cos(a) * sp, math.sin(a) * sp - 2,
                       random.randint(40, 70), random.uniform(5, 10),
                       random.choice([WHITE, CYAN, SILVER, GLACIER_LIGHT]), g=0.18)

    def spawn_card_sparkle(self):
        cy = self.CARD_CY + self.bob_prev
        hw, hh = self.CARD_W / 2, self.CARD_H / 2
        side = random.choice("tblr")
        if side in "tb":
            x, y = 500 + random.uniform(-hw, hw), cy + (-hh if side == "t" else hh)
        else:
            x, y = 500 + (-hw if side == "l" else hw), cy + random.uniform(-hh, hh)
        self.spawn("star", x, y, random.uniform(-0.4, 0.4), random.uniform(-0.8, -0.2),
                   random.randint(28, 45), random.uniform(3, 7),
                   random.choice([WHITE, CYAN, SILVER]))

    def update_particles(self):
        alive = []
        for p in self.parts:
            p["life"] -= 1
            if p["life"] <= 0:
                self.canvas.delete(p["id"])
                continue
            p["x"] += p["vx"]
            p["y"] += p["vy"]
            p["vy"] += p["g"]
            s = max(0.6, p["size"] * p["life"] / p["max"])
            if p["kind"] == "star":
                self.canvas.coords(p["id"], *star_pts(p["x"], p["y"], s))
            else:
                self.canvas.coords(p["id"], p["x"] - s, p["y"] - s, p["x"] + s, p["y"] + s)
            alive.append(p)
        self.parts = alive

    # ---------- home texts & buttons ----------
    def make_home_text(self):
        c = self.canvas
        title = "Happy Birthday!"
        tfont = tkfont.Font(family=self.display_font, size=44, weight="bold")
        tw = tfont.measure(title)
        pw = max(580, tw + 200)
        x1, x2, y1, y2 = 500 - pw / 2, 500 + pw / 2, 135, 300
        self.panel_x1, self.panel_x2, self.panel_y1, self.panel_y2 = x1, x2, y1, y2
        self.panel_w = pw
        self.home_ty = 192
        bg = lerp_color(DEEP_NAVY, GLACIER, (217 / H) ** 1.4)
        self.panel_fill = lerp_color(bg, "#bfeaff", 0.16)

        # frosted-glass panel built from solid tints (no stipple, so it renders cleanly)
        panel = [
            c.create_polygon(rrect(x1 - 5, y1 - 5, x2 + 5, y2 + 5, 38), smooth=True,
                             fill=lerp_color(bg, CYAN, 0.14), outline=""),
            c.create_polygon(rrect(x1, y1, x2, y2, 32), smooth=True, fill=self.panel_fill,
                             outline=lerp_color(bg, WHITE, 0.55), width=2),
            c.create_polygon(rrect(x1 + 8, y1 + 6, x2 - 8, y1 + 78, 24), smooth=True,
                             fill=lerp_color(self.panel_fill, WHITE, 0.09), outline=""),
            c.create_line(x1 + 30, y1 + 3, x2 - 30, y1 + 3,
                          fill=lerp_color(self.panel_fill, WHITE, 0.7), width=2),
        ]
        self.shine = c.create_polygon(0, 0, 1, 0, 1, 1, 0, 1, fill=lerp_color(self.panel_fill, WHITE, 0.16),
                                      outline="", state="hidden")
        panel.append(self.shine)
        for it in panel:                       # let the snow fall in front of the glass
            c.tag_lower(it, self.flakes[0]["id"])

        # one canvas item per letter so every letter can move on its own
        self.home_letters = []
        letter_ids = []
        for i, ch in enumerate(title):
            if ch == " ":
                continue
            x = 500 - tw / 2 + tfont.measure(title[:i]) + tfont.measure(ch) / 2
            item = c.create_text(x, self.home_ty, text=ch, font=tfont, fill=WHITE, state="hidden")
            self.home_letters.append({"id": item, "x": x, "i": i})
            letter_ids.append(item)

        self.home_flake_x = [500 - (tw / 2 + 42), 500 + (tw / 2 + 42)]
        self.home_flakes = [c.create_text(x, self.home_ty, text="❄", fill="#d8fbff",
                                          font=("Segoe UI Symbol", 28), state="hidden")
                            for x in self.home_flake_x]
        self.sub_full = "LOOTLOOT THE PENGUIN QUEEN"
        self.sub_item = c.create_text(500, 264, text="", fill="#e4fbff",
                                      font=(self.text_font, 16, "italic"))
        self.home_ids = panel + letter_ids + self.home_flakes + [self.sub_item]

    def animate_home_text(self):
        c = self.canvas
        k = self.t - self.home_t0
        ty = self.home_ty
        # letters drop in with a bounce, then ride a gentle wave while a light ripple runs through them
        for L in self.home_letters:
            loc = (k - L["i"] * 3) / 30
            if loc <= 0:
                c.itemconfigure(L["id"], state="hidden")
                continue
            ramp = max(0.0, min(1.0, loc - 1))
            y = ty - 100 * (1 - ease_out_bounce(loc)) + math.sin(k * 0.08 - L["i"] * 0.55) * 5 * ramp
            u = (math.sin(k * 0.07 - L["i"] * 0.5) + 1) / 2
            col = lerp_color(self.panel_fill, lerp_color(WHITE, "#8feaff", u), min(1.0, loc * 2))
            c.coords(L["id"], L["x"], y)
            c.itemconfigure(L["id"], state="normal", fill=col)
        # snowflake ornaments fade in, sway and twinkle
        f = min(1.0, max(0.0, (k - 40) / 25))
        for j, item in enumerate(self.home_flakes):
            u = (math.sin(k * 0.09 + j * 2) + 1) / 2
            c.itemconfigure(item, state="normal" if f > 0 else "hidden",
                            fill=lerp_color(self.panel_fill, lerp_color("#bfeeff", WHITE, u), f))
            c.coords(item, self.home_flake_x[j] + math.sin(k * 0.06 + j * 3) * 5,
                     ty + math.sin(k * 0.05 + j) * 3)
        # subtitle is typed out, then softly breathes
        n = int(max(0, (k - 55) * 1.3))
        c.itemconfigure(self.sub_item, text=self.sub_full[:n])
        if n >= len(self.sub_full):
            u = (math.sin(k * 0.05) + 1) / 2
            c.itemconfigure(self.sub_item, fill=lerp_color("#a9dff2", "#ffffff", u))
        # a streak of light sweeps across the glass
        ph = ((k - 90) % 260) / 70
        if k > 90 and ph < 1:
            sx = self.panel_x1 - 40 + ph * (self.panel_w + 80)
            lo, hi = self.panel_x1 + 12, self.panel_x2 - 12
            xs = [min(hi, max(lo, v)) for v in (sx, sx + 34, sx + 4, sx - 30)]
            if max(xs) - min(xs) > 2:
                c.coords(self.shine, xs[0], self.panel_y1 + 8, xs[1], self.panel_y1 + 8,
                         xs[2], self.panel_y2 - 8, xs[3], self.panel_y2 - 8)
                c.itemconfigure(self.shine, state="normal")
            else:
                c.itemconfigure(self.shine, state="hidden")
        else:
            c.itemconfigure(self.shine, state="hidden")
        # twinkles popping off random letters
        if k > 60 and k % 16 == 0 and self.home_letters:
            L = random.choice(self.home_letters)
            self.spawn("star", L["x"] + random.uniform(-8, 8), ty + random.uniform(-25, 15),
                       0, -0.5, random.randint(22, 36), random.uniform(4, 8),
                       random.choice([WHITE, CYAN]))

    def show_home_text(self, visible):
        if visible and not self.home_visible:
            self.home_t0 = self.t          # replay the title entrance
        self.home_visible = visible
        for i in self.home_ids:
            self.canvas.itemconfigure(i, state="normal" if visible else "hidden")
        if visible:
            self.animate_home_text()

    def make_buttons(self):
        c = self.canvas
        self.open_btn = GlassButton(c, 500, 604, "✉  Open Your Letter", self.open_letter,
                                    240, 44, "aqua", 13)
        self.replay_btn = GlassButton(c, 410, 590, "↻  Replay", self.replay_letter, 140, 42, "ice")
        self.close_btn = GlassButton(c, 600, 590, "✕  Close Letter", self.close_letter, 176, 42, "deep")
        self.mute_btn = GlassButton(c, 500, 30, "🔊 Music On", self.toggle_music, 150, 36, "deep", 11)
        self.buttons = [self.open_btn, self.replay_btn, self.close_btn, self.mute_btn]
        self.mute_btn.show(True)

    def toggle_music(self):
        on = self.music.toggle()
        self.mute_btn.set_text("🔊 Music On" if on else "🔇 Music Off")

    def show_letter_buttons(self, visible):
        self.replay_btn.show(visible)
        self.close_btn.show(visible)

    # ---------- envelope + card ----------
    def create_envelope(self, dy):
        c = self.canvas
        self.env_dy, self.env_dx, self.rock = dy, 0.0, 0.0
        self.flap_q = 0.0
        self.card_key = None
        self.glow = c.create_polygon(0, 0, 10, 10, 20, 0, smooth=True, fill="#5bb8e0",
                                     outline="", state="hidden")
        self.card = c.create_image(500, self.ENV_CY + 5, anchor="center")
        self.env_img = c.create_image(500, self.ENV_CY + dy, image=self.env_frames[4],
                                      anchor="center")
        self.env_ids = [self.env_img]
        self.card_ids = [self.glow, self.card]
        self.layout_env()

    def layout_env(self, place_card=True):
        c = self.canvas
        idx = max(0, min(8, int(round(4 + max(-1.0, min(1.0, self.rock)) * 4))))
        c.itemconfigure(self.env_img, image=self.env_frames[idx])
        c.coords(self.env_img, 500 + self.env_dx, self.ENV_CY + self.env_dy)
        if place_card:
            self.set_card(500, self.ENV_CY + 5 + self.env_dy, 180, 130)

    def set_card(self, cx, cy, w, h, pulse=0.0):
        m = 2 * PAPER_INSET + 4
        wi, hi = max(m, int(w)), max(m, int(h))
        if (wi, hi) != self.card_key:
            self.card_key = (wi, hi)
            self.card_photo = ImageTk.PhotoImage(nine_slice(self.paper, wi, hi, PAPER_INSET))
            self.canvas.itemconfigure(self.card, image=self.card_photo)
        self.canvas.coords(self.card, cx, cy)
        hw, hh = wi / 2, hi / 2
        r = min(34, hw, hh)
        g = 9 + 4 * pulse
        self.canvas.coords(self.glow, *rrect(cx - hw - g, cy - hh - g, cx + hw + g, cy + hh + g, r + g))

    def destroy_scene(self):
        for i in self.letter_ids + self.card_ids + self.env_ids:
            self.canvas.delete(i)
        self.letter_ids, self.card_ids, self.env_ids = [], [], []

    # ---------- letter text ----------
    def prepare_letter_text(self):
        self.body_font = tkfont.Font(family="Georgia", size=12)
        max_w = self.CARD_W - 90
        paragraphs = [f"Dear {RECIPIENT},"] + LETTER_BODY.split("\n\n") + \
                     [f"With warm wishes,\n{SENDER} ❄"]
        lines = []
        for para in paragraphs:
            for raw in para.split("\n"):
                line = ""
                for word in raw.split():
                    trial = (line + " " + word).strip()
                    if self.body_font.measure(trial) <= max_w:
                        line = trial
                    else:
                        lines.append(line)
                        line = word
                lines.append(line)
            lines.append("")
        self.full_text = "\n".join(lines).rstrip()

    def build_letter_text(self):
        c = self.canvas
        top = self.CARD_CY - self.CARD_H / 2
        left = 500 - self.CARD_W / 2 + 45
        tfont = tkfont.Font(family=self.display_font, size=21, weight="bold")
        title = f"Happy Birthday, {RECIPIENT}!"
        tw = tfont.measure(title)
        self.title_letters, ids = [], []
        for i, ch in enumerate(title):
            if ch == " ":
                continue
            x = 500 - tw / 2 + tfont.measure(title[:i]) + tfont.measure(ch) / 2
            item = c.create_text(x, top + 66, text=ch, font=tfont, fill=self.card_bg)
            self.title_letters.append({"id": item, "i": i, "off": 0.0})
            ids.append(item)
        self.flake_items = [c.create_text(500 + dx, top + 26, text="❄", fill=self.card_bg,
                                          font=("Segoe UI Symbol", 14)) for dx in (-45, 0, 45)]
        self.line_item = c.create_line(500, top + 96, 500, top + 96, fill=GLACIER_LIGHT, width=2)
        self.body_item = c.create_text(left, top + 112, text="", anchor="nw", fill=NAVY,
                                       font=self.body_font, justify="left")
        self.letter_ids = self.flake_items + ids + [self.line_item, self.body_item]

    def animate_letter_title(self):
        c = self.canvas
        k = self.t - self.t0
        for L in self.title_letters:
            loc = (k - L["i"] * 2.5) / 26
            if loc <= 0:
                off, f = -40.0, 0.0
            else:
                ramp = max(0.0, min(1.0, loc - 1))
                off = -40 * (1 - ease_out_back(loc)) + math.sin(k * 0.09 - L["i"] * 0.5) * 2.5 * ramp
                f = min(1.0, loc * 1.5)
            c.move(L["id"], 0, off - L["off"])
            L["off"] = off
            u = (math.sin(k * 0.08 - L["i"] * 0.45) + 1) / 2
            c.itemconfigure(L["id"], fill=lerp_color(self.card_bg, lerp_color("#1d6fb0", "#2fa5dc", u), f))
        for j, item in enumerate(self.flake_items):
            f = min(1.0, max(0.0, (k - 8 - j * 6) / 20))
            u = (math.sin(k * 0.1 - j * 1.2) + 1) / 2
            c.itemconfigure(item, fill=lerp_color(self.card_bg, lerp_color(GLACIER_LIGHT, GLACIER, u), f))
        half = (self.CARD_W / 2 - 45) * ease(min(1.0, max(0.0, (k - 20) / 30)))
        y = c.coords(self.line_item)[1]
        c.coords(self.line_item, 500 - half, y, 500 + half, y)

    def clear_letter_text(self):
        for i in self.letter_ids:
            self.canvas.delete(i)
        self.letter_ids = []

    # ---------- user actions ----------
    def open_letter(self):
        if self.state != "home":
            return
        self.open_btn.show(False)
        self.show_letter_buttons(True)
        self.flap_q = 0.0
        self.state = "flap"

    def replay_letter(self):
        if self.state not in ("flap", "rise", "pop", "typing", "open"):
            return
        self.destroy_scene()
        self.create_envelope(0)
        self.show_home_text(True)
        self.bob_prev = 0.0
        self.state = "flap"

    def close_letter(self):
        if self.state in ("typing", "open"):
            self.clear_letter_text()
            self.show_home_text(True)
            self.show_letter_buttons(False)
            self.spawn_burst(500, self.CARD_CY + self.bob_prev, 24)
            self.cl = 1.0
            self.bob_cy = self.CARD_CY + self.bob_prev
            self.state = "closing"
        elif self.state in ("flap", "rise", "pop"):
            self.destroy_scene()
            self.go_envin()

    def go_envin(self, initial=False):
        self.destroy_scene()
        self.create_envelope(-450)
        self.show_home_text(True)
        self.show_letter_buttons(False)
        self.open_btn.show(False)
        self.env_c = 0.0
        self.bob_prev = 0.0
        self.state = "envin"

    # ---------- per-frame state machine ----------
    def update_scene(self):
        c, st = self.canvas, self.state
        pulse = (math.sin(self.t * 0.12) + 1) / 2

        if self.home_visible:
            self.animate_home_text()

        if st == "envin":
            self.env_c += 0.022
            self.env_dy = -450 * (1 - ease_out_bounce(self.env_c))
            self.rock = math.sin(self.env_c * 30) * (1 - self.env_c) * 0.8
            self.layout_env()
            if self.env_c >= 1:
                self.env_dy, self.rock = 0, 0.0
                self.layout_env()
                self.spawn_burst(500, self.EY2, 14)
                self.open_btn.show(True)
                self.state = "home"

        elif st == "home":
            self.env_dy = math.sin(self.t * 0.07) * 5
            self.rock = math.sin(self.t * 0.05) * 0.5
            self.layout_env()
            if self.t % 20 == 0:
                self.spawn("star", random.uniform(self.EX1 - 20, self.EX2 + 20),
                           random.uniform(self.EY1 - 30, self.EY2 + 10), 0, -0.4,
                           random.randint(25, 40), random.uniform(3, 6),
                           random.choice([WHITE, CYAN]))

        elif st == "flap":
            self.flap_q = min(1.0, self.flap_q + 0.035)      # the envelope shakes with excitement
            q = self.flap_q
            self.rock = math.sin(q * 42) * (1 - q)
            self.env_dx = math.sin(q * 60) * 6 * (1 - q)
            self.layout_env()
            if self.t % 3 == 0:
                self.spawn("star", random.uniform(self.EX1 - 20, self.EX2 + 20),
                           random.uniform(self.EY1 - 20, self.EY2), random.uniform(-1, 1),
                           random.uniform(-1.5, -0.3), 24, random.uniform(3, 6),
                           random.choice([WHITE, CYAN]))
            if q >= 1:
                self.rock = self.env_dx = 0.0
                self.layout_env()
                self.rise = 0.0
                self.state = "rise"

        elif st == "rise":
            self.rise += 0.03
            r = min(1.0, self.rise)
            base = self.ENV_CY + 5 + self.env_dy
            self.set_card(500, base - ease(r) * 190, 180, 130)   # paper slides out from behind
            if r >= 1:
                self.card_cy0 = base - 190
                self.card_w0 = 180
                self.pop_dy0 = self.env_dy
                self.pc = 0.0
                c.tag_raise(self.glow)
                c.tag_raise(self.card)
                c.itemconfigure(self.glow, state="normal")
                self.spawn_burst(500, self.card_cy0, 44)
                for p in self.penguins:
                    p.celebrate()
                self.state = "pop"

        elif st == "pop":
            self.pc += 0.028
            k = min(1.0, self.pc)
            s = ease_out_back(k)
            self.env_dy = self.pop_dy0 + ease(k) * self.DROP
            self.layout_env(place_card=False)
            w = self.card_w0 + (self.CARD_W - self.card_w0) * s
            h = 130 + (self.CARD_H - 130) * s
            cy = self.card_cy0 + (self.CARD_CY - self.card_cy0) * s
            self.set_card(500, cy, w, h)
            if k >= 1:
                for i in self.env_ids:
                    c.delete(i)
                self.env_ids = []
                self.show_home_text(False)
                self.build_letter_text()
                self.t0, self.bob_prev, self.chars = self.t, 0.0, 0.0
                self.state = "typing"

        elif st in ("typing", "open"):
            bob = math.sin((self.t - self.t0) * 0.05) * 5
            d, self.bob_prev = bob - self.bob_prev, bob
            self.set_card(500, self.CARD_CY + bob, self.CARD_W, self.CARD_H, pulse)
            for i in self.letter_ids:
                c.move(i, 0, d)
            c.itemconfigure(self.glow, fill=lerp_color("#4ea9d6", "#8fe0f5", pulse))
            self.animate_letter_title()
            if self.t % 5 == 0:
                self.spawn_card_sparkle()
            if st == "typing":
                if self.t - self.t0 > 38:      # body starts typing after the title lands
                    self.chars += 1.7
                n = int(self.chars)
                cursor = "▌" if (self.t // 8) % 2 == 0 else " "
                c.itemconfigure(self.body_item, text=self.full_text[:n] + cursor)
                if n >= len(self.full_text):
                    c.itemconfigure(self.body_item, text=self.full_text)
                    self.state = "open"

        elif st == "closing":
            self.cl -= 0.045
            s = ease(self.cl)
            self.set_card(500, self.bob_cy - (1 - s) * 60, self.CARD_W * s, self.CARD_H * s)
            if self.cl <= 0:
                self.go_envin()

    # ---------- loop ----------
    def tick(self):
        self.t += 1
        self.update_snow()
        for p in self.penguins:
            p.update()
        self.update_particles()
        self.update_scene()
        for b in self.buttons:
            b.raise_()
        self.root.after(FPS_MS, self.tick)

    def on_quit(self):
        self.music.stop()
        self.root.destroy()


def main():
    path = find_image()
    root = tk.Tk()
    if not path:
        messagebox.showerror(
            "Image not found",
            "Put 'Untitled Design.png' in the same folder as this script and run it again.")
        root.destroy()
        return
    sheet = Image.open(path)
    BirthdayApp(root, sheet, find_mail())
    root.mainloop()


if __name__ == "__main__":
    main()
