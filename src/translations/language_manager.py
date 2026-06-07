from src.translations.translations import TRANSLATIONS


class LanguageManager:

    current_language = "en"

    @classmethod
    def set_language(cls, language):
        cls.current_language = language

    @classmethod
    def translate(cls, key):
        return TRANSLATIONS.get(
            cls.current_language,
            TRANSLATIONS["en"]
        ).get(
            key,
            key
        )