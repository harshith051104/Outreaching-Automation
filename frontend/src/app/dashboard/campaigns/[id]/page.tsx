"use client";

import { useEffect, useState, useMemo, useRef } from "react";
import { useParams, useRouter } from "next/navigation";
import { getCampaign, getCampaignStats, startCampaign, pauseCampaign, deleteCampaign, updateCampaign } from "@/services/campaign-api";
import { getGmailAccounts } from "@/services/gmail-api";
import { getLeads } from "@/services/lead-api";
import { getFollowups, executeFollowup, cancelFollowup } from "@/services/followup-api";
import type { FollowupTask } from "@/services/followup-api";
import type { Lead } from "@/types/lead";
import Link from "next/link";
import { useAuthStore } from "@/store/auth-store";
import { Play, Pause, Trash2 } from "lucide-react";

export default function CampaignDetailPage() {
  const params = useParams();
  const router = useRouter();
  const campaignId = params.id as string;
  const { user } = useAuthStore();
  const [campaign, setCampaign] = useState<any>(null);
  const [stats, setStats] = useState<any>(null);
  const [gmailAccounts, setGmailAccounts] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [leads, setLeads] = useState<Lead[]>([]);
  const [selectedLeadId, setSelectedLeadId] = useState<string>("");
  const [sequenceSteps, setSequenceSteps] = useState<any[]>([]);
  const [savingSequence, setSavingSequence] = useState(false);
  const [previewStepIndex, setPreviewStepIndex] = useState<number>(-1);
  const [hasLoadedInitial, setHasLoadedInitial] = useState(false);

  // New state variables for live editing raw templates and tracking followups
  const [subjectTemplate, setSubjectTemplate] = useState("");
  const [bodyTemplate, setBodyTemplate] = useState("");
  const [followups, setFollowups] = useState<FollowupTask[]>([]);

  const selectedLead = useMemo(
    () => leads.find((l) => l.id === selectedLeadId) || null,
    [leads, selectedLeadId]
  );

  const previewSubject = useMemo(() => {
    if (previewStepIndex === -1) return subjectTemplate || "";
    const step = sequenceSteps[previewStepIndex];
    return step?.channel === "email" ? (step?.subject_template || "") : `[${step?.channel?.toUpperCase()} Step ${step?.step_number}]`;
  }, [subjectTemplate, sequenceSteps, previewStepIndex]);

  const previewBody = useMemo(() => {
    if (previewStepIndex === -1) return bodyTemplate || "";
    const step = sequenceSteps[previewStepIndex];
    if (step?.channel === "email" || step?.channel === "linkedin") {
      return step?.body_template || "";
    }
    return step?.notes || "";
  }, [bodyTemplate, sequenceSteps, previewStepIndex]);

  const handleStart = async () => {
    setActionLoading(true);
    try {
      await startCampaign(campaignId);
      await loadData(true);
    } catch (err) {
      console.error("Failed to start campaign:", err);
    } finally {
      setActionLoading(false);
    }
  };

  const handlePause = async () => {
    setActionLoading(true);
    try {
      await pauseCampaign(campaignId);
      await loadData(true);
    } catch (err) {
      console.error("Failed to pause campaign:", err);
    } finally {
      setActionLoading(false);
    }
  };

  const handleDelete = async () => {
    if (!window.confirm("Are you sure you want to delete this campaign?")) return;
    setActionLoading(true);
    try {
      await deleteCampaign(campaignId);
      router.push("/dashboard/campaigns");
    } catch (err) {
      console.error("Failed to delete campaign:", err);
      setActionLoading(false);
    }
  };

  const loadData = async (forceSyncSequence = false, isPoll = false) => {
    try {
      const [campaignData, statsData, accountsData, leadsData, followupsData] = await Promise.all([
        getCampaign(campaignId),
        getCampaignStats(campaignId),
        getGmailAccounts().catch(() => []),
        getLeads(campaignId).catch(() => []),
        getFollowups({ campaign_id: campaignId }).catch(() => []),
      ]);
      setCampaign(campaignData);
      setStats(statsData);
      setGmailAccounts(accountsData);
      setLeads(leadsData);
      setFollowups(followupsData);
      
      if (!isPoll || !hasLoadedInitial || forceSyncSequence) {
        setSequenceSteps(campaignData.sequence_steps || [
          { step_number: 1, channel: "email", delay_days: 3 },
          { step_number: 2, channel: "email", delay_days: 10 },
          { step_number: 3, channel: "email", delay_days: 20 },
          { step_number: 4, channel: "email", delay_days: 28 }
        ]);
        setSubjectTemplate(campaignData.subject_template || "");
        setBodyTemplate(campaignData.body_template || "");
        setHasLoadedInitial(true);
      }
      setSelectedLeadId((prev) => {
        if (prev && leadsData.some((l) => l.id === prev)) return prev;
        return leadsData.length > 0 ? leadsData[0].id : "";
      });
    } catch (err) {
      console.error("Failed to load campaign:", err);
    } finally {
      setLoading(false);
    }
  };


  // LINKEDIN DISABLED — change back to "email" | "linkedin" | "task" to re-enable LinkedIn steps
  const handleAddStep = (channel: "email" | /* "linkedin" | */ "task") => {
    setSequenceSteps(prev => {
      const nextStepNum = prev.length + 1;
      const lastStep = prev[prev.length - 1];
      const nextDelay = lastStep ? lastStep.delay_days + 2 : 0;
      return [
        ...prev,
        {
          step_number: nextStepNum,
          channel,
          delay_days: nextDelay,
          body_template: channel === "email" ? "Hi {{first_name}},\n\nFollowing up." : "Hi {{first_name}}, let's connect.",
          subject_template: channel === "email" ? "Re: " + (campaign?.subject_template || "Outreach") : undefined
        }
      ];
    });
  };

  const handleDeleteStep = (index: number) => {
    setSequenceSteps(prev => {
      const filtered = prev.filter((_, i) => i !== index);
      return filtered.map((step, idx) => ({
        ...step,
        step_number: idx + 1
      }));
    });
  };

  const handleMoveStep = (index: number, direction: "up" | "down") => {
    setSequenceSteps(prev => {
      const list = [...prev];
      const targetIndex = direction === "up" ? index - 1 : index + 1;
      if (targetIndex < 0 || targetIndex >= list.length) return prev;
      const temp = list[index];
      list[index] = list[targetIndex];
      list[targetIndex] = temp;
      return list.map((step, idx) => ({
        ...step,
        step_number: idx + 1
      }));
    });
  };

  const handleSaveSequence = async () => {
    setSavingSequence(true);
    try {
      await updateCampaign(campaignId, {
        ...campaign,
        sequence_steps: sequenceSteps
      });
      alert("Sequence steps updated successfully!");
      loadData(true);
    } catch (err) {
      console.error(err);
      alert("Failed to save sequence steps.");
    } finally {
      setSavingSequence(false);
    }
  };


  const isTemplateChanged = subjectTemplate !== (campaign?.subject_template || "") || bodyTemplate !== (campaign?.body_template || "");

  const handleSaveTemplates = async () => {
    setActionLoading(true);
    try {
      await updateCampaign(campaignId, {
        ...campaign,
        subject_template: subjectTemplate,
        body_template: bodyTemplate
      });
      alert("Templates saved successfully!");
      await loadData(true);
    } catch (err) {
      console.error("Failed to save templates:", err);
      alert("Failed to save templates.");
    } finally {
      setActionLoading(false);
    }
  };

  const loadDataRef = useRef(loadData);
  useEffect(() => {
    loadDataRef.current = loadData;
  });

  useEffect(() => {
    if (campaignId) {
      loadDataRef.current(false, false);
      const interval = setInterval(() => {
        loadDataRef.current(false, true);
      }, 5000);
      return () => clearInterval(interval);
    }
  }, [campaignId]);


  const getFirstName = (lead: Lead | null): string => {
    if (!lead?.name) return "there";
    const parts = lead.name.trim().split(/\s+/);
    return parts[0] || "there";
  };

  const getLastName = (lead: Lead | null): string => {
    if (!lead?.name) return "";
    const parts = lead.name.trim().split(/\s+/);
    return parts.slice(1).join(" ") || "";
  };

  const renderTemplate = (template: string, lead: Lead | null) => {
    if (!template) return "";

    const gmailAccount = gmailAccounts.find((a: any) => a.id === campaign?.gmail_account_id);
    const senderEmail = gmailAccount?.email || user?.email || "sender@example.com";
    const senderName = gmailAccount?.name || user?.name || senderEmail.split('@')[0] || "Sender Name";
    const senderTitle = "Founder & CEO";

    let result = template;

    if (lead) {
      result = result
        .replace(/\{\{\s*first_name\s*\}\}/gi, getFirstName(lead))
        .replace(/\{\{\s*last_name\s*\}\}/gi, getLastName(lead))
        .replace(/\{\{\s*name\s*\}\}/gi, lead.name || "")
        .replace(/\{\{\s*email\s*\}\}/gi, lead.email || "")
        .replace(/\{\{\s*company\s*\}\}/gi, lead.company || "your company")
        .replace(/\{\{\s*role\s*\}\}/gi, lead.role || "your role")
        .replace(/\{\{\s*title\s*\}\}/gi, lead.role || "your role");
    }

    result = result
      .replace(/\{\{\s*sender_name\s*\}\}/gi, senderName)
      .replace(/\{\{\s*sender_email\s*\}\}/gi, senderEmail)
      .replace(/\{\{\s*sender_title\s*\}\}/gi, senderTitle)
      .replace(/\[Your\s+Name\]/gi, senderName)
      .replace(/\[Sender\s+Name\]/gi, senderName)
      .replace(/\[Your\s+Email\]/gi, senderEmail)
      .replace(/\[Sender\s+Email\]/gi, senderEmail)
      .replace(/\[Your\s+Title\]/gi, senderTitle)
      .replace(/\[Sender\s+Title\]/gi, senderTitle);

    return result;
  };

  const gmailEmail = gmailAccounts.find((a: any) => a.id === campaign?.gmail_account_id)?.email || campaign?.gmail_account_id || "Your Connected Gmail";

  const toDisplay = selectedLead
    ? selectedLead.name
      ? `${selectedLead.name} <${selectedLead.email}>`
      : selectedLead.email
    : "recipient@example.com";

  if (loading) return <div className="text-gray-500">Loading...</div>;
  if (!campaign) return <div className="text-red-500">Campaign not found</div>;

  return (
    <div style={{ padding: '24px', maxWidth: '1200px', margin: '0 auto' }} className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <h1 className="text-2xl font-bold text-gray-900">{campaign.name}</h1>
        <div className="flex gap-3 flex-wrap">
          {campaign.status === "draft" && (
            <button
              onClick={handleStart}
              disabled={actionLoading}
              className="flex items-center gap-2 rounded-lg bg-gradient-to-r from-emerald-600 to-teal-500 px-4 py-2 text-sm font-bold text-white shadow-md transition-all hover:scale-[1.02] hover:shadow-lg disabled:opacity-50 cursor-pointer"
            >
              <Play size={14} fill="currentColor" /> Start Campaign
            </button>
          )}
          {campaign.status === "active" && (
            <button
              onClick={handlePause}
              disabled={actionLoading}
              className="flex items-center gap-2 rounded-lg bg-gradient-to-r from-amber-500 to-orange-500 px-4 py-2 text-sm font-bold text-white shadow-md transition-all hover:scale-[1.02] hover:shadow-lg disabled:opacity-50 cursor-pointer"
            >
              <Pause size={14} /> Pause Campaign
            </button>
          )}
          {campaign.status === "paused" && (
            <button
              onClick={handleStart}
              disabled={actionLoading}
              className="flex items-center gap-2 rounded-lg bg-gradient-to-r from-emerald-600 to-teal-500 px-4 py-2 text-sm font-bold text-white shadow-md transition-all hover:scale-[1.02] hover:shadow-lg disabled:opacity-50 cursor-pointer"
            >
              <Play size={14} fill="currentColor" /> Resume Campaign
            </button>
          )}
          <button
            onClick={handleDelete}
            disabled={actionLoading}
            className="flex items-center gap-2 rounded-lg bg-gradient-to-r from-rose-600 to-red-500 px-4 py-2 text-sm font-bold text-white shadow-md transition-all hover:scale-[1.02] hover:shadow-lg disabled:opacity-50 cursor-pointer"
          >
            <Trash2 size={14} /> Delete
          </button>
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 md:grid-cols-4">
        <div className="rounded-lg bg-white p-4 shadow">
          <div className="text-sm text-gray-500">Emails Sent</div>
          <div className="mt-1 text-2xl font-bold text-blue-600">{stats?.emails_sent ?? 0}</div>
        </div>
        <div className="rounded-lg bg-white p-4 shadow">
          <div className="text-sm text-gray-500">Opens</div>
          <div className="mt-1 text-2xl font-bold text-green-600">{stats?.unique_opens ?? 0}</div>
        </div>
        <div className="rounded-lg bg-white p-4 shadow">
          <div className="text-sm text-gray-500">Clicks</div>
          <div className="mt-1 text-2xl font-bold text-purple-600">{stats?.total_clicks ?? 0}</div>
        </div>
        <div className="rounded-lg bg-white p-4 shadow">
          <div className="text-sm text-gray-500">Replies</div>
          <div className="mt-1 text-2xl font-bold text-orange-600">{stats?.total_replies ?? 0}</div>
        </div>
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        <div className="space-y-6">
          <div className="rounded-lg bg-white p-6 shadow">
            <h2 className="mb-4 text-lg font-semibold">Campaign Details</h2>
            <dl className="space-y-2">
              <div className="flex justify-between">
                <dt className="text-gray-500">Status</dt>
                <dd className="font-medium">{campaign.status}</dd>
              </div>
              <div className="flex justify-between items-center py-1">
                <dt className="text-gray-500 shrink-0">Gmail Account</dt>
                <dd className="ml-4 flex-1 max-w-[220px]">
                  <select
                    value={campaign.gmail_account_id || ""}
                    onChange={async (e) => {
                      const newAccountId = e.target.value;
                      try {
                        await updateCampaign(campaignId, {
                          ...campaign,
                          gmail_account_id: newAccountId
                        });
                        await loadData();
                      } catch (err) {
                        console.error("Failed to update campaign Gmail account:", err);
                      }
                    }}
                    className="rounded border border-gray-300 px-2 py-1 text-xs bg-white text-gray-800 focus:border-blue-500 focus:outline-none w-full"
                  >
                    <option value="">Select Account</option>
                    {gmailAccounts.map((account) => (
                      <option key={account.id} value={account.id}>
                        {account.name || account.email}
                      </option>
                    ))}
                  </select>
                </dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-gray-500">Total Leads</dt>
                <dd className="font-medium">{campaign.total_leads ?? 0}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-gray-500">Open Rate</dt>
                <dd className="font-medium">{stats?.open_rate ?? 0}%</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-gray-500">Reply Rate</dt>
                <dd className="font-medium">{stats?.reply_rate ?? 0}%</dd>
              </div>
            </dl>
          </div>

          {/* Sequence Timeline card */}
          <div className="rounded-xl bg-white p-6 shadow-sm border border-slate-100 space-y-4">
            <div className="flex items-center justify-between border-b pb-2">
              <h2 className="text-sm font-bold text-slate-900 uppercase tracking-wider">Outreach Sequence Flow</h2>
              <button
                onClick={handleSaveSequence}
                disabled={savingSequence}
                className="px-3 py-1 bg-blue-600 hover:bg-blue-700 text-white font-bold text-xs rounded-lg transition-colors disabled:opacity-50"
              >
                {savingSequence ? "Saving..." : "Save Sequence"}
              </button>
            </div>

            <div className="relative border-l border-slate-200 pl-6 space-y-4 ml-2 mt-4">
              {sequenceSteps.map((step: any, idx: number) => (
                <div key={idx} className="relative group">
                  <span className="absolute -left-[32px] top-1 flex h-5.5 w-5.5 items-center justify-center rounded-full bg-slate-900 ring-4 ring-white text-[10px] font-bold text-white">
                    {step.step_number}
                  </span>
                  
                  <div className="bg-slate-50 border border-slate-200 p-4 rounded-lg space-y-3">
                    <div className="flex items-center justify-between gap-4 border-b border-gray-200 pb-2">
                      <div className="flex items-center gap-3">
                        <span className="text-xs font-bold text-slate-900 capitalize">{step.channel} Step</span>
                        <div className="flex items-center gap-1">
                          <span className="text-[10px] text-slate-500 uppercase tracking-wider font-bold">Delay:</span>
                          <input
                            type="number"
                            value={step.delay_days}
                            onChange={(e) => {
                              const val = parseInt(e.target.value) || 0;
                              setSequenceSteps(prev => {
                                const next = [...prev];
                                next[idx] = { ...next[idx], delay_days: val };
                                return next;
                              });
                            }}
                            className="w-12 rounded border border-gray-300 px-1 py-0.5 text-xs bg-white text-gray-800 font-semibold focus:outline-none"
                            min={0}
                          />
                          <span className="text-[10px] text-slate-500 font-bold">days</span>
                        </div>
                      </div>

                      <div className="flex items-center gap-1 shrink-0">
                        <button
                          onClick={() => handleMoveStep(idx, "up")}
                          disabled={idx === 0}
                          className="p-1 hover:bg-slate-200 rounded disabled:opacity-30 text-xs"
                          title="Move Step Up"
                        >
                          &uarr;
                        </button>
                        <button
                          onClick={() => handleMoveStep(idx, "down")}
                          disabled={idx === sequenceSteps.length - 1}
                          className="p-1 hover:bg-slate-200 rounded disabled:opacity-30 text-xs"
                          title="Move Step Down"
                        >
                          &darr;
                        </button>
                        <button
                          onClick={() => handleDeleteStep(idx)}
                          className="p-1 hover:bg-red-50 text-red-500 rounded ml-1 text-xs"
                          title="Delete Step"
                        >
                          &times;
                        </button>
                      </div>
                    </div>

                    {step.channel === "email" && (
                      <div className="space-y-2">
                        <div className="space-y-1">
                          <label className="text-[10px] font-bold text-gray-500 uppercase tracking-wider block">Subject Template</label>
                          <input
                            type="text"
                            value={step.subject_template || ""}
                            onChange={(e) => {
                              setSequenceSteps(prev => {
                                const next = [...prev];
                                next[idx] = { ...next[idx], subject_template: e.target.value };
                                return next;
                              });
                            }}
                            placeholder="Follow up subject"
                            className="w-full rounded border border-gray-300 px-2 py-1 text-xs bg-white text-gray-800 focus:outline-none"
                          />
                        </div>
                        <div className="space-y-1">
                          <label className="text-[10px] font-bold text-gray-500 uppercase tracking-wider block">Body Template</label>
                          <textarea
                            value={step.body_template || ""}
                            onChange={(e) => {
                              setSequenceSteps(prev => {
                                const next = [...prev];
                                next[idx] = { ...next[idx], body_template: e.target.value };
                                return next;
                              });
                            }}
                            rows={3}
                            placeholder="Hi {{first_name}},\n\nFollowing up on my last email."
                            className="w-full rounded border border-gray-300 p-2 text-xs bg-white text-gray-800 focus:outline-none font-mono"
                          />
                        </div>
                      </div>
                    )}

                    {/* LINKEDIN DISABLED — uncomment block below to re-enable LinkedIn message template editor
                    {step.channel === "linkedin" && (
                      <div className="space-y-1">
                        <label className="text-[10px] font-bold text-gray-500 uppercase tracking-wider block">LinkedIn Message Template</label>
                        <textarea
                          value={step.body_template || ""}
                          onChange={(e) => {
                            setSequenceSteps(prev => {
                              const next = [...prev];
                              next[idx] = { ...next[idx], body_template: e.target.value };
                              return next;
                            });
                          }}
                          rows={3}
                          placeholder="Hi {{first_name}}, let's connect."
                          className="w-full rounded border border-gray-300 p-2 text-xs bg-white text-gray-800 focus:outline-none font-mono"
                        />
                      </div>
                    )}
                    */}

                    {step.channel === "task" && (
                      <div className="space-y-1">
                        <label className="text-[10px] font-bold text-gray-500 uppercase tracking-wider block">Task Notes</label>
                        <textarea
                          value={step.notes || ""}
                          onChange={(e) => {
                            setSequenceSteps(prev => {
                              const next = [...prev];
                              next[idx] = { ...next[idx], notes: e.target.value };
                              return next;
                            });
                          }}
                          rows={2}
                          placeholder="Call lead / Check social media profile"
                          className="w-full rounded border border-gray-300 p-2 text-xs bg-white text-gray-800 focus:outline-none font-mono"
                        />
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>

            {/* Quick Add Step Controls */}
            <div className="border-t pt-4 space-y-2">
              <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">Add Sequence Step</span>
              <div className="grid grid-cols-2 gap-2">
                <button
                  type="button"
                  onClick={() => handleAddStep("email")}
                  className="px-2 py-1.5 border border-slate-200 bg-slate-50 hover:bg-slate-100 text-[10px] font-bold rounded-lg text-slate-800 transition-all text-center"
                >
                  + Email Step
                </button>
                <button
                  type="button"
                  onClick={() => handleAddStep("task")}
                  className="px-2 py-1.5 border border-slate-200 bg-slate-50 hover:bg-slate-100 text-[10px] font-bold rounded-lg text-slate-800 transition-all text-center"
                >
                  + Call Task
                </button>
              </div>
            </div>
          </div>
        </div>

        <div className="rounded-xl bg-white p-4 sm:p-6 shadow-sm border border-gray-100 space-y-6">
          <div className="flex flex-col gap-4 border-b border-gray-100 pb-4">
            <div>
              <h2 className="text-lg font-bold text-gray-900">Email Campaign Preview</h2>
              <p className="text-xs text-gray-500 font-medium">Verify how your template is personalized for each lead.</p>
            </div>

            {leads.length > 0 ? (
              <div className="flex flex-col gap-3">
                <div className="flex flex-col sm:flex-row sm:items-center gap-2">
                  <label className="text-xs font-bold text-gray-500 uppercase tracking-wider whitespace-nowrap min-w-[100px]">
                    Select Lead:
                  </label>
                  <select
                    value={selectedLeadId}
                    onChange={(e) => setSelectedLeadId(e.target.value)}
                    className="rounded border border-gray-300 bg-white px-3 py-1.5 text-xs font-medium text-gray-950 outline-none focus:border-blue-500 w-full sm:w-auto"
                  >
                    {leads.map((l) => (
                      <option key={l.id} value={l.id}>
                        {l.name ? `${l.name} (${l.email})` : l.email}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="flex flex-col sm:flex-row sm:items-center gap-2">
                  <label className="text-xs font-bold text-gray-500 uppercase tracking-wider whitespace-nowrap min-w-[100px]">
                    Preview Step:
                  </label>
                  <select
                    value={previewStepIndex}
                    onChange={(e) => setPreviewStepIndex(parseInt(e.target.value))}
                    className="rounded border border-gray-300 bg-white px-3 py-1.5 text-xs font-medium text-gray-950 outline-none focus:border-blue-500 w-full sm:w-auto"
                  >
                    <option value={-1}>Initial Campaign Email</option>
                    {sequenceSteps.map((step: any, idx: number) => (
                      <option key={idx} value={idx}>
                        Step {step.step_number}: {step.channel.toUpperCase()} (Day {step.delay_days})
                      </option>
                    ))}
                  </select>
                </div>
              </div>
            ) : (
              <div className="text-xs text-amber-600 bg-amber-50 px-3 py-1.5 rounded-lg font-medium border border-amber-100">
                No leads added to this campaign yet.
              </div>
            )}
          </div>

          <div className="grid gap-6 lg:grid-cols-2">
            {/* Left Column: Raw Template */}
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-bold text-gray-500 uppercase tracking-wider">Raw Templates</h3>
                {isTemplateChanged && (
                  <button
                    onClick={handleSaveTemplates}
                    disabled={actionLoading}
                    className="px-3 py-1 bg-violet-600 hover:bg-violet-700 text-white font-bold text-xs rounded-lg transition-all hover:scale-[1.02] active:scale-[0.98] cursor-pointer disabled:opacity-50"
                  >
                    Save Templates
                  </button>
                )}
              </div>
              <div className="rounded-xl bg-gray-50/50 p-4 border border-gray-200/60 space-y-4">
                <div>
                  <label className="text-xs font-bold text-gray-400 mb-1 block uppercase tracking-wider">Subject Template</label>
                  <input
                    type="text"
                    value={subjectTemplate}
                    onChange={(e) => setSubjectTemplate(e.target.value)}
                    className="w-full rounded border border-gray-300 px-3 py-2 text-sm bg-white text-gray-800 focus:border-violet-500 focus:outline-none"
                    placeholder="No template set"
                  />
                </div>
                <hr className="border-gray-200/50" />
                <div>
                  <label className="text-xs font-bold text-gray-400 mb-1 block uppercase tracking-wider">Body Template</label>
                  <textarea
                    value={bodyTemplate}
                    onChange={(e) => setBodyTemplate(e.target.value)}
                    rows={8}
                    className="w-full rounded border border-gray-300 p-3 text-sm bg-white text-gray-800 focus:border-violet-500 focus:outline-none font-sans"
                    placeholder="No template set"
                  />
                </div>
                {campaign.attachments && campaign.attachments.length > 0 && (
                  <>
                    <hr className="border-gray-200/50" />
                    <div>
                      <div className="text-xs font-semibold text-gray-400 mb-1">Attachments</div>
                      <div className="space-y-1">
                        {campaign.attachments.map((att: any, idx: number) => (
                          <a
                            key={idx}
                            href={att.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="flex items-center gap-2 text-sm text-blue-600 hover:text-blue-700"
                          >
                            <svg className="h-3.5 w-3.5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13" />
                            </svg>
                            <span>{att.name || `File ${idx + 1}`}</span>
                          </a>
                        ))}
                      </div>
                    </div>
                  </>
                )}
              </div>
            </div>

            {/* Right Column: Live Personalized Preview */}
            <div className="space-y-4">
              <h3 className="text-sm font-bold text-gray-500 uppercase tracking-wider">Personalized Live Preview</h3>
              <div className="rounded-xl border border-gray-200 shadow-sm overflow-hidden bg-white">
                {/* Mock Email Window header */}
                <div className="bg-gray-50/50 px-4 py-3 border-b border-gray-200 space-y-1 text-xs">
                  <div className="flex justify-between gap-2">
                    <span className="text-gray-400 font-medium shrink-0">From:</span>
                    <span className="text-gray-700 font-semibold truncate text-right">
                      {gmailEmail}
                    </span>
                  </div>
                  <div className="flex justify-between gap-2">
                    <span className="text-gray-400 font-medium shrink-0">To:</span>
                    <span className="text-gray-700 font-semibold truncate text-right">
                      {toDisplay}
                    </span>
                  </div>
                  <div className="flex justify-between gap-2 pt-1 border-t border-gray-200/40">
                    <span className="text-gray-400 font-medium shrink-0">Subject:</span>
                    <span className="text-gray-900 font-bold truncate text-right">
                      {renderTemplate(previewSubject, selectedLead)}
                    </span>
                  </div>
                </div>

                {/* Email Body */}
                <div
                  className="p-6 text-sm text-gray-800 bg-white min-h-[160px] whitespace-pre-wrap leading-relaxed"
                  dangerouslySetInnerHTML={{
                    __html: renderTemplate(previewBody, selectedLead)
                  }}
                />

                {/* Attachments */}
                {campaign.attachments && campaign.attachments.length > 0 && (
                  <div className="border-t border-gray-200 px-4 py-3 bg-gray-50/50">
                    <div className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">
                      Attachments
                    </div>
                    <div className="space-y-1.5">
                      {campaign.attachments.map((att: any, idx: number) => (
                        <a
                          key={idx}
                          href={att.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="flex items-center gap-2 text-sm text-blue-600 hover:text-blue-800 hover:bg-blue-50 rounded-lg px-2 py-1.5 transition-colors"
                        >
                          <svg className="h-4 w-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13" />
                          </svg>
                          <span className="font-medium truncate">{att.name || `Attachment ${idx + 1}`}</span>
                        </a>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Follow-up Tracking card */}
      <div className="rounded-xl bg-white p-6 shadow-sm border border-slate-100 space-y-4">
        <div className="border-b pb-2">
          <h2 className="text-lg font-bold text-slate-900">Follow-up Queue & Tracking</h2>
          <p className="text-xs text-gray-500 font-medium">Monitor upcoming follow-up stages and cancel or send them manually.</p>
        </div>

        {followups.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-100">
              <thead>
                <tr className="bg-slate-50 text-[10px] font-bold text-slate-500 uppercase tracking-wider text-left">
                  <th className="px-4 py-3">Lead</th>
                  <th className="px-4 py-3">Stage</th>
                  <th className="px-4 py-3">Scheduled For</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {followups.map((f) => {
                  const lead = leads.find((l) => l.id === f.lead_id);
                  const displayLead = lead ? (lead.name ? `${lead.name} (${lead.email})` : lead.email) : "Unknown Lead";
                  
                  // Status Badge configuration
                  const statusColorMap = {
                    pending: "bg-amber-50 text-amber-700 border-amber-200",
                    executed: "bg-emerald-50 text-emerald-700 border-emerald-200",
                    failed: "bg-rose-50 text-rose-700 border-rose-200",
                    cancelled: "bg-slate-50 text-slate-500 border-slate-200",
                  };
                  const statusClass = statusColorMap[f.status] || "bg-slate-50 text-slate-500";

                  return (
                    <tr key={f.id} className="text-xs text-slate-700">
                      <td className="px-4 py-3 font-medium">{displayLead}</td>
                      <td className="px-4 py-3 font-semibold">Stage #{f.sequence_number}</td>
                      <td className="px-4 py-3">{new Date(f.scheduled_at).toLocaleString()}</td>
                      <td className="px-4 py-3">
                        <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold border ${statusClass}`}>
                          {f.status}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-right">
                        {f.status === "pending" && (
                          <div className="flex justify-end gap-2">
                            <button
                              onClick={async () => {
                                if (!window.confirm("Send this follow-up email immediately?")) return;
                                try {
                                  await executeFollowup(f.id);
                                  alert("Follow-up executed successfully!");
                                  loadData(true);
                                } catch (err) {
                                  console.error("Failed to execute follow-up:", err);
                                  alert("Failed to send follow-up.");
                                }
                              }}
                              className="px-2 py-1 bg-emerald-600 hover:bg-emerald-700 text-white font-bold rounded text-[10px] transition-colors cursor-pointer"
                            >
                              Send Now
                            </button>
                            <button
                              onClick={async () => {
                                if (!window.confirm("Cancel this scheduled follow-up?")) return;
                                try {
                                  await cancelFollowup(f.id);
                                  alert("Follow-up cancelled.");
                                  loadData(true);
                                } catch (err) {
                                  console.error("Failed to cancel follow-up:", err);
                                  alert("Failed to cancel.");
                                }
                              }}
                              className="px-2 py-1 bg-rose-50 hover:bg-rose-100 text-rose-600 border border-rose-200 font-bold rounded text-[10px] transition-colors cursor-pointer"
                            >
                              Cancel
                            </button>
                          </div>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="text-xs text-slate-500 bg-slate-50 p-4 rounded-lg text-center font-medium border border-slate-100">
            No follow-ups scheduled or sent yet for this campaign.
          </div>
        )}
      </div>

      <div>
        <Link href="/dashboard/leads" className="text-blue-600 hover:underline">
          Manage leads for this campaign &rarr;
        </Link>
      </div>
    </div>
  );
}