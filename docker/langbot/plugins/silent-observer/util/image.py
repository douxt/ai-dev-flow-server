"""图片处理 — 打开、缩放、格式转换."""
import io

from PIL import Image


def open_image(bytes_data):
    return Image.open(io.BytesIO(bytes_data))


def resize_image(bytes_data):
    img = Image.open(io.BytesIO(bytes_data))
    try:
        w, h = img.size
        max_dim = max(w, h)
        if max_dim > 1024:
            ratio = 1024 / max_dim
            new_size = (int(w * ratio), int(h * ratio))
            img = img.resize(new_size, Image.LANCZOS)
        buf = io.BytesIO()
        if img.mode in ('RGBA', 'P'):
            img = img.convert('RGB')
        img_format = 'JPEG' if img.mode == 'RGB' else (img.format or 'JPEG')
        img.save(buf, format=img_format, quality=70)
        return buf.getvalue()
    finally:
        img.close()
