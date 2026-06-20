"""
Western Armenian phonetic transliteration (diaspora pronunciation).

Approximate letter-level scheme with light context rules for ե/Ե (-> "ye"
word-initially) and ո/Ո (-> "vo" word-initially) and the digraph ու (-> "u").
Intended for a read-along toggle on the site, not as an academic standard.
"""

# Lowercase map (applied after lowercasing the input).
_MAP = {
    "ա": "a", "բ": "p", "գ": "k", "դ": "t", "զ": "z", "է": "e", "ը": "ë",
    "թ": "t", "ժ": "j", "ի": "i", "լ": "l", "խ": "kh", "ծ": "ts", "կ": "g",
    "հ": "h", "ձ": "dz", "ղ": "gh", "ճ": "ch", "մ": "m", "յ": "y", "ն": "n",
    "շ": "sh", "չ": "ch", "պ": "b", "ջ": "j", "ռ": "r", "ս": "s", "վ": "v",
    "տ": "d", "ց": "ts", "փ": "p", "ք": "k", "և": "ev", "օ": "o", "ֆ": "f",
    "ո": "o", "ե": "e", "ր": "r",
}

_VOWELS = set("աէըիոօեև")


def _transliterate_word(word):
    out = []
    n = len(word)
    for i, ch in enumerate(word.lower()):
        # digraph ու -> u
        if ch == "ո" and i + 1 < n and word[i + 1].lower() == "ւ":
            out.append("u")
            continue
        if ch == "ւ":
            # handled by preceding ո (or silent standalone) -> skip
            continue
        # ե -> "ye" at word start or following a consonant cluster start;
        # keep simple: "ye" when first letter, else "e"
        if ch == "ե" and i == 0:
            out.append("ye")
            continue
        # ո -> "vo" at word start, else "o"
        if ch == "ո" and i == 0:
            out.append("vo")
            continue
        out.append(_MAP.get(ch, ch))
    result = "".join(out)
    # preserve leading capitalization of the original word
    if word and word[0].isupper():
        result = result[:1].upper() + result[1:]
    return result


def transliterate(text):
    if not text:
        return ""
    out = []
    word = []
    for ch in text:
        if ch.isalpha() or ch in ("՚", "'", "՝"):
            word.append(ch)
        else:
            if word:
                out.append(_transliterate_word("".join(word)))
                word = []
            out.append(ch)
    if word:
        out.append(_transliterate_word("".join(word)))
    return "".join(out)
