"""Conservative safety routing and transparent topic analysis."""

import re
from . import semantic
from .topics import list_topics

SENSITIVE = re.compile(
    r"\b(bull(?:y|ied|ies|ying)|harass(?:ed|ment|ing)?|threat(?:en(?:ed|ing)?|s)?|unsafe|abuse(?:d)?|assault(?:ed)?|weapon|suicid\w*|self[ -]?harm|kill myself|hurt myself|end my life|cutting myself|hit me|hitting me|hurt me|hurting me|picked on|picking on me|stalk\w*|blackmail\w*|sexual|molest\w*|want to die|don['’]t want to live|do not want to live|not safe|don['’]t feel safe|do not feel safe|doesn['’]t feel safe|does not feel safe|not feeling safe|scared to go home|personal safety)\b",
    re.IGNORECASE,
)
CONTACT = re.compile(
    r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}|(?:https?://|www\.)\S+|(?<!\w)@\w{2,}|(?:\+?\d[\d ().-]{7,}\d)|\b\d+\s+[A-Za-z ]+\s(?:street|st|road|rd|avenue|ave|drive|dr|lane|ln)\b",
    re.IGNORECASE,
)


def normalized_text(text):
    return " ".join(re.findall(r"\w+", text.casefold()))


def contains_contact(text):
    return bool(CONTACT.search(text))


def analyze_text(text, mode=None):
    if SENSITIVE.search(text):
        return {"topic": None, "route": "private_support", "analysis": {"method": "safety_rules", "confidence": 0.9, "uncertainty": 0.1, "reason": "A personal-safety or bullying phrase triggered conservative private routing. These numbers describe a routing indicator, not a measured probability of detecting danger. Automated rules can miss concerns and are not a safety guarantee."}}
    normalized = normalized_text(text)
    counts = {topic: sum(1 for word in words if re.search(r"\b" + re.escape(word) + r"\b", normalized)) for topic, words in ((t['id'], t['keywords']) for t in list_topics())}
    ranked = sorted(counts, key=counts.get, reverse=True)
    best, second = ranked[:2]
    actual_mode = semantic.effective_mode(mode)
    if counts[best] > 0:
        # Distinct topics with equally strong evidence need the student's clarification.
        if counts[best] == counts[second]:
            return {"topic": None, "route": "clarify", "analysis": {"method": "keyword_rules", "confidence": 0.4, "uncertainty": 0.6, "reason": "More than one topic has equal evidence. Please describe one subject and the help you need."}}
        confidence = min(0.96, 0.78 + counts[best] * 0.06)
        method = "keyword_rules"
        if actual_mode == "semantic":
            scores = semantic.topic_scores(text, "semantic")
            semantic_topic = max(scores, key=scores.get)
            method = "rules_and_semantic"
            if semantic_topic == best:
                confidence = min(0.98, confidence + 0.02)
        route = "school_transition" if best == "school_transition" else "academic"
        return {"topic": best, "route": route, "analysis": {"method": method, "confidence": round(confidence, 3), "uncertainty": round(1-confidence, 3), "reason": f"Recognized evidence for {best.replace('_', ' ')}. {'A cached embedding model was also used.' if actual_mode == 'semantic' else 'Topic classification used explicit keyword rules, not a live AI model.'}"}}
    if actual_mode == "semantic":
        scores = semantic.topic_scores(text, "semantic")
        order = sorted(scores, key=scores.get, reverse=True)
        confidence = scores[order[0]]
        if confidence >= 0.43 and confidence - scores[order[1]] >= 0.055:
            best = order[0]
            return {"topic": best, "route": "school_transition" if best == "school_transition" else "academic", "analysis": {"method": "semantic", "confidence": round(confidence, 3), "uncertainty": round(1-confidence, 3), "reason": "The cached sentence-transformer recognized a topic with sufficient similarity and separation from the next topic."}}
    return {"topic": None, "route": "clarify", "analysis": {"method": "semantic" if actual_mode == "semantic" else "keyword_rules", "confidence": 0.0, "uncertainty": 1.0, "reason": "No topic was recognized confidently. Please name one subject or explain the school-related help you need; no peer matching has been attempted."}}
