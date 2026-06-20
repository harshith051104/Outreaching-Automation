"use client";

import { useEffect, useState } from "react";
import { 
  getLeads, 
  createLead, 
  updateLead, 
  deleteLead, 
  uploadLeadCsv,
  getLeadSignals,
  getLeadOpportunity,
  evaluateLeadOpportunity 
} from "@/services/lead-api";
import { getCampaigns } from "@/services/campaign-api";
import { extractErrorMessage } from "@/utils/error";
import { Users, Upload, Plus, X, Zap, Search, Star, Target } from "lucide-react";

const STATUS_COLORS: Record<string, { color: string; bg: string; border: string }> = {
  new:       { color: '#7c5cff', bg: 'rgba(124,92,255,0.1)',  border: 'rgba(124,92,255,0.25)' },
  contacted: { color: '#f59e0b', bg: 'rgba(245,158,11,0.1)',  border: 'rgba(245,158,11,0.25)' },
  replied:   { color: '#10b981', bg: 'rgba(16,185,129,0.1)',  border: 'rgba(16,185,129,0.25)' },
  engaged:   { color: '#10b981', bg: 'rgba(16,185,129,0.1)',  border: 'rgba(16,185,129,0.25)' },
  qualified: { color: '#8b5cf6', bg: 'rgba(139,92,246,0.1)',  border: 'rgba(139,92,246,0.25)' },
  converted: { color: '#06b6d4', bg: 'rgba(6,182,212,0.1)',   border: 'rgba(6,182,212,0.25)'  },
  lost:      { color: '#ef4444', bg: 'rgba(239,68,68,0.1)',   border: 'rgba(239,68,68,0.25)'  },
  meeting:   { color: '#10b981', bg: 'rgba(16,185,129,0.1)',  border: 'rgba(16,185,129,0.25)' },
};

export default function LeadsPage() {
  const [leads, setLeads] = useState<any[]>([]);
  const [campaigns, setCampaigns] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedCampaignFilterId, setSelectedCampaignFilterId] = useState("");

  const [isCsvModalOpen, setIsCsvModalOpen] = useState(false);
  const [isLeadModalOpen, setIsLeadModalOpen] = useState(false);
  const [editLead, setEditLead] = useState<any>(null);
  const [selectedLeadIntel, setSelectedLeadIntel] = useState<any>(null);
  const [intelLoading, setIntelLoading] = useState(false);
  const [leadSignals, setLeadSignals] = useState<any[]>([]);
  const [leadOpportunity, setLeadOpportunity] = useState<any>(null);
  const [oppEvaluating, setOppEvaluating] = useState(false);

  const [selectedCampaignId, setSelectedCampaignId] = useState("");
  const [csvFile, setCsvFile] = useState<File | null>(null);
  const [csvError, setCsvError] = useState("");
  const [csvSuccess, setCsvSuccess] = useState("");
  const [leadForm, setLeadForm] = useState({ first_name: "", last_name: "", email: "", company: "", title: "", website: "", focus: "" });
  const [leadError, setLeadError] = useState("");
  const [editForm, setEditForm] = useState({ name: "", email: "", company: "", role: "", website: "", status: "", focus: "" });
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    loadLeads(selectedCampaignFilterId);
  }, [selectedCampaignFilterId]);

  useEffect(() => {
    loadCampaigns();
  }, []);

  const loadLeads = async (campaignId?: string) => {
    setLoading(true);
    try { const data = await getLeads(campaignId); setLeads(data); }
    catch (err) { console.error(err); } finally { setLoading(false); }
  };
  const loadCampaigns = async () => {
    try {
      const data = await getCampaigns(); setCampaigns(data);
      if (data.length > 0) setSelectedCampaignId(data[0].id);
    } catch (err) { console.error(err); }
  };


  const handleCsvUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedCampaignId || !csvFile) { setCsvError("Please select a campaign and choose a CSV file."); return; }
    setCsvError(""); setCsvSuccess("");
    try {
      const res = await uploadLeadCsv(selectedCampaignId, csvFile);
      setCsvSuccess(`Successfully imported ${res.imported} leads! (Skipped: ${res.skipped})`);
      setCsvFile(null); loadLeads();
      setTimeout(() => { setIsCsvModalOpen(false); setCsvSuccess(""); }, 2000);
    } catch (err: any) { setCsvError(extractErrorMessage(err, "Failed to upload CSV.")); }
  };

  const handleCreateLead = async (e: React.FormEvent) => {
    e.preventDefault();
    const fullName = `${leadForm.first_name} ${leadForm.last_name}`.trim();
    if (!selectedCampaignId || !leadForm.email || !fullName) { setLeadError("Please fill required fields."); return; }
    setLeadError("");
    try {
      await createLead({ campaign_id: selectedCampaignId, name: fullName, email: leadForm.email, company: leadForm.company, role: leadForm.title, focus: leadForm.focus, website: leadForm.website });
      setLeadForm({ first_name: "", last_name: "", email: "", company: "", title: "", website: "", focus: "" });
      setIsLeadModalOpen(false); loadLeads();
    } catch (err: any) { setLeadError(extractErrorMessage(err, "Failed to create lead.")); }
  };

  const handleDeleteLead = async (leadId: string) => {
    if (!window.confirm("Delete this lead?")) return;
    try { await deleteLead(leadId); setLeads((prev) => prev.filter((l) => l.id !== leadId)); }
    catch (err) { console.error(err); }
  };

  const openEditModal = (lead: any) => {
    setEditLead(lead);
    setEditForm({ name: lead.name || "", email: lead.email || "", company: lead.company || "", role: lead.role || "", focus: lead.focus || "", website: lead.website || "", status: lead.status || "new" });
  };

  const handleSaveEdit = async () => {
    if (!editLead) return;
    setSaving(true);
    try { await updateLead(editLead.id, editForm); setEditLead(null); loadLeads(); }
    catch (err) { console.error(err); } finally { setSaving(false); }
  };

  const openLeadIntel = async (lead: any) => {
    setSelectedLeadIntel(lead); setIntelLoading(true); setLeadSignals([]); setLeadOpportunity(null);
    try {
      const [signalsData, oppData] = await Promise.all([
        getLeadSignals(lead.id).catch(() => ({ signals: [] })),
        getLeadOpportunity(lead.id).catch(() => ({ opportunity: null }))
      ]);
      setLeadSignals(signalsData.signals || []); setLeadOpportunity(oppData.opportunity || null);
    } catch (err) { console.error(err); } finally { setIntelLoading(false); }
  };

  const handleEvaluateOpportunity = async () => {
    if (!selectedLeadIntel) return; setOppEvaluating(true);
    try { const res = await evaluateLeadOpportunity(selectedLeadIntel.id); setLeadOpportunity(res.opportunity || null); }
    catch (err) { console.error(err); } finally { setOppEvaluating(false); }
  };

  const filteredLeads = leads.filter(l =>
    !searchQuery || 
    (l.name || '').toLowerCase().includes(searchQuery.toLowerCase()) ||
    (l.email || '').toLowerCase().includes(searchQuery.toLowerCase()) ||
    (l.company || '').toLowerCase().includes(searchQuery.toLowerCase())
  );

  const cardStyle: React.CSSProperties = {
    background: 'var(--card-bg)', border: '1px solid var(--card-border)',
    borderRadius: '16px', boxShadow: 'var(--card-shadow)',
    backdropFilter: 'blur(12px)', WebkitBackdropFilter: 'blur(12px)',
  };

  const modalStyle: React.CSSProperties = {
    width: '100%', maxWidth: '500px', borderRadius: '20px',
    background: 'var(--card-bg)', border: '1px solid var(--card-border)',
    boxShadow: '0 32px 64px rgba(0,0,0,0.5)', padding: '28px',
    maxHeight: '90vh', overflowY: 'auto',
  };

  const inputStyle: React.CSSProperties = {
    width: '100%', padding: '9px 12px', fontSize: '13px',
    background: 'var(--sidebar-toggle-bg)', border: '1px solid var(--card-border)',
    borderRadius: '8px', color: 'var(--foreground-color)', fontFamily: 'inherit', outline: 'none',
  };

  const overlayStyle: React.CSSProperties = {
    position: 'fixed', inset: 0, zIndex: 50,
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    background: 'rgba(0,0,0,0.7)', backdropFilter: 'blur(4px)',
  };

  const getQualityColor = (score: number) => {
    if (score >= 70) return { color: '#10b981', bg: 'rgba(16,185,129,0.1)', border: 'rgba(16,185,129,0.25)' };
    if (score >= 40) return { color: '#f59e0b', bg: 'rgba(245,158,11,0.1)', border: 'rgba(245,158,11,0.25)' };
    return { color: '#ef4444', bg: 'rgba(239,68,68,0.1)', border: 'rgba(239,68,68,0.25)' };
  };

  return (
    <div style={{ padding: '24px', maxWidth: '1400px', margin: '0 auto' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '24px', flexWrap: 'wrap', gap: '12px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div style={{
            width: '36px', height: '36px', borderRadius: '10px',
            background: 'linear-gradient(135deg, rgba(124,92,255,0.2), rgba(124,92,255,0.05))',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>
            <Users size={18} color="#7c5cff" />
          </div>
          <div>
            <h1 style={{ fontSize: '22px', fontWeight: '800', color: 'var(--foreground-color)', margin: 0, letterSpacing: '-0.02em' }}>Leads</h1>
            <p style={{ fontSize: '12px', color: 'var(--sidebar-text-muted)', margin: 0 }}>{leads.length} total · {leads.filter(l => l.status === 'replied').length} replied</p>
          </div>
        </div>
        <div style={{ display: 'flex', gap: '10px', alignItems: 'center', flexWrap: 'wrap' }}>
          {/* Search */}
          <div style={{ position: 'relative' }}>
            <Search size={14} color="var(--sidebar-text-muted)" style={{ position: 'absolute', left: '10px', top: '50%', transform: 'translateY(-50%)' }} />
            <input
              type="text"
              placeholder="Search leads..."
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              style={{ ...inputStyle, width: '220px', paddingLeft: '32px' }}
            />
          </div>
          {/* Campaign Filter */}
          <div>
            <select
              value={selectedCampaignFilterId}
              onChange={e => setSelectedCampaignFilterId(e.target.value)}
              style={{ ...inputStyle, width: '200px', cursor: 'pointer' }}
            >
              <option value="">All Campaigns</option>
              {campaigns.map(c => (
                <option key={c.id} value={c.id}>{c.name}</option>
              ))}
            </select>
          </div>
          <button onClick={() => setIsCsvModalOpen(true)} style={{
            display: 'flex', alignItems: 'center', gap: '7px',
            padding: '9px 16px', borderRadius: '10px',
            border: '1px solid var(--card-border)', background: 'var(--card-bg)',
            color: 'var(--foreground-color)', fontSize: '13px', fontWeight: '600', cursor: 'pointer',
            boxShadow: 'var(--card-shadow)',
          }}>
            <Upload size={14} /> Import CSV
          </button>
          <button onClick={() => setIsLeadModalOpen(true)} style={{
            display: 'flex', alignItems: 'center', gap: '7px',
            padding: '9px 16px', borderRadius: '10px', border: 'none',
            background: 'linear-gradient(135deg, #7c5cff, #6344d9)',
            color: 'white', fontSize: '13px', fontWeight: '600', cursor: 'pointer',
            boxShadow: '0 4px 16px rgba(124,92,255,0.4)',
          }}>
            <Plus size={14} /> Add Lead
          </button>
        </div>
      </div>

      {/* Table */}
      {loading ? (
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '200px' }}>
          <div style={{ width: '36px', height: '36px', border: '3px solid rgba(124,92,255,0.2)', borderTopColor: '#7c5cff', borderRadius: '50%', animation: 'spin 0.8s linear infinite' }} />
          <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
        </div>
      ) : filteredLeads.length === 0 ? (
        <div style={{ ...cardStyle, padding: '60px', textAlign: 'center' }}>
          <Users size={40} color="rgba(124,92,255,0.4)" style={{ margin: '0 auto 16px', display: 'block' }} />
          <h3 style={{ fontSize: '16px', fontWeight: '700', color: 'var(--foreground-color)', margin: '0 0 8px' }}>No leads found</h3>
          <p style={{ fontSize: '13px', color: 'var(--sidebar-text-muted)', margin: 0 }}>Import leads via CSV or add them manually.</p>
        </div>
      ) : (
        <div style={{ ...cardStyle, overflow: 'hidden' }}>
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--card-border)' }}>
                  {['Name', 'Email', 'Company', 'Job Title', 'Focus', 'Status', 'Score', 'Quality', 'Actions'].map((h, i) => (
                    <th key={h} style={{
                      padding: '12px 16px', textAlign: i === 8 ? 'right' : 'left',
                      fontSize: '11px', fontWeight: '700', letterSpacing: '0.06em',
                      textTransform: 'uppercase', color: 'var(--sidebar-text-muted)',
                      whiteSpace: 'nowrap',
                    }}>
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {filteredLeads.map((lead, idx) => {
                  const statusCfg = STATUS_COLORS[lead.status] || STATUS_COLORS.new;
                  const quality = lead.lead_quality_score ? getQualityColor(lead.lead_quality_score) : null;
                  return (
                    <tr key={lead.id} style={{
                      borderBottom: idx < filteredLeads.length - 1 ? '1px solid rgba(124,92,255,0.05)' : 'none',
                      transition: 'background 0.15s ease',
                    }}
                    onMouseEnter={e => (e.currentTarget as HTMLTableRowElement).style.background = 'var(--sidebar-hover)'}
                    onMouseLeave={e => (e.currentTarget as HTMLTableRowElement).style.background = 'transparent'}
                    >
                      <td style={{ padding: '14px 16px', whiteSpace: 'nowrap' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                          <div style={{
                            width: '32px', height: '32px', borderRadius: '50%', flexShrink: 0,
                            background: 'linear-gradient(135deg, #7c5cff, #a78bfa)',
                            display: 'flex', alignItems: 'center', justifyContent: 'center',
                            fontSize: '12px', fontWeight: '700', color: 'white',
                          }}>
                            {(lead.name || lead.email || '?').charAt(0).toUpperCase()}
                          </div>
                          <span style={{ fontSize: '13px', fontWeight: '600', color: 'var(--foreground-color)' }}>
                            {lead.name || '—'}
                          </span>
                        </div>
                      </td>
                      <td style={{ padding: '14px 16px', whiteSpace: 'nowrap', fontSize: '13px', color: 'var(--sidebar-text-muted)' }}>
                        {lead.email}
                      </td>
                      <td style={{ padding: '14px 16px', whiteSpace: 'nowrap', fontSize: '13px', color: 'var(--foreground-color)' }}>
                        {lead.company || '—'}
                      </td>
                      <td style={{ padding: '14px 16px', whiteSpace: 'nowrap', fontSize: '13px', color: 'var(--sidebar-text-muted)' }}>
                        {lead.role || '—'}
                      </td>
                      <td style={{ padding: '14px 16px', whiteSpace: 'nowrap', fontSize: '13px', color: 'var(--sidebar-text-muted)' }}>
                        {lead.focus || '—'}
                      </td>
                      <td style={{ padding: '14px 16px', whiteSpace: 'nowrap' }}>
                        <span style={{
                          display: 'inline-flex', alignItems: 'center', gap: '5px',
                          padding: '3px 10px', borderRadius: '999px',
                          background: statusCfg.bg, border: `1px solid ${statusCfg.border}`,
                          color: statusCfg.color, fontSize: '11px', fontWeight: '600',
                        }}>
                          {lead.status || 'new'}
                        </span>
                      </td>
                      <td style={{ padding: '14px 16px', whiteSpace: 'nowrap' }}>
                        <span style={{
                          fontSize: '14px', fontWeight: '700',
                          color: (lead.score ?? 0) >= 80 ? '#10b981' : (lead.score ?? 0) >= 50 ? '#f59e0b' : 'var(--foreground-color)',
                        }}>
                          {lead.score ?? 0}
                        </span>
                      </td>
                      <td style={{ padding: '14px 16px', whiteSpace: 'nowrap' }}>
                        {quality ? (
                          <span style={{
                            display: 'inline-flex', alignItems: 'center', gap: '4px',
                            padding: '3px 8px', borderRadius: '999px',
                            background: quality.bg, border: `1px solid ${quality.border}`,
                            color: quality.color, fontSize: '11px', fontWeight: '600',
                          }}>
                            <Star size={10} fill="currentColor" />
                            {Math.round(lead.lead_quality_score)}
                          </span>
                        ) : <span style={{ color: 'var(--sidebar-text-muted)', fontSize: '13px' }}>—</span>}
                      </td>
                      <td style={{ padding: '14px 16px', whiteSpace: 'nowrap', textAlign: 'right' }}>
                        <div style={{ display: 'flex', gap: '6px', justifyContent: 'flex-end' }}>
                          <button onClick={() => openLeadIntel(lead)} style={{
                            padding: '5px 10px', borderRadius: '7px',
                            background: 'rgba(124,92,255,0.1)', border: '1px solid rgba(124,92,255,0.25)',
                            color: '#7c5cff', fontSize: '11px', fontWeight: '600', cursor: 'pointer',
                            display: 'flex', alignItems: 'center', gap: '4px',
                          }}>
                            <Zap size={11} /> Intel
                          </button>
                          <button onClick={() => openEditModal(lead)} style={{
                            padding: '5px 10px', borderRadius: '7px',
                            border: '1px solid var(--card-border)', background: 'var(--sidebar-hover)',
                            color: 'var(--foreground-color)', fontSize: '11px', fontWeight: '600', cursor: 'pointer',
                          }}>
                            Edit
                          </button>
                          <button onClick={() => handleDeleteLead(lead.id)} style={{
                            padding: '5px 10px', borderRadius: '7px',
                            background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.2)',
                            color: '#ef4444', fontSize: '11px', fontWeight: '600', cursor: 'pointer',
                          }}>
                            Delete
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* CSV Import Modal */}
      {isCsvModalOpen && (
        <div style={overlayStyle}>
          <div style={modalStyle}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
              <h2 style={{ fontSize: '18px', fontWeight: '800', color: 'var(--foreground-color)', margin: 0 }}>Import via CSV</h2>
              <button onClick={() => setIsCsvModalOpen(false)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--sidebar-text-muted)' }}>
                <X size={20} />
              </button>
            </div>
            {csvError && <div style={{ padding: '10px 14px', borderRadius: '8px', background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.2)', color: '#ef4444', fontSize: '13px', marginBottom: '14px' }}>{csvError}</div>}
            {csvSuccess && <div style={{ padding: '10px 14px', borderRadius: '8px', background: 'rgba(16,185,129,0.1)', border: '1px solid rgba(16,185,129,0.2)', color: '#10b981', fontSize: '13px', marginBottom: '14px' }}>{csvSuccess}</div>}
            <form onSubmit={handleCsvUpload} style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
              <div>
                <label style={{ display: 'block', fontSize: '12px', fontWeight: '600', color: 'var(--sidebar-text-muted)', marginBottom: '6px' }}>Select Campaign *</label>
                <select value={selectedCampaignId} onChange={e => setSelectedCampaignId(e.target.value)} style={inputStyle} required>
                  <option value="" disabled>Select a campaign</option>
                  {campaigns.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
                </select>
              </div>
              <div>
                <label style={{ display: 'block', fontSize: '12px', fontWeight: '600', color: 'var(--sidebar-text-muted)', marginBottom: '6px' }}>CSV File *</label>
                <input type="file" accept=".csv" onChange={e => setCsvFile(e.target.files?.[0] || null)} style={{ fontSize: '13px', color: 'var(--foreground-color)' }} required />
              </div>
              <div style={{ display: 'flex', gap: '10px', justifyContent: 'flex-end', paddingTop: '4px' }}>
                <button type="button" onClick={() => setIsCsvModalOpen(false)} style={{ padding: '9px 18px', borderRadius: '9px', border: '1px solid var(--card-border)', background: 'var(--sidebar-hover)', color: 'var(--foreground-color)', fontSize: '13px', fontWeight: '600', cursor: 'pointer' }}>Cancel</button>
                <button type="submit" style={{ padding: '9px 18px', borderRadius: '9px', border: 'none', background: 'linear-gradient(135deg, #7c5cff, #6344d9)', color: 'white', fontSize: '13px', fontWeight: '600', cursor: 'pointer' }}>Upload CSV</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Add Lead Modal */}
      {isLeadModalOpen && (
        <div style={overlayStyle}>
          <div style={modalStyle}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
              <h2 style={{ fontSize: '18px', fontWeight: '800', color: 'var(--foreground-color)', margin: 0 }}>Add New Lead</h2>
              <button onClick={() => setIsLeadModalOpen(false)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--sidebar-text-muted)' }}><X size={20} /></button>
            </div>
            {leadError && <div style={{ padding: '10px 14px', borderRadius: '8px', background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.2)', color: '#ef4444', fontSize: '13px', marginBottom: '14px' }}>{leadError}</div>}
            <form onSubmit={handleCreateLead} style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              <div>
                <label style={{ display: 'block', fontSize: '12px', fontWeight: '600', color: 'var(--sidebar-text-muted)', marginBottom: '5px' }}>Campaign *</label>
                <select value={selectedCampaignId} onChange={e => setSelectedCampaignId(e.target.value)} style={inputStyle} required>
                  <option value="" disabled>Select a campaign</option>
                  {campaigns.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
                </select>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
                <div>
                  <label style={{ display: 'block', fontSize: '12px', fontWeight: '600', color: 'var(--sidebar-text-muted)', marginBottom: '5px' }}>First Name</label>
                  <input type="text" value={leadForm.first_name} onChange={e => setLeadForm({ ...leadForm, first_name: e.target.value })} style={inputStyle} />
                </div>
                <div>
                  <label style={{ display: 'block', fontSize: '12px', fontWeight: '600', color: 'var(--sidebar-text-muted)', marginBottom: '5px' }}>Last Name</label>
                  <input type="text" value={leadForm.last_name} onChange={e => setLeadForm({ ...leadForm, last_name: e.target.value })} style={inputStyle} />
                </div>
              </div>
              {['email', 'company', 'title', 'focus', 'website'].map(field => (
                <div key={field}>
                  <label style={{ display: 'block', fontSize: '12px', fontWeight: '600', color: 'var(--sidebar-text-muted)', marginBottom: '5px' }}>
                    {field.charAt(0).toUpperCase() + field.slice(1)}{field === 'email' ? ' *' : ''}
                  </label>
                  <input
                    type={field === 'email' ? 'email' : 'text'}
                    value={leadForm[field as keyof typeof leadForm]}
                    onChange={e => setLeadForm({ ...leadForm, [field]: e.target.value })}
                    style={inputStyle}
                    required={field === 'email'}
                  />
                </div>
              ))}
              <div style={{ display: 'flex', gap: '10px', justifyContent: 'flex-end', paddingTop: '4px' }}>
                <button type="button" onClick={() => setIsLeadModalOpen(false)} style={{ padding: '9px 18px', borderRadius: '9px', border: '1px solid var(--card-border)', background: 'var(--sidebar-hover)', color: 'var(--foreground-color)', fontSize: '13px', fontWeight: '600', cursor: 'pointer' }}>Cancel</button>
                <button type="submit" style={{ padding: '9px 18px', borderRadius: '9px', border: 'none', background: 'linear-gradient(135deg, #7c5cff, #6344d9)', color: 'white', fontSize: '13px', fontWeight: '600', cursor: 'pointer' }}>Save Lead</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Edit Lead Modal */}
      {editLead && (
        <div style={overlayStyle}>
          <div style={modalStyle}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
              <h2 style={{ fontSize: '18px', fontWeight: '800', color: 'var(--foreground-color)', margin: 0 }}>Edit Lead</h2>
              <button onClick={() => setEditLead(null)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--sidebar-text-muted)' }}><X size={20} /></button>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              {['name', 'email', 'company', 'role', 'focus', 'website'].map(field => (
                <div key={field}>
                  <label style={{ display: 'block', fontSize: '12px', fontWeight: '600', color: 'var(--sidebar-text-muted)', marginBottom: '5px' }}>
                    {field === 'role' ? 'Job Title' : field.charAt(0).toUpperCase() + field.slice(1)}
                  </label>
                  <input type={field === 'email' ? 'email' : 'text'} value={editForm[field as keyof typeof editForm]}
                    onChange={e => setEditForm({ ...editForm, [field]: e.target.value })} style={inputStyle} />
                </div>
              ))}
              <div>
                <label style={{ display: 'block', fontSize: '12px', fontWeight: '600', color: 'var(--sidebar-text-muted)', marginBottom: '5px' }}>Status</label>
                <select value={editForm.status} onChange={e => setEditForm({ ...editForm, status: e.target.value })} style={inputStyle}>
                  {['new', 'contacted', 'engaged', 'qualified', 'converted', 'lost'].map(s => <option key={s} value={s}>{s.charAt(0).toUpperCase() + s.slice(1)}</option>)}
                </select>
              </div>
              <div style={{ display: 'flex', gap: '10px', justifyContent: 'flex-end', paddingTop: '4px' }}>
                <button onClick={() => setEditLead(null)} style={{ padding: '9px 18px', borderRadius: '9px', border: '1px solid var(--card-border)', background: 'var(--sidebar-hover)', color: 'var(--foreground-color)', fontSize: '13px', fontWeight: '600', cursor: 'pointer' }}>Cancel</button>
                <button onClick={handleSaveEdit} disabled={saving} style={{ padding: '9px 18px', borderRadius: '9px', border: 'none', background: 'linear-gradient(135deg, #7c5cff, #6344d9)', color: 'white', fontSize: '13px', fontWeight: '600', cursor: 'pointer', opacity: saving ? 0.7 : 1 }}>
                  {saving ? 'Saving...' : 'Save Changes'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Lead Intelligence Modal */}
      {selectedLeadIntel && (
        <div style={{ ...overlayStyle, alignItems: 'flex-start', padding: '24px', overflowY: 'auto' }}>
          <div style={{
            width: '100%', maxWidth: '860px', borderRadius: '20px',
            background: 'var(--card-bg)', border: '1px solid var(--card-border)',
            boxShadow: '0 32px 64px rgba(0,0,0,0.5)', padding: '28px',
            margin: 'auto',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '20px', paddingBottom: '16px', borderBottom: '1px solid var(--card-border)' }}>
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '4px' }}>
                  <div style={{ width: '36px', height: '36px', borderRadius: '50%', background: 'linear-gradient(135deg, #7c5cff, #a78bfa)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '14px', fontWeight: '700', color: 'white' }}>
                    {(selectedLeadIntel.name || '?').charAt(0).toUpperCase()}
                  </div>
                  <h2 style={{ fontSize: '18px', fontWeight: '800', color: 'var(--foreground-color)', margin: 0 }}>
                    Lead Intelligence: {selectedLeadIntel.name}
                  </h2>
                </div>
                <p style={{ fontSize: '13px', color: 'var(--sidebar-text-muted)', margin: 0, marginLeft: '46px' }}>
                  {selectedLeadIntel.role || 'No Title'} at <strong style={{ color: 'var(--foreground-color)' }}>{selectedLeadIntel.company || 'No Company'}</strong>
                </p>
              </div>
              <button onClick={() => setSelectedLeadIntel(null)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--sidebar-text-muted)' }}><X size={22} /></button>
            </div>

            {intelLoading ? (
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '60px 0', gap: '12px' }}>
                <div style={{ width: '36px', height: '36px', border: '3px solid rgba(124,92,255,0.2)', borderTopColor: '#7c5cff', borderRadius: '50%', animation: 'spin 0.8s linear infinite' }} />
                <p style={{ color: 'var(--sidebar-text-muted)', fontSize: '13px', fontWeight: '500' }}>Harvesting lead signals...</p>
              </div>
            ) : (
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' }}>
                {/* Left Column */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                  {/* Quality Score */}
                  <div style={{ background: 'var(--sidebar-hover)', borderRadius: '12px', border: '1px solid var(--card-border)', padding: '16px' }}>
                    <div style={{ fontSize: '10px', fontWeight: '700', letterSpacing: '0.08em', color: 'var(--sidebar-text-muted)', marginBottom: '12px', textTransform: 'uppercase' }}>Lead Quality</div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
                      {(() => {
                        const score = selectedLeadIntel.lead_quality_score || 0;
                        const qcfg = getQualityColor(score);
                        return (
                          <>
                            <div style={{ width: '56px', height: '56px', borderRadius: '50%', background: qcfg.bg, border: `2px solid ${qcfg.border}`, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '18px', fontWeight: '800', color: qcfg.color, flexShrink: 0 }}>
                              {Math.round(score)}
                            </div>
                            <div>
                              <div style={{ fontSize: '14px', fontWeight: '700', color: 'var(--foreground-color)' }}>Quality Score / 100</div>
                              <p style={{ fontSize: '11px', color: 'var(--sidebar-text-muted)', margin: '3px 0 0' }}>Based on contact info, title match & verification</p>
                            </div>
                          </>
                        );
                      })()}
                    </div>
                  </div>

                  {/* Hunter Verification */}
                  <div style={{ background: 'var(--sidebar-hover)', borderRadius: '12px', border: '1px solid var(--card-border)', padding: '16px' }}>
                    <div style={{ fontSize: '10px', fontWeight: '700', letterSpacing: '0.08em', color: 'var(--sidebar-text-muted)', marginBottom: '10px', textTransform: 'uppercase' }}>Hunter.io Verification</div>
                    {selectedLeadIntel.enrichment_data?.email_verification ? (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                          <span style={{
                            padding: '3px 10px', borderRadius: '999px', fontSize: '11px', fontWeight: '600',
                            background: selectedLeadIntel.enrichment_data.email_verification.deliverable ? 'rgba(16,185,129,0.1)' : 'rgba(239,68,68,0.1)',
                            border: `1px solid ${selectedLeadIntel.enrichment_data.email_verification.deliverable ? 'rgba(16,185,129,0.25)' : 'rgba(239,68,68,0.25)'}`,
                            color: selectedLeadIntel.enrichment_data.email_verification.deliverable ? '#10b981' : '#ef4444',
                          }}>
                            {selectedLeadIntel.enrichment_data.email_verification.deliverable ? 'Deliverable' : 'Undeliverable'}
                          </span>
                          <span style={{ fontSize: '12px', color: 'var(--sidebar-text-muted)' }}>Confidence: <strong style={{ color: 'var(--foreground-color)' }}>{selectedLeadIntel.enrichment_data.email_verification.score}%</strong></span>
                        </div>
                      </div>
                    ) : (
                      <p style={{ fontSize: '12px', color: 'var(--sidebar-text-muted)', margin: 0 }}>No email verification data available.</p>
                    )}
                  </div>

                  {/* Opportunity Intelligence */}
                  <div style={{ background: 'var(--sidebar-hover)', borderRadius: '12px', border: '1px solid var(--card-border)', padding: '16px', flex: 1 }}>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px' }}>
                      <div style={{ fontSize: '10px', fontWeight: '700', letterSpacing: '0.08em', color: 'var(--sidebar-text-muted)', textTransform: 'uppercase' }}>Opportunity Intelligence</div>
                      {leadOpportunity && (
                        <span style={{
                          padding: '3px 10px', borderRadius: '999px', fontSize: '11px', fontWeight: '600',
                          background: leadOpportunity.urgency === 'High' ? 'rgba(239,68,68,0.1)' : leadOpportunity.urgency === 'Medium' ? 'rgba(245,158,11,0.1)' : 'rgba(124,92,255,0.1)',
                          border: `1px solid ${leadOpportunity.urgency === 'High' ? 'rgba(239,68,68,0.25)' : leadOpportunity.urgency === 'Medium' ? 'rgba(245,158,11,0.25)' : 'rgba(124,92,255,0.25)'}`,
                          color: leadOpportunity.urgency === 'High' ? '#ef4444' : leadOpportunity.urgency === 'Medium' ? '#f59e0b' : '#7c5cff',
                        }}>
                          {leadOpportunity.urgency} Urgency
                        </span>
                      )}
                    </div>
                    {leadOpportunity ? (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
                          {[
                            { label: 'Best Contact', value: leadOpportunity.best_contact },
                            { label: 'Confidence', value: `${leadOpportunity.confidence_score}%` },
                          ].map(item => (
                            <div key={item.label} style={{ background: 'var(--card-bg)', borderRadius: '8px', padding: '10px', border: '1px solid var(--card-border)' }}>
                              <div style={{ fontSize: '10px', fontWeight: '700', color: 'var(--sidebar-text-muted)', marginBottom: '4px', textTransform: 'uppercase' }}>{item.label}</div>
                              <div style={{ fontSize: '13px', fontWeight: '700', color: 'var(--foreground-color)' }}>{item.value}</div>
                            </div>
                          ))}
                        </div>
                        <div style={{ background: 'rgba(124,92,255,0.08)', borderRadius: '8px', padding: '10px', border: '1px solid rgba(124,92,255,0.15)' }}>
                          <div style={{ fontSize: '10px', fontWeight: '700', color: '#7c5cff', marginBottom: '4px', textTransform: 'uppercase' }}>Recommended Offer</div>
                          <div style={{ fontSize: '12px', color: 'var(--foreground-color)', fontWeight: '500' }}>{leadOpportunity.recommended_offer}</div>
                        </div>
                        <div style={{ fontSize: '12px', color: 'var(--sidebar-text-muted)', lineHeight: '1.5' }}>{leadOpportunity.reasoning}</div>
                      </div>
                    ) : (
                      <div style={{ textAlign: 'center', padding: '20px 0' }}>
                        <Target size={28} color="rgba(124,92,255,0.3)" style={{ margin: '0 auto 10px', display: 'block' }} />
                        <p style={{ fontSize: '12px', color: 'var(--sidebar-text-muted)', margin: '0 0 14px' }}>
                          Evaluate opportunity with the AI Opportunity Agent
                        </p>
                        <button onClick={handleEvaluateOpportunity} disabled={oppEvaluating} style={{
                          padding: '8px 16px', borderRadius: '8px', border: 'none',
                          background: 'linear-gradient(135deg, #7c5cff, #6344d9)',
                          color: 'white', fontSize: '12px', fontWeight: '600', cursor: 'pointer',
                          display: 'flex', alignItems: 'center', gap: '6px', margin: '0 auto',
                          opacity: oppEvaluating ? 0.7 : 1,
                        }}>
                          {oppEvaluating ? <>Analyzing...</> : <><Zap size={13} /> Evaluate Opportunity</>}
                        </button>
                      </div>
                    )}
                  </div>
                </div>

                {/* Right Column: Signals */}
                <div>
                  <div style={{ fontSize: '10px', fontWeight: '700', letterSpacing: '0.08em', color: 'var(--sidebar-text-muted)', marginBottom: '12px', textTransform: 'uppercase' }}>Scraped Business Signals</div>
                  {leadSignals.length === 0 ? (
                    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '60px 20px', background: 'var(--sidebar-hover)', borderRadius: '12px', border: '1px dashed var(--card-border)', textAlign: 'center' }}>
                      <Zap size={30} color="rgba(124,92,255,0.3)" style={{ marginBottom: '12px' }} />
                      <p style={{ fontSize: '13px', fontWeight: '600', color: 'var(--foreground-color)', margin: '0 0 4px' }}>No buying signals yet</p>
                      <p style={{ fontSize: '11px', color: 'var(--sidebar-text-muted)', margin: 0 }}>Run signal scraping in campaign flow.</p>
                    </div>
                  ) : (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', maxHeight: '60vh', overflowY: 'auto' }}>
                      {leadSignals.map((sig: any, idx: number) => (
                        <div key={idx} style={{ background: 'var(--sidebar-hover)', border: '1px solid var(--card-border)', borderRadius: '12px', padding: '14px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                            <span style={{ fontSize: '10px', fontWeight: '700', padding: '2px 8px', borderRadius: '999px', background: 'rgba(124,92,255,0.1)', color: '#7c5cff', border: '1px solid rgba(124,92,255,0.2)' }}>
                              {sig.category || 'Signal'}
                            </span>
                            {sig.score && <span style={{ fontSize: '11px', fontWeight: '700', color: '#7c5cff' }}>Score: {sig.score}</span>}
                          </div>
                          <div style={{ fontSize: '13px', fontWeight: '600', color: 'var(--foreground-color)' }}>{sig.signal || sig.description}</div>
                          <p style={{ fontSize: '11px', color: 'var(--sidebar-text-muted)', margin: 0, lineHeight: '1.5' }}>{sig.description}</p>
                          {sig.hook && (
                            <div style={{ background: 'rgba(16,185,129,0.08)', border: '1px solid rgba(16,185,129,0.15)', borderRadius: '8px', padding: '10px' }}>
                              <div style={{ fontSize: '9px', fontWeight: '700', color: '#10b981', marginBottom: '3px', textTransform: 'uppercase' }}>Suggested Opener:</div>
                              <p style={{ fontSize: '12px', color: 'var(--foreground-color)', fontStyle: 'italic', margin: 0 }}>"{sig.hook}"</p>
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            )}

            <div style={{ display: 'flex', justifyContent: 'flex-end', paddingTop: '20px', borderTop: '1px solid var(--card-border)', marginTop: '20px' }}>
              <button onClick={() => setSelectedLeadIntel(null)} style={{ padding: '9px 20px', borderRadius: '9px', border: '1px solid var(--card-border)', background: 'var(--sidebar-hover)', color: 'var(--foreground-color)', fontSize: '13px', fontWeight: '600', cursor: 'pointer' }}>
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}