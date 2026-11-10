"""Fuzzy matching of free text against the workspace's own categories.

Ported from Family-Budget: tolerates Russian word endings, typos, the wrong
keyboard layout ("rfat" -> "кафе"), Latin transliteration and look-alike
Latin letters inside Cyrillic words. It only picks a category when the best
match is clearly better than the runner-up; otherwise it returns None.
"""

from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher
from typing import Iterable, List, Optional, Sequence, Tuple, TypeVar

T = TypeVar("T")

_ENDINGS = (
    "иями", "ами", "ями", "ого", "ему", "ыми", "ими", "ые", "ое", "ая", "яя", "ий", "ый", "ой",
    "ие", "ую", "юю", "ам", "ям", "ов", "ев", "ом", "ем", "а", "я", "ы", "и", "е", "у",
)
_EN = "qwertyuiop[]asdfghjkl;'zxcvbnm,."
_RU = "йцукенгшщзхъфывапролджэячсмитьбю"
_TRANSLIT = {
    "shch": "щ", "sch": "щ", "yo": "ё", "zh": "ж", "kh": "х", "ts": "ц", "ch": "ч", "sh": "ш",
    "yu": "ю", "ya": "я", "a": "а", "b": "б", "v": "в", "g": "г", "d": "д", "e": "е", "z": "з",
    "i": "и", "j": "й", "k": "к", "l": "л", "m": "м", "n": "н", "o": "о", "p": "п", "r": "р",
    "s": "с", "t": "т", "u": "у", "f": "ф", "h": "х", "c": "к", "y": "ы",
}
_TRANSLIT_RE = re.compile("|".join(sorted(_TRANSLIT, key=len, reverse=True)))

MIN_SCORE = 0.78
MIN_GAP = 0.10


def normalize(text: str) -> str:
    return " ".join(re.sub(r"[^\w\s]", " ", str(text).lower().replace("ё", "е")).split())


def stems(text: str) -> str:
    result = []
    for word in normalize(text).split():
        if len(word) > 4:
            for ending in _ENDINGS:
                if word.endswith(ending) and len(word) - len(ending) >= 3:
                    word = word[: -len(ending)]
                    break
        result.append(word)
    return " ".join(result)


def basic_score(a: str, b: str) -> float:
    a, b = stems(a), stems(b)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    if set(a.split()) <= set(b.split()):
        return 0.92
    return SequenceMatcher(None, a, b).ratio()


def variants(text: str) -> set:
    value = normalize(unicodedata.normalize("NFKC", text))
    lower = str(text).lower()
    result = {
        value,
        normalize(lower.translate(str.maketrans(_EN, _RU))),
        normalize(lower.translate(str.maketrans(_RU, _EN))),
        re.sub(r"(\w)\1{1,}", r"\1", value),
    }
    if re.search("[а-я]", value):
        result.add(value.translate(str.maketrans("aceopxykmt", "асеорхукмт")))
    if re.fullmatch(r"[a-z\s]+", value):
        result.add(_TRANSLIT_RE.sub(lambda m: _TRANSLIT[m[0]], value))
    return result


def score(text: str, name: str) -> float:
    target = normalize(name).split()
    values = []
    for candidate in variants(str(text)[:320]):
        values.append(basic_score(candidate, name))
        words = candidate.split()[:60]
        if len(words) > len(target) and len(normalize(name)) >= 4:
            for width in {len(target), len(target) + 1}:
                values.extend(
                    0.96 * basic_score(" ".join(words[i : i + width]), name)
                    for i in range(len(words) - width + 1)
                )
    return max(values, default=0.0)


def best_match(text: str, items: Iterable[T], name_of=lambda x: x) -> Optional[T]:
    """Unique clear winner among items, or None when absent/ambiguous."""
    if len(normalize(text)) < 3:
        return None
    text = re.sub(r"^\s*категори[яию]\s*[:—-]?\s*", "", text, flags=re.I)
    ranked: List[Tuple[float, int, T]] = sorted(
        ((score(text, name_of(item)), i, item) for i, item in enumerate(items)),
        key=lambda r: (-r[0], r[1]),
    )
    if not ranked or ranked[0][0] < MIN_SCORE:
        return None
    if len(ranked) > 1 and ranked[0][0] - ranked[1][0] < MIN_GAP:
        return None
    return ranked[0][2]


def candidates(text: str, items: Sequence[T], name_of=lambda x: x, limit: int = 3, floor: float = 0.55) -> List[T]:
    ranked = sorted(((score(text, name_of(item)), i, item) for i, item in enumerate(items)), key=lambda r: (-r[0], r[1]))
    return [item for value, _i, item in ranked[:limit] if value >= floor]
