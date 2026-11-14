# Escolhe o texto certo de conteúdos bilingues ({pt, en}) conforme o idioma do utilizador.
def pick(text, locale: str) -> str:
    if isinstance(text, str):
        return text
    key = "en" if locale == "en" else "pt"
    return text.get(key) or text.get("pt") or text.get("en") or ""
