"""'미장' 앱 아이콘 생성: python android/tools/make_icons.py <Noto Sans CJK KR Bold 폰트 경로>"""

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

RES = Path(__file__).resolve().parent.parent / "app" / "src" / "main" / "res"
TEXT = "미장"
DENSITIES = {"mdpi": 1, "hdpi": 1.5, "xhdpi": 2, "xxhdpi": 3, "xxxhdpi": 4}
SCALE = 4  # 슈퍼샘플링 후 축소해서 가장자리를 부드럽게


def draw_text(img: Image.Image, font_path: str, text_width_ratio: float) -> None:
    w, h = img.size
    draw = ImageDraw.Draw(img)
    size = int(h * 0.5)
    font = ImageFont.truetype(font_path, size)
    while draw.textlength(TEXT, font=font) > w * text_width_ratio:
        size -= 2
        font = ImageFont.truetype(font_path, size)
    draw.text((w / 2, h / 2), TEXT, font=font, fill="white", anchor="mm")


def legacy(px: int, font_path: str) -> Image.Image:
    """검은 둥근 사각형 + 흰 글자 (구형 런처, 알림 큰 아이콘용)."""
    big = Image.new("RGBA", (px * SCALE, px * SCALE), (0, 0, 0, 0))
    ImageDraw.Draw(big).rounded_rectangle(
        (0, 0, big.width - 1, big.height - 1), radius=int(big.width * 0.3), fill="black"
    )
    draw_text(big, font_path, 0.64)
    return big.resize((px, px), Image.LANCZOS)


def foreground(px: int, font_path: str) -> Image.Image:
    """적응형 아이콘 전경 (108dp 중 가운데 66dp가 보이는 영역)."""
    big = Image.new("RGBA", (px * SCALE, px * SCALE), (0, 0, 0, 0))
    draw_text(big, font_path, 0.64 * 66 / 108)
    return big.resize((px, px), Image.LANCZOS)


def main(font_path: str) -> None:
    for name, d in DENSITIES.items():
        out = RES / f"mipmap-{name}"
        out.mkdir(parents=True, exist_ok=True)
        legacy(round(48 * d), font_path).save(out / "ic_launcher.png")
        foreground(round(108 * d), font_path).save(out / "ic_launcher_foreground.png")
    nodpi = RES / "drawable-nodpi"
    nodpi.mkdir(parents=True, exist_ok=True)
    legacy(256, font_path).save(nodpi / "ic_notif_large.png")
    legacy(512, font_path).save(Path(__file__).resolve().parent / "icon_preview.png")


if __name__ == "__main__":
    main(sys.argv[1])
