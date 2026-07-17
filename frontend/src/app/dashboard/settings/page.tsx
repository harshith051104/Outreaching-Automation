"use client";

import { useState, useEffect } from "react";
import api from "@/services/api";
import { useAuthStore } from "@/store/auth-store";
import { getGmailAccounts, getGmailAuthUrl, disconnectGmailAccount } from "@/services/gmail-api";
import { getIntegrations, saveIntegration, deleteIntegration } from "@/services/integrations-api";
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from "@/components/ui/card";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Label } from "@/components/ui/label";
import IntegrationsCenter from "./integrations-center";
import { 
  Terminal,
  DatabaseBackup,
  User, 
  Settings as SettingsIcon, 
  Cpu, 
  Layers, 
  Mail, 
  Key, 
  ShieldAlert, 
  Sliders, 
  Check, 
  Eye, 
  EyeOff, 
  Link2, 
  Link2Off,
  Database,
  Clock,
  Volume2,
  Trash2,
  AlertTriangle
} from "lucide-react";

interface AIModelsConfig {
  researchModel: string;
  emailModel: string;
  classifierModel: string;
  routerMode: string;
  similarityThreshold: number;
  recencyWeight: number;
}

interface ApiKeysConfig {
  apolloApiKey: string;
  hunterApiKey: string;
  tavilyApiKey: string;
  firecrawlApiKey: string;
}

interface PreferencesConfig {
  defaultTone: string;
  focusKeywords: string;
  dailyLimit: number;
  spacingDelay: number;
  randomOffset: boolean;
  timezone: string;
}

export default function SettingsPage() {
  const { user, setUser } = useAuthStore();
  
  // States for Profile Tab
  const [profileName, setProfileName] = useState(user?.name || "");
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showCurrentPassword, setShowCurrentPassword] = useState(false);
  const [showNewPassword, setShowNewPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [profileSuccess, setProfileSuccess] = useState("");
  const [profileError, setProfileError] = useState("");

  // States for AI Models Tab (Now LLM keys management)
  const [groqKey, setGroqKey] = useState("");
  const [nvidiaKey, setNvidiaKey] = useState("");
  const [xiaomiKey, setXiaomiKey] = useState("");
  const [geminiKey, setGeminiKey] = useState("");
  const [llmStatus, setLlmStatus] = useState<Record<string, { connected: boolean; error?: string }>>({
    groq: { connected: false },
    nvidia: { connected: false },
    xiaomi: { connected: false },
    gemini: { connected: false },
  });
  const [showLlmKeys, setShowLlmKeys] = useState<Record<string, boolean>>({});
  const [llmSaveLoading, setLlmSaveLoading] = useState<Record<string, boolean>>({});
  const [aiModelsSuccess, setAiModelsSuccess] = useState("");

  // States for Integrations Tab
  const [gmailAccounts, setGmailAccounts] = useState<any[]>([]);
  const [gmailLoading, setGmailLoading] = useState(true);
  const [gmailConnecting, setGmailConnecting] = useState(false);
  const [apiKeys, setApiKeys] = useState<ApiKeysConfig>({
    apolloApiKey: "",
    hunterApiKey: "",
    tavilyApiKey: "",
    firecrawlApiKey: "",
  });
  const [showKeys, setShowKeys] = useState<Record<string, boolean>>({});
  const [apiKeysSuccess, setApiKeysSuccess] = useState("");

  // States for Preferences Tab
  const [preferences, setPreferences] = useState<PreferencesConfig>({
    defaultTone: "Professional",
    focusKeywords: "",
    dailyLimit: 50,
    spacingDelay: 30,
    randomOffset: true,
    timezone: "America/New_York",
  });
  const [preferencesSuccess, setPreferencesSuccess] = useState("");

  // States for Diagnostics Tab
  const [healthStatus, setHealthStatus] = useState<Record<string, { status: string; message: string }> | null>(null);
  const [healthLoading, setHealthLoading] = useState(false);
  const [jobStats, setJobStats] = useState<any>(null);
  const [jobStatsLoading, setJobStatsLoading] = useState(false);
  const [restoreJson, setRestoreJson] = useState("");
  const [restoreSuccess, setRestoreSuccess] = useState("");
  const [restoreError, setRestoreError] = useState("");
  const [auditLogs, setAuditLogs] = useState<any[]>([]);
  const [auditLogsLoading, setAuditLogsLoading] = useState(false);

  const fetchHealthStatus = async () => {
    setHealthLoading(true);
    try {
      const response = await api.get("/system/health-check");
      setHealthStatus(response.data);
    } catch (err) {
      console.error("Failed to fetch system health status:", err);
    } finally {
      setHealthLoading(false);
    }
  };

  const fetchJobStats = async () => {
    setJobStatsLoading(true);
    try {
      const response = await api.get("/system/background-jobs");
      setJobStats(response.data);
    } catch (err) {
      console.error("Failed to fetch background jobs stats:", err);
    } finally {
      setJobStatsLoading(false);
    }
  };

  const fetchAuditLogs = async () => {
    setAuditLogsLoading(true);
    try {
      const response = await api.get("/audit-logs");
      setAuditLogs(response.data);
    } catch (err) {
      console.error("Failed to fetch audit logs:", err);
    } finally {
      setAuditLogsLoading(false);
    }
  };

  const handleExportBackup = async () => {
    try {
      const response = await api.get("/system/backup");
      const blob = new Blob([JSON.stringify(response.data, null, 2)], { type: "application/json" });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.setAttribute("download", `outreach_backup_${new Date().toISOString().split("T")[0]}.json`);
      document.body.appendChild(link);
      link.click();
      link.remove();
    } catch (err) {
      console.error("Failed to export backup:", err);
      alert("Backup export failed. Please try again.");
    }
  };

  const handleRestoreBackup = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!restoreJson.trim()) return;
    setRestoreSuccess("");
    setRestoreError("");
    try {
      const parsed = JSON.parse(restoreJson);
      const response = await api.post("/system/restore", parsed);
      const imported = response.data.imported || {};
      setRestoreSuccess(
        `Backup restored successfully! Imported: ${imported.campaigns || 0} campaigns, ${imported.leads || 0} leads, ${imported.system_settings || 0} settings.`
      );
      setRestoreJson("");
    } catch (err: any) {
      console.error("Failed to restore backup:", err);
      setRestoreError(err.message || "Invalid JSON format or restoration failed.");
    }
  };

  // Load Gmail accounts & LocalStorage Settings on Mount
  const loadLlmStatus = async () => {
    try {
      const data = await getIntegrations();
      const statusMap: Record<string, { connected: boolean; error?: string }> = {
        groq: { connected: false },
        nvidia: { connected: false },
        xiaomi: { connected: false },
        gemini: { connected: false },
      };
      data.forEach(item => {
        if (item.provider === "groq" || item.provider === "nvidia" || item.provider === "xiaomi" || item.provider === "gemini") {
          statusMap[item.provider] = {
            connected: item.connected,
            error: item.last_error || undefined,
          };
        }
      });
      setLlmStatus(statusMap);
    } catch (err) {
      console.error("Failed to load LLM integrations status:", err);
    }
  };

  useEffect(() => {
    loadGmail();
    loadLlmStatus();
    fetchHealthStatus();
    fetchJobStats();
    fetchAuditLogs();

    // Load API key overrides from localStorage
    const savedApiKeys = localStorage.getItem("outreach_settings_api_keys");
    if (savedApiKeys) {
      try {
        setApiKeys((prev) => ({ ...prev, ...JSON.parse(savedApiKeys) }));
      } catch (err) {
        console.error("Error loading saved API keys overrides:", err);
      }
    }

    // Load preferences settings from backend API
    const loadSystemPreferences = async () => {
      try {
        const response = await api.get("/system/preferences");
        if (response.data) {
          setPreferences((prev) => ({ ...prev, ...response.data }));
        }
      } catch (err) {
        console.error("Error loading system preferences from backend:", err);
        // Fallback to localStorage
        const savedPreferences = localStorage.getItem("outreach_settings_preferences");
        if (savedPreferences) {
          try {
            setPreferences((prev) => ({ ...prev, ...JSON.parse(savedPreferences) }));
          } catch (e) {
            console.error("Error parsing localStorage preferences:", e);
          }
        }
      }
    };
    loadSystemPreferences();
  }, []);

  const loadGmail = async () => {
    setGmailLoading(true);
    try {
      const data = await getGmailAccounts();
      setGmailAccounts(data);
    } catch (err) {
      console.error("Failed to load Gmail accounts:", err);
    } finally {
      setGmailLoading(false);
    }
  };

  const handleProfileSave = (e: React.FormEvent) => {
    e.preventDefault();
    if (!user) return;
    
    // Validate password fields if filled
    if (currentPassword || newPassword || confirmPassword) {
      if (!currentPassword) {
        setProfileError("Current password is required to set a new password.");
        return;
      }
      if (newPassword !== confirmPassword) {
        setProfileError("New password and confirm password fields do not match.");
        return;
      }
      if (newPassword.length < 8) {
        setProfileError("New password must be at least 8 characters long.");
        return;
      }
    }

    setUser({ ...user, name: profileName });
    setProfileSuccess("Profile updated successfully!");
    setProfileError("");
    
    // Clear password fields
    setCurrentPassword("");
    setNewPassword("");
    setConfirmPassword("");

    setTimeout(() => setProfileSuccess(""), 3000);
  };

  const handleSaveLlmKey = async (provider: string, apiKey: string) => {
    if (!apiKey.trim()) return;
    setLlmSaveLoading(prev => ({ ...prev, [provider]: true }));
    try {
      await saveIntegration(provider, { api_key: apiKey.trim() });
      setAiModelsSuccess(`${provider === "groq" ? "Groq" : provider === "nvidia" ? "Nvidia NIM" : provider === "xiaomi" ? "Xiaomi" : "Google Gemini"} API key updated successfully!`);
      // Clear key input
      if (provider === "groq") setGroqKey("");
      else if (provider === "nvidia") setNvidiaKey("");
      else if (provider === "xiaomi") setXiaomiKey("");
      else if (provider === "gemini") setGeminiKey("");
      
      await loadLlmStatus();
      setTimeout(() => setAiModelsSuccess(""), 3000);
    } catch (err) {
      console.error("Failed to save LLM key:", err);
    } finally {
      setLlmSaveLoading(prev => ({ ...prev, [provider]: false }));
    }
  };

  const handleDeleteLlmKey = async (provider: string) => {
    const label = provider === "groq" ? "Groq" : provider === "nvidia" ? "Nvidia NIM" : provider === "xiaomi" ? "Xiaomi" : "Google Gemini";
    if (!confirm(`Remove configured key for ${label}?`)) return;
    try {
      await deleteIntegration(provider);
      setAiModelsSuccess(`${label} API key removed.`);
      await loadLlmStatus();
      setTimeout(() => setAiModelsSuccess(""), 3000);
    } catch (err) {
      console.error("Failed to delete LLM key:", err);
    }
  };

  const handleApiKeysSave = (e: React.FormEvent) => {
    e.preventDefault();
    localStorage.setItem("outreach_settings_api_keys", JSON.stringify(apiKeys));
    setApiKeysSuccess("API overrides updated successfully!");
    setTimeout(() => setApiKeysSuccess(""), 3000);
  };

  const handlePreferencesSave = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await api.post("/system/preferences", preferences);
      localStorage.setItem("outreach_settings_preferences", JSON.stringify(preferences));
      setPreferencesSuccess("System preferences updated successfully!");
    } catch (err) {
      console.error("Failed to save system preferences to backend:", err);
      // Still write to localStorage as backup
      localStorage.setItem("outreach_settings_preferences", JSON.stringify(preferences));
      setPreferencesSuccess("Preferences saved locally (failed to sync with backend).");
    } finally {
      setTimeout(() => setPreferencesSuccess(""), 3000);
    }
  };

  const handleConnectGmail = async () => {
    setGmailConnecting(true);
    try {
      const response = await getGmailAuthUrl();
      if (response && response.authorization_url) {
        window.location.href = response.authorization_url;
      } else {
        console.error("Gmail OAuth response invalid:", response);
      }
    } catch (err) {
      console.error("Failed to fetch Gmail OAuth URL:", err);
    } finally {
      setGmailConnecting(false);
    }
  };

  const handleDisconnectGmail = async (accountId: string) => {
    if (!confirm("Are you sure you want to disconnect this Gmail account? Active campaigns using this sender will fail to send.")) {
      return;
    }
    try {
      await disconnectGmailAccount(accountId);
      await loadGmail();
    } catch (err) {
      console.error("Failed to disconnect Gmail account:", err);
    }
  };

  const toggleShowKey = (field: string) => {
    setShowKeys((prev) => ({ ...prev, [field]: !prev[field] }));
  };

  const clearApiKeyOverride = (field: keyof ApiKeysConfig) => {
    const updated = { ...apiKeys, [field]: "" };
    setApiKeys(updated);
    localStorage.setItem("outreach_settings_api_keys", JSON.stringify(updated));
    setApiKeysSuccess(`Cleared override for ${field.replace("ApiKey", "").toUpperCase()}.`);
    setTimeout(() => setApiKeysSuccess(""), 3000);
  };

  const selectStyleClass = "flex h-10 w-full rounded-md border border-[var(--card-border)] bg-[var(--card-bg)] px-3 py-2 text-sm text-[var(--foreground-color)] focus:outline-none focus:ring-2 focus:ring-[var(--primary)]";
  const textareaStyleClass = "flex w-full rounded-md border border-[var(--card-border)] bg-[var(--card-bg)] p-3 text-sm text-[var(--foreground-color)] placeholder-[var(--sidebar-text-muted)]/50 focus:outline-none focus:ring-2 focus:ring-[var(--primary)]";

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-2">
        <h1 className="text-3xl font-extrabold tracking-tight bg-gradient-to-r from-blue-400 to-indigo-400 bg-clip-text text-transparent">
          System Settings
        </h1>
        <p className="text-[var(--sidebar-text-muted)] max-w-2xl text-sm">
          Fine-tune LLM routing parameters, configure Gmail senders, override API integration keys, and manage outbound preferences.
        </p>
      </div>

      <Tabs defaultValue="profile" className="w-full">
        <TabsList className="grid w-full grid-cols-2 md:grid-cols-5 max-w-4xl mb-8">
          <TabsTrigger value="profile" className="gap-2">
            <User className="h-4 w-4" />
            Profile
          </TabsTrigger>
          <TabsTrigger value="ai-models" className="gap-2">
            <Cpu className="h-4 w-4" />
            AI Models
          </TabsTrigger>
          <TabsTrigger value="integrations" className="gap-2">
            <Link2 className="h-4 w-4" />
            Integrations
          </TabsTrigger>
          <TabsTrigger value="preferences" className="gap-2">
            <Sliders className="h-4 w-4" />
            Preferences
          </TabsTrigger>
          <TabsTrigger value="diagnostics" className="gap-2">
            <ShieldAlert className="h-4 w-4" />
            Diagnostics
          </TabsTrigger>
        </TabsList>

        {/* 1. Profile Tab Content */}
        <TabsContent value="profile">
          <div className="grid gap-6 md:grid-cols-3">
            <Card className="md:col-span-2">
              <CardHeader>
                <CardTitle>Profile Details</CardTitle>
                <CardDescription>
                  Modify your account identity and login credentials.
                </CardDescription>
              </CardHeader>
              <form onSubmit={handleProfileSave}>
                <CardContent className="space-y-4">
                  {profileSuccess && (
                    <div className="flex items-center gap-2 rounded-md bg-emerald-500/10 border border-emerald-500/20 p-3 text-sm text-emerald-400">
                      <Check className="h-4 w-4" />
                      {profileSuccess}
                    </div>
                  )}
                  {profileError && (
                    <div className="flex items-center gap-2 rounded-md bg-red-500/10 border border-red-500/20 p-3 text-sm text-red-400">
                      <AlertTriangle className="h-4 w-4" />
                      {profileError}
                    </div>
                  )}

                  <div className="grid gap-4 sm:grid-cols-2">
                    <div className="space-y-2">
                      <Label htmlFor="name">Full Name</Label>
                      <Input
                        id="name"
                        value={profileName}
                        onChange={(e) => setProfileName(e.target.value)}
                        required
                      />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="email">Email Address (Read-only)</Label>
                      <Input
                        id="email"
                        type="email"
                        value={user?.email || ""}
                        disabled
                        className="opacity-60 cursor-not-allowed"
                      />
                    </div>
                  </div>

                  <div className="border-t border-[var(--card-border)] pt-4 mt-6">
                    <h3 className="text-sm font-semibold text-[var(--foreground-color)] mb-4">Change Password</h3>
                    <div className="space-y-4">
                      <div className="space-y-2">
                        <Label htmlFor="curr-password">Current Password</Label>
                        <div className="relative">
                          <Input
                            id="curr-password"
                            type={showCurrentPassword ? "text" : "password"}
                            placeholder="••••••••"
                            value={currentPassword}
                            onChange={(e) => setCurrentPassword(e.target.value)}
                            className="pr-10"
                          />
                          <button
                            type="button"
                            onClick={() => setShowCurrentPassword(!showCurrentPassword)}
                            className="absolute right-3 top-1/2 -translate-y-1/2 text-[var(--sidebar-text-muted)] hover:text-[var(--foreground-color)]"
                          >
                            {showCurrentPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                          </button>
                        </div>
                      </div>
                      <div className="grid gap-4 sm:grid-cols-2">
                        <div className="space-y-2">
                          <Label htmlFor="new-password">New Password</Label>
                          <div className="relative">
                            <Input
                              id="new-password"
                              type={showNewPassword ? "text" : "password"}
                              placeholder="Min 8 characters"
                              value={newPassword}
                              onChange={(e) => setNewPassword(e.target.value)}
                              className="pr-10"
                            />
                            <button
                              type="button"
                              onClick={() => setShowNewPassword(!showNewPassword)}
                              className="absolute right-3 top-1/2 -translate-y-1/2 text-[var(--sidebar-text-muted)] hover:text-[var(--foreground-color)]"
                            >
                              {showNewPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                            </button>
                          </div>
                        </div>
                        <div className="space-y-2">
                          <Label htmlFor="confirm-password">Confirm New Password</Label>
                          <div className="relative">
                            <Input
                              id="confirm-password"
                              type={showConfirmPassword ? "text" : "password"}
                              placeholder="Re-type new password"
                              value={confirmPassword}
                              onChange={(e) => setConfirmPassword(e.target.value)}
                              className="pr-10"
                            />
                            <button
                              type="button"
                              onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                              className="absolute right-3 top-1/2 -translate-y-1/2 text-[var(--sidebar-text-muted)] hover:text-[var(--foreground-color)]"
                            >
                              {showConfirmPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                            </button>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                </CardContent>
                <CardFooter className="border-t border-[var(--card-border)] px-6 py-4 flex justify-end">
                  <Button type="submit">
                    Save Profile Changes
                  </Button>
                </CardFooter>
              </form>
            </Card>

            <Card className="h-fit">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <ShieldAlert className="h-4 w-4 text-[var(--primary)]" />
                  Account Security
                </CardTitle>
                <CardDescription>
                  Your registration status and security parameters.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4 text-sm text-[var(--foreground-color)]/90">
                <div className="flex justify-between border-b border-[var(--card-border)] pb-2">
                  <span className="text-[var(--sidebar-text-muted)]">Account status</span>
                  <Badge variant="success">Active</Badge>
                </div>
                <div className="flex justify-between border-b border-[var(--card-border)] pb-2">
                  <span className="text-[var(--sidebar-text-muted)]">Security Provider</span>
                  <span className="font-mono text-xs text-[var(--foreground-color)]">JWT Authorization</span>
                </div>
                <div className="flex justify-between border-b border-[var(--card-border)] pb-2">
                  <span className="text-[var(--sidebar-text-muted)]">Role</span>
                  <span className="font-semibold text-[var(--foreground-color)]">Owner</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-[var(--sidebar-text-muted)]">Member since</span>
                  <span className="text-[var(--foreground-color)]">
                    {user?.created_at ? new Date(user.created_at).toLocaleDateString() : "—"}
                  </span>
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* 2. AI Models Tab Content */}
        <TabsContent value="ai-models">
          <Card className="max-w-4xl border-[var(--card-border)] bg-[var(--card-bg)] shadow-2xl">
            <CardHeader className="border-b border-[var(--card-border)] pb-6 mb-6">
              <CardTitle className="flex items-center gap-2 text-white">
                <Cpu className="h-5 w-5 text-indigo-400" />
                LLM Provider Configurations
              </CardTitle>
              <CardDescription className="text-slate-400">
                Configure your API credentials for large language model providers. These keys are encrypted at rest and used securely server-side for chat agent execution.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              {aiModelsSuccess && (
                <div className="flex items-center gap-2 rounded-md bg-emerald-500/10 border border-emerald-500/20 p-3 text-sm text-emerald-400 animate-in fade-in">
                  <Check className="h-4 w-4" />
                  {aiModelsSuccess}
                </div>
              )}

              <div className="space-y-6">
                {/* 1. Groq key */}
                <div className="border border-white/5 bg-[#0d0d14]/40 p-5 rounded-2xl space-y-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <h4 className="text-sm font-semibold text-white">Groq AI Provider</h4>
                      <p className="text-xs text-slate-400 mt-1">Powers fast inference and agent reasoning routines.</p>
                    </div>
                    <div>
                      {llmStatus.groq.connected ? (
                        <Badge variant="success">✓ Configured</Badge>
                      ) : (
                        <Badge variant="secondary" className="opacity-60">Not configured</Badge>
                      )}
                    </div>
                  </div>
                  
                  {llmStatus.groq.error && (
                    <div className="p-2.5 bg-red-500/10 border border-red-500/20 rounded-xl text-xs text-red-400">
                      ⚠️ Connection Error: {llmStatus.groq.error}
                    </div>
                  )}

                  <div className="flex gap-3">
                    <div className="relative flex-1">
                      <Input
                        type={showLlmKeys.groq ? "text" : "password"}
                        placeholder={llmStatus.groq.connected ? "••••••••••••••••" : "gsk_..."}
                        value={groqKey}
                        onChange={(e) => setGroqKey(e.target.value)}
                        className="bg-[#08080c] border border-white/10 text-white rounded-xl focus:border-indigo-500"
                      />
                      <button
                        type="button"
                        onClick={() => setShowLlmKeys(prev => ({ ...prev, groq: !prev.groq }))}
                        className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300"
                      >
                        {showLlmKeys.groq ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                      </button>
                    </div>
                    <Button
                      onClick={() => handleSaveLlmKey("groq", groqKey)}
                      disabled={llmSaveLoading.groq || !groqKey.trim()}
                      className="bg-indigo-600 hover:bg-indigo-700 text-white font-bold rounded-xl"
                    >
                      {llmSaveLoading.groq ? "Saving..." : "Update"}
                    </Button>
                    {llmStatus.groq.connected && (
                      <Button
                        variant="destructive"
                        onClick={() => handleDeleteLlmKey("groq")}
                        className="bg-rose-500/10 hover:bg-rose-650 border border-rose-500/15 text-rose-450 hover:text-white rounded-xl"
                      >
                        Remove
                      </Button>
                    )}
                  </div>
                </div>

                {/* 2. Nvidia NIM key */}
                <div className="border border-white/5 bg-[#0d0d14]/40 p-5 rounded-2xl space-y-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <h4 className="text-sm font-semibold text-white">Nvidia NIM</h4>
                      <p className="text-xs text-slate-400 mt-1">Powers specialized large-context Llama and Qwen models.</p>
                    </div>
                    <div>
                      {llmStatus.nvidia.connected ? (
                        <Badge variant="success">✓ Configured</Badge>
                      ) : (
                        <Badge variant="secondary" className="opacity-60">Not configured</Badge>
                      )}
                    </div>
                  </div>
                  
                  {llmStatus.nvidia.error && (
                    <div className="p-2.5 bg-red-500/10 border border-red-500/20 rounded-xl text-xs text-red-400">
                      ⚠️ Connection Error: {llmStatus.nvidia.error}
                    </div>
                  )}

                  <div className="flex gap-3">
                    <div className="relative flex-1">
                      <Input
                        type={showLlmKeys.nvidia ? "text" : "password"}
                        placeholder={llmStatus.nvidia.connected ? "••••••••••••••••" : "nvapi-..."}
                        value={nvidiaKey}
                        onChange={(e) => setNvidiaKey(e.target.value)}
                        className="bg-[#08080c] border border-white/10 text-white rounded-xl focus:border-indigo-500"
                      />
                      <button
                        type="button"
                        onClick={() => setShowLlmKeys(prev => ({ ...prev, nvidia: !prev.nvidia }))}
                        className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300"
                      >
                        {showLlmKeys.nvidia ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                      </button>
                    </div>
                    <Button
                      onClick={() => handleSaveLlmKey("nvidia", nvidiaKey)}
                      disabled={llmSaveLoading.nvidia || !nvidiaKey.trim()}
                      className="bg-indigo-600 hover:bg-indigo-700 text-white font-bold rounded-xl"
                    >
                      {llmSaveLoading.nvidia ? "Saving..." : "Update"}
                    </Button>
                    {llmStatus.nvidia.connected && (
                      <Button
                        variant="destructive"
                        onClick={() => handleDeleteLlmKey("nvidia")}
                        className="bg-rose-500/10 hover:bg-rose-650 border border-rose-500/15 text-rose-450 hover:text-white rounded-xl"
                      >
                        Remove
                      </Button>
                    )}
                  </div>
                </div>

                {/* 3. Xiaomi key */}
                <div className="border border-white/5 bg-[#0d0d14]/40 p-5 rounded-2xl space-y-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <h4 className="text-sm font-semibold text-white">Xiaomi MiMo LLM</h4>
                      <p className="text-xs text-slate-400 mt-1">Powers specialized MiMo model integrations.</p>
                    </div>
                    <div>
                      {llmStatus.xiaomi.connected ? (
                        <Badge variant="success">✓ Configured</Badge>
                      ) : (
                        <Badge variant="secondary" className="opacity-60">Not configured</Badge>
                      )}
                    </div>
                  </div>
                  
                  {llmStatus.xiaomi.error && (
                    <div className="p-2.5 bg-red-500/10 border border-red-500/20 rounded-xl text-xs text-red-400">
                      ⚠️ Connection Error: {llmStatus.xiaomi.error}
                    </div>
                  )}

                  <div className="flex gap-3">
                    <div className="relative flex-1">
                      <Input
                        type={showLlmKeys.xiaomi ? "text" : "password"}
                        placeholder={llmStatus.xiaomi.connected ? "••••••••••••••••" : "xiaomi-api-key..."}
                        value={xiaomiKey}
                        onChange={(e) => setXiaomiKey(e.target.value)}
                        className="bg-[#08080c] border border-white/10 text-white rounded-xl focus:border-indigo-500"
                      />
                      <button
                        type="button"
                        onClick={() => setShowLlmKeys(prev => ({ ...prev, xiaomi: !prev.xiaomi }))}
                        className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300"
                      >
                        {showLlmKeys.xiaomi ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                      </button>
                    </div>
                    <Button
                      onClick={() => handleSaveLlmKey("xiaomi", xiaomiKey)}
                      disabled={llmSaveLoading.xiaomi || !xiaomiKey.trim()}
                      className="bg-indigo-600 hover:bg-indigo-700 text-white font-bold rounded-xl"
                    >
                      {llmSaveLoading.xiaomi ? "Saving..." : "Update"}
                    </Button>
                    {llmStatus.xiaomi.connected && (
                      <Button
                        variant="destructive"
                        onClick={() => handleDeleteLlmKey("xiaomi")}
                        className="bg-rose-500/10 hover:bg-rose-650 border border-rose-500/15 text-rose-450 hover:text-white rounded-xl"
                      >
                        Remove
                      </Button>
                    )}
                  </div>
                </div>

                {/* 4. Gemini key */}
                <div className="border border-white/5 bg-[#0d0d14]/40 p-5 rounded-2xl space-y-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <h4 className="text-sm font-semibold text-white">Google Gemini</h4>
                      <p className="text-xs text-slate-400 mt-1">Powers advanced Gemma-4 model integrations.</p>
                    </div>
                    <div>
                      {llmStatus.gemini?.connected ? (
                        <Badge variant="success">✓ Configured</Badge>
                      ) : (
                        <Badge variant="secondary" className="opacity-60">Not configured</Badge>
                      )}
                    </div>
                  </div>
                  
                  {llmStatus.gemini?.error && (
                    <div className="p-2.5 bg-red-500/10 border border-red-500/20 rounded-xl text-xs text-red-400">
                      ⚠️ Connection Error: {llmStatus.gemini.error}
                    </div>
                  )}

                  <div className="flex gap-3">
                    <div className="relative flex-1">
                      <Input
                        type={showLlmKeys.gemini ? "text" : "password"}
                        placeholder={llmStatus.gemini?.connected ? "••••••••••••••••" : "gemini-api-key..."}
                        value={geminiKey}
                        onChange={(e) => setGeminiKey(e.target.value)}
                        className="bg-[#08080c] border border-white/10 text-white rounded-xl focus:border-indigo-500"
                      />
                      <button
                        type="button"
                        onClick={() => setShowLlmKeys(prev => ({ ...prev, gemini: !prev.gemini }))}
                        className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300"
                      >
                        {showLlmKeys.gemini ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                      </button>
                    </div>
                    <Button
                      onClick={() => handleSaveLlmKey("gemini", geminiKey)}
                      disabled={llmSaveLoading.gemini || !geminiKey.trim()}
                      className="bg-indigo-600 hover:bg-indigo-700 text-white font-bold rounded-xl"
                    >
                      {llmSaveLoading.gemini ? "Saving..." : "Update"}
                    </Button>
                    {llmStatus.gemini?.connected && (
                      <Button
                        variant="destructive"
                        onClick={() => handleDeleteLlmKey("gemini")}
                        className="bg-rose-500/10 hover:bg-rose-650 border border-rose-500/15 text-rose-450 hover:text-white rounded-xl"
                      >
                        Remove
                      </Button>
                    )}
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* 3. Integrations Tab Content */}
        <TabsContent value="integrations">
          <div className="space-y-8">
            {/* Gmail accounts - preserved from original */}
            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-3">
                <div>
                  <CardTitle className="flex items-center gap-2">
                    <Mail className="h-5 w-5 text-[var(--primary)]" />
                    Gmail / Google Workspace Senders
                  </CardTitle>
                  <CardDescription className="mt-1">
                    Manage connected email accounts used for automated campaigns.
                  </CardDescription>
                </div>
                <Button
                  onClick={handleConnectGmail}
                  disabled={gmailConnecting}
                  variant="outline"
                  size="sm"
                >
                  {gmailConnecting ? "Loading OAuth..." : "+ Add Sender"}
                </Button>
              </CardHeader>
              <CardContent>
                {gmailLoading ? (
                  <div className="py-4 text-center text-xs text-[var(--sidebar-text-muted)] animate-pulse">
                    Retrieving connected accounts...
                  </div>
                ) : gmailAccounts.length === 0 ? (
                  <div className="py-6 border border-dashed border-[var(--card-border)] rounded-lg text-center">
                    <Link2Off className="h-8 w-8 mx-auto mb-2 text-[var(--sidebar-text-muted)]" />
                    <p className="text-sm font-semibold text-[var(--foreground-color)]">No active senders connected</p>
                    <p className="text-xs text-[var(--sidebar-text-muted)] mt-1 max-w-sm mx-auto">
                      Authenticate with Google OAuth to authorize outreach campaigns to send emails.
                    </p>
                  </div>
                ) : (
                  <div className="space-y-3">
                    {gmailAccounts.map((account) => (
                      <div
                        key={account.id}
                        className="flex items-center justify-between border border-[var(--card-border)] bg-[var(--sidebar-toggle-bg)]/40 p-4 rounded-lg hover:border-[var(--card-border)]/80 transition-colors"
                      >
                        <div className="flex items-center gap-3">
                          <div className="h-9 w-9 rounded-full bg-[var(--primary)]/10 border border-[var(--primary)]/25 flex items-center justify-center text-[var(--primary)]">
                            <Mail className="h-4 w-4" />
                          </div>
                          <div>
                            <p className="text-sm font-semibold text-[var(--foreground-color)]">{account.email}</p>
                            <div className="flex gap-2 items-center mt-0.5">
                              <Badge variant={account.is_active ? "success" : "warning"} className="scale-90 origin-left">
                                {account.is_active ? "Active" : "Paused"}
                              </Badge>
                              <span className="text-[10px] text-[var(--sidebar-text-muted)]">ID: {account.id}</span>
                            </div>
                          </div>
                        </div>
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => handleDisconnectGmail(account.id)}
                          className="text-red-400 hover:text-red-300 hover:bg-red-500/10"
                          title="Disconnect Account"
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>

            {/* New: Integrations Center (DB-backed encrypted credentials) */}
            <IntegrationsCenter />
          </div>
        </TabsContent>



        {/* 4. Preferences Tab Content */}
        <TabsContent value="preferences">
          <Card className="max-w-4xl">
            <CardHeader>
              <CardTitle>System and Outreach Preferences</CardTitle>
              <CardDescription>
                Define safety rails, copy guidelines, and time scheduling behavior for all campaigns.
              </CardDescription>
            </CardHeader>
            <form onSubmit={handlePreferencesSave}>
              <CardContent className="space-y-6">
                {preferencesSuccess && (
                  <div className="flex items-center gap-2 rounded-md bg-emerald-500/10 border border-emerald-500/20 p-3 text-sm text-emerald-400">
                    <Check className="h-4 w-4" />
                    {preferencesSuccess}
                  </div>
                )}

                <div className="grid gap-6 sm:grid-cols-2">
                  {/* Default Tone Selector */}
                  <div className="space-y-2">
                    <Label htmlFor="default-tone" className="flex items-center gap-1">
                      <Volume2 className="h-4 w-4 text-[var(--primary)]" />
                      Default Outreach Tone
                    </Label>
                    <select
                      id="default-tone"
                      value={preferences.defaultTone}
                      onChange={(e) => setPreferences({ ...preferences, defaultTone: e.target.value })}
                      className={selectStyleClass}
                    >
                      <option value="Professional" style={{ background: 'var(--card-bg)', color: 'var(--foreground-color)' }}>Professional (Polite, direct, ROI-focused)</option>
                      <option value="Friendly" style={{ background: 'var(--card-bg)', color: 'var(--foreground-color)' }}>Friendly (Approachable, connection-focused)</option>
                      <option value="Creative" style={{ background: 'var(--card-bg)', color: 'var(--foreground-color)' }}>Creative (Intriguing, narrative hooks)</option>
                      <option value="Direct" style={{ background: 'var(--card-bg)', color: 'var(--foreground-color)' }}>Direct (Short, simple value propositons)</option>
                      <option value="Casual" style={{ background: 'var(--card-bg)', color: 'var(--foreground-color)' }}>Casual (Semi-formal, conversational)</option>
                    </select>
                  </div>

                  {/* Timezone Selector */}
                  <div className="space-y-2">
                    <Label htmlFor="timezone" className="flex items-center gap-1">
                      <Clock className="h-4 w-4 text-[var(--primary)]" />
                      System Timezone
                    </Label>
                    <select
                      id="timezone"
                      value={preferences.timezone}
                      onChange={(e) => setPreferences({ ...preferences, timezone: e.target.value })}
                      className={selectStyleClass}
                    >
                      <option value="America/New_York" style={{ background: 'var(--card-bg)', color: 'var(--foreground-color)' }}>Eastern Time (US & Canada)</option>
                      <option value="America/Los_Angeles" style={{ background: 'var(--card-bg)', color: 'var(--foreground-color)' }}>Pacific Time (US & Canada)</option>
                      <option value="Europe/London" style={{ background: 'var(--card-bg)', color: 'var(--foreground-color)' }}>Greenwich Mean Time (London)</option>
                      <option value="Asia/Kolkata" style={{ background: 'var(--card-bg)', color: 'var(--foreground-color)' }}>India Standard Time (IST)</option>
                      <option value="Asia/Singapore" style={{ background: 'var(--card-bg)', color: 'var(--foreground-color)' }}>Singapore Standard Time (SGT)</option>
                      <option value="UTC" style={{ background: 'var(--card-bg)', color: 'var(--foreground-color)' }}>Universal Coordinated Time (UTC)</option>
                    </select>
                  </div>

                  {/* Daily Limits */}
                  <div className="space-y-2">
                    <Label htmlFor="daily-limit">Daily Send Limit (per email account)</Label>
                    <Input
                      id="daily-limit"
                      type="number"
                      min={5}
                      max={200}
                      value={preferences.dailyLimit}
                      onChange={(e) => setPreferences({ ...preferences, dailyLimit: parseInt(e.target.value) || 50 })}
                    />
                    <p className="text-[10px] text-[var(--sidebar-text-muted)]">
                      Keeps daily send limits safe to avoid Gmail spam filters flag triggers (recommended: under 50).
                    </p>
                  </div>

                  {/* Message spacing */}
                  <div className="space-y-2">
                    <Label htmlFor="spacing-delay">Min Send Intermission Spacing (Seconds)</Label>
                    <Input
                      id="spacing-delay"
                      type="number"
                      min={10}
                      max={600}
                      value={preferences.spacingDelay}
                      onChange={(e) => setPreferences({ ...preferences, spacingDelay: parseInt(e.target.value) || 30 })}
                    />
                    <p className="text-[10px] text-[var(--sidebar-text-muted)]">
                      Minimum queue pause time between sending sequential campaign outreach emails.
                    </p>
                  </div>
                </div>

                {/* Spacing Offset toggle */}
                <div className="flex items-center justify-between border-t border-[var(--card-border)] pt-4">
                  <div className="space-y-0.5">
                    <Label htmlFor="offset-toggle" className="text-[var(--foreground-color)]">Human-like Random Delays</Label>
                    <p className="text-xs text-[var(--sidebar-text-muted)] max-w-lg">
                      Applies a random jitter (+/- 5s to 15s) to the intermission spacing delay to replicate manual outbound behavior.
                    </p>
                  </div>
                  <button
                    id="offset-toggle"
                    type="button"
                    onClick={() => setPreferences({ ...preferences, randomOffset: !preferences.randomOffset })}
                    className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-[var(--primary)] ${
                      preferences.randomOffset ? "bg-[var(--primary)]" : "bg-[var(--sidebar-toggle-bg)]"
                    }`}
                  >
                    <span
                      className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${
                        preferences.randomOffset ? "translate-x-5" : "translate-x-0"
                      }`}
                    />
                  </button>
                </div>

                {/* Focus guidelines instructions */}
                <div className="space-y-2 border-t border-[var(--card-border)] pt-4">
                  <Label htmlFor="keywords">Outbound copywriting restrictions and focus guidelines</Label>
                  <p className="text-xs text-[var(--sidebar-text-muted)]">
                    Add custom constraints injected into the email generation prompts.
                  </p>
                  <textarea
                    id="keywords"
                    rows={4}
                    value={preferences.focusKeywords}
                    onChange={(e) => setPreferences({ ...preferences, focusKeywords: e.target.value })}
                    placeholder="Example: Keep email length strictly under 100 words. Avoid using salesy buzzwords like 'synergy' or 'disrupt'. Ensure every pitch ends with a clear, low-friction scheduling CTA."
                    className={textareaStyleClass}
                  />
                </div>
              </CardContent>
              <CardFooter className="border-t border-[var(--card-border)] px-6 py-4 flex justify-end">
                <Button type="submit">
                  Save System Preferences
                </Button>
              </CardFooter>
            </form>
          </Card>
        </TabsContent>

        {/* 5. Diagnostics Tab Content */}
        <TabsContent value="diagnostics" className="space-y-6">
          <div className="grid gap-6 md:grid-cols-2">
            {/* Operational Health */}
            <Card>
              <CardHeader>
                <div className="flex justify-between items-center">
                  <div>
                    <CardTitle>Operational Infrastructure Health</CardTitle>
                    <CardDescription>Real-time status of backend service dependencies.</CardDescription>
                  </div>
                  <Button variant="outline" size="sm" onClick={fetchHealthStatus} disabled={healthLoading}>
                    {healthLoading ? "Refreshing..." : "Refresh Health"}
                  </Button>
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                {healthStatus ? (
                  <div className="space-y-3">
                    {Object.entries(healthStatus).map(([service, info]: [string, any]) => {
                      const isHealthy = info.status === "Healthy" || info.status === "Available" || info.status === "Connected";
                      return (
                        <div key={service} className="flex items-center justify-between p-3 rounded-lg border border-[var(--card-border)] bg-[var(--card-bg)]/50">
                          <div className="flex flex-col">
                            <span className="text-sm font-semibold capitalize">{service.replace("_", " ")}</span>
                            <span className="text-xs text-[var(--sidebar-text-muted)]">{info.message}</span>
                          </div>
                          <Badge variant={isHealthy ? "default" : "destructive"}>
                            {info.status}
                          </Badge>
                        </div>
                      );
                    })}
                  </div>
                ) : (
                  <p className="text-sm text-[var(--sidebar-text-muted)] text-center py-4">No health data available. Click refresh.</p>
                )}
              </CardContent>
            </Card>

            {/* Background Jobs */}
            <Card>
              <CardHeader>
                <div className="flex justify-between items-center">
                  <div>
                    <CardTitle>Background Job Engine</CardTitle>
                    <CardDescription>Scheduled outreach queues and Celery task execution.</CardDescription>
                  </div>
                  <Button variant="outline" size="sm" onClick={fetchJobStats} disabled={jobStatsLoading}>
                    {jobStatsLoading ? "Refreshing..." : "Refresh Queue"}
                  </Button>
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                {jobStats ? (
                  <div className="space-y-4">
                    <div className="grid grid-cols-4 gap-4 text-center">
                      <div className="p-3 rounded-lg border border-[var(--card-border)] bg-[var(--card-bg)]/50">
                        <div className="text-xl font-bold text-blue-400">{jobStats.summary?.pending || 0}</div>
                        <div className="text-[10px] text-[var(--sidebar-text-muted)] capitalize">Pending</div>
                      </div>
                      <div className="p-3 rounded-lg border border-[var(--card-border)] bg-[var(--card-bg)]/50">
                        <div className="text-xl font-bold text-emerald-400">{jobStats.summary?.executed || 0}</div>
                        <div className="text-[10px] text-[var(--sidebar-text-muted)] capitalize">Executed</div>
                      </div>
                      <div className="p-3 rounded-lg border border-[var(--card-border)] bg-[var(--card-bg)]/50">
                        <div className="text-xl font-bold text-amber-400">{jobStats.summary?.running || 0}</div>
                        <div className="text-[10px] text-[var(--sidebar-text-muted)] capitalize">Running</div>
                      </div>
                      <div className="p-3 rounded-lg border border-[var(--card-border)] bg-[var(--card-bg)]/50">
                        <div className="text-xl font-bold text-rose-400">{jobStats.summary?.failed || 0}</div>
                        <div className="text-[10px] text-[var(--sidebar-text-muted)] capitalize">Failed</div>
                      </div>
                    </div>

                    <div className="space-y-2">
                      <h4 className="text-xs font-semibold text-[var(--sidebar-text-muted)] uppercase tracking-wider">Recent Executed Tasks</h4>
                      <div className="max-h-[160px] overflow-y-auto space-y-1.5 pr-1">
                        {jobStats.recent_tasks?.length > 0 ? (
                          jobStats.recent_tasks.map((task: any, idx: number) => (
                            <div key={idx} className="flex justify-between items-center text-xs p-2 rounded border border-[var(--card-border)]/50 bg-[var(--card-bg)]/20">
                              <span className="font-mono text-[10px] truncate max-w-[120px]">{task.campaign_id}</span>
                              <Badge variant={task.status === "executed" ? "default" : task.status === "failed" ? "destructive" : "secondary"}>
                                {task.status}
                              </Badge>
                            </div>
                          ))
                        ) : (
                          <div className="text-center text-xs text-[var(--sidebar-text-muted)] py-4">No recent task logs.</div>
                        )}
                      </div>
                    </div>
                  </div>
                ) : (
                  <p className="text-sm text-[var(--sidebar-text-muted)] text-center py-4">No queue stats available. Click refresh.</p>
                )}
              </CardContent>
            </Card>
          </div>

          <div className="grid gap-6 md:grid-cols-2">
            {/* Backup & Restore */}
            <Card>
              <CardHeader>
                <CardTitle>System Backup & Restore</CardTitle>
                <CardDescription>Export your setup metadata or import them to restore campaign data.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {restoreSuccess && (
                  <div className="flex items-center gap-2 rounded-md bg-emerald-500/10 border border-emerald-500/20 p-3 text-sm text-emerald-400">
                    <Check className="h-4 w-4" />
                    {restoreSuccess}
                  </div>
                )}
                {restoreError && (
                  <div className="flex items-center gap-2 rounded-md bg-red-500/10 border border-red-500/20 p-3 text-sm text-red-400">
                    <AlertTriangle className="h-4 w-4" />
                    {restoreError}
                  </div>
                )}

                <div className="flex flex-col gap-4">
                  <div className="space-y-2">
                    <Label>Database Operations</Label>
                    <Button onClick={handleExportBackup} className="w-full flex items-center justify-center gap-2">
                      <DatabaseBackup className="h-4 w-4" />
                      Export Outreach Backup JSON
                    </Button>
                    <p className="text-[10px] text-[var(--sidebar-text-muted)]">
                      Downloads your campaigns, leads, and custom copywriting configuration.
                    </p>
                  </div>

                  <form onSubmit={handleRestoreBackup} className="space-y-2 border-t border-[var(--card-border)] pt-4">
                    <Label htmlFor="restore-json">Restore from Backup JSON</Label>
                    <textarea
                      id="restore-json"
                      rows={5}
                      value={restoreJson}
                      onChange={(e) => setRestoreJson(e.target.value)}
                      placeholder="Paste exported backup JSON text here..."
                      className={textareaStyleClass}
                    />
                    <Button type="submit" variant="secondary" className="w-full">
                      Import and Restore Data
                    </Button>
                  </form>
                </div>
              </CardContent>
            </Card>

            {/* Audit Log Trail */}
            <Card>
              <CardHeader>
                <div className="flex justify-between items-center">
                  <div>
                    <CardTitle>Platform Audit Logs</CardTitle>
                    <CardDescription>Historical security actions audit log trail.</CardDescription>
                  </div>
                  <Button variant="outline" size="sm" onClick={fetchAuditLogs} disabled={auditLogsLoading}>
                    {auditLogsLoading ? "Refreshing..." : "Refresh Logs"}
                  </Button>
                </div>
              </CardHeader>
              <CardContent>
                <div className="max-h-[360px] overflow-y-auto space-y-2 pr-1">
                  {auditLogs.length > 0 ? (
                    auditLogs.map((log: any, idx: number) => (
                      <div key={idx} className="p-2.5 rounded border border-[var(--card-border)] bg-[var(--card-bg)]/30 space-y-1 text-xs">
                        <div className="flex justify-between font-semibold">
                          <span className="text-blue-400">{log.action}</span>
                          <span className="text-[10px] text-[var(--sidebar-text-muted)]">{new Date(log.timestamp).toLocaleString()}</span>
                        </div>
                        <div className="flex justify-between text-[10px] text-[var(--sidebar-text-muted)]">
                          <span>User: {log.user_id}</span>
                          <span>IP: {log.client_ip}</span>
                        </div>
                        {log.resource && (
                          <div className="text-[10px] truncate">
                            <span className="text-[var(--sidebar-text-muted)]">Resource: </span>
                            <span className="font-mono">{log.resource}</span>
                          </div>
                        )}
                      </div>
                    ))
                  ) : (
                    <div className="text-center text-xs text-[var(--sidebar-text-muted)] py-8">No audit log records found.</div>
                  )}
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}