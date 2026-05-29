import csv
import io
from datetime import datetime
from decimal import Decimal
from django.utils.timezone import now
from ingestion.models import Facility, RawRecord, NormalizedRecord, IngestionJob

# GL Accounts definitions
GL_ACCOUNT_MAPPING = {
    '521010': {
        'category': 'Diesel',
        'scope_type': 'SCOPE_1',
        'standard_unit': 'Liters',
        'base_factor': Decimal('0.00268'),  # tCO2e per Liter of Diesel
        'description_template': 'SAP Ledger: Scope 1 direct Diesel combustion (A/C 521010)'
    },
    '521020': {
        'category': 'Natural Gas',
        'scope_type': 'SCOPE_1',
        'standard_unit': 'm3',
        'base_factor': Decimal('0.00202'),  # tCO2e per cubic meter of Nat Gas
        'description_template': 'SAP Ledger: Scope 1 direct Natural Gas combustion (A/C 521020)'
    },
    '550000': {
        'category': 'Procurement (Steel)',
        'scope_type': 'SCOPE_3',
        'standard_unit': 'MT',  # Metric Tons
        'base_factor': Decimal('1.85'),  # tCO2e per Metric Ton of Steel
        'description_template': 'SAP Ledger: Scope 3 Category 1 - Steel procurement (A/C 550000)'
    },
    '550010': {
        'category': 'Procurement (Paper)',
        'scope_type': 'SCOPE_3',
        'standard_unit': 'MT',
        'base_factor': Decimal('0.95'),  # tCO2e per Metric Ton of Paper
        'description_template': 'SAP Ledger: Scope 3 Category 1 - Paper procurement (A/C 550010)'
    }
}

# Unit converters
def normalize_unit(qty, unit, target_unit):
    qty = Decimal(str(qty))
    unit_upper = unit.strip().upper()
    
    if target_unit == 'Liters':
        if unit_upper in ['L', 'LITER', 'LITERS']:
            return qty, 'Liters'
        elif unit_upper in ['GAL', 'GALLON', 'GALLONS']:
            return qty * Decimal('3.78541'), 'Liters'  # US Gallons to Liters
    elif target_unit == 'm3':
        if unit_upper in ['M3', 'CUBIC_METERS', 'CUBIC_METER']:
            return qty, 'm3'
    elif target_unit == 'MT':
        if unit_upper in ['MT', 'T', 'TON', 'TONS', 'METRIC_TONS']:
            return qty, 'MT'
        elif unit_upper in ['KG', 'KILOGRAM', 'KILOGRAMS']:
            return qty / Decimal('1000.0'), 'MT'  # KG to MT
            
    # If no matching converter, return as-is (will trigger a unit warning flag)
    return qty, unit

def parse_sap_date(date_str):
    date_str = date_str.strip()
    # Handle YYYYMMDD
    if len(date_str) == 8 and date_str.isdigit():
        return datetime.strptime(date_str, '%Y%m%d').date()
    # Handle DD.MM.YYYY
    try:
        return datetime.strptime(date_str, '%d.%m.%Y').date()
    except ValueError:
        pass
    # Handle YYYY-MM-DD
    try:
        return datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        pass
    raise ValueError(f"Unknown SAP Date format: {date_str}")

def parse_sap_csv(job_id, csv_content):
    job = IngestionJob.objects.get(id=job_id)
    org = job.organization
    
    reader = csv.DictReader(io.StringIO(csv_content))
    
    # Required German standard SAP headers mapping
    header_map = {
        'BUKRS': 'company_code',
        'BELNR': 'doc_number',
        'HKONT': 'gl_account',
        'BUDAT': 'posting_date',
        'MENGE': 'quantity',
        'MEINS': 'unit',
        'WRBTR': 'cost',
        'WERKS': 'plant_code'
    }
    
    success_count = 0
    fail_count = 0
    
    for row_idx, row in enumerate(reader, 1):
        # Validate headers are present in the row
        mapped_row = {}
        missing_headers = []
        for german_h, internal_h in header_map.items():
            if german_h in row:
                mapped_row[internal_h] = row[german_h]
            else:
                missing_headers.append(german_h)
                
        if missing_headers:
            job.error_message = f"Row {row_idx}: Missing required SAP header(s): {', '.join(missing_headers)}"
            job.status = 'FAILED'
            job.save()
            return False
            
        # Log audit lineage: RawRecord
        raw_rec = RawRecord.objects.create(
            ingestion_job=job,
            organization=org,
            source_type='SAP',
            raw_payload=row
        )
        
        try:
            gl_acc = mapped_row['gl_account'].strip()
            if gl_acc not in GL_ACCOUNT_MAPPING:
                raise ValueError(f"G/L Account {gl_acc} not mapped to any carbon activity type.")
                
            activity = GL_ACCOUNT_MAPPING[gl_acc]
            
            # Parse Date
            tx_date = parse_sap_date(mapped_row['posting_date'])
            
            # Parse quantities
            raw_qty = Decimal(mapped_row['quantity'].strip().replace(',', '.'))
            raw_unit = mapped_row['unit'].strip()
            
            # Unit Normalization
            norm_qty, norm_unit = normalize_unit(raw_qty, raw_unit, activity['standard_unit'])
            
            # Emission calculation
            em_factor = activity['base_factor']
            co2e = (norm_qty * em_factor)
            
            # Plant Code resolution
            plant = mapped_row['plant_code'].strip()
            facility = Facility.objects.filter(organization=org, plant_code=plant).first()
            
            # Validation warnings logic (Anomaly engine)
            warnings = []
            status = 'DRAFT'
            
            if not facility:
                warnings.append(f"Plant code '{plant}' is not registered. Ingested as a draft with empty facility reference.")
                status = 'FLAGGED'
                
            if raw_qty <= 0:
                warnings.append("Ingested quantity is zero or negative. Placed on review.")
                status = 'FLAGGED'
                
            if norm_unit != activity['standard_unit']:
                warnings.append(f"Could not normalize unit '{raw_unit}' to target '{activity['standard_unit']}'. Value un-normalized.")
                status = 'FLAGGED'
                
            # Create Normalized record
            NormalizedRecord.objects.create(
                raw_record=raw_rec,
                ingestion_job=job,
                organization=org,
                transaction_date=tx_date,
                scope_type=activity['scope_type'],
                category=activity['category'],
                description=f"{activity['description_template']} - Doc: {mapped_row['doc_number']}",
                quantity=raw_qty,
                unit=raw_unit,
                normalized_quantity=norm_qty,
                normalized_unit=norm_unit,
                emission_factor=em_factor,
                co2e_emissions=co2e,
                source_system='SAP',
                plant_code=plant,
                facility=facility,
                status=status,
                validation_warnings=warnings
            )
            success_count += 1
            
        except Exception as e:
            # Let's create a failed normalized record structure, keeping lineage but marked REJECTED or FLAGGED
            fail_count += 1
            # Write a record marked as REJECTED to let analysts view ingestion failures directly
            NormalizedRecord.objects.create(
                raw_record=raw_rec,
                ingestion_job=job,
                organization=org,
                transaction_date=datetime.now().date(),
                scope_type='SCOPE_1',
                category='SAP Ingestion Error',
                description=f"Failed to parse SAP GL ledger row: {str(e)}",
                quantity=Decimal('0.00'),
                unit='UNKNOWN',
                normalized_quantity=Decimal('0.00'),
                normalized_unit='UNKNOWN',
                emission_factor=Decimal('0.00'),
                co2e_emissions=Decimal('0.00'),
                source_system='SAP',
                plant_code=row.get('WERKS', 'UNKNOWN'),
                status='REJECTED',
                review_notes=f"Automatic Parser Rejection: {str(e)}",
                validation_warnings=[f"Parser failure: {str(e)}"]
            )
            
    job.total_rows = row_idx
    job.successful_rows = success_count
    job.failed_rows = fail_count
    job.status = 'SUCCESS'
    job.save()
    return True
