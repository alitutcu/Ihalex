"""Telegram kimliğini Windows kullanıcı hesabına bağlı şifreli biçimde saklar."""

from __future__ import annotations

import base64
import ctypes
import json
import os
from ctypes import wintypes
from pathlib import Path


KIMLIK_DOSYASI = Path(
    os.getenv("IHALEX_TELEGRAM_KIMLIK_DOSYASI")
    or Path(__file__).resolve().with_name(".telegram_kimlik")
)
CRYPTPROTECT_UI_FORBIDDEN = 0x01


class _DataBlob(ctypes.Structure):
    _fields_ = [
        ("cbData", wintypes.DWORD),
        ("pbData", ctypes.POINTER(ctypes.c_byte)),
    ]


if os.name == "nt":
    _crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
    _kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _crypt32.CryptProtectData.argtypes = [
        ctypes.POINTER(_DataBlob),
        wintypes.LPCWSTR,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(_DataBlob),
    ]
    _crypt32.CryptProtectData.restype = wintypes.BOOL
    _crypt32.CryptUnprotectData.argtypes = [
        ctypes.POINTER(_DataBlob),
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(_DataBlob),
    ]
    _crypt32.CryptUnprotectData.restype = wintypes.BOOL
    _kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    _kernel32.LocalFree.restype = ctypes.c_void_p
else:
    _crypt32 = None
    _kernel32 = None


def _blob(veri: bytes) -> tuple[_DataBlob, ctypes.Array]:
    tampon = ctypes.create_string_buffer(veri)
    return (
        _DataBlob(len(veri), ctypes.cast(tampon, ctypes.POINTER(ctypes.c_byte))),
        tampon,
    )


def _windows_sifrele(veri: bytes) -> bytes:
    if os.name != "nt":
        raise RuntimeError("Güvenli Telegram kaydı yalnızca Windows üzerinde kullanılabilir.")
    giris, _tampon = _blob(veri)
    cikis = _DataBlob()
    basarili = _crypt32.CryptProtectData(
        ctypes.byref(giris),
        "İhalex Telegram",
        None,
        None,
        None,
        CRYPTPROTECT_UI_FORBIDDEN,
        ctypes.byref(cikis),
    )
    if not basarili:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        return ctypes.string_at(cikis.pbData, cikis.cbData)
    finally:
        _kernel32.LocalFree(ctypes.cast(cikis.pbData, ctypes.c_void_p))


def _windows_coz(veri: bytes) -> bytes:
    if os.name != "nt":
        raise RuntimeError("Güvenli Telegram kaydı yalnızca Windows üzerinde kullanılabilir.")
    giris, _tampon = _blob(veri)
    cikis = _DataBlob()
    basarili = _crypt32.CryptUnprotectData(
        ctypes.byref(giris),
        None,
        None,
        None,
        None,
        CRYPTPROTECT_UI_FORBIDDEN,
        ctypes.byref(cikis),
    )
    if not basarili:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        return ctypes.string_at(cikis.pbData, cikis.cbData)
    finally:
        _kernel32.LocalFree(ctypes.cast(cikis.pbData, ctypes.c_void_p))


def kimlik_kaydet(token: str, chat_id: str, bot_kullanici_adi: str = "") -> None:
    veri = json.dumps(
        {
            "token": token,
            "chat_id": str(chat_id),
            "bot_kullanici_adi": bot_kullanici_adi,
        },
        ensure_ascii=False,
    ).encode("utf-8")
    sifreli = base64.b64encode(_windows_sifrele(veri))
    gecici = KIMLIK_DOSYASI.with_suffix(".tmp")
    gecici.write_bytes(sifreli)
    gecici.replace(KIMLIK_DOSYASI)


def kimlik_oku() -> dict[str, str] | None:
    if not KIMLIK_DOSYASI.exists():
        return None
    try:
        veri = _windows_coz(base64.b64decode(KIMLIK_DOSYASI.read_bytes()))
        kimlik = json.loads(veri.decode("utf-8"))
        if not kimlik.get("token") or not kimlik.get("chat_id"):
            return None
        return {anahtar: str(deger) for anahtar, deger in kimlik.items()}
    except (OSError, ValueError, json.JSONDecodeError):
        return None
