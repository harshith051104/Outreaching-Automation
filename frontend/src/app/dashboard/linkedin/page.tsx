"use client";

import { useEffect, useState, useCallback } from "react";
import { getCampaigns } from "@/services/campaign-api";
import { generateLinkedInCalendar, getLinkedInCalendars, LinkedInCalendar } from "@/services/linkedin-api";
import {
  getLinkedInSessionStatus,
  connectLinkedInSession,
  importLinkedInCookies,
  disconnectLinkedInSession,
  validateLinkedInSession,
  getPendingActions,
  approveAction,
  rejectAction,
  editAction,
  rescheduleAction,
  createConnectionRequest,
  getLinkedInCampaigns,
  createLinkedInCampaign,
  startLinkedInCampaign,
  pauseLinkedInCampaign,
  getLinkedInConversations,
  getLinkedInAnalytics,
  getLinkedInRelationships,
  getLinkedInHistory,
  getLinkedInQueueStatus,
  getLLMStatus,
  toggleLLMStatus,
  getAutoReplyStatus,
  toggleAutoReplyStatus,
  type LinkedInSessionStatus,
  type LinkedInAction,
  type LinkedInCampaign as OutreachCampaign,
  type LinkedInConversation,
  type LinkedInAnalytics,
  type LinkedInRelationship,
  type LinkedInQueueStatus,
} from "@/services/linkedin-outreach-api";
import {
  importLeadsFromCSV,
  parseCSVPreview,
  getLinkedInLeads,
  type LinkedInLead,
  type CSVImportResult,
} from "@/services/linkedin-api";
import {
  Linkedin,
  Calendar as CalendarIcon,
  FileText,
  Users,
  MessageSquare,
  Sparkles,
  Loader2,
  AlertCircle,
  Send,
  Check,
  X,
  Wifi,
  WifiOff,
  Search,
  TrendingUp,
  Clock,
  CheckCircle2,
  XCircle,
  Edit3,
  Play,
  Pause,
  Plus,
  BarChart3,
  ArrowRight,
  RefreshCw,
  Shield,
  UserPlus,
  Mail,
  Target,
  Activity,
  Zap,
  Eye,
  Settings,
  AlertTriangle,
  Upload,
  FileSpreadsheet,
} from "lucide-react";

/* ═══════════════════════════════════════════════════════════════════════════
   MAIN COMPONENT
   ═══════════════════════════════════════════════════════════════════════════ */

export default function LinkedInHubPage() {
  /* ── top-level tab state ───────────────────────────────── */
  const [mainTab, setMainTab] = useState<"session" | "queue" | "campaigns">("session");
  const [campaignSubTab, setCampaignSubTab] = useState<"outreach" | "content">("outreach");

  /* ── data state ────────────────────────────────────────── */
  const [sessionStatus, setSessionStatus] = useState<LinkedInSessionStatus | null>(null);
  const [pendingActions, setPendingActions] = useState<LinkedInAction[]>([]);
  const [outreachCampaigns, setOutreachCampaigns] = useState<OutreachCampaign[]>([]);
  const [conversations, setConversations] = useState<LinkedInConversation[]>([]);
  const [analytics, setAnalytics] = useState<LinkedInAnalytics | null>(null);
  const [relationships, setRelationships] = useState<LinkedInRelationship[]>([]);
  const [history, setHistory] = useState<LinkedInAction[]>([]);
  const [queueStatus, setQueueStatus] = useState<LinkedInQueueStatus | null>(null);
  const [llmDisabled, setLlmDisabled] = useState<boolean>(false);
  const [autoReplyEnabled, setAutoReplyEnabled] = useState<boolean>(true);

  /* ── content calendar state (existing) ─────────────────── */
  const [campaigns, setCampaigns] = useState<any[]>([]);
  const [calendars, setCalendars] = useState<LinkedInCalendar[]>([]);
  const [selectedCalendar, setSelectedCalendar] = useState<LinkedInCalendar | null>(null);
  const [campaignGoal, setCampaignGoal] = useState("");
  const [targetAudience, setTargetAudience] = useState("");
  const [industry, setIndustry] = useState("");
  const [selectedCampaignId, setSelectedCampaignId] = useState("");
  const [formError, setFormError] = useState("");
  const [generating, setGenerating] = useState(false);

  /* ── outreach form state ───────────────────────────────── */
  const [connectionUrl, setConnectionUrl] = useState("");
  const [sendingConnection, setSendingConnection] = useState(false);
  const [editingActionId, setEditingActionId] = useState<string | null>(null);
  const [editMessage, setEditMessage] = useState("");

  /* ── campaign creation state ───────────────────────────── */
  const [showCampaignForm, setShowCampaignForm] = useState(false);
  const [newCampaignName, setNewCampaignName] = useState("");
  const [newCampaignGoal, setNewCampaignGoal] = useState("");
  const [newCampaignAudience, setNewCampaignAudience] = useState("");

  /* ── CSV import state ──────────────────────────────────── */
  const [importingCSV, setImportingCSV] = useState(false);
  const [csvImportResult, setCsvImportResult] = useState<CSVImportResult | null>(null);
  const [previewLeads, setPreviewLeads] = useState<any[]>([]);
  const [showImportModal, setShowImportModal] = useState(false);
  const [selectedCampaignIdForImport, setSelectedCampaignIdForImport] = useState("");
  const [selectedCSVFile, setSelectedCSVFile] = useState<File | null>(null);

  /* ── loading & modal states ────────────────────────────── */
  const [loading, setLoading] = useState(true);
  const [connectingSession, setConnectingSession] = useState(false);
  const [validatingSession, setValidatingSession] = useState(false);
  const [cookiesJson, setCookiesJson] = useState("");
  const [importingCookies, setImportingCookies] = useState(false);
  const [showCookieForm, setShowCookieForm] = useState(false);
  const [approvingId, setApprovingId] = useState<string | null>(null);
  const [screenshotUrl, setScreenshotUrl] = useState<string | null>(null);
  const [reschedulingActionId, setReschedulingActionId] = useState<string | null>(null);
  const [rescheduleTime, setRescheduleTime] = useState<string>("");
  const [togglingAutoReply, setTogglingAutoReply] = useState<boolean>(false);

  /* ════════════════════════════════════════════════════════
     DATA LOADING
     ════════════════════════════════════════════════════════ */

  const loadAllData = useCallback(async () => {
    setLoading(true);
    try {
      const [
        session,
        pending,
        oCampaigns,
        convos,
        anal,
        rels,
        hist,
        queue,
        camps,
        cals,
        llmStatus,
        autoReply,
      ] = await Promise.all([
        getLinkedInSessionStatus().catch(() => ({ status: "disconnected" as const })),
        getPendingActions().catch(() => ({ actions: [], count: 0 })),
        getLinkedInCampaigns().catch(() => []),
        getLinkedInConversations().catch(() => []),
        getLinkedInAnalytics().catch(() => null),
        getLinkedInRelationships().catch(() => []),
        getLinkedInHistory(1, 20).catch(() => ({ actions: [], total: 0, page: 1, total_pages: 0 })),
        getLinkedInQueueStatus().catch(() => null),
        getCampaigns().catch(() => []),
        getLinkedInCalendars().catch(() => []),
        getLLMStatus("linkedin").catch(() => ({ disabled: false })),
        getAutoReplyStatus().catch(() => ({ enabled: true })),
      ]);

      setSessionStatus(session);
      setPendingActions(pending.actions || []);
      setOutreachCampaigns(oCampaigns);
      setConversations(convos);
      setAnalytics(anal);
      setRelationships(rels);
      setHistory(hist.actions || []);
      setQueueStatus(queue);
      setCampaigns(camps);
      setCalendars(cals);
      setLlmDisabled(llmStatus.disabled);
      setAutoReplyEnabled(autoReply.enabled);

      if (camps.length > 0) setSelectedCampaignId(camps[0].id);
      if (cals.length > 0) setSelectedCalendar(cals[0]);
    } catch (err) {
      console.error("Failed to load LinkedIn data:", err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadAllData();
  }, [loadAllData]);

  /* ════════════════════════════════════════════════════════
     HANDLERS
     ════════════════════════════════════════════════════════ */

  const handleConnectSession = async () => {
    setConnectingSession(true);
    try {
      const result = await connectLinkedInSession();
      setSessionStatus(result);
      if (result.status === "error") {
        alert(`Failed to connect LinkedIn: ${result.message || "Unknown error"}`);
      } else if (result.status === "login_timeout") {
        alert("Login timed out. Please make sure to complete the login in the browser window.");
      } else {
        await loadAllData();
      }
    } catch (err: any) {
      console.error("Session connect failed:", err);
      alert(`Session connection failed: ${err.message || "Unknown error"}`);
    } finally {
      setConnectingSession(false);
    }
  };

  const handleImportCookies = async () => {
    if (!cookiesJson.trim()) {
      alert("Please paste some cookie JSON.");
      return;
    }
    
    let parsedCookies: any[] = [];
    try {
      parsedCookies = JSON.parse(cookiesJson.trim());
      if (!Array.isArray(parsedCookies)) {
        throw new Error("Cookies must be a JSON array.");
      }
    } catch (e: any) {
      alert(`Invalid JSON format: ${e.message || "Make sure you copied a valid JSON array of cookies."}`);
      return;
    }
    
    setImportingCookies(true);
    try {
      const result = await importLinkedInCookies(parsedCookies);
      setSessionStatus(result);
      if (result.status === "connected") {
        alert("LinkedIn session connected and imported successfully!");
        setCookiesJson("");
        setShowCookieForm(false);
        await loadAllData();
      } else {
        alert(`Failed to import cookies: ${result.message || "Validation failed."}`);
      }
    } catch (err: any) {
      console.error("Cookie import failed:", err);
      alert(`Cookie import failed: ${err.response?.data?.detail || err.message || "Unknown error"}`);
    } finally {
      setImportingCookies(false);
    }
  };

  const handleDisconnectSession = async () => {
    try {
      const result = await disconnectLinkedInSession();
      setSessionStatus(result);
      await loadAllData();
    } catch (err) {
      console.error("Session disconnect failed:", err);
    }
  };

  const handleValidateSession = async () => {
    setValidatingSession(true);
    try {
      const result = await validateLinkedInSession();
      setSessionStatus(result);
      await loadAllData();
      alert("LinkedIn session validation finished.");
    } catch (err) {
      console.error("Session validation failed:", err);
      alert("Failed to validate LinkedIn session.");
    } finally {
      setValidatingSession(false);
    }
  };

  const handleToggleLLM = async () => {
    const nextState = !llmDisabled;
    try {
      await toggleLLMStatus(nextState, "linkedin");
      setLlmDisabled(nextState);
    } catch (err) {
      console.error("Failed to toggle LLM status:", err);
    }
  };

  const handleToggleAutoReply = async () => {
    setTogglingAutoReply(true);
    const nextState = !autoReplyEnabled;
    try {
      await toggleAutoReplyStatus(nextState);
      setAutoReplyEnabled(nextState);
    } catch (err) {
      console.error("Failed to toggle auto-reply:", err);
    } finally {
      setTogglingAutoReply(false);
    }
  };

  const handleSendConnection = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!connectionUrl.trim()) return;
    setSendingConnection(true);
    try {
      const result = await createConnectionRequest(connectionUrl.trim());
      setPendingActions((prev) => [
        {
          id: result.action_id,
          linkedin_url: connectionUrl,
          action_type: "connection_request",
          status: "pending_approval",
          message: result.draft_message,
          user_id: "",
          created_at: new Date().toISOString(),
        },
        ...prev,
      ]);
      setConnectionUrl("");
      setMainTab("queue");
    } catch (err) {
      console.error("Connection request failed:", err);
    } finally {
      setSendingConnection(false);
    }
  };

  const handleApprove = async (actionId: string) => {
    setApprovingId(actionId);
    try {
      const res = await approveAction(actionId);
      if (res.action_status === "failed") {
        const errMsg = typeof res.result?.error === "string" ? res.result.error : "Unknown error";
        alert(`Execution failed: ${errMsg}`);
        await loadAllData();
      } else {
        setPendingActions((prev) => prev.filter((a) => a.id !== actionId));
        await loadAllData();
      }
    } catch (err: any) {
      console.error("Approval failed:", err);
      const detail = err.response?.data?.detail || err.message || "Unknown error";
      alert(`Approval request failed: ${detail}`);
      await loadAllData();
    } finally {
      setApprovingId(null);
    }
  };

  const handleReject = async (actionId: string) => {
    try {
      await rejectAction(actionId);
      setPendingActions((prev) => prev.filter((a) => a.id !== actionId));
      await loadAllData();
    } catch (err) {
      console.error("Reject failed:", err);
    }
  };

  const handleEditSave = async (actionId: string) => {
    try {
      await editAction(actionId, editMessage);
      setPendingActions((prev) =>
        prev.map((a) => (a.id === actionId ? { ...a, message: editMessage } : a))
      );
      setEditingActionId(null);
      setEditMessage("");
    } catch (err) {
      console.error("Edit failed:", err);
    }
  };

  const handleReschedule = async (actionId: string) => {
    if (!rescheduleTime) return;
    try {
      await rescheduleAction(actionId, new Date(rescheduleTime).toISOString());
      setReschedulingActionId(null);
      setRescheduleTime("");
      await loadAllData();
    } catch (err) {
      console.error("Reschedule failed:", err);
      alert("Failed to reschedule outreach action.");
    }
  };

  const handleCreateCampaign = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newCampaignName.trim()) return;
    try {
      const campaign = await createLinkedInCampaign({
        name: newCampaignName,
        goal: newCampaignGoal,
        target_audience: newCampaignAudience,
      });
      setOutreachCampaigns((prev) => [campaign, ...prev]);
      setShowCampaignForm(false);
      setNewCampaignName("");
      setNewCampaignGoal("");
      setNewCampaignAudience("");
    } catch (err) {
      console.error("Campaign creation failed:", err);
    }
  };

  const handleStartCampaign = async (campaignId: string) => {
    try {
      await startLinkedInCampaign(campaignId);
      setOutreachCampaigns((prev) =>
        prev.map((c) => (c.id === campaignId ? { ...c, status: "active" } : c))
      );
      await loadAllData();
    } catch (err) {
      console.error("Campaign start failed:", err);
    }
  };

  const handlePauseCampaign = async (campaignId: string) => {
    try {
      await pauseLinkedInCampaign(campaignId);
      setOutreachCampaigns((prev) =>
        prev.map((c) => (c.id === campaignId ? { ...c, status: "paused" } : c))
      );
      await loadAllData();
    } catch (err) {
      console.error("Campaign pause failed:", err);
    }
  };

  const handleCSVFileChange = async (e: React.ChangeEvent<HTMLInputElement>, campaignId: string) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (!file.name.endsWith(".csv") && !file.name.endsWith(".txt")) {
      alert("Please select a CSV file");
      return;
    }

    setSelectedCSVFile(file);
    setSelectedCampaignIdForImport(campaignId);
    setImportingCSV(true);
    try {
      const result = await parseCSVPreview(file);
      setPreviewLeads(result.leads || []);
      setShowImportModal(true);
    } catch (err) {
      console.error("CSV preview failed:", err);
      alert("Failed to parse CSV file");
    } finally {
      setImportingCSV(false);
    }
    e.target.value = "";
  };

  const handleImportCSV = async () => {
    if (!selectedCSVFile) return;
    setImportingCSV(true);
    try {
      const result = await importLeadsFromCSV(
        selectedCSVFile,
        selectedCampaignIdForImport || undefined
      );
      setCsvImportResult(result);
      setShowImportModal(false);
      setSelectedCSVFile(null);
      await loadAllData();
      alert(`Import completed! Created: ${result.leads_created}, Updated: ${result.leads_updated}`);
    } catch (err) {
      console.error("CSV import failed:", err);
      alert("Failed to import leads from CSV");
    } finally {
      setImportingCSV(false);
    }
  };

  const handleGenerate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!campaignGoal || !targetAudience || !industry) {
      setFormError("All fields are required to build a Content Strategy.");
      return;
    }
    setFormError("");
    setGenerating(true);
    try {
      const newCal = await generateLinkedInCalendar({
        campaign_id: selectedCampaignId,
        campaign_goal: campaignGoal,
        target_audience: targetAudience,
        industry: industry,
      });
      setCalendars((prev) => [newCal, ...prev]);
      setSelectedCalendar(newCal);
    } catch (err) {
      setFormError("Failed to run LinkedIn Content Strategy Crew.");
    } finally {
      setGenerating(false);
    }
  };

  /* ════════════════════════════════════════════════════════
     HELPERS & COLOR MAPS
     ════════════════════════════════════════════════════════ */

  const isConnected = sessionStatus?.status === "connected";

  const stageColors: Record<string, { bg: string; text: string; border: string }> = {
    profile_viewed: { bg: "rgba(100,116,139,0.1)", text: "var(--sidebar-text-muted)", border: "rgba(100,116,139,0.2)" },
    connection_sent: { bg: "rgba(245,158,11,0.1)", text: "#f59e0b", border: "rgba(245,158,11,0.25)" },
    connection_accepted: { bg: "rgba(16,185,129,0.1)", text: "#10b981", border: "rgba(16,185,129,0.25)" },
    message_sent: { bg: "rgba(59,130,246,0.1)", text: "#3b82f6", border: "rgba(59,130,246,0.25)" },
    replied: { bg: "rgba(124,92,255,0.1)", text: "#7c5cff", border: "rgba(124,92,255,0.25)" },
    followup_sent: { bg: "rgba(99,102,241,0.1)", text: "#6366f1", border: "rgba(99,102,241,0.25)" },
    meeting_booked: { bg: "rgba(16,185,129,0.1)", text: "#10b981", border: "rgba(16,185,129,0.25)" },
    opportunity_created: { bg: "rgba(6,182,212,0.1)", text: "#06b6d4", border: "rgba(6,182,212,0.25)" },
    closed_won: { bg: "rgba(16,185,129,0.15)", text: "#10b981", border: "rgba(16,185,129,0.3)" },
    closed_lost: { bg: "rgba(239,68,68,0.1)", text: "#ef4444", border: "rgba(239,68,68,0.25)" },
  };

  const statusColors: Record<string, { bg: string; text: string; border: string }> = {
    pending_approval: { bg: "rgba(245,158,11,0.1)", text: "#f59e0b", border: "rgba(245,158,11,0.25)" },
    scheduled: { bg: "rgba(59,130,246,0.1)", text: "#3b82f6", border: "rgba(59,130,246,0.25)" },
    executed: { bg: "rgba(16,185,129,0.1)", text: "#10b981", border: "rgba(16,185,129,0.25)" },
    failed: { bg: "rgba(239,68,68,0.1)", text: "#ef4444", border: "rgba(239,68,68,0.25)" },
    rejected: { bg: "rgba(100,116,139,0.1)", text: "var(--sidebar-text-muted)", border: "rgba(100,116,139,0.2)" },
  };

  const cardStyle: React.CSSProperties = {
    background: "var(--card-bg)",
    border: "1px solid var(--card-border)",
    borderRadius: "16px",
    boxShadow: "var(--card-shadow)",
    backdropFilter: "blur(12px)",
    WebkitBackdropFilter: "blur(12px)",
  };

  const bannerStyle: React.CSSProperties = {
    background: "linear-gradient(135deg, var(--banner-bg-from) 0%, var(--banner-bg-to) 100%)",
    border: "1px solid var(--banner-border)",
    borderRadius: "16px",
    boxShadow: "var(--card-shadow)",
  };

  const inputStyle: React.CSSProperties = {
    width: "100%",
    padding: "9px 12px",
    fontSize: "13px",
    background: "var(--sidebar-toggle-bg)",
    border: "1px solid var(--card-border)",
    borderRadius: "8px",
    color: "var(--foreground-color)",
    outline: "none",
  };

  const selectStyle: React.CSSProperties = {
    width: "100%",
    padding: "9px 12px",
    fontSize: "13px",
    background: "var(--sidebar-toggle-bg)",
    border: "1px solid var(--card-border)",
    borderRadius: "8px",
    color: "var(--foreground-color)",
    outline: "none",
  };

  const mainTabs = [
    { id: "session" as const, label: "Session Status", icon: Shield },
    { id: "queue" as const, label: "Approvals Queue", icon: Clock },
    { id: "campaigns" as const, label: "Campaigns & Strategy", icon: Target },
  ];

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] space-y-4">
        <Loader2 className="h-8 w-8 animate-spin text-[var(--primary)]" />
        <p className="text-xs text-[var(--sidebar-text-muted)] font-medium">Syncing LinkedIn Dashboard with Playwright runtime...</p>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      {/* ── HERO HEADER ──────────────────────────────────────── */}
      <div style={bannerStyle} className="p-6 relative overflow-hidden">
        <div style={{ background: "radial-gradient(circle, var(--primary) 0%, transparent 70%)" }} className="absolute -right-24 -top-24 h-64 w-64 opacity-10 rounded-full blur-3xl" />
        <div style={{ background: "radial-gradient(circle, var(--secondary) 0%, transparent 70%)" }} className="absolute -left-24 -bottom-24 h-64 w-64 opacity-10 rounded-full blur-3xl" />
        
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-6 relative z-10">
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <span className="bg-[rgba(124,92,255,0.1)] text-[var(--primary)] text-[10px] px-3 py-1 rounded-full font-black uppercase tracking-wider border border-[rgba(124,92,255,0.2)]">
                LinkedIn Outreach
              </span>
              <span style={{ background: "var(--banner-btn-bg)", color: "var(--banner-desc)", borderColor: "var(--banner-border)" }} className="text-[10px] px-2.5 py-1 rounded-full font-bold border">
                Playwright Engine v2.0
              </span>
            </div>
            <h1 style={{ color: "var(--banner-text)" }} className="text-3xl font-black tracking-tight">
              LinkedIn Control Panel
            </h1>
            <p style={{ color: "var(--banner-desc)" }} className="text-xs max-w-xl">
              Monitor active browser sessions, edit generated message queues, schedule personalized connection campaigns, and strategize content.
            </p>
          </div>
 
          <div className="flex flex-wrap items-center gap-3">
            {/* LLM Toggle */}
            <button
              onClick={handleToggleLLM}
              className={`flex items-center gap-1.5 px-4 py-2 rounded-full text-xs font-bold transition-all border ${
                llmDisabled
                  ? "bg-amber-500/10 text-amber-500 border-amber-500/20 hover:bg-amber-500/20"
                  : "bg-emerald-500/10 text-emerald-500 border-emerald-500/20 hover:bg-emerald-500/20"
              }`}
            >
              <Sparkles className={`h-3.5 w-3.5 ${llmDisabled ? "text-amber-500" : "text-emerald-500 animate-pulse"}`} />
              {llmDisabled ? "LLM: Mock Mode" : "LLM: Active"}
            </button>
 
            {/* Connection Status Pill */}
            {isConnected ? (
              <div style={{ background: "var(--card-bg)", border: "1px solid var(--card-border)" }} className="flex items-center gap-3 px-4 py-1.5 rounded-full">
                {sessionStatus?.avatar_url ? (
                  <img
                     src={sessionStatus.avatar_url}
                     alt={sessionStatus.account_name}
                     className="h-6 w-6 rounded-full object-cover border border-[var(--card-border)]"
                  />
                ) : (
                  <div className="h-6 w-6 rounded-full bg-[var(--primary)] flex items-center justify-center text-white font-bold text-[10px]">
                    {sessionStatus?.account_name?.[0] || "L"}
                  </div>
                )}
                <div className="text-left">
                  <p className="text-[11px] font-bold text-[var(--foreground-color)] max-w-[120px] truncate leading-none">
                    {sessionStatus?.account_name}
                  </p>
                  <span className="text-[9px] text-green-500 font-bold flex items-center gap-1 mt-0.5">
                    <span className="h-1.5 w-1.5 rounded-full bg-green-500 animate-pulse" />
                    Connected
                  </span>
                </div>
                <button
                  onClick={handleValidateSession}
                  disabled={validatingSession}
                  className="text-[10px] text-[var(--sidebar-text-muted)] hover:text-[var(--primary)] transition-colors ml-2 hover:underline disabled:opacity-50"
                >
                  {validatingSession ? "Verifying..." : "Verify"}
                </button>
                <span className="text-[var(--card-border)] text-[10px]">|</span>
                <button
                  onClick={handleDisconnectSession}
                  className="text-[10px] text-[var(--sidebar-text-muted)] hover:text-red-500 transition-colors hover:underline"
                >
                  Disconnect
                </button>
              </div>
            ) : (
              <button
                onClick={handleConnectSession}
                disabled={connectingSession}
                style={{ boxShadow: "0 4px 16px rgba(124,92,255,0.3)" }}
                className="flex items-center gap-2 bg-[var(--primary)] hover:brightness-110 text-white px-5 py-2 rounded-full text-xs font-black transition-all disabled:opacity-50 cursor-pointer"
              >
                {connectingSession ? (
                  <Loader2 className="h-4.5 w-4.5 animate-spin" />
                ) : (
                  <Linkedin className="h-4.5 w-4.5" />
                )}
                {connectingSession ? "Initializing browser..." : "Connect LinkedIn"}
              </button>
            )}
          </div>
        </div>
      </div>

      {/* ── TABS NAVIGATION ───────────────────────────────────── */}
      <div style={{ borderBottom: "1px solid var(--card-border)" }} className="flex gap-2 pb-0.5 overflow-x-auto">
        {mainTabs.map((tab) => {
          const Icon = tab.icon;
          return (
            <button
              key={tab.id}
              onClick={() => setMainTab(tab.id)}
              className={`flex items-center gap-2 px-5 py-3 text-xs font-bold border-b-2 transition-all whitespace-nowrap cursor-pointer ${
                mainTab === tab.id
                  ? "border-[var(--primary)] text-[var(--primary)]"
                  : "border-transparent text-[var(--sidebar-text-muted)] hover:text-[var(--foreground-color)] hover:border-[var(--card-border)]"
              }`}
            >
              <Icon className="h-4 w-4" />
              {tab.label}
              {tab.id === "queue" && pendingActions.length > 0 && (
                <span className="bg-amber-500 text-white text-[10px] font-black px-2 py-0.5 rounded-full ml-1 animate-pulse">
                  {pendingActions.length}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* ══════════════════════════════════════════════════════
         PANEL 1: SESSION STATUS
         ══════════════════════════════════════════════════════ */}
      {mainTab === "session" && (
        <div className="grid lg:grid-cols-3 gap-6">
          
          {/* Column 1: Connection Health & Automation Controls */}
          <div className="lg:col-span-2 space-y-6">
            
            {/* Session Card */}
            <div style={cardStyle} className="p-6 space-y-4">
              <h2 style={{ borderColor: "var(--card-border)" }} className="text-base font-bold text-[var(--foreground-color)] flex items-center gap-2 border-b pb-3">
                <Shield className="h-5 w-5 text-[var(--primary)]" />
                Session Connection & Health
              </h2>
              
              <div className="grid md:grid-cols-2 gap-4">
                <div className="space-y-1">
                  <span className="text-[10px] uppercase tracking-wider text-[var(--sidebar-text-muted)] font-bold">Engine Connection Mode</span>
                  <div className="flex items-center gap-2">
                    {isConnected ? (
                      <>
                        <div className="h-2 w-2 rounded-full bg-green-500 animate-ping" />
                        <span className="text-xs font-bold text-green-500 flex items-center gap-1.5">
                          <Wifi className="h-4 w-4" /> Connected & Syncing
                        </span>
                      </>
                    ) : (
                      <>
                        <div className="h-2 w-2 rounded-full bg-red-500" />
                        <span className="text-xs font-bold text-red-500 flex items-center gap-1.5">
                          <WifiOff className="h-4 w-4" /> Disconnected
                        </span>
                      </>
                    )}
                  </div>
                </div>
                
                <div className="space-y-1">
                  <span className="text-[10px] uppercase tracking-wider text-[var(--sidebar-text-muted)] font-bold">Auto-Validation Check</span>
                  <p className="text-xs text-[var(--foreground-color)] font-medium">
                    {sessionStatus?.last_validated_at 
                      ? new Date(sessionStatus.last_validated_at).toLocaleString() 
                      : "Never Checked"}
                  </p>
                </div>
              </div>
              
              {isConnected ? (
                <div style={{ background: "var(--sidebar-toggle-bg)", borderColor: "var(--card-border)" }} className="border p-4 rounded-xl flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                  <div className="flex items-center gap-3">
                    {sessionStatus?.avatar_url ? (
                      <img
                        src={sessionStatus.avatar_url}
                        alt="Avatar"
                        className="h-10 w-10 rounded-full border border-[var(--card-border)] object-cover"
                      />
                    ) : (
                      <div className="h-10 w-10 bg-[var(--primary)] text-white flex items-center justify-center rounded-full font-black text-sm">
                        {sessionStatus?.account_name?.[0] || "L"}
                      </div>
                    )}
                    <div>
                      <h4 className="text-sm font-bold text-[var(--foreground-color)] leading-snug">{sessionStatus?.account_name}</h4>
                      <p className="text-[11px] text-[var(--sidebar-text-muted)] truncate max-w-[240px]">
                        {sessionStatus?.profile_url || "LinkedIn Session Profile Link Unavailable"}
                      </p>
                    </div>
                  </div>
                  <div className="flex gap-2">
                    <button
                      onClick={handleValidateSession}
                      disabled={validatingSession}
                      className="bg-[var(--sidebar-active-bg)] text-[var(--primary)] hover:brightness-95 px-3 py-1.5 rounded-lg text-xs font-bold transition-all disabled:opacity-50 cursor-pointer"
                    >
                      {validatingSession ? "Validating Session..." : "Verify Session"}
                    </button>
                    <button
                      onClick={handleDisconnectSession}
                      className="bg-red-500/10 hover:bg-red-500/20 text-red-500 px-3 py-1.5 rounded-lg text-xs font-bold transition-all cursor-pointer"
                    >
                      Disconnect
                    </button>
                  </div>
                </div>
              ) : (
                <div style={{ background: "var(--sidebar-toggle-bg)", borderColor: "var(--card-border)" }} className="border border-dashed p-6 rounded-xl text-center space-y-4">
                  <AlertCircle className="h-8 w-8 text-amber-500 mx-auto animate-pulse" />
                  <div className="space-y-1">
                    <h4 className="text-sm font-bold text-[var(--foreground-color)]">No LinkedIn Session Linked</h4>
                    <p className="text-[11px] text-[var(--sidebar-text-muted)] max-w-sm mx-auto">
                      Connect your LinkedIn profile to configure automation tasks, parse connection pipelines, and sync history.
                    </p>
                  </div>
                  
                  <div className="flex flex-col sm:flex-row items-center justify-center gap-3 pt-2">
                    <button
                      onClick={handleConnectSession}
                      disabled={connectingSession || importingCookies}
                      className="bg-[var(--primary)] hover:brightness-110 text-white px-4 py-2 rounded-lg text-xs font-bold transition-all disabled:opacity-50 cursor-pointer w-full sm:w-auto"
                    >
                      {connectingSession ? "Spinning Up Browser..." : "Connect via Local Browser"}
                    </button>
                    
                    <button
                      onClick={() => setShowCookieForm(!showCookieForm)}
                      disabled={connectingSession || importingCookies}
                      className="bg-transparent hover:bg-[rgba(124,92,255,0.05)] border border-[var(--primary)] text-[var(--primary)] px-4 py-2 rounded-lg text-xs font-bold transition-all disabled:opacity-50 cursor-pointer w-full sm:w-auto"
                    >
                      {showCookieForm ? "Hide Cookie Panel" : "Connect via Cookie Import (Cloud)"}
                    </button>
                  </div>

                  {showCookieForm && (
                    <div style={{ borderTop: "1px solid var(--card-border)" }} className="pt-4 mt-4 text-left space-y-3">
                      <div className="space-y-1">
                        <h5 className="text-xs font-bold text-[var(--foreground-color)]">Pasted Cookie JSON</h5>
                        <p className="text-[10px] text-[var(--sidebar-text-muted)] leading-relaxed">
                          To connect in the cloud (Railway): Log into LinkedIn in your browser, export your cookies as a JSON array using an extension like <strong>EditThisCookie</strong>, and paste the JSON array below.
                        </p>
                      </div>
                      
                      <textarea
                        rows={5}
                        placeholder='[{"domain": ".linkedin.com", "name": "li_at", "value": "..."}]'
                        value={cookiesJson}
                        onChange={(e) => setCookiesJson(e.target.value)}
                        style={inputStyle}
                        className="font-mono text-[11px] focus:ring-1 focus:ring-[var(--primary)] resize-none"
                      />
                      
                      <button
                        onClick={handleImportCookies}
                        disabled={importingCookies || !cookiesJson.trim()}
                        className="bg-[var(--primary)] hover:brightness-110 text-white px-4 py-2 rounded-lg text-xs font-bold flex items-center justify-center gap-2 transition-all disabled:opacity-50 cursor-pointer w-full"
                      >
                        {importingCookies && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
                        {importingCookies ? "Validating & Connecting..." : "Import & Connect"}
                      </button>
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Quick Connection Request Box */}
            <div style={cardStyle} className="p-6 space-y-4">
              <h2 style={{ borderColor: "var(--card-border)" }} className="text-base font-bold text-[var(--foreground-color)] flex items-center gap-2 border-b pb-3">
                <UserPlus className="h-5 w-5 text-[var(--primary)]" />
                Add Lead to Outreach Queue
              </h2>
              <p className="text-[11px] text-[var(--sidebar-text-muted)]">
                Provide a LinkedIn profile URL to instantly generate personalized connection request drafts and load them into the pending queue.
              </p>
              
              <form onSubmit={handleSendConnection} className="flex gap-2">
                <input
                  type="url"
                  placeholder="https://www.linkedin.com/in/username/"
                  required
                  value={connectionUrl}
                  onChange={(e) => setConnectionUrl(e.target.value)}
                  style={inputStyle}
                  className="flex-1 focus:ring-1 focus:ring-[var(--primary)]"
                />
                <button
                  type="submit"
                  disabled={sendingConnection}
                  className="bg-[var(--primary)] hover:brightness-110 text-white px-4 py-2 rounded-lg text-xs font-bold flex items-center gap-2 transition-all disabled:opacity-50 cursor-pointer whitespace-nowrap"
                >
                  {sendingConnection ? (
                    <Loader2 className="h-4.5 w-4.5 animate-spin" />
                  ) : (
                    <Send className="h-3.5 w-3.5" />
                  )}
                  Queue Outreach
                </button>
              </form>
            </div>

            {/* Auto-Reply & Monitor Settings */}
            <div style={cardStyle} className="p-6 space-y-4">
              <h2 style={{ borderColor: "var(--card-border)" }} className="text-base font-bold text-[var(--foreground-color)] flex items-center gap-2 border-b pb-3">
                <Settings className="h-5 w-5 text-[var(--primary)]" />
                Automation & Intelligence Toggles
              </h2>
              
              <div className="space-y-4 divide-y divide-[var(--card-border)]">
                <div className="flex items-start justify-between gap-4 pt-1">
                  <div className="space-y-1">
                    <h4 className="text-xs font-bold text-[var(--foreground-color)]">AI Message Customization (LLM status)</h4>
                    <p className="text-[11px] text-[var(--sidebar-text-muted)] leading-relaxed">
                      Enable LLM generation to write hyper-personalized connection hooks. If disabled, default fallback templates will be loaded.
                    </p>
                  </div>
                  <button
                    onClick={handleToggleLLM}
                    style={{ background: llmDisabled ? "var(--sidebar-toggle-bg)" : "rgba(124,92,255,0.15)", borderColor: "var(--card-border)" }}
                    className={`border px-3 py-1.5 rounded-lg text-[11px] font-bold transition-all cursor-pointer whitespace-nowrap ${
                      llmDisabled ? "text-[var(--sidebar-text-muted)]" : "text-[var(--primary)]"
                    }`}
                  >
                    {llmDisabled ? "Disabled" : "Enabled"}
                  </button>
                </div>

                <div className="flex items-start justify-between gap-4 pt-4">
                  <div className="space-y-1">
                    <h4 className="text-xs font-bold text-[var(--foreground-color)]">AI Auto-Reply Monitor & Inbox Hook</h4>
                    <p className="text-[11px] text-[var(--sidebar-text-muted)] leading-relaxed">
                      Automatically check your inbox for new responses, draft contextual follow-up messages, and flag hot leads directly in suggestions.
                    </p>
                  </div>
                  <button
                    onClick={handleToggleAutoReply}
                    disabled={togglingAutoReply}
                    style={{ background: autoReplyEnabled ? "rgba(16,185,129,0.1)" : "var(--sidebar-toggle-bg)", borderColor: "var(--card-border)" }}
                    className={`border px-3 py-1.5 rounded-lg text-[11px] font-bold transition-all disabled:opacity-50 cursor-pointer whitespace-nowrap ${
                      autoReplyEnabled ? "text-green-500" : "text-[var(--sidebar-text-muted)]"
                    }`}
                  >
                    {togglingAutoReply ? "Toggling..." : autoReplyEnabled ? "Active Monitor" : "Inactive"}
                  </button>
                </div>
              </div>
            </div>
          </div>

          {/* Column 2: Inbox & Conversation Feeds */}
          <div className="space-y-6">
            
            {/* Active Conversations Panel */}
            <div style={cardStyle} className="p-6 space-y-4">
              <h2 style={{ borderColor: "var(--card-border)" }} className="text-base font-bold text-[var(--foreground-color)] flex items-center gap-2 border-b pb-3">
                <MessageSquare className="h-5 w-5 text-[var(--primary)]" />
                Active Inbox Threads
              </h2>
              
              {conversations.length > 0 ? (
                <div className="space-y-3 max-h-[360px] overflow-y-auto pr-1">
                  {conversations.map((convo, i) => (
                    <div
                      key={convo.id || i}
                      style={{ background: "var(--sidebar-toggle-bg)", borderColor: "var(--card-border)" }}
                      className="p-3 border rounded-xl space-y-1.5 relative group hover:border-[var(--primary)] transition-all"
                    >
                      {convo.has_unread && (
                        <span className="absolute top-3 right-3 h-2 w-2 rounded-full bg-[var(--primary)] animate-pulse" />
                      )}
                      <div className="flex items-center justify-between">
                        <h4 className="text-xs font-bold text-[var(--foreground-color)] truncate max-w-[150px]">
                          {convo.contact_name}
                        </h4>
                        <span className="text-[9px] text-[var(--sidebar-text-muted)]">
                          {convo.last_message_at ? new Date(convo.last_message_at).toLocaleDateString() : ""}
                        </span>
                      </div>
                      <p className="text-[10px] text-[var(--sidebar-text-muted)] line-clamp-2 leading-relaxed">
                        {convo.last_message_preview || "No messages parsed yet"}
                      </p>
                      <a
                        href={convo.contact_linkedin_url}
                        target="_blank"
                        rel="noreferrer"
                        className="text-[9px] text-[var(--primary)] hover:underline inline-flex items-center gap-1 font-bold pt-1"
                      >
                        Open LinkedIn Profile <ArrowRight className="h-2 w-2" />
                      </a>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-center py-8 text-[var(--sidebar-text-muted)] space-y-2">
                  <MessageSquare className="h-8 w-8 mx-auto opacity-30" />
                  <p className="text-xs">No active conversations synced.</p>
                </div>
              )}
            </div>

            {/* Relationship Stage Metrics */}
            <div style={cardStyle} className="p-6 space-y-4">
              <h2 style={{ borderColor: "var(--card-border)" }} className="text-base font-bold text-[var(--foreground-color)] flex items-center gap-2 border-b pb-3">
                <Activity className="h-5 w-5 text-[var(--primary)]" />
                Pipeline Stages
              </h2>
              
              {relationships.length > 0 ? (
                <div className="space-y-3">
                  {/* Stage Summary Statistics */}
                  <div className="grid grid-cols-2 gap-2">
                    <div style={{ background: "var(--sidebar-toggle-bg)" }} className="p-2.5 rounded-lg text-center">
                      <span className="text-[10px] text-[var(--sidebar-text-muted)] font-medium">Total Leads</span>
                      <p className="text-lg font-black text-[var(--foreground-color)] mt-0.5">{relationships.length}</p>
                    </div>
                    <div style={{ background: "var(--sidebar-toggle-bg)" }} className="p-2.5 rounded-lg text-center">
                      <span className="text-[10px] text-[var(--sidebar-text-muted)] font-medium">Meetings booked</span>
                      <p className="text-lg font-black text-emerald-500 mt-0.5">
                        {relationships.filter(r => r.current_stage === "meeting_booked" || r.current_stage === "closed_won").length}
                      </p>
                    </div>
                  </div>

                  {/* Top Leads List */}
                  <div className="space-y-2 max-h-[200px] overflow-y-auto pr-1">
                    {relationships.slice(0, 5).map((rel) => {
                      const colors = stageColors[rel.current_stage] || {
                        bg: "var(--sidebar-toggle-bg)",
                        text: "var(--foreground-color)",
                        border: "var(--card-border)"
                      };
                      return (
                        <div
                          key={rel.id}
                          style={{ borderColor: "var(--card-border)" }}
                          className="flex items-center justify-between p-2 border rounded-lg text-xs"
                        >
                          <span className="font-bold text-[var(--foreground-color)] truncate max-w-[120px]">
                            {rel.contact_name || "Unknown Lead"}
                          </span>
                          <span
                            style={{ background: colors.bg, color: colors.text, borderColor: colors.border }}
                            className="text-[9px] font-black border px-2 py-0.5 rounded-full capitalize"
                          >
                            {rel.current_stage.replace("_", " ")}
                          </span>
                        </div>
                      );
                    })}
                  </div>
                </div>
              ) : (
                <div className="text-center py-8 text-[var(--sidebar-text-muted)] space-y-2">
                  <Activity className="h-8 w-8 mx-auto opacity-30" />
                  <p className="text-xs">No campaign pipeline data loaded.</p>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ── TABS AND OTHER PANELS... (OMITTED REDUNDANCY) ── */}
      {/* ══════════════════════════════════════════════════════
         PANEL 2: APPROVALS QUEUE
         ══════════════════════════════════════════════════════ */}
      {mainTab === "queue" && (
        <div className="grid lg:grid-cols-3 gap-6">
          
          {/* Column 1: Action approvals feed */}
          <div className="lg:col-span-2 space-y-6">
            
            {/* Pending Actions List */}
            <div style={cardStyle} className="p-6 space-y-4">
              <div style={{ borderColor: "var(--card-border)" }} className="flex items-center justify-between border-b pb-3">
                <h2 className="text-base font-bold text-[var(--foreground-color)] flex items-center gap-2">
                  <Clock className="h-5 w-5 text-amber-500" />
                  Outreach Approvals Checklist
                </h2>
                <button
                  onClick={loadAllData}
                  className="text-[var(--sidebar-text-muted)] hover:text-[var(--foreground-color)] transition-colors p-1"
                  title="Refresh Queue"
                >
                  <RefreshCw className="h-4 w-4" />
                </button>
              </div>

              {pendingActions.length > 0 ? (
                <div className="space-y-4">
                  {pendingActions.map((action) => {
                    const isEditing = editingActionId === action.id;
                    const badgeStyles = statusColors[action.status] || {
                      bg: "var(--sidebar-toggle-bg)",
                      text: "var(--foreground-color)",
                      border: "var(--card-border)"
                    };
                    return (
                      <div
                        key={action.id}
                        style={{ background: "var(--sidebar-toggle-bg)", borderColor: "var(--card-border)" }}
                        className="p-4 border rounded-xl space-y-3"
                      >
                        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[var(--card-border)] pb-2.5">
                          <div className="flex items-center gap-2">
                            <span className="text-[10px] uppercase font-black tracking-wider text-[var(--primary)] bg-[rgba(124,92,255,0.08)] px-2.5 py-0.5 rounded border border-[rgba(124,92,255,0.2)]">
                              {action.action_type.replace("_", " ")}
                            </span>
                            <span
                              style={{ background: badgeStyles.bg, color: badgeStyles.text, borderColor: badgeStyles.border }}
                              className="text-[9px] font-black border px-2 py-0.5 rounded capitalize"
                            >
                              {action.status.replace("_", " ")}
                            </span>
                          </div>
                          
                          <span className="text-[9px] text-[var(--sidebar-text-muted)]">
                            Created: {new Date(action.created_at).toLocaleString()}
                          </span>
                        </div>

                        {/* URL info */}
                        <div className="text-xs space-y-1">
                          <span className="text-[9px] uppercase tracking-wider text-[var(--sidebar-text-muted)] font-black">Target Profile</span>
                          <a
                            href={action.linkedin_url}
                            target="_blank"
                            rel="noreferrer"
                            className="text-[var(--primary)] font-bold hover:underline block truncate"
                          >
                            {action.linkedin_url}
                          </a>
                        </div>

                        {/* Draft Message Area */}
                        <div className="space-y-1">
                          <span className="text-[9px] uppercase tracking-wider text-[var(--sidebar-text-muted)] font-black">Draft Message</span>
                          {isEditing ? (
                            <div className="space-y-2">
                              <textarea
                                value={editMessage}
                                onChange={(e) => setEditMessage(e.target.value)}
                                rows={4}
                                style={{ background: "var(--card-bg)", borderColor: "var(--card-border)", color: "var(--foreground-color)" }}
                                className="w-full text-xs p-3 border rounded-lg focus:outline-none"
                              />
                              <div className="flex justify-end gap-2">
                                <button
                                  onClick={() => handleEditSave(action.id)}
                                  className="bg-green-500 hover:brightness-110 text-white px-3 py-1.5 rounded-lg text-xs font-bold flex items-center gap-1 transition-all cursor-pointer"
                                >
                                  <Check className="h-3 w-3" /> Save Changes
                                </button>
                                <button
                                  onClick={() => {
                                    setEditingActionId(null);
                                    setEditMessage("");
                                  }}
                                  style={{ background: "var(--sidebar-toggle-bg)", borderColor: "var(--card-border)" }}
                                  className="border text-[var(--foreground-color)] px-3 py-1.5 rounded-lg text-xs font-bold flex items-center gap-1 transition-all cursor-pointer"
                                >
                                  <X className="h-3 w-3" /> Cancel
                                </button>
                              </div>
                            </div>
                          ) : (
                            <div
                              style={{ background: "var(--card-bg)", borderColor: "var(--card-border)" }}
                              className="border p-3 rounded-lg text-xs text-[var(--foreground-color)] relative group whitespace-pre-wrap leading-relaxed"
                            >
                              {action.message ? action.message : <em className="text-[var(--sidebar-text-muted)]">No note attached (blank connection request)</em>}
                              <button
                                onClick={() => {
                                  setEditingActionId(action.id);
                                  setEditMessage(action.message || "");
                                }}
                                className="absolute right-2.5 bottom-2.5 bg-[var(--sidebar-toggle-bg)] hover:bg-[var(--sidebar-toggle-hover)] border border-[var(--card-border)] p-1.5 rounded-lg text-[var(--sidebar-text-muted)] hover:text-[var(--foreground-color)] opacity-0 group-hover:opacity-100 transition-opacity cursor-pointer"
                                title="Edit Draft"
                              >
                                <Edit3 className="h-3.5 w-3.5" />
                              </button>
                            </div>
                          )}
                        </div>

                        {/* Scheduling inputs */}
                        {reschedulingActionId === action.id ? (
                          <div style={{ background: "var(--card-bg)", borderColor: "var(--card-border)" }} className="border p-3 rounded-lg flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                            <input
                              type="datetime-local"
                              value={rescheduleTime}
                              onChange={(e) => setRescheduleTime(e.target.value)}
                              style={inputStyle}
                              className="max-w-[200px]"
                            />
                            <div className="flex gap-2">
                              <button
                                onClick={() => handleReschedule(action.id)}
                                className="bg-[var(--primary)] hover:brightness-110 text-white px-3 py-1.5 rounded-lg text-xs font-bold transition-all cursor-pointer"
                              >
                                Reschedule
                              </button>
                              <button
                                onClick={() => {
                                  setReschedulingActionId(null);
                                  setRescheduleTime("");
                                }}
                                style={{ background: "var(--sidebar-toggle-bg)", borderColor: "var(--card-border)" }}
                                className="border text-[var(--foreground-color)] px-3 py-1.5 rounded-lg text-xs font-bold transition-all cursor-pointer"
                              >
                                Cancel
                              </button>
                            </div>
                          </div>
                        ) : null}

                        {/* Action buttons */}
                        <div className="flex flex-wrap items-center justify-between gap-3 pt-2.5 border-t border-[var(--card-border)]">
                          <button
                            onClick={() => {
                              setReschedulingActionId(action.id);
                              // Default reschedule to 1 hour from now
                              const def = new Date();
                              def.setHours(def.getHours() + 1);
                              setRescheduleTime(def.toISOString().slice(0, 16));
                            }}
                            className="text-[10px] text-[var(--sidebar-text-muted)] hover:text-[var(--primary)] hover:underline flex items-center gap-1.5 font-bold cursor-pointer"
                          >
                            <Clock className="h-3.5 w-3.5" />
                            Schedule/Reschedule
                          </button>

                          <div className="flex gap-2">
                            <button
                              onClick={() => handleReject(action.id)}
                              className="bg-red-500/10 hover:bg-red-500/20 text-red-500 px-3.5 py-1.5 rounded-lg text-xs font-bold flex items-center gap-1 transition-all cursor-pointer"
                            >
                              <XCircle className="h-3.5 w-3.5" /> Reject
                            </button>
                            <button
                              onClick={() => handleApprove(action.id)}
                              disabled={approvingId !== null}
                              className="bg-[var(--primary)] hover:brightness-110 text-white px-4 py-1.5 rounded-lg text-xs font-black flex items-center gap-1 transition-all disabled:opacity-50 cursor-pointer"
                            >
                              {approvingId === action.id ? (
                                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                              ) : (
                                <CheckCircle2 className="h-3.5 w-3.5" />
                              )}
                              Approve & Send
                            </button>
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              ) : (
                <div className="text-center py-12 text-[var(--sidebar-text-muted)] space-y-2">
                  <CheckCircle2 className="h-10 w-10 mx-auto text-emerald-500 animate-bounce" />
                  <h4 className="text-sm font-bold text-[var(--foreground-color)]">Outreach Queue Clear</h4>
                  <p className="text-xs max-w-xs mx-auto">
                    All generated LinkedIn actions have been dispatched. Launch a campaign or parse a CSV leads file to queue more actions.
                  </p>
                </div>
              )}
            </div>
          </div>

          {/* Column 2: Limit gauges and history log */}
          <div className="space-y-6">
            
            {/* Limit metrics gauges */}
            <div style={cardStyle} className="p-6 space-y-4">
              <h2 style={{ borderColor: "var(--card-border)" }} className="text-base font-bold text-[var(--foreground-color)] flex items-center gap-2 border-b pb-3">
                <BarChart3 className="h-5 w-5 text-[var(--primary)]" />
                Daily Automation Quotas
              </h2>

              {queueStatus ? (
                <div className="space-y-4">
                  {/* Connections gauge */}
                  <div className="space-y-1.5">
                    <div className="flex items-center justify-between text-xs">
                      <span className="font-medium text-[var(--sidebar-text-muted)]">Connection Requests Sent</span>
                      <span className="font-bold text-[var(--foreground-color)]">
                        {queueStatus.daily_connections.used} / {queueStatus.daily_connections.max}
                      </span>
                    </div>
                    <div className="h-2 w-full bg-[var(--sidebar-toggle-bg)] rounded-full overflow-hidden border border-[var(--card-border)]">
                      <div
                        style={{
                          width: `${Math.min(100, (queueStatus.daily_connections.used / queueStatus.daily_connections.max) * 100)}%`,
                          background: "linear-gradient(90deg, var(--primary) 0%, var(--secondary) 100%)"
                        }}
                        className="h-full rounded-full transition-all duration-500"
                      />
                    </div>
                    <p className="text-[9px] text-[var(--sidebar-text-muted)]">
                      Remaining quota: {queueStatus.daily_connections.remaining} requests
                    </p>
                  </div>

                  {/* Messages gauge */}
                  <div className="space-y-1.5">
                    <div className="flex items-center justify-between text-xs">
                      <span className="font-medium text-[var(--sidebar-text-muted)]">InMail / Message Dispatches</span>
                      <span className="font-bold text-[var(--foreground-color)]">
                        {queueStatus.daily_messages.used} / {queueStatus.daily_messages.max}
                      </span>
                    </div>
                    <div className="h-2 w-full bg-[var(--sidebar-toggle-bg)] rounded-full overflow-hidden border border-[var(--card-border)]">
                      <div
                        style={{
                          width: `${Math.min(100, (queueStatus.daily_messages.used / queueStatus.daily_messages.max) * 100)}%`,
                          background: "linear-gradient(90deg, var(--primary) 0%, var(--secondary) 100%)"
                        }}
                        className="h-full rounded-full transition-all duration-500"
                      />
                    </div>
                    <p className="text-[9px] text-[var(--sidebar-text-muted)]">
                      Remaining quota: {queueStatus.daily_messages.remaining} dispatches
                    </p>
                  </div>
                </div>
              ) : (
                <div className="text-center py-6 text-[var(--sidebar-text-muted)]">
                  <p className="text-xs">No active limits data synced.</p>
                </div>
              )}
            </div>

            {/* Historic Execution logs */}
            <div style={cardStyle} className="p-6 space-y-4">
              <h2 style={{ borderColor: "var(--card-border)" }} className="text-base font-bold text-[var(--foreground-color)] flex items-center gap-2 border-b pb-3">
                <Activity className="h-5 w-5 text-[var(--primary)]" />
                Historic Dispatch Log
              </h2>

              {history.length > 0 ? (
                <div className="space-y-3 max-h-[300px] overflow-y-auto pr-1">
                  {history.map((item) => {
                    const badge = statusColors[item.status] || {
                      bg: "var(--sidebar-toggle-bg)",
                      text: "var(--foreground-color)",
                      border: "var(--card-border)"
                    };
                    const isFailed = item.status === "failed";
                    return (
                      <div
                        key={item.id}
                        style={{ background: "var(--sidebar-toggle-bg)", borderColor: "var(--card-border)" }}
                        className="p-3 border rounded-xl space-y-2 text-xs"
                      >
                        <div className="flex items-center justify-between">
                          <span className="font-bold text-[var(--foreground-color)] capitalize">
                            {item.action_type.replace("_", " ")}
                          </span>
                          <span
                            style={{ background: badge.bg, color: badge.text, borderColor: badge.border }}
                            className="text-[9px] font-bold border px-1.5 py-0.5 rounded capitalize"
                          >
                            {item.status}
                          </span>
                        </div>
                        
                        <p className="text-[10px] text-[var(--sidebar-text-muted)] truncate block">
                          Target: {item.linkedin_url}
                        </p>
                        
                        <p className="text-[10px] text-[var(--foreground-color)] line-clamp-2 italic">
                          "{item.message}"
                        </p>

                        {isFailed && item.error && (
                          <div className="bg-red-500/10 border border-red-500/20 text-red-500 p-2 rounded text-[10px] space-y-1">
                            <span className="font-bold">Error Info:</span>
                            <p className="leading-normal">{item.error}</p>
                            {item.execution_result?.error_screenshot && (
                              <button
                                onClick={() => setScreenshotUrl(item.execution_result?.error_screenshot || null)}
                                className="text-[10px] font-bold text-[var(--primary)] hover:underline flex items-center gap-1 pt-1 cursor-pointer"
                              >
                                <Eye className="h-3 w-3" /> View Execution Screenshot
                              </button>
                            )}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              ) : (
                <div className="text-center py-8 text-[var(--sidebar-text-muted)] space-y-2">
                  <FileText className="h-8 w-8 mx-auto opacity-30" />
                  <p className="text-xs">No historic dispatches logged.</p>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ══════════════════════════════════════════════════════
         PANEL 3: CAMPAIGNS & STRATEGY
         ══════════════════════════════════════════════════════ */}
      {mainTab === "campaigns" && (
        <div className="space-y-6">
          
          {/* Sub Tab selection */}
          <div style={{ background: "var(--sidebar-toggle-bg)", borderColor: "var(--card-border)" }} className="flex gap-2 p-1 border rounded-xl w-fit">
            <button
              onClick={() => setCampaignSubTab("outreach")}
              style={{ background: campaignSubTab === "outreach" ? "var(--card-bg)" : "transparent", color: campaignSubTab === "outreach" ? "var(--primary)" : "var(--sidebar-text-muted)" }}
              className="px-4 py-1.5 rounded-lg text-xs font-bold transition-all cursor-pointer"
            >
              Outreach Campaigns
            </button>
            <button
              onClick={() => setCampaignSubTab("content")}
              style={{ background: campaignSubTab === "content" ? "var(--card-bg)" : "transparent", color: campaignSubTab === "content" ? "var(--primary)" : "var(--sidebar-text-muted)" }}
              className="px-4 py-1.5 rounded-lg text-xs font-bold transition-all cursor-pointer"
            >
              Content Strategy Crew
            </button>
          </div>

          {/* Sub Panel 1: Outreach Campaigns */}
          {campaignSubTab === "outreach" && (
            <div className="grid lg:grid-cols-3 gap-6">
              
              {/* Campaigns list */}
              <div className="lg:col-span-2 space-y-6">
                <div style={cardStyle} className="p-6 space-y-4">
                  <div style={{ borderColor: "var(--card-border)" }} className="flex items-center justify-between border-b pb-3">
                    <h2 className="text-base font-bold text-[var(--foreground-color)] flex items-center gap-2">
                      <Target className="h-5 w-5 text-[var(--primary)]" />
                      Active Outreach Pipelines
                    </h2>
                    <button
                      onClick={() => setShowCampaignForm(!showCampaignForm)}
                      className="bg-[var(--primary)] hover:brightness-110 text-white p-1.5 rounded-lg text-xs font-bold flex items-center gap-1.5 transition-all cursor-pointer"
                    >
                      {showCampaignForm ? <X className="h-4 w-4" /> : <Plus className="h-4 w-4" />}
                      New Campaign
                    </button>
                  </div>

                  {/* Campaign Creation Drawer */}
                  {showCampaignForm && (
                    <form onSubmit={handleCreateCampaign} style={{ background: "var(--sidebar-toggle-bg)", borderColor: "var(--card-border)" }} className="p-4 border rounded-xl space-y-3">
                      <h3 className="text-xs font-bold text-[var(--foreground-color)]">Configure LinkedIn Pipeline</h3>
                      <div className="grid sm:grid-cols-3 gap-3">
                        <div className="space-y-1">
                          <label className="text-[10px] text-[var(--sidebar-text-muted)] font-bold">Campaign Name</label>
                          <input
                            type="text"
                            required
                            placeholder="SaaS Founders Pitch"
                            value={newCampaignName}
                            onChange={(e) => setNewCampaignName(e.target.value)}
                            style={inputStyle}
                          />
                        </div>
                        <div className="space-y-1">
                          <label className="text-[10px] text-[var(--sidebar-text-muted)] font-bold">Goal / Pitch</label>
                          <input
                            type="text"
                            placeholder="Book Demo Call"
                            value={newCampaignGoal}
                            onChange={(e) => setNewCampaignGoal(e.target.value)}
                            style={inputStyle}
                          />
                        </div>
                        <div className="space-y-1">
                          <label className="text-[10px] text-[var(--sidebar-text-muted)] font-bold">Target Audience</label>
                          <input
                            type="text"
                            placeholder="CTOs, Tech Founders"
                            value={newCampaignAudience}
                            onChange={(e) => setNewCampaignAudience(e.target.value)}
                            style={inputStyle}
                          />
                        </div>
                      </div>
                      <div className="flex justify-end pt-1">
                        <button
                          type="submit"
                          className="bg-[var(--primary)] hover:brightness-110 text-white px-4 py-2 rounded-lg text-xs font-bold transition-all cursor-pointer"
                        >
                          Create & Initialize Pipeline
                        </button>
                      </div>
                    </form>
                  )}

                  {/* Pipelines map */}
                  {outreachCampaigns.length > 0 ? (
                    <div className="space-y-4">
                      {outreachCampaigns.map((camp) => {
                        const isActive = camp.status === "active";
                        const isDraft = camp.status === "draft";
                        const isPaused = camp.status === "paused";
                        return (
                          <div
                            key={camp.id}
                            style={{ background: "var(--sidebar-toggle-bg)", borderColor: "var(--card-border)" }}
                            className="p-4 border rounded-xl space-y-3 hover:border-[var(--primary)] transition-all"
                          >
                            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[var(--card-border)] pb-2.5">
                              <div>
                                <h3 className="text-sm font-bold text-[var(--foreground-color)]">{camp.name}</h3>
                                <p className="text-[10px] text-[var(--sidebar-text-muted)] mt-0.5">
                                  Goal: {camp.goal || "Not Configured"} | Audience: {camp.target_audience || "Unspecified"}
                                </p>
                              </div>
                              <div className="flex items-center gap-2">
                                <span className={`text-[9px] font-black border px-2 py-0.5 rounded capitalize ${
                                  isActive
                                    ? "bg-green-500/10 text-green-500 border-green-500/20"
                                    : isPaused
                                    ? "bg-amber-500/10 text-amber-500 border-amber-500/20"
                                    : "bg-slate-500/10 text-[var(--sidebar-text-muted)] border-slate-500/20"
                                }`}>
                                  {camp.status}
                                </span>
                              </div>
                            </div>

                            <div className="grid sm:grid-cols-3 gap-3 text-xs">
                              <div style={{ background: "var(--card-bg)" }} className="p-2.5 rounded-lg border border-[var(--card-border)] text-center">
                                <span className="text-[10px] text-[var(--sidebar-text-muted)] font-medium">Outreach Action Dispatches</span>
                                <p className="text-sm font-black text-[var(--foreground-color)] mt-0.5">
                                  {camp.executed_actions} / {camp.total_planned_actions}
                                </p>
                              </div>
                              
                              <div style={{ background: "var(--card-bg)" }} className="p-2.5 rounded-lg border border-[var(--card-border)] text-center">
                                <span className="text-[10px] text-[var(--sidebar-text-muted)] font-medium">Daily Send Limits</span>
                                <p className="text-sm font-bold text-[var(--foreground-color)] mt-0.5">
                                  Conn: {camp.daily_connection_limit} | InMail: {camp.daily_message_limit}
                                </p>
                              </div>

                              {/* CSV Import lead loader */}
                              <div style={{ background: "var(--card-bg)" }} className="p-2 border border-[var(--card-border)] rounded-lg flex flex-col justify-center items-center text-center">
                                <label className="text-[10px] text-[var(--primary)] hover:brightness-95 font-bold cursor-pointer flex items-center gap-1">
                                  <Upload className="h-3 w-3" />
                                  Upload Leads CSV
                                  <input
                                    type="file"
                                    accept=".csv,.txt"
                                    onChange={(e) => handleCSVFileChange(e, camp.id)}
                                    className="hidden"
                                  />
                                </label>
                                <span className="text-[8px] text-[var(--sidebar-text-muted)] mt-0.5">Loads contacts into campaign</span>
                              </div>
                            </div>

                            <div className="flex justify-end gap-2 pt-1">
                              {isActive ? (
                                <button
                                  onClick={() => handlePauseCampaign(camp.id)}
                                  className="bg-amber-500/10 hover:bg-amber-500/20 text-amber-500 px-3.5 py-1.5 rounded-lg text-xs font-bold flex items-center gap-1 transition-all cursor-pointer"
                                >
                                  <Pause className="h-3.5 w-3.5" /> Pause Campaign
                                </button>
                              ) : (
                                <button
                                  onClick={() => handleStartCampaign(camp.id)}
                                  className="bg-green-500/10 hover:bg-green-500/20 text-green-500 px-3.5 py-1.5 rounded-lg text-xs font-bold flex items-center gap-1 transition-all cursor-pointer"
                                >
                                  <Play className="h-3.5 w-3.5" /> Launch Campaign
                                </button>
                              )}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  ) : (
                    <div className="text-center py-12 text-[var(--sidebar-text-muted)] space-y-2">
                      <Target className="h-10 w-10 mx-auto opacity-30" />
                      <h4 className="text-sm font-bold text-[var(--foreground-color)]">No Outreach Campaigns</h4>
                      <p className="text-xs">Configure a campaign pipeline to manage connection request sequences.</p>
                    </div>
                  )}
                </div>
              </div>

              {/* CSV Import Results Feed */}
              <div className="space-y-6">
                <div style={cardStyle} className="p-6 space-y-4">
                  <h2 style={{ borderColor: "var(--card-border)" }} className="text-base font-bold text-[var(--foreground-color)] flex items-center gap-2 border-b pb-3">
                    <FileSpreadsheet className="h-5 w-5 text-[var(--primary)]" />
                    CSV Import Statistics
                  </h2>

                  {csvImportResult ? (
                    <div style={{ background: "var(--sidebar-toggle-bg)", borderColor: "var(--card-border)" }} className="p-4 border rounded-xl space-y-3 text-xs">
                      <div className="flex items-center gap-2 text-green-500 font-bold border-b border-[var(--card-border)] pb-2">
                        <CheckCircle2 className="h-4 w-4" />
                        <span>File Parsed: {csvImportResult.filename}</span>
                      </div>
                      
                      <div className="space-y-2 leading-relaxed">
                        <div className="flex justify-between">
                          <span className="text-[var(--sidebar-text-muted)]">Total Rows:</span>
                          <span className="font-bold text-[var(--foreground-color)]">{csvImportResult.total_rows}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-[var(--sidebar-text-muted)]">Valid Contacts:</span>
                          <span className="font-bold text-[var(--foreground-color)]">{csvImportResult.valid_leads}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-[var(--sidebar-text-muted)]">New Contacts Loaded:</span>
                          <span className="font-bold text-green-500">{csvImportResult.leads_created}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-[var(--sidebar-text-muted)]">Existing Contacts Updated:</span>
                          <span className="font-bold text-[var(--primary)]">{csvImportResult.leads_updated}</span>
                        </div>
                      </div>

                      {csvImportResult.errors && csvImportResult.errors.length > 0 ? (
                        <div className="bg-red-500/10 border border-red-500/20 text-red-500 p-2.5 rounded-lg space-y-1">
                          <span className="font-bold text-[10px] uppercase flex items-center gap-1">
                            <AlertTriangle className="h-3 w-3" /> Parsing Warnings
                          </span>
                          <ul className="list-disc list-inside text-[9px] space-y-0.5">
                            {csvImportResult.errors.slice(0, 5).map((e, idx) => (
                              <li key={idx} className="truncate">{e}</li>
                            ))}
                          </ul>
                        </div>
                      ) : null}
                    </div>
                  ) : (
                    <div className="text-center py-8 text-[var(--sidebar-text-muted)] space-y-2">
                      <Upload className="h-8 w-8 mx-auto opacity-30" />
                      <p className="text-xs">No CSV load statistics available yet.</p>
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* Sub Panel 2: Content Strategy */}
          {campaignSubTab === "content" && (
            <div className="grid lg:grid-cols-3 gap-6">
              
              {/* Strategy Generator parameters Form */}
              <div className="space-y-6">
                <div style={cardStyle} className="p-6 space-y-4">
                  <h2 style={{ borderColor: "var(--card-border)" }} className="text-base font-bold text-[var(--foreground-color)] flex items-center gap-2 border-b pb-3">
                    <Sparkles className="h-5 w-5 text-[var(--primary)]" />
                    Content Strategy Generator
                  </h2>
                  <p className="text-[11px] text-[var(--sidebar-text-muted)]">
                    Activate the AI Strategy Crew to research your industry, structure marketing content pillars, and compile a tailored 7-day post schedule.
                  </p>
                  
                  <form onSubmit={handleGenerate} className="space-y-3 text-xs">
                    <div className="space-y-1">
                      <label className="text-[10px] text-[var(--sidebar-text-muted)] font-bold">Connect outreach pipeline (Optional)</label>
                      <select
                        value={selectedCampaignId}
                        onChange={(e) => setSelectedCampaignId(e.target.value)}
                        style={selectStyle}
                      >
                        <option value="">Do not bind to outreach campaign</option>
                        {campaigns.map((c) => (
                          <option key={c.id} value={c.id}>{c.name}</option>
                        ))}
                      </select>
                    </div>

                    <div className="space-y-1">
                      <label className="text-[10px] text-[var(--sidebar-text-muted)] font-bold">Campaign Target Goal</label>
                      <input
                        type="text"
                        required
                        placeholder="Promote SaaS launch, hire engineers, build brand authority"
                        value={campaignGoal}
                        onChange={(e) => setCampaignGoal(e.target.value)}
                        style={inputStyle}
                      />
                    </div>

                    <div className="space-y-1">
                      <label className="text-[10px] text-[var(--sidebar-text-muted)] font-bold">Target Audience Persona</label>
                      <input
                        type="text"
                        required
                        placeholder="Venture Capitalists, Engineering Leads, Product Managers"
                        value={targetAudience}
                        onChange={(e) => setTargetAudience(e.target.value)}
                        style={inputStyle}
                      />
                    </div>

                    <div className="space-y-1">
                      <label className="text-[10px] text-[var(--sidebar-text-muted)] font-bold">Industry Sector</label>
                      <input
                        type="text"
                        required
                        placeholder="AI/ML, B2B SaaS, FinTech, Web3"
                        value={industry}
                        onChange={(e) => setIndustry(e.target.value)}
                        style={inputStyle}
                      />
                    </div>

                    {formError && (
                      <div className="bg-red-500/10 border border-red-500/20 text-red-500 p-2.5 rounded-lg flex items-center gap-1.5 font-bold">
                        <AlertCircle className="h-4 w-4" />
                        {formError}
                      </div>
                    )}

                    <button
                      type="submit"
                      disabled={generating}
                      style={{ boxShadow: "0 4px 16px rgba(124,92,255,0.25)" }}
                      className="w-full bg-[var(--primary)] hover:brightness-110 text-white py-2 rounded-lg font-black transition-all flex items-center justify-center gap-2 disabled:opacity-50 cursor-pointer"
                    >
                      {generating ? (
                        <>
                          <Loader2 className="h-4.5 w-4.5 animate-spin" />
                          Crew generating content calendar...
                        </>
                      ) : (
                        <>
                          <Sparkles className="h-4.5 w-4.5" />
                          Execute Content Strategy Crew
                        </>
                      )}
                    </button>
                  </form>
                </div>
              </div>

              {/* Day-by-Day Calendar Preview grid */}
              <div className="lg:col-span-2 space-y-6">
                <div style={cardStyle} className="p-6 space-y-4">
                  <div style={{ borderColor: "var(--card-border)" }} className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b pb-3">
                    <h2 className="text-base font-bold text-[var(--foreground-color)] flex items-center gap-2">
                      <CalendarIcon className="h-5 w-5 text-[var(--primary)]" />
                      Strategic Content Calendars
                    </h2>
                    
                    {/* Calendar select dropdown */}
                    {calendars.length > 0 && (
                      <select
                        value={selectedCalendar?.id || ""}
                        onChange={(e) => {
                          const found = calendars.find(c => c.id === e.target.value);
                          if (found) setSelectedCalendar(found);
                        }}
                        style={selectStyle}
                        className="max-w-[240px]"
                      >
                        {calendars.map((cal, index) => (
                          <option key={cal.id || index} value={cal.id}>
                            Strategy: {cal.industry} ({new Date(cal.created_at).toLocaleDateString()})
                          </option>
                        ))}
                      </select>
                    )}
                  </div>

                  {selectedCalendar ? (
                    <div className="space-y-4 text-xs">
                      {/* Strategy Summary info */}
                      <div style={{ background: "var(--sidebar-toggle-bg)", borderColor: "var(--card-border)" }} className="border p-4 rounded-xl space-y-2.5">
                        <h3 className="text-xs font-bold text-[var(--foreground-color)] uppercase tracking-wider">Strategy Briefing</h3>
                        <div className="grid sm:grid-cols-3 gap-3">
                          <div>
                            <span className="text-[10px] text-[var(--sidebar-text-muted)] font-medium">Primary Goal</span>
                            <p className="font-bold text-[var(--foreground-color)] mt-0.5">{selectedCalendar.campaign_goal}</p>
                          </div>
                          <div>
                            <span className="text-[10px] text-[var(--sidebar-text-muted)] font-medium">Audience Persona</span>
                            <p className="font-bold text-[var(--foreground-color)] mt-0.5">{selectedCalendar.target_audience}</p>
                          </div>
                          <div>
                            <span className="text-[10px] text-[var(--sidebar-text-muted)] font-medium">Industry Focus</span>
                            <p className="font-bold text-[var(--foreground-color)] mt-0.5">{selectedCalendar.industry}</p>
                          </div>
                        </div>

                        {/* Core Pillars list */}
                        {selectedCalendar.pillars && selectedCalendar.pillars.length > 0 && (
                          <div className="pt-2.5 border-t border-[var(--card-border)] space-y-1.5">
                            <span className="text-[10px] text-[var(--sidebar-text-muted)] font-medium">Marketing Content Pillars</span>
                            <div className="flex flex-wrap gap-1.5">
                              {selectedCalendar.pillars.map((p, idx) => (
                                <span key={idx} style={{ background: "var(--card-bg)", borderColor: "var(--card-border)" }} className="border text-[var(--foreground-color)] font-medium px-2 py-0.5 rounded text-[10px]">
                                  {p}
                                </span>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>

                      {/* Day-by-Day Post Grid */}
                      <div className="space-y-3">
                        <h3 className="text-xs font-bold text-[var(--foreground-color)] uppercase tracking-wider">7-Day Post Schedule</h3>
                        
                        <div className="space-y-3 max-h-[400px] overflow-y-auto pr-1">
                          {selectedCalendar.schedule && selectedCalendar.schedule.map((item, idx) => (
                            <div key={idx} style={{ background: "var(--sidebar-toggle-bg)", borderColor: "var(--card-border)" }} className="border p-4 rounded-xl space-y-2.5">
                              <div className="flex items-center justify-between border-b border-[var(--card-border)] pb-2">
                                <div className="flex items-center gap-2">
                                  <span className="bg-[var(--primary)] text-white font-black px-2 py-0.5 rounded text-[10px]">
                                    Day {item.day}
                                  </span>
                                  <span style={{ background: "var(--card-bg)", borderColor: "var(--card-border)" }} className="border text-[var(--foreground-color)] px-2 py-0.5 rounded font-bold text-[9px] uppercase tracking-wider">
                                    Pillar: {item.pillar}
                                  </span>
                                </div>
                              </div>

                              <div className="space-y-1.5">
                                <h4 className="font-bold text-[var(--foreground-color)] text-xs">Topic: {item.topic}</h4>
                                {item.hook_concept && (
                                  <p className="text-[10px] text-[var(--sidebar-text-muted)] leading-relaxed">
                                    <strong className="text-[var(--foreground-color)] font-semibold">Hook Concept: </strong>
                                    {item.hook_concept}
                                  </p>
                                )}
                                
                                <div style={{ background: "var(--card-bg)", borderColor: "var(--card-border)" }} className="border p-3 rounded-lg font-mono text-[10px] leading-relaxed text-[var(--foreground-color)] whitespace-pre-wrap">
                                  {item.generated_post}
                                  {item.hashtags && item.hashtags.length > 0 && (
                                    <p className="text-[var(--primary)] font-semibold mt-2.5 font-sans">
                                      {item.hashtags.map(h => h.startsWith("#") ? h : `#${h}`).join(" ")}
                                    </p>
                                  )}
                                </div>
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>
                  ) : (
                    <div className="text-center py-16 text-[var(--sidebar-text-muted)] border border-dashed border-[var(--card-border)] rounded-xl space-y-2.5">
                      <CalendarIcon className="h-10 w-10 mx-auto opacity-30" />
                      <h4 className="text-xs font-bold text-[var(--foreground-color)]">No Content Strategy Calendars Found</h4>
                      <p className="text-[11px] max-w-xs mx-auto leading-normal">
                        Submit a goal and target audience in the generator panel on the left to spin up the AI Content Creator.
                      </p>
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── CSV PREVIEW IMPORT MODAL ─────────────────────────── */}
      {showImportModal && (
        <div style={{ background: "rgba(0,0,0,0.5)" }} className="fixed inset-0 z-50 flex items-center justify-center p-4 backdrop-blur-sm animate-fade-in">
          <div style={cardStyle} className="w-full max-w-2xl p-6 space-y-4 max-h-[85vh] overflow-y-auto">
            <div className="flex items-center justify-between border-b border-[var(--card-border)] pb-3">
              <h3 className="text-base font-bold text-[var(--foreground-color)] flex items-center gap-2">
                <FileSpreadsheet className="h-5 w-5 text-[var(--primary)]" />
                Leads CSV Verification
              </h3>
              <button
                onClick={() => {
                  setShowImportModal(false);
                  setSelectedCSVFile(null);
                }}
                className="text-[var(--sidebar-text-muted)] hover:text-[var(--foreground-color)] transition-colors p-1"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <div className="space-y-3">
              <p className="text-xs text-[var(--sidebar-text-muted)]">
                The CSV file has been parsed. Review the lead list before finalizing imports to the campaign.
              </p>
              
              <div className="border border-[var(--card-border)] rounded-xl overflow-hidden max-h-[300px] overflow-y-auto">
                <table className="w-full border-collapse text-left text-xs text-[var(--foreground-color)]">
                  <thead style={{ background: "var(--sidebar-toggle-bg)" }} className="font-bold border-b border-[var(--card-border)] sticky top-0">
                    <tr>
                      <th className="p-2.5">Name</th>
                      <th className="p-2.5">Role</th>
                      <th className="p-2.5">Company</th>
                      <th className="p-2.5">LinkedIn Profile</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[var(--card-border)]">
                    {previewLeads.map((lead, idx) => (
                      <tr key={idx} className="hover:bg-[var(--sidebar-toggle-bg)] transition-colors">
                        <td className="p-2.5 font-bold">{lead.name || "N/A"}</td>
                        <td className="p-2.5 text-[var(--sidebar-text-muted)]">{lead.role || "N/A"}</td>
                        <td className="p-2.5 text-[var(--sidebar-text-muted)]">{lead.company || "N/A"}</td>
                        <td className="p-2.5 truncate max-w-[160px] text-[var(--primary)] font-medium">
                          {lead.linkedin_url || lead.linkedin || "N/A"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            <div className="flex justify-end gap-2 border-t border-[var(--card-border)] pt-4">
              <button
                onClick={() => {
                  setShowImportModal(false);
                  setSelectedCSVFile(null);
                }}
                style={{ background: "var(--sidebar-toggle-bg)", borderColor: "var(--card-border)" }}
                className="border text-[var(--foreground-color)] px-4 py-2 rounded-lg text-xs font-bold transition-all cursor-pointer"
              >
                Cancel
              </button>
              <button
                onClick={handleImportCSV}
                className="bg-[var(--primary)] hover:brightness-110 text-white px-5 py-2 rounded-lg text-xs font-bold transition-all cursor-pointer"
              >
                Confirm & Load Leads
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── EXECUTION FAILURE SCREENSHOT MODAL ───────────── */}
      {screenshotUrl && (
        <div style={{ background: "rgba(0,0,0,0.7)" }} className="fixed inset-0 z-50 flex items-center justify-center p-4 backdrop-blur-sm">
          <div style={cardStyle} className="w-full max-w-4xl p-6 space-y-4">
            <div className="flex items-center justify-between border-b border-[var(--card-border)] pb-3">
              <h3 className="text-sm font-bold text-[var(--foreground-color)] flex items-center gap-2">
                <AlertTriangle className="h-5 w-5 text-red-500" />
                Playwright Run Error Screenshot
              </h3>
              <button
                onClick={() => setScreenshotUrl(null)}
                className="text-[var(--sidebar-text-muted)] hover:text-[var(--foreground-color)] transition-colors p-1"
              >
                <X className="h-5 w-5" />
              </button>
            </div>
            
            <div style={{ borderColor: "var(--card-border)" }} className="border rounded-lg overflow-hidden bg-slate-950 flex items-center justify-center max-h-[60vh]">
              <img
                src={screenshotUrl}
                alt="Playwright Execution Error Screenshot"
                className="max-h-[60vh] object-contain"
              />
            </div>
            
            <div className="flex justify-end gap-2 pt-1 border-t border-[var(--card-border)] pt-4">
              <a
                href={screenshotUrl}
                download="linkedin_error_screenshot.png"
                className="bg-[var(--primary)] hover:brightness-110 text-white px-4 py-2 rounded-lg text-xs font-bold transition-all"
              >
                Download Screenshot
              </a>
              <button
                onClick={() => setScreenshotUrl(null)}
                style={{ background: "var(--sidebar-toggle-bg)", borderColor: "var(--card-border)" }}
                className="border text-[var(--foreground-color)] px-4 py-2 rounded-lg text-xs font-bold transition-all cursor-pointer"
              >
                Close View
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
