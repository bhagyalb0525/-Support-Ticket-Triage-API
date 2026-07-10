import os
import re
import json
import logging
from collections import Counter
from typing import List
import google.generativeai as genai
from app.models.ticket import TicketExtraction

logger = logging.getLogger(__name__)

# Small, general-purpose word lists used only by the offline heuristic path.
# These are intentionally simple (no external NLP deps) so the app can run
# fully offline with zero setup.
_POSITIVE_WORDS = {
    "thanks", "thank", "great", "good", "awesome", "excellent", "happy",
    "pleased", "appreciate", "appreciated", "resolved", "working", "perfect",
    "smooth", "helpful", "love", "nice",
}

_NEGATIVE_WORDS = {
    "urgent", "asap", "broken", "error", "fail", "failed", "failing", "down",
    "crash", "crashed", "crashing", "issue", "issues", "problem", "problems",
    "angry", "frustrated", "unacceptable", "terrible", "worst", "bad",
    "delay", "delayed", "blocked", "blocker", "critical", "not working",
    "cannot", "can't", "unable", "disappointed", "furious", "complaint",
}

_STOPWORDS = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "to", "of", "and", "or", "but", "in", "on", "at", "for", "with",
    "this", "that", "these", "those", "it", "its", "i", "we", "you",
    "my", "our", "your", "please", "hi", "hello", "hey", "team", "regards",
    "not", "no", "do", "does", "did", "have", "has", "had", "as", "so",
    "from", "will", "would", "can", "could", "should", "just", "get",
    "getting", "im", "i'm", "us", "me", "there", "here", "when", "what",
}

_WORD_RE = re.compile(r"[a-zA-Z]+")


class GeminiAPIKeyMissingError(Exception):
    """Exception raised when the Gemini API key is missing from environment variables."""
    pass


class GeminiService:
    def __init__(self):
        self.api_key = os.environ.get("GEMINI_API_KEY")
        # Check if the key is unset or set to the placeholder value from .env
        if not self.api_key or "your_actual_gemini_api_key_here" in self.api_key:
            self.has_api_key = False
            logger.warning(
                "GeminiService: GEMINI_API_KEY is not configured. "
                "Falling back to offline heuristic extraction."
            )
        else:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel("gemini-3.1-flash-lite")
            self.has_api_key = True
            logger.info("GeminiService: Successfully configured with GEMINI_API_KEY environment variable.")

    def extract_ticket_info(self, ticket_text: str, categories: List[str]) -> TicketExtraction:
        """
        Extracts structured ticket metadata.

        Uses the live Gemini API when a key is configured. If no key is
        configured, or the live call fails for any reason (network issue,
        rate limit, invalid key, etc.), falls back to a deterministic
        offline heuristic so the API always returns a usable result.
        """
        if not self.has_api_key:
            logger.info("GeminiService: No API key configured, using offline heuristic extraction.")
            return self._extract_offline_heuristic(ticket_text, categories)

        try:
            return self._extract_live(ticket_text, categories)
        except Exception as e:
            logger.error(
                f"GeminiService: Live API call failed ({str(e)}). "
                f"Falling back to offline heuristic extraction."
            )
            return self._extract_offline_heuristic(ticket_text, categories)

    def _extract_live(self, ticket_text: str, categories: List[str]) -> TicketExtraction:
        """Calls the real Gemini API using Pydantic structured output."""
        prompt = (
            f"You are an AI support ticket classification agent.\n"
            f"Read the support ticket text below and extract structured metadata.\n\n"
            f"Support Ticket:\n"
            f"\"\"\"\n{ticket_text}\n\"\"\"\n\n"
            f"Allowed categories list (select suggested_department ONLY from these):\n"
            f"{categories}\n\n"
            f"Instructions:\n"
            f"1. Extract 'primary_topic' summarizing the main issue in 3-6 words.\n"
            f"2. Extract 'sentiment' (must be exactly 'positive', 'neutral', or 'negative').\n"
            f"3. Extract 'detected_keywords' (a list of 2 to 5 relevant technical/functional terms or phrases).\n"
            f"4. Assign 'suggested_department' which must match one of the allowed categories listed above. "
            f"If no category fits perfectly, select the closest one. Do not output any category not in the allowed list."
        )

        response = self.model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json",
                response_schema=TicketExtraction,
                temperature=0.1
            )
        )

        parsed_json = json.loads(response.text)
        return TicketExtraction(**parsed_json)

    def _extract_offline_heuristic(self, ticket_text: str, categories: List[str]) -> TicketExtraction:
        """
        Deterministic, dependency-free fallback used when the Gemini API is
        unavailable. Not as accurate as the LLM, but keeps the service
        functional offline (e.g. during local dev, demos, or API outages).
        """
        words = _WORD_RE.findall(ticket_text.lower())
        meaningful_words = [w for w in words if w not in _STOPWORDS and len(w) > 2]

        # --- sentiment ---
        pos_hits = sum(1 for w in words if w in _POSITIVE_WORDS)
        neg_hits = sum(1 for w in words if w in _NEGATIVE_WORDS)
        if neg_hits > pos_hits:
            sentiment = "negative"
        elif pos_hits > neg_hits:
            sentiment = "positive"
        else:
            sentiment = "neutral"

        # --- detected_keywords: most frequent meaningful words, 2-5 items ---
        freq = Counter(meaningful_words)
        top_keywords = [w for w, _ in freq.most_common(5)]
        if len(top_keywords) < 2:
            # Not enough distinct meaningful words; pad with generic fallback
            # so the field still satisfies "2 to 5 relevant terms".
            top_keywords += ["general_inquiry"] * (2 - len(top_keywords))

        # --- primary_topic: short summary from the first sentence ---
        first_sentence = re.split(r"(?<=[.!?])\s+", ticket_text.strip())[0]
        topic_words = first_sentence.split()
        primary_topic = " ".join(topic_words[:6]).strip(".,!? ") or "General support request"

        # --- suggested_department: best word-overlap match against categories ---
        text_word_set = set(meaningful_words)
        best_category = categories[0] if categories else "general"
        best_score = 0
        for category in categories:
            category_words = set(_WORD_RE.findall(category.lower()))
            overlap = len(category_words & text_word_set)
            if overlap > best_score:
                best_score = overlap
                best_category = category

        return TicketExtraction(
            primary_topic=primary_topic,
            sentiment=sentiment,
            detected_keywords=top_keywords,
            suggested_department=best_category,
        )