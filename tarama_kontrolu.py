"""Web arayuzu ile tarama worker'i arasindaki hafif durum/istek koprusu."""

from __future__ import annotations

from datetime import datetime
import json
import os
from pathlib import Path


KOK = Path(__file__).resolve().parent
DURUM_DOSYASI = KOK / "worker_durumu.json"
MANUEL_ISTEK_DOSYASI = KOK / "manuel_tarama_istegi.json"


def tarama_durumu_oku(dosya: Path | None = None) -> dict[str, object]:
    yol = dosya or DURUM_DOSYASI
    try:
        veri = json.loads(yol.read_text(encoding="utf-8"))
        return veri if isinstance(veri, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def manuel_tarama_istegi_var(dosya: Path | None = None) -> bool:
    return (dosya or MANUEL_ISTEK_DOSYASI).is_file()


def manuel_tarama_iste(*, dosya: Path | None = None) -> bool:
    """Ayni anda yalnizca bir bekleyen tam tarama istegi olusturur."""
    yol = dosya or MANUEL_ISTEK_DOSYASI
    yol.parent.mkdir(parents=True, exist_ok=True)
    icerik = json.dumps(
        {
            "istenme_zamani": datetime.now().astimezone().isoformat(timespec="seconds"),
            "tur": "tam_tarama",
        },
        ensure_ascii=False,
        indent=2,
    ).encode("utf-8")
    try:
        tanimlayici = os.open(yol, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
    except FileExistsError:
        return False
    try:
        os.write(tanimlayici, icerik)
    finally:
        os.close(tanimlayici)
    return True


def manuel_tarama_istegini_al(dosya: Path | None = None) -> dict[str, object] | None:
    """Worker tarafindan bekleyen istegi bir kez tuketir."""
    yol = dosya or MANUEL_ISTEK_DOSYASI
    try:
        veri = json.loads(yol.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(veri, dict):
        return None
    try:
        yol.unlink()
    except FileNotFoundError:
        return None
    return veri
