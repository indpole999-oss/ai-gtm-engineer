"""Conservative, versioned rules: no external model and no side effects."""
import re
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

Category = Literal["positive", "negative", "objection", "out_of_office", "wrong_person", "question", "meeting_intent", "unsubscribe", "other"]
VERSION = "inbox-rules-v1"
ACTIONS = {"positive": "review_and_draft_reply", "negative": "review_and_close", "objection": "review_objection",
    "out_of_office": "review_return_timing_keep_paused", "wrong_person": "review_contact_no_replacement_assumed",
    "question": "review_question_and_draft", "meeting_intent": "review_meeting_intent_no_booking",
    "unsubscribe": "suppress_no_reply", "other": "manual_review"}


class Classification(BaseModel):
    model_config = ConfigDict(extra="forbid")
    category: Category
    confidence: float | None = Field(default=None, ge=0, le=1)
    reason: str = Field(min_length=1, max_length=3000)
    evidence: list[str] = Field(max_length=10)
    classifier_version: str = VERSION
    recommended_action: str
    requires_review: bool


def authored_text(body):
    lines = []
    for line in body.splitlines():
        if re.match(r"\s*(on .{1,200}wrote:|-{2,}\s*(original|forwarded) message|from:\s|--\s*$)", line, re.I):
            break
        if not line.lstrip().startswith(">"):
            lines.append(line)
    return "\n".join(lines).strip()[:20000]


def classify(subject, body, auto_submitted="no"):
    text = authored_text(body).casefold()
    # Do not scan quoted outreach footers or subject text for opt-out intent.
    negated = re.search(r"\b(?:do not|don't|never|not)\s+unsubscribe\b", text)
    if negated:
        return result("other", [negated.group()], "Negated opt-out wording requires review", None, True)
    unsubscribe = re.search(r"\b(unsubscribe me|remove me (?:from|off)|stop (?:emailing|contacting|messaging) me|do not (?:email|contact) me|don't (?:email|contact) me|i (?:want|wish|would like) to unsubscribe)\b|^\s*(?:please\s+)?unsubscribe[.!]?\s*$", text)
    if unsubscribe:
        return result("unsubscribe", [unsubscribe.group()], "Explicit opt-out request in authored reply", .99, False)
    ooo = re.search(r"\b(out of (?:the )?office|on (?:annual )?leave|on vacation|away from (?:the )?office|automatic reply)\b", subject.casefold() + "\n" + text)
    if ooo or auto_submitted == "auto-replied":
        return result("out_of_office", [ooo.group() if ooo else "Auto-Submitted: auto-replied"], "Automatic absence signal; no positive engagement or return date inferred", .95, True)
    if auto_submitted == "auto-generated":
        return result("other", ["Auto-Submitted: auto-generated"], "Machine-generated event; no human reply assumed", None, True)
    patterns = {
        "wrong_person": r"\b(wrong person|not (?:the )?right (?:person|contact)|not responsible for|no longer (?:work|working) (?:at|for))\b",
        "negative": r"\b(not interested|no thanks|no thank you|not a fit|please close this)\b",
        "objection": r"\b(too expensive|no budget|already (?:use|using|have)|concerned about|not (?:a )?priority|price is (?:too )?high)\b",
        "meeting_intent": r"\b(schedule (?:a |the )?(?:call|meeting|demo)|book (?:a |the )?(?:call|meeting|demo)|let'?s (?:meet|talk|schedule)|available (?:for|on) a? ?(?:call|meeting)|send (?:me )?(?:your )?(?:calendar|availability))\b",
        "positive": r"\b(interested|sounds good|sounds interesting|happy to (?:learn|discuss)|tell me more|yes please)\b",
    }
    hits = {category: match.group() for category, pattern in patterns.items() if (match := re.search(pattern, text))}
    if "negative" in hits:
        hits.pop("positive", None)  # "not interested" is not positive.
    if "meeting_intent" in hits and set(hits) <= {"meeting_intent", "positive"}:
        return result("meeting_intent", list(hits.values()), "Explicit discussion/meeting request; intent only", .9, True)
    if len(hits) == 1:
        category = next(iter(hits))
        return result(category, list(hits.values()), "Matched a clear reply phrase; customer review remains available", .85, True)
    if len(hits) > 1:
        return result("other", list(hits.values()), "Conflicting reply signals require manual review", None, True)
    if "?" in text or re.match(r"^(how|what|when|where|why|can you|could you)\b", text):
        return result("question", [text[:300]], "An explicit question needs a reviewed response", .8, True)
    return result("other", [text[:300]] if text else [], "Insufficient evidence to infer intent", None, True)


def result(category, evidence, reason, confidence, review):
    return Classification(category=category, confidence=confidence, reason=reason, evidence=evidence,
        recommended_action=ACTIONS[category], requires_review=review)
