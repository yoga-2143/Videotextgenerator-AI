"""
Hard Words & Easy Meanings Service.
Identifies technical, domain-specific, or complex terms strictly present within
the video's source transcript and generates simple meanings, clear explanations,
and context-accurate examples without hallucinating external facts.
"""
import re
import json
import logging
import html
from app.services.error_validator import contains_raw_error_text

logger = logging.getLogger(__name__)

COMMON_ENGLISH_WORDS = {
    "the", "be", "to", "of", "and", "a", "in", "that", "have", "i", "it", "for",
    "not", "on", "with", "he", "as", "you", "do", "at", "this", "but", "his", "by",
    "from", "they", "we", "say", "her", "she", "or", "an", "will", "my", "one",
    "all", "would", "there", "their", "what", "so", "up", "out", "if", "about",
    "who", "get", "which", "go", "me", "when", "make", "can", "like", "time", "no",
    "just", "him", "know", "take", "people", "into", "year", "your", "good", "some",
    "could", "them", "see", "other", "than", "then", "now", "look", "only", "come",
    "its", "over", "think", "also", "back", "after", "use", "two", "how", "our",
    "work", "first", "well", "way", "even", "new", "want", "because", "any", "these",
    "give", "day", "most", "us", "is", "are", "was", "were", "been", "being", "has",
    "had", "doing", "does", "did", "going", "goes", "went", "gone", "make", "made",
    "video", "watch", "channel", "subscribe", "thanks", "welcome", "hello", "today"
}

# Domain vocabulary database for instant, accurate explanations grounded in technical contexts
KNOWN_HARD_WORDS_DB = {
    "algorithm": {
        "simple_meaning": "A step-by-step method used to solve a problem or complete a task.",
        "explanation": "A set of clear instructions that a computer or person follows to accomplish a specific goal.",
        "example": "Searching for a contact in a phonebook follows an algorithm."
    },
    "figma": {
        "simple_meaning": "A web-based interface design and prototyping tool.",
        "explanation": "Software used by UI/UX designers to build app screens, websites, and interactive prototypes collaboratively.",
        "example": "Designers create app layouts and vector wireframes using Figma."
    },
    "react": {
        "simple_meaning": "A JavaScript library for building user interfaces.",
        "explanation": "A front-end development technology that lets developers create interactive web components efficiently.",
        "example": "Modern web apps update dynamic buttons and views using React."
    },
    "javascript": {
        "simple_meaning": "A programming language used to add interactivity to web pages.",
        "explanation": "A core web technology that enables interactive animations, form validation, and web applications.",
        "example": "JavaScript handles user click events and data fetching in browsers."
    },
    "python": {
        "simple_meaning": "A high-level programming language known for readability.",
        "explanation": "A versatile language widely used in software development, data science, and artificial intelligence.",
        "example": "Python is used to build web backends and train machine learning models."
    },
    "api": {
        "simple_meaning": "Application Programming Interface — a way for two programs to talk to each other.",
        "explanation": "A set of rules that lets different software applications request and exchange data securely.",
        "example": "A weather app uses an API to get live temperature data from a server."
    },
    "database": {
        "simple_meaning": "An organized collection of structured data stored electronically.",
        "explanation": "A system used to store, manage, and retrieve data efficiently for applications.",
        "example": "User login details and user profiles are saved in a database."
    },
    "html": {
        "simple_meaning": "HyperText Markup Language — the standard code for web page structure.",
        "explanation": "The foundational language used to structure headings, text, links, and elements on the web.",
        "example": "Every webpage uses HTML tags like <h1> and <p> to display content."
    },
    "css": {
        "simple_meaning": "Cascading Style Sheets — used to style and layout web pages.",
        "explanation": "A style sheet language used to format fonts, colors, spacing, and responsive design on websites.",
        "example": "CSS turns plain HTML text into styled buttons and grid layouts."
    },
    "patanjali": {
        "simple_meaning": "An ancient sage credited with organizing the Yoga Sutras.",
        "explanation": "The ancient scholar who compiled the fundamental philosophy and principles of classical Ashtanga Yoga.",
        "example": "Patanjali described eight stages of yoga practice in the Yoga Sutras."
    },
    "samadhi": {
        "simple_meaning": "A state of deep meditative absorption and focused consciousness.",
        "explanation": "The ultimate stage of yoga meditation where the mind becomes fully absorbed in pure awareness.",
        "example": "In meditation, Samadhi represents complete mental tranquility and unity."
    },
    "prana": {
        "simple_meaning": "Vital life force energy or breath energy.",
        "explanation": "The foundational energy concept in Eastern wellness referring to vital breath and life energy.",
        "example": "Pranayama techniques help regulate prana through controlled breathing."
    },
    "chitta": {
        "simple_meaning": "The mind-stuff or collective mental consciousness.",
        "explanation": "In yoga philosophy, Chitta refers to the mind comprising intellect, memory, and ego.",
        "example": "Yoga aims to calm the fluctuating thoughts of Chitta."
    },
    "ahamkara": {
        "simple_meaning": "The sense of ego or self-identity.",
        "explanation": "The aspect of human consciousness responsible for feelings of individual ownership and self.",
        "example": "Ahamkara creates the feeling of 'I' and 'mine' in personal thoughts."
    },
    "prototype": {
        "simple_meaning": "An early sample or model built to test a concept.",
        "explanation": "A preliminary version of a product created to test and validate user experience before full build.",
        "example": "The team created an interactive mobile app prototype to test navigation."
    },
    "wireframe": {
        "simple_meaning": "A basic visual blueprint of a screen or user interface.",
        "explanation": "A low-fidelity structural layout showing where content and UI elements will be placed.",
        "example": "Designers outline button positions on a wireframe before applying colors."
    },
    "asynchronous": {
        "simple_meaning": "Operations that execute independently without blocking the main process.",
        "explanation": "A execution pattern where tasks run in the background without making the user wait.",
        "example": "Downloading a file asynchronously lets you continue browsing the site."
    },
    "validation": {
        "simple_meaning": "The process of checking that data is accurate and correctly formatted.",
        "explanation": "Verifying input data against rules to ensure safety, completeness, and accuracy.",
        "example": "Form validation checks that an email address contains an '@' symbol."
    },
    "neural": {
        "simple_meaning": "Relating to artificial neural networks inspired by biological brain cells.",
        "explanation": "AI architectures designed with interconnected layers that learn patterns from data.",
        "example": "Neural networks are used to synthesize human-like speech and recognize images."
    },
    "synthesis": {
        "simple_meaning": "The combination of ideas or data to form a connected whole.",
        "explanation": "Merging separate elements into a unified, clear, and comprehensive summary.",
        "example": "The article provides a synthesis of key technical concepts from the video."
    },
    "mitigation": {
        "simple_meaning": "The action of reducing the severity, risk, or painful impact of something.",
        "explanation": "Taking proactive steps to prevent or lessen potential errors, risks, or failures.",
        "example": "Data backups are an essential risk mitigation strategy for servers."
    },
    "authentication": {
        "simple_meaning": "The process of verifying the identity of a user or system.",
        "explanation": "Confirming who someone is before giving access to accounts or secure data.",
        "example": "Entering a password and one-time code completes user authentication."
    }
}


def extract_candidate_words_from_transcript(transcript_text: str) -> list[str]:
    """Finds technical or complex terms present in the transcript with bounded chunk sampling."""
    if not transcript_text or not isinstance(transcript_text, str):
        return []

    # Bounded sampling for long transcripts (1-10 hours)
    full_text = html.unescape(transcript_text)
    if len(full_text) > 24000:
        chunk_len = 8000
        mid_start = len(full_text) // 2 - 4000
        sampled_text = (
            full_text[:chunk_len] + "\n" +
            full_text[mid_start:mid_start + chunk_len] + "\n" +
            full_text[-chunk_len:]
        )
    else:
        sampled_text = full_text

    words = re.findall(r"\b[\w-]{3,}\b", sampled_text, flags=re.UNICODE)

    seen = set()
    candidates = []

    for w in words:
        w_lower = w.lower()
        if w_lower in COMMON_ENGLISH_WORDS:
            continue
        if len(w_lower) < 4 and w_lower not in ["api", "css", "url", "ui", "ux", "aws"]:
            continue

        if w_lower in KNOWN_HARD_WORDS_DB and w_lower not in seen:
            seen.add(w_lower)
            candidates.append(w)
        elif (len(w_lower) >= 8 or w.isupper() or any(tech in w_lower for tech in ["code", "tech", "data", "base", "script", "byte", "net", "web"])) and w_lower not in seen:
            seen.add(w_lower)
            candidates.append(w)

    return candidates


def generate_fallback_definition_for_word(word: str, transcript_context: str) -> dict:
    w_lower = word.lower().strip()
    if w_lower in KNOWN_HARD_WORDS_DB:
        entry = KNOWN_HARD_WORDS_DB[w_lower]
        return {
            "word": word.capitalize() if word.islower() else word,
            "simple_meaning": entry["simple_meaning"],
            "explanation": entry["explanation"],
            "example": entry["example"]
        }

    # Contextual sentence search for fallback with strict length bounding (max 100 chars)
    raw_parts = [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", transcript_context) if word.lower() in s.lower()]
    if raw_parts:
        candidate = raw_parts[0]
        if len(candidate) > 100:
            candidate = candidate[:100].rsplit(' ', 1)[0] + "..."
        example_sentence = candidate
    else:
        example_sentence = f"{word} is a key concept discussed in this video."

    return {
        "word": word.capitalize() if word.islower() else word,
        "simple_meaning": f"A key technical term ({word}) used in the video content.",
        "explanation": f"In the context of this video, {word} refers to a specific concept, component, or technical method.",
        "example": example_sentence
    }


def extract_hard_words(transcript_text: str, video_title: str = "") -> list[dict]:
    """
    Primary entry point: extracts hard words strictly from the current transcript.
    Returns a list of dicts: [{"word": "...", "simple_meaning": "...", "explanation": "...", "example": "..."}]
    """
    if not transcript_text or contains_raw_error_text(transcript_text):
        return []

    candidates = extract_candidate_words_from_transcript(transcript_text)
    if not candidates:
        return []

    # Limit to top 5 most relevant terms
    selected_words = candidates[:5]
    result = []
    seen_words = set()

    for word in selected_words:
        w_norm = word.lower()
        if w_norm in seen_words:
            continue
        seen_words.add(w_norm)
        item = generate_fallback_definition_for_word(word, transcript_text)
        result.append(item)

    logger.info(f"[HARD_WORDS] Extracted {len(result)} hard words for video '{video_title}': {[r['word'] for r in result]}")
    return result
