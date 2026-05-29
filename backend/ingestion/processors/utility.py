import csv
import io
from datetime import datetime, date, timedelta
from decimal import Decimal
from collections import defaultdict
from django.utils.timezone import now
from ingestion.models import Facility, RawRecord, NormalizedRecord, IngestionJob

# Subregional grid emission factors (tCO2e per kWh)
GRID_FACTORS = {
    'eGRID:NYUP': Decimal('0.000116'),  # Upstate NY grid mix
    'Grid:Germany': Decimal('0.000385'),  # Germany national grid mix
    'Grid:UK': Decimal('0.000207'),  # UK national grid mix
    'Grid:US-DEFAULT': Decimal('0.000371'),  # Average US mix
    'DEFAULT': Decimal('0.000250')  # Fallback emission factor
}

def parse_utility_date(date_str):
    date_str = date_str.strip()
    for fmt in ('%m/%d/%Y', '%Y-%m-%d', '%d/%m/%Y', '%d.%m.%Y'):
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            pass
    raise ValueError(f"Unknown utility date format: {date_str}")

def parse_utility_csv(job_id, csv_content):
    job = IngestionJob.objects.get(id=job_id)
    org = job.organization
    
    reader = csv.DictReader(io.StringIO(csv_content))
    
    header_map = {
        'Utility Provider': 'provider',
        'Account Number': 'account_number',
        'Meter ID': 'meter_id',
        'Billing Start Date': 'start_date',
        'Billing End Date': 'end_date',
        'Total Consumption': 'consumption',
        'Consumption Unit': 'unit',
        'Peak Demand': 'peak_demand',
        'Plant Code': 'plant_code'
    }
    
    success_count = 0
    fail_count = 0
    row_count = 0
    
    for row in reader:
        row_count += 1
        
        # Lineage tracking
        raw_rec = RawRecord.objects.create(
            ingestion_job=job,
            organization=org,
            source_type='UTILITY',
            raw_payload=row
        )
        
        try:
            # Map fields safely
            mapped = {}
            for csv_h, internal_h in header_map.items():
                if csv_h not in row:
                    raise ValueError(f"Missing required utility CSV column: '{csv_h}'")
                mapped[internal_h] = row[csv_h].strip()
                
            start_dt = parse_utility_date(mapped['start_date'])
            end_dt = parse_utility_date(mapped['end_date'])
            
            if end_dt < start_dt:
                raise ValueError(f"Billing End Date ({end_dt}) cannot be before Start Date ({start_dt})")
                
            raw_consumption = Decimal(mapped['consumption'].replace(',', '.'))
            raw_unit = mapped['unit'].upper()
            
            # Unit standardization to kWh
            norm_consumption = raw_consumption
            if raw_unit in ['MWH', 'MEGAWATT_HOURS']:
                norm_consumption = raw_consumption * Decimal('1000.0')
            elif raw_unit not in ['KWH', 'KILOWATT_HOURS']:
                raise ValueError(f"Unsupported consumption unit: '{raw_unit}'. Expected kWh or MWh.")
                
            plant = mapped['plant_code']
            facility = Facility.objects.filter(organization=org, plant_code=plant).first()
            
            # Resolve emission factor from plant grid region
            if facility:
                grid = facility.grid_region
                factor = GRID_FACTORS.get(grid, GRID_FACTORS['DEFAULT'])
            else:
                factor = GRID_FACTORS['DEFAULT']
                
            # Perform Pro-rata calendar allocation math!
            total_days = (end_dt - start_dt).days + 1
            if total_days <= 0:
                raise ValueError("Billing period days count must be greater than 0")
                
            daily_kwh = norm_consumption / Decimal(str(total_days))
            
            # Distribute consumption to (Year, Month) buckets
            monthly_distribution = defaultdict(Decimal)
            current_day = start_dt
            while current_day <= end_dt:
                bucket_key = (current_day.year, current_day.month)
                monthly_distribution[bucket_key] += daily_kwh
                current_day += timedelta(days=1)
                
            # For each month represented, generate a normalized record
            for (year, month), allocated_kwh in monthly_distribution.items():
                # We determine the "transaction date" as the last day of that month within the billing period, or standard end of month
                # For reporting, we will set the day to the last day of the month or the billing period's end day, whichever is earlier
                # Let's use the last day of the month or the actual billing end date
                last_day_of_month = date(year, month, 28) + timedelta(days=4)
                last_day_of_month = last_day_of_month - timedelta(days=last_day_of_month.day)
                tx_date = min(last_day_of_month, end_dt)
                
                # Check for anomalies
                warnings = []
                status = 'DRAFT'
                
                if not facility:
                    warnings.append(f"Plant code '{plant}' not found in registry. Assigned fallback emission factor.")
                    status = 'FLAGGED'
                    
                if allocated_kwh > Decimal('100000'):
                    warnings.append(f"Electricity consumption of {allocated_kwh:.1f} kWh for {month}/{year} exceeds typical baseline threshold.")
                    status = 'FLAGGED'
                    
                if total_days > 45:
                    warnings.append(f"Billing period is unusually long ({total_days} days). Expect allocation gaps.")
                    status = 'FLAGGED'
                
                # Calculate Scope 2 emissions (tCO2e)
                co2e = (allocated_kwh * factor)
                
                NormalizedRecord.objects.create(
                    raw_record=raw_rec,
                    ingestion_job=job,
                    organization=org,
                    transaction_date=tx_date,
                    scope_type='SCOPE_2',
                    category='Electricity',
                    description=(
                        f"Electricity supply - Meter: {mapped['meter_id']} ({mapped['provider']}). "
                        f"Allocated pro-rata from cycle: {start_dt} to {end_dt}."
                    ),
                    # Original billing quantities (pro-rated proportionally for visibility)
                    quantity=(raw_consumption * (allocated_kwh / norm_consumption)).quantize(Decimal('1.0000')),
                    unit=mapped['unit'],
                    # Normalized quantities
                    normalized_quantity=allocated_kwh.quantize(Decimal('1.0000')),
                    normalized_unit='kWh',
                    emission_factor=factor,
                    co2e_emissions=co2e.quantize(Decimal('1.000000')),
                    source_system='UTILITY',
                    plant_code=plant,
                    facility=facility,
                    status=status,
                    validation_warnings=warnings
                )
            success_count += 1
            
        except Exception as e:
            fail_count += 1
            # Ingestion fail logging
            NormalizedRecord.objects.create(
                raw_record=raw_rec,
                ingestion_job=job,
                organization=org,
                transaction_date=now().date(),
                scope_type='SCOPE_2',
                category='Electricity Ingestion Error',
                description=f"Failed parsing utility row: {str(e)}",
                quantity=Decimal('0.00'),
                unit='UNKNOWN',
                normalized_quantity=Decimal('0.00'),
                normalized_unit='UNKNOWN',
                emission_factor=Decimal('0.00'),
                co2e_emissions=Decimal('0.00'),
                source_system='UTILITY',
                status='REJECTED',
                review_notes=f"Automatic Parser Rejection: {str(e)}",
                validation_warnings=[f"Parser failure: {str(e)}"]
            )
            
    job.total_rows = row_count
    job.successful_rows = success_count
    job.failed_rows = fail_count
    job.status = 'SUCCESS'
    job.save()
    return True
