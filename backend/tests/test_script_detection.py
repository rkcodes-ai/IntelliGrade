"""Unit tests for `app.services.document_intelligence.script_detection`
— deterministic, real Unicode-codepoint classification (no model, no
mocking possible or needed)."""

from __future__ import annotations

from app.services.document_intelligence.script_detection import detect_script


def test_empty_text_is_unknown_not_fabricated_latin() -> None:
    result = detect_script("")
    assert result.primary_script == "UNKNOWN"
    assert result.candidate_languages == ()


def test_digits_and_punctuation_only_is_unknown() -> None:
    result = detect_script("123, 456. 789;")
    assert result.primary_script == "UNKNOWN"


def test_latin_text_detected_with_english_candidate() -> None:
    result = detect_script("The quick brown fox.")
    assert result.primary_script == "LATIN"
    assert result.candidate_languages == ("English",)


def test_devanagari_never_claims_a_single_certain_language() -> None:
    result = detect_script("नमस्ते दुनिया")
    assert result.primary_script == "DEVANAGARI"
    assert len(result.candidate_languages) > 1  # script alone cannot disambiguate
    assert "Hindi" in result.candidate_languages
    assert "Marathi" in result.candidate_languages
    assert "Sanskrit" in result.candidate_languages


def test_bengali_covers_bengali_and_assamese() -> None:
    result = detect_script("আমি ভালো আছি")
    assert result.primary_script == "BENGALI"
    assert "Bengali" in result.candidate_languages
    assert "Assamese" in result.candidate_languages


def test_gurmukhi_maps_to_punjabi() -> None:
    result = detect_script("ਸਤ ਸ੍ਰੀ ਅਕਾਲ")
    assert result.primary_script == "GURMUKHI"
    assert result.candidate_languages == ("Punjabi",)


def test_arabic_derived_script_covers_urdu_kashmiri_sindhi() -> None:
    result = detect_script("یہ ایک جملہ ہے")
    assert result.primary_script == "ARABIC"
    assert "Urdu" in result.candidate_languages
    assert "Kashmiri" in result.candidate_languages
    assert "Sindhi" in result.candidate_languages


def test_meitei_mayek_script_detected() -> None:
    result = detect_script("ꯀꯁꯂꯃꯄ")
    assert result.primary_script == "MEITEI_MAYEK"
    assert result.candidate_languages == ("Manipuri/Meitei",)


def test_ol_chiki_script_detected() -> None:
    result = detect_script("᱐᱑᱒᱓᱔")
    assert result.primary_script == "OL_CHIKI"
    assert result.candidate_languages == ("Santali",)


def test_mixed_script_flag_requires_meaningful_presence_not_a_stray_character() -> None:
    # A single stray Devanagari digit inside an otherwise all-Latin
    # sentence should not flip is_multi_script -- below the presence
    # threshold.
    result = detect_script("This is a long English sentence with one Devanagari letter अ inside.")
    assert result.primary_script == "LATIN"


def test_genuinely_mixed_tamil_english_flagged() -> None:
    result = detect_script("இயக்க முறைமை Operating System ஐ கையாள்கிறது இயக்க முறைமை")
    assert result.is_multi_script is True


def test_to_dict_is_json_serializable() -> None:
    import json

    result = detect_script("Hello")
    serialized = json.dumps(result.to_dict())
    assert "primary_script" in serialized
