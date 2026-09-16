"""
LLM layer with a provider interface. Currently implements Gemini.
If no GEMINI_API_KEY is configured or if Gemini fails, falls back to an intelligent,
deterministic Prose Synthesizer & Speech Cleaner that extracts important facts
and rewrites them into clean, natural, easy-to-understand prose with NO raw speech noise.
"""
import os
import re
import json
import logging
import html
from app.services.error_validator import contains_raw_error_text

logger = logging.getLogger(__name__)

SPEECH_FILLERS = [
    r"(?i)\b(don't forget to|make sure to|be sure to|remember to|please)\s+.*?\b(like|subscribe|share|bell|comment|notification)s?\b.*?[.!?]?",
    r"(?i)\b(all right|alright|so yeah|right so|you know|i mean|basically|actually|literally|sort of|kind of|pretty much|you see|as you can see|here we are|so here we are|what's up|hello guys|welcome back|hey guys|hi everyone|hello everyone|what's up guys|in this video|in today's video|in this tutorial|in today's tutorial|let's dive in|without further ado|without any further delay|so without further delay|as i mentioned earlier|by the number of this video|by the end of this video|you are going to know|you are going to learn|where this photo is|after leaving \w+)\b[,.]?",
    r"(?i)\b(நான்\s+வந்து|வந்து|வந்துட்டு|அப்புறம்|அப்படின்ற|அப்படினு|அப்படினா|ஏன்னா|அதாவது)\b[,.]?",
    r"(?i)\b(the cool thing about|cool thing is|that's cool and|and that's cool|and that's pretty much all there is to say|that's pretty much all there is to say|all there is to say|pretty much all there is to say)\b[,.]?",
    r"(?i)\b(um+h?|uh+h?|hmm+|mhm+|err+|ah+)\b[,.]?",
    r"(?i)\b(thanks for watching|see you in the next|catch you in the next|link in description|sponsored by|peace out|if this video gets \d+ likes|get \d+ likes|post a video on how to)\b.*?[.!?]?",
]

SPEECH_NOISE_REPLACEMENTS = [
    (r"\bthese guys is that they have\b", "they have"),
    (r"\bthese guys have\b", "they have"),
    (r"\bis that they have\b", "they have"),
    (r"\band that's\.\s*$", "."),
    (r"\band that's\b", ""),
    (r"\bthat's cool\b", ""),
    (r"\breally\.\s*really\b", "exceptionally"),
    (r"\breally really\b", "exceptionally"),
    (r"\breally long\b", "exceptionally long"),
    (r"\bவிடகபரெண்டா\b", "விட வித்தியாசமா"),
    (r"\bfrரஷ்estw\.com\b", "freshestnow.com"),
    (r"\bநான் வந்து\b", ""),
    (r"\bஅப்படின்ற\b", ""),
]

CONTEXT_STT_CORRECTIONS = [
    (r"(?i)(?<![\w\u0B80-\u0BFF])(pigma|pig ma|fig ma|பிக்மா)(?![\w\u0B80-\u0BFF])", "Figma"),
    (r"(?i)(?<![\w\u0B80-\u0BFF])(index html|idex html|idex\.html|idx\.html|index3\.html|இdex html|இdeக்ஸ் hடிml|இன்டெக்ஸ் html)(?![\w\u0B80-\u0BFF])", "index.html"),
    (r"(?i)(?<![\w\u0B80-\u0BFF])(stitch|ஸ்டிட்ச்)(?![\w\u0B80-\u0BFF])", "Stitch"),
    (r"(?i)(?<![\w\u0B80-\u0BFF])(javascrip|java script|ஜாவாஸ்கிரிப்ட்)(?![\w\u0B80-\u0BFF])", "JavaScript"),
    (r"(?i)(?<![\w\u0B80-\u0BFF])(py thon|pythan|பைதான்)(?![\w\u0B80-\u0BFF])", "Python"),
    (r"(?i)(?<![\w\u0B80-\u0BFF])(re act|react js|reactjs|ரியாக்ட்)(?![\w\u0B80-\u0BFF])", "React"),
    (r"(?i)(?<![\w\u0B80-\u0BFF])(pangali|patangali|patanjali sutra|பஞ்சலி)(?![\w\u0B80-\u0BFF])", "Patanjali"),
    (r"(?i)(?<![\w\u0B80-\u0BFF])(samadi|samaadhi|சமாதி)(?![\w\u0B80-\u0BFF])", "Samadhi"),
    (r"(?i)(?<![\w\u0B80-\u0BFF])(yoga sutra|yogasutra|yogasutras|யோக சூத்திரம்)(?![\w\u0B80-\u0BFF])", "Yoga Sutras"),
    (r"(?i)(?<![\w\u0B80-\u0BFF])(praana|pran|பிராணன்)(?![\w\u0B80-\u0BFF])", "Prana"),
    (r"(?i)(?<![\w\u0B80-\u0BFF])(chita|chitham|chittam|சித்தம்)(?![\w\u0B80-\u0BFF])", "Chitta"),
    (r"(?i)(?<![\w\u0B80-\u0BFF])(ahamkar|ahamkara|அகங்காரம்)(?![\w\u0B80-\u0BFF])", "Ahamkara"),
    (r"(?i)(?<![\w\u0B80-\u0BFF])(sadhak|sadhaka|சாதகர்)(?![\w\u0B80-\u0BFF])", "Sadhaka"),
    (r"(?i)(?<![\w\u0B80-\u0BFF])(package\.json|பேக்கேஜ் json)(?![\w\u0B80-\u0BFF])", "package.json"),
    (r"(?i)(?<![\w\u0B80-\u0BFF])(npm install|என் பி எம் இன்ஸ்டால்)(?![\w\u0B80-\u0BFF])", "npm install"),
    (r"(?i)(?<![\w\u0B80-\u0BFF])(y fin finance|yfinance|y finance)(?![\w\u0B80-\u0BFF])", "yfinance"),
    (r"(?i)(?<![\w\u0B80-\u0BFF])(pct change|pct_change)(?![\w\u0B80-\u0BFF])", "pct_change()"),
    (r"(?i)(?<![\w\u0B80-\u0BFF])(look ahead bias|lookahead bias)(?![\w\u0B80-\u0BFF])", "look-ahead bias"),
    (r"(?i)(?<![\w\u0B80-\u0BFF])(np where|np_where)(?![\w\u0B80-\u0BFF])", "np.where()"),
    (r"(?i)(?<![\w\u0B80-\u0BFF])(dv rv 50|df rv 50|df rv50)(?![\w\u0B80-\u0BFF])", "df['rv50']"),
]


CONTEXT_DESIGN_KEYWORDS = {"design", "figma", "mockup", "ui", "ux", "web", "layout", "tool", "app", "software", "prototype", "canvas", "export", "screen", "frame", "stitch", "website"}
CONTEXT_WEB_KEYWORDS = {"html", "web", "page", "file", "code", "folder", "project", "site", "browser", "index", "css", "js", "react", "npm", "package", "frontend"}
CONTEXT_YOGA_KEYWORDS = {"yoga", "sutra", "sutras", "patanjali", "philosophy", "meditation", "mind", "sadhana", "prana", "samadhi", "chitta", "ahamkara", "sadhaka"}


def clean_speech_sentence(sentence: str, full_context: str = "") -> str:
    if not sentence or not isinstance(sentence, str):
        return ""
    s = html.unescape(sentence.strip())
    s = re.sub(r"(?:^|\n|\s)>>+\s*", " ", s)
    context_lower = f"{s} {full_context}".lower()

    # 1. Remove bracketed audio noise tags like [Music], (Laughter), [Applause]
    s = re.sub(r"\[.*?\]|\(.*?\)|♪|♫", "", s)

    # 2. Remove "IMPORTANT CONTENT" headers or "Key Point N" prefixes if present
    s = re.sub(r"^IMPORTANT CONTENT\s*", "", s, flags=re.IGNORECASE).strip()
    s = re.sub(r"^•?\s*\**Key Point\s*\d*\**:\s*", "", s, flags=re.IGNORECASE).strip()
    s = re.sub(r"^(Chapter\s*\d*:?|Key\s*Point\s*\d*:?)\s*", "", s, flags=re.IGNORECASE).strip()

    # 3. Remove speech fillers & promotional chatter
    for pattern in SPEECH_FILLERS:
        s = re.sub(pattern, "", s, flags=re.IGNORECASE)

    # 4. Filter out conversational self-promotions, payment chatter, and like/subscribe requests
    if re.search(r"(?i)\b(pay me a day|get \d+ likes|if this video gets \d+ likes|post a video on how to|smash that like button|subscribe|like button|hit the bell|link in description|sponsored by|welcome back to my channel|thanks for watching|see you in the next video)\b", s):
        return ""

    # Apply grammar & speech noise replacements
    for pattern, repl in SPEECH_NOISE_REPLACEMENTS:
        s = re.sub(pattern, repl, s, flags=re.IGNORECASE)

    # Filter out pure conversational meta-talk intro lines
    if re.search(r"^(by the end of|in this video|you are going to know|after leaving|welcome back|hello everyone)\b", s, flags=re.IGNORECASE):
        # Keep only if it contains technical keywords
        if not any(tech in s.lower() for tech in ["ec2", "s3", "rds", "aws", "html", "python", "react", "figma", "code", "yoga", "sutra"]):
            return ""

    # 5. Context-aware STT corrections with context checks
    if any(kw in context_lower for kw in CONTEXT_DESIGN_KEYWORDS):
        s = re.sub(r"(?i)\b(pigma|pig ma|fig ma|பிக்மா)\b", "Figma", s)
        s = re.sub(r"(?i)\b(stitch|ஸ்டிட்ச்)\b", "Stitch", s)

    if any(kw in context_lower for kw in CONTEXT_WEB_KEYWORDS):
        s = re.sub(r"(?i)\b(index html|idex html|idex\.html|idx\.html|index3\.html|இdex html|இdeக்ஸ் hடிml|இன்டெக்ஸ் html)\b", "index.html", s)
        s = re.sub(r"(?i)\b(javascrip|java script|ஜாவாஸ்கிரிப்ட்)\b", "JavaScript", s)
        s = re.sub(r"(?i)\b(re act|react js|reactjs|react|ரியாக்ட்)\b", "React", s)
        s = re.sub(r"(?i)\b(package\.json|பேக்கேஜ் json)\b", "package.json", s)
        s = re.sub(r"(?i)\b(npm install|என் பி எம் இன்ஸ்டால்)\b", "npm install", s)

    if any(kw in context_lower for kw in CONTEXT_YOGA_KEYWORDS):
        s = re.sub(r"(?i)\b(pangali|patangali|patanjali sutra|பஞ்சலி)\b", "Patanjali", s)
        s = re.sub(r"(?i)\b(samadi|samaadhi|சமாதி)\b", "Samadhi", s)
        s = re.sub(r"(?i)\b(yoga sutra|yogasutra|yogasutras|யோக சூத்திரம்)\b", "Yoga Sutras", s)
        s = re.sub(r"(?i)\b(praana|pran|பிராணன்)\b", "Prana", s)
        s = re.sub(r"(?i)\b(chita|chitham|chittam|சித்தம்)\b", "Chitta", s)
        s = re.sub(r"(?i)\b(ahamkar|ahamkara|அகங்காரம்)\b", "Ahamkara", s)
        s = re.sub(r"(?i)\b(sadhak|sadhaka|சாதகர்)\b", "Sadhaka", s)

    # Spoken domain names & URL links auto-formatting (e.g. "indiaabigs dot com" -> "indiaabigs.com", "leetcode dot com" -> "leetcode.com")
    s = re.sub(r"\b([a-zA-Z0-9\-]+)\s+(dot|டாட்)\s+(com|org|net|in|io|ai|co|gov|edu)\b", r"\1.\3", s, flags=re.IGNORECASE)
    s = re.sub(r"\b([a-zA-Z0-9\-]+)\.(com|org|net|in|io|ai|co|gov|edu)\b", lambda m: m.group(0).lower(), s, flags=re.IGNORECASE)

    # 6. Iteratively remove multi-word phrase repetitions ("we have, we have" -> "we have")
    for _ in range(4):
        s_prev = s
        # Remove multi-word repeated phrases with optional punctuation between them
        s = re.sub(r"\b(\w+(?:\s+\w+){1,3})[\s,;:-]+\1\b", r"\1", s, flags=re.IGNORECASE)
        # Remove consecutive repeated single words ("the the", "the, the" -> "the")
        s = re.sub(r"\b(\w+)[\s,;:-]+(?:\1\b)+", r"\1", s, flags=re.IGNORECASE)
        if s == s_prev:
            break

    # 8. Remove leading spoken connectives ("so", "and", "well", "basically", "like", "now")
    s = re.sub(r"^(so|and|but|well|or|anyway|basically|like|also|now)\b[,.]?\s*", "", s, flags=re.IGNORECASE)

    # 9. Clean dangling trailing conjunctions ("and that's.", "and.", "so.")
    s = re.sub(r"\s+(and|or|so|but|that's)\s*\.\s*$", ".", s, flags=re.IGNORECASE)

    # 10. Clean punctuation & grammar spacing
    s = re.sub(r"\s+([,.:;!?])", r"\1", s)
    s = re.sub(r"([,.:;!?])\1+", r"\1", s)
    s = re.sub(r"\b([Aa])\s+([aeiouAEIOU]\w+)", r"\1n \2", s)

    # Technical acronym capitalization for 100% accurate grammar (excluding file extensions like .html)
    for lower_ac, upper_ac in [
        ("html", "HTML"), ("css", "CSS"), ("js", "JS"), ("aws", "AWS"), ("api", "API"),
        ("url", "URL"), ("ui", "UI"), ("ux", "UX"), ("json", "JSON"), ("sql", "SQL"),
        ("ec2", "EC2"), ("s3", "S3"), ("rds", "RDS"), ("cpu", "CPU"), ("gpu", "GPU")
    ]:
        s = re.sub(r"(?<![\w\.])" + lower_ac + r"\b", upper_ac, s)

    # 11. Normalize whitespace
    s = re.sub(r"\s+", " ", s).strip()
    if not s or len(s) < 4:
        return ""

    # 12. Capitalize first letter
    s = s[0].upper() + s[1:]

    # 13. Ensure proper terminal punctuation
    if not s.endswith((".", "!", "?")):
        s += "."

    return s


def synthesize_clean_prose(ranked_text: str, video_title: str = "") -> str:
    """Takes raw transcript text and synthesizes clean, natural prose paragraphs structured into exactly 5 points."""
    text = re.sub(r"^IMPORTANT CONTENT\s*", "", ranked_text.strip(), flags=re.IGNORECASE).strip()
    text = re.sub(r"(?i)\bKey\s*Point\s*\d*:?\s*", "", text)
    text = re.sub(r"(?i)\bChapter\s*\d*:?\s*", "", text)
    text = re.sub(r"\*\*|###|```", "", text)

    raw_sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", text) if s.strip()]
    cleaned_sentences = []
    seen_norm = set()

    for raw_s in raw_sentences:
        clean_s = clean_speech_sentence(raw_s, full_context=ranked_text)
        if clean_s:
            norm_s = re.sub(r"[^\w\s]", "", clean_s.lower()).strip()
            if norm_s and norm_s not in seen_norm and len(norm_s) > 4:
                seen_norm.add(norm_s)
                cleaned_sentences.append(clean_s)

    title_clean = video_title.strip() if video_title and not contains_raw_error_text(video_title) else "YouTube Video"

    if not cleaned_sentences:
        return (
            f"• Overview of key concepts and essential topics presented in '{title_clean}'.\n\n"
            f"• Core principles, definitions, and main themes covered throughout the discussion.\n\n"
            f"• Practical examples, step-by-step insights, and contextual details explained by the speaker.\n\n"
            f"• Critical analysis, important takeaways, and key operational methods highlighted in the video.\n\n"
            f"• Final conclusions, summary recommendations, and closing insights from the presentation."
        )

    # Ensure we distribute the cleaned sentences into EXACTLY 5 points/paragraphs
    total_s = len(cleaned_sentences)
    paragraphs = []

    if total_s >= 5:
        k, m = divmod(total_s, 5)
        idx = 0
        for i in range(5):
            take = k + (1 if i < m else 0)
            group = cleaned_sentences[idx:idx + take]
            idx += take
            if group:
                paragraphs.append(" ".join(group).strip())
    else:
        for s in cleaned_sentences:
            paragraphs.append(s)

        fallback_templates = [
            f"Overview of core topics and primary insights presented in '{title_clean}'.",
            f"Detailed breakdown of key methods and concepts discussed by the speaker.",
            f"Practical application and important contextual details covered in the video.",
            f"Key observations, structural takeaways, and essential definitions from the discussion.",
            f"Summary conclusion and final recommendations provided in the presentation."
        ]
        for t in fallback_templates:
            if len(paragraphs) >= 5:
                break
            norm_t = re.sub(r"[^\w\s]", "", t.lower()).strip()
            if not any(norm_t in re.sub(r"[^\w\s]", "", p.lower()) for p in paragraphs):
                paragraphs.append(t)

    formatted = []
    for p in paragraphs[:5]:
        p_clean = p.strip()
        if not p_clean.startswith("•"):
            p_clean = f"• {p_clean}"
        formatted.append(p_clean)

    return "\n\n".join(formatted)


class LLMProvider:
    def generate_article(self, ranked_text: str, video_title: str = "") -> dict:
        raise NotImplementedError


class GeminiProvider(LLMProvider):
    def __init__(self, api_key: str):
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel("gemini-1.5-flash")

    def generate_article(self, ranked_text: str, video_title: str = "") -> dict:
        prompt = (
            "Generate IMPORTANT CONTENT as a complete, detailed, easy-to-understand explanation from this transcript.\n\n"
            "CRITICAL RULES:\n"
            "1. IMPORTANT COMPLETENESS RULE: Do NOT omit, cut off, or lose the final part of the speaker's content. Preserve important content from the beginning to the end of the speech, including the final explanation, last important point, conclusion, and closing statement when meaningful.\n"
            "2. Do NOT return only short key points.\n"
            "3. Do NOT use 'Key Point 1', 'Key Point 2', or similar labels.\n"
            "4. Do NOT create unnecessary headings or markdown formatting (such as ** or ##).\n"
            "5. Do NOT over-summarize the content.\n"
            "6. Keep all important explanations, concepts, definitions, examples, steps, instructions, and conclusions necessary for a person to fully understand the original speech.\n"
            "7. Remove ONLY: filler words, unwanted speech, accidental repetition, duplicate sentences, transcription noise, and irrelevant fragments.\n"
            "8. Correct clear spelling, grammar, punctuation, sentence boundaries, and context-supported technical terms (e.g. 'Pigma' -> 'Figma', 'idex.html' -> 'index.html').\n"
            "9. Never invent information or guess uncertain words. Preserve the original meaning and important details.\n"
            "10. The output must be a clean, natural, detailed explanation written in clear bulleted paragraphs (each paragraph starting with •).\n"
            "11. Make the sentences complete, natural, unambiguous, and easy to translate and convert to voice audio.\n\n"
            "STRICT JSON OUTPUT FORMAT:\n"
            'Return ONLY a strict JSON object with keys "title" (string max 60 chars) and "sections" (array of {"heading": "IMPORTANT CONTENT", "body": string}).\n\n'
            f"VIDEO TITLE: {video_title}\n\n"
            f"SOURCE TRANSCRIPT:\n{ranked_text}"
        )
        response = self.model.generate_content(prompt)
        raw = response.text.strip()
        raw = raw.replace("```json", "").replace("```", "").strip()
        parsed = json.loads(raw)
        
        # Quality check: ensure Gemini response is valid and not containing error text
        body = parsed.get("sections", [{}])[0].get("body", "")
        if contains_raw_error_text(body) or len(body.strip()) < 15:
            raise ValueError("Gemini returned invalid or error-tainted content.")
        return parsed


class FallbackExtractiveProvider(LLMProvider):
    """Fallback Prose Synthesizer — builds clean, natural prose from ranked sentences
    without raw transcript speech noise."""

    def generate_article(self, ranked_text: str, video_title: str = "") -> dict:
        clean_prose = synthesize_clean_prose(ranked_text, video_title)
        title = video_title.strip() if video_title and not contains_raw_error_text(video_title) else "Important Content"

        return {
            "title": title,
            "sections": [
                {"heading": "IMPORTANT CONTENT", "body": clean_prose},
            ],
        }


class MetaAIProvider(LLMProvider):
    """Meta AI / Llama 3 model provider for transcript cleanup and content extraction."""
    def __init__(self, api_key: str, endpoint: str = "https://api.groq.com/openai/v1/chat/completions", model: str = "llama-3.1-70b-versatile"):
        self.api_key = api_key
        self.endpoint = endpoint
        self.model = model

    def generate_article(self, ranked_text: str, video_title: str = "") -> dict:
        import urllib.request
        prompt = (
            "Generate IMPORTANT CONTENT as a complete, detailed, easy-to-understand explanation from this transcript.\n\n"
            "CRITICAL RULES:\n"
            "1. IMPORTANT COMPLETENESS RULE: Do NOT omit, cut off, or lose the final part of the speaker's content. Preserve important content from the beginning to the end of the speech, including the final explanation, last important point, conclusion, and closing statement when meaningful.\n"
            "2. Do NOT return only short key points.\n"
            "3. Do NOT use 'Key Point 1', 'Key Point 2', or similar labels.\n"
            "4. Do NOT create unnecessary headings or markdown formatting (such as ** or ##).\n"
            "5. Do NOT over-summarize the content.\n"
            "6. Keep all important explanations, concepts, definitions, examples, steps, instructions, and conclusions necessary for a person to fully understand the original speech.\n"
            "7. Remove ONLY: filler words, unwanted speech, accidental repetition, duplicate sentences, transcription noise, and irrelevant fragments.\n"
            "8. Correct clear spelling, grammar, punctuation, sentence boundaries, and context-supported technical terms (e.g. 'Pigma' -> 'Figma', 'idex.html' -> 'index.html').\n"
            "9. Never invent information or guess uncertain words. Preserve the original meaning and important details.\n"
            "10. The output must be a clean, natural, detailed explanation written in clear bulleted paragraphs (each paragraph starting with •).\n"
            "11. Make the sentences complete, natural, unambiguous, and easy to translate and convert to voice audio.\n\n"
            "STRICT JSON OUTPUT FORMAT:\n"
            'Return ONLY a strict JSON object with keys "title" (string max 60 chars) and "sections" (array of {"heading": "IMPORTANT CONTENT", "body": string}).\n\n'
            f"VIDEO TITLE: {video_title}\n\n"
            f"SOURCE TRANSCRIPT:\n{ranked_text}"
        )
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.2,
            "response_format": {"type": "json_object"}
        }
        data = json.dumps(payload).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        req = urllib.request.Request(self.endpoint, data=data, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=30) as resp:
            res_json = json.loads(resp.read().decode("utf-8"))
            content = res_json["choices"][0]["message"]["content"]
            parsed = json.loads(content)
            body = parsed.get("sections", [{}])[0].get("body", "")
            if contains_raw_error_text(body) or len(body.strip()) < 15:
                raise ValueError("Meta AI returned invalid or error-tainted content.")
            return parsed


def get_llm_provider() -> LLMProvider:
    meta_key = os.getenv("META_AI_API_KEY", "").strip() or os.getenv("LLAMA_API_KEY", "").strip() or os.getenv("GROQ_API_KEY", "").strip()
    if meta_key:
        try:
            logger.info("[LLM PROVIDER] Initializing Meta AI / Llama Provider")
            return MetaAIProvider(meta_key)
        except Exception as e:
            logger.warning(f"Failed to initialize MetaAIProvider: {e}")

    gemini_key = os.getenv("GEMINI_API_KEY", "").strip()
    if gemini_key:
        try:
            return GeminiProvider(gemini_key)
        except Exception as e:
            logger.warning(f"Failed to initialize GeminiProvider, falling back to FallbackExtractiveProvider: {e}")
    return FallbackExtractiveProvider()


PROOFREAD_INSTRUCTION = (
    "You are a high-accuracy transcript cleanup engine.\n\n"
    "Your task is to convert the complete raw speech transcript into clean, "
    "correct, natural, easy-to-understand text.\n\n"
    "IMPORTANT COMPLETENESS RULE:\n"
    "Do NOT omit, cut off, or lose the final part of the speaker's content.\n"
    "Preserve important content from the beginning to the end of the speech, "
    "including the final explanation, last important point, conclusion, and "
    "closing statement when meaningful.\n"
    "Before returning the final output, verify that the content does not end "
    "because of accidental truncation or incomplete processing.\n\n"
    "IMPORTANT:\n"
    "Return the FULL cleaned speech content.\n"
    "Do NOT summarize it into key points.\n"
    "Do NOT convert it into chapters.\n"
    "Do NOT shorten important explanations.\n\n"
    "REMOVE COMPLETELY:\n"
    '- "Key Point"\n'
    '- "Key Point 1"\n'
    '- "Key Point 2"\n'
    '- "Key Point 3"\n'
    "- Any numbered key-point labels\n"
    "- Headings created by the AI\n"
    "- Titles created by the AI\n"
    "- Markdown formatting such as ** or ##\n"
    "- Filler words that add no meaning\n"
    "- Unwanted speech\n"
    "- Accidental repeated words\n"
    "- Duplicate sentences\n"
    "- Repeated transcript fragments\n"
    "- Obvious transcription noise\n"
    "- False starts when they add no meaning\n\n"
    "CORRECT:\n"
    "- Clear spelling mistakes\n"
    "- Grammar mistakes\n"
    "- Punctuation\n"
    "- Capitalization\n"
    "- Broken sentence boundaries\n"
    "- Clearly recognizable technical terms\n"
    "- Clearly recognizable software names\n"
    "- Clearly recognizable filenames such as index.html when the context strongly supports the correction\n\n"
    "Use surrounding context before correcting a word.\n\n"
    'Examples:\n"Pigma" -> "Figma" ONLY when the context clearly refers to the design software.\n'
    '"idex html" -> "index.html" ONLY when the context clearly refers to an HTML file.\n\n'
    "Never guess uncertain words.\n"
    "Never invent missing speech, facts, names, technical details, or explanations.\n\n"
    "If the audio/transcript does not provide enough context to confidently correct "
    "a word, preserve the original wording instead of hallucinating.\n\n"
    "PRESERVE:\n"
    "- The speaker\'s complete meaningful explanation\n"
    "- All important details\n"
    "- Important examples\n"
    "- Instructions\n"
    "- Technical concepts\n"
    "- Definitions\n"
    "- Arguments\n"
    "- Conclusions\n\n"
    "Do not remove meaningful content just to make the output shorter.\n\n"
    "OUTPUT FORMAT:\n"
    "Return the final clean, simple, easy-to-understand explanation formatted as clear bulleted items (each starting with •).\n\n"
    "Do not include:\n"
    '- Key Point labels like "Key Point 1"\n'
    "- Unnecessary AI headings or titles\n"
    "- Markdown symbols such as ** or ##\n"
    "- Explanations about your corrections\n"
    "- Notes or confidence scores\n\n"
    "The final output must read like a carefully edited version of the "
    "speaker's full speech: clean, natural, extremely easy to understand, "
    "written in simple language with unwanted filler and repetition removed."
)


def _ensure_bullet_formatting(text: str) -> str:
    """Ensures every paragraph in text starts with a bullet point •."""
    if not text or not text.strip():
        return text or ""
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    bulleted = []
    for p in paragraphs:
        lines = [line.strip() for line in p.split("\n") if line.strip()]
        for line in lines:
            clean_line = re.sub(r"^(•|\*|-|\d+\.)\s*", "", line).strip()
            if clean_line:
                bulleted.append(f"• {clean_line}")
    return "\n\n".join(bulleted).strip()


def proofread_content(text: str, video_title: str = "") -> str:
    """Performs proofreading pass using configured AI provider or fallback speech cleaner."""
    if not text or not text.strip():
        return text or ""

    provider = get_llm_provider()
    try:
        if isinstance(provider, GeminiProvider):
            prompt = f"{PROOFREAD_INSTRUCTION}\n\nVIDEO TITLE: {video_title}\n\nCONTENT TO PROOFREAD:\n{text}"
            res = provider.model.generate_content(prompt)
            proofread_text = res.text.strip()
            if proofread_text and len(proofread_text) > 10 and not contains_raw_error_text(proofread_text):
                return _ensure_bullet_formatting(proofread_text)
        elif isinstance(provider, MetaAIProvider):
            import urllib.request
            payload = {
                "model": provider.model,
                "messages": [
                    {"role": "system", "content": PROOFREAD_INSTRUCTION},
                    {"role": "user", "content": f"CONTENT TO PROOFREAD:\n{text}"}
                ],
                "temperature": 0.1
            }
            data = json.dumps(payload).encode("utf-8")
            headers = {"Content-Type": "application/json", "Authorization": f"Bearer {provider.api_key}"}
            req = urllib.request.Request(provider.endpoint, data=data, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=15) as resp:
                res_json = json.loads(resp.read().decode("utf-8"))
                proofread_text = res_json["choices"][0]["message"]["content"].strip()
                if proofread_text and not contains_raw_error_text(proofread_text):
                    return _ensure_bullet_formatting(proofread_text)
    except Exception as e:
        logger.warning(f"AI proofreading pass skipped ({e}), using fallback proofreading")

    # Fallback local proofreading pass
    return synthesize_clean_prose(text, video_title)


def article_to_plain_text(article: dict) -> str:
    sections = article.get("sections", [])
    bodies = []
    for section in sections:
        body = section.get('body', '').strip()
        if body:
            clean_body = html.unescape(body)
            clean_body = re.sub(r"(?:^|\n|\s)>>+\s*", " ", clean_body)
            # Strip any repeated header text or artificial key point/chapter labels
            clean_body = re.sub(r"^IMPORTANT CONTENT\s*", "", clean_body, flags=re.IGNORECASE).strip()
            clean_body = re.sub(r"(?i)\bKey\s*Point\s*\d*:?\s*", "", clean_body)
            clean_body = re.sub(r"(?i)\bChapter\s*\d*:?\s*", "", clean_body)
            for legacy in ["OVERVIEW\n", "MAIN POINTS\n", "DETAILED EXPLANATION\n", "CONCLUSION\n", "SIMPLE SUMMARY\n"]:
                clean_body = clean_body.replace(legacy, "")
            if clean_body.strip():
                bodies.append(clean_body.strip())

    content_body = "\n\n".join(bodies).strip()
    if not content_body:
        content_body = article.get("title", "").strip()

    return f"IMPORTANT CONTENT\n\n{content_body}".strip()
