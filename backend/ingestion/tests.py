from datetime import date, datetime
from decimal import Decimal
import json
from django.test import TestCase
from django.utils.timezone import now
from rest_framework import status
from rest_framework.test import APITestCase

from ingestion.models import Organization, Facility, IngestionJob, RawRecord, NormalizedRecord, AuditLog
from ingestion.processors import parse_sap_csv, parse_utility_csv, parse_travel_json
from ingestion.processors.travel import calculate_haversine

class IngestionProcessorTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="Acme Testing Corp")
        
        # Register test facilities
        self.facility_de = Facility.objects.create(
            organization=self.org,
            plant_code="DE10",
            plant_name="Frankfurt Engine Plant",
            location="Frankfurt, Germany",
            grid_region="Grid:Germany"
        )
        self.facility_us = Facility.objects.create(
            organization=self.org,
            plant_code="US20",
            plant_name="Syracuse Hub",
            location="Syracuse, NY, USA",
            grid_region="eGRID:NYUP"
        )

    def test_sap_parser_german_headers_and_units(self):
        # Sample SAP GL CSV export with German headers
        csv_data = (
            "BUKRS,BELNR,HKONT,BUDAT,MENGE,MEINS,WRBTR,WERKS\n"
            "DE10,1001,521010,20260315,1000,L,1500.00,DE10\n" # Scope 1 Diesel, 1000 Liters
            "DE10,1002,521010,15.03.2026,100,GAL,450.00,US20\n" # Scope 1 Diesel, 100 Gallons -> normalized to Liters
            "DE10,1003,550000,2026-03-16,500,KG,3000.00,DE10\n" # Scope 3 Steel, 500 KG -> normalized to 0.5 MT
        )
        
        job = IngestionJob.objects.create(
            organization=self.org,
            source_type="SAP",
            file_name="sap_test.csv",
            file_size=len(csv_data)
        )
        
        success = parse_sap_csv(job.id, csv_data)
        self.assertTrue(success)
        job.refresh_from_db()
        self.assertEqual(job.status, "SUCCESS")
        self.assertEqual(job.total_rows, 3)
        
        # Verify first row: 1000 Liters diesel -> 2.68 tCO2e (1000 * 0.00268)
        rec1 = NormalizedRecord.objects.get(raw_record__raw_payload__BELNR="1001")
        self.assertEqual(rec1.scope_type, "SCOPE_1")
        self.assertEqual(rec1.category, "Diesel")
        self.assertEqual(rec1.normalized_quantity, Decimal("1000.0000"))
        self.assertEqual(rec1.normalized_unit, "Liters")
        self.assertEqual(rec1.co2e_emissions, Decimal("2.680000"))
        self.assertEqual(rec1.facility, self.facility_de)
        self.assertEqual(rec1.status, "DRAFT")
        
        # Verify second row: 100 Gallons diesel -> normalized to ~378.54 Liters
        rec2 = NormalizedRecord.objects.get(raw_record__raw_payload__BELNR="1002")
        self.assertAlmostEqual(float(rec2.normalized_quantity), 378.541, places=3)
        self.assertEqual(rec2.normalized_unit, "Liters")
        self.assertEqual(rec2.facility, self.facility_us)
        
        # Verify third row: 500 KG steel -> normalized to 0.5 MT -> 0.925 tCO2e (0.5 * 1.85)
        rec3 = NormalizedRecord.objects.get(raw_record__raw_payload__BELNR="1003")
        self.assertEqual(rec3.scope_type, "SCOPE_3")
        self.assertEqual(rec3.normalized_quantity, Decimal("0.5000"))
        self.assertEqual(rec3.normalized_unit, "MT")
        self.assertEqual(rec3.co2e_emissions, Decimal("0.925000"))

    def test_utility_parser_pro_rata_daily_distribution(self):
        # Bill overlaps February and March: 2026-02-15 to 2026-03-16 = 30 days total
        # Feb has 14 days (Feb 15 to Feb 28), Mar has 16 days (Mar 01 to Mar 16)
        # Total consumption = 3000 kWh -> 100 kWh per day
        # February allocated = 1400 kWh, March allocated = 1600 kWh
        csv_data = (
            "Utility Provider,Account Number,Meter ID,Billing Start Date,Billing End Date,Total Consumption,Consumption Unit,Peak Demand,Plant Code\n"
            "PowerGrid,ACT-1002,MTR-55,02/15/2026,03/16/2026,3,MWh,45,DE10\n" # 3 MWh = 3000 kWh
        )
        
        job = IngestionJob.objects.create(
            organization=self.org,
            source_type="UTILITY",
            file_name="utility_test.csv",
            file_size=len(csv_data)
        )
        
        success = parse_utility_csv(job.id, csv_data)
        self.assertTrue(success)
        job.refresh_from_db()
        self.assertEqual(job.status, "SUCCESS")
        
        # Germany grid factor = 0.000385 tCO2e per kWh
        # February allocation: 1400 kWh * 0.000385 = 0.539 tCO2e
        rec_feb = NormalizedRecord.objects.get(transaction_date=date(2026, 2, 28))
        self.assertEqual(rec_feb.scope_type, "SCOPE_2")
        self.assertEqual(rec_feb.normalized_quantity, Decimal("1400.0000"))
        self.assertEqual(rec_feb.co2e_emissions, Decimal("0.539000"))
        self.assertEqual(rec_feb.facility, self.facility_de)
        
        # March allocation: 1600 kWh * 0.000385 = 0.616 tCO2e
        rec_mar = NormalizedRecord.objects.get(transaction_date=date(2026, 3, 16))
        self.assertEqual(rec_mar.normalized_quantity, Decimal("1600.0000"))
        self.assertEqual(rec_mar.co2e_emissions, Decimal("0.616000"))

    def test_travel_parser_haversine_and_cabin_multipliers(self):
        # Test Haversine distance calculator directly
        # JFK coordinates (40.6398, -73.7789) to LHR (51.4700, -0.4543)
        dist = calculate_haversine("JFK", "LHR")
        self.assertIsNotNone(dist)
        self.assertGreater(dist, 5500)
        self.assertLess(dist, 5700)
        
        # Travel JSON payload with flight, hotel, and ground
        travel_json = json.dumps([
            {
                "trip_type": "FLIGHT",
                "booking_id": "B001",
                "passenger_name": "Marcus Aurelius",
                "departure_airport": "JFK",
                "arrival_airport": "LHR",
                "cabin_class": "Business", # Business multiplier is 2.9x
                "transaction_date": "2026-04-12"
            },
            {
                "trip_type": "HOTEL",
                "booking_id": "B002",
                "passenger_name": "Marcus Aurelius",
                "hotel_name": "Frankfurt Hilton",
                "city": "Frankfurt",
                "country": "Germany", # Germany factor is 0.0142
                "nights": 4,
                "rooms": 2, # Total 8 room-nights
                "transaction_date": "2026-04-15"
            }
        ])
        
        job = IngestionJob.objects.create(
            organization=self.org,
            source_type="TRAVEL",
            file_name="travel_test.json",
            file_size=len(travel_json)
        )
        
        success = parse_travel_json(job.id, travel_json)
        self.assertTrue(success)
        
        # Verify Flight: Distance * (0.000152 * 2.9)
        flight_rec = NormalizedRecord.objects.get(category="Flight")
        self.assertEqual(flight_rec.scope_type, "SCOPE_3")
        self.assertEqual(flight_rec.status, "FLAGGED") # Flags because premium cabin class
        self.assertIn("Cabin class is premium", flight_rec.validation_warnings[0])
        
        # Verify Hotel: 8 room-nights * 0.0142 = 0.1136 tCO2e
        hotel_rec = NormalizedRecord.objects.get(category="Hotel Stay")
        self.assertEqual(hotel_rec.normalized_quantity, Decimal("8.0000"))
        self.assertEqual(hotel_rec.co2e_emissions, Decimal("0.113600"))


class AuditorWorkflowAPITests(APITestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="Audit Safeguards Corp")
        
        self.job = IngestionJob.objects.create(
            organization=self.org,
            source_type="SAP",
            status="SUCCESS",
            file_name="sap_audit.csv",
            file_size=200
        )
        
        self.raw = RawRecord.objects.create(
            ingestion_job=self.job,
            organization=self.org,
            source_type="SAP",
            raw_payload={"item": "test"}
        )
        
        # Create a Draft record
        self.record_draft = NormalizedRecord.objects.create(
            raw_record=self.raw,
            ingestion_job=self.job,
            organization=self.org,
            transaction_date=date(2026, 4, 1),
            scope_type="SCOPE_1",
            category="Diesel",
            description="Diesel fuel test",
            quantity=Decimal("1000.00"),
            unit="Liters",
            normalized_quantity=Decimal("1000.00"),
            normalized_unit="Liters",
            emission_factor=Decimal("0.00268"),
            co2e_emissions=Decimal("2.68"),
            source_system="SAP",
            status="DRAFT"
        )
        
        # Create an already Approved record
        self.record_approved = NormalizedRecord.objects.create(
            raw_record=None,
            ingestion_job=None,
            organization=self.org,
            transaction_date=date(2026, 4, 1),
            scope_type="SCOPE_2",
            category="Electricity",
            description="Electricity locked",
            quantity=Decimal("5000.00"),
            unit="kWh",
            normalized_quantity=Decimal("5000.00"),
            normalized_unit="kWh",
            emission_factor=Decimal("0.00025"),
            co2e_emissions=Decimal("1.25"),
            source_system="UTILITY",
            status="APPROVED"
        )

    def test_update_requires_audit_reason(self):
        url = f"/api/records/{self.record_draft.id}/"
        
        # Attempt update without audit_reason -> must fail with 400
        data = {
            "quantity": 1200
        }
        response = self.client.put(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("explanatory audit_reason", response.data['error'])
        
        # Verify record was not modified
        self.record_draft.refresh_from_db()
        self.assertEqual(self.record_draft.quantity, Decimal("1000.0000"))

    def test_update_blocked_on_approved_record(self):
        url = f"/api/records/{self.record_approved.id}/"
        data = {
            "quantity": 6000,
            "audit_reason": "Correcting billing amount override"
        }
        response = self.client.put(url, data, format='json')
        
        # Approved record modifications must be rejected -> 400 Bad Request
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("locked for audit", response.data['error'])
        
        # Verify no audit log is generated
        self.assertEqual(AuditLog.objects.filter(normalized_record=self.record_approved).count(), 0)

    def test_successful_auditor_edit_generates_audit_trail(self):
        url = f"/api/records/{self.record_draft.id}/"
        data = {
            "quantity": 1500,
            "audit_reason": "Verified invoice quantity was understated by 500L.",
            "user": "auditor.sally@breatheesg.com"
        }
        
        response = self.client.put(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify quantities and emissions updated (1500 * 0.00268 = 4.02)
        self.record_draft.refresh_from_db()
        self.assertEqual(self.record_draft.quantity, Decimal("1500.0000"))
        self.assertEqual(self.record_draft.normalized_quantity, Decimal("1500.0000"))
        self.assertEqual(self.record_draft.co2e_emissions, Decimal("4.020000"))
        
        # Verify Audit Log is saved
        audit = AuditLog.objects.get(normalized_record=self.record_draft)
        self.assertEqual(audit.user, "auditor.sally@breatheesg.com")
        self.assertEqual(audit.action, "UPDATE")
        self.assertEqual(audit.reason, "Verified invoice quantity was understated by 500L.")
        self.assertEqual(audit.previous_values["quantity"], "1000.0000")
        self.assertEqual(audit.new_values["quantity"], "1500")
