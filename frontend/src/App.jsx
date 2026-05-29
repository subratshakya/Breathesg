import React, { useState, useEffect, useRef, useCallback } from 'react';
import { 
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, 
  AreaChart, Area, PieChart, Pie, Cell 
} from 'recharts';
import { 
  LayoutDashboard, FileSpreadsheet, ClipboardList, History, Building2, 
  Upload, CheckCircle, AlertTriangle, XCircle, ArrowRight, ShieldAlert, 
  Edit3, Trash2, Check, RefreshCw, FileUp, X 
} from 'lucide-react';

// Use relative path in production (same origin), env var for custom backends
const API_BASE = import.meta.env.VITE_API_URL || '/api';

export default function App() {
  const [activeTab, setActiveTab] = useState('dashboard');
  const [organizations, setOrganizations] = useState([]);
  const [selectedOrgId, setSelectedOrgId] = useState('');
  const [orgName, setOrgName] = useState('Acme Industrial Corp');
  
  // Dynamic Data Lists
  const [records, setRecords] = useState([]);
  const [analytics, setAnalytics] = useState(null);
  const [jobs, setJobs] = useState([]);
  const [facilities, setFacilities] = useState([]);
  const [auditLogs, setAuditLogs] = useState([]);
  
  // Selection / Queue states
  const [selectedRecord, setSelectedRecord] = useState(null);
  const [selectedRowIds, setSelectedRowIds] = useState([]);
  const [filters, setFilters] = useState({ status: '', scope: '', plant: '' });
  
  // Drawer Editing Form state
  const [editForm, setEditForm] = useState({
    quantity: '',
    unit: '',
    plant_code: '',
    description: '',
    transaction_date: ''
  });
  const [auditReason, setAuditReason] = useState('');
  const [auditorName, setAuditorName] = useState('Jane Smith (Auditor)');
  const [formError, setFormError] = useState('');

  // Pipeline Upload states
  const [uploading, setUploading] = useState(false);
  const [toasts, setToasts] = useState([]);
  const fileInputRef = useRef(null);
  const [dragOver, setDragOver] = useState(false);
  const [uploadSourceType, setUploadSourceType] = useState('SAP');
  const [uploadSuccess, setUploadSuccess] = useState('');
  const [uploadError, setUploadError] = useState('');

  // Initial Fetch Setup
  useEffect(() => {
    fetchOrganizations();
  }, []);

  // Reload when switching organizations
  useEffect(() => {
    if (selectedOrgId) {
      const activeOrg = organizations.find(o => o.id == selectedOrgId);
      if (activeOrg) setOrgName(activeOrg.name);
      
      fetchAllData();
    }
  }, [selectedOrgId, activeTab, filters]);

  const fetchOrganizations = async () => {
    try {
      const res = await fetch(`${API_BASE}/organizations/`);
      const data = await res.json();
      setOrganizations(data);
      if (data.length > 0) {
        setSelectedOrgId(data[0].id);
        setOrgName(data[0].name);
      }
    } catch (err) {
      console.error("Failed to load tenants", err);
    }
  };

  const fetchAllData = () => {
    fetchAnalytics();
    fetchRecords();
    fetchJobs();
    fetchFacilities();
    fetchAuditLogs();
  };

  // Toast notification system
  const addToast = (type, message) => {
    const id = Date.now();
    setToasts(prev => [...prev, { id, type, message }]);
    setTimeout(() => setToasts(prev => prev.filter(t => t.id !== id)), 4000);
  };

  const fetchAnalytics = async () => {
    try {
      const res = await fetch(`${API_BASE}/analytics/?org_id=${selectedOrgId}`);
      const data = await res.json();
      setAnalytics(data);
    } catch (err) {
      console.error(err);
    }
  };

  const fetchRecords = async () => {
    try {
      let url = `${API_BASE}/records/?org_id=${selectedOrgId}`;
      if (filters.status) url += `&status=${filters.status}`;
      if (filters.scope) url += `&scope=${filters.scope}`;
      if (filters.plant) url += `&plant_code=${filters.plant}`;
      
      const res = await fetch(url);
      const data = await res.json();
      setRecords(data);
    } catch (err) {
      console.error(err);
    }
  };

  const fetchJobs = async () => {
    try {
      const res = await fetch(`${API_BASE}/jobs/?org_id=${selectedOrgId}`);
      const data = await res.json();
      setJobs(data);
    } catch (err) {
      console.error(err);
    }
  };

  const fetchFacilities = async () => {
    try {
      const res = await fetch(`${API_BASE}/facilities/?org_id=${selectedOrgId}`);
      const data = await res.json();
      setFacilities(data);
    } catch (err) {
      console.error(err);
    }
  };

  const fetchAuditLogs = async () => {
    try {
      const res = await fetch(`${API_BASE}/audit-logs/?org_id=${selectedOrgId}`);
      const data = await res.json();
      setAuditLogs(data);
    } catch (err) {
      console.error(err);
    }
  };

  // Trigger file ingestion
  const handleIngestPayload = async (sourceType, payloadStr) => {
    setUploading(true);
    setUploadError('');
    setUploadSuccess('');
    try {
      const formData = new FormData();
      formData.append('source_type', sourceType);
      formData.append('org_id', selectedOrgId);
      
      const blob = new Blob([payloadStr], { type: 'text/plain' });
      const file = new File([blob], sourceType === 'TRAVEL' ? 'api_pull.json' : 'portal_export.csv');
      formData.append('file', file);

      const res = await fetch(`${API_BASE}/jobs/ingest/`, {
        method: 'POST',
        headers: { 'X-Organization-ID': selectedOrgId.toString() },
        body: formData
      });
      const data = await res.json();
      
      if (res.ok) {
        addToast('success', `Ingestion Job #${data.id} complete — ${data.successful_rows} rows processed.`);
        setUploadSuccess(`Job #${data.id}: ${data.successful_rows} rows ingested successfully.`);
        fetchAllData();
      } else {
        addToast('error', data.error || 'Ingestion failed');
        setUploadError(data.error || 'Failed to ingest data');
      }
    } catch (err) {
      addToast('error', 'Network error: could not reach API server.');
      setUploadError('Network connection error: failed to reach Django API.');
    } finally {
      setUploading(false);
    }
  };

  // Real file upload handler
  const handleFileUpload = async (file) => {
    if (!file) return;
    setUploading(true);
    setUploadError('');
    setUploadSuccess('');
    try {
      const formData = new FormData();
      formData.append('source_type', uploadSourceType);
      formData.append('file', file);

      const res = await fetch(`${API_BASE}/jobs/ingest/`, {
        method: 'POST',
        headers: { 'X-Organization-ID': selectedOrgId.toString() },
        body: formData
      });
      const data = await res.json();
      if (res.ok) {
        addToast('success', `"${file.name}" ingested — ${data.successful_rows} rows processed.`);
        setUploadSuccess(`Job #${data.id}: ${file.name} — ${data.successful_rows} rows.`);
        fetchAllData();
      } else {
        addToast('error', data.error || 'File ingestion failed');
        setUploadError(data.error || 'Failed to process file');
      }
    } catch (err) {
      addToast('error', 'Network error uploading file.');
      setUploadError('Network error uploading file.');
    } finally {
      setUploading(false);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file) handleFileUpload(file);
  };

  // Seed / Simulation Generators
  const simulateSAP = () => {
    const csv = 
`BUKRS,BELNR,HKONT,BUDAT,MENGE,MEINS,WRBTR,WERKS
DE10,200041,521010,20260510,18500,L,26300.00,DE10
DE10,200042,521020,12.05.2026,3800,M3,7200.00,DE10
DE10,200043,521010,20260515,650,GAL,1200.00,US20
DE10,200044,521010,20260516,8400,L,12500.00,JP90`; // Triggers a Warning due to unregistered plant JP90
    handleIngestPayload('SAP', csv);
  };

  const simulateUtility = () => {
    const csv = 
`Utility Provider,Account Number,Meter ID,Billing Start Date,Billing End Date,Total Consumption,Consumption Unit,Peak Demand,Plant Code
ConEd,ACT-55019,MTR-8819,04/15/2026,05/14/2026,115000,kWh,120,GB30
ConEd,ACT-55019,MTR-8819,04/15/2026,05/14/2026,220,MWh,480,US20`; // Triggers Warning due to MWh > 100,000 baseline
    handleIngestPayload('UTILITY', csv);
  };

  const simulateTravel = () => {
    const json = [
      {
        "trip_type": "FLIGHT",
        "booking_id": "B3001",
        "passenger_name": "Sarah Jenkins",
        "departure_airport": "JFK",
        "arrival_airport": "LHR",
        "cabin_class": "Business", // Business multiplier flag
        "transaction_date": "2026-05-18"
      },
      {
        "trip_type": "HOTEL",
        "booking_id": "B3002",
        "passenger_name": "Sarah Jenkins",
        "hotel_name": "Intercontinental Berlin",
        "city": "Berlin",
        "country": "DE",
        "nights": 6,
        "rooms": 1,
        "transaction_date": "2026-05-20"
      }
    ];
    handleIngestPayload('TRAVEL', JSON.stringify(json));
  };

  // Queue Workflow Operations
  const handleSelectRow = (id) => {
    if (selectedRowIds.includes(id)) {
      setSelectedRowIds(selectedRowIds.filter(x => x !== id));
    } else {
      setSelectedRowIds([...selectedRowIds, id]);
    }
  };

  const handleSelectAll = (e) => {
    if (e.target.checked) {
      setSelectedRowIds(records.filter(r => r.status !== 'APPROVED').map(r => r.id));
    } else {
      setSelectedRowIds([]);
    }
  };

  const handleBulkApprove = async () => {
    if (selectedRowIds.length === 0) return;
    try {
      const res = await fetch(`${API_BASE}/records/bulk-approve/?org_id=${selectedOrgId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ids: selectedRowIds,
          user: auditorName
        })
      });
      if (res.ok) {
        setSelectedRowIds([]);
        fetchAllData();
      }
    } catch (err) {
      console.error(err);
    }
  };

  const handleSingleApprove = async (id) => {
    try {
      const res = await fetch(`${API_BASE}/records/bulk-approve/?org_id=${selectedOrgId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ids: [id],
          user: auditorName
        })
      });
      if (res.ok) {
        if (selectedRecord && selectedRecord.id === id) {
          setSelectedRecord(null);
        }
        fetchAllData();
      }
    } catch (err) {
      console.error(err);
    }
  };

  const handleReject = async (id, reason) => {
    try {
      const res = await fetch(`${API_BASE}/records/${id}/reject/?org_id=${selectedOrgId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user: auditorName,
          audit_reason: reason
        })
      });
      if (res.ok) {
        setSelectedRecord(null);
        fetchAllData();
      }
    } catch (err) {
      console.error(err);
    }
  };

  // Open Edit panel
  const handleOpenDrawer = (record) => {
    setSelectedRecord(record);
    setEditForm({
      quantity: record.quantity,
      unit: record.unit,
      plant_code: record.plant_code || '',
      description: record.description,
      transaction_date: record.transaction_date
    });
    setAuditReason('');
    setFormError('');
  };

  // Save Manual Adjustments
  const handleSaveChanges = async (e) => {
    e.preventDefault();
    setFormError('');
    if (!auditReason || auditReason.trim().length < 5) {
      setFormError("A detailed audit reason (at least 5 characters) is mandatory to log changes.");
      return;
    }
    
    try {
      const res = await fetch(`${API_BASE}/records/${selectedRecord.id}/?org_id=${selectedOrgId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ...editForm,
          audit_reason: auditReason,
          user: auditorName
        })
      });
      
      const data = await res.json();
      if (res.ok) {
        setSelectedRecord(null);
        fetchAllData();
      } else {
        setFormError(data.error || "Failed to update record.");
      }
    } catch (err) {
      setFormError("Network error: failed to submit changes.");
    }
  };

  // Chart Color Palettes
  const COLORS_PIE = [
    '#f59e0b', // Scope 1 - Amber
    '#06b6d4', // Scope 2 - Cyan
    '#6366f1', // Scope 3 - Indigo
    '#10b981', // Emerald
    '#a855f7'  // Purple
  ];

  return (
    <div className="app-container">
      {/* --- Sidebar Navigation --- */}
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-icon">B</div>
          <h1 className="brand-text">Breathe ESG</h1>
        </div>
        
        <ul className="nav-list">
          <li 
            className={`nav-item ${activeTab === 'dashboard' ? 'active' : ''}`}
            onClick={() => setActiveTab('dashboard')}
          >
            <LayoutDashboard size={20} />
            <span>Dashboard</span>
          </li>
          <li 
            className={`nav-item ${activeTab === 'queue' ? 'active' : ''}`}
            onClick={() => setActiveTab('queue')}
          >
            <ClipboardList size={20} />
            <span>Review Queue</span>
          </li>
          <li 
            className={`nav-item ${activeTab === 'ingest' ? 'active' : ''}`}
            onClick={() => setActiveTab('ingest')}
          >
            <Upload size={20} />
            <span>Data Ingestion</span>
          </li>
          <li 
            className={`nav-item ${activeTab === 'audit' ? 'active' : ''}`}
            onClick={() => setActiveTab('audit')}
          >
            <History size={20} />
            <span>Audit Trail</span>
          </li>
          <li 
            className={`nav-item ${activeTab === 'facilities' ? 'active' : ''}`}
            onClick={() => setActiveTab('facilities')}
          >
            <Building2 size={20} />
            <span>Facilities Lookup</span>
          </li>
        </ul>

        {/* Tenant Switching System */}
        <div className="tenant-selector">
          <span className="tenant-label">Corporate Tenant</span>
          <select 
            value={selectedOrgId} 
            onChange={(e) => setSelectedOrgId(e.target.value)}
            className="tenant-select"
          >
            {organizations.map(org => (
              <option key={org.id} value={org.id}>{org.name}</option>
            ))}
          </select>
        </div>
      </aside>

      {/* --- Main Dashboard Container --- */}
      <main className="main-content">
        <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '32px' }}>
          <div>
            <h2 style={{ fontSize: '28px', fontWeight: '700' }}>
              {activeTab === 'dashboard' && 'Carbon Accounting Hub'}
              {activeTab === 'queue' && 'Auditable Review Queue'}
              {activeTab === 'ingest' && 'Automated Ingestion Pipelines'}
              {activeTab === 'audit' && 'Immutable Audit Logs'}
              {activeTab === 'facilities' && 'Facility Plants Profile'}
            </h2>
            <p style={{ color: 'var(--text-secondary)', fontSize: '14px', marginTop: '4px' }}>
              Corporate Organization: <strong style={{ color: 'var(--accent)' }}>{orgName}</strong>
            </p>
          </div>

          <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
            <span style={{ fontSize: '13px', color: 'var(--text-muted)' }}>Signing User:</span>
            <input 
              type="text" 
              value={auditorName} 
              onChange={(e) => setAuditorName(e.target.value)}
              className="form-input" 
              style={{ width: '200px', padding: '8px 12px', background: 'rgba(255,255,255,0.04)' }}
            />
            <button className="btn btn-secondary" onClick={fetchAllData} title="Force Refresh Data">
              <RefreshCw size={16} />
            </button>
          </div>
        </header>

        {/* --- TAB 1: DASHBOARD --- */}
        {activeTab === 'dashboard' && analytics && (
          <div>
            {/* KPI Cards Grid */}
            <div className="kpi-grid">
              <div className="glass-panel kpi-card scope1">
                <h4 className="kpi-title">Scope 1 - Direct</h4>
                <div className="kpi-value">
                  {analytics.scopes.SCOPE_1.toLocaleString(undefined, { maximumFractionDigits: 1 })}
                  <span className="kpi-unit">tCO2e</span>
                </div>
                <div className="kpi-sub">Diesel & natural gas combustion</div>
              </div>

              <div className="glass-panel kpi-card scope2">
                <h4 className="kpi-title">Scope 2 - Energy</h4>
                <div className="kpi-value">
                  {analytics.scopes.SCOPE_2.toLocaleString(undefined, { maximumFractionDigits: 1 })}
                  <span className="kpi-unit">tCO2e</span>
                </div>
                <div className="kpi-sub">Grid electricity pro-rata utility bills</div>
              </div>

              <div className="glass-panel kpi-card scope3">
                <h4 className="kpi-title">Scope 3 - Indirect</h4>
                <div className="kpi-value">
                  {analytics.scopes.SCOPE_3.toLocaleString(undefined, { maximumFractionDigits: 1 })}
                  <span className="kpi-unit">tCO2e</span>
                </div>
                <div className="kpi-sub">Travel bookings & steel/paper spend</div>
              </div>

              <div className="glass-panel kpi-card total">
                <h4 className="kpi-title">Total Emissions</h4>
                <div className="kpi-value" style={{ color: 'var(--accent)' }}>
                  {(analytics.scopes.SCOPE_1 + analytics.scopes.SCOPE_2 + analytics.scopes.SCOPE_3).toLocaleString(undefined, { maximumFractionDigits: 1 })}
                  <span className="kpi-unit">tCO2e</span>
                </div>
                <div className="kpi-sub">Aggregated across all registered facilities</div>
              </div>
            </div>

            {/* Dynamic Charts Grid */}
            <div className="analytics-grid">
              {/* Stacked Monthly Area Chart */}
              <div className="glass-panel chart-panel">
                <div className="chart-header">
                  <h3 style={{ fontSize: '18px' }}>Emissions Trend (Stacked tCO2e)</h3>
                </div>
                <div style={{ flex: 1, minHeight: '300px' }}>
                  {analytics.monthly_trend.length > 0 ? (
                    <ResponsiveContainer width="100%" height="100%">
                      <AreaChart data={analytics.monthly_trend} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
                        <defs>
                          <linearGradient id="colorS1" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="5%" stopColor="var(--scope1)" stopOpacity={0.4}/>
                            <stop offset="95%" stopColor="var(--scope1)" stopOpacity={0}/>
                          </linearGradient>
                          <linearGradient id="colorS2" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="5%" stopColor="var(--scope2)" stopOpacity={0.4}/>
                            <stop offset="95%" stopColor="var(--scope2)" stopOpacity={0}/>
                          </linearGradient>
                          <linearGradient id="colorS3" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="5%" stopColor="var(--scope3)" stopOpacity={0.4}/>
                            <stop offset="95%" stopColor="var(--scope3)" stopOpacity={0}/>
                          </linearGradient>
                        </defs>
                        <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                        <XAxis dataKey="month" stroke="var(--text-secondary)" fontSize={12} />
                        <YAxis stroke="var(--text-secondary)" fontSize={12} />
                        <Tooltip contentStyle={{ background: '#161b26', border: 'var(--border-glass)', color: 'white' }} />
                        <Legend wrapperStyle={{ color: 'white' }} />
                        <Area type="monotone" dataKey="scope1" name="Scope 1 (Direct)" stroke="var(--scope1)" fillOpacity={1} fill="url(#colorS1)" stackId="1" />
                        <Area type="monotone" dataKey="scope2" name="Scope 2 (Electricity)" stroke="var(--scope2)" fillOpacity={1} fill="url(#colorS2)" stackId="1" />
                        <Area type="monotone" dataKey="scope3" name="Scope 3 (Travel/Spend)" stroke="var(--scope3)" fillOpacity={1} fill="url(#colorS3)" stackId="1" />
                      </AreaChart>
                    </ResponsiveContainer>
                  ) : (
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'var(--text-muted)' }}>
                      No historical metrics seeded. Go to Ingest and simulate files!
                    </div>
                  )}
                </div>
              </div>

              {/* Data Completeness KPI Circular progress */}
              <div className="glass-panel chart-panel" style={{ justifyContent: 'center' }}>
                <h3 style={{ fontSize: '18px', textAlign: 'center', marginBottom: '24px' }}>Data Completeness</h3>
                
                <div 
                  className="completeness-circle" 
                  style={{
                    background: `conic-gradient(var(--accent) ${analytics.data_health.completeness_score}%, rgba(255,255,255,0.05) ${analytics.data_health.completeness_score}%)`
                  }}
                >
                  <div className="completeness-circle-inner">
                    <span style={{ fontSize: '32px', fontWeight: '800', fontFamily: 'var(--font-display)', color: 'white' }}>
                      {analytics.data_health.completeness_score}%
                    </span>
                    <span style={{ fontSize: '11px', color: 'var(--text-secondary)', textTransform: 'uppercase', marginTop: '4px' }}>
                      Audit Signed
                    </span>
                  </div>
                </div>

                <div style={{ marginTop: '24px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '13px' }}>
                    <span style={{ color: 'var(--text-secondary)' }}>Locked (Approved) rows</span>
                    <strong style={{ color: 'var(--accent)' }}>{analytics.data_health.approved_count}</strong>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '13px' }}>
                    <span style={{ color: 'var(--text-secondary)' }}>Flagged (Anomaly warnings)</span>
                    <strong style={{ color: 'var(--warning)' }}>{analytics.data_health.flagged_count}</strong>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '13px' }}>
                    <span style={{ color: 'var(--text-secondary)' }}>Pending (Drafts)</span>
                    <strong style={{ color: 'var(--info)' }}>{analytics.data_health.draft_count}</strong>
                  </div>
                </div>
              </div>
            </div>

            {/* Bottom Row Charts */}
            <div className="analytics-grid" style={{ gridTemplateColumns: '1fr 1fr' }}>
              {/* Category Breakdown Bar Chart */}
              <div className="glass-panel chart-panel">
                <h3 style={{ fontSize: '18px', marginBottom: '20px' }}>Category Footprint (tCO2e)</h3>
                <div style={{ flex: 1, minHeight: '260px' }}>
                  {analytics.category_breakdown.length > 0 ? (
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={analytics.category_breakdown}>
                        <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                        <XAxis dataKey="name" stroke="var(--text-secondary)" fontSize={11} />
                        <YAxis stroke="var(--text-secondary)" fontSize={12} />
                        <Tooltip contentStyle={{ background: '#161b26', border: 'var(--border-glass)' }} />
                        <Bar dataKey="value" name="Carbon Output (tCO2e)">
                          {analytics.category_breakdown.map((entry, index) => (
                            <Cell key={`cell-${index}`} fill={COLORS_PIE[index % COLORS_PIE.length]} />
                          ))}
                        </Bar>
                      </BarChart>
                    </ResponsiveContainer>
                  ) : (
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'var(--text-muted)' }}>
                      No categorical share found.
                    </div>
                  )}
                </div>
              </div>

              {/* Plant Breakdown */}
              <div className="glass-panel chart-panel">
                <h3 style={{ fontSize: '18px', marginBottom: '20px' }}>Emissions by Operational Facility</h3>
                <div style={{ flex: 1, minHeight: '260px' }}>
                  {analytics.facility_breakdown.length > 0 ? (
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={analytics.facility_breakdown}>
                        <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                        <XAxis dataKey="plant_code" stroke="var(--text-secondary)" fontSize={12} />
                        <YAxis stroke="var(--text-secondary)" fontSize={12} />
                        <Tooltip contentStyle={{ background: '#161b26', border: 'var(--border-glass)' }} />
                        <Bar dataKey="co2e" fill="var(--accent)" name="Facility Carbon (tCO2e)" radius={[4, 4, 0, 0]} />
                      </BarChart>
                    </ResponsiveContainer>
                  ) : (
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'var(--text-muted)' }}>
                      No facility allocations.
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* --- TAB 2: REVIEW QUEUE --- */}
        {activeTab === 'queue' && (
          <div className="glass-panel">
            {/* Table Filters and Queue Operations */}
            <div className="queue-header-bar">
              <div className="filter-bar">
                <select 
                  value={filters.status}
                  onChange={(e) => setFilters({ ...filters, status: e.target.value })}
                  className="filter-select"
                >
                  <option value="">All Review Statuses</option>
                  <option value="DRAFT">Draft Queue</option>
                  <option value="FLAGGED">Flagged Anomalies</option>
                  <option value="APPROVED">Approved (Locked)</option>
                  <option value="REJECTED">Rejected List</option>
                </select>

                <select 
                  value={filters.scope}
                  onChange={(e) => setFilters({ ...filters, scope: e.target.value })}
                  className="filter-select"
                >
                  <option value="">All Emission Scopes</option>
                  <option value="SCOPE_1">Scope 1 - Direct</option>
                  <option value="SCOPE_2">Scope 2 - Grid</option>
                  <option value="SCOPE_3">Scope 3 - Procurement/Travel</option>
                </select>

                <select 
                  value={filters.plant}
                  onChange={(e) => setFilters({ ...filters, plant: e.target.value })}
                  className="filter-select"
                >
                  <option value="">All Facilities</option>
                  {facilities.map(fac => (
                    <option key={fac.id} value={fac.plant_code}>{fac.plant_code} - {fac.plant_name}</option>
                  ))}
                  <option value="JP90">JP90 (Unregistered)</option>
                </select>
              </div>

              {selectedRowIds.length > 0 && (
                <button className="btn btn-primary" onClick={handleBulkApprove}>
                  <CheckCircle size={16} />
                  <span>Bulk Sign-off Selected ({selectedRowIds.length})</span>
                </button>
              )}
            </div>

            {/* Ingestion Table */}
            <div className="table-container">
              {records.length > 0 ? (
                <table className="esg-table">
                  <thead>
                    <tr>
                      <th style={{ width: '40px' }}>
                        <input 
                          type="checkbox" 
                          onChange={handleSelectAll} 
                          checked={selectedRowIds.length === records.filter(r => r.status !== 'APPROVED').length && records.filter(r => r.status !== 'APPROVED').length > 0} 
                        />
                      </th>
                      <th>Activity Date</th>
                      <th>Scope / Source</th>
                      <th>Category & Description</th>
                      <th style={{ textAlign: 'right' }}>Ingested Qty</th>
                      <th style={{ textAlign: 'right' }}>Carbon (tCO2e)</th>
                      <th>Workflow Status</th>
                      <th style={{ textAlign: 'center' }}>Review</th>
                    </tr>
                  </thead>
                  <tbody>
                    {records.map(rec => (
                      <tr 
                        key={rec.id} 
                        className={
                          rec.status === 'FLAGGED' ? 'row-flagged' : rec.status === 'REJECTED' ? 'row-rejected' : ''
                        }
                      >
                        <td>
                          {rec.status !== 'APPROVED' && rec.status !== 'REJECTED' && (
                            <input 
                              type="checkbox" 
                              checked={selectedRowIds.includes(rec.id)}
                              onChange={() => handleSelectRow(rec.id)}
                              onClick={(e) => e.stopPropagation()}
                            />
                          )}
                        </td>
                        <td style={{ fontWeight: '500' }}>{rec.transaction_date}</td>
                        <td>
                          <div style={{ display: 'flex', flexDirection: 'column' }}>
                            <span style={{ fontSize: '12px', fontWeight: '700', color: rec.scope_type === 'SCOPE_1' ? 'var(--scope1)' : rec.scope_type === 'SCOPE_2' ? 'var(--scope2)' : 'var(--scope3)' }}>
                              {rec.scope_type}
                            </span>
                            <span style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>
                              {rec.source_system} Ingest
                            </span>
                          </div>
                        </td>
                        <td>
                          <div style={{ display: 'flex', flexDirection: 'column', maxWidth: '350px' }}>
                            <strong style={{ fontSize: '14px', color: 'white' }}>{rec.category}</strong>
                            <span style={{ fontSize: '12px', color: 'var(--text-secondary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                              {rec.description}
                            </span>
                            {rec.facility_details ? (
                              <span style={{ fontSize: '11px', color: 'var(--accent)', marginTop: '2px' }}>
                                Facility: {rec.facility_details.name} ({rec.plant_code})
                              </span>
                            ) : (
                              <span style={{ fontSize: '11px', color: 'var(--danger)', marginTop: '2px', display: 'flex', alignItems: 'center', gap: '4px' }}>
                                <AlertTriangle size={12} /> Plant {rec.plant_code || 'N/A'} Unresolved
                              </span>
                            )}
                          </div>
                        </td>
                        <td style={{ textAlign: 'right', fontWeight: '500', fontFamily: 'monospace' }}>
                          {parseFloat(rec.quantity).toLocaleString()} <span style={{ color: 'var(--text-secondary)', fontSize: '11px' }}>{rec.unit}</span>
                        </td>
                        <td style={{ textAlign: 'right', fontWeight: '700', color: 'white', fontFamily: 'monospace', fontSize: '15px' }}>
                          {parseFloat(rec.co2e_emissions).toFixed(4)}
                        </td>
                        <td>
                          <span className={`badge badge-${rec.status.toLowerCase()}`}>
                            {rec.status === 'FLAGGED' && <AlertTriangle size={12} style={{ marginRight: '4px' }} />}
                            {rec.status === 'APPROVED' && <Check size={12} style={{ marginRight: '4px' }} />}
                            {rec.status}
                          </span>
                        </td>
                        <td style={{ textAlign: 'center' }}>
                          <button 
                            className="btn btn-secondary" 
                            style={{ padding: '6px 12px', fontSize: '12px' }}
                            onClick={() => handleOpenDrawer(rec)}
                          >
                            Review
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <div style={{ textAlign: 'center', padding: '48px', color: 'var(--text-muted)' }}>
                  No records matching the selected queue filter. Select "All Review Statuses" to verify historical approved list!
                </div>
              )}
            </div>
          </div>
        )}

        {/* --- TAB 3: DATA INGESTION --- */}
        {activeTab === 'ingest' && (
          <div>
            <div className="glass-panel" style={{ marginBottom: '32px' }}>
              <h3 style={{ fontSize: '18px', marginBottom: '24px' }}>Simulate Enterprise Pipeline Feeds</h3>
              <p style={{ color: 'var(--text-secondary)', fontSize: '14px', marginBottom: '24px' }}>
                Since we are evaluating the prototype without external active databases, click any simulator below. It will inject actual raw client data, process daily calendar allocations, calculate carbon factors, and seed the review queue instantly.
              </p>

              {/* Real File Upload Dropzone */}
              <div className="glass-panel" style={{ marginBottom: '24px', background: 'var(--bg-elevated)' }}>
                <h4 style={{ fontSize: '15px', marginBottom: '12px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <FileUp size={18} style={{ color: 'var(--accent)' }} /> Upload Your Own Data File
                </h4>
                <div style={{ display: 'flex', gap: '12px', alignItems: 'center', marginBottom: '12px' }}>
                  <select value={uploadSourceType} onChange={(e) => setUploadSourceType(e.target.value)} className="filter-select">
                    <option value="SAP">SAP (CSV)</option>
                    <option value="UTILITY">Utility (CSV)</option>
                    <option value="TRAVEL">Travel (JSON)</option>
                  </select>
                  <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Select source type, then drag a file or click to browse</span>
                </div>
                <div
                  className={`dropzone ${dragOver ? 'drag-over' : ''}`}
                  onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
                  onDragLeave={() => setDragOver(false)}
                  onDrop={handleDrop}
                  onClick={() => fileInputRef.current?.click()}
                >
                  <Upload size={28} style={{ color: 'var(--text-muted)', marginBottom: '8px' }} />
                  <p style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>Drop a CSV or JSON file here, or click to browse</p>
                  <p style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '4px' }}>SAP &amp; Utility: CSV files &bull; Travel: JSON files</p>
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept=".csv,.json,.txt"
                    style={{ display: 'none' }}
                    onChange={(e) => { if (e.target.files[0]) handleFileUpload(e.target.files[0]); e.target.value = ''; }}
                  />
                </div>
              </div>

              <h4 style={{ fontSize: '14px', color: 'var(--text-secondary)', marginBottom: '12px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Or Simulate Enterprise Feeds</h4>
              <div className="source-cards-grid">
                {/* SAP simulator */}
                <div className="glass-panel" style={{ background: 'rgba(255,255,255,0.02)' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '16px' }}>
                    <div className="badge badge-draft" style={{ background: '#2563eb', color: 'white' }}>SAP CSV</div>
                  </div>
                  <h4 style={{ marginBottom: '8px' }}>Fuel & Materials ledger</h4>
                  <p style={{ fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '20px' }}>
                    Imports German SAP ERP fields (`BUKRS`, `HKONT`, `WERKS`), converts Gallons to Liters, maps plants, and flags unmapped facility codes.
                  </p>
                  <button className="btn btn-primary" style={{ width: '100%' }} onClick={simulateSAP} disabled={uploading}>
                    Simulate SAP Upload
                  </button>
                </div>

                {/* Utility simulator */}
                <div className="glass-panel" style={{ background: 'rgba(255,255,255,0.02)' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '16px' }}>
                    <div className="badge badge-draft" style={{ background: '#0891b2', color: 'white' }}>Utility CSV</div>
                  </div>
                  <h4 style={{ marginBottom: '8px' }}>Electricity Billing Split</h4>
                  <p style={{ fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '20px' }}>
                    Distributes consumption pro-rata daily across months, normalizes MWh to kWh, maps subregion eGRID emission factors, and flags high loads.
                  </p>
                  <button className="btn btn-primary" style={{ width: '100%' }} onClick={simulateUtility} disabled={uploading}>
                    Simulate PGE Utility Bill
                  </button>
                </div>

                {/* Travel simulator */}
                <div className="glass-panel" style={{ background: 'rgba(255,255,255,0.02)' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '16px' }}>
                    <div className="badge badge-draft" style={{ background: '#4f46e5', color: 'white' }}>Concur JSON</div>
                  </div>
                  <h4 style={{ marginBottom: '8px' }}>Travel API Ingestion</h4>
                  <p style={{ fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '20px' }}>
                    Calculates Great-Circle Haversine distance from airport coordinates, applies 2.9x Business cabin multiplier, and logs auditor flags.
                  </p>
                  <button className="btn btn-primary" style={{ width: '100%' }} onClick={simulateTravel} disabled={uploading}>
                    Simulate Travel API
                  </button>
                </div>
              </div>

              {uploading && (
                <div style={{ marginTop: '24px', display: 'flex', alignItems: 'center', gap: '12px', color: 'var(--accent)' }}>
                  <RefreshCw className="animate-spin" size={20} />
                  <span>Processing transactions, calculating emission factors, and daily splitting cycles...</span>
                </div>
              )}

              {uploadSuccess && (
                <div className="alert alert-success" style={{ marginTop: '24px' }}>
                  <CheckCircle size={20} />
                  <span>{uploadSuccess}</span>
                </div>
              )}

              {uploadError && (
                <div className="alert alert-danger" style={{ marginTop: '24px' }}>
                  <XCircle size={20} />
                  <span>{uploadError}</span>
                </div>
              )}
            </div>

            {/* Ingestion runs logs */}
            <div className="glass-panel">
              <h3 style={{ fontSize: '18px', marginBottom: '20px' }}>Active Ingestion Runs</h3>
              <div className="table-container">
                <table className="esg-table">
                  <thead>
                    <tr>
                      <th>Job ID</th>
                      <th>Timestamp</th>
                      <th>Source Type</th>
                      <th>Ingested File</th>
                      <th style={{ textAlign: 'center' }}>Total Rows</th>
                      <th style={{ textAlign: 'center' }}>Successful</th>
                      <th style={{ textAlign: 'center' }}>Errors</th>
                      <th>Upload Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {jobs.map(job => (
                      <tr key={job.id}>
                        <td style={{ fontWeight: '700' }}>#{job.id}</td>
                        <td>{new Date(job.created_at).toLocaleString()}</td>
                        <td style={{ fontWeight: '600' }}>{job.source_type}</td>
                        <td style={{ fontFamily: 'monospace', fontSize: '12px' }}>{job.file_name}</td>
                        <td style={{ textAlign: 'center' }}>{job.total_rows}</td>
                        <td style={{ textAlign: 'center', color: 'var(--accent)', fontWeight: '600' }}>{job.successful_rows}</td>
                        <td style={{ textAlign: 'center', color: job.failed_rows > 0 ? 'var(--danger)' : 'var(--text-muted)' }}>{job.failed_rows}</td>
                        <td>
                          <span className={`badge badge-${job.status.toLowerCase()}`}>
                            {job.status}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* --- TAB 4: AUDIT TRAIL --- */}
        {activeTab === 'audit' && (
          <div className="glass-panel">
            <h3 style={{ fontSize: '18px', marginBottom: '24px' }}>Regulatory Audit Log (Immutable History)</h3>
            <div className="table-container">
              {auditLogs.length > 0 ? (
                <table className="esg-table">
                  <thead>
                    <tr>
                      <th>Timestamp</th>
                      <th>Record ID</th>
                      <th>Signed User</th>
                      <th>Workflow Action</th>
                      <th>Audit Justification Reason</th>
                      <th>Values Snapshot</th>
                    </tr>
                  </thead>
                  <tbody>
                    {auditLogs.map(log => (
                      <tr key={log.id}>
                        <td style={{ whiteSpace: 'nowrap' }}>{new Date(log.timestamp).toLocaleString()}</td>
                        <td style={{ fontWeight: '700' }}>#{log.normalized_record}</td>
                        <td style={{ fontWeight: '600', color: 'white' }}>{log.user}</td>
                        <td>
                          <span className={`badge ${log.action === 'APPROVE' ? 'badge-approved' : log.action === 'REJECT' ? 'badge-rejected' : 'badge-draft'}`}>
                            {log.action}
                          </span>
                        </td>
                        <td style={{ maxWidth: '280px', color: 'var(--text-primary)', fontStyle: 'italic' }}>
                          "{log.reason}"
                        </td>
                        <td>
                          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', maxWidth: '240px', fontSize: '11px', fontFamily: 'monospace' }}>
                            {log.action === 'UPDATE' ? (
                              <>
                                <span style={{ color: 'var(--danger)' }}>- {log.previous_values.quantity} {log.previous_values.unit} ({log.previous_values.plant_code})</span>
                                <span style={{ color: 'var(--accent)' }}>+ {log.new_values.quantity} {log.new_values.unit} ({log.new_values.plant_code})</span>
                              </>
                            ) : (
                              <span style={{ color: 'var(--text-muted)' }}>Status marked {log.new_values.status}</span>
                            )}
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <div style={{ textAlign: 'center', padding: '48px', color: 'var(--text-muted)' }}>
                  No manual auditor adjustments logged yet. Open Draft Review drawer, submit edits, and they will log immutably here.
                </div>
              )}
            </div>
          </div>
        )}

        {/* --- TAB 5: FACILITIES REGISTRY --- */}
        {activeTab === 'facilities' && (
          <div className="glass-panel">
            <h3 style={{ fontSize: '18px', marginBottom: '20px' }}>Registered Facilities Lookup Table</h3>
            <p style={{ color: 'var(--text-secondary)', fontSize: '14px', marginBottom: '24px' }}>
              Maps transactional ERP codes (e.g. SAP `WERKS`) to geographical regions to resolve localized Scope 2 grid emission factors.
            </p>
            <div className="table-container">
              <table className="esg-table">
                <thead>
                  <tr>
                    <th>Plant Code (ERP)</th>
                    <th>Facility Name</th>
                    <th>Geographic Location</th>
                    <th>Grid Interconnection Region</th>
                    <th>Scope 2 Grid Carbon Factor</th>
                  </tr>
                </thead>
                <tbody>
                  {facilities.map(fac => (
                    <tr key={fac.id}>
                      <td style={{ fontWeight: '700', color: 'var(--accent)' }}>{fac.plant_code}</td>
                      <td style={{ color: 'white', fontWeight: '500' }}>{fac.plant_name}</td>
                      <td>{fac.location}</td>
                      <td style={{ fontFamily: 'monospace' }}>{fac.grid_region}</td>
                      <td style={{ fontWeight: '600' }}>
                        {fac.grid_region === 'Grid:Germany' && '0.000385 tCO2e/kWh (National Mix)'}
                        {fac.grid_region === 'eGRID:NYUP' && '0.000116 tCO2e/kWh (Upstate eGRID)'}
                        {fac.grid_region === 'Grid:UK' && '0.000207 tCO2e/kWh (DEFRA UK)'}
                        {fac.grid_region === 'Grid:US-DEFAULT' && '0.000371 tCO2e/kWh (US Average)'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </main>

      {/* --- REVIEW QUEUE SLIDE-OVER DETAIL DRAWER --- */}
      {selectedRecord && (
        <div className="drawer-backdrop" onClick={() => setSelectedRecord(null)}>
          <div className="drawer" onClick={(e) => e.stopPropagation()}>
            <div className="drawer-header">
              <div>
                <span style={{ fontSize: '12px', fontWeight: '700', color: 'var(--accent)', textTransform: 'uppercase' }}>
                  Record #{selectedRecord.id} Details
                </span>
                <h3 style={{ fontSize: '20px', color: 'white', marginTop: '4px' }}>Auditor Verification Panel</h3>
              </div>
              <button 
                onClick={() => setSelectedRecord(null)}
                style={{ background: 'none', border: 'none', color: 'var(--text-secondary)', cursor: 'pointer' }}
              >
                <XCircle size={24} />
              </button>
            </div>

            <div className="drawer-content">
              {/* Suspicious warning notifications */}
              {selectedRecord.validation_warnings && selectedRecord.validation_warnings.length > 0 && (
                <div className="alert alert-warning">
                  <ShieldAlert size={20} style={{ flexShrink: 0, marginTop: '2px' }} />
                  <div>
                    <strong style={{ display: 'block', marginBottom: '4px' }}>Automated Anomaly Warnings:</strong>
                    <ul style={{ listStyle: 'disc', paddingLeft: '16px', fontSize: '12px', display: 'flex', flexDirection: 'column', gap: '4px' }}>
                      {selectedRecord.validation_warnings.map((w, idx) => (
                        <li key={idx}>{w}</li>
                      ))}
                    </ul>
                  </div>
                </div>
              )}

              {/* Locked approved warnings */}
              {selectedRecord.status === 'APPROVED' && (
                <div className="alert alert-danger" style={{ background: 'rgba(16, 185, 129, 0.1)', color: 'var(--accent)', borderColor: 'rgba(16,185,129,0.2)' }}>
                  <CheckCircle size={20} />
                  <span>This record is APPROVED and locked for audit. Fields are read-only.</span>
                </div>
              )}

              {/* Ingestion audit lineage panel */}
              <div style={{ marginBottom: '24px' }}>
                <h4 style={{ fontSize: '14px', textTransform: 'uppercase', color: 'var(--text-secondary)', marginBottom: '8px' }}>
                  Original Activity Data Lineage
                </h4>
                <p style={{ fontSize: '12px', color: 'var(--text-muted)', marginBottom: '8px' }}>
                  Raw transactional record pulled from {selectedRecord.source_system} feed.
                </p>
                <div className="raw-payload-box">
                  {selectedRecord.raw_payload ? (
                    <pre>{JSON.stringify(selectedRecord.raw_payload, null, 2)}</pre>
                  ) : (
                    <span style={{ color: 'var(--text-muted)' }}>No raw payload available (Manual entry).</span>
                  )}
                </div>
              </div>

              {/* Verification & Modification Form */}
              <form onSubmit={handleSaveChanges}>
                <h4 style={{ fontSize: '14px', textTransform: 'uppercase', color: 'var(--text-secondary)', marginBottom: '16px', borderTop: 'var(--border-glass)', paddingTop: '20px' }}>
                  Activity Parameters
                </h4>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
                  <div className="form-group">
                    <label className="form-label">Quantity</label>
                    <input 
                      type="number" 
                      step="any"
                      value={editForm.quantity}
                      onChange={(e) => setEditForm({ ...editForm, quantity: e.target.value })}
                      className="form-input"
                      disabled={selectedRecord.status === 'APPROVED'}
                      required
                    />
                  </div>

                  <div className="form-group">
                    <label className="form-label">Base Unit</label>
                    <input 
                      type="text" 
                      value={editForm.unit}
                      onChange={(e) => setEditForm({ ...editForm, unit: e.target.value })}
                      className="form-input"
                      disabled={selectedRecord.status === 'APPROVED'}
                      required
                    />
                  </div>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
                  <div className="form-group">
                    <label className="form-label">Facility Plant Code</label>
                    <input 
                      type="text" 
                      value={editForm.plant_code}
                      onChange={(e) => setEditForm({ ...editForm, plant_code: e.target.value.toUpperCase() })}
                      className="form-input"
                      placeholder="e.g. DE10, US20"
                      disabled={selectedRecord.status === 'APPROVED'}
                    />
                    <small style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '4px', display: 'block' }}>
                      Tip: If plant warning, edit to <strong>DE10</strong> or <strong>US20</strong> to clear flag!
                    </small>
                  </div>

                  <div className="form-group">
                    <label className="form-label">Activity Date</label>
                    <input 
                      type="date" 
                      value={editForm.transaction_date}
                      onChange={(e) => setEditForm({ ...editForm, transaction_date: e.target.value })}
                      className="form-input"
                      disabled={selectedRecord.status === 'APPROVED'}
                      required
                    />
                  </div>
                </div>

                <div className="form-group">
                  <label className="form-label">Line Description</label>
                  <textarea 
                    value={editForm.description}
                    onChange={(e) => setEditForm({ ...editForm, description: e.target.value })}
                    className="form-input"
                    style={{ height: '80px', resize: 'vertical' }}
                    disabled={selectedRecord.status === 'APPROVED'}
                    required
                  />
                </div>

                {/* Carbon Factors readonly metadata */}
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', background: 'rgba(255,255,255,0.02)', padding: '16px', borderRadius: '8px', border: 'var(--border-glass)', marginBottom: '24px' }}>
                  <div>
                    <span style={{ fontSize: '11px', color: 'var(--text-secondary)', textTransform: 'uppercase' }}>Scope Standardized Unit</span>
                    <div style={{ fontWeight: '600', color: 'white', marginTop: '2px' }}>
                      {parseFloat(selectedRecord.normalized_quantity).toLocaleString()} {selectedRecord.normalized_unit}
                    </div>
                  </div>
                  <div>
                    <span style={{ fontSize: '11px', color: 'var(--text-secondary)', textTransform: 'uppercase' }}>Applied Emission Factor</span>
                    <div style={{ fontWeight: '600', color: 'white', marginTop: '2px' }}>
                      {parseFloat(selectedRecord.emission_factor).toFixed(6)} <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>tCO2e/{selectedRecord.normalized_unit}</span>
                    </div>
                  </div>
                </div>

                {/* Audit Signature block */}
                {selectedRecord.status !== 'APPROVED' && (
                  <div style={{ background: 'rgba(16,185,129,0.02)', border: '1px solid rgba(16,185,129,0.15)', borderRadius: '12px', padding: '20px', marginBottom: '24px' }}>
                    <h4 style={{ fontSize: '13px', textTransform: 'uppercase', color: 'var(--accent)', display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '12px' }}>
                      <CheckCircle size={16} /> Auditor Change Authorization
                    </h4>
                    
                    <div className="form-group">
                      <label className="form-label" style={{ color: 'white' }}>MANDATORY Audit Justification Reason</label>
                      <input 
                        type="text" 
                        value={auditReason}
                        onChange={(e) => setAuditReason(e.target.value)}
                        placeholder="e.g. Corrected unregistered plant WERKS code DE10 after invoice validation."
                        className="form-input"
                        style={{ borderColor: auditReason.trim().length >= 5 ? 'var(--accent)' : 'rgba(255,255,255,0.1)' }}
                        required={selectedRecord.status !== 'APPROVED'}
                      />
                    </div>
                    {formError && (
                      <div style={{ color: 'var(--danger)', fontSize: '12px', display: 'flex', alignItems: 'center', gap: '4px' }}>
                        <AlertTriangle size={14} /> {formError}
                      </div>
                    )}
                  </div>
                )}

                {/* Actions Row */}
                <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px' }}>
                  {selectedRecord.status !== 'APPROVED' && (
                    <>
                      {selectedRecord.status !== 'REJECTED' && (
                        <button 
                          type="button" 
                          className="btn btn-danger" 
                          onClick={() => handleReject(selectedRecord.id, auditReason || "Auditor rejected transaction")}
                        >
                          Reject
                        </button>
                      )}
                      <button type="submit" className="btn btn-secondary">
                        Save Corrections
                      </button>
                      <button 
                        type="button" 
                        className="btn btn-primary"
                        onClick={() => handleSingleApprove(selectedRecord.id)}
                      >
                        Approve & Lock
                      </button>
                    </>
                  )}
                  {selectedRecord.status === 'APPROVED' && (
                    <button 
                      type="button" 
                      className="btn btn-secondary" 
                      onClick={() => setSelectedRecord(null)}
                    >
                      Close Panel
                    </button>
                  )}
                </div>
              </form>
            </div>
          </div>
        </div>
      )}

      {/* Toast Notifications */}
      {toasts.length > 0 && (
        <div className="toast-container">
          {toasts.map(t => (
            <div key={t.id} className={`toast toast-${t.type}`}>
              {t.type === 'success' && <CheckCircle size={16} style={{ color: 'var(--success)', flexShrink: 0 }} />}
              {t.type === 'error' && <XCircle size={16} style={{ color: 'var(--danger)', flexShrink: 0 }} />}
              {t.type === 'info' && <AlertTriangle size={16} style={{ color: 'var(--info)', flexShrink: 0 }} />}
              <span style={{ flex: 1 }}>{t.message}</span>
              <button className="btn-ghost" onClick={() => setToasts(prev => prev.filter(x => x.id !== t.id))} style={{ padding: '2px' }}>
                <X size={14} />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
