"""分享卡片：Pillow 服务端渲染（一期），后续可换 Playwright 渲染 HTML 模板。"""

import io
import os

from PIL import Image, ImageDraw, ImageFont

from app.constants import OVERALL_LEVELS
from app.services.storage import storage

W, H = 750, 1000
LEVEL_COLORS = {
    "benchmark": "#1f8a4c",
    "good": "#3aa76d",
    "neutral": "#8c8c8c",
    "disputed": "#d98a1a",
    "severe": "#c2352b",
    "insufficient": "#a0a0a0",
}

FONT_CANDIDATES = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
    "/System/Library/Fonts/PingFang.ttc",
    "C:/Windows/Fonts/msyh.ttc",
]


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in FONT_CANDIDATES:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _wrap(draw: ImageDraw.ImageDraw, text: str, font, max_width: int) -> list[str]:
    lines, cur = [], ""
    for ch in text:
        if draw.textlength(cur + ch, font=font) > max_width:
            lines.append(cur)
            cur = ch
        else:
            cur += ch
    if cur:
        lines.append(cur)
    return lines


def render_merchant_card(name: str, level: str, facts: list[str], updated: str, qrcode: bytes | None = None) -> str:
    img = Image.new("RGB", (W, H), "#fafafa")
    d = ImageDraw.Draw(img)
    color = LEVEL_COLORS.get(level, "#8c8c8c")

    d.rectangle([0, 0, W, 220], fill=color)
    d.text((48, 48), name, font=_font(48), fill="white")
    d.text((48, 130), f"平台评级：{OVERALL_LEVELS.get(level, level)}", font=_font(34), fill="white")

    y = 270
    d.text((48, y), "关键事实", font=_font(30), fill="#333")
    y += 56
    body = _font(26)
    for fact in facts[:3]:
        for line in _wrap(d, "• " + fact, body, W - 96)[:3]:
            d.text((48, y), line, font=body, fill="#444")
            y += 40
        y += 12

    if qrcode:
        qr = Image.open(io.BytesIO(qrcode)).convert("RGB").resize((200, 200))
        img.paste(qr, (W - 248, H - 260))
    else:
        d.rectangle([W - 248, H - 260, W - 48, H - 60], outline="#ccc", width=2)
        d.text((W - 210, H - 170), "小程序码", font=_font(24), fill="#999")

    foot = _font(22)
    d.text((48, H - 200), f"最近更新：{updated}", font=foot, fill="#888")
    d.text((48, H - 160), "评级依据来自公开信息整理", font=foot, fill="#888")
    d.text((48, H - 120), "用户评价未经核实，详见小程序", font=foot, fill="#888")

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return storage.put_bytes(buf.getvalue(), "png", prefix="cards", content_type="image/png")
