"""
Reading text off the screen with Windows' own built-in text recognition (Windows.Media.Ocr).

It runs on this PC: the picture never leaves it, it's instant, and it gives the exact characters (error codes,
serial numbers, file paths), which a description of a screenshot can get wrong. The text it finds goes to her only
so she can answer you, or onto your clipboard if you asked for that.

Uses the languages installed in Windows (Settings > Time & language > Language). English is always there.
"""
import asyncio

MAX_SIDE = 2600            # Windows OCR won't take bigger pictures than about this


def _prep(img):
    img = img.convert("RGBA")
    w, h = img.size
    k = min(1.0, MAX_SIDE / max(w, h))
    if max(w, h) < 900:                      # small crops: bigger letters read better
        k = min(2.5, MAX_SIDE / max(w, h))
    if k != 1.0:
        img = img.resize((max(1, round(w * k)), max(1, round(h * k))))
    return img


async def _recognize(img):
    from winrt.windows.media.ocr import OcrEngine
    from winrt.windows.graphics.imaging import SoftwareBitmap, BitmapPixelFormat, BitmapAlphaMode
    img = _prep(img)
    bmp = SoftwareBitmap.create_copy_from_buffer(img.tobytes("raw", "BGRA"), BitmapPixelFormat.BGRA8, img.width, img.height,
                                                 BitmapAlphaMode.PREMULTIPLIED)
    eng = OcrEngine.try_create_from_user_profile_languages()
    if eng is None:
        raise RuntimeError("Windows has no text-recognition language installed")
    res = await eng.recognize_async(bmp)
    return "\n".join(line.text for line in res.lines).strip()


def read(img):
    """All the text in a PIL image, line by line."""
    return asyncio.run(_recognize(img))
