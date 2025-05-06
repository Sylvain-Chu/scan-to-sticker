"""
Scanne le NETUM → extrait l’ID Ubiqod → compose une étiquette PNG prête à imprimer.
"""

# ------------------------- LIBRAIRIES ----------------------------------------
import sys, re, datetime, pathlib, logging, io
import serial, serial.tools.list_ports
import treepoem
from PIL import Image, ImageDraw, ImageFont

# ------------------------- CONFIG SÉRIE --------------------------------------
PORT        = None          # None = auto, ou "COM4" pour forcer
BAUDRATE    = 115200
TIMEOUT_S   = 0.1
END_BYTES   = b"\r"

# ------------------------- CONFIG ÉTIQUETTE ----------------------------------
PREFIX          = "UK"          # préfixe devant l'ID
LABEL_W, LABEL_H = 543, 248
MARGIN          = 16
CORNER_R        = 25
FRAME_DASH      = (10, 10)
LIGHT_GRAY      = 180

TEXT1 = "UBIQOD KEY"
TEXT2 = "P/N : SKPF000252"

FONT_BIG = ImageFont.truetype("arialbd.ttf", 30)  
FONT_MED = ImageFont.truetype("arial.ttf",   26)
FONT_BAR = ImageFont.truetype("arial.ttf",   24)

BAR_SCALE   = 3
BAR_HEIGHT  = 0.7
BAR_WIDTH   = 2.2
QUIET_ZONE  = 2

OUT_DIR  = pathlib.Path("barcodes")
LOG_LEVEL = logging.INFO

OUT_DIR.mkdir(exist_ok=True)
logging.basicConfig(level=LOG_LEVEL, format="%(message)s")

# ------------------------- OUTILS GRAPHIQUES ---------------------------------
def load_logo(path: pathlib.Path, width_px: int) -> Image.Image:
    """Charge un PNG, le redimensionne en conservant le ratio -> Pillow RGBA."""
    img = Image.open(path).convert("RGBA")
    if img.width != width_px:
        ratio = width_px / img.width
        img   = img.resize((width_px, int(img.height * ratio)), Image.LANCZOS)
    return img

def make_barcode(code: str) -> Image.Image:
    """Code 128 + texte lisible centré sous les barres (monochrome)."""
    symbol = treepoem.generate_barcode(
        "code128", code,
        options={
            "scale":     str(BAR_SCALE),
            "height":    str(BAR_HEIGHT),
            "width":     str(BAR_WIDTH),
            "quietzone": str(QUIET_ZONE),
        }
    ).convert("1")

    w_txt, h_txt = FONT_BAR.getbbox(code)[2:]
    canvas = Image.new("1", (symbol.width, symbol.height + h_txt + 8), 1)
    canvas.paste(symbol, (0, 0))
    ImageDraw.Draw(canvas).text(
        ((symbol.width - w_txt)//2, symbol.height + 4),
        code, font=FONT_BAR, fill=0
    )
    return canvas

def compose_label(uid: str) -> Image.Image:
    """Construit l'étiquette complète à partir de l'UID."""
    label = Image.new("RGB", (LABEL_W, LABEL_H), "white")
    draw  = ImageDraw.Draw(label)

    # chargement des textes fixes
    draw.text((MARGIN, MARGIN), TEXT1, font=FONT_BIG, fill=0)
    draw.text((MARGIN, MARGIN + 38), TEXT2, font=FONT_MED, fill=0)

    # chargement des logos PNG 
    taqt = load_logo("img/taqt.png", 190)
    weee = load_logo("img/WEEE.png", 70)
    ce   = load_logo("img/CE.png",   80)

    label.paste(taqt, (LABEL_W - taqt.width - MARGIN, MARGIN), taqt)

    gap = 4
    total_width  = weee.width + gap + ce.width
    x_start = LABEL_W - total_width - MARGIN
    y_logos = LABEL_H - max(weee.height, ce.height) - MARGIN

    label.paste(weee, (x_start, y_logos), weee)
    label.paste(ce,   (x_start + weee.width + gap, y_logos), ce)

    # ── code‑barres ─────────────────────────────────────────────────────
    full_code = f"{PREFIX}{uid}"
    barcode = make_barcode(full_code)
    label.paste(barcode, (MARGIN, LABEL_H - barcode.height - MARGIN))

    return label

# ------------------------- OUTILS SÉRIE --------------------------------------
def autodetect_port() -> str:
    ports = list(serial.tools.list_ports.comports())
    if PORT:
        return PORT
    if len(ports) == 1:
        return ports[0].device
    raise RuntimeError("Plusieurs ports USB‑COM ; fixez PORT dans le script.")

# ------------------------- BOUCLE PRINCIPALE ---------------------------------
def main() -> None:
    port = autodetect_port()
    logging.info(f"Port {port} @ {BAUDRATE} bauds – prêt (Ctrl‑C pour quitter)")
    try:
        with serial.Serial(port, BAUDRATE, timeout=TIMEOUT_S) as ser:
            buf = bytearray()
            while True:
                buf.extend(ser.read(ser.in_waiting or 1))
                if buf.endswith(END_BYTES):
                    line = bytes(buf).decode(errors="ignore").strip()
                    buf.clear()

                    m = re.search(r"/m/(\d{6,12})/", line)
                    if not m:
                        logging.debug(f"Ignoré : {line}")
                        continue

                    uid = m.group(1)
                    img = compose_label(uid)

                    ts   = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                    file = OUT_DIR / f"label_{PREFIX}{uid}_{ts}.png"
                    img.save(file, dpi=(300, 300))
                    logging.info(f"✔ {PREFIX}{uid} → {file.name}")
    except KeyboardInterrupt:
        logging.info("\nArrêt demandé.")
    except Exception as exc:
        logging.error(f"Erreur : {exc}")
        sys.exit(1)

if __name__ == "__main__":
    main()
