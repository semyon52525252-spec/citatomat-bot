import vk_api
from vk_api.longpoll import VkLongPoll, VkEventType
import requests
import os
import time
import random
import threading
import logging
from io import BytesIO
from collections import OrderedDict
from PIL import Image, ImageDraw, ImageFont, ImageOps

TOKEN = "vk1.a.VFLP5jl-ACDiZazpFHnfi7XvO3NpsUknFT3KOAa3wO_lI9QKgOWVHjxfWd8GCrOvpYomT9_5N1RclO3baxmlZQwJndWaO7udvC1V0ApPlY3hd3Fwir-7ajfUn61jTCtF5-KrUDDX31UAl9yomL_OU2_P8bbVAnvwqxpmHUFHkpGSkftHYD5G1-ChfHABnkeaVxbvG9RNbKyAk32Vcso-6Q"
BG_DIR = "/storage/emulated/0/Download/"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FONT_DIR = os.path.join(BASE_DIR, "fonts")
TEMP_DIR = os.path.join(BASE_DIR, "temp")
USER_FONT_DIR = os.path.join(BASE_DIR, "user_fonts")
try:
    os.makedirs(BG_DIR, exist_ok=True)
except Exception:
    BG_DIR = BASE_DIR
os.makedirs(FONT_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)
os.makedirs(USER_FONT_DIR, exist_ok=True)
MAX_MESSAGES = 6
MAX_TEXT_LEN = 300
CACHE_LIMIT = 500
SEND_RETRIES = 3
NET_TIMEOUT = 8
W, H = 800, 500
HEADER_H = 80
DIALOG_AV = 60
DIALOG_AV_GAP = 20
DIALOG_NAME_GAP = 14
DIALOG_BLOCK_GAP = 30
DIALOG_AREA_TOP = HEADER_H + 20
DIALOG_AREA_BOTTOM = H - 20
MONO_TEXT_TOP = HEADER_H + 25
MONO_FOOTER_H = 150
MONO_TEXT_BOTTOM = H - MONO_FOOTER_H - 10
MONO_TEXT_MAX_W = W - 80
AV_SIZE = 80
AV_X = 40
AV_Y = H - AV_SIZE - 40
NAME_X = AV_X + AV_SIZE + 20
NAME_Y = AV_Y + AV_SIZE // 2
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S", handlers=[logging.StreamHandler()])
log = logging.getLogger("vk_quote_bot")
try:
    vk = vk_api.VkApi(token=TOKEN)
    api = vk.get_api()
    uploader = vk_api.upload.VkUpload(api)
except Exception as e:
    log.exception(f"Ошибка инициализации VK API: {e}")
    raise SystemExit(1)
user_cache = OrderedDict()
avatar_cache = OrderedDict()
cache_lock = threading.Lock()

def _lru_put(cache, key, value):
    with cache_lock:
        if key in cache:
            cache.move_to_end(key)
        cache[key] = value
        while len(cache) > CACHE_LIMIT:
            cache.popitem(last=False)

def _lru_get(cache, key):
    with cache_lock:
        if key in cache:
            cache.move_to_end(key)
            return cache[key]
    return None

_FONT_CACHE = {}
_FONT_LOCK = threading.Lock()
DEJAVU_URLS = [
    "https://cdn.jsdelivr.net/gh/dejavu-fonts/dejavu-fonts@version_2_37/ttf/DejaVuSans.ttf",
    "https://raw.githubusercontent.com/dejavu-fonts/dejavu-fonts/version_2_37/ttf/DejaVuSans.ttf",
    "https://github.com/dejavu-fonts/dejavu-fonts/raw/version_2_37/ttf/DejaVuSans.ttf",
]
DEJAVU_PATH = os.path.join(FONT_DIR, "DejaVuSans.ttf")
DEJAVU_BOLD_URL = "https://cdn.jsdelivr.net/gh/dejavu-fonts/dejavu-fonts@version_2_37/ttf/DejaVuSans-Bold.ttf"
DEJAVU_BOLD_PATH = os.path.join(FONT_DIR, "DejaVuSans-Bold.ttf")
SYSTEM_FONTS = ["/system/fonts/Roboto-Regular.ttf", "/system/fonts/DroidSans.ttf", "/system/fonts/RobotoCondensed-Regular.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf", "/Library/Fonts/Arial.ttf", "C:\\Windows\\Fonts\\arial.ttf", "arial.ttf"]
BOLD_FONTS = ["/system/fonts/Roboto-Bold.ttf", "/system/fonts/RobotoCondensed-Bold.ttf", "/system/fonts/DroidSans-Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf", "/Library/Fonts/Arial Bold.ttf", "C:\\Windows\\Fonts\\arialbd.ttf"]

def _ensure_fallback_font():
    if not os.path.exists(DEJAVU_PATH) or os.path.getsize(DEJAVU_PATH) < 100000:
        for url in DEJAVU_URLS:
            try:
                log.info(f"Скачиваю fallback-шрифт: {url}")
                r = requests.get(url, timeout=30)
                r.raise_for_status()
                if len(r.content) < 100000:
                    raise RuntimeError("слишком маленький файл")
                with open(DEJAVU_PATH, "wb") as f:
                    f.write(r.content)
                log.info("Fallback-шрифт сохранён.")
                break
            except Exception as e:
                log.warning(f"Не удалось скачать с {url}: {e}")
    if not os.path.exists(DEJAVU_BOLD_PATH) or os.path.getsize(DEJAVU_BOLD_PATH) < 100000:
        try:
            log.info("Скачиваю fallback-жирный шрифт...")
            r = requests.get(DEJAVU_BOLD_URL, timeout=30)
            r.raise_for_status()
            if len(r.content) < 100000:
                raise RuntimeError("слишком маленький файл")
            with open(DEJAVU_BOLD_PATH, "wb") as f:
                f.write(r.content)
            log.info("Fallback-жирный шрифт сохранён.")
        except Exception as e:
            log.warning(f"Не удалось скачать жирный шрифт: {e}")
    if not os.path.exists(DEJAVU_PATH):
        log.warning("Fallback-шрифт не скачан, будет использован системный.")

def _default_font_path():
    for p in SYSTEM_FONTS:
        if os.path.exists(p):
            return p
    if os.path.exists(DEJAVU_PATH):
        return DEJAVU_PATH
    return None

def get_font(size, font_path=None, bold=False):
    size = max(8, int(size))
    key = (font_path or "", size, bool(bold))
    with _FONT_LOCK:
        if key in _FONT_CACHE:
            return _FONT_CACHE[key]
    font = None
    if bold:
        for p in BOLD_FONTS:
            try:
                if os.path.exists(p):
                    font = ImageFont.truetype(p, size)
                    break
            except Exception:
                continue
        if font is None and os.path.exists(DEJAVU_BOLD_PATH):
            try:
                font = ImageFont.truetype(DEJAVU_BOLD_PATH, size)
            except Exception:
                font = None
    if font is None and font_path and os.path.exists(font_path):
        try:
            font = ImageFont.truetype(font_path, size)
        except Exception:
            font = None
    if font is None:
        for p in SYSTEM_FONTS:
            try:
                if os.path.exists(p):
                    font = ImageFont.truetype(p, size)
                    break
            except Exception:
                continue
    if font is None:
        try:
            if os.path.exists(DEJAVU_PATH):
                font = ImageFont.truetype(DEJAVU_PATH, size)
        except Exception:
            font = None
    if font is None:
        try:
            font = ImageFont.load_default()
        except Exception:
            font = ImageFont.load_default()
    with _FONT_LOCK:
        if len(_FONT_CACHE) > 128:
            _FONT_CACHE.clear()
        _FONT_CACHE[key] = font
    return font

_session = requests.Session()
_session.headers.update({"User-Agent": "VKQuoteBot/1.0"})

def fetch_bytes(url, timeout=NET_TIMEOUT):
    if not url:
        return None
    try:
        r = _session.get(url, timeout=timeout)
        if r.status_code == 200 and r.content:
            return r.content
    except Exception as e:
        log.warning(f"fetch_bytes fail: {e}")
    return None

def open_image_from_bytes(data):
    if not data:
        return None
    try:
        img = Image.open(BytesIO(data))
        img = ImageOps.exif_transpose(img)
        if img.mode != "RGB":
            img = img.convert("RGB")
        return img
    except Exception as e:
        log.warning(f"open_image fail: {e}")
        return None

def _rand_id():
    return random.randint(1, 2**31 - 1)

def send_photo(peer_id, img):
    if img is None:
        return
    for attempt in range(1, SEND_RETRIES + 1):
        tmp_path = os.path.join(TEMP_DIR, f"quote_{_rand_id()}.png")
        try:
            img.save(tmp_path, format="PNG", optimize=True)
            uploaded = uploader.photo_messages(tmp_path, peer_id=peer_id)
            if not uploaded:
                raise RuntimeError("upload empty")
            att = f'photo{uploaded[0]["owner_id"]}_{uploaded[0]["id"]}'
            api.messages.send(peer_id=peer_id, message="", attachment=att, keyboard='{"buttons":[],"one_time":true}', random_id=_rand_id())
            log.info(f"📤 Фото отправлено (peer {peer_id})")
            return
        except Exception as e:
            log.warning(f"send_photo attempt {attempt} fail: {e}")
            time.sleep(1.0 * attempt)
        finally:
            try:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except Exception:
                pass
    log.error("send_photo: все попытки провалились")

def send_text(peer_id, text):
    for attempt in range(1, SEND_RETRIES + 1):
        try:
            api.messages.send(peer_id=peer_id, message=text, keyboard='{"buttons":[],"one_time":true}', random_id=_rand_id())
            return
        except Exception as e:
            log.warning(f"send_text attempt {attempt} fail: {e}")
            time.sleep(0.5 * attempt)

def get_user_info(uid):
    if not uid:
        return "Пользователь", None
    cached = _lru_get(user_cache, uid)
    if cached is not None:
        return cached
    try:
        u = api.users.get(user_ids=uid, fields="photo_100")[0]
        name = f"{u.get('first_name','')} {u.get('last_name','')}".strip() or "Пользователь"
        if len(name) > 25:
            name = name[:25] + "..."
        res = (name, u.get("photo_100"))
    except Exception as e:
        log.warning(f"get_user_info fail uid={uid}: {e}")
        res = ("Пользователь", None)
    _lru_put(user_cache, uid, res)
    return res

def get_avatar_image(url):
    if not url:
        return None
    cached = _lru_get(avatar_cache, url)
    if cached is not None:
        return cached
    data = fetch_bytes(url)
    img = open_image_from_bytes(data)
    if img is not None:
        _lru_put(avatar_cache, url, img)
    return img

def get_photo_url(attachments):
    if not isinstance(attachments, list):
        return None
    for att in attachments:
        if not isinstance(att, dict) or att.get("type") != "photo":
            continue
        photo = att.get("photo") or {}
        sizes = photo.get("sizes")
        if isinstance(sizes, list) and sizes:
            for s in reversed(sizes):
                if isinstance(s, dict) and s.get("url"):
                    return s["url"]
    return None

def clear_old_temp():
    for d in (BG_DIR, TEMP_DIR):
        if not os.path.exists(d):
            continue
        try:
            for f in os.listdir(d):
                if f.startswith("quote_") or f.startswith("custom_bg_"):
                    try:
                        os.remove(os.path.join(d, f))
                    except Exception:
                        pass
        except Exception as e:
            log.warning(f"clear_old_temp({d}): {e}")

def _load_background(attach_bg_url, custom_bg_path):
    bg = None
    if attach_bg_url:
        bg = open_image_from_bytes(fetch_bytes(attach_bg_url))
    if bg is None and custom_bg_path and os.path.exists(custom_bg_path):
        try:
            with open(custom_bg_path, "rb") as f:
                bg = open_image_from_bytes(f.read())
        except Exception as e:
            log.warning(f"custom bg read fail: {e}")
    if bg is not None:
        try:
            bg = bg.resize((W, H), Image.LANCZOS)
        except Exception:
            bg = bg.resize((W, H))
    else:
        bg = Image.new("RGB", (W, H), color=(10, 10, 10))
    return bg

def _wrap_text(draw, text, font, max_width):
    lines = []
    cur = ""
    for w in text.split():
        test = (cur + " " + w).strip()
        try:
            tw = draw.textlength(test, font=font)
        except Exception:
            tw = len(test) * (font.size if hasattr(font, "size") else 10)
        if tw <= max_width:
            cur = test
        else:
            if cur:
                lines.append(cur)
            try:
                wlen = draw.textlength(w, font=font)
            except Exception:
                wlen = len(w) * 10
            if wlen > max_width:
                piece = ""
                for ch in w:
                    try:
                        plen = draw.textlength(piece + ch, font=font)
                    except Exception:
                        plen = (len(piece) + 1) * 10
                    if plen <= max_width:
                        piece += ch
                    else:
                        if piece:
                            lines.append(piece)
                        piece = ch
                cur = piece
            else:
                cur = w
    if cur:
        lines.append(cur)
    return lines or [""]

def _circle_avatar(img, size):
    try:
        img = img.resize((size, size), Image.LANCZOS)
    except Exception:
        img = img.resize((size, size))
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size, size), fill=255)
    out = Image.new("RGB", (size, size), (0, 0, 0))
    out.paste(img, (0, 0), mask)
    return out, mask

def _block_text_height(block):
    f = block["font"]
    fsize = f.size if hasattr(f, "size") else 20
    return len(block["lines"]) * (fsize + 5)

def create_quote_image(peer_id, messages, custom_bg_path=None, attach_bg=None, font_path=None):
    t_start = time.time()
    try:
        log.info("🖼 Рисую картинку...")
        bg = _load_background(attach_bg, custom_bg_path)
        draw = ImageDraw.Draw(bg)
        messages = (messages or [])[:MAX_MESSAGES]
        unique_senders = {m.get("user_id") for m in messages if m.get("user_id")}
        if len(unique_senders) > 1:
            title = "Диалоги великих людей"
        elif len(messages) > 1:
            title = "Монологи великих людей"
        else:
            title = "Цитаты великих людей"
        draw.text((W // 2, 40), title, fill=(200, 200, 200), font=get_font(28, font_path), anchor="mm")
        if not messages:
            send_photo(peer_id, bg)
            log.info(f"✅ Готово за {time.time()-t_start:.2f} сек")
            return
        is_dialog = len(unique_senders) > 1
        if is_dialog:
            _draw_dialog(draw, bg, messages, font_path)
        else:
            _draw_monologue(draw, bg, messages, font_path)
        send_photo(peer_id, bg)
        log.info(f"✅ Готово за {time.time()-t_start:.2f} сек")
    except Exception as e:
        log.exception(f"create_quote_image fatal: {e}")
        try:
            send_text(peer_id, "⚠️ Не удалось создать картинку.")
        except Exception:
            pass

def _draw_dialog(draw, bg, messages, font_path=None):
    area_top = DIALOG_AREA_TOP
    area_bottom = DIALOG_AREA_BOTTOM
    inner_w = W - 40
    font_size = 36
    per_block = []
    while font_size >= 12:
        font = get_font(font_size, font_path)
        fsize = font.size if hasattr(font, "size") else font_size
        per_block = []
        total_h = 0
        for m in messages:
            txt = (m.get("text") or "").strip() or "<без текста>"
            if len(txt) > MAX_TEXT_LEN:
                txt = txt[:MAX_TEXT_LEN].rstrip() + "..."
            lines = _wrap_text(draw, txt, font, inner_w - DIALOG_AV - DIALOG_NAME_GAP)
            text_h = len(lines) * (fsize + 4)
            av_h = max(DIALOG_AV, text_h)
            block_h = av_h + DIALOG_NAME_GAP + DIALOG_BLOCK_GAP
            per_block.append({"font": font, "fsize": fsize, "lines": lines, "av_h": av_h, "block_h": block_h})
            total_h += block_h
        if total_h <= (area_bottom - area_top):
            break
        font_size -= 2
    cur_h = 0
    keep = 0
    for b in per_block:
        if cur_h + b["block_h"] > (area_bottom - area_top):
            break
        cur_h += b["block_h"]
        keep += 1
    blocks_to_draw = per_block[:max(keep, 1)]
    msg_pairs = messages[:len(blocks_to_draw)]
    total_h = sum(b["block_h"] for b in blocks_to_draw)
    y = area_top + max(0, (area_bottom - area_top - total_h) // 2)
    for block, msg in zip(blocks_to_draw, msg_pairs):
        font = block["font"]
        fsize = block["fsize"]
        uid = msg.get("user_id") or 0
        name, photo_url = get_user_info(uid) if uid else ("Пользователь", None)
        av_img = get_avatar_image(photo_url) if photo_url else None
        av_x = 40
        av_y = y
        text_x = av_x + DIALOG_AV + DIALOG_NAME_GAP
        if av_img is not None:
            try:
                av_small, mask = _circle_avatar(av_img, DIALOG_AV)
                bg.paste(av_small, (av_x, av_y), mask)
            except Exception as e:
                log.warning(f"avatar paste fail: {e}")
        ty = av_y
        for line in block["lines"]:
            draw.text((text_x, ty), line, fill=(255, 255, 255), font=font, anchor="la")
            ty += fsize + 4
        draw.text((av_x + DIALOG_AV // 2, av_y + DIALOG_AV + 6), name,
                  fill=(220, 220, 220), font=get_font(14, font_path, bold=True), anchor="ma")
        y += block["block_h"]

def _draw_monologue(draw, bg, messages, font_path=None):
    available_h = MONO_TEXT_BOTTOM - MONO_TEXT_TOP
    font_size = 52
    text_blocks = []
    while font_size >= 14:
        font = get_font(font_size, font_path)
        text_blocks = []
        total_h = 0
        for msg in messages:
            txt = (msg.get("text") or "").strip()
            if not txt:
                continue
            if len(txt) > MAX_TEXT_LEN:
                txt = txt[:MAX_TEXT_LEN].rstrip() + "..."
            lines = _wrap_text(draw, txt, font, MONO_TEXT_MAX_W)
            block = {"lines": lines, "font": font, "user_id": msg.get("user_id")}
            text_blocks.append(block)
            fsize = font.size if hasattr(font, "size") else font_size
            total_h += len(lines) * (fsize + 5) + 8
        if total_h <= available_h:
            break
        font_size -= 2
    if not text_blocks:
        return
    total_h = sum(_block_text_height(b) + 8 for b in text_blocks)
    current_y = MONO_TEXT_TOP + max(0, (available_h - total_h) // 2)
    for block in text_blocks:
        font = block["font"]
        fsize = font.size if hasattr(font, "size") else 20
        for line in block["lines"]:
            if current_y + fsize > MONO_TEXT_BOTTOM:
                break
            draw.text((W // 2, current_y), line, fill=(255, 255, 255), font=font, anchor="mm")
            current_y += fsize + 5
        current_y += 8
    last_uid = None
    for m in reversed(messages):
        if m.get("user_id"):
            last_uid = m["user_id"]
            break
    if last_uid:
        name, photo_url = get_user_info(last_uid)
        av_img = get_avatar_image(photo_url) if photo_url else None
        if av_img is not None:
            try:
                av_small, mask = _circle_avatar(av_img, AV_SIZE)
                bg.paste(av_small, (AV_X, AV_Y), mask)
            except Exception as e:
                log.warning(f"avatar paste fail: {e}")
        draw.text((NAME_X, NAME_Y), name, fill=(200, 200, 200), font=get_font(28, font_path), anchor="lm")

def _list_user_fonts():
    fonts = []
    if not os.path.isdir(FONT_DIR):
        return fonts
    for f in sorted(os.listdir(FONT_DIR)):
        if f.lower().endswith((".ttf", ".otf")):
            path = os.path.join(FONT_DIR, f)
            display = os.path.splitext(f)[0]
            fonts.append((path, display))
    if os.path.exists(DEJAVU_PATH):
        if not any(os.path.abspath(p) == os.path.abspath(DEJAVU_PATH) for p, _ in fonts):
            fonts.append((DEJAVU_PATH, "DejaVuSans"))
    default = _default_font_path()
    if default and not any(os.path.abspath(p) == os.path.abspath(default) for p, _ in fonts):
        fonts.insert(0, (default, "Стандартный"))
    return fonts

def _user_font_file(user_id):
    return os.path.join(USER_FONT_DIR, f"font_{user_id}.txt")

def save_user_font(user_id, font_index):
    fonts = _list_user_fonts()
    idx = font_index - 1
    if idx < 0 or idx >= len(fonts):
        return None
    path, name = fonts[idx]
    try:
        with open(_user_font_file(user_id), "w", encoding="utf-8") as f:
            f.write(path)
        return name
    except Exception as e:
        log.warning(f"save_user_font fail: {e}")
        return None

def load_user_font(user_id):
    path = _user_font_file(user_id)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            p = f.read().strip()
        if p and os.path.exists(p):
            return p
    except Exception:
        pass
    return None

def clear_user_font(user_id):
    path = _user_font_file(user_id)
    if os.path.exists(path):
        try:
            os.remove(path)
            return True
        except Exception:
            pass
    return False

def render_font_catalog():
    fonts = _list_user_fonts()
    if not fonts:
        img = Image.new("RGB", (W, 200), (10, 10, 10))
        d = ImageDraw.Draw(img)
        d.text((W // 2, 100), "Нет доступных шрифтов", fill=(200, 200, 200), font=get_font(28), anchor="mm")
        return img
    line_h = 95
    header_h = 70
    footer_h = 30
    H2 = header_h + line_h * len(fonts) + footer_h
    img = Image.new("RGB", (W, H2), (15, 15, 15))
    draw = ImageDraw.Draw(img)
    draw.text((W // 2, 35), "Каталог шрифтов", fill=(200, 200, 200), font=get_font(28), anchor="mm")
    y = header_h
    for i, (path, name) in enumerate(fonts, 1):
        try:
            fname = ImageFont.truetype(path, 32)
        except Exception:
            fname = get_font(32)
        label = f"{i}. {name}"
        draw.text((40, y + 10), label, fill=(255, 255, 255), font=fname, anchor="la")
        try:
            fprev = ImageFont.truetype(path, 20)
        except Exception:
            fprev = get_font(20)
        draw.text((40, y + 55), "Аа Бб Вв Гг — Умный в гору пойдёт, умный гору обойдёт",
                  fill=(170, 170, 170), font=fprev, anchor="la")
        if i < len(fonts):
            draw.line([(40, y + line_h - 5), (W - 40, y + line_h - 5)], fill=(50, 50, 50), width=1)
        y += line_h
    draw.text((W // 2, H2 - 15), "Выбор: шрифт N  |  Сброс: -шрифт",
              fill=(150, 150, 150), font=get_font(16), anchor="mm")
    return img

def _fmt_text_preview(text, limit=60):
    text = (text or "").replace("\n", " ").strip()
    if len(text) > limit:
        text = text[:limit] + "..."
    return text or "<без текста>"

def log_incoming(full_msg, fwd_messages, reply_message):
    from_id = full_msg.get("from_id") or 0
    name, _ = get_user_info(from_id) if from_id else ("Пользователь", None)
    text = full_msg.get("text") or ""
    log.info(f"💬 {name} (id {from_id}): {_fmt_text_preview(text)}")
    if fwd_messages:
        log.info(f"↪ Пересылка ({len(fwd_messages)} сообщений):")
        for i, fwd in enumerate(fwd_messages[:MAX_MESSAGES], 1):
            uid = fwd.get("from_id") or fwd.get("user_id") or 0
            fname, _ = get_user_info(uid) if uid else ("Пользователь", None)
            ftxt = _fmt_text_preview(fwd.get("text"))
            log.info(f"   {i}. {fname} (id {uid}): {ftxt}")
    elif reply_message:
        uid = reply_message.get("from_id") or 0
        rname, _ = get_user_info(uid) if uid else ("Пользователь", None)
        rtxt = _fmt_text_preview(reply_message.get("text"))
        log.info(f"↩ Ответ на {rname} (id {uid}): {rtxt}")

def handle_event(ev):
    try:
        if ev.type != VkEventType.MESSAGE_NEW:
            return
        if not getattr(ev, "to_me", False):
            return
        if getattr(ev, "out", 0) == 1:
            return
        peer_id = ev.peer_id
        user_id = ev.user_id
        msg_id = ev.message_id
        try:
            res = vk.method("messages.getById", {"message_ids": msg_id})
        except Exception as e:
            log.warning(f"getById fail: {e}")
            return
        items = (res or {}).get("items") or []
        if not items:
            return
        full_msg = items[0]
        text = (full_msg.get("text") or "").strip()
        attachments = full_msg.get("attachments") or []
        fwd_messages = full_msg.get("fwd_messages") or []
        reply_message = full_msg.get("reply_message")
        log_incoming(full_msg, fwd_messages, reply_message)
        low = text.lower()
        if low == "шрифты":
            log.info("🎨 Отправляю каталог шрифтов...")
            send_photo(peer_id, render_font_catalog())
            return
        if low.startswith("шрифт "):
            arg = low[len("шрифт "):].strip()
            if not arg.isdigit():
                send_text(peer_id, "❌ Формат: «шрифт N». Список — командой «шрифты».")
                return
            n = int(arg)
            name = save_user_font(user_id, n)
            if name:
                send_text(peer_id, f"✅ Шрифт установлен: {name}")
            else:
                send_text(peer_id, "❌ Нет такого номера. Список — командой «шрифты».")
            return
        if low == "-шрифт":
            if clear_user_font(user_id):
                send_text(peer_id, "✅ Шрифт сброшен на стандартный.")
            else:
                send_text(peer_id, "У тебя и так стандартный шрифт.")
            return
        custom_bg_path = os.path.join(BG_DIR, f"custom_bg_{user_id}.jpg")
        attach_bg = get_photo_url(attachments)
        if low == "+фон":
            if not attach_bg:
                send_text(peer_id, "❌ Прикрепи картинку к сообщению «+фон».")
                return
            log.info("⚙️ Сохраняю новый фон...")
            data = fetch_bytes(attach_bg, timeout=15)
            if not data:
                send_text(peer_id, "❌ Не удалось скачать фон.")
                return
            try:
                img = open_image_from_bytes(data)
                if img is None:
                    raise RuntimeError("bad image")
                img.save(custom_bg_path, format="JPEG", quality=90)
                send_text(peer_id, "✅ Фон сохранён!")
            except Exception as e:
                log.warning(f"save custom bg fail: {e}")
                send_text(peer_id, "❌ Ошибка при сохранении фона.")
            return
        if low == "-фон":
            if os.path.exists(custom_bg_path):
                try:
                    os.remove(custom_bg_path)
                    send_text(peer_id, "✅ Фон сброшен.")
                except Exception:
                    send_text(peer_id, "❌ Не удалось сбросить фон.")
            else:
                send_text(peer_id, "У тебя стандартный фон.")
            return
        user_font_path = load_user_font(user_id)
        messages_data = []
        bg_url = None
        if fwd_messages:
            for fwd in fwd_messages[:MAX_MESSAGES]:
                uid = fwd.get("from_id") or fwd.get("user_id") or 0
                name, photo = get_user_info(uid) if uid else ("Пользователь", None)
                fwd_bg = get_photo_url(fwd.get("attachments") or [])
                if fwd_bg and not bg_url:
                    bg_url = fwd_bg
                messages_data.append({"user_id": uid, "name": name, "photo": photo, "text": fwd.get("text") or ""})
        elif reply_message:
            uid = reply_message.get("from_id") or 0
            name, photo = get_user_info(uid) if uid else ("Пользователь", None)
            reply_bg = get_photo_url(reply_message.get("attachments") or [])
            if reply_bg:
                bg_url = reply_bg
            messages_data.append({"user_id": uid, "name": name, "photo": photo, "text": reply_message.get("text") or ""})
        elif text or attachments:
            uid = full_msg.get("from_id") or 0
            name, photo = get_user_info(uid) if uid else ("Пользователь", None)
            if attach_bg:
                bg_url = attach_bg
            messages_data.append({"user_id": uid, "name": name, "photo": photo, "text": text})
        if messages_data or bg_url:
            create_quote_image(peer_id, messages_data, custom_bg_path, bg_url, user_font_path)
    except Exception as e:
        log.exception(f"handle_event fatal: {e}")

def run_longpoll():
    while True:
        try:
            log.info("Запуск LongPoll...")
            lp = VkLongPoll(vk, mode=2)
            for ev in lp.listen():
                try:
                    handle_event(ev)
                except Exception as e:
                    log.exception(f"handle_event fail: {e}")
        except KeyboardInterrupt:
            log.info("Остановлено пользователем.")
            break
        except Exception as e:
            log.error(f"LongPoll упал: {e}. Перезапуск через 5 сек...")
            time.sleep(5)

if __name__ == "__main__":
    try:
        log.info("=== ГЕНЕРАТОР ЦИТАТ ЗАПУЩЕН ===")
        clear_old_temp()
        _ensure_fallback_font()
        run_longpoll()
    except KeyboardInterrupt:
        log.info("Выход.")
    except Exception as e:
        log.exception(f"Фатальная ошибка: {e}")