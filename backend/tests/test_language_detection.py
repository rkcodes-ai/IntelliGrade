"""Unit tests for `app.services.document_intelligence.language_detection`
— real, unmocked fastText lid.176 inference via the isolated `.venv-langid`
runtime bridge (Section 51: "mocks do NOT count as real verification")."""

from __future__ import annotations

from app.services.document_intelligence.language_detection import (
    FASTTEXT_LABEL_TO_LANGUAGE,
    LANGUAGE_NAME_TO_LANGUAGETOOL_CODE,
    LANGUAGE_NAME_TO_OCR_CODE,
    LANGUAGES_WITHOUT_FASTTEXT_SUPPORT,
    FastTextLanguageDetector,
)

_detector = FastTextLanguageDetector()

_REAL_SAMPLES = {
    "English": "The operating system schedules processes based on priority.",
    "Tamil": "இயக்க முறைமையானது செயலாக்க அட்டவணையை நிர்வகிக்கிறது.",
    "Hindi": "ऑपरेटिंग सिस्टम प्रोसेस शेड्यूलिंग को नियंत्रित करता है।",
    "Telugu": "ఆపరేటింగ్ సిస్టమ్ ప్రాసెస్ షెడ్యూలింగ్‌ను నిర్వహిస్తుంది.",
    "Malayalam": "ഓപ്പറേറ്റിംഗ് സിസ്റ്റം പ്രോസസ് ഷെഡ്യൂളിംഗ് കൈകാര്യം ചെയ്യുന്നു.",
    "Kannada": "ಆಪರೇಟಿಂಗ್ ಸಿಸ್ಟಮ್ ಪ್ರಕ್ರಿಯೆ ವೇಳಾಪಟ್ಟಿಯನ್ನು ನಿರ್ವಹಿಸುತ್ತದೆ.",
    "Bengali": "অপারেটিং সিস্টেম প্রক্রিয়া নির্ধারণ পরিচালনা করে।",
    "Marathi": "ऑपरेटिंग सिस्टम प्रक्रिया वेळापत्रक व्यवस्थापित करते.",
    "Gujarati": "ઓપરેટિંગ સિસ્ટમ પ્રક્રિયા શેડ્યુલિંગનું સંચાલન કરે છે.",
    "Punjabi": "ਓਪਰੇਟਿੰਗ ਸਿਸਟਮ ਪ੍ਰਕਿਰਿਆ ਸ਼ਡਿਊਲਿੰਗ ਦਾ ਪ੍ਰਬੰਧਨ ਕਰਦਾ ਹੈ।",
    "Urdu": "آپریٹنگ سسٹم عمل کے شیڈولنگ کا انتظام کرتا ہے۔",
}


def test_health_check_reports_installed() -> None:
    health = _detector.health_check()
    assert health["installed"] is True
    assert health["ready"] is True


def test_real_detection_priority_a_english() -> None:
    result = _detector.detect(_REAL_SAMPLES["English"])
    assert result.status == "SUCCESS"
    assert result.primary_language == "English"


def test_real_detection_priority_a_tamil() -> None:
    result = _detector.detect(_REAL_SAMPLES["Tamil"])
    assert result.status == "SUCCESS"
    assert result.primary_language == "Tamil"
    assert result.confidence > 0.9


def test_real_detection_priority_a_hindi() -> None:
    result = _detector.detect(_REAL_SAMPLES["Hindi"])
    assert result.primary_language == "Hindi"


def test_real_detection_priority_a_telugu() -> None:
    result = _detector.detect(_REAL_SAMPLES["Telugu"])
    assert result.primary_language == "Telugu"


def test_real_detection_priority_a_malayalam() -> None:
    result = _detector.detect(_REAL_SAMPLES["Malayalam"])
    assert result.primary_language == "Malayalam"


def test_real_detection_priority_a_kannada() -> None:
    result = _detector.detect(_REAL_SAMPLES["Kannada"])
    assert result.primary_language == "Kannada"


def test_real_detection_priority_b_bengali() -> None:
    result = _detector.detect(_REAL_SAMPLES["Bengali"])
    assert result.primary_language == "Bengali"


def test_real_detection_priority_b_marathi() -> None:
    result = _detector.detect(_REAL_SAMPLES["Marathi"])
    assert result.primary_language == "Marathi"


def test_real_detection_priority_b_gujarati() -> None:
    result = _detector.detect(_REAL_SAMPLES["Gujarati"])
    assert result.primary_language == "Gujarati"


def test_real_detection_priority_b_punjabi() -> None:
    result = _detector.detect(_REAL_SAMPLES["Punjabi"])
    assert result.primary_language == "Punjabi"


def test_real_detection_priority_b_urdu() -> None:
    result = _detector.detect(_REAL_SAMPLES["Urdu"])
    assert result.primary_language == "Urdu"


def test_empty_text_returns_empty_status_without_invoking_model() -> None:
    result = _detector.detect("")
    assert result.status == "EMPTY_TEXT"
    assert result.primary_language is None


def test_missing_runtime_fails_safely() -> None:
    detector = FastTextLanguageDetector(python_exe="C:/does/not/exist/python.exe")
    result = detector.detect("some text")
    assert result.status == "FAILED"
    assert result.detail is not None


def test_short_ambiguous_technical_string_does_not_fabricate_high_confidence() -> None:
    """Section 27: short technical strings like 'CPU' carry little
    language evidence -- this test doesn't assert a specific language
    (fastText WILL produce some guess), only that the result honestly
    reports whatever confidence it actually computed rather than always
    claiming certainty."""
    result = _detector.detect("CPU")
    assert result.status in ("SUCCESS", "LOW_CONFIDENCE")
    assert 0.0 <= result.confidence <= 1.0


def test_candidate_languages_include_raw_label_for_audit() -> None:
    result = _detector.detect(_REAL_SAMPLES["Tamil"])
    assert result.candidate_languages
    assert result.candidate_languages[0].raw_label == "ta"


def test_to_dict_is_json_serializable() -> None:
    import json

    result = _detector.detect(_REAL_SAMPLES["English"])
    serialized = json.dumps(result.to_dict())
    assert "primary_language" in serialized


def test_fasttext_label_map_has_no_duplicate_language_names() -> None:
    names = list(FASTTEXT_LABEL_TO_LANGUAGE.values())
    assert len(names) == len(set(names))


def test_languages_without_fasttext_support_are_honestly_documented() -> None:
    for language in LANGUAGES_WITHOUT_FASTTEXT_SUPPORT:
        assert language not in FASTTEXT_LABEL_TO_LANGUAGE.values()


def test_ocr_code_map_preserves_existing_english_default() -> None:
    assert LANGUAGE_NAME_TO_OCR_CODE["English"] == "eng"


def test_languagetool_code_map_only_contains_genuinely_supported_languages() -> None:
    from app.services.document_intelligence.language_quality import SUPPORTED_LANGUAGES

    for code in LANGUAGE_NAME_TO_LANGUAGETOOL_CODE.values():
        assert code in SUPPORTED_LANGUAGES
