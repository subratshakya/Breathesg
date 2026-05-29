# Breathe ESG Carbon Accounting Platform: Data Sources Specification

This document details the real-world database schemas we researched, explains our sample dataset choices, and analyzes what edge cases would break these pipelines in a production deployment.

---

## Source 1: SAP ERP Fuel & Procurement (Flat-File Ledger)

### Real-world format researched:
SAP financial transactional ledgers are stored in database tables like **BSEG** (accounting document segment) or **ACDOCA** (Universal Journal entry table in S/4HANA). Large enterprises export these tables as CSVs or trigger BAPIs/OData services to pull records matching specific G/L Accounts.
*   **Real-world headers**: SAP uses German abbreviations as column identifiers:
    *   `MANDT` (Client tenant), `BUKRS` (Company Code), `BELNR` (Accounting Document Number), `GJAHR` (Fiscal Year), `BUDAT` (Posting Date), `HKONT` (General Ledger Account), `MENGE` (Quantity), `MEINS` (Base Unit of Measure), `WRBTR` (Amount in Transaction Currency), `WERKS` (Plant/Facility Code).

### Sample data choice & Rationale:
Our simulator processes ledger entries that represent diesel, natural gas, and raw steel/paper purchases:
```csv
BUKRS,BELNR,HKONT,BUDAT,MENGE,MEINS,WRBTR,WERKS
DE10,200041,521010,20260510,18500,L,26300.00,DE10
DE10,200043,521010,20260515,650,GAL,1200.00,US20
DE10,200044,521010,20260516,8400,L,12500.00,JP90
```
*   **Why it looks like this**: In the real world, fuel is bought in inconsistent units: Europe registers in Liters (`L`), while US branches register in Gallons (`GAL`). Some postings use `YYYYMMDD` date formats, while others use standard European dots (`DD.MM.YYYY`). Additionally, plant codes (like `WERKS` `JP90`) can be posted in ledgers without being pre-registered in the facilities directory, which triggers our dashboard's `FLAGGED` anomaly warn state.

### What breaks in production:
1.  **Reversing Entries**: SAP ledger entries are frequently corrected via reversing journal postings (matching a positive debit with a negative credit, or using custom reversing flags like `STGRD`). A simple parser would count both, doubling the carbon footprint. Production engines must track document reversals (`XREVERS` / `STJAH`) to net out carbon values.
2.  **Unit of Measure Inconsistencies**: Enterprises use customized base units. A plant might input raw diesel as "drums" or "barrels" (`BBL`), or enter steel purchases in "pallets". Without a robust density and unit conversion matrix, the parser will fail.

---

## Source 2: Utility Grid Electricity (Portal Billing Dumps)

### Real-world format researched:
Large enterprises pull electricity consumption data from utility company portals (like PG&E, National Grid, or ConEd) or utilize structured XML formats like the **Green Button Data standard** (which logs billing and interval details in ESPI XML/JSON schemas).
*   **Real-world headers**: Standard portal billing exports contain:
    *   `Utility Provider`, `Account Number`, `Meter ID`, `Billing Start Date`, `Billing End Date`, `Total Consumption`, `Consumption Unit`, `Peak Demand (kW)`, `Tariff/Rate Class`, `Plant Code`.

### Sample data choice & Rationale:
Our simulator processes billing periods that cross calendar month boundaries:
```csv
Utility Provider,Account Number,Meter ID,Billing Start Date,Billing End Date,Total Consumption,Consumption Unit,Peak Demand,Plant Code
ConEd,ACT-55019,MTR-8819,04/15/2026,05/14/2026,115000,kWh,120,GB30
ConEd,ACT-55019,MTR-8819,04/15/2026,05/14/2026,220,MWh,480,US20
```
*   **Why it looks like this**: Electricity usage is reported in either `kWh` or `MWh`. Most importantly, billing periods are cycle-based (e.g. April 15 to May 14). To generate monthly reporting metrics (e.g. how much carbon did we emit in April?), the system must daily pro-rata split the consumption. Massive energy amounts (like `220 MWh` above) trigger baseline deviation flags.

### What breaks in production:
1.  **Meter Swaps**: If a facility's physical electricity meter breaks, the utility company swaps the meter mid-cycle, resulting in two separate records with overlapping periods but different meter IDs. Simple parsers might flag these as duplicates.
2.  **Estimated Bills**: Utilities often post "Estimated" bills when meter readings fail, followed by "Adjusted" bills the next month. The normalization engine must detect adjustments and dynamically overwrite previous calculations or post adjustment reconciliations to prevent double-counting.

---

## Source 3: Corporate Travel (Concur Booking API)

### Real-world format researched:
Corporate travel software (like the SAP Concur Travel v4 API or Navan APIs) exposes booking JSON segments representing flight segments, hotel night stays, and ground car rentals.
*   **Real-world schema**: Flight payloads contain Passenger, Departure and Arrival Airport codes (IATA 3-letter codes), Cabin Class (Economy, Business, First), Booking ID, and transactional date timestamps.

### Sample data choice & Rationale:
Our simulator processes structured travel booking arrays:
```json
[
  {
    "trip_type": "FLIGHT",
    "booking_id": "B3001",
    "passenger_name": "Sarah Jenkins",
    "departure_airport": "JFK",
    "arrival_airport": "LHR",
    "cabin_class": "Business",
    "transaction_date": "2026-05-18"
  }
]
```
*   **Why it looks like this**: Real travel APIs do not provide mileage values. The parser must dynamically look up IATA coordinates (e.g. JFK is `40.6398, -73.7789` and LHR is `51.4700, -0.4543`) and calculate the exact distance (e.g., `5585 km` JFK-to-LHR) using the Haversine Great-Circle formula. Cabin classes are flagged because business travelers take larger footprints, triggering a 2.9x carbon multiplier.

### What breaks in production:
1.  **Cancellations & Rebookings**: Business travelers frequently cancel or modify flights. The API logs a cancelled booking as a separate transaction. If the normalization engine does not reconcile the original booking ID (`parent_booking_id` / `status=CANCELLED`), it will count cancelled, un-flown flights as active carbon emissions.
2.  **Multi-leg flights**: A flight from San Francisco (SFO) to London (LHR) might have a layover in New York (JFK). A simple geocoder calculating SFO-to-LHR direct will understate emissions. Layovers incur high fuel burn rates due to takeoffs/landings; hence, the pipeline must parse segments (`legs`) individually to calculate carbon accurately.
