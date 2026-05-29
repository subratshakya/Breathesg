from django.db import models

class Organization(models.Model):
    """Tenant organization."""
    name = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Facility(models.Model):
    """Facility or plant. Maps codes (e.g., WERKS DE10) to emission regions."""
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='facilities')
    plant_code = models.CharField(max_length=50)
    plant_name = models.CharField(max_length=255)
    location = models.CharField(max_length=255, help_text="e.g., Frankfurt, Germany or New York, US")
    grid_region = models.CharField(
        max_length=100, 
        help_text="e.g., eGRID:NYUP, Grid:Germany, Grid:UK. Used to resolve Scope 2 grid emission factors."
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('organization', 'plant_code')

    def __str__(self):
        return f"{self.plant_code} - {self.plant_name} ({self.organization.name})"


class IngestionJob(models.Model):
    """Tracks raw ingestion runs."""
    SOURCE_CHOICES = (
        ('SAP', 'SAP ERP Fuel & Procurement'),
        ('UTILITY', 'Utility electricity bills'),
        ('TRAVEL', 'Corporate travel platform'),
    )
    STATUS_CHOICES = (
        ('PENDING', 'Pending Processing'),
        ('SUCCESS', 'Successfully Processed'),
        ('FAILED', 'Failed Processing'),
    )
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='ingestion_jobs')
    source_type = models.CharField(max_length=20, choices=SOURCE_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    file_name = models.CharField(max_length=255)
    file_size = models.IntegerField(help_text="File size in bytes")
    total_rows = models.IntegerField(default=0)
    successful_rows = models.IntegerField(default=0)
    failed_rows = models.IntegerField(default=0)
    error_message = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.source_type} Job #{self.id} ({self.status}) - {self.organization.name}"


class RawRecord(models.Model):
    """Audit lineage: keeps the exact original payload as ingested."""
    ingestion_job = models.ForeignKey(IngestionJob, on_delete=models.CASCADE, related_name='raw_records')
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    source_type = models.CharField(max_length=20)
    raw_payload = models.JSONField(help_text="Original JSON representation of the row")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Raw Record #{self.id} (Job #{self.ingestion_job.id})"


class NormalizedRecord(models.Model):
    """Normalized emissions calculations table ready for review and sign-off."""
    SCOPE_CHOICES = (
        ('SCOPE_1', 'Scope 1 - Direct Emissions'),
        ('SCOPE_2', 'Scope 2 - Indirect Energy Emissions'),
        ('SCOPE_3', 'Scope 3 - Other Indirect Emissions'),
    )
    STATUS_CHOICES = (
        ('DRAFT', 'Draft'),
        ('APPROVED', 'Approved (Locked)'),
        ('FLAGGED', 'Flagged (Suspicious)'),
        ('REJECTED', 'Rejected'),
    )
    raw_record = models.ForeignKey(RawRecord, on_delete=models.SET_NULL, null=True, blank=True, related_name='normalized_records')
    ingestion_job = models.ForeignKey(IngestionJob, on_delete=models.SET_NULL, null=True, blank=True, related_name='normalized_records')
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='normalized_records')
    
    transaction_date = models.DateField(help_text="Normalized activity occurrence date")
    scope_type = models.CharField(max_length=15, choices=SCOPE_CHOICES)
    category = models.CharField(max_length=50, help_text="e.g., Diesel, Electricity, Flights, Procurement, Hotels")
    description = models.TextField()
    
    # Original Activity quantities
    quantity = models.DecimalField(max_digits=18, decimal_places=4)
    unit = models.CharField(max_length=50, help_text="Original unit: e.g., Liters, Gallons, MWh, Miles")
    
    # Standardized Activity quantities
    normalized_quantity = models.DecimalField(max_digits=18, decimal_places=4)
    normalized_unit = models.CharField(max_length=50, help_text="SI standardized unit: e.g., Liters, kWh, pkm")
    
    # Calculations
    emission_factor = models.DecimalField(max_digits=12, decimal_places=6, help_text="tCO2e per normalized unit")
    co2e_emissions = models.DecimalField(max_digits=18, decimal_places=6, help_text="Calculated total emissions in metric tons (tCO2e)")
    
    # Context columns
    source_system = models.CharField(max_length=20, default='SAP')
    plant_code = models.CharField(max_length=50, blank=True, null=True, help_text="Plant/facility code as ingested")
    facility = models.ForeignKey(Facility, on_delete=models.SET_NULL, null=True, blank=True, related_name='records')
    
    # Workflow states
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='DRAFT')
    review_notes = models.TextField(blank=True, null=True, help_text="Auditor/Analyst review comments")
    validation_warnings = models.JSONField(default=list, blank=True, help_text="List of triggers why record is flagged")
    
    # Lock details
    approved_by = models.CharField(max_length=100, blank=True, null=True)
    approved_at = models.DateTimeField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.category} ({self.co2e_emissions} tCO2e) - {self.status} - {self.organization.name}"


class AuditLog(models.Model):
    """Immutable audit trail for regulatory verification."""
    normalized_record = models.ForeignKey(NormalizedRecord, on_delete=models.CASCADE, related_name='audit_logs')
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    user = models.CharField(max_length=100, help_text="Username of the analyst performing modification")
    action = models.CharField(max_length=50, help_text="e.g. CREATE, UPDATE, APPROVE, REJECT")
    previous_values = models.JSONField(help_text="Historical state snapshot")
    new_values = models.JSONField(help_text="Updated state snapshot")
    reason = models.TextField(help_text="Why the change was made - MANDATORY for edits")
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.action} on Record #{self.normalized_record_id} by {self.user}"
