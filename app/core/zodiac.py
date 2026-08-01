"""Constantes zodiacales partagées : signes, éléments, modalités."""

SIGNS = [
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
]

SIGNS_FR = {
    "Aries": "Bélier", "Taurus": "Taureau", "Gemini": "Gémeaux", "Cancer": "Cancer",
    "Leo": "Lion", "Virgo": "Vierge", "Libra": "Balance", "Scorpio": "Scorpion",
    "Sagittarius": "Sagittaire", "Capricorn": "Capricorne", "Aquarius": "Verseau", "Pisces": "Poissons",
}

ELEMENTS = {
    "Aries": "fire", "Leo": "fire", "Sagittarius": "fire",
    "Taurus": "earth", "Virgo": "earth", "Capricorn": "earth",
    "Gemini": "air", "Libra": "air", "Aquarius": "air",
    "Cancer": "water", "Scorpio": "water", "Pisces": "water",
}

MODALITIES = {
    "Aries": "cardinal", "Cancer": "cardinal", "Libra": "cardinal", "Capricorn": "cardinal",
    "Taurus": "fixed", "Leo": "fixed", "Scorpio": "fixed", "Aquarius": "fixed",
    "Gemini": "mutable", "Virgo": "mutable", "Sagittarius": "mutable", "Pisces": "mutable",
}


def sign_and_degree(longitude: float) -> tuple[str, float]:
    """Retourne (signe, degré dans le signe [0,30)) pour une longitude écliptique [0,360)."""
    longitude = longitude % 360
    index = int(longitude // 30)
    degree = longitude - index * 30
    return SIGNS[index], degree


def sign_index(sign: str) -> int:
    return SIGNS.index(sign)


def signs_distance(from_sign: str, to_sign: str) -> int:
    """Distance en 'maisons de signes' (1 = même signe, ... 12) de from_sign vers to_sign, sens zodiacal."""
    return ((sign_index(to_sign) - sign_index(from_sign)) % 12) + 1
