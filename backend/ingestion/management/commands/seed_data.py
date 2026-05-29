from datetime import date, datetime
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.utils.timezone import now
from ingestion.models import Organization, Facility, IngestionJob, RawRecord, NormalizedRecord, AuditLog

BASE_FLIGHT_FACTOR = Decimal('0.000152')

class Command(BaseCommand):
    help = "Seeds database with highly realistic multi-tenant carbon accounting activity data."

    def handle(self, *args, **options):
        self.stdout.write("Purging existing data...")
        AuditLog.objects.all().delete()
        NormalizedRecord.objects.all().delete()
        RawRecord.objects.all().delete()
        IngestionJob.objects.all().delete()
        Facility.objects.all().delete()
        Organization.objects.all().delete()

        self.stdout.write("Creating multi-tenant organizations...")
        org1 = Organization.objects.create(name="Acme Industrial Corp")
        org2 = Organization.objects.create(name="Global Tech Ventures")

        self.stdout.write("Registering facility plants & utility grid regions...")
        # Tenant 1 Facilities
        fac_de = Facility.objects.create(
            organization=org1,
            plant_code="DE10",
            plant_name="Frankfurt Assembly Plant",
            location="Frankfurt, Germany",
            grid_region="Grid:Germany"
        )
        fac_us = Facility.objects.create(
            organization=org1,
            plant_code="US20",
            plant_name="NY Logistics Hub",
            location="Syracuse, NY, USA",
            grid_region="eGRID:NYUP"
        )
        fac_gb = Facility.objects.create(
            organization=org1,
            plant_code="GB30",
            plant_name="London Data Center",
            location="Slough, UK",
            grid_region="Grid:UK"
        )
        
        # Tenant 2 Facilities
        fac_t2 = Facility.objects.create(
            organization=org2,
            plant_code="US50",
            plant_name="Silicon Valley HQ",
            location="Sunnyvale, CA, USA",
            grid_region="Grid:US-DEFAULT"
        )

        self.stdout.write("Creating historical ingestion jobs...")
        job_sap = IngestionJob.objects.create(
            organization=org1,
            source_type="SAP",
            status="SUCCESS",
            file_name="SAP_ACDOCA_GL_2026_Q1.csv",
            file_size=45120,
            total_rows=12,
            successful_rows=12,
            failed_rows=0
        )
        
        job_util = IngestionJob.objects.create(
            organization=org1,
            source_type="UTILITY",
            status="SUCCESS",
            file_name="Utility_Portal_Export_Feb_Apr.csv",
            file_size=28100,
            total_rows=4,
            successful_rows=4,
            failed_rows=0
        )
        
        job_travel = IngestionJob.objects.create(
            organization=org1,
            source_type="TRAVEL",
            status="SUCCESS",
            file_name="Concur_API_CorporateTravel_Pull.json",
            file_size=12050,
            total_rows=6,
            successful_rows=6,
            failed_rows=0
        )

        # ----------------------------------------------------
        # Tenant 1: HISTORICAL EMISSIONS SEEDING (Acme Industrial Corp)
        # ----------------------------------------------------
        self.stdout.write("Seeding Acme Industrial Corp calculations...")

        historical_records = [
            # --- SCOPE 1: SAP Fuels ---
            # Feb 2026 - Frankfurt Assembly
            {
                'job': job_sap,
                'date': date(2026, 2, 10),
                'scope': 'SCOPE_1',
                'category': 'Diesel',
                'desc': 'SAP Ledger: Scope 1 direct Diesel combustion (A/C 521010) - Doc: 10004928',
                'qty': Decimal('15000.00'), 'unit': 'Liters',
                'n_qty': Decimal('15000.00'), 'n_unit': 'Liters',
                'factor': Decimal('0.00268'), 'co2e': Decimal('40.20'),
                'plant': 'DE10', 'fac': fac_de, 'status': 'APPROVED'
            },
            # Feb 2026 - NY Logistics
            {
                'job': job_sap,
                'date': date(2026, 2, 15),
                'scope': 'SCOPE_1',
                'category': 'Diesel',
                'desc': 'SAP Ledger: Scope 1 direct Diesel combustion (A/C 521010) - Doc: 10004955',
                'qty': Decimal('2500.00'), 'unit': 'GAL',
                'n_qty': Decimal('9463.525'), 'n_unit': 'Liters',
                'factor': Decimal('0.00268'), 'co2e': Decimal('25.362'),
                'plant': 'US20', 'fac': fac_us, 'status': 'APPROVED'
            },
            # Mar 2026 - Frankfurt Assembly
            {
                'job': job_sap,
                'date': date(2026, 3, 10),
                'scope': 'SCOPE_1',
                'category': 'Diesel',
                'desc': 'SAP Ledger: Scope 1 direct Diesel combustion (A/C 521010) - Doc: 10005112',
                'qty': Decimal('18000.00'), 'unit': 'Liters',
                'n_qty': Decimal('18000.00'), 'n_unit': 'Liters',
                'factor': Decimal('0.00268'), 'co2e': Decimal('48.24'),
                'plant': 'DE10', 'fac': fac_de, 'status': 'APPROVED'
            },
            # Mar 2026 - Natural Gas Frankfurt
            {
                'job': job_sap,
                'date': date(2026, 3, 12),
                'scope': 'SCOPE_1',
                'category': 'Natural Gas',
                'desc': 'SAP Ledger: Scope 1 direct Natural Gas combustion (A/C 521020) - Doc: 10005140',
                'qty': Decimal('5200.00'), 'unit': 'm3',
                'n_qty': Decimal('5200.00'), 'n_unit': 'm3',
                'factor': Decimal('0.00202'), 'co2e': Decimal('10.504'),
                'plant': 'DE10', 'fac': fac_de, 'status': 'APPROVED'
            },
            # Apr 2026 - Frankfurt Assembly
            {
                'job': job_sap,
                'date': date(2026, 4, 10),
                'scope': 'SCOPE_1',
                'category': 'Diesel',
                'desc': 'SAP Ledger: Scope 1 direct Diesel combustion (A/C 521010) - Doc: 10006230',
                'qty': Decimal('14500.00'), 'unit': 'Liters',
                'n_qty': Decimal('14500.00'), 'n_unit': 'Liters',
                'factor': Decimal('0.00268'), 'co2e': Decimal('38.86'),
                'plant': 'DE10', 'fac': fac_de, 'status': 'APPROVED'
            },

            # --- SCOPE 2: Utility Electricity ---
            # Feb 2026 Electricity - London Data Center (Grid:UK = 0.000207 tCO2e/kWh)
            {
                'job': job_util,
                'date': date(2026, 2, 28),
                'scope': 'SCOPE_2',
                'category': 'Electricity',
                'desc': 'Electricity supply - Meter: MTR-8819 (British Grid). Allocated pro-rata from cycle: 2026-02-01 to 2026-02-28.',
                'qty': Decimal('120.00'), 'unit': 'MWh',
                'n_qty': Decimal('120000.00'), 'n_unit': 'kWh',
                'factor': Decimal('0.000207'), 'co2e': Decimal('24.84'),
                'plant': 'GB30', 'fac': fac_gb, 'status': 'APPROVED'
            },
            # Mar 2026 Electricity - London Data Center
            {
                'job': job_util,
                'date': date(2026, 3, 31),
                'scope': 'SCOPE_2',
                'category': 'Electricity',
                'desc': 'Electricity supply - Meter: MTR-8819 (British Grid). Allocated pro-rata from cycle: 2026-03-01 to 2026-03-31.',
                'qty': Decimal('125.00'), 'unit': 'MWh',
                'n_qty': Decimal('125000.00'), 'n_unit': 'kWh',
                'factor': Decimal('0.000207'), 'co2e': Decimal('25.875'),
                'plant': 'GB30', 'fac': fac_gb, 'status': 'APPROVED'
            },
            # Feb 2026 Electricity - NY Logistics (eGRID:NYUP = 0.000116 tCO2e/kWh)
            {
                'job': job_util,
                'date': date(2026, 2, 28),
                'scope': 'SCOPE_2',
                'category': 'Electricity',
                'desc': 'Electricity supply - Meter: MTR-4402 (National Grid). Allocated pro-rata from cycle: 2026-01-15 to 2026-02-14.',
                'qty': Decimal('45000.00'), 'unit': 'kWh',
                'n_qty': Decimal('45000.00'), 'n_unit': 'kWh',
                'factor': Decimal('0.000116'), 'co2e': Decimal('5.22'),
                'plant': 'US20', 'fac': fac_us, 'status': 'APPROVED'
            },
            # Mar 2026 Electricity - NY Logistics
            {
                'job': job_util,
                'date': date(2026, 3, 31),
                'scope': 'SCOPE_2',
                'category': 'Electricity',
                'desc': 'Electricity supply - Meter: MTR-4402 (National Grid). Allocated pro-rata from cycle: 2026-02-15 to 2026-03-14.',
                'qty': Decimal('42000.00'), 'unit': 'kWh',
                'n_qty': Decimal('42000.00'), 'n_unit': 'kWh',
                'factor': Decimal('0.000116'), 'co2e': Decimal('4.872'),
                'plant': 'US20', 'fac': fac_us, 'status': 'APPROVED'
            },

            # --- SCOPE 3: Travel ---
            # Flight Feb 2026: SFO - JFK, Economy class (calculated distance: ~4150 km)
            {
                'job': job_travel,
                'date': date(2026, 2, 5),
                'scope': 'SCOPE_3',
                'category': 'Flight',
                'desc': 'Business Flight (Concur: B9911) - Sarah Jenkins: SFO to JFK (Economy Class) [Distance calculated using Great-Circle coordinate lookup]',
                'qty': Decimal('4150.00'), 'unit': 'km',
                'n_qty': Decimal('4150.00'), 'n_unit': 'pkm',
                'factor': Decimal('0.000152'), 'co2e': Decimal('0.631'),
                'plant': 'US20', 'fac': fac_us, 'status': 'APPROVED'
            },
            # Hotel Feb 2026: London stay (Grid:UK factor = 0.0178)
            {
                'job': job_travel,
                'date': date(2026, 2, 8),
                'scope': 'SCOPE_3',
                'category': 'Hotel Stay',
                'desc': 'Hotel lodging (Concur: B9912) - Sarah Jenkins at Slough Premier Inn, London, UK (5 Room-Nights)',
                'qty': Decimal('5.00'), 'unit': 'room-nights',
                'n_qty': Decimal('5.00'), 'n_unit': 'room-nights',
                'factor': Decimal('0.017800'), 'co2e': Decimal('0.089'),
                'plant': 'GB30', 'fac': fac_gb, 'status': 'APPROVED'
            },
            # Scope 3 Procurement Steel (Acme Industrial) - March 2026 (Account 550000)
            {
                'job': job_sap,
                'date': date(2026, 3, 20),
                'scope': 'SCOPE_3',
                'category': 'Procurement (Steel)',
                'desc': 'SAP Ledger: Scope 3 Category 1 - Steel procurement (A/C 550000) - Doc: 10005202',
                'qty': Decimal('12.50'), 'unit': 'MT',
                'n_qty': Decimal('12.50'), 'n_unit': 'MT',
                'factor': Decimal('1.850000'), 'co2e': Decimal('23.125'),
                'plant': 'DE10', 'fac': fac_de, 'status': 'APPROVED'
            }
        ]

        # Bulk create approved records and log their corresponding audits
        for r_data in historical_records:
            # Create a raw record placeholder
            raw = RawRecord.objects.create(
                ingestion_job=r_data['job'],
                organization=org1,
                source_type=r_data['job'].source_type,
                raw_payload={"details": r_data['desc'], "seeded": True}
            )
            
            rec = NormalizedRecord.objects.create(
                raw_record=raw,
                ingestion_job=r_data['job'],
                organization=org1,
                transaction_date=r_data['date'],
                scope_type=r_data['scope'],
                category=r_data['category'],
                description=r_data['desc'],
                quantity=r_data['qty'],
                unit=r_data['unit'],
                normalized_quantity=r_data['n_qty'],
                normalized_unit=r_data['n_unit'],
                emission_factor=r_data['factor'],
                co2e_emissions=r_data['co2e'],
                source_system=r_data['job'].source_type,
                plant_code=r_data['plant'],
                facility=r_data['fac'],
                status=r_data['status']
            )
            
            # Log Audit trail
            AuditLog.objects.create(
                normalized_record=rec,
                organization=org1,
                user="System Migration Engine",
                action="APPROVE",
                previous_values={"status": "DRAFT"},
                new_values={"status": "APPROVED", "approved_by": "System Migration Engine"},
                reason="Automatic lock of historical closed quarters."
            )

        # ----------------------------------------------------
        # Seed UNRESOLVED Drafts and Flags for Analyst review demo!
        # ----------------------------------------------------
        self.stdout.write("Seeding active review pipeline items (Drafts, Flags)...")

        # Draft 1: SAP procurement paper
        raw_draft_1 = RawRecord.objects.create(
            ingestion_job=job_sap,
            organization=org1,
            source_type="SAP",
            raw_payload={"BUKRS": "US10", "BELNR": "10008892", "HKONT": "550010", "BUDAT": "20260515", "MENGE": "2500", "MEINS": "KG", "WRBTR": "450,00", "WERKS": "US20"}
        )
        NormalizedRecord.objects.create(
            raw_record=raw_draft_1,
            ingestion_job=job_sap,
            organization=org1,
            transaction_date=date(2026, 5, 15),
            scope_type="SCOPE_3",
            category="Procurement (Paper)",
            description="SAP Ledger: Scope 3 Category 1 - Paper procurement (A/C 550010) - Doc: 10008892",
            quantity=Decimal('2500.00'),
            unit="KG",
            normalized_quantity=Decimal('2.50'),
            normalized_unit="MT",
            emission_factor=Decimal('0.950000'),
            co2e_emissions=Decimal('2.375'),
            source_system="SAP",
            plant_code="US20",
            facility=fac_us,
            status="DRAFT"
        )

        # Flagged 1: SAP Fuel combustion with UNREGISTERED PLANT 'JP90'
        # Anomaly: Missing Plant Lookup (Allows Analyst to type DE10 and save!)
        raw_flag_1 = RawRecord.objects.create(
            ingestion_job=job_sap,
            organization=org1,
            source_type="SAP",
            raw_payload={"BUKRS": "DE10", "BELNR": "10008910", "HKONT": "521010", "BUDAT": "20260516", "MENGE": "12000", "MEINS": "L", "WRBTR": "18400,00", "WERKS": "JP90"}
        )
        NormalizedRecord.objects.create(
            raw_record=raw_flag_1,
            ingestion_job=job_sap,
            organization=org1,
            transaction_date=date(2026, 5, 16),
            scope_type="SCOPE_1",
            category="Diesel",
            description="SAP Ledger: Scope 1 direct Diesel combustion (A/C 521010) - Doc: 10008910 [Warning: Unmapped Plant]",
            quantity=Decimal('12000.00'),
            unit="Liters",
            normalized_quantity=Decimal('12000.00'),
            normalized_unit="Liters",
            emission_factor=Decimal('0.00268'),
            co2e_emissions=Decimal('32.16'),
            source_system="SAP",
            plant_code="JP90",
            facility=None,
            status="FLAGGED",
            validation_warnings=["Plant code 'JP90' is not registered. Ingested as a draft with empty facility reference."]
        )

        # Flagged 2: Utility Bill with massive consumption (kWh > 100,000 threshold) and extremely long cycle
        # Anomaly: Out of typical baseline limits
        raw_flag_2 = RawRecord.objects.create(
            ingestion_job=job_util,
            organization=org1,
            source_type="UTILITY",
            raw_payload={"Utility Provider": "PGE", "Account Number": "ACT-99120", "Meter ID": "MTR-8819", "Billing Start Date": "03/15/2026", "Billing End Date": "05/01/2026", "Total Consumption": "145", "Consumption Unit": "MWh", "Peak Demand": "320", "Plant Code": "GB30"}
        )
        NormalizedRecord.objects.create(
            raw_record=raw_flag_2,
            ingestion_job=job_util,
            organization=org1,
            transaction_date=date(2026, 5, 1),
            scope_type="SCOPE_2",
            category="Electricity",
            description="Electricity supply - Meter: MTR-8819 (British Grid). Allocated pro-rata from cycle: 2026-03-15 to 2026-05-01.",
            quantity=Decimal('145.00'),
            unit="MWh",
            normalized_quantity=Decimal('145000.00'),
            normalized_unit="kWh",
            emission_factor=Decimal('0.000207'),
            co2e_emissions=Decimal('30.015'),
            source_system="UTILITY",
            plant_code="GB30",
            facility=fac_gb,
            status="FLAGGED",
            validation_warnings=[
                "Electricity consumption of 145000.0 kWh exceeds typical baseline threshold.",
                "Billing period is unusually long (48 days). Expect allocation gaps."
            ]
        )

        # Flagged 3: Corporate Travel flight with Premium Cabin class (Business JFK to LHR)
        # Anomaly: Premium Cabin multiplier
        raw_flag_3 = RawRecord.objects.create(
            ingestion_job=job_travel,
            organization=org1,
            source_type="TRAVEL",
            raw_payload={"trip_type": "FLIGHT", "booking_id": "B1009", "passenger_name": "Marcus Aurelius", "departure_airport": "JFK", "arrival_airport": "LHR", "cabin_class": "Business", "transaction_date": "2026-05-20"}
        )
        # Distance JFK-LHR is 5585 km.
        dist = Decimal('5585.00')
        f_factor = BASE_FLIGHT_FACTOR * Decimal('2.90') # Business multiplier
        co2e_val = dist * f_factor
        NormalizedRecord.objects.create(
            raw_record=raw_flag_3,
            ingestion_job=job_travel,
            organization=org1,
            transaction_date=date(2026, 5, 20),
            scope_type="SCOPE_3",
            category="Flight",
            description="Business Flight (Concur: B1009) - Marcus Aurelius: JFK to LHR (Business Class) [Distance calculated using Great-Circle coordinate lookup]",
            quantity=dist,
            unit="km",
            normalized_quantity=dist,
            normalized_unit="pkm",
            emission_factor=f_factor,
            co2e_emissions=co2e_val,
            source_system="TRAVEL",
            status="FLAGGED",
            validation_warnings=["Cabin class is premium (BUSINESS). 2.9x carbon multiplier applied."]
        )

        # ----------------------------------------------------
        # Tenant 2: DATA SEEDING (Global Tech Ventures)
        # To demonstrate absolute multi-tenant containment!
        # ----------------------------------------------------
        self.stdout.write("Seeding Global Tech Ventures (Tenant 2) isolation...")
        job_t2 = IngestionJob.objects.create(
            organization=org2,
            source_type="UTILITY",
            status="SUCCESS",
            file_name="Tenant_2_Utility_Q1.csv",
            file_size=5420,
            total_rows=1,
            successful_rows=1,
            failed_rows=0
        )
        raw_t2 = RawRecord.objects.create(
            ingestion_job=job_t2,
            organization=org2,
            source_type="UTILITY",
            raw_payload={"Meter": "MTR-T2", "Consumption": "8500"}
        )
        NormalizedRecord.objects.create(
            raw_record=raw_t2,
            ingestion_job=job_t2,
            organization=org2,
            transaction_date=date(2026, 3, 1),
            scope_type="SCOPE_2",
            category="Electricity",
            description="Tenant 2 Grid electricity billing - Meter: MTR-T2 (US Central)",
            quantity=Decimal('8500.00'),
            unit="kWh",
            normalized_quantity=Decimal('8500.00'),
            normalized_unit="kWh",
            emission_factor=Decimal('0.000371'),
            co2e_emissions=Decimal('3.1535'),
            source_system="UTILITY",
            plant_code="US50",
            facility=fac_t2,
            status="APPROVED"
        )

        self.stdout.write(self.style.SUCCESS("Database seeded successfully with multi-tenant historical calculations, active drafts, and review flags."))
