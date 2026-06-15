"use client";

import { useState, useEffect } from "react";
import { useAuthStore } from "@/store/auth-store";
import { getGmailAccounts, getGmailAuthUrl, disconnectGmailAccount } from "@/services/gmail-api";
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from "@/components/ui/card";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Label } from "@/components/ui/label";
import { 
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

  // States for AI Models Tab
  const [aiModels, setAiModels] = useState<AIModelsConfig>({
    researchModel: "llama-3.3-70b-versatile",
    emailModel: "llama-3.3-70b-versatile",
    classifierModel: "llama-3.3-70b-versatile",
    routerMode: "dynamic",
    similarityThreshold: 0.7,
    recencyWeight: 0.3,
  });
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

  // Load Gmail accounts & LocalStorage Settings on Mount
  useEffect(() => {
    loadGmail();

    // Load AI models settings from localStorage
    const savedAiModels = localStorage.getItem("outreach_settings_ai_models");
    if (savedAiModels) {
      try {
        setAiModels((prev) => ({ ...prev, ...JSON.parse(savedAiModels) }));
      } catch (err) {
        console.error("Error loading saved AI models:", err);
      }
    }

    // Load API key overrides from localStorage
    const savedApiKeys = localStorage.getItem("outreach_settings_api_keys");
    if (savedApiKeys) {
      try {
        setApiKeys((prev) => ({ ...prev, ...JSON.parse(savedApiKeys) }));
      } catch (err) {
        console.error("Error loading saved API keys overrides:", err);
      }
    }

    // Load preferences settings from localStorage
    const savedPreferences = localStorage.getItem("outreach_settings_preferences");
    if (savedPreferences) {
      try {
        setPreferences((prev) => ({ ...prev, ...JSON.parse(savedPreferences) }));
      } catch (err) {
        console.error("Error loading saved preferences:", err);
      }
    }
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

  const handleAiModelsSave = (e: React.FormEvent) => {
    e.preventDefault();
    localStorage.setItem("outreach_settings_ai_models", JSON.stringify(aiModels));
    setAiModelsSuccess("AI model configurations updated successfully!");
    setTimeout(() => setAiModelsSuccess(""), 3000);
  };

  const handleApiKeysSave = (e: React.FormEvent) => {
    e.preventDefault();
    localStorage.setItem("outreach_settings_api_keys", JSON.stringify(apiKeys));
    setApiKeysSuccess("API overrides updated successfully!");
    setTimeout(() => setApiKeysSuccess(""), 3000);
  };

  const handlePreferencesSave = (e: React.FormEvent) => {
    e.preventDefault();
    localStorage.setItem("outreach_settings_preferences", JSON.stringify(preferences));
    setPreferencesSuccess("System preferences updated successfully!");
    setTimeout(() => setPreferencesSuccess(""), 3000);
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
        <TabsList className="grid w-full grid-cols-2 md:grid-cols-4 max-w-3xl mb-8">
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
          <Card className="max-w-4xl">
            <CardHeader>
              <CardTitle>AI Agents and LLM Routing</CardTitle>
              <CardDescription>
                Assign models to specialized roles. All models run on Groq Server infrastructure.
              </CardDescription>
            </CardHeader>
            <form onSubmit={handleAiModelsSave}>
              <CardContent className="space-y-6">
                {aiModelsSuccess && (
                  <div className="flex items-center gap-2 rounded-md bg-emerald-500/10 border border-emerald-500/20 p-3 text-sm text-emerald-400">
                    <Check className="h-4 w-4" />
                    {aiModelsSuccess}
                  </div>
                )}

                <div className="grid gap-6 sm:grid-cols-2">
                  {/* Research Model Selector */}
                  <div className="space-y-2">
                    <Label htmlFor="research-model">Research Agent Model</Label>
                    <p className="text-xs text-[var(--sidebar-text-muted)] mb-1">
                      Powers background Tavily and Firecrawl deep research.
                    </p>
                    <select
                      id="research-model"
                      value={aiModels.researchModel}
                      onChange={(e) => setAiModels({ ...aiModels, researchModel: e.target.value })}
                      className={selectStyleClass}
                    >
                      <option value="llama-3.3-70b-versatile" style={{ background: 'var(--card-bg)', color: 'var(--foreground-color)' }}>Llama 3.3 70B Versatile (Recommended)</option>
                      <option value="llama-3.1-8b-instant" style={{ background: 'var(--card-bg)', color: 'var(--foreground-color)' }}>Llama 3.1 8B Instant (Fast / Cost-optimized)</option>
                      <option value="mixtral-8x7b-32768" style={{ background: 'var(--card-bg)', color: 'var(--foreground-color)' }}>Mixtral 8x7B (High-Context Open Source)</option>
                      <option value="deepseek-r1-distill-llama-70b" style={{ background: 'var(--card-bg)', color: 'var(--foreground-color)' }}>DeepSeek R1 Distill 70B (Complex Reasoning)</option>
                    </select>
                  </div>

                  {/* Copywriting Model Selector */}
                  <div className="space-y-2">
                    <Label htmlFor="email-model">Copywriting & Sequencing Model</Label>
                    <p className="text-xs text-[var(--sidebar-text-muted)] mb-1">
                      Powers personalized email template drafts and RAG personalization hooks.
                    </p>
                    <select
                      id="email-model"
                      value={aiModels.emailModel}
                      onChange={(e) => setAiModels({ ...aiModels, emailModel: e.target.value })}
                      className={selectStyleClass}
                    >
                      <option value="llama-3.3-70b-versatile" style={{ background: 'var(--card-bg)', color: 'var(--foreground-color)' }}>Llama 3.3 70B Versatile (Recommended)</option>
                      <option value="llama-3.1-70b-specdec" style={{ background: 'var(--card-bg)', color: 'var(--foreground-color)' }}>Llama 3.1 70B Speculative (High Speed)</option>
                      <option value="mixtral-8x7b-32768" style={{ background: 'var(--card-bg)', color: 'var(--foreground-color)' }}>Mixtral 8x7B (Natural Context Flow)</option>
                    </select>
                  </div>

                  {/* Classifier Model Selector */}
                  <div className="space-y-2">
                    <Label htmlFor="classifier-model">Reply Intent Classification Model</Label>
                    <p className="text-xs text-[var(--sidebar-text-muted)] mb-1">
                      Analyzes incoming responses and assigns intent (referral, demo request, interested, OOO).
                    </p>
                    <select
                      id="classifier-model"
                      value={aiModels.classifierModel}
                      onChange={(e) => setAiModels({ ...aiModels, classifierModel: e.target.value })}
                      className={selectStyleClass}
                    >
                      <option value="llama-3.3-70b-versatile" style={{ background: 'var(--card-bg)', color: 'var(--foreground-color)' }}>Llama 3.3 70B Versatile (Standard)</option>
                      <option value="llama-3.1-8b-instant" style={{ background: 'var(--card-bg)', color: 'var(--foreground-color)' }}>Llama 3.1 8B Instant (Ultra-fast / Accurate)</option>
                    </select>
                  </div>

                  {/* Router Mode Selector */}
                  <div className="space-y-2">
                    <Label htmlFor="router-mode">Multi-LLM Router Mode</Label>
                    <p className="text-xs text-[var(--sidebar-text-muted)] mb-1">
                      Determine how API routing handles Groq token limits and speed fallbacks.
                    </p>
                    <select
                      id="router-mode"
                      value={aiModels.routerMode}
                      onChange={(e) => setAiModels({ ...aiModels, routerMode: e.target.value })}
                      className={selectStyleClass}
                    >
                      <option value="dynamic" style={{ background: 'var(--card-bg)', color: 'var(--foreground-color)' }}>Dynamic Routing (Auto-recovery & Failovers)</option>
                      <option value="cost" style={{ background: 'var(--card-bg)', color: 'var(--foreground-color)' }}>Cost Optimized (Prioritizes 8B Models)</option>
                      <option value="quality" style={{ background: 'var(--card-bg)', color: 'var(--foreground-color)' }}>Quality Optimized (Strictly 70B Models)</option>
                    </select>
                  </div>
                </div>

                <div className="border-t border-[var(--card-border)] pt-6 space-y-4">
                  <h3 className="text-sm font-semibold text-[var(--foreground-color)] flex items-center gap-2">
                    <Layers className="h-4 w-4 text-[var(--primary)]" />
                    Knowledge Retrieval & Embeddings RAG Configurations
                  </h3>
                  <p className="text-xs text-[var(--sidebar-text-muted)]">
                    Fine-tune similarity queries against the local Qdrant Vector database collections (leads, signals, emails).
                  </p>

                  <div className="grid gap-4 sm:grid-cols-2">
                    <div className="space-y-2">
                      <div className="flex justify-between text-xs text-[var(--foreground-color)]/90">
                        <span>Similarity Score Threshold</span>
                        <span>{aiModels.similarityThreshold}</span>
                      </div>
                      <input
                        type="range"
                        min="0.1"
                        max="0.9"
                        step="0.05"
                        value={aiModels.similarityThreshold}
                        onChange={(e) => setAiModels({ ...aiModels, similarityThreshold: parseFloat(e.target.value) })}
                        className="w-full h-1 bg-[var(--sidebar-toggle-bg)] rounded-lg appearance-none cursor-pointer accent-[var(--primary)]"
                      />
                      <p className="text-[10px] text-[var(--sidebar-text-muted)]">
                        Minimum cosine similarity match required to pull memories. Higher values prevent irrelevant context.
                      </p>
                    </div>

                    <div className="space-y-2">
                      <div className="flex justify-between text-xs text-[var(--foreground-color)]/90">
                        <span>Recency decay boost weight</span>
                        <span>{aiModels.recencyWeight}</span>
                      </div>
                      <input
                        type="range"
                        min="0.0"
                        max="1.0"
                        step="0.05"
                        value={aiModels.recencyWeight}
                        onChange={(e) => setAiModels({ ...aiModels, recencyWeight: parseFloat(e.target.value) })}
                        className="w-full h-1 bg-[var(--sidebar-toggle-bg)] rounded-lg appearance-none cursor-pointer accent-[var(--primary)]"
                      />
                      <p className="text-[10px] text-[var(--sidebar-text-muted)]">
                        Weights newer emails & signals higher. 0.0 relies strictly on semantic similarity.
                      </p>
                    </div>
                  </div>

                  <div className="rounded-lg bg-[var(--primary)]/5 border border-[var(--primary)]/10 p-4 flex gap-3 text-xs text-[var(--foreground-color)]/90">
                    <Database className="h-5 w-5 text-[var(--primary)] shrink-0 mt-0.5" />
                    <div>
                      <p className="font-semibold text-[var(--foreground-color)] mb-0.5">Embeddings engine specifications</p>
                      <p className="leading-relaxed">
                        Currently using local FastEmbed generation with the <span className="font-mono text-[var(--primary)]">BAAI/bge-small-en-v1.5</span> model. This yields a dense 384-dimensional vector, keeping Qdrant indexing extremely fast, fully local, and free from external OpenAI/Cohere costs.
                      </p>
                    </div>
                  </div>
                </div>
              </CardContent>
              <CardFooter className="border-t border-[var(--card-border)] px-6 py-4 flex justify-end">
                <Button type="submit">
                  Update Agent Config
                </Button>
              </CardFooter>
            </form>
          </Card>
        </TabsContent>

        {/* 3. Integrations Tab Content */}
        <TabsContent value="integrations">
          <div className="grid gap-6 lg:grid-cols-3">
            {/* Left side: API Integrations */}
            <div className="lg:col-span-2 space-y-6">
              {/* Gmail Connection */}
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

              {/* API Overrides */}
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Key className="h-5 w-5 text-[var(--primary)]" />
                    API Integrations Overrides
                  </CardTitle>
                  <CardDescription>
                    Custom client-side key overrides. If blank, the platform defaults to server-side keys configured in the backend's <span className="font-mono text-[var(--primary)]">.env</span> file.
                  </CardDescription>
                </CardHeader>
                <form onSubmit={handleApiKeysSave}>
                  <CardContent className="space-y-4">
                    {apiKeysSuccess && (
                      <div className="flex items-center gap-2 rounded-md bg-emerald-500/10 border border-emerald-500/20 p-3 text-sm text-emerald-400">
                        <Check className="h-4 w-4" />
                        {apiKeysSuccess}
                      </div>
                    )}

                    {/* Apollo Key */}
                    <div className="space-y-1.5">
                      <div className="flex justify-between items-center">
                        <Label htmlFor="apollo" className="flex items-center gap-1.5">
                          Apollo.io API Key
                          {apiKeys.apolloApiKey ? (
                            <Badge variant="success" className="scale-75 origin-left">Custom Override</Badge>
                          ) : (
                            <Badge variant="outline" className="scale-75 origin-left">Default Server Env</Badge>
                          )}
                        </Label>
                        {apiKeys.apolloApiKey && (
                          <button
                            type="button"
                            onClick={() => clearApiKeyOverride("apolloApiKey")}
                            className="text-xs text-red-400 hover:underline hover:text-red-300"
                          >
                            Clear Override
                          </button>
                        )}
                      </div>
                      <div className="relative">
                        <Input
                          id="apollo"
                          type={showKeys["apollo"] ? "text" : "password"}
                          placeholder={apiKeys.apolloApiKey ? "Override Active" : "Using server configured APOLLO_API_KEY"}
                          value={apiKeys.apolloApiKey}
                          onChange={(e) => setApiKeys({ ...apiKeys, apolloApiKey: e.target.value })}
                          className="pr-10"
                        />
                        <button
                          type="button"
                          onClick={() => toggleShowKey("apollo")}
                          className="absolute right-3 top-1/2 -translate-y-1/2 text-[var(--sidebar-text-muted)] hover:text-[var(--foreground-color)]"
                        >
                          {showKeys["apollo"] ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                        </button>
                      </div>
                    </div>

                    {/* Hunter Key */}
                    <div className="space-y-1.5">
                      <div className="flex justify-between items-center">
                        <Label htmlFor="hunter" className="flex items-center gap-1.5">
                          Hunter.io API Key
                          {apiKeys.hunterApiKey ? (
                            <Badge variant="success" className="scale-75 origin-left">Custom Override</Badge>
                          ) : (
                            <Badge variant="outline" className="scale-75 origin-left">Default Server Env</Badge>
                          )}
                        </Label>
                        {apiKeys.hunterApiKey && (
                          <button
                            type="button"
                            onClick={() => clearApiKeyOverride("hunterApiKey")}
                            className="text-xs text-red-400 hover:underline hover:text-red-300"
                          >
                            Clear Override
                          </button>
                        )}
                      </div>
                      <div className="relative">
                        <Input
                          id="hunter"
                          type={showKeys["hunter"] ? "text" : "password"}
                          placeholder={apiKeys.hunterApiKey ? "Override Active" : "Using server configured HUNTER_API_KEY"}
                          value={apiKeys.hunterApiKey}
                          onChange={(e) => setApiKeys({ ...apiKeys, hunterApiKey: e.target.value })}
                          className="pr-10"
                        />
                        <button
                          type="button"
                          onClick={() => toggleShowKey("hunter")}
                          className="absolute right-3 top-1/2 -translate-y-1/2 text-[var(--sidebar-text-muted)] hover:text-[var(--foreground-color)]"
                        >
                          {showKeys["hunter"] ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                        </button>
                      </div>
                    </div>

                    {/* Tavily Key */}
                    <div className="space-y-1.5">
                      <div className="flex justify-between items-center">
                        <Label htmlFor="tavily" className="flex items-center gap-1.5">
                          Tavily Search API Key
                          {apiKeys.tavilyApiKey ? (
                            <Badge variant="success" className="scale-75 origin-left">Custom Override</Badge>
                          ) : (
                            <Badge variant="outline" className="scale-75 origin-left">Default Server Env</Badge>
                          )}
                        </Label>
                        {apiKeys.tavilyApiKey && (
                          <button
                            type="button"
                            onClick={() => clearApiKeyOverride("tavilyApiKey")}
                            className="text-xs text-red-400 hover:underline hover:text-red-300"
                          >
                            Clear Override
                          </button>
                        )}
                      </div>
                      <div className="relative">
                        <Input
                          id="tavily"
                          type={showKeys["tavily"] ? "text" : "password"}
                          placeholder={apiKeys.tavilyApiKey ? "Override Active" : "Using server configured TAVILY_API_KEY"}
                          value={apiKeys.tavilyApiKey}
                          onChange={(e) => setApiKeys({ ...apiKeys, tavilyApiKey: e.target.value })}
                          className="pr-10"
                        />
                        <button
                          type="button"
                          onClick={() => toggleShowKey("tavily")}
                          className="absolute right-3 top-1/2 -translate-y-1/2 text-[var(--sidebar-text-muted)] hover:text-[var(--foreground-color)]"
                        >
                          {showKeys["tavily"] ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                        </button>
                      </div>
                    </div>

                    {/* Firecrawl Key */}
                    <div className="space-y-1.5">
                      <div className="flex justify-between items-center">
                        <Label htmlFor="firecrawl" className="flex items-center gap-1.5">
                          Firecrawl Web Scraper Key
                          {apiKeys.firecrawlApiKey ? (
                            <Badge variant="success" className="scale-75 origin-left">Custom Override</Badge>
                          ) : (
                            <Badge variant="outline" className="scale-75 origin-left">Default Server Env</Badge>
                          )}
                        </Label>
                        {apiKeys.firecrawlApiKey && (
                          <button
                            type="button"
                            onClick={() => clearApiKeyOverride("firecrawlApiKey")}
                            className="text-xs text-red-400 hover:underline hover:text-red-300"
                          >
                            Clear Override
                          </button>
                        )}
                      </div>
                      <div className="relative">
                        <Input
                          id="firecrawl"
                          type={showKeys["firecrawl"] ? "text" : "password"}
                          placeholder={apiKeys.firecrawlApiKey ? "Override Active" : "Using server configured FIRECRAWL_API_KEY"}
                          value={apiKeys.firecrawlApiKey}
                          onChange={(e) => setApiKeys({ ...apiKeys, firecrawlApiKey: e.target.value })}
                          className="pr-10"
                        />
                        <button
                          type="button"
                          onClick={() => toggleShowKey("firecrawl")}
                          className="absolute right-3 top-1/2 -translate-y-1/2 text-[var(--sidebar-text-muted)] hover:text-[var(--foreground-color)]"
                        >
                          {showKeys["firecrawl"] ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                        </button>
                      </div>
                    </div>
                  </CardContent>
                  <CardFooter className="border-t border-[var(--card-border)] px-6 py-4 flex justify-end">
                    <Button type="submit">
                      Save Override Keys
                    </Button>
                  </CardFooter>
                </form>
              </Card>
            </div>

            {/* Right side: Database / Infrastructure details */}
            <div className="space-y-6">
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Database className="h-4 w-4 text-[var(--primary)]" />
                    Vector Engine Details
                  </CardTitle>
                  <CardDescription>
                    Qdrant database cluster configurations and indexes.
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4 text-xs text-[var(--foreground-color)]/90">
                  <div className="flex justify-between border-b border-[var(--card-border)] pb-2">
                    <span className="text-[var(--sidebar-text-muted)]">Database Engine</span>
                    <span className="text-[var(--foreground-color)] font-semibold">Qdrant Local</span>
                  </div>
                  <div className="flex justify-between border-b border-[var(--card-border)] pb-2">
                    <span className="text-[var(--sidebar-text-muted)]">Host Address</span>
                    <span className="font-mono text-[var(--foreground-color)]">localhost</span>
                  </div>
                  <div className="flex justify-between border-b border-[var(--card-border)] pb-2">
                    <span className="text-[var(--sidebar-text-muted)]">Host Port</span>
                    <span className="font-mono text-[var(--foreground-color)]">6333</span>
                  </div>
                  <div className="flex justify-between border-b border-[var(--card-border)] pb-2">
                    <span className="text-[var(--sidebar-text-muted)]">Active Collection</span>
                    <span className="font-mono text-[var(--primary)]">leads</span>
                  </div>
                  <div>
                    <span className="text-[var(--sidebar-text-muted)] block mb-1">Index Collections</span>
                    <div className="flex flex-wrap gap-1">
                      <span className="bg-[var(--sidebar-toggle-bg)] border border-[var(--card-border)] px-2 py-0.5 rounded text-[10px] text-[var(--foreground-color)] font-mono">campaigns</span>
                      <span className="bg-[var(--sidebar-toggle-bg)] border border-[var(--card-border)] px-2 py-0.5 rounded text-[10px] text-[var(--foreground-color)] font-mono">leads</span>
                      <span className="bg-[var(--sidebar-toggle-bg)] border border-[var(--card-border)] px-2 py-0.5 rounded text-[10px] text-[var(--foreground-color)] font-mono">emails</span>
                      <span className="bg-[var(--sidebar-toggle-bg)] border border-[var(--card-border)] px-2 py-0.5 rounded text-[10px] text-[var(--foreground-color)] font-mono">replies</span>
                      <span className="bg-[var(--sidebar-toggle-bg)] border border-[var(--card-border)] px-2 py-0.5 rounded text-[10px] text-[var(--foreground-color)] font-mono">company_research</span>
                      <span className="bg-[var(--sidebar-toggle-bg)] border border-[var(--card-border)] px-2 py-0.5 rounded text-[10px] text-[var(--foreground-color)] font-mono">signals</span>
                    </div>
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Database className="h-4 w-4 text-emerald-500" />
                    MongoDB Cluster
                  </CardTitle>
                  <CardDescription>
                    Relational storage specifications.
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-2 text-xs text-[var(--foreground-color)]/90">
                  <div className="flex justify-between border-b border-[var(--card-border)] pb-2">
                    <span className="text-[var(--sidebar-text-muted)]">DB Host</span>
                    <span className="font-mono text-[var(--foreground-color)]">mongodb://localhost:27017</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-[var(--sidebar-text-muted)]">Database Name</span>
                    <span className="font-mono text-emerald-500">outreach_ai</span>
                  </div>
                </CardContent>
              </Card>
            </div>
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
      </Tabs>
    </div>
  );
}