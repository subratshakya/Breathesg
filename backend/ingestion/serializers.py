from rest_framework import serializers
from ingestion.models import Organization, Facility, IngestionJob, RawRecord, NormalizedRecord, AuditLog

class OrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = '__all__'


class FacilitySerializer(serializers.ModelSerializer):
    class Meta:
        model = Facility
        fields = '__all__'


class IngestionJobSerializer(serializers.ModelSerializer):
    class Meta:
        model = IngestionJob
        fields = '__all__'


class RawRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = RawRecord
        fields = '__all__'


class NormalizedRecordSerializer(serializers.ModelSerializer):
    raw_payload = serializers.SerializerMethodField()
    facility_details = serializers.SerializerMethodField()
    
    class Meta:
        model = NormalizedRecord
        fields = '__all__'
        read_only_fields = [
            'scope_type', 'category', 'co2e_emissions', 
            'normalized_quantity', 'normalized_unit', 
            'emission_factor', 'source_system', 
            'validation_warnings', 'approved_by', 'approved_at', 
            'created_at', 'updated_at'
        ]

    def get_raw_payload(self, obj):
        if obj.raw_record:
            return obj.raw_record.raw_payload
        return None

    def get_facility_details(self, obj):
        if obj.facility:
            return {
                'name': obj.facility.plant_name,
                'location': obj.facility.location,
                'grid_region': obj.facility.grid_region
            }
        return None


class AuditLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = AuditLog
        fields = '__all__'
