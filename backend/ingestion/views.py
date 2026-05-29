import json
from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from django.db import transaction
from django.db.models import Sum, Count
from django.utils.timezone import now
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from ingestion.models import Organization, Facility, IngestionJob, RawRecord, NormalizedRecord, AuditLog
from ingestion.serializers import (
    OrganizationSerializer, FacilitySerializer, IngestionJobSerializer, 
    NormalizedRecordSerializer, AuditLogSerializer
)
from ingestion.processors import parse_sap_csv, parse_utility_csv, parse_travel_json

class TenantScopedViewSet(viewsets.ModelViewSet):
    """Base ViewSet that automatically scopes queries to the active Organization (tenant)."""
    
    def get_org(self):
        # Retrieve organization from header or query param for multi-tenancy simulation
        org_id = self.request.headers.get('X-Organization-ID') or self.request.query_params.get('org_id')
        if org_id:
            try:
                return Organization.objects.get(id=org_id)
            except (Organization.DoesNotExist, ValueError):
                pass
        # Fallback to the first organization for ease of testing
        first_org = Organization.objects.first()
        if not first_org:
            first_org = Organization.objects.create(name="Acme Industrial Corp")
        return first_org

    def get_queryset(self):
        org = self.get_org()
        return self.queryset.filter(organization=org)

    def perform_create(self, serializer):
        serializer.save(organization=self.get_org())


class OrganizationViewSet(viewsets.ModelViewSet):
    queryset = Organization.objects.all().order_by('id')
    serializer_class = OrganizationSerializer


class FacilityViewSet(TenantScopedViewSet):
    queryset = Facility.objects.all().order_by('id')
    serializer_class = FacilitySerializer


class IngestionJobViewSet(TenantScopedViewSet):
    queryset = IngestionJob.objects.all().order_by('-id')
    serializer_class = IngestionJobSerializer

    @action(detail=False, methods=['POST'], url_path='ingest')
    def ingest_file(self, request):
        org = self.get_org()
        source_type = request.data.get('source_type')
        uploaded_file = request.FILES.get('file')
        raw_json = request.data.get('json_payload') # Support API post directly
        
        if not source_type or source_type not in ['SAP', 'UTILITY', 'TRAVEL']:
            return Response(
                {"error": "Valid source_type ('SAP', 'UTILITY', 'TRAVEL') is required"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
            
        file_name = "API_PAYLOAD.json"
        file_size = 0
        content = ""
        
        if uploaded_file:
            file_name = uploaded_file.name
            file_size = uploaded_file.size
            try:
                content = uploaded_file.read().decode('utf-8')
            except Exception as e:
                return Response(
                    {"error": f"Failed to read uploaded file: {str(e)}"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
        elif raw_json:
            file_name = "concur_travel_api_pull.json"
            content = raw_json if isinstance(raw_json, str) else json.dumps(raw_json)
            file_size = len(content)
        else:
            return Response(
                {"error": "Either file upload or json_payload is required"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
            
        # Create IngestionJob in PENDING state
        job = IngestionJob.objects.create(
            organization=org,
            source_type=source_type,
            file_name=file_name,
            file_size=file_size,
            status='PENDING'
        )
        
        # Run appropriate parser inside transaction
        try:
            with transaction.atomic():
                if source_type == 'SAP':
                    success = parse_sap_csv(job.id, content)
                elif source_type == 'UTILITY':
                    success = parse_utility_csv(job.id, content)
                elif source_type == 'TRAVEL':
                    success = parse_travel_json(job.id, content)
                    
            if success:
                job.refresh_from_db()
                return Response(IngestionJobSerializer(job).data, status=status.HTTP_201_CREATED)
            else:
                return Response(
                    {"error": f"Ingestion failed: {job.error_message}"}, 
                    status=status.HTTP_422_UNPROCESSABLE_ENTITY
                )
        except Exception as e:
            job.status = 'FAILED'
            job.error_message = f"Critical Pipeline Failure: {str(e)}"
            job.save()
            return Response(
                {"error": f"Unexpected Ingestion Error: {str(e)}"}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class NormalizedRecordViewSet(TenantScopedViewSet):
    queryset = NormalizedRecord.objects.all().order_by('-transaction_date', '-id')
    serializer_class = NormalizedRecordSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        status_filter = self.request.query_params.get('status')
        scope_filter = self.request.query_params.get('scope')
        category_filter = self.request.query_params.get('category')
        plant_filter = self.request.query_params.get('plant_code')
        
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        if scope_filter:
            queryset = queryset.filter(scope_type=scope_filter)
        if category_filter:
            queryset = queryset.filter(category=category_filter)
        if plant_filter:
            queryset = queryset.filter(plant_code=plant_filter)
            
        return queryset

    def update(self, request, *args, **kwargs):
        """Strict auditor update endpoint requiring audit reasoning and preventing locked modification."""
        record = self.get_object()
        org = self.get_org()
        
        # Guardrail 1: Enforce audit locks
        if record.status == 'APPROVED':
            return Response(
                {"error": "This record is APPROVED and locked for audit. Edits are strictly prohibited."},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        # Guardrail 2: Require an audit reason
        audit_reason = request.data.get('audit_reason')
        if not audit_reason or len(audit_reason.strip()) < 5:
            return Response(
                {"error": "An explanatory audit_reason (at least 5 characters) is mandatory to modify normalized ESG data."},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        # Snapshot previous state for AuditLog
        prev_values = {
            "quantity": str(record.quantity),
            "unit": record.unit,
            "normalized_quantity": str(record.normalized_quantity),
            "description": record.description,
            "plant_code": record.plant_code,
            "facility_id": record.facility_id,
            "status": record.status,
            "transaction_date": record.transaction_date.isoformat()
        }
        
        # Modify and calculate fields
        qty_str = request.data.get('quantity')
        unit = request.data.get('unit', record.unit)
        plant_code = request.data.get('plant_code', record.plant_code)
        description = request.data.get('description', record.description)
        tx_date_str = request.data.get('transaction_date')
        
        if qty_str is not None:
            new_qty = Decimal(str(qty_str))
            record.quantity = new_qty
            
            # Recalculate normalized quantity and emissions based on original type
            # (In a production system, we'd pull these converters dynamically)
            if record.category in ['Diesel', 'Natural Gas', 'Procurement (Steel)', 'Procurement (Paper)']:
                # Re-apply SAP mappings
                from ingestion.processors.sap import normalize_unit, GL_ACCOUNT_MAPPING
                gl_mapping = {v['category']: v for v in GL_ACCOUNT_MAPPING.values()}
                act = gl_mapping.get(record.category)
                if act:
                    norm_qty, norm_unit = normalize_unit(new_qty, unit, act['standard_unit'])
                    record.normalized_quantity = norm_qty
                    record.normalized_unit = norm_unit
                    record.co2e_emissions = norm_qty * record.emission_factor
            elif record.category == 'Electricity':
                # Re-apply utility MWh/kWh conversion
                norm_qty = new_qty
                if unit.upper() in ['MWH', 'MEGAWATT_HOURS']:
                    norm_qty = new_qty * Decimal('1000.0')
                record.normalized_quantity = norm_qty
                record.co2e_emissions = norm_qty * record.emission_factor
            else:
                # Travel flights, hotel stays, ground
                record.normalized_quantity = new_qty
                record.co2e_emissions = new_qty * record.emission_factor
                
        if unit:
            record.unit = unit
        if plant_code is not None:
            record.plant_code = plant_code
            # Try to resolve facility profile
            fac = Facility.objects.filter(organization=org, plant_code=plant_code.strip()).first()
            if fac:
                record.facility = fac
                # Clear facility warnings if resolved!
                record.validation_warnings = [w for w in record.validation_warnings if "Plant code" not in w]
                # Also recalculate electricity factors if grid changed
                if record.category == 'Electricity':
                    from ingestion.processors.utility import GRID_FACTORS
                    record.emission_factor = GRID_FACTORS.get(fac.grid_region, GRID_FACTORS['DEFAULT'])
                    record.co2e_emissions = record.normalized_quantity * record.emission_factor
            else:
                record.facility = None
                
        if description:
            record.description = description
            
        if tx_date_str:
            record.transaction_date = datetime.strptime(tx_date_str, '%Y-%m-%d').date()
            
        # Clear Suspicious Flags if everything resolved
        if record.status == 'FLAGGED' and not record.validation_warnings:
            record.status = 'DRAFT'
            
        record.save()
        
        # Log to Audit Log
        new_values = {
            "quantity": str(record.quantity),
            "unit": record.unit,
            "normalized_quantity": str(record.normalized_quantity),
            "description": record.description,
            "plant_code": record.plant_code,
            "facility_id": record.facility_id,
            "status": record.status,
            "transaction_date": record.transaction_date.isoformat()
        }
        
        AuditLog.objects.create(
            normalized_record=record,
            organization=org,
            user=request.data.get('user', 'ESG Analyst (Console)'),
            action='UPDATE',
            previous_values=prev_values,
            new_values=new_values,
            reason=audit_reason
        )
        
        return Response(NormalizedRecordSerializer(record).data)

    @action(detail=False, methods=['POST'], url_path='bulk-approve')
    def bulk_approve(self, request):
        org = self.get_org()
        ids = request.data.get('ids', [])
        user = request.data.get('user', 'ESG Analyst (Console)')
        
        if not ids:
            return Response({"error": "No record IDs provided for approval"}, status=status.HTTP_400_BAD_REQUEST)
            
        records = NormalizedRecord.objects.filter(organization=org, id__in=ids)
        approved_count = 0
        
        for record in records:
            if record.status in ['APPROVED', 'REJECTED']:
                continue
                
            prev_status = record.status
            record.status = 'APPROVED'
            record.approved_by = user
            record.approved_at = now()
            record.save()
            
            # Log Audit Trail
            AuditLog.objects.create(
                normalized_record=record,
                organization=org,
                user=user,
                action='APPROVE',
                previous_values={"status": prev_status},
                new_values={"status": "APPROVED", "approved_by": user, "approved_at": record.approved_at.isoformat()},
                reason="Bulk analyst sign-off and audit lock."
            )
            approved_count += 1
            
        return Response({"message": f"Successfully approved and locked {approved_count} records for audit."})

    @action(detail=True, methods=['POST'], url_path='reject')
    def reject_record(self, request, pk=None):
        record = self.get_object()
        org = self.get_org()
        user = request.data.get('user', 'ESG Analyst (Console)')
        audit_reason = request.data.get('audit_reason', 'Analyst rejected this transaction.')
        
        if record.status == 'APPROVED':
            return Response({"error": "Approved records are locked and cannot be rejected."}, status=status.HTTP_400_BAD_REQUEST)
            
        prev_status = record.status
        record.status = 'REJECTED'
        record.save()
        
        AuditLog.objects.create(
            normalized_record=record,
            organization=org,
            user=user,
            action='REJECT',
            previous_values={"status": prev_status},
            new_values={"status": "REJECTED"},
            reason=audit_reason
        )
        return Response(NormalizedRecordSerializer(record).data)


class AuditLogViewSet(TenantScopedViewSet):
    queryset = AuditLog.objects.all().order_by('-timestamp')
    serializer_class = AuditLogSerializer


class AnalyticsView(APIView):
    """Dynamically aggregates emissions metrics for the frontend charts."""
    
    def get_org(self, request):
        org_id = request.headers.get('X-Organization-ID') or request.query_params.get('org_id')
        if org_id:
            try:
                return Organization.objects.get(id=org_id)
            except (Organization.DoesNotExist, ValueError):
                pass
        return Organization.objects.first()

    def get(self, request):
        org = self.get_org(request)
        if not org:
            return Response({"error": "No tenant organization registered."}, status=status.HTTP_400_BAD_REQUEST)
            
        records = NormalizedRecord.objects.filter(organization=org)
        
        # 1. Scope Breakdowns
        scope_sums = records.exclude(status='REJECTED').values('scope_type').annotate(
            total_co2e=Sum('co2e_emissions'),
            count=Count('id')
        )
        scopes = {
            'SCOPE_1': 0.0,
            'SCOPE_2': 0.0,
            'SCOPE_3': 0.0
        }
        for s in scope_sums:
            scopes[s['scope_type']] = float(s['total_co2e'] or 0.0)
            
        # 2. Monthly Emission Trends (Scope-stacked)
        # In sqlite we'll slice strings from date to group. Group by YYYY-MM
        monthly_data = defaultdict(lambda: {'scope1': 0.0, 'scope2': 0.0, 'scope3': 0.0, 'total': 0.0})
        active_records = records.exclude(status='REJECTED')
        
        for rec in active_records:
            month_str = rec.transaction_date.strftime('%Y-%m')
            scope_key = rec.scope_type.lower().replace('_', '') # SCOPE_1 -> scope1
            val = float(rec.co2e_emissions or 0.0)
            monthly_data[month_str][scope_key] += val
            monthly_data[month_str]['total'] += val
            
        monthly_trend = []
        for m, s_vals in sorted(monthly_data.items()):
            monthly_trend.append({
                'month': m,
                'scope1': round(s_vals['scope1'], 2),
                'scope2': round(s_vals['scope2'], 2),
                'scope3': round(s_vals['scope3'], 2),
                'total': round(s_vals['total'], 2),
            })
            
        # 3. Category Breakdown (Pie chart)
        category_sums = active_records.values('category').annotate(
            total_co2e=Sum('co2e_emissions')
        ).order_by('-total_co2e')
        
        categories = []
        for cat in category_sums:
            categories.append({
                'name': cat['category'],
                'value': round(float(cat['total_co2e'] or 0.0), 2)
            })
            
        # 4. Facility Breakdown (Bar chart)
        facility_sums = active_records.values('plant_code', 'facility__plant_name').annotate(
            total_co2e=Sum('co2e_emissions')
        ).order_by('-total_co2e')
        
        facilities = []
        for fac in facility_sums:
            facilities.append({
                'plant_code': fac['plant_code'] or 'UNRESOLVED',
                'name': fac['facility__plant_name'] or 'Unregistered Facility',
                'co2e': round(float(fac['total_co2e'] or 0.0), 2)
            })
            
        # 5. Pipeline completeness KPI metrics
        status_counts = records.values('status').annotate(count=Count('id'))
        states = {
            'DRAFT': 0,
            'FLAGGED': 0,
            'APPROVED': 0,
            'REJECTED': 0
        }
        total_records = 0
        for st in status_counts:
            states[st['status']] = st['count']
            if st['status'] != 'REJECTED':
                total_records += st['count']
                
        completeness = 100.0
        if total_records > 0:
            completeness = (states['APPROVED'] / total_records) * 100.0
            
        return Response({
            "organization": org.name,
            "scopes": scopes,
            "monthly_trend": monthly_trend,
            "category_breakdown": categories,
            "facility_breakdown": facilities,
            "data_health": {
                "completeness_score": round(completeness, 1),
                "draft_count": states['DRAFT'],
                "flagged_count": states['FLAGGED'],
                "approved_count": states['APPROVED'],
                "rejected_count": states['REJECTED']
            }
        })
