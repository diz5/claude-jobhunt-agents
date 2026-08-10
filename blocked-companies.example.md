# Blocked companies — template. Copy to blocked-companies.md (gitignored) and edit.
# Companies you never want to apply to: the sourcing pipeline auto-drops their
# postings during `seen.py board-dedup`, so they never reach triage or analysis.
# Format: Name | <note/reason>   (case-insensitive WHOLE-WORD match — "Citi" hits
# "Citi Bank" but not "Citizens Bank"; list name variants like Citigroup explicitly)

Example Bank | culture mismatch
Example Corp Two | hiring freeze burned me twice
