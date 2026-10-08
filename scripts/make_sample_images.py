"""Generates the flat-illustration sample photos used by the "Try a sample" buttons (no camera needed).
They are illustrations, not photographs: the demo AI keys off the file name, and a real vision model
(Bedrock) may be less sure about them than about a real photo."""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

OUT = Path(__file__).resolve().parent.parent / "frontend" / "public" / "samples"
W, H = 800, 600
BG, FLOOR = "#E9EFF0", "#D5DEE0"


def canvas() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)
    d.rectangle([0, 430, W, H], fill=FLOOR)
    return im, d


def shadow(im: Image.Image, box, blur=14) -> Image.Image:
    layer = Image.new("RGBA", im.size, (0, 0, 0, 0))
    ImageDraw.Draw(layer).ellipse(box, fill=(13, 27, 30, 70))
    return Image.alpha_composite(im.convert("RGBA"), layer.filter(ImageFilter.GaussianBlur(blur))).convert("RGB")


def laptop():
    im, _ = canvas()
    im = shadow(im, [120, 430, 680, 500])
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([190, 130, 610, 370], 18, fill="#2A3C40")
    d.rounded_rectangle([205, 145, 595, 355], 8, fill="#14797F")
    d.polygon([(205, 355), (330, 235), (410, 310), (470, 255), (595, 355)], fill="#A3CFD1")
    d.ellipse([500, 170, 548, 218], fill="#F5B83D")
    d.polygon([(150, 380), (650, 380), (700, 440), (100, 440)], fill="#566A6F")
    d.rounded_rectangle([320, 395, 480, 425], 8, fill="#73868B")
    for k in range(9):
        d.rectangle([170 + k * 52, 388, 200 + k * 52, 394], fill="#8FA0A4")
    return im


def phone():
    im, _ = canvas()
    im = shadow(im, [280, 440, 520, 490])
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([290, 70, 510, 470], 34, fill="#1B2A2E")
    d.rounded_rectangle([302, 86, 498, 454], 24, fill="#0E5257")
    d.rounded_rectangle([325, 120, 475, 200], 14, fill="#14797F")
    for r in range(3):
        for c in range(3):
            d.rounded_rectangle([325 + c * 52, 225 + r * 62, 366 + c * 52, 270 + r * 62], 10, fill="#A3CFD1")
    d.rounded_rectangle([370, 92, 430, 102], 5, fill="#1B2A2E")
    d.rectangle([507, 150, 512, 210], fill="#566A6F")
    return im


def charger():
    im, _ = canvas()
    im = shadow(im, [250, 430, 560, 490])
    d = ImageDraw.Draw(im)
    d.rectangle([365, 90, 378, 150], fill="#8FA0A4")
    d.rectangle([425, 90, 438, 150], fill="#8FA0A4")
    d.rounded_rectangle([320, 145, 480, 350], 22, fill="#F7F9F9", outline="#CBD6D9", width=4)
    d.rounded_rectangle([345, 285, 455, 305], 8, fill="#E1E8EA")
    pts = [(400, 350), (400, 390), (330, 420), (260, 400), (300, 360), (230, 330), (160, 360), (170, 420), (250, 460), (360, 470), (470, 440), (560, 460)]
    d.line(pts, fill="#0D1B1E", width=9, joint="curve")
    d.rounded_rectangle([555, 442, 625, 480], 8, fill="#566A6F")
    return im


def power_bank():
    im, _ = canvas()
    im = shadow(im, [200, 440, 600, 500])
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([210, 200, 590, 420], 30, fill="#2A3C40")
    d.rounded_rectangle([225, 215, 575, 405], 22, fill="#3A5258")
    for k in range(4):
        d.ellipse([260 + k * 42, 250, 282 + k * 42, 272], fill="#F5B83D" if k < 3 else "#73868B")
    d.rounded_rectangle([430, 245, 540, 275], 6, fill="#0D1B1E")
    d.text((262, 330), "10000 mAh", fill="#CBD6D9")
    d.line([(590, 300), (650, 300), (690, 340)], fill="#0D1B1E", width=8)
    return im


def mixed_bin():
    im, _ = canvas()
    im = shadow(im, [190, 470, 610, 520])
    d = ImageDraw.Draw(im)
    d.ellipse([240, 140, 300, 260], fill="#5AA6E0")                      # plastic bottle
    d.rectangle([262, 120, 280, 145], fill="#5AA6E0")
    d.rectangle([340, 150, 470, 240], fill="#F7F9F9", outline="#CBD6D9")  # paper
    d.rectangle([360, 130, 490, 215], fill="#EFE7D4", outline="#CBD6D9")
    d.rounded_rectangle([510, 150, 580, 250], 10, fill="#B7C0C4")        # metal can
    d.ellipse([300, 230, 380, 300], fill="#E8892B")                      # organic: orange peel
    d.line([(420, 235), (470, 205), (520, 245), (560, 210)], fill="#0D1B1E", width=7)  # charger cable
    d.rounded_rectangle([590, 215, 622, 262], 5, fill="#2A3C40")        # loose battery
    d.rectangle([600, 209, 612, 215], fill="#8FA0A4")
    d.polygon([(215, 250), (585, 250), (545, 470), (255, 470)], fill="#3A5258")
    d.rectangle([205, 238, 595, 256], fill="#2A3C40")
    for k in range(5):
        d.line([(265 + k * 68, 262), (277 + k * 62, 460)], fill="#2F454A", width=3)
    return im


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    for name, fn in {"laptop": laptop, "phone": phone, "charger": charger, "power-bank": power_bank, "mixed-bin": mixed_bin}.items():
        fn().save(OUT / f"{name}.jpg", "JPEG", quality=88)
        print("wrote", OUT / f"{name}.jpg")
