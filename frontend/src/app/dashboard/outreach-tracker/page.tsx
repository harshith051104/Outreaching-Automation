"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  CHECKBOX_FIELDS,
  CHECKBOX_LABELS,
  TrackerFilters,
  TrackerLead,
  TrackerResponse,
  getTrackerLeads,
  updateCheckboxes,
  getTrackerUsers,
  createTrackerUser,
  updateTrackerUser,
  deleteTrackerUser,
  triggerPullSync,
  triggerPushSync,
  type TrackerUser,
} from "@/services/outreach-tracker-api";
import { getCampaigns } from "@/services/campaign-api";
import { createLead, deleteLead } from "@/services/lead-api";
import type { Campaign } from "@/types/campaign";
import Link from "next/link";
import { useAuthStore } from "@/store/auth-store";
import {
  Plus,
  Menu,
  Grid,
  ChevronLeft,
  ChevronRight,
  Users,
  Check,
  RefreshCw,
  Sparkles,
  Search,
  BookOpen,
  ArrowRight,
  ExternalLink,
  UserPlus,
  Sliders,
  Filter,
  Save,
  Pencil,
  Loader2,
  Trash2,
  Lock,
} from "lucide-react";

// ─── Utility ─────────────────────────────────────────────────────────────────

function formatDate(d: string | null) {
  if (!d) return "—";
  return new Date(d).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "2-digit" });
}

// ─── Checkbox Cell Component ──────────────────────────────────────────────────

function CheckCell({
  checked,
  field,
  leadId,
  onChange,
  disabled,
}: {
  checked: boolean;
  field: string;
  leadId: string;
  onChange: (leadId: string, field: string, val: boolean) => void;
  disabled?: boolean;
}) {
  return (
    <div className="flex items-center justify-center">
      <button
        onClick={() => onChange(leadId, field, !checked)}
        disabled={disabled}
        className={`w-5 h-5 rounded-md border flex items-center justify-center transition-all focus:outline-none ${
          checked
            ? "bg-violet-600 border-violet-500 text-white shadow-lg shadow-violet-500/25"
            : "border-slate-700 bg-slate-900/50 text-transparent hover:border-slate-500 hover:bg-slate-900"
        } ${disabled ? "opacity-50 cursor-not-allowed" : "cursor-pointer"}`}
      >
        {checked && <Check size={12} strokeWidth={3} />}
      </button>
    </div>
  );
}

// ─── Main Page ────────────────────────────────────────────────────────────────

export default function OutreachTrackerPage() {
  const { user } = useAuthStore();
  const isAdmin = user?.role === "admin";

  const [data, setData] = useState<TrackerResponse>({
    total: 0, page: 1, page_size: 50, total_pages: 1, leads: [],
  });
  const [users, setUsers] = useState<TrackerUser[]>([]);
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [selectedUserTab, setSelectedUserTab] = useState<string>("All");
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState<TrackerFilters>({
    page: 1, page_size: 50, sort_by: "last_activity_at", sort_dir: -1,
  });
  const [search, setSearch] = useState("");
  const [updating, setUpdating] = useState<Set<string>>(new Set());
  const searchTimeout = useRef<NodeJS.Timeout | null>(null);

  // Sheets Sync and notification states
  const [syncing, setSyncing] = useState(false);
  const [notification, setNotification] = useState<{ type: "success" | "error"; text: string } | null>(null);

  // Editing cells in Spreadsheet
  const [editingCell, setEditingCell] = useState<{ leadId: string; field: string } | null>(null);
  const cellInputRef = useRef<HTMLInputElement | null>(null);

  // Bottom Tabs dropdown menus state
  const [activeUserDropdownId, setActiveUserDropdownId] = useState<string | null>(null);

  // Local values for cells (inline editing)
  const [localValues, setLocalValues] = useState<Record<string, Record<string, string>>>({});

  // User Management Modal state
  const [showUserModal, setShowUserModal] = useState(false);
  const [editingUser, setEditingUser] = useState<TrackerUser | null>(null);
  const [userForm, setUserForm] = useState({
    name: "",
    display_name: "",
    email: "",
    role: "member",
    password: "",
  });

  // Add Lead Modal state
  const [showAddLeadModal, setShowAddLeadModal] = useState(false);
  const [leadForm, setLeadForm] = useState({
    name: "",
    email: "",
    focus: "",
    linkedin: "",
    company: "",
    campaign_id: "",
    notes: "",
  });

  // Load Leads Data
  const loadLeads = useCallback(async (f: TrackerFilters, silent = false) => {
    if (!silent) setLoading(true);
    try {
      const res = await getTrackerLeads(f);
      setData(res);
    } catch (e) {
      console.error("Failed to load tracker leads:", e);
      if (!silent) showToast("error", "Failed to load leads data.");
    } finally {
      if (!silent) setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadLeads(filters);
  }, [filters, loadLeads]);

  // Polling loop for real-time collaboration updates
  useEffect(() => {
    const interval = setInterval(async () => {
      if (!editingCell && updating.size === 0 && !loading) {
        loadLeads(filters, true);
        try {
          const userList = await getTrackerUsers();
          setUsers(userList);
        } catch (err) {
          console.error("Failed to silently load users:", err);
        }
      }
    }, 10000); // silent check every 10 seconds

    return () => clearInterval(interval);
  }, [filters, editingCell, updating, loading, loadLeads]);

  // Load Team Users and Campaigns
  const loadInitialData = async () => {
    try {
      const [userList, campaignList] = await Promise.all([
        getTrackerUsers(),
        getCampaigns(),
      ]);
      setUsers(userList);
      setCampaigns(campaignList);
      if (campaignList.length > 0) {
        setLeadForm(prev => ({ ...prev, campaign_id: campaignList[0].id }));
      }
    } catch (err) {
      console.error("Failed to load initial metadata:", err);
    }
  };

  useEffect(() => {
    loadInitialData();
  }, []);

  // Sync local edit values when master leads load
  useEffect(() => {
    const values: Record<string, Record<string, string>> = {};
    data.leads.forEach(l => {
      values[l.id] = {
        name: l.name || "",
        focus: l.focus || "",
        linkedin: l.linkedin || "",
        email: l.email || "",
        notes: l.notes || "",
        company: l.company || "",
      };
    });
    setLocalValues(values);
  }, [data.leads]);

  // Focus inline input automatically
  useEffect(() => {
    if (editingCell && cellInputRef.current) {
      cellInputRef.current.focus();
      cellInputRef.current.select();
    }
  }, [editingCell]);

  // Close dropdown on click outside
  useEffect(() => {
    const handleOutsideClick = () => {
      setActiveUserDropdownId(null);
    };
    window.addEventListener("click", handleOutsideClick);
    return () => window.removeEventListener("click", handleOutsideClick);
  }, []);

  const showToast = (type: "success" | "error", text: string) => {
    setNotification({ type, text });
    setTimeout(() => {
      setNotification(null);
    }, 4000);
  };

  const handleSearch = (val: string) => {
    setSearch(val);
    if (searchTimeout.current) clearTimeout(searchTimeout.current);
    searchTimeout.current = setTimeout(() => {
      setFilters(f => ({ ...f, search: val || undefined, page: 1 }));
    }, 400);
  };

  // Checkbox toggle handler
  const handleCheckboxChange = async (leadId: string, field: string, val: boolean) => {
    const key = `${leadId}-${field}`;
    setUpdating(prev => new Set(prev).add(key));

    // Optimistic update
    setData(prev => ({
      ...prev,
      leads: prev.leads.map(l => l.id === leadId ? { ...l, [field]: val } : l),
    }));

    try {
      await updateCheckboxes(leadId, { [field]: val });
    } catch (e) {
      // Revert on error
      setData(prev => ({
        ...prev,
        leads: prev.leads.map(l => l.id === leadId ? { ...l, [field]: !val } : l),
      }));
      console.error("Checkbox update failed:", e);
      showToast("error", "Failed to update checkbox in database.");
    } finally {
      setUpdating(prev => { const s = new Set(prev); s.delete(key); return s; });
    }
  };

  // Local text input change handler
  const handleLocalChange = (leadId: string, field: string, val: string) => {
    setLocalValues(prev => ({
      ...prev,
      [leadId]: {
        ...(prev[leadId] || {}),
        [field]: val,
      }
    }));
  };

  // Commit text field saves
  const handleFieldSave = async (leadId: string, field: string, forcedVal?: string) => {
    const val = forcedVal !== undefined ? forcedVal : localValues[leadId]?.[field] ?? "";
    const lead = data.leads.find(l => l.id === leadId);
    if (!lead) return;

    const originalVal = lead[field as keyof TrackerLead] || "";
    if (originalVal === val) {
      setEditingCell(null);
      return;
    }

    // Optimistic update
    setData(prev => ({
      ...prev,
      leads: prev.leads.map(l => l.id === leadId ? { ...l, [field]: val } : l)
    }));

    try {
      await updateCheckboxes(leadId, { [field]: val });
    } catch (e) {
      console.error("Field save failed:", e);
      showToast("error", "Sync to server failed. Value reverted.");
      // Revert master data
      setData(prev => ({
        ...prev,
        leads: prev.leads.map(l => l.id === leadId ? { ...l, [field]: originalVal } : l)
      }));
      // Revert local values
      setLocalValues(prev => ({
        ...prev,
        [leadId]: {
          ...(prev[leadId] || {}),
          [field]: String(originalVal),
        }
      }));
    } finally {
      setEditingCell(null);
    }
  };

  // Delete Lead Handler
  const handleDeleteLead = async (leadId: string, leadName: string) => {
    if (window.confirm(`Are you sure you want to delete lead "${leadName}"?`)) {
      try {
        await deleteLead(leadId);
        showToast("success", `Lead "${leadName}" successfully deleted.`);
        loadLeads(filters);
      } catch (err: any) {
        showToast("error", err.response?.data?.detail || "Failed to delete lead.");
      }
    }
  };

  // Tab Selection (Bottom sheets)
  const selectTab = (tabName: string) => {
    setSelectedUserTab(tabName);
    if (tabName === "All") {
      setFilters(f => ({ ...f, assigned_user: undefined, page: 1 }));
    } else {
      setFilters(f => ({ ...f, assigned_user: tabName, page: 1 }));
    }
    setEditingCell(null);
  };

  // Manual Pull from Google Sheets
  const handlePullSync = async () => {
    setSyncing(true);
    try {
      const res = await triggerPullSync();
      showToast("success", res.message || "Successfully pulled data from Google Sheets.");
      loadLeads(filters);
    } catch (err: any) {
      console.error("Pull sync failed:", err);
      showToast("error", err.response?.data?.detail || "Google Sheets sync pull failed.");
    } finally {
      setSyncing(false);
    }
  };

  // Manual Push to Google Sheets
  const handlePushSync = async () => {
    setSyncing(true);
    try {
      const res = await triggerPushSync();
      showToast("success", res.message || "Successfully pushed data to Google Sheets.");
    } catch (err: any) {
      console.error("Push sync failed:", err);
      showToast("error", err.response?.data?.detail || "Google Sheets sync push failed.");
    } finally {
      setSyncing(false);
    }
  };

  // Handle Team User Creation
  const handleCreateUser = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await createTrackerUser(userForm);
      showToast("success", `User "${userForm.display_name || userForm.name}" created successfully.`);
      setUserForm({ name: "", display_name: "", email: "", role: "member", password: "" });
      setEditingUser(null);
      loadInitialData();
    } catch (err: any) {
      showToast("error", err.response?.data?.detail || "Failed to create team member.");
    }
  };

  // Handle Team User Update
  const handleUpdateUser = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingUser) return;
    try {
      await updateTrackerUser(editingUser.id, {
        name: userForm.name,
        display_name: userForm.display_name,
        email: userForm.email,
        role: userForm.role,
      });
      showToast("success", `User details updated successfully.`);
      setEditingUser(null);
      setUserForm({ name: "", display_name: "", email: "", role: "member", password: "" });
      loadInitialData();
    } catch (err: any) {
      showToast("error", err.response?.data?.detail || "Failed to update team member.");
    }
  };

  // Handle Team User Deletion
  const handleDeleteUser = async (userId: string, userName: string) => {
    if (window.confirm(`Are you sure you want to remove team member "${userName}"?`)) {
      try {
        await deleteTrackerUser(userId);
        showToast("success", `User "${userName}" has been successfully removed.`);
        loadInitialData();
        if (selectedUserTab === userName) {
          selectTab("All");
        }
        if (editingUser?.id === userId) {
          setEditingUser(null);
          setUserForm({ name: "", display_name: "", email: "", role: "member", password: "" });
        }
      } catch (err: any) {
        showToast("error", err.response?.data?.detail || "Failed to remove team member.");
      }
    }
  };

  // Add Lead (Row insert)
  const handleAddLeadSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!leadForm.name || !leadForm.email) {
      showToast("error", "Name and Email are required.");
      return;
    }
    try {
      await createLead({
        campaign_id: leadForm.campaign_id,
        name: leadForm.name,
        email: leadForm.email,
        company: leadForm.company || undefined,
        role: "investor",
      });
      showToast("success", `New lead "${leadForm.name}" successfully created.`);
      setShowAddLeadModal(false);
      setLeadForm({
        name: "",
        email: "",
        focus: "",
        linkedin: "",
        company: "",
        campaign_id: campaigns[0]?.id || "",
        notes: "",
      });
      loadLeads(filters);
    } catch (err: any) {
      showToast("error", err.response?.data?.detail || "Failed to add lead.");
    }
  };

  const handleCellDoubleClick = (leadId: string, field: string) => {
    setEditingCell({ leadId, field });
  };

  return (
    <div className="flex flex-col h-screen bg-[#0a0a0f] text-white overflow-hidden select-none font-sans">
      
      {/* Toast Notification */}
      {notification && (
        <div className="fixed top-4 right-4 z-50 flex items-center gap-2.5 px-5 py-3.5 rounded-xl border border-white/10 bg-slate-900/90 text-white backdrop-blur-md animate-fadeIn shadow-2xl">
          <div className={`w-2 h-2 rounded-full ${notification.type === "success" ? "bg-emerald-500 animate-pulse" : "bg-rose-500"}`} />
          <span className="text-xs font-bold uppercase tracking-wider">{notification.text}</span>
        </div>
      )}

      {/* ─── HEADER BAR ─── */}
      <div className="flex flex-col border-b border-white/5 bg-[#0e0e15] shrink-0 p-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-black bg-gradient-to-r from-violet-400 to-indigo-400 bg-clip-text text-transparent flex items-center gap-2">
              <Sliders className="text-violet-400" size={24} />
              Outreach Progress Tracker
            </h1>
            <p className="text-xs text-slate-400 mt-1 font-medium">
              {data.total} leads found · Real-time pipeline milestone checklists
            </p>
          </div>

          <div className="flex items-center gap-3">
            {/* Search Box */}
            <div className="relative">
              <span className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-500"><Search size={14} /></span>
              <input
                value={search}
                onChange={e => handleSearch(e.target.value)}
                placeholder="Search leads..."
                className="pl-9 pr-4 py-2 bg-white/5 border border-white/10 rounded-xl text-xs text-white placeholder-slate-500 focus:outline-none focus:border-violet-500/50 focus:ring-1 focus:ring-violet-500/20 font-medium w-60 transition-all"
              />
            </div>

            {isAdmin && (
              <button 
                onClick={() => { setShowUserModal(true); setEditingUser(null); }}
                className="flex items-center gap-1.5 px-4 py-2 bg-white/5 hover:bg-white/10 border border-white/10 text-slate-200 rounded-xl text-xs font-bold transition-all cursor-pointer"
              >
                <Users size={14} />
                Manage Team
              </button>
            )}

            <button 
              onClick={handlePullSync} 
              disabled={syncing}
              className="flex items-center gap-1.5 px-4 py-2 bg-white/5 hover:bg-white/10 border border-white/10 text-slate-200 rounded-xl text-xs font-bold transition-all disabled:opacity-50 cursor-pointer"
            >
              <RefreshCw size={13} className={syncing ? "animate-spin" : ""} />
              Pull Sheets
            </button>

            <button 
              onClick={handlePushSync} 
              disabled={syncing}
              className="flex items-center gap-1.5 px-4 py-2 bg-violet-600/20 hover:bg-violet-600/30 border border-violet-500/30 text-violet-300 rounded-xl text-xs font-bold transition-all disabled:opacity-50 cursor-pointer"
            >
              <RefreshCw size={13} className={syncing ? "animate-spin" : ""} />
              Push Sheets
            </button>

            <button 
              onClick={() => setShowAddLeadModal(true)}
              className="flex items-center gap-1 px-4 py-2 bg-gradient-to-r from-violet-600 to-indigo-600 text-white font-bold text-xs rounded-xl hover:shadow-lg hover:shadow-violet-600/20 transition-all cursor-pointer"
            >
              <Plus size={14} />
              Add Lead
            </button>
          </div>
        </div>
      </div>

      {/* ─── GRID / TABLE ─── */}
      <div className="flex-1 overflow-hidden bg-[#0a0a0f] p-6 pt-0 flex flex-col max-w-full">
        <div className="flex-1 border border-white/5 bg-[#0f0f15]/50 backdrop-blur-xl rounded-2xl overflow-hidden flex flex-col max-w-full h-full">
          {loading ? (
            <div className="flex flex-col items-center justify-center flex-1 gap-3 text-slate-400 h-full">
              <Loader2 className="animate-spin text-violet-500" size={32} />
              <span className="text-xs font-bold uppercase tracking-wider">Loading Tracker Data...</span>
            </div>
          ) : (
            <div className="overflow-auto flex-1 scrollbar-thin scrollbar-thumb-white/10 max-w-full h-full">
              <table className="w-full border-collapse text-left text-xs text-slate-300 min-w-[2450px]">
              <thead>
                <tr className="border-b border-white/5 bg-[#12121a] text-slate-400 font-bold uppercase tracking-wider text-[10px]">
                  <th className="p-3.5 pl-6 min-w-[180px]">Investor Name</th>
                  <th className="p-3.5 min-w-[120px]">Focus</th>
                  <th className="p-3.5 min-w-[200px]">LinkedIn URL</th>
                  <th className="p-3.5 min-w-[180px]">Email</th>
                  
                  {/* Checklist Milestone Columns */}
                  {CHECKBOX_FIELDS.map(f => (
                    <th key={f} className="p-2 text-center min-w-[105px] whitespace-normal text-[9px] border-l border-white/5 leading-tight" title={CHECKBOX_LABELS[f]}>
                      {CHECKBOX_LABELS[f]}
                    </th>
                  ))}

                  <th className="p-3.5 min-w-[220px] border-l border-white/5">Notes</th>
                  <th className="p-3.5 min-w-[110px]">Last Activity</th>
                  <th className="p-3.5 text-center min-w-[110px]">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {data.leads.map((lead) => (
                  <tr 
                    key={lead.id} 
                    className="hover:bg-white/[0.01] transition-all align-middle group border-b border-white/5 h-[45px]"
                  >
                    
                    {/* Investor's Name */}
                    <td 
                      onDoubleClick={() => handleCellDoubleClick(lead.id, "name")}
                      className="p-3 pl-6 font-semibold text-white relative h-[45px]"
                    >
                      {editingCell?.leadId === lead.id && editingCell?.field === "name" ? (
                        <input
                          ref={cellInputRef}
                          value={localValues[lead.id]?.name ?? ""}
                          onChange={(e) => handleLocalChange(lead.id, "name", e.target.value)}
                          onBlur={() => handleFieldSave(lead.id, "name")}
                          onKeyDown={(e) => {
                            if (e.key === "Enter") handleFieldSave(lead.id, "name");
                          }}
                          className="absolute inset-0 w-full h-full px-3 bg-[#161622] text-white focus:outline-none focus:ring-1 focus:ring-violet-500 font-semibold"
                        />
                      ) : (
                        <div className="flex items-center justify-between group/cell pr-2">
                          <span className="truncate block">{localValues[lead.id]?.name || lead.name || "—"}</span>
                          <Pencil size={11} className="text-slate-600 opacity-0 group-hover/cell:opacity-100 transition-opacity cursor-pointer ml-1.5" />
                        </div>
                      )}
                    </td>

                    {/* Focus */}
                    <td 
                      onDoubleClick={() => handleCellDoubleClick(lead.id, "focus")}
                      className="p-3 text-slate-300 relative h-[45px]"
                    >
                      {editingCell?.leadId === lead.id && editingCell?.field === "focus" ? (
                        <input
                          ref={cellInputRef}
                          value={localValues[lead.id]?.focus ?? ""}
                          onChange={(e) => handleLocalChange(lead.id, "focus", e.target.value)}
                          onBlur={() => handleFieldSave(lead.id, "focus")}
                          onKeyDown={(e) => {
                            if (e.key === "Enter") handleFieldSave(lead.id, "focus");
                          }}
                          className="absolute inset-0 w-full h-full px-3 bg-[#161622] text-white focus:outline-none focus:ring-1 focus:ring-violet-500"
                        />
                      ) : (
                        <div className="flex items-center justify-between group/cell pr-2">
                          <span className="truncate block">{localValues[lead.id]?.focus || lead.focus || "—"}</span>
                          <Pencil size={11} className="text-slate-600 opacity-0 group-hover/cell:opacity-100 transition-opacity cursor-pointer ml-1.5" />
                        </div>
                      )}
                    </td>

                    {/* LinkedIn Profile */}
                    <td 
                      onDoubleClick={() => handleCellDoubleClick(lead.id, "linkedin")}
                      className="p-3 text-cyan-400 relative h-[45px]"
                    >
                      {editingCell?.leadId === lead.id && editingCell?.field === "linkedin" ? (
                        <input
                          ref={cellInputRef}
                          value={localValues[lead.id]?.linkedin ?? ""}
                          onChange={(e) => handleLocalChange(lead.id, "linkedin", e.target.value)}
                          onBlur={() => handleFieldSave(lead.id, "linkedin")}
                          onKeyDown={(e) => {
                            if (e.key === "Enter") handleFieldSave(lead.id, "linkedin");
                          }}
                          className="absolute inset-0 w-full h-full px-3 bg-[#161622] text-cyan-400 focus:outline-none focus:ring-1 focus:ring-violet-500"
                        />
                      ) : (
                        <div className="flex items-center justify-between group/cell pr-2">
                          <span className="truncate block underline cursor-pointer">
                            {localValues[lead.id]?.linkedin || lead.linkedin || "—"}
                          </span>
                          <div className="flex items-center gap-1.5 shrink-0 opacity-0 group-hover/cell:opacity-100 transition-opacity">
                            {lead.linkedin && (
                              <a
                                href={lead.linkedin.startsWith("http") ? lead.linkedin : `https://${lead.linkedin}`}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="text-slate-400 hover:text-cyan-400 transition-colors"
                              >
                                <ExternalLink size={11} />
                              </a>
                            )}
                            <Pencil size={11} className="text-slate-600 cursor-pointer" />
                          </div>
                        </div>
                      )}
                    </td>

                    {/* Email */}
                    <td 
                      onDoubleClick={() => handleCellDoubleClick(lead.id, "email")}
                      className="p-3 text-slate-300 relative h-[45px]"
                    >
                      {editingCell?.leadId === lead.id && editingCell?.field === "email" ? (
                        <input
                          ref={cellInputRef}
                          value={localValues[lead.id]?.email ?? ""}
                          onChange={(e) => handleLocalChange(lead.id, "email", e.target.value)}
                          onBlur={() => handleFieldSave(lead.id, "email")}
                          onKeyDown={(e) => {
                            if (e.key === "Enter") handleFieldSave(lead.id, "email");
                          }}
                          className="absolute inset-0 w-full h-full px-3 bg-[#161622] text-white focus:outline-none focus:ring-1 focus:ring-violet-500"
                        />
                      ) : (
                        <div className="flex items-center justify-between group/cell pr-2">
                          <span className="truncate block">{localValues[lead.id]?.email || lead.email || "—"}</span>
                          <Pencil size={11} className="text-slate-600 opacity-0 group-hover/cell:opacity-100 transition-opacity cursor-pointer ml-1.5" />
                        </div>
                      )}
                    </td>

                    {/* Checkbox Checklist Cells */}
                    {CHECKBOX_FIELDS.map(f => {
                      const isUp = updating.has(`${lead.id}-${f}`);
                      return (
                        <td key={f} className="p-2 border-l border-white/5 text-center">
                          <CheckCell
                            checked={!!lead[f as keyof TrackerLead]}
                            field={f}
                            leadId={lead.id}
                            onChange={handleCheckboxChange}
                            disabled={isUp}
                          />
                        </td>
                      );
                    })}

                    {/* Notes */}
                    <td 
                      onDoubleClick={() => handleCellDoubleClick(lead.id, "notes")}
                      className="p-3 text-slate-400 border-l border-white/5 relative h-[45px]"
                    >
                      {editingCell?.leadId === lead.id && editingCell?.field === "notes" ? (
                        <input
                          ref={cellInputRef}
                          value={localValues[lead.id]?.notes ?? ""}
                          onChange={(e) => handleLocalChange(lead.id, "notes", e.target.value)}
                          onBlur={() => handleFieldSave(lead.id, "notes")}
                          onKeyDown={(e) => {
                            if (e.key === "Enter") handleFieldSave(lead.id, "notes");
                          }}
                          className="absolute inset-0 w-full h-full px-3 bg-[#161622] text-white focus:outline-none focus:ring-1 focus:ring-violet-500"
                        />
                      ) : (
                        <div className="flex items-center justify-between group/cell pr-2">
                          <span className="truncate block italic">{localValues[lead.id]?.notes || lead.notes || "Add details..."}</span>
                          <Pencil size={11} className="text-slate-600 opacity-0 group-hover/cell:opacity-100 transition-opacity cursor-pointer ml-1.5" />
                        </div>
                      )}
                    </td>

                    {/* Last Activity */}
                    <td className="p-3 text-slate-500">
                      {formatDate(lead.last_activity_at)}
                    </td>

                    {/* Actions timeline link & Delete lead */}
                    <td className="p-3 text-center align-middle">
                      <div className="flex items-center justify-center gap-1.5">
                        <Link
                          href={`/dashboard/outreach-tracker/${lead.id}/timeline`}
                          className="inline-flex items-center gap-1 px-2.5 py-1.5 bg-violet-500/10 text-violet-400 hover:bg-violet-500 hover:text-white rounded-lg text-[10px] font-bold tracking-wider uppercase transition-all shadow-sm border border-violet-500/15 cursor-pointer"
                        >
                          Log
                          <ArrowRight size={10} />
                        </Link>
                        
                        <button
                          onClick={() => handleDeleteLead(lead.id, lead.name)}
                          className="inline-flex items-center justify-center p-1.5 bg-rose-500/10 text-rose-400 hover:bg-rose-600 hover:text-white rounded-lg text-[10px] font-bold transition-all border border-rose-500/15 cursor-pointer"
                          title="Delete Lead Row"
                        >
                          <Trash2 size={11} />
                        </button>
                      </div>
                    </td>

                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>

      {/* ─── BOTTOM SHEET SELECTION BAR ─── */}
      <div className="border-t border-white/10 bg-[#0d0d14]/90 backdrop-blur-md px-6 py-3.5 flex items-center justify-between shrink-0">
        
        {/* Dynamic Sheet Selection Tabs (Dark mode pills style matching image) */}
        <div className="flex-1 flex items-center overflow-x-auto gap-2 mx-6 scrollbar-none select-none">
          
          {/* All Tab */}
          <div className="relative group">
            <button
              onClick={() => selectTab("All")}
              className={`flex items-center gap-1.5 px-4.5 py-1.5 text-xs font-bold whitespace-nowrap transition-all border rounded-xl relative ${
                selectedUserTab === "All"
                  ? "bg-gradient-to-r from-violet-600 to-indigo-600 text-white border-violet-500/50 shadow-lg shadow-violet-500/25"
                  : "bg-white/5 text-slate-400 hover:bg-white/10 hover:text-slate-200 border-white/5"
              }`}
            >
              All
            </button>
          </div>

          {/* User Specific Tabs */}
          {users.map(u => {
            const userName = u.display_name || u.name;
            const isActive = selectedUserTab === userName;
            return (
              <div key={u.id} className="relative flex items-center shrink-0">
                <button
                  onClick={() => selectTab(userName)}
                  className={`flex items-center gap-1 px-4 py-1.5 text-xs font-bold whitespace-nowrap transition-all border rounded-xl relative ${
                    isActive
                      ? "bg-gradient-to-r from-violet-600 to-indigo-600 text-white border-violet-500/50 shadow-lg shadow-violet-500/25"
                      : "bg-white/5 text-slate-400 hover:bg-white/10 hover:text-slate-200 border-white/5"
                  }`}
                >
                  {userName}
                  
                  {/* Small Dropdown Arrow that acts as edit/delete menu trigger */}
                  <span 
                    onClick={(e) => {
                      e.stopPropagation();
                      setActiveUserDropdownId(activeUserDropdownId === u.id ? null : u.id);
                    }}
                    className="ml-1.5 pl-1 text-[10px] text-slate-500 hover:text-white font-bold select-none cursor-pointer"
                    title="User options"
                  >
                    ▾
                  </span>
                </button>

                {/* Dropdown Menu above the tab */}
                {activeUserDropdownId === u.id && (
                  <div className="absolute bottom-full mb-2 left-0 w-36 bg-[#12121a] border border-white/10 rounded-lg shadow-2xl z-50 py-1 font-sans">
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        setActiveUserDropdownId(null);
                        setEditingUser(u);
                        setUserForm({
                          name: u.name,
                          display_name: u.display_name,
                          email: u.email,
                          role: u.role || "member",
                          password: "",
                        });
                        setShowUserModal(true);
                      }}
                      className="flex items-center gap-1.5 w-full text-left px-3 py-2 text-slate-300 hover:bg-white/5 hover:text-white text-xs font-bold cursor-pointer"
                    >
                      <Pencil size={11} />
                      Edit Details
                    </button>
                    <button
                      onClick={async (e) => {
                        e.stopPropagation();
                        setActiveUserDropdownId(null);
                        await handleDeleteUser(u.id, userName);
                      }}
                      className="flex items-center gap-1.5 w-full text-left px-3 py-2 text-rose-400 hover:bg-rose-500/10 hover:text-rose-300 text-xs font-bold cursor-pointer"
                    >
                      <Trash2 size={11} />
                      Delete User
                    </button>
                  </div>
                )}
              </div>
            );
          })}

        </div>

        {/* Scroll controls and auto sync indicator */}
        <div className="flex items-center gap-2 text-slate-500 shrink-0">
          <button className="p-1 hover:bg-white/5 hover:text-white rounded-lg text-slate-600 cursor-not-allowed">
            <ChevronLeft size={16} />
          </button>
          <button className="p-1 hover:bg-white/5 hover:text-white rounded-lg text-slate-600 cursor-not-allowed">
            <ChevronRight size={16} />
          </button>
          <div className="w-[1px] h-4 bg-white/10 mx-2" />
          <div className="text-[10px] text-emerald-400 font-bold uppercase tracking-widest pl-1 select-none flex items-center gap-1.5">
            <span className="w-2 h-2 bg-emerald-500 rounded-full animate-ping" />
            Sync Active
          </div>
        </div>
      </div>

      {/* ─── MODAL 1: TEAM USER MANAGEMENT ─── */}
      {showUserModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm animate-fadeIn font-sans">
          <div className="bg-[#0e0e15] border border-white/10 rounded-2xl w-full max-w-2xl shadow-2xl p-6 overflow-hidden">
            
            <div className="flex items-center justify-between border-b border-white/5 pb-4 mb-4">
              <h2 className="text-lg font-black text-white flex items-center gap-2">
                <Users className="text-violet-400" size={20} />
                Team Members & Bottom Tabs configuration
              </h2>
              <button 
                onClick={() => { setShowUserModal(false); setEditingUser(null); }}
                className="text-slate-400 hover:text-white text-lg font-bold p-1 cursor-pointer"
              >
                ✕
              </button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6 h-[400px]">
              
              {/* User List */}
              <div className="flex flex-col border border-white/5 rounded-xl overflow-hidden bg-white/[0.01]">
                <div className="bg-white/5 px-3 py-2 border-b border-white/5 text-xs font-bold text-slate-400 flex justify-between items-center uppercase tracking-wider">
                  <span>Registered Users</span>
                  <button 
                    onClick={() => {
                      setEditingUser(null);
                      setUserForm({ name: "", display_name: "", email: "", role: "member", password: "" });
                    }}
                    className="text-[10px] bg-violet-600 text-white font-bold px-2 py-0.5 rounded shadow hover:bg-violet-700 cursor-pointer"
                  >
                    <UserPlus size={11} /> Add
                  </button>
                </div>
                <div className="flex-1 overflow-y-auto p-1.5 space-y-1 text-xs">
                  {users.map(u => (
                    <div 
                      key={u.id}
                      onClick={() => {
                        setEditingUser(u);
                        setUserForm({
                          name: u.name,
                          display_name: u.display_name || "",
                          email: u.email,
                          role: u.role || "member",
                          password: "",
                        });
                      }}
                      className={`p-2.5 rounded-lg border transition-all cursor-pointer flex items-center justify-between ${
                        editingUser?.id === u.id 
                          ? "bg-violet-600/20 border-violet-500/50 text-white shadow-md shadow-violet-600/5"
                          : "bg-white/[0.02] border-white/5 hover:border-white/10 text-slate-300"
                      }`}
                    >
                      <div className="flex flex-col gap-0.5">
                        <span className="font-bold flex items-center gap-1.5">
                          {u.display_name || u.name}
                          <span className={`px-1.5 py-0.25 text-[9px] rounded-full uppercase tracking-wider font-extrabold ${
                            u.role === "admin" ? "bg-amber-500/20 text-amber-300" : "bg-blue-500/20 text-blue-300"
                          }`}>
                            {u.role || "member"}
                          </span>
                        </span>
                        <span className="text-[11px] text-slate-500 font-mono truncate max-w-[150px]">{u.email}</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation();
                            handleDeleteUser(u.id, u.display_name || u.name);
                          }}
                          className="p-1.5 hover:bg-rose-500/20 text-slate-500 hover:text-rose-400 rounded-lg transition-all cursor-pointer"
                          title="Remove user"
                        >
                          <Trash2 size={13} />
                        </button>
                        <ChevronRight size={14} className="text-slate-500 flex-shrink-0" />
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Form: Add / Edit User */}
              <div className="flex flex-col justify-between p-1">
                <form onSubmit={editingUser ? handleUpdateUser : handleCreateUser} className="space-y-3.5 text-xs text-slate-300">
                  <div className="text-xs font-bold text-violet-400 uppercase tracking-wider mb-2">
                    {editingUser ? "📝 Edit User Details" : "✨ Create New Team User"}
                  </div>

                  <div>
                    <label className="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">Full Name</label>
                    <input
                      required
                      value={userForm.name}
                      onChange={e => setUserForm({ ...userForm, name: e.target.value })}
                      placeholder="e.g. John Doe"
                      className="w-full px-3 py-2 bg-white/5 border border-white/10 rounded-lg text-white placeholder-slate-600 focus:outline-none focus:border-violet-500 font-medium"
                    />
                  </div>

                  <div>
                    <label className="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">Display Name (Tab Name)</label>
                    <input
                      value={userForm.display_name}
                      onChange={e => setUserForm({ ...userForm, display_name: e.target.value })}
                      placeholder="e.g. John"
                      className="w-full px-3 py-2 bg-white/5 border border-white/10 rounded-lg text-white placeholder-slate-600 focus:outline-none focus:border-violet-500 font-medium"
                    />
                    <p className="text-[10px] text-slate-500 mt-1">This will display as their bottom sheet selector tab.</p>
                  </div>

                  <div>
                    <label className="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">Email Address</label>
                    <input
                      required
                      type="email"
                      value={userForm.email}
                      onChange={e => setUserForm({ ...userForm, email: e.target.value })}
                      placeholder="e.g. john@domain.com"
                      className="w-full px-3 py-2 bg-white/5 border border-white/10 rounded-lg text-white placeholder-slate-600 focus:outline-none focus:border-violet-500 font-medium"
                    />
                  </div>

                  {!editingUser && (
                    <div>
                      <label className="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">Password</label>
                      <input
                        required
                        type="password"
                        value={userForm.password}
                        onChange={e => setUserForm({ ...userForm, password: e.target.value })}
                        placeholder="••••••••"
                        className="w-full px-3 py-2 bg-white/5 border border-white/10 rounded-lg text-white placeholder-slate-600 focus:outline-none focus:border-violet-500 font-medium"
                      />
                    </div>
                  )}

                  <div>
                    <label className="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">Role</label>
                    <select
                      value={userForm.role}
                      onChange={e => setUserForm({ ...userForm, role: e.target.value })}
                      className="w-full px-3 py-2 bg-[#161622] border border-white/10 rounded-lg text-white focus:outline-none focus:border-violet-500 font-semibold cursor-pointer"
                    >
                      <option value="member">Member</option>
                      <option value="admin">Admin</option>
                    </select>
                  </div>

                  <div className="flex gap-2.5 pt-4">
                    {editingUser && (
                      <button
                        type="button"
                        onClick={() => {
                          setEditingUser(null);
                          setUserForm({ name: "", display_name: "", email: "", role: "member", password: "" });
                        }}
                        className="flex-1 py-2.5 bg-white/5 hover:bg-white/10 text-slate-300 rounded-lg font-bold border border-white/5 transition-all cursor-pointer"
                      >
                        Cancel
                      </button>
                    )}
                    <button
                      type="submit"
                      className="flex-1 py-2.5 bg-gradient-to-r from-violet-600 to-indigo-600 hover:shadow-lg hover:shadow-violet-600/25 text-white rounded-lg font-bold transition-all cursor-pointer"
                    >
                      {editingUser ? "Save Updates" : "Create User"}
                    </button>
                  </div>
                </form>
              </div>

            </div>

          </div>
        </div>
      )}

      {/* ─── MODAL 2: ADD NEW LEAD ROW ─── */}
      {showAddLeadModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm animate-fadeIn font-sans">
          <div className="bg-[#0e0e15] border border-white/10 rounded-2xl w-full max-w-md shadow-2xl p-6 overflow-hidden">
            
            <div className="flex items-center justify-between border-b border-white/5 pb-4 mb-4">
              <h2 className="text-lg font-bold text-white flex items-center gap-2">
                ➕ Add New Lead Row
              </h2>
              <button 
                onClick={() => setShowAddLeadModal(false)}
                className="text-slate-400 hover:text-white text-lg font-bold p-1 cursor-pointer"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleAddLeadSubmit} className="space-y-3.5 text-xs text-slate-300">
              <div>
                <label className="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">Investor Name *</label>
                <input
                  required
                  value={leadForm.name}
                  onChange={e => setLeadForm({ ...leadForm, name: e.target.value })}
                  placeholder="e.g. Jorik Fritsch"
                  className="w-full px-3 py-2 bg-white/5 border border-white/10 rounded-lg text-white placeholder-slate-600 focus:outline-none focus:border-violet-500 font-medium"
                />
              </div>

              <div>
                <label className="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">Email Address *</label>
                <input
                  required
                  type="email"
                  value={leadForm.email}
                  onChange={e => setLeadForm({ ...leadForm, email: e.target.value })}
                  placeholder="e.g. jorik@soziusinvest.de"
                  className="w-full px-3 py-2 bg-white/5 border border-white/10 rounded-lg text-white placeholder-slate-600 focus:outline-none focus:border-violet-500 font-medium"
                />
              </div>

              <div>
                <label className="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">Focus</label>
                <input
                  value={leadForm.focus}
                  onChange={e => setLeadForm({ ...leadForm, focus: e.target.value })}
                  placeholder="e.g. Web3, SaaS"
                  className="w-full px-3 py-2 bg-white/5 border border-white/10 rounded-lg text-white placeholder-slate-600 focus:outline-none focus:border-violet-500 font-medium"
                />
              </div>

              <div>
                <label className="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">LinkedIn URL</label>
                <input
                  value={leadForm.linkedin}
                  onChange={e => setLeadForm({ ...leadForm, linkedin: e.target.value })}
                  placeholder="e.g. linkedin.com/in/jorik-fritsch"
                  className="w-full px-3 py-2 bg-white/5 border border-white/10 rounded-lg text-white placeholder-slate-600 focus:outline-none focus:border-violet-500 font-medium"
                />
              </div>

              <div>
                <label className="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">Company / VC Firm</label>
                <input
                  value={leadForm.company}
                  onChange={e => setLeadForm({ ...leadForm, company: e.target.value })}
                  placeholder="e.g. Sozius Invest"
                  className="w-full px-3 py-2 bg-white/5 border border-white/10 rounded-lg text-white placeholder-slate-600 focus:outline-none focus:border-violet-500 font-medium"
                />
              </div>

              {campaigns.length > 0 && (
                <div>
                  <label className="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">Select Campaign *</label>
                  <select
                    value={leadForm.campaign_id}
                    onChange={e => setLeadForm({ ...leadForm, campaign_id: e.target.value })}
                    className="w-full px-3 py-2 bg-[#161622] border border-white/10 rounded-lg text-white focus:outline-none focus:border-violet-500 font-semibold cursor-pointer"
                  >
                    {campaigns.map(c => (
                      <option key={c.id} value={c.id}>{c.name}</option>
                    ))}
                  </select>
                </div>
              )}

              <div className="flex gap-2.5 pt-4">
                <button
                  type="button"
                  onClick={() => setShowAddLeadModal(false)}
                  className="flex-1 py-2.5 bg-white/5 hover:bg-white/10 text-slate-300 rounded-lg font-bold border border-white/5 transition-all cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="flex-1 py-2.5 bg-gradient-to-r from-violet-600 to-indigo-600 hover:shadow-lg hover:shadow-violet-600/25 text-white rounded-lg font-bold transition-all cursor-pointer"
                >
                  Create Row
                </button>
              </div>
            </form>

          </div>
        </div>
      )}

    </div>
  );
}
