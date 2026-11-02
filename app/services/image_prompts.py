"""Conservative preparation of benign literary scene descriptions."""
import re

STYLE_SUFFIX = ", book illustration style, painterly watercolor and ink, cinematic lighting, no text, no letters, no numbers, no writing, no watermark"

# Explicit literary disambiguation, not an attempt to hide prohibited intent.
IDIOM_SCENES = {
    "as dead as a door-nail": "A quiet Victorian counting-house with an empty chair beside a ledger",
    "dead as a door-nail": "A quiet Victorian counting-house with an empty chair beside a ledger",
    "murdering the time": "A tense royal music performance with a singer and an impatient queen",
}
DISALLOWED = re.compile(r"\b(graphic gore|sexual assault|child nudity|explicit sexual)\b", re.IGNORECASE)


def prepare_image_prompt(scene: str) -> str:
    if not isinstance(scene, str) or not scene.strip() or len(scene) > 500:
        raise ValueError("A short scene description is required")
    if DISALLOWED.search(scene):
        raise ValueError("Scene requires manual safety review")
    if any(ord(char) < 32 and char not in "\n\r\t" for char in scene):
        raise ValueError("Control characters are not allowed")
    normalized = " ".join(scene.split()).strip(" ,.")
    normalized = IDIOM_SCENES.get(normalized.lower(), normalized)
    if not any("a" <= char.lower() <= "z" for char in normalized):
        raise ValueError("English scene text is required")
    if any(char.isalpha() and not char.isascii() for char in normalized):
        raise ValueError("English/Latin scene text is required")
    return normalized + STYLE_SUFFIX
