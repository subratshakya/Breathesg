import json
import math
from datetime import datetime
from decimal import Decimal
from django.utils.timezone import now
from ingestion.models import RawRecord, NormalizedRecord, IngestionJob

# Airport Database (Latitude, Longitude) for Haversine calculations
AIRPORT_COORDINATES = {
    'JFK': (40.6398, -73.7789),      # New York Kennedy
    'LHR': (51.4700, -0.4543),       # London Heathrow
    'CDG': (49.0097, 2.5479),        # Paris Charles de Gaulle
    'FRA': (50.0333, 8.5706),        # Frankfurt
    'SFO': (37.6190, -122.3749),     # San Francisco
    'LAX': (33.9416, -118.4085),     # Los Angeles
    'DXB': (25.2532, 55.3657),       # Dubai
    'BOM': (19.0896, 72.8656),       # Mumbai Chhatrapati Shivaji
    'SIN': (1.3644, 103.9915),       # Singapore Changi
    'SYD': (-33.9461, 151.1772)      # Sydney Kingsford Smith
}

# Country specific hotel stay factors (tCO2e per room-night)
HOTEL_FACTORS = {
    'US': Decimal('0.0246'),
    'USA': Decimal('0.0246'),
    'GB': Decimal('0.0178'),
    'UK': Decimal('0.0178'),
    'DE': Decimal('0.0142'),
    'GERMANY': Decimal('0.0142'),
    'IN': Decimal('0.0294'),
    'INDIA': Decimal('0.0294'),
    'DEFAULT': Decimal('0.0200')
}

# Ground Vehicle factors (tCO2e per kilometer)
GROUND_FACTORS = {
    'EV': Decimal('0.000045'),       # Carbon share of charging grid
    'ECONOMY': Decimal('0.000164'),  # Average midsize gasoline
    'SUV': Decimal('0.000275'),      # Large SUV/Truck
    'DEFAULT': Decimal('0.000180')
}

# Base flight factor (tCO2e per passenger-kilometer)
BASE_FLIGHT_FACTOR = Decimal('0.000152')

# Cabin class multipliers (DEFRA/EPA Standard)
CABIN_MULTIPLIERS = {
    'ECONOMY': Decimal('1.00'),
    'PREMIUM_ECONOMY': Decimal('1.60'),
    'BUSINESS': Decimal('2.90'),     # Space occupancy premium
    'FIRST': Decimal('4.00'),        # High footprint premium
    'DEFAULT': Decimal('1.00')
}

def calculate_haversine(airport1, airport2):
    """Calculate distance in kilometers using the Haversine formula."""
    coord1 = AIRPORT_COORDINATES.get(airport1.strip().upper())
    coord2 = AIRPORT_COORDINATES.get(airport2.strip().upper())
    
    if not coord1 or not coord2:
        return None
        
    lat1, lon1 = map(math.radians, coord1)
    lat2, lon2 = map(math.radians, coord2)
    
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    r = 6371  # Earth radius in km
    return r * c

def parse_travel_json(job_id, json_content):
    job = IngestionJob.objects.get(id=job_id)
    org = job.organization
    
    try:
        data = json.loads(json_content)
    except Exception as e:
        job.error_message = f"Invalid JSON payload: {str(e)}"
        job.status = 'FAILED'
        job.save()
        return False
        
    # Standard Concur-like payload should be an array of bookings
    if not isinstance(data, list):
        data = [data]
        
    success_count = 0
    fail_count = 0
    row_count = 0
    
    for item in data:
        row_count += 1
        
        # Lineage record
        raw_rec = RawRecord.objects.create(
            ingestion_job=job,
            organization=org,
            source_type='TRAVEL',
            raw_payload=item
        )
        
        try:
            category_type = item.get('trip_type', '').upper()
            tx_date_str = item.get('transaction_date', '')
            tx_date = datetime.strptime(tx_date_str, '%Y-%m-%d').date()
            booking_id = item.get('booking_id', 'UNKNOWN')
            passenger = item.get('passenger_name', 'Employee')
            
            # Anomaly/Warnings lists
            warnings = []
            status = 'DRAFT'
            
            if category_type == 'FLIGHT':
                dep = item.get('departure_airport', '').strip().upper()
                arr = item.get('arrival_airport', '').strip().upper()
                
                # Check for distances
                distance = item.get('distance_km')
                calculated = False
                if distance is not None:
                    distance = Decimal(str(distance))
                else:
                    # Calculate via geocoding
                    dist_val = calculate_haversine(dep, arr)
                    if dist_val is None:
                        # Fallback for unrecognized codes
                        distance = Decimal('800.0') # Default flight length
                        warnings.append(f"Airport codes '{dep}' or '{arr}' not in database. Assumed default flight distance.")
                        status = 'FLAGGED'
                    else:
                        distance = Decimal(str(dist_val))
                        calculated = True
                
                cabin = item.get('cabin_class', '').strip().upper()
                multiplier = CABIN_MULTIPLIERS.get(cabin, CABIN_MULTIPLIERS['DEFAULT'])
                
                if cabin not in CABIN_MULTIPLIERS:
                    warnings.append(f"Unrecognized cabin class '{cabin}'. economy emission factor applied.")
                    status = 'FLAGGED'
                    
                if cabin in ['BUSINESS', 'FIRST']:
                    warnings.append(f"Cabin class is premium ({cabin}). 2.9x/4.0x carbon multiplier applied.")
                    # Let it stay FLAGGED for confirmation, or let it be DRAFT if normal. Let's make it FLAGGED to let analyst review cabin multipliers!
                    status = 'FLAGGED'
                    
                factor = BASE_FLIGHT_FACTOR * multiplier
                co2e = distance * factor
                
                desc = f"Business Flight (Concur: {booking_id}) - {passenger}: {dep} to {arr} ({cabin} Class)"
                if calculated:
                    desc += " [Distance calculated using Great-Circle coordinate lookup]"
                
                NormalizedRecord.objects.create(
                    raw_record=raw_rec,
                    ingestion_job=job,
                    organization=org,
                    transaction_date=tx_date,
                    scope_type='SCOPE_3',
                    category='Flight',
                    description=desc,
                    quantity=distance,
                    unit='km',
                    normalized_quantity=distance,
                    normalized_unit='pkm',  # passenger-km
                    emission_factor=factor.quantize(Decimal('1.000000')),
                    co2e_emissions=co2e.quantize(Decimal('1.000000')),
                    source_system='TRAVEL',
                    status=status,
                    validation_warnings=warnings
                )
                
            elif category_type == 'HOTEL':
                hotel_name = item.get('hotel_name', 'Hotel')
                city = item.get('city', 'Unknown City')
                country = item.get('country', '').strip().upper()
                nights = Decimal(str(item.get('nights', 1)))
                rooms = Decimal(str(item.get('rooms', 1)))
                
                total_nights = nights * rooms
                factor = HOTEL_FACTORS.get(country, HOTEL_FACTORS['DEFAULT'])
                
                if country not in HOTEL_FACTORS:
                    warnings.append(f"Hotel country code '{country}' not in regional factor registry. Fallback global factor used.")
                    status = 'FLAGGED'
                    
                co2e = total_nights * factor
                
                NormalizedRecord.objects.create(
                    raw_record=raw_rec,
                    ingestion_job=job,
                    organization=org,
                    transaction_date=tx_date,
                    scope_type='SCOPE_3',
                    category='Hotel Stay',
                    description=f"Hotel lodging (Concur: {booking_id}) - {passenger} at {hotel_name}, {city}, {country} ({total_nights:.0f} Room-Nights)",
                    quantity=total_nights,
                    unit='room-nights',
                    normalized_quantity=total_nights,
                    normalized_unit='room-nights',
                    emission_factor=factor,
                    co2e_emissions=co2e.quantize(Decimal('1.000000')),
                    source_system='TRAVEL',
                    status=status,
                    validation_warnings=warnings
                )
                
            elif category_type == 'GROUND':
                vehicle = item.get('vehicle_class', '').strip().upper()
                distance = Decimal(str(item.get('distance_km', 50)))
                
                factor = GROUND_FACTORS.get(vehicle, GROUND_FACTORS['DEFAULT'])
                if vehicle not in GROUND_FACTORS:
                    warnings.append(f"Unrecognized ground transport category '{vehicle}'. Used default factor.")
                    status = 'FLAGGED'
                    
                co2e = distance * factor
                
                NormalizedRecord.objects.create(
                    raw_record=raw_rec,
                    ingestion_job=job,
                    organization=org,
                    transaction_date=tx_date,
                    scope_type='SCOPE_3',
                    category='Ground Transport',
                    description=f"Ground transit (Concur: {booking_id}) - {passenger} via rental {vehicle} ({distance:.1f} km)",
                    quantity=distance,
                    unit='km',
                    normalized_quantity=distance,
                    normalized_unit='pkm',
                    emission_factor=factor,
                    co2e_emissions=co2e.quantize(Decimal('1.000000')),
                    source_system='TRAVEL',
                    status=status,
                    validation_warnings=warnings
                )
            else:
                raise ValueError(f"Unsupported travel trip_type: '{category_type}'")
                
            success_count += 1
            
        except Exception as e:
            fail_count += 1
            NormalizedRecord.objects.create(
                raw_record=raw_rec,
                ingestion_job=job,
                organization=org,
                transaction_date=now().date(),
                scope_type='SCOPE_3',
                category='Travel Ingestion Error',
                description=f"Failed parsing travel entry: {str(e)}",
                quantity=Decimal('0.00'),
                unit='UNKNOWN',
                normalized_quantity=Decimal('0.00'),
                normalized_unit='UNKNOWN',
                emission_factor=Decimal('0.00'),
                co2e_emissions=Decimal('0.00'),
                source_system='TRAVEL',
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
