#!/usr/bin/env python3
"""Klore 源码补丁：models.py (3处) + ingester.py (1处)。pip upgrade 后需重跑。"""
import shutil
from pathlib import Path

venv = Path("/home/coder/.venvs/klore")
models = next(venv.glob("lib/python*/site-packages/klore/models.py"))
ingester = next(venv.glob("lib/python*/site-packages/klore/ingester.py"))

# 备份
for f in (models, ingester):
    bak = f.with_suffix(".py.bak")
    if not bak.exists():
        shutil.copy2(f, bak)

# --- models.py: 3 处修改 ---
content = models.read_text()

# 1. OPENROUTER_BASE_URL → DeepSeek
content = content.replace(
    "https://openrouter.ai/api/v1", "https://api.deepseek.com"
)

# 2. DEFAULT_MODELS 三级全部 → deepseek-v4-flash
for tier in ("fast", "strong", "director"):
    content = content.replace(
        f'"{tier}": "google/gemini-3-flash-preview"',
        f'"{tier}": "deepseek-v4-flash"',
    )
    content = content.replace(
        f'"{tier}": "google/gemini-3.1-pro-preview"',
        f'"{tier}": "deepseek-v4-flash"',
    )

# 3. CONTEXT_LIMITS 新增 deepseek-v4-flash
if '"deepseek-v4-flash"' not in content:
    marker = "CONTEXT_LIMITS: dict[str, int] = {"
    content = content.replace(
        marker, marker + '\n    "deepseek-v4-flash": 1_000_000,'
    )

models.write_text(content)

# --- ingester.py: slugify() 替换为 Unicode 版本 ---
content = ingester.read_text()
old = '''def slugify(text: str) -> str:
    """Convert text to a filename-safe slug."""
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = re.sub(r"&[a-zA-Z]+;", " ", text)
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s-]", " ", text)
    text = re.sub(r"[\s-]+", "-", text).strip("-")
    return text or "untitled"'''

new = '''def slugify(text: str, max_len: int = 80) -> str:
    """Convert text to a filename-safe slug, truncated to max_len."""
    original = text
    text = unicodedata.normalize("NFKD", text)
    text = re.sub(r"[^\w\s-]", " ", text, flags=re.UNICODE)
    text = re.sub(r"&[a-zA-Z]+;", " ", text)
    text = text.lower()
    text = re.sub(r"[\s-]+", "-", text).strip("-")
    if len(text) > max_len:
        text = text[:max_len].rstrip("-")
        if "-" in text:
            last_dash = text.rfind("-")
            if last_dash > max_len * 0.6:
                text = text[:last_dash]
    import hashlib
    return text or "untitled-" + hashlib.sha256(original.encode()).hexdigest()[:8]'''

if old in content:
    content = content.replace(old, new)
    ingester.write_text(content)
else:
    print(
        "WARNING: slugify() original not found — "
        "patch may already be applied or upstream changed"
    )

print("Klore patches applied successfully.")
