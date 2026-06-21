from hymns.transliteration import transliterate, _transliterate_word


# --- empty / passthrough -----------------------------------------------

def test_transliterate_empty():
    assert transliterate("") == ""
    assert transliterate(None) == ""


def test_transliterate_passthrough_non_armenian():
    assert transliterate("Hello World") == "Hello World"
    assert transliterate("123 abc!") == "123 abc!"


def test_transliterate_preserves_punctuation_and_whitespace():
    assert transliterate("սեր - սեր,։") == "ser - ser,։"


# --- letter-level mapping ----------------------------------------------

def test_simple_consonants_and_vowels():
    # ս -> s, ե (non-initial) -> e, ր -> r
    assert _transliterate_word("սեր") == "ser"


def test_word_initial_e_becomes_ye():
    # ե at i==0 -> "ye"
    assert _transliterate_word("ես") == "yes"


def test_word_initial_o_becomes_vo():
    # ո at i==0 -> "vo"
    assert _transliterate_word("ով") == "vov"  # ո->vo, վ->v


def test_non_initial_e_stays_e():
    # first letter ս -> s, then ե -> e
    assert _transliterate_word("սե") == "se"


def test_non_initial_o_stays_o():
    # first letter վ -> v, then ո -> o
    assert _transliterate_word("վո") == "vo"


# --- digraph ու --------------------------------------------------------

def test_digraph_un_becomes_u():
    assert _transliterate_word("ու") == "u"


def test_digraph_un_mid_word():
    # ս -> s, ու -> u, ր -> r
    assert _transliterate_word("սուր") == "sur"


def test_digraph_at_word_start_takes_precedence_over_e_o_rules():
    # ու at start -> "u" (not "vo" + "ւ")
    assert _transliterate_word("ուր") == "ur"


def test_standalone_wn_is_silent():
    # ս -> s, ւ -> skipped, ր -> r
    assert _transliterate_word("սւր") == "sr"


# --- capitalization -----------------------------------------------------

def test_leading_capital_is_preserved():
    # Ո -> "vo" at start, then capitalized -> "Vo"
    assert _transliterate_word("Ո") == "Vo"
    # Ե -> "ye" at start, then capitalized -> "Ye"
    assert _transliterate_word("Ե") == "Ye"


def test_capital_digraph_un_becomes_U():
    assert _transliterate_word("Ու") == "U"


def test_only_first_letter_capitalized_in_output():
    # multi-letter word with leading capital: only first output char is upper
    result = _transliterate_word("Սեր")
    assert result == "Ser"


# --- full text with word boundaries ------------------------------------

def test_transliterate_splits_on_punctuation():
    # Two words separated by a space
    assert transliterate("սեր սեր") == "ser ser"


def test_transliterate_mixed_script_sentence():
    # Armenian word, space, latin word
    assert transliterate("սեր love") == "ser love"


def test_transliterate_preserves_armenian_apostrophe_inside_word():
    # ՚ (armenian apostrophe) is treated as part of the word
    out = transliterate("սեր՚ս")
    assert out.startswith("ser")
