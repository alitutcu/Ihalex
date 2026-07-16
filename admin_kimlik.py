"""Ihalex yonetim alani icin yerel ve ortam degiskenli kimlik dogrulama."""

from __future__ import annotations

import hashlib
import hmac
import base64
import json
import os
from pathlib import Path
import secrets
from datetime import datetime


KOK = Path(__file__).resolve().parent
ADMIN_DOSYASI = KOK / ".admin_kimlik"
PBKDF2_TUR_SAYISI = 390_000
ADMIN_OTURUM_SANIYESI = 3 * 60 * 60


class AdminKimlikHatasi(ValueError):
    pass


def admin_oturumu_gecerli(
    bitis: object,
    *,
    simdi: datetime | None = None,
) -> bool:
    try:
        bitis_zamani = datetime.fromisoformat(str(bitis or ""))
    except ValueError:
        return False
    return (simdi or datetime.now()) < bitis_zamani


def _oturum_anahtari(dosya: Path | None = None) -> bytes | None:
    ortam_parolasi = os.getenv("IHALEX_ADMIN_PASSWORD", "")
    if ortam_parolasi:
        return hashlib.sha256(
            ("ihalex-admin-oturum:" + ortam_parolasi).encode("utf-8")
        ).digest()
    veri = _yerel_kimlik_oku(dosya)
    try:
        parola_ozeti = bytes.fromhex(str(veri["parola_ozeti"]))
    except (KeyError, TypeError, ValueError):
        return None
    return hashlib.sha256(b"ihalex-admin-oturum:" + parola_ozeti).digest()


def _b64_yaz(veri: bytes) -> str:
    return base64.urlsafe_b64encode(veri).decode("ascii").rstrip("=")


def _b64_oku(metin: str) -> bytes:
    return base64.urlsafe_b64decode(metin + "=" * (-len(metin) % 4))


def admin_oturum_tokeni_olustur(
    kullanici_adi: str,
    *,
    simdi: datetime | None = None,
    sure_saniye: int = ADMIN_OTURUM_SANIYESI,
    dosya: Path | None = None,
) -> tuple[str, datetime]:
    anahtar = _oturum_anahtari(dosya)
    if anahtar is None:
        raise AdminKimlikHatasi("Yönetici oturum anahtarı oluşturulamadı")
    simdi = simdi or datetime.now()
    bitis = datetime.fromtimestamp(simdi.timestamp() + int(sure_saniye))
    veri = {
        "surum": 1,
        "kullanici_adi": str(kullanici_adi),
        "baslangic": int(simdi.timestamp()),
        "bitis": int(bitis.timestamp()),
        "nonce": secrets.token_hex(12),
    }
    govde = _b64_yaz(
        json.dumps(veri, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    )
    imza = _b64_yaz(hmac.new(anahtar, govde.encode("ascii"), hashlib.sha256).digest())
    return f"{govde}.{imza}", bitis


def admin_oturum_tokenini_dogrula(
    token: object,
    *,
    simdi: datetime | None = None,
    dosya: Path | None = None,
) -> dict[str, object] | None:
    anahtar = _oturum_anahtari(dosya)
    if anahtar is None:
        return None
    try:
        govde, gelen_imza = str(token or "").split(".", 1)
        beklenen = _b64_yaz(
            hmac.new(anahtar, govde.encode("ascii"), hashlib.sha256).digest()
        )
        if not hmac.compare_digest(gelen_imza, beklenen):
            return None
        veri = json.loads(_b64_oku(govde).decode("utf-8"))
        simdi_damgasi = int((simdi or datetime.now()).timestamp())
        if int(veri["baslangic"]) > simdi_damgasi + 60:
            return None
        if int(veri["bitis"]) <= simdi_damgasi:
            return None
        beklenen_kullanici = os.getenv("IHALEX_ADMIN_USERNAME", "admin")
        if not os.getenv("IHALEX_ADMIN_PASSWORD", ""):
            beklenen_kullanici = str(_yerel_kimlik_oku(dosya).get("kullanici_adi") or "")
        if not hmac.compare_digest(str(veri["kullanici_adi"]), beklenen_kullanici):
            return None
        return {
            **veri,
            "bitis_zamani": datetime.fromtimestamp(int(veri["bitis"])),
        }
    except (ValueError, TypeError, KeyError, json.JSONDecodeError, UnicodeDecodeError):
        return None


def _yerel_kimlik_oku(dosya: Path | None = None) -> dict[str, object]:
    yol = dosya or ADMIN_DOSYASI
    try:
        veri = json.loads(yol.read_text(encoding="utf-8"))
        return veri if isinstance(veri, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def admin_kurulumu_gerekli(dosya: Path | None = None) -> bool:
    if os.getenv("IHALEX_ADMIN_PASSWORD", ""):
        return False
    return not bool(_yerel_kimlik_oku(dosya))


def yerel_admin_olustur(
    kullanici_adi: str,
    parola: str,
    *,
    dosya: Path | None = None,
) -> None:
    yol = dosya or ADMIN_DOSYASI
    kullanici_adi = kullanici_adi.strip()
    if not 3 <= len(kullanici_adi) <= 64:
        raise AdminKimlikHatasi("Kullanıcı adı 3–64 karakter olmalıdır.")
    if len(parola) < 10:
        raise AdminKimlikHatasi("Parola en az 10 karakter olmalıdır.")
    if parola.casefold() in {"1234567890", "password123", "admin12345"}:
        raise AdminKimlikHatasi("Daha güçlü bir parola seçin.")

    tuz = secrets.token_bytes(32)
    ozet = hashlib.pbkdf2_hmac(
        "sha256", parola.encode("utf-8"), tuz, PBKDF2_TUR_SAYISI
    )
    veri = {
        "surum": 1,
        "kullanici_adi": kullanici_adi,
        "tuz": tuz.hex(),
        "parola_ozeti": ozet.hex(),
        "tur_sayisi": PBKDF2_TUR_SAYISI,
    }
    gecici = yol.with_suffix(".tmp")
    gecici.write_text(json.dumps(veri, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        gecici.chmod(0o600)
    except OSError:
        pass
    gecici.replace(yol)


def admin_kimligini_dogrula(
    kullanici_adi: str,
    parola: str,
    *,
    dosya: Path | None = None,
) -> bool:
    ortam_parolasi = os.getenv("IHALEX_ADMIN_PASSWORD", "")
    if ortam_parolasi:
        ortam_kullanicisi = os.getenv("IHALEX_ADMIN_USERNAME", "admin")
        return hmac.compare_digest(kullanici_adi, ortam_kullanicisi) and hmac.compare_digest(
            parola, ortam_parolasi
        )

    veri = _yerel_kimlik_oku(dosya)
    try:
        beklenen_kullanici = str(veri["kullanici_adi"])
        tuz = bytes.fromhex(str(veri["tuz"]))
        beklenen_ozet = bytes.fromhex(str(veri["parola_ozeti"]))
        tur_sayisi = int(veri.get("tur_sayisi") or PBKDF2_TUR_SAYISI)
    except (KeyError, TypeError, ValueError):
        return False
    gelen_ozet = hashlib.pbkdf2_hmac(
        "sha256", parola.encode("utf-8"), tuz, tur_sayisi
    )
    return hmac.compare_digest(kullanici_adi, beklenen_kullanici) and hmac.compare_digest(
        gelen_ozet, beklenen_ozet
    )
