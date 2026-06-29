"use client";

import { useEffect, useState } from "react";
import { getCampaigns, startCampaign, pauseCampaign, deleteCampaign, updateCampaign } from "@/services/campaign-api";
import Link from "next/link";
import { Play, Pause, RotateCcw, Pencil, Eye, Trash2, Plus, Megaphone, Mail, Users } from "lucide-react";

interface Campaign {
  id: string;
  name: string;
  description?: string;
  status: string;
  subject_template?: string;
  body_template?: string;
  total_leads: number;
  emails_sent: number;
  created_at: string;
  daily_send_limit?: number;
  followup_enabled?: boolean;
  followup_stages?: number;
  followup_delay_days?: number;
}

const STATUS_CONFIG: Record<string, { label: string; color: string; bg: string; border: string; dot: string; pulse?: boolean }> = {
  draft:     { label: 'Draft',     color: '#6b7280', bg: 'rgba(107,114,128,0.08)',  border: 'rgba(107,114,128,0.2)',  dot: '#6b7280' },
  active:    { label: 'Active',    color: '#10b981', bg: 'rgba(16,185,129,0.1)',    border: 'rgba(16,185,129,0.25)',  dot: '#10b981', pulse: true },
  paused:    { label: 'Paused',    color: '#f59e0b', bg: 'rgba(245,158,11,0.1)',    border: 'rgba(245,158,11,0.25)',  dot: '#f59e0b' },
  completed: { label: 'Completed', color: '#7c5cff', bg: 'rgba(124,92,255,0.1)',    border: 'rgba(124,92,255,0.25)', dot: '#7c5cff' },
};

const FILTER_TABS = ['all', 'active', 'paused', 'draft'] as const;
type FilterTab = typeof FILTER_TABS[number];

export default function CampaignsPage() {
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<FilterTab>("all");
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [editCampaign, setEditCampaign] = useState<Campaign | null>(null);
  const [editForm, setEditForm] = useState({
    name: "",
    description: "",
    subject_template: "",
    body_template: "",
    daily_send_limit: 50,
  });
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    loadCampaigns();
    const interval = setInterval(loadCampaigns, 10000);
    return () => clearInterval(interval);
  }, []);

  const loadCampaigns = async () => {
    try {
      const data = await getCampaigns();
      setCampaigns(data);
    } catch (err) {
      console.error("Failed to load campaigns:", err);
    } finally {
      setLoading(false);
    }
  };

  const handleStart = async (id: string) => {
    setActionLoading(id);
    try { await startCampaign(id); loadCampaigns(); } catch (err) { console.error(err); } finally { setActionLoading(null); }
  };

  const handlePause = async (id: string) => {
    setActionLoading(id);
    try { await pauseCampaign(id); loadCampaigns(); } catch (err) { console.error(err); } finally { setActionLoading(null); }
  };

  const handleDelete = async (id: string) => {
    if (!window.confirm("Delete this campaign? This cannot be undone.")) return;
    setActionLoading(id);
    try { await deleteCampaign(id); loadCampaigns(); } catch (err) { console.error(err); } finally { setActionLoading(null); }
  };

  const openEditModal = (campaign: Campaign) => {
    setEditCampaign(campaign);
    setEditForm({
      name: campaign.name,
      description: campaign.description || "",
      subject_template: campaign.subject_template || "",
      body_template: campaign.body_template || "",
      daily_send_limit: campaign.daily_send_limit || 50,
    });
  };

  const handleSaveEdit = async () => {
    if (!editCampaign) return;
    setSaving(true);
    try { await updateCampaign(editCampaign.id, editForm); setEditCampaign(null); loadCampaigns(); }
    catch (err) { console.error(err); } finally { setSaving(false); }
  };

  const filteredCampaigns = filter === "all" ? campaigns : campaigns.filter((c) => c.status === filter);
  const statusCounts = {
    all: campaigns.length,
    active: campaigns.filter((c) => c.status === "active").length,
    paused: campaigns.filter((c) => c.status === "paused").length,
    draft: campaigns.filter((c) => c.status === "draft").length,
  };

  const cardStyle: React.CSSProperties = {
    background: 'var(--card-bg)',
    border: '1px solid var(--card-border)',
    borderRadius: '14px',
    boxShadow: 'var(--card-shadow)',
  };

  const inputStyle: React.CSSProperties = {
    width: '100%',
    padding: '9px 12px',
    fontSize: '13px',
    background: 'var(--card-bg)',
    border: '1px solid var(--card-border)',
    borderRadius: '8px',
    color: 'var(--foreground-color)',
    fontFamily: 'inherit',
    outline: 'none',
  };

  return (
    <div style={{ padding: '24px', maxWidth: '1200px', margin: '0 auto' }}>
      {/* Page Header */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: '24px', flexWrap: 'wrap', gap: '12px' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '4px' }}>
            <div style={{
              width: '36px', height: '36px', borderRadius: '10px',
              background: 'linear-gradient(135deg, rgba(124,92,255,0.2), rgba(124,92,255,0.05))',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}>
              <Megaphone size={18} color="#7c5cff" />
            </div>
            <h1 style={{ fontSize: '22px', fontWeight: '800', color: 'var(--foreground-color)', margin: 0, letterSpacing: '-0.02em' }}>
              Campaigns
            </h1>
          </div>
          <p style={{ fontSize: '13px', color: 'var(--sidebar-text-muted)', margin: 0, marginLeft: '46px' }}>
            {campaigns.length} campaigns · {statusCounts.active} active
          </p>
        </div>
        <Link href="/dashboard/campaigns/new" style={{
          display: 'inline-flex', alignItems: 'center', gap: '7px',
          padding: '10px 20px', borderRadius: '10px',
          background: 'linear-gradient(135deg, #7c5cff, #6344d9)',
          color: 'white', textDecoration: 'none',
          fontSize: '13px', fontWeight: '600',
          boxShadow: '0 4px 16px rgba(124,92,255,0.4)',
        }}>
          <Plus size={16} /> New Campaign
        </Link>
      </div>

      {/* Status Filter Tabs */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '20px', flexWrap: 'wrap', gap: '12px' }}>
        <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
          {FILTER_TABS.map((tab) => {
            const isActive = filter === tab;
            const cfg = STATUS_CONFIG[tab] || STATUS_CONFIG.draft;
            return (
              <button key={tab} onClick={() => setFilter(tab)} style={{
                display: 'flex', alignItems: 'center', gap: '7px',
                padding: '8px 16px', borderRadius: '10px',
                background: isActive ? 'linear-gradient(135deg, #7c5cff, #6344d9)' : 'var(--card-bg)',
                border: isActive ? 'none' : '1px solid var(--card-border)',
                color: isActive ? 'white' : 'var(--sidebar-text-muted)',
                fontSize: '13px', fontWeight: '600', cursor: 'pointer',
                boxShadow: isActive ? '0 4px 12px rgba(124,92,255,0.3)' : 'var(--card-shadow)',
                transition: 'all 0.2s ease',
              }}>
                {tab !== 'all' && (
                  <span style={{
                    width: '7px', height: '7px', borderRadius: '50%',
                    background: isActive ? 'rgba(255,255,255,0.8)' : cfg.dot,
                    flexShrink: 0,
                  }} />
                )}
                {tab.charAt(0).toUpperCase() + tab.slice(1)}
                <span style={{
                  padding: '1px 7px', borderRadius: '999px', fontSize: '11px', fontWeight: '700',
                  background: isActive ? 'rgba(255,255,255,0.2)' : 'var(--sidebar-hover)',
                }}>
                  {statusCounts[tab as FilterTab] ?? statusCounts.all}
                </span>
              </button>
            );
          })}
        </div>

        <button onClick={loadCampaigns} style={{
          display: 'inline-flex', alignItems: 'center', gap: '6px',
          padding: '8px 16px', borderRadius: '10px',
          background: 'var(--card-bg)',
          border: '1px solid var(--card-border)',
          color: 'var(--sidebar-text-muted)',
          fontSize: '13px', fontWeight: '600', cursor: 'pointer',
          boxShadow: 'var(--card-shadow)',
          transition: 'all 0.2s ease',
        }}>
          <RotateCcw size={14} /> Refresh
        </button>
      </div>

      {/* Campaigns List */}
      {loading ? (
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '200px' }}>
          <div style={{ textAlign: 'center' }}>
            <div style={{ width: '36px', height: '36px', border: '3px solid rgba(124,92,255,0.2)', borderTopColor: '#7c5cff', borderRadius: '50%', animation: 'spin 0.8s linear infinite', margin: '0 auto 12px' }} />
            <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
            <p style={{ color: 'var(--sidebar-text-muted)', fontSize: '13px' }}>Loading campaigns...</p>
          </div>
        </div>
      ) : filteredCampaigns.length === 0 ? (
        <div style={{ ...cardStyle, padding: '60px', textAlign: 'center' }}>
          <div style={{ width: '56px', height: '56px', borderRadius: '16px', background: 'rgba(124,92,255,0.1)', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 16px' }}>
            <Megaphone size={24} color="#7c5cff" />
          </div>
          <h3 style={{ fontSize: '16px', fontWeight: '700', color: 'var(--foreground-color)', margin: '0 0 8px' }}>No campaigns yet</h3>
          <p style={{ fontSize: '13px', color: 'var(--sidebar-text-muted)', margin: '0 0 20px' }}>Create your first campaign to start outreach automation.</p>
          <Link href="/dashboard/campaigns/new" style={{
            display: 'inline-flex', alignItems: 'center', gap: '7px',
            padding: '10px 20px', borderRadius: '10px',
            background: 'linear-gradient(135deg, #7c5cff, #6344d9)',
            color: 'white', textDecoration: 'none',
            fontSize: '13px', fontWeight: '600',
          }}>
            <Plus size={15} /> Create Campaign
          </Link>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          {filteredCampaigns.map((campaign) => {
            const cfg = STATUS_CONFIG[campaign.status] || STATUS_CONFIG.draft;
            const isLoading = actionLoading === campaign.id;
            return (
              <div key={campaign.id} style={{
                ...cardStyle,
                padding: '18px 22px',
                display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                gap: '16px', flexWrap: 'wrap',
                transition: 'box-shadow 0.2s ease, transform 0.2s ease',
              }}
              onMouseEnter={e => {
                (e.currentTarget as HTMLDivElement).style.boxShadow = 'var(--card-hover-shadow)';
                (e.currentTarget as HTMLDivElement).style.transform = 'translateY(-1px)';
              }}
              onMouseLeave={e => {
                (e.currentTarget as HTMLDivElement).style.boxShadow = 'var(--card-shadow)';
                (e.currentTarget as HTMLDivElement).style.transform = 'translateY(0)';
              }}
              >
                {/* Campaign Icon + Info */}
                <div style={{ display: 'flex', alignItems: 'center', gap: '14px', flex: 1, minWidth: '200px' }}>
                  <div style={{
                    width: '44px', height: '44px', borderRadius: '12px',
                    background: cfg.bg, border: `1px solid ${cfg.border}`,
                    display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
                  }}>
                    {campaign.status === 'active' ? <Play size={18} color={cfg.color} fill={cfg.color} /> :
                     campaign.status === 'paused' ? <Pause size={18} color={cfg.color} /> :
                     <Mail size={18} color={cfg.color} />}
                  </div>
                  <div>
                    <Link href={`/dashboard/campaigns/${campaign.id}`} style={{
                      fontSize: '15px', fontWeight: '700', color: 'var(--foreground-color)',
                      textDecoration: 'none', display: 'block', marginBottom: '4px',
                    }}>
                      {campaign.name}
                    </Link>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                      <span style={{
                        display: 'inline-flex', alignItems: 'center', gap: '5px',
                        padding: '3px 10px', borderRadius: '999px',
                        background: cfg.bg, border: `1px solid ${cfg.border}`,
                        color: cfg.color, fontSize: '11px', fontWeight: '600',
                      }}>
                        <span style={{
                          width: '6px', height: '6px', borderRadius: '50%', background: cfg.color,
                          ...(cfg.pulse ? { boxShadow: `0 0 6px ${cfg.color}` } : {}),
                        }} />
                        {cfg.label}
                      </span>
                      <span style={{ fontSize: '11px', color: 'var(--sidebar-text-muted)' }}>
                        Created {new Date(campaign.created_at).toLocaleDateString()}
                      </span>
                    </div>
                  </div>
                </div>

                {/* Stats */}
                <div style={{ display: 'flex', alignItems: 'center', gap: '24px', flexShrink: 0 }}>
                  <div style={{ textAlign: 'center' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '5px', justifyContent: 'center' }}>
                      <Users size={13} color="var(--sidebar-text-muted)" />
                      <span style={{ fontSize: '18px', fontWeight: '800', color: 'var(--foreground-color)' }}>
                        {Math.max(0, campaign.total_leads || 0)}
                      </span>
                    </div>
                    <div style={{ fontSize: '10px', color: 'var(--sidebar-text-muted)', fontWeight: '500' }}>Leads</div>
                  </div>
                  <div style={{ textAlign: 'center' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '5px', justifyContent: 'center' }}>
                      <Mail size={13} color="#7c5cff" />
                      <span style={{ fontSize: '18px', fontWeight: '800', color: '#7c5cff' }}>
                        {campaign.emails_sent || 0}
                      </span>
                    </div>
                    <div style={{ fontSize: '10px', color: 'var(--sidebar-text-muted)', fontWeight: '500' }}>Sent</div>
                  </div>
                </div>

                {/* Actions */}
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexShrink: 0 }}>
                  {campaign.status === 'active' && (
                    <button onClick={() => handlePause(campaign.id)} disabled={isLoading} style={{
                      padding: '7px 14px', borderRadius: '8px', border: 'none',
                      background: 'rgba(245,158,11,0.12)', color: '#f59e0b',
                      fontSize: '12px', fontWeight: '600', cursor: 'pointer',
                      display: 'flex', alignItems: 'center', gap: '5px',
                      opacity: isLoading ? 0.5 : 1,
                    }}>
                      <Pause size={13} /> Pause
                    </button>
                  )}
                  {campaign.status === 'paused' && (
                    <button onClick={() => handleStart(campaign.id)} disabled={isLoading} style={{
                      padding: '7px 14px', borderRadius: '8px', border: 'none',
                      background: 'rgba(16,185,129,0.12)', color: '#10b981',
                      fontSize: '12px', fontWeight: '600', cursor: 'pointer',
                      display: 'flex', alignItems: 'center', gap: '5px',
                      opacity: isLoading ? 0.5 : 1,
                    }}>
                      <RotateCcw size={13} /> Resume
                    </button>
                  )}
                  {campaign.status === 'draft' && (
                    <button onClick={() => handleStart(campaign.id)} disabled={isLoading} style={{
                      padding: '7px 14px', borderRadius: '8px', border: 'none',
                      background: 'rgba(16,185,129,0.12)', color: '#10b981',
                      fontSize: '12px', fontWeight: '600', cursor: 'pointer',
                      display: 'flex', alignItems: 'center', gap: '5px',
                      opacity: isLoading ? 0.5 : 1,
                    }}>
                      <Play size={13} /> Start
                    </button>
                  )}
                  <button onClick={() => openEditModal(campaign)} style={{
                    width: '32px', height: '32px', borderRadius: '8px', border: '1px solid var(--card-border)',
                    background: 'var(--sidebar-hover)', cursor: 'pointer',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    color: 'var(--sidebar-text-muted)',
                  }}>
                    <Pencil size={14} />
                  </button>
                  <Link href={`/dashboard/campaigns/${campaign.id}`} style={{
                    width: '32px', height: '32px', borderRadius: '8px', border: '1px solid var(--card-border)',
                    background: 'var(--sidebar-hover)', cursor: 'pointer',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    color: 'var(--sidebar-text-muted)', textDecoration: 'none',
                  }}>
                    <Eye size={14} />
                  </Link>
                  <button onClick={() => handleDelete(campaign.id)} disabled={isLoading} style={{
                    width: '32px', height: '32px', borderRadius: '8px', border: '1px solid rgba(239,68,68,0.2)',
                    background: 'rgba(239,68,68,0.06)', cursor: 'pointer',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    color: '#ef4444', opacity: isLoading ? 0.5 : 1,
                  }}>
                    <Trash2 size={14} />
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Edit Campaign Modal */}
      {editCampaign && (
        <div style={{
          position: 'fixed', inset: 0, zIndex: 50,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          background: 'rgba(0,0,0,0.7)', backdropFilter: 'blur(4px)',
        }}>
          <div style={{
            width: '100%', maxWidth: '520px', borderRadius: '20px',
            background: 'var(--card-bg)', border: '1px solid var(--card-border)',
            boxShadow: '0 32px 64px rgba(0,0,0,0.5)',
            padding: '28px', maxHeight: '90vh', overflowY: 'auto',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '20px' }}>
              <h2 style={{ fontSize: '18px', fontWeight: '800', color: 'var(--foreground-color)', margin: 0 }}>Edit Campaign</h2>
              <button onClick={() => setEditCampaign(null)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--sidebar-text-muted)', display: 'flex' }}>
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M18 6L6 18M6 6l12 12"/></svg>
              </button>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
              {[
                { label: 'Campaign Name', key: 'name', type: 'text' },
                { label: 'Description', key: 'description', type: 'textarea' },
                { label: 'Subject Template', key: 'subject_template', type: 'text', placeholder: 'Hi {{first_name}}, quick question' },
                { label: 'Body Template', key: 'body_template', type: 'textarea', placeholder: 'Hi {{first_name}}, I noticed...' },
              ].map((field) => (
                <div key={field.key}>
                  <label style={{ display: 'block', fontSize: '12px', fontWeight: '600', color: 'var(--sidebar-text-muted)', marginBottom: '6px', letterSpacing: '0.04em' }}>
                    {field.label}
                  </label>
                  {field.type === 'textarea' ? (
                    <textarea
                      value={editForm[field.key as keyof typeof editForm] as string}
                      onChange={(e) => setEditForm({ ...editForm, [field.key]: e.target.value })}
                      placeholder={field.placeholder}
                      rows={field.key === 'body_template' ? 4 : 2}
                      style={{ ...inputStyle, resize: 'vertical' }}
                    />
                  ) : (
                    <input
                      type={field.type}
                      value={editForm[field.key as keyof typeof editForm] as string}
                      onChange={(e) => setEditForm({ ...editForm, [field.key]: e.target.value })}
                      placeholder={field.placeholder}
                      style={inputStyle}
                    />
                  )}
                </div>
              ))}
              <div>
                <label style={{ display: 'block', fontSize: '12px', fontWeight: '600', color: 'var(--sidebar-text-muted)', marginBottom: '6px', letterSpacing: '0.04em' }}>
                  Daily Send Limit
                </label>
                <input
                  type="number"
                  value={editForm.daily_send_limit}
                  min={1} max={500}
                  onChange={(e) => setEditForm({ ...editForm, daily_send_limit: parseInt(e.target.value) || 50 })}
                  style={inputStyle}
                />
              </div>
              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', paddingTop: '8px' }}>
                <button onClick={() => setEditCampaign(null)} style={{
                  padding: '9px 18px', borderRadius: '9px', border: '1px solid var(--card-border)',
                  background: 'var(--sidebar-hover)', color: 'var(--foreground-color)',
                  fontSize: '13px', fontWeight: '600', cursor: 'pointer',
                }}>
                  Cancel
                </button>
                <button onClick={handleSaveEdit} disabled={saving} style={{
                  padding: '9px 18px', borderRadius: '9px', border: 'none',
                  background: 'linear-gradient(135deg, #7c5cff, #6344d9)',
                  color: 'white', fontSize: '13px', fontWeight: '600', cursor: 'pointer',
                  opacity: saving ? 0.7 : 1,
                }}>
                  {saving ? 'Saving...' : 'Save Changes'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
