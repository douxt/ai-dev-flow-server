"""P0+P1 验证测试：semaphore 限并发 + 1024px 缩放阈值"""
import io, sys, os, time, asyncio
from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'components', 'event_listener'))
from default import _resize_image

def test_resize_large_image():
    """P1: 大图 >1024px 应被缩放到 ≤1024px"""
    img = Image.new('RGB', (3000, 2000), color='red')
    buf = io.BytesIO()
    img.save(buf, format='JPEG', quality=95)
    original = buf.getvalue()

    result = _resize_image(original)
    result_img = Image.open(io.BytesIO(result))
    w, h = result_img.size

    assert max(w, h) <= 1024, f'FAIL: {w}x{h} exceeds 1024px limit'
    assert len(result) < len(original), f'FAIL: resized {len(result)} >= original {len(original)}'
    print(f'  PASS: {3000}x{2000} → {w}x{h}, {len(original)//1024}KB → {len(result)//1024}KB')

def test_no_resize_small_image():
    """P1: 小图 ≤1024px 不应被缩放"""
    img = Image.new('RGB', (800, 600), color='blue')
    buf = io.BytesIO()
    img.save(buf, format='JPEG', quality=95)
    original = buf.getvalue()

    result = _resize_image(original)
    result_img = Image.open(io.BytesIO(result))
    w, h = result_img.size

    assert w == 800 and h == 600, f'FAIL: {800}x{600} was resized to {w}x{h}'
    print(f'  PASS: {800}x{600} unchanged')

def test_resize_jumbo_pixels():
    """P1: 超大像素量 (4096*4096) 应触发缩放"""
    img = Image.new('RGB', (3000, 3000), color='green')
    buf = io.BytesIO()
    img.save(buf, format='JPEG', quality=95)
    original = buf.getvalue()

    result = _resize_image(original)
    result_img = Image.open(io.BytesIO(result))
    w, h = result_img.size

    assert max(w, h) <= 1024, f'FAIL: {w}x{h} exceeds 1024px'
    assert w * h <= 1024 * 1024, f'FAIL: {w*h} pixels exceeds 1024*1024'
    print(f'  PASS: {3000}x{3000} → {w}x{h}, {len(original)//1024}KB → {len(result)//1024}KB')

def test_png_to_jpeg():
    """P1: RGBA PNG → JPEG 转换 + 缩放"""
    img = Image.new('RGBA', (2000, 1500), color=(255, 0, 0, 128))
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    original = buf.getvalue()

    result = _resize_image(original)
    result_img = Image.open(io.BytesIO(result))

    assert result_img.mode == 'RGB', f'FAIL: mode={result_img.mode}, expected RGB'
    assert max(result_img.size) <= 1024
    print(f'  PASS: RGBA PNG {2000}x{1500} → {result_img.mode} {result_img.size[0]}x{result_img.size[1]}, {len(original)//1024}KB → {len(result)//1024}KB')

if __name__ == '__main__':
    print('=== P1: resize 阈值 1024px ===')
    test_resize_large_image()
    test_no_resize_small_image()
    test_resize_jumbo_pixels()
    test_png_to_jpeg()
    print('=== P1: all tests passed ===')
    print()
    print('=== P0: semaphore 验证 ===')
    print('  semaphore=2 限制并发 LLM 调用，gate log 中多图场景应观察到：')
    print('  - img[0] llm_ok → img[1] llm_ok → (wait) → img[2] llm_ok → img[3] llm_ok → (wait) → ...')
    print('  - 即每批最多 2 张同时调用 LLM API')
    print('  - 部署后发 3+ 张图到测试群验证')
