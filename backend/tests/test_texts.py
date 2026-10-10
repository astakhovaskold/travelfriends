import pytest
from app.services.common import lang_of
from app.texts import TEXTS, render_text
from string import Formatter


def test_translations_have_matching_keys_and_placeholders():
    assert set(TEXTS["ru"]) == set(TEXTS["en"])
    formatter = Formatter()
    for key in TEXTS["en"]:
        fields = [
            {name for _, name, _, _ in formatter.parse(TEXTS[lang][key]) if name is not None}
            for lang in ("ru", "en")
        ]
        assert fields[0] == fields[1], key
        for lang in ("ru", "en"):
            assert render_text(key, lang, **dict.fromkeys(fields[0], "test"))


def test_rendering_preserves_copy_and_unknown_language_falls_back():
    assert (
            render_text("trip.accepted", "ru", dest="Мадрид")
            == "Тебя приняли в поездку «Мадрид»! Чат открыт."
    )
    assert (
            render_text("trip.joined", "en", who="Astrid", dest="Madrid", members=1, people=2)
            == "Astrid joined your trip: Madrid (1/2)"
    )
    assert render_text("button.chat", "es") == render_text("button.chat", "en")
    assert render_text("admin.banned", "en", user_id="101") == "Banned 101"
    assert lang_of("uk") == "ru"
    assert lang_of("es") == "en"


def test_invalid_template_usage_is_visible():
    with pytest.raises(KeyError):
        render_text("unknown", "en")
    with pytest.raises(KeyError):
        render_text("trip.accepted", "en")
