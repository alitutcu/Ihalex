"""Okul adları için tek ve tekrar kullanılabilir normalleştirme kuralı."""

from __future__ import annotations

import re
import unicodedata


def okul_adi_temizle(deger: object) -> str | None:
    """Okul adında harf, rakam, nokta ve boşluk dışındaki işaretleri kaldırır."""
    metin = unicodedata.normalize("NFC", str(deger or "")).replace("_", " ")
    metin = re.sub(r"[^\w\s.]", " ", metin, flags=re.UNICODE)
    metin = re.sub(r"\s+", " ", metin).strip(" .")
    return metin or None
