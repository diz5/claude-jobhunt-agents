# Referral-target companies (TEMPLATE — copy to referral-companies.md, gitignored)

# Companies you have a friend/contact who can refer you. The linkedin-sourcing skill
# runs a SEPARATE, bounded pass for these: one LinkedIn guest search per company
# (senior roles, your metros), analyzes new fits, and files the >=6 ones with their
# post date into a review queue so you can decide whether to ask for a referral.
#
# Format: one company per line.  "Name | <linkedin_company_id> | <optional note>"
#   - Name              — matched (whole-word) against the job's company to flag it.
#   - linkedin_company_id — LinkedIn's numeric company id, used for the guest search
#                           filter f_C=<id> (precise). Leave blank to fall back to a
#                           keyword search. Find it in the company's /jobs/ page URL.
# Lines starting with '#' and blank lines are ignored.

Acme Corp | 1234567 | college friend on the platform team
Globex | | contact in recruiting (no company id yet — keyword fallback)
