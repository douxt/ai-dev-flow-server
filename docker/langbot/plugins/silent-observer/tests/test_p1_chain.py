"""P1: 消息链操作测试 — 使用 Fake 组件，无需 Docker"""
import pytest
from tests.conftest import FakePlain, FakeFace, FakeUnknown, FakeImage, FakeQuote, FakeForward, FakeForwardNode, FakeAt


class TestStripBase64:
    def test_image_base64_cleared(self, listener):
        img = FakeImage(url='https://x.com/i.png', base64='data:image/png;base64,AAAA')
        chain = [img]
        listener._strip_base64(chain)
        assert img.base64 == ''

    def test_url_preserved(self, listener):
        img = FakeImage(url='https://x.com/i.png', base64='xxx')
        listener._strip_base64([img])
        assert img.url == 'https://x.com/i.png'

    def test_quote_recursive(self, listener):
        img = FakeImage(url='https://x.com/i.png', base64='xxx')
        quote = FakeQuote(origin=[img])
        listener._strip_base64([quote])
        assert img.base64 == ''

    def test_forward_recursive(self, listener):
        img = FakeImage(url='https://x.com/i.png', base64='xxx')
        node = FakeForwardNode(message_chain=[img])
        fwd = FakeForward(node_list=[node])
        listener._strip_base64([fwd])
        assert img.base64 == ''

    def test_none_safe(self, listener):
        listener._strip_base64(None)  # 不抛异常


class TestExtractFaces:
    def test_pure_face_chain(self, listener):
        chain = [FakeFace(face_id=14, face_name='')]
        result = listener._extract_faces(chain)
        assert '惊讶' in result

    def test_mixed_chain(self, listener):
        chain = [FakeFace(face_id=0, face_name=''), FakePlain(text='hello'),
                 FakeFace(face_id=14, face_name='惊讶')]
        result = listener._extract_faces(chain)
        assert '微笑' in result
        assert '惊讶' in result

    def test_empty_chain(self, listener):
        assert listener._extract_faces([]) == ''
        assert listener._extract_faces(None) == ''

    def test_unknown_face_collected(self, listener):
        chain = [FakeUnknown(face_id=178, face_name=''), FakePlain(text='hi')]
        result = listener._extract_faces(chain)
        assert '斜眼笑' in result


class TestNormalizeFaceComponents:
    def test_replaces_face_with_plain(self, listener):
        chain = [FakeFace(face_id=14, face_name='惊讶'), FakePlain(text='hello')]
        listener._normalize_face_components(chain)
        assert 'QQ表情:惊讶' in chain[0].text

    def test_quote_origin_recursive(self, listener):
        face = FakeFace(face_id=0, face_name='微笑')
        quote = FakeQuote(origin=[face])
        listener._normalize_face_components([quote])
        assert 'QQ表情:微笑' in quote.origin[0].text

    def test_none_safe(self, listener):
        listener._normalize_face_components(None)  # 不抛异常


class TestQuoteHasImage:
    def test_quote_with_image(self, listener):
        img = FakeImage()
        quote = FakeQuote(origin=[img, FakePlain(text='text')])
        assert listener._quote_has_image([quote]) is True

    def test_quote_without_image(self, listener):
        quote = FakeQuote(origin=[FakePlain(text='text')])
        assert listener._quote_has_image([quote]) is False

    def test_no_quote(self, listener):
        assert listener._quote_has_image([FakePlain(text='text')]) is False

    def test_none_chain(self, listener):
        assert listener._quote_has_image(None) is False


class TestHasImage:
    def test_direct_image(self, listener):
        assert listener._has_image([FakeImage()]) is True

    def test_image_in_quote(self, listener):
        quote = FakeQuote(origin=[FakeImage()])
        assert listener._has_image([quote]) is True

    def test_no_image(self, listener):
        assert listener._has_image([FakePlain(text='hello')]) is False


class TestCollectImages:
    def test_collects_indices(self, listener):
        chain = [FakePlain(text='x'), FakeImage(), FakePlain(text='y'), FakeImage()]
        result = listener._collect_images(chain)
        assert len(result) == 2
        assert result[0][0] == 1  # index of first Image
        assert result[1][0] == 3  # index of second Image

    def test_collects_all_images(self, listener):
        chain = [FakeImage() for _ in range(10)]
        result = listener._collect_images(chain)
        assert len(result) == 10

    def test_none_chain(self, listener):
        assert listener._collect_images(None) == []


class TestHasAt:
    def test_at_matches_bot_qq(self, listener):
        at = FakeAt(target='3228649756')
        assert listener._has_at([at]) is True

    def test_at_mismatch(self, listener):
        at = FakeAt(target='1111111111')
        assert listener._has_at([at]) is False

    def test_at_in_quote(self, listener):
        at = FakeAt(target='3228649756')
        quote = FakeQuote(origin=[at])
        assert listener._has_at([quote]) is True
