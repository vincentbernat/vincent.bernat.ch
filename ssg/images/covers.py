"""Cover images for social networks."""

import base64
import functools
import io
import json
import math
import pathlib
import tempfile
import unicodedata

import skia
from PIL import Image

from .. import config, deps
from ..tools import ProcessHelper


class Cover:
    """Generate OG cover images (1200x630) for articles."""

    WIDTH = 1200
    HEIGHT = 630
    BG_COLOR = (255, 249, 240)  # #fff9f0
    AUTHOR_COLOR = (100, 100, 100)

    @functools.cached_property
    def icon(self) -> Image.Image:
        icon = config.CONTENT / "media" / "images" / "favicon.png"
        return (
            Image.open(icon)
            .convert("RGBA")
            .resize((128, 128), Image.Resampling.NEAREST)
        )

    @functools.cached_property
    def typeface(self) -> skia.Typeface:
        typeface = skia.Typeface.MakeFromName(
            "Noto Sans Display SemiBold",
            skia.FontStyle(
                600, skia.FontStyle.kNormal_Width, skia.FontStyle.kUpright_Slant
            ),
        )
        if typeface is None:
            raise RuntimeError("cannot find font for cover images")
        return typeface

    @functools.cached_property
    def title_font(self) -> skia.Font:
        return skia.Font(self.typeface, 64)

    @functools.cached_property
    def author_font(self) -> skia.Font:
        return skia.Font(self.typeface, 32)

    @functools.cached_property
    def firefox_profile(self) -> str:
        return tempfile.mkdtemp(prefix="ssg-firefox-")

    @functools.cached_property
    def firefox(self) -> ProcessHelper:
        script = pathlib.Path(__file__).parent / "firefox.mjs"
        return ProcessHelper("node", str(script), self.firefox_profile)

    @staticmethod
    def render_text(
        text: str, font: skia.Font, color: tuple[int, int, int]
    ) -> Image.Image:
        """Render text to a PIL RGBA image using skia."""
        width = math.ceil(font.measureText(text)) + 2
        metrics = font.getMetrics()
        ascent = math.ceil(-metrics.fAscent)
        descent = math.ceil(metrics.fDescent)
        height = ascent + descent
        if width <= 0 or height <= 0:
            return Image.new("RGBA", (1, 1), (0, 0, 0, 0))

        surface = skia.Surface(width, height)
        canvas = surface.getCanvas()
        canvas.clear(skia.ColorTRANSPARENT)
        r, g, b = color
        paint = skia.Paint(AntiAlias=True)
        paint.setColor(skia.Color(r, g, b, 255))
        canvas.drawString(text, 0, ascent, font, paint)

        sk_img = surface.makeImageSnapshot()
        info = skia.ImageInfo.Make(
            width,
            height,
            skia.ColorType.kRGBA_8888_ColorType,
            skia.AlphaType.kUnpremul_AlphaType,
        )
        data = bytearray(width * height * 4)
        sk_img.readPixels(info, data, width * 4)
        return Image.frombytes("RGBA", (width, height), bytes(data))

    def load(self, path: pathlib.Path, width: int) -> Image.Image:
        """Load a cover image (SVG or raster) and return as RGBA."""
        match pathlib.Path(path).suffix:
            case ".svg":
                return self.load_svg(path, width)
            case _:
                return self.load_raster(path)

    def load_raster(self, path: pathlib.Path) -> Image.Image:
        return Image.open(path).convert("RGBA")

    def load_svg(self, path: pathlib.Path, width: int) -> Image.Image:
        """Render an SVG image with Firefox, twice the given width."""
        width *= 2
        r, g, b = self.BG_COLOR
        src = pathlib.Path(path).resolve().as_uri()
        with tempfile.TemporaryDirectory() as tmp:
            html = pathlib.Path(tmp) / "cover.html"
            html.write_text(
                '<body style="margin:0">'
                f'<img src="{src}" style="display:block;width:{width}px;'
                f'background:rgb({r},{g},{b})">'
            )
            request = {
                "url": html.as_uri(),
                "width": width,
                "height": 100,
                "selector": "img",
            }
            with self.firefox:
                self.firefox.send(json.dumps(request) + "\n")
                answer = json.loads(self.firefox.readline())
                if "error" in answer:
                    errors = self.firefox.errors()
                    raise RuntimeError(f"{path}: {answer['error']}\n{errors}")
        return Image.open(io.BytesIO(base64.b64decode(answer["png"]))).convert("RGBA")

    @functools.cache
    def render_author(self, author: str) -> Image.Image:
        return self.render_text(author, self.author_font, self.AUTHOR_COLOR)

    @staticmethod
    def wrap_text(text: str, font: skia.Font, max_width: float) -> list[str]:
        """Word-wrap text to fit within max_width, then balance line widths."""
        words = text.split()
        if not words:
            return []

        def line_width(s: str) -> float:
            return font.measureText(s)

        def wrap(width: float) -> list[str]:
            """Greedily fit the words into lines no wider than width."""
            lines = []
            current = ""
            for word in words:
                test = f"{current} {word}".strip()
                if line_width(test) <= width:
                    current = test
                else:
                    if current:
                        lines.append(current)
                    current = word
            if current:
                lines.append(current)
            return lines

        lines = wrap(max_width)
        n = len(lines)
        if n <= 1:
            return lines

        # Balance: binary search for the smallest width that fits in n lines
        lo, hi = max(line_width(w) for w in words), max_width
        while lo < hi:
            mid = (lo + hi) // 2
            if len(wrap(mid)) <= n:
                hi = mid
            else:
                lo = mid + 1

        return wrap(hi)

    def generate(
        self, title: str, author: str, cover: pathlib.Path | None, target: pathlib.Path
    ) -> None:
        """Generate a 1200x630 OG cover image."""
        # Fonts are found with Fontconfig
        deps.getenv("FONTCONFIG_FILE", "")
        W, H = self.WIDTH, self.HEIGHT
        title = "".join(
            ch
            for ch in title.split(" | ", 1)[0]
            if unicodedata.category(ch) != "Cf"
            and (self.typeface.unicharToGlyph(ord(ch)) != 0 or ch == " ")
        )

        font = self.title_font
        line_height = int(font.getSize() * 1.2)
        margin = 40
        icon_w, icon_h = self.icon.size

        if cover:
            # Layout: icon left, title + author right, at bottom
            gap = 20
            text_x = margin + icon_w + gap
            max_width = W - text_x - margin
            lines = self.wrap_text(title, font, max_width)

            author_img = self.render_author(author)
            author_gap = 8

            text_block_h = len(lines) * line_height + author_gap + author_img.height
            block_h = max(icon_h, text_block_h)

            # Position block at bottom
            bottom_margin = 40
            block_y = H - bottom_margin - block_h

            # Load cover and crop to fill 1200x630
            image = self.load(cover, W)
            target_ratio = W / H
            cover_ratio = image.width / image.height
            if cover_ratio > target_ratio:
                new_w = int(image.height * target_ratio)
                left = (image.width - new_w) // 2
                image = image.crop((left, 0, left + new_w, image.height))
            else:
                new_h = int(image.width / target_ratio)
                top = (image.height - new_h) // 2
                image = image.crop((0, top, image.width, top + new_h))
            image = image.resize((W, H), Image.Resampling.LANCZOS)
            img = Image.new("RGB", (W, H), self.BG_COLOR)
            img.paste(image, (0, 0), image)

            # Gradient: start depends on block position
            bg = self.BG_COLOR
            gradient_end = block_y
            gradient_start = max(0, gradient_end - int(H * 0.35))
            overlay = Image.new("RGBA", (W, H), (*bg, 0))
            for row_y in range(gradient_start, H):
                if row_y < gradient_end:
                    alpha = int(
                        255 * (row_y - gradient_start) / (gradient_end - gradient_start)
                    )
                else:
                    alpha = 255
                row = Image.new("RGBA", (W, 1), (*bg, alpha))
                overlay.paste(row, (0, row_y))
            img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")

            # Icon vertically centered with text block
            icon_y = block_y + (block_h - icon_h) // 2
            img.paste(self.icon, (margin, icon_y), self.icon)

            # Title left-aligned, vertically centered in block
            y: float = block_y + (block_h - text_block_h) // 2
            for line in lines:
                line_img = self.render_text(line, font, (0, 0, 0))
                img.paste(line_img, (text_x, int(y)), line_img)
                y += line_height

            # Author below title
            y += author_gap
            img.paste(author_img, (text_x, int(y)), author_img)
        else:
            max_width = W - 120
            lines = self.wrap_text(title, font, max_width)
            total_title_height = len(lines) * line_height

            img = Image.new("RGB", (W, H), self.BG_COLOR)

            # Title (almost) centered
            y = (H - total_title_height + line_height) / 2
            for line in lines:
                line_img = self.render_text(line, font, (0, 0, 0))
                x = (W - line_img.width) / 2
                img.paste(line_img, (int(x), int(y)), line_img)
                y += line_height

            # Branding: icon + author in upper left
            author_img = self.render_author(author)
            img.paste(self.icon, (margin, margin), self.icon)
            author_y = margin + (icon_h - author_img.height) // 2
            img.paste(author_img, (margin + icon_w + margin, author_y), author_img)

        target.parent.mkdir(parents=True, exist_ok=True)
        img.save(target, "JPEG", quality=100)


generate = Cover().generate
