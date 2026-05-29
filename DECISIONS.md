# Breathe ESG Carbon Accounting Platform: Decisions & Assumptions Log

This document records the design decisions, assumptions, and resolved ambiguities established during the development of this prototype.

---

## 1. Ambiguities Resolved & Selected Approaches

### SAP Fuel & Procurement Ingestion
*   **The Ambiguity**: SAP exports can take many forms: XML IDocs, flat files, OData services, or BAPI connections. What subset of SAP reality are we handling?
*   **Our Decision**: We decided to support a flat-file **General Ledger CSV export (ACDOCA/BSEG transactional structures)**. Why? CSV files are the universal denominator for corporate accounting. In large organizations, IT teams generate monthly ledger dumps for ESG teams.
*   **German Headers & Account mapping**: We explicitly mapped standard SAP German database columns:
    *   `BUKRS` (Company Code), `BELNR` (Document number), `HKONT` (GL Account), `BUDAT` (Posting Date), `MENGE` (Quantity), `MEINS` (Base Unit), `WERKS` (Plant/Facility code).
    *   Mapped accounts: `521010` (Scope 1 Diesel), `521020` (Scope 1 Natural Gas), `550000` (Scope 3 Steel spend), `550010` (Scope 3 Paper spend). Mapped plant codes to active Facility profiles to dynamically resolve localized emission factors.

### Utility Data & Daily Pro-Rata Split
*   **The Ambiguity**: Utility billing periods rarely match neat calendar months (e.g., a bill spanning Dec 12, 2025 to Jan 11, 2026). How do we report monthly grid carbon footprints?
*   **Our Decision**: We built a **calendar pro-rata daily split engine**. If a bill spans 30 days and overlaps January and February, we divide the consumption by 30 to get daily usage, then allocate the usage proportionally to the days in January and February.
*   **Grid carbon factors**: Maps the plant code to the local facility grid region. E.g., a plant in Slough, UK, is mapped to `Grid:UK` (using DEFRA factors), and Syracuse, NY, is mapped to `eGRID:NYUP` (using EPA subregional grid factors). This is far more realistic than using standard national grid averages, which overstate or understate actual impact.

### Corporate Travel Airport Geocoding
*   **The Ambiguity**: Travel databases like Concur list flights as departure and arrival airport codes (e.g., JFK, LHR) rather than pre-calculated distances.
*   **Our Decision**: We embedded a **geocoding database of major international airports** (latitude/longitude coordinates) inside the Travel parser and implemented a **Haversine Great-Circle distance formula**. If a flight payload lacks a distance value, the processor automatically calculates the flight distance.
*   **Cabin Class Multipliers**: Business and First class flights have 2.9x and 4x higher emission intensities due to physical floor-space allocation, which is standard DEFRA practice. We flag these premium class records to allow analyst review of the high multipliers.

---

## 2. What We Handled vs What We Ignored

### Handled (High-value scope):
1.  **Strict Audit Locks**: Once a record is marked `APPROVED`, it is locked. The backend blocks any manual changes to preserve audit readiness.
2.  **Mandatory Audit Reasons**: If an analyst modifies a draft or flagged record, the backend enforces a mandatory description of *why* (minimum 5 characters).
3.  **Dynamic Calculations**: Modifying an original quantity in the draft view automatically triggers unit conversions and recalculates normalized values and CO2e outputs on the fly.
4.  **Raw Lineage**: Every normalized line maps back to a JSON snapshot of the original raw upload row to prevent provenance gaps.

### Ignored (Prototype boundaries):
1.  **Active PDF OCR Parsing**: Ingesting utility bills as PDF documents. In reality, ESG teams use OCR parsers (like Document AI) to output structured CSV/JSON first. We assume this pipeline has occurred and ingest the portal CSV.
2.  **Continuous Live API syncing**: Pulling travel data directly from Concur endpoints. We emulate the API response using a direct JSON payload post.
3.  **Historical Grid Factor Schedules**: National grid emission factors change annually. We assume a static factor schedule for this prototype's reporting year.

---

## 3. What We Would Ask the PM

If we could jump on a call with the Product Manager, these would be our top 3 questions:
1.  **For Scope 3 Procurement**: Are we reporting steel and paper emissions using mass-based life-cycle values (e.g., tons of steel bought), or spend-based economic emission factors (e.g., carbon per $1,000 spent)? (We designed our backend models to support both, but want to clarify the client's carbon accounting standard.)
2.  **For Auditor retro-active edits**: If an auditor discovers a systemic historical mistake after locking/approving periods, what is the unlocking protocol? Do we allow highly privileged super-users to reopen locked rows, or do we post negative adjustment rows in the active quarter to maintain clean ledger continuity?
3.  **For Facility plant codes**: Do clients have a centralized plant registry API in SAP (like a BAPI query) we can sync with daily, or will facilities be managed manually by ESG analysts on our platform?
