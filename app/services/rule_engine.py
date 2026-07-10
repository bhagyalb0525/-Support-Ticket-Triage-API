import re
import logging
from app.models.client import ClientConfig
from app.models.ticket import TicketExtraction, TicketAnalyzeResponse

logger = logging.getLogger(__name__)

_WORD_RE = re.compile(r"[a-zA-Z]+")


class RuleEngine:
    def __init__(self):
        pass

    @staticmethod
    def _best_overlap_match(suggested_dept: str, categories: list) -> tuple:
        """
        Scores each allowed category against the suggested department using
        word-level overlap (Jaccard-style) instead of blind substring checks.
        Returns (best_category_or_None, score).
        """
        suggested_words = set(_WORD_RE.findall(suggested_dept.lower()))
        if not suggested_words:
            return None, 0.0

        best_category = None
        best_score = 0.0
        for category in categories:
            category_words = set(_WORD_RE.findall(category.lower()))
            if not category_words:
                continue
            overlap = suggested_words & category_words
            if not overlap:
                continue
            score = len(overlap) / len(suggested_words | category_words)
            if score > best_score:
                best_score = score
                best_category = category

        return best_category, best_score

    def evaluate(self, extracted: TicketExtraction, config: ClientConfig, ticket_text: str) -> TicketAnalyzeResponse:
        """
        Runs the rule engine logic to determine the final triage metrics and audit reasoning.
        """
        reasoning_steps = []

        # 1. Final Department Resolution
        # Note: ClientConfig's validator already lowercases every entry in
        # config.categories, so there is no "original casing" to preserve.
        suggested_dept = extracted.suggested_department.strip().lower()
        allowed_categories = config.categories  # already lowercased by the model

        final_dept = None
        dept_reason = ""
        department_matched = True

        if suggested_dept in allowed_categories:
            # Exact match
            final_dept = suggested_dept
            dept_reason = (
                f"Suggested department '{extracted.suggested_department}' was validated "
                f"directly against client allowed categories."
            )
        else:
            # Substring match attempt (handles things like "billing" vs "billing issues")
            matched_dept = None
            for category in allowed_categories:
                if category in suggested_dept or suggested_dept in category:
                    matched_dept = category
                    break

            if matched_dept:
                final_dept = matched_dept
                dept_reason = (
                    f"Suggested department '{extracted.suggested_department}' was mapped to "
                    f"closest allowed category '{final_dept}' via substring match."
                )
            else:
                # Word-overlap match attempt (handles paraphrases like
                # "network connectivity" vs "networking", "payments" vs "billing")
                overlap_dept, score = self._best_overlap_match(suggested_dept, allowed_categories)
                if overlap_dept:
                    final_dept = overlap_dept
                    dept_reason = (
                        f"Suggested department '{extracted.suggested_department}' was mapped to "
                        f"closest allowed category '{final_dept}' via keyword overlap "
                        f"(match score {score:.2f})."
                    )
                else:
                    # Truly no signal at all — this is the only case that
                    # should fall back to a default, and we say so explicitly.
                    department_matched = False
                    final_dept = allowed_categories[0]
                    dept_reason = (
                        f"Suggested department '{extracted.suggested_department}' has no match "
                        f"(exact, substring, or keyword overlap) in client allowed categories "
                        f"{allowed_categories}. Defaulted to '{final_dept}' — flagged as unmatched "
                        f"for manual review."
                    )

        reasoning_steps.append(dept_reason)

        # 2. Escalation Flag Determination
        # Check escalation keywords in raw ticket text AND LLM detected keywords
        escalated = False
        matching_escalation_kws = []
        text_lower = ticket_text.lower()

        for kw in config.escalation_keywords:
            kw_lower = kw.lower()
            # Direct check in raw text
            if kw_lower in text_lower:
                escalated = True
                matching_escalation_kws.append(kw)
                continue

            # Check in LLM detected keywords
            for d_kw in extracted.detected_keywords:
                if kw_lower in d_kw.lower():
                    escalated = True
                    matching_escalation_kws.append(kw)
                    break

        # Remove duplicates
        matching_escalation_kws = sorted(list(set(matching_escalation_kws)))

        if escalated:
            esc_reason = f"Ticket escalated because it contains escalation keywords: {matching_escalation_kws}."
        else:
            esc_reason = "No client-defined escalation keywords were detected in the ticket text or keywords."

        reasoning_steps.append(esc_reason)

        # 3. Urgency Determination
        # Urgency is derived from escalation + sentiment
        # Escalated + negative -> critical
        # Escalated + neutral/positive -> high
        # Not escalated + negative -> medium
        # Not escalated + neutral/positive -> low
        urgency = "low"
        if escalated:
            if extracted.sentiment == "negative":
                urgency = "critical"
            else:
                urgency = "high"
        else:
            if extracted.sentiment == "negative":
                urgency = "medium"
            else:
                urgency = "low"

        urgency_reason = (
            f"Urgency set to '{urgency}' based on combination of escalation={escalated} "
            f"and sentiment='{extracted.sentiment}'."
        )
        reasoning_steps.append(urgency_reason)

        # 4. Complexity Heuristic
        # Simple: length < 150 chars AND <= 2 detected keywords
        # Complex: length >= 500 chars OR >= 5 detected keywords
        # Moderate: any other case
        char_count = len(ticket_text)
        keyword_count = len(extracted.detected_keywords)

        if char_count < 150 and keyword_count <= 2:
            complexity = "simple"
            complexity_reason = (
                f"Resolution complexity is 'simple' because the ticket is short ({char_count} chars < 150) "
                f"and mentions few keywords ({keyword_count} <= 2)."
            )
        elif char_count >= 500 or keyword_count >= 5:
            complexity = "complex"
            complexity_reason = (
                f"Resolution complexity is 'complex' because the ticket is either long ({char_count} chars >= 500) "
                f"or details multiple key aspects (keyword count {keyword_count} >= 5)."
            )
        else:
            complexity = "moderate"
            complexity_reason = (
                f"Resolution complexity is 'moderate' (character count: {char_count}, keyword count: {keyword_count})."
            )

        reasoning_steps.append(complexity_reason)

        # 5. SLA Hours Lookup
        sla_hours = config.sla_hours.get(urgency, 24)  # fallback to 24 if somehow missing
        sla_reason = f"SLA resolved to {sla_hours} hours according to urgency level '{urgency}'."
        reasoning_steps.append(sla_reason)

        if not department_matched:
            reasoning_steps.append(
                "NOTE: final_department was defaulted due to no category match — treat with lower confidence."
            )

        # Combine reasoning steps
        combined_reasoning = " | ".join(reasoning_steps)

        return TicketAnalyzeResponse(
            client_id=config.client_id,
            primary_topic=extracted.primary_topic,
            sentiment=extracted.sentiment,
            detected_keywords=extracted.detected_keywords,
            suggested_department=extracted.suggested_department,
            final_department=final_dept,
            escalate=escalated,
            urgency=urgency,
            complexity_estimate=complexity,
            sla_hours=sla_hours,
            reasoning=combined_reasoning
        )