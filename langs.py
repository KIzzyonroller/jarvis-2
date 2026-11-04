"""
Other languages (the "Other languages" option): which language a reply is in, and which Kokoro voice reads it.

Kokoro has voices for Spanish, French, Italian, Brazilian Portuguese and Hindi (plus English). Detection is a quick
count of each language's most common little words (and Devanagari letters for Hindi): no model, no delay. Short or
mixed text stays in English, so a stray "no" or "a" never flips his accent.
"""
import re

# (language code for Kokoro's pronunciation, male voice, female voice)
VOICES = {
    "es": ("es", "em_alex", "ef_dora"),
    "fr": ("fr-fr", "ff_siwis", "ff_siwis"),         # Kokoro only has a French woman's voice
    "it": ("it", "im_nicola", "if_sara"),
    "pt": ("pt-br", "pm_alex", "pf_dora"),
    "hi": ("hi", "hm_omega", "hf_alpha"),
}
_WORDS = {
    "es": "el la los las de que y en un una es por con para no se lo como más pero sus le ya o este sí porque esta "
          "entre cuando muy sin sobre también me hasta hay donde quien desde todo nos durante todos uno les ni contra "
          "otros ese eso ante ellos e esto mí antes algunos qué unos yo otro otras otra él tanto esa estos mucho "
          "quienes nada muchos cual poco ella estar estas algunas algo nosotros mi mis tú te ti tu tus ellas vosotros "
          "está estoy hola gracias señor ahora puedo aquí claro",
    "fr": "le la les de des du et en un une est que qui pour pas dans ce il elle ne sur se plus par avec tout faire "
          "son mais nous vous je tu on au aux cette ces mon ma mes ton ta tes leur sont ai as avons avez ont été "
          "être bonjour merci oui très bien voici voilà aussi",
    "it": "il lo la gli le di che e è un una per non in con su mi ti si ma come anche questo questa sono sei siamo "
          "hanno ho hai ha del della dei delle nel nella al alla ciao grazie sì molto bene ecco perché",
    "pt": "o a os as de que e em um uma é para não com por se mais mas como seu sua ele ela você eu nós eles foi são "
          "está estou tem têm isso isto aqui muito obrigado obrigada olá sim também então do da dos das no na",
}
_SETS = {k: set(v.split()) for k, v in _WORDS.items()}
_EN = set("the a an and is are of to in it that you i he she we they this was for on with as be at by not have "
          "has do does your my me can will just what all so but".split())
_DEVANAGARI = re.compile(r"[ऀ-ॿ]")


def detect(text):
    """'es', 'fr', 'it', 'pt', 'hi' or 'en'."""
    t = (text or "").lower()
    if len(_DEVANAGARI.findall(t)) > 3:
        return "hi"
    words = re.findall(r"[a-zà-ÿ']+", t)
    if len(words) < 3:
        return "en"
    en = sum(w in _EN for w in words)
    best, score = "en", en
    for code, s in _SETS.items():
        n = sum(w in s for w in words)
        if n > score:
            best, score = code, n
    # accents tip a close call (ñ ¿ ¡ for Spanish, ç for French/Portuguese, ã õ for Portuguese)
    if best == "en" and score < 2:
        return "en"
    if best in ("es", "pt", "it") and re.search(r"[ãõ]", t):
        best = "pt"
    elif best in ("es", "pt", "it") and re.search(r"[ñ¿¡]", t):
        best = "es"
    return best if score >= max(2, en + 1) or best == "en" else "en"


def voice_for(text, persona_voice):
    """(voice, kokoro lang) for this text, or None to keep the persona's own English voice."""
    code = detect(text)
    if code == "en" or code not in VOICES:
        return None
    lang, male, female = VOICES[code]
    female_persona = len(persona_voice or "") > 1 and persona_voice[1] == "f"
    return (female if female_persona else male), lang


def reply_rule():
    """The line added to each message so his replies follow the language option."""
    import prefs
    if not prefs.get("languages"):
        return ""
    lang = prefs.get("language")
    names = {"es": "Spanish", "fr": "French", "it": "Italian", "pt": "Brazilian Portuguese", "hi": "Hindi", "en": "English"}
    if lang in names:
        return f"Always reply in {names[lang]}."
    return "Reply in the language the user spoke or wrote in."
