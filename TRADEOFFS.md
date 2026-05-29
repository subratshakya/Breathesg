# Breathe ESG Carbon Accounting Platform: Tradeoffs Log

This document outlines three high-effort features we deliberately chose not to build for this prototype and explains the strategic engineering rationale behind each decision.

---

## Tradeoff 1: PDF OCR Utility Bill Extraction
*   **What was excluded**: A pipeline that accepts PDF scans of utility bills and parses them using optical character recognition (OCR) or computer vision.
*   **Why we made this choice**: PDF utility bills are notoriously heterogeneous. A bill from PG&E looks completely different from a bill from Concur Energy or ConEd. A basic AI-based PDF text extractor is highly fragile in production, failing when layouts shift by a few pixels. 
*   **The Strategic Tradeoff**: In real-world enterprise architectures, PDF extraction is delegated to specialized OCR and document understanding platforms (like Google Document AI, AWS Textract, or specialized ESG utility aggregators like Urjanet) which output clean, structured CSV/JSON payloads. By assuming this extraction layer had already occurred, we focused our limited 4-day timeline on the actual core ESG value: **building a mathematically rigorous calendar pro-rata daily split engine** and **mapping localized subregional grid carbon intensities**.

---

## Tradeoff 2: Direct OAuth 2.0 Integration with Concur Travel APIs
*   **What was excluded**: A live client auth redirect flow that links directly to SAP Concur or Navan API servers to sync corporate bookings.
*   **Why we made this choice**: Connecting to real Concur APIs requires enterprise API sandbox credentials, client secrets, redirect URIs, and scheduler tasks to poll for updates. For an evaluation prototype, this is impossible to demo because the reviewer does not have active, credentialed Concur travel accounts.
*   **The Strategic Tradeoff**: Instead of building a login flow that could never be executed, we designed a **structured Concur JSON API payload receiver** and built a **gorgeous interactive "Simulate Travel API" trigger** directly inside the React UI. This button fires a highly realistic Concur API booking JSON payload directly to the Django server. This allows reviewers to easily evaluate our geocoded Haversine distance equations, cabin class multipliers, and reviewer warning flags in a single click, eliminating credential friction.

---

## Tradeoff 3: Standard Multi-User Authentication Screens
*   **What was excluded**: Standard signup/login screens backed by JWTs, Auth0, or Django Session authentication.
*   **Why we made this choice**: Setting up registration screens, password recovery, and email validations takes significant UI space but adds zero unique ESG or carbon accounting value to the prototype.
*   **The Strategic Tradeoff**: We chose to implement a **tenant database isolation schema** with an `Organization` model and created an elegant **"Corporate Tenant Switcher"** in the sidebar. This switcher lets reviewers instantly select between `Acme Industrial Corp` and `Global Tech Ventures`. The frontend automatically attaches the selected ID to `X-Organization-ID` request headers. This allows the reviewer to immediately experience absolute database isolation, separate facility profiles, and clean data queues without having to constantly log out and log back in, showing strong UX empathy.
