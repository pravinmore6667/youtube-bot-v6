def sanitize_for_tts(text: str) -> str:
    """Remove/replace Unicode characters that break TTS encoders."""
    replacements = {
        "\u2014": "-",   # em dash  ← THIS was causing Bhashini failure
        "\u2013": "-",   # en dash
        "\u2019": "'",   # right single quote
        "\u2018": "'",   # left single quote
        "\u201c": '"',   # left double quote
        "\u201d": '"',   # right double quote
        "\u2026": "...", # ellipsis
        "\u00e9": "e",
        "\u00e0": "a",
        "\u00e8": "e",
    }
    for char, repl in replacements.items():
        text = text.replace(char, repl)
    return text.strip()
