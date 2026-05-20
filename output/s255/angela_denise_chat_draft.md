Hi Denise + Angela —

Quick heads up: S255 (AP system hardening) added two **filter views** on AP Master Payment Plan tab that mirror Angela's "Scheduled for Online Transfer - Due" and "Scheduled for Release Check - Due" tabs from your Project: 2-Week Payment Plan sheet.

These are LIVE filter views directly on Payment Plan — no data duplication, no manual refresh. They filter on col I (STATUS — the mapped AP-vocab version, which the script maintains from your raw STATUS):

- **Scheduled for Online Transfer - Due** → rows where STATUS = "FOR ONLINE PAYMENT"
- **Scheduled for Release Check - Due** → rows where STATUS = "CHECK READY" OR "CHECK RELEASED"

To use: open the AP Master sheet → Payment Plan tab → click the filter funnel icon (top-left) → "Filter views" → pick the view you want.

Whenever you're ready to transition off your standalone sheet into AP Master, these views are waiting. Sam will toggle the mirror flag when you say go.

— S255 closeout
