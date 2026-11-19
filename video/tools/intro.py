"""Animated opening for the KrishiNexus demo: title, then each Team Heat Wave member one by one, then the group photo.

`intro_frames()` yields 1920x1080 PIL images at 30 fps (about 18 s). Photos come from video/assets/ (team_5.webp,
team_6.webp, the team's own portraits); the yellow "Heat Wave" letters behind the heads are painted out of each crop.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

ASSETS = Path("C:/ai-congress/KrishiNexus/video/assets")
W, H, FPS = 1920, 1080, 30
NAVY = (20, 26, 51)  # the portraits' own background, so their edges disappear
NAVY_2 = (27, 35, 66)
YELLOW = (244, 194, 31)
WHITE = (255, 255, 255)
SOFT = (196, 205, 228)

TITLE_S, MEMBER_S, GROUP_S = 3.0, 2.1, 2.6

# (name, role, image, crop box) in the order they are introduced: the lead first, the advisor last.
MEMBERS = [
    ("Tanvir Hossin", "Team Lead", "team_5", (830, 330, 1170, 915)),
    ("Md. Omar Faruk", "AI/ML Engineer", "team_5", (30, 330, 370, 915)),
    ("Md. Abdur Rahman", "Full-Stack & Backend", "team_5", (425, 330, 765, 915)),
    ("Mohammed Mahmud Parvez", "Full-Stack Developer", "team_5", (1255, 330, 1595, 915)),
    ("Md. Morsalin", "Full-Stack & Backend", "team_5", (1635, 330, 1975, 915)),
    ("Md Rifat", "Advisor · Domain & Network Expert (online)", "team_6", (1380, 300, 1672, 765)),
]


def font(size: int, weight: str = "Bold") -> ImageFont.FreeTypeFont:
    f = ImageFont.truetype("C:/Windows/Fonts/bahnschrift.ttf", size)
    f.set_variation_by_name(weight)
    return f


F_TITLE, F_SUB, F_TAG = font(138), font(46, "SemiLight"), font(44, "SemiBold")
F_NAME, F_ROLE, F_LABEL, F_MARK = font(96), font(50, "SemiLight"), font(30, "SemiBold"), font(420)


def ease_out(x: float) -> float:
    x = min(1.0, max(0.0, x))
    return 1 - (1 - x) ** 3


def phase(t: float, start: float, end: float) -> float:
    return ease_out((t - start) / (end - start))


def portrait(image: str, box: tuple[int, int, int, int]) -> Image.Image:
    """The crop with the yellow title letters painted navy and a dark fade on the sides (neighbours' shoulders)."""
    img = Image.open(ASSETS / f"{image}.webp").convert("RGB").crop(box)
    h, s, v = img.convert("HSV").split()
    # The letters are a saturated yellow (hue about 33 of 255); skin is far less saturated, hair far darker.
    yellowish = ImageChops.multiply(ImageChops.multiply(h.point(lambda x: 255 if 22 <= x <= 46 else 0),
                                                        s.point(lambda x: 255 if x > 135 else 0)),
                                    v.point(lambda x: 255 if x > 55 else 0))
    top = Image.new("L", img.size, 0)
    top.paste(255, (0, 0, img.width, 95))  # only where the letters are, never the shirts
    mask = ImageChops.multiply(yellowish, top).filter(ImageFilter.MaxFilter(3))
    img.paste(Image.new("RGB", img.size, (20, 26, 51)), mask=mask)
    shade = Image.new("L", img.size, 0)
    d = ImageDraw.Draw(shade)
    edge = 46
    for i in range(edge):
        a = int(255 * (1 - i / edge) ** 1.6)
        d.line((i, 0, i, img.height), fill=a)
        d.line((img.width - 1 - i, 0, img.width - 1 - i, img.height), fill=a)
    img.paste(Image.new("RGB", img.size, (20, 26, 51)), mask=shade)
    return img


def base(t_total: float) -> Image.Image:
    img = Image.new("RGB", (W, H), NAVY)
    d = ImageDraw.Draw(img)
    x = -120 - 40 * t_total  # the watermark drifts slowly through the whole intro
    d.text((x, 560), "HEAT WAVE", font=F_MARK, fill=NAVY_2)
    return img


def text_alpha(img: Image.Image, xy, text, fnt, fill, alpha: float):
    if alpha <= 0:
        return
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(layer).text(xy, text, font=fnt, fill=(*fill, int(255 * min(1, alpha))))
    img.paste(Image.alpha_composite(img.convert("RGBA"), layer).convert("RGB"))


def title_frame(t: float) -> Image.Image:
    img = base(t)
    d = ImageDraw.Draw(img)
    out = 1 - phase(t, TITLE_S - 0.35, TITLE_S)
    a = phase(t, 0.0, 0.7) * out
    tw = d.textlength("KrishiNexus OS", font=F_TITLE)
    text_alpha(img, ((W - tw) / 2, 330 + 40 * (1 - phase(t, 0, 0.7))), "KrishiNexus OS", F_TITLE, WHITE, a)
    bar = 420 * phase(t, 0.4, 1.0)
    if bar > 1 and out > 0.05:
        ImageDraw.Draw(img).rectangle(((W - bar) / 2, 505, (W + bar) / 2, 513), fill=YELLOW)
    sub = "One AI operating system for Bangladesh's farm-to-market chain"
    sw = d.textlength(sub, font=F_SUB)
    text_alpha(img, ((W - sw) / 2, 548), sub, F_SUB, SOFT, phase(t, 0.8, 1.3) * out)
    tag = "Built by Team Heat Wave"
    gw = d.textlength(tag, font=F_TAG)
    text_alpha(img, ((W - gw) / 2, 630), tag, F_TAG, YELLOW, phase(t, 1.4, 1.9) * out)
    return img


def member_frame(i: int, photo: Image.Image, t: float, t_total: float) -> Image.Image:
    name, role, _, _ = MEMBERS[i]
    img = base(t_total)
    calm = img.copy()
    # Photo: a yellow block slides up behind it, then the portrait is wiped in from the bottom (always opaque, so the
    # block never tints a face) and zooms slowly.
    ph = 860
    scale = ph / photo.height * (1 + 0.035 * t / MEMBER_S)
    pic = photo.resize((int(photo.width * scale), int(photo.height * scale)), Image.LANCZOS)
    pw = pic.width
    cx = 1330 + int(120 * (1 - phase(t, 0.05, 0.5)))
    px, py = cx - pw // 2, H - pic.height
    d = ImageDraw.Draw(img)
    block_top = int(H - (H - py + 40) * phase(t, 0.0, 0.4))
    d.rectangle((px + 34, block_top, px + pw + 34, H), fill=YELLOW)
    shown = int(pic.height * phase(t, 0.12, 0.6))
    if shown > 0:
        img.paste(pic.crop((0, pic.height - shown, pw, pic.height)), (px, H - shown))
    # Text, left: a small label, the name rising, a growing underline, the role.
    x = 160
    label = "TEAM LEAD" if i == 0 else ("ADVISOR" if role.startswith("Advisor") else "TEAM HEAT WAVE")
    text_alpha(img, (x, 360), label, F_LABEL, SOFT, phase(t, 0.15, 0.5))
    rise = 40 * (1 - phase(t, 0.25, 0.7))
    size = 96
    while ImageDraw.Draw(img).textlength(name, font=font(size)) > 860 and size > 56:  # keep clear of the photo
        size -= 4
    fnt = F_NAME if size == 96 else font(size)
    text_alpha(img, (x, 410 + rise), name, fnt, WHITE, phase(t, 0.25, 0.7))
    bar = 170 * phase(t, 0.45, 0.8)
    if bar > 1:
        ImageDraw.Draw(img).rectangle((x, 540, x + bar, 548), fill=YELLOW)
    text_alpha(img, (x, 575), role, F_ROLE, YELLOW, phase(t, 0.55, 0.95))
    leave = phase(t, MEMBER_S - 0.3, MEMBER_S)
    return Image.blend(img, calm, leave) if leave > 0 else img


def group_frame(t: float, group: Image.Image) -> Image.Image:
    z = 1.10 - 0.10 * phase(t, 0, GROUP_S)
    gw, gh = int(W * z), int(H * z)
    pic = group.resize((gw, gh), Image.LANCZOS).crop(((gw - W) // 2, (gh - H) // 2, (gw - W) // 2 + W, (gh - H) // 2 + H))
    a = phase(t, 0, 0.35)
    return Image.blend(Image.new("RGB", (W, H), NAVY), pic, a)


def intro_frames():
    t_total = 0.0
    for k in range(int(TITLE_S * FPS)):
        yield title_frame(k / FPS)
    t_total += TITLE_S
    for i, (_, _, image, box) in enumerate(MEMBERS):
        photo = portrait(image, box)
        for k in range(int(MEMBER_S * FPS)):
            yield member_frame(i, photo, k / FPS, t_total + k / FPS)
        t_total += MEMBER_S
    group = Image.open(ASSETS / "team_6.webp").convert("RGB")
    group = group.resize((W, int(group.height * W / group.width)), Image.LANCZOS)
    if group.height < H:
        group = group.resize((int(group.width * H / group.height), H), Image.LANCZOS)
    group = group.crop(((group.width - W) // 2, (group.height - H) // 2, (group.width - W) // 2 + W, (group.height - H) // 2 + H))
    for k in range(int(GROUP_S * FPS)):
        yield group_frame(k / FPS, group)


if __name__ == "__main__":  # preview: a contact sheet of key moments
    frames = list(intro_frames())
    picks = [20, 80, 95, 140, 160, 220, 290, 350, 420, 470, 500, len(frames) - 5]
    sheet = Image.new("RGB", (480 * 4, 270 * 3))
    for n, f in enumerate(picks):
        sheet.paste(frames[f].resize((480, 270)), (480 * (n % 4), 270 * (n // 4)))
    sheet.save(Path(__file__).with_name("intro_sheet.jpg"), quality=85)
    print(len(frames), "frames", len(frames) / FPS, "s")
