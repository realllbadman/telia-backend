                                                                                                                                                                                                                                                                                                                                                                                    # Telia Backend — Development Log

## Log Format

Each entry must follow this structure:
```
DATE:
CHANGE TYPE: BUG | FIX | IMPROVEMENT | REFACTOR
DESCRIPTION:
CAUSE:
ACTION TAKEN:
STATUS: pending | done
```

Do NOT delete entries. Always append. Keep chronological order.

---

DATE: 2026-04-28
CHANGE TYPE: IMPROVEMENT
DESCRIPTION: Initial system documentation created (system_context.md, dev_log.md)
CAUSE: Project onboarding — no architecture documentation existed
ACTION TAKEN: Read all core backend files and produced system_context.md and dev_log.md
STATUS: done

---

DATE: 2026-04-28
CHANGE TYPE: IMPROVEMENT
DESCRIPTION: Added smart_rewrite_query() — intelligent query pre-processing layer
CAUSE: Need to handle messy, abbreviated, mixed-language, and vague user input before it reaches the pipeline
ACTION TAKEN: Created app/chat/smart_query.py with smart_rewrite_query(text, language) -> List[str]. Existing pipeline (analyze_multimodal_query, service.py, grouping, search) untouched.
STATUS: done

---

DATE: 2026-04-28
CHANGE TYPE: IMPROVEMENT
DESCRIPTION: Updated smart_rewrite_query return type to dict; integrated into /recommend route
CAUSE: Richer return needed — callers require both the list of queries and the joined string separately
ACTION TAKEN: (1) smart_query.py — return changed to {"queries": List[str], "joined": str}; cache type updated. (2) routes.py — added import, /recommend now calls smart_rewrite_query, uses result["joined"] as enriched_message, prints debug output.
STATUS: done

---

DATE: 2026-05-05
CHANGE TYPE: IMPROVEMENT
DESCRIPTION: Replaced structural rewrite prompt with intent extraction prompt in smart_query.py
CAUSE: Previous prompt focused on grammar cleanup; new requirement is exhaustive product intent extraction — no product may be dropped, each must be separated
ACTION TAKEN: (1) Replaced _MISTRAL_REWRITE_PROMPT with intent extraction prompt that injects language hint. (2) Updated _mistral_rewrite with two failsafes: empty-response guard and intent-collapse guard (reverts to original if Mistral reduces split count). (3) max_tokens raised 80→100. No other files modified.
STATUS: done
