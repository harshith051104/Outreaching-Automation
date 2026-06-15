"use client";

import { useEffect, useState, use } from "react";
import { getLead, getLeadEngagement, getLeadOpportunity } from "@/services/lead-api";
import { getLeadSignals } from "@/services/signals-api";
import { getCampaign } from "@/services/campaign-api";
import { 
  Users, 
  MapPin, 
  Globe, 
  Linkedin, 
  TrendingUp, 
  Brain, 
  Activity, 
  Mail, 
  ChevronRight, 
  BookOpen, 
  Clock, 
  ShieldAlert, 
  Award,
  ExternalLink,
  MessageSquare
} from "lucide-react";
import Link from "next/link";

interface PageProps {
  params: Promise<{ id: string }>;
}

export default function LeadDetailsPage({ params }: PageProps) {
  const { id } = use(params);
  const [lead, setLead] = useState<any>(null);
  const [engagement, setEngagement] = useState<any>(null);
  const [signals, setSignals] = useState<any[]>([]);
  const [opportunity, setOpportunity] = useState<any>(null);
  const [campaign, setCampaign] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState("overview");

  useEffect(() => {
    loadLeadData();
  }, [id]);

  const loadLeadData = async () => {
    try {
      setLoading(true);
      const leadData = await getLead(id);
      setLead(leadData);

      // Load related information in parallel
      const [engagementData, signalsData, oppData] = await Promise.all([
        getLeadEngagement(id).catch(() => null),
        getLeadSignals(id).catch(() => []),
        getLeadOpportunity(id).catch(() => null)
      ]);

      setEngagement(engagementData);
      setSignals(signalsData);
      setOpportunity(oppData);

      if (leadData.campaign_id) {
        const campaignData = await getCampaign(leadData.campaign_id).catch(() => null);
        setCampaign(campaignData);
      }
    } catch (err) {
      console.error("Failed to load lead profile:", err);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex h-[85vh] items-center justify-center">
        <div className="text-center space-y-3">
          <div className="h-10 w-10 border-4 border-blue-600 border-t-transparent rounded-full animate-spin mx-auto"></div>
          <p className="text-gray-500 font-medium animate-pulse">Loading Lead Intelligence Profile...</p>
        </div>
      </div>
    );
  }

  if (!lead) {
    return (
      <div className="p-8 text-center bg-white border border-red-100 rounded-xl max-w-md mx-auto mt-20">
        <ShieldAlert className="h-12 w-12 text-red-500 mx-auto mb-2" />
        <h2 className="text-lg font-bold text-slate-900">Lead Profile Not Found</h2>
        <p className="text-xs text-gray-500 mt-1">The requested lead ID does not exist or you do not have permission to view it.</p>
        <Link href="/dashboard/leads" className="mt-4 inline-block text-xs font-bold text-blue-600 hover:underline">
          &larr; Back to Leads List
        </Link>
      </div>
    );
  }

  const tabs = [
    { id: "overview", label: "Overview", icon: Users },
    { id: "research", label: "Company Research", icon: BookOpen },
    { id: "signals", label: "Signals Feed", icon: Brain },
    { id: "campaigns", label: "Campaign / Sequence", icon: ChevronRight },
    { id: "memory", label: "Memory (Vector)", icon: Award },
    { id: "activity", label: "Engagement Timeline", icon: Activity },
  ];

  return (
    <div className="max-w-7xl mx-auto space-y-6 p-4">
      {/* Back Button */}
      <Link href="/dashboard/leads" className="text-xs text-slate-500 hover:text-slate-950 font-bold flex items-center gap-1">
        &larr; Back to Leads Database
      </Link>

      {/* Header Profile Summary */}
      <div className="bg-white border border-slate-100 rounded-2xl p-6 shadow-sm flex flex-col md:flex-row md:items-center justify-between gap-6">
        <div className="flex items-center gap-4">
          <div className="h-16 w-16 bg-gradient-to-tr from-blue-600 to-indigo-600 rounded-2xl flex items-center justify-center text-white text-2xl font-black">
            {lead.name?.charAt(0).toUpperCase()}
          </div>
          <div className="space-y-1">
            <h1 className="text-xl font-extrabold text-slate-950">{lead.name}</h1>
            <p className="text-xs text-slate-500 font-medium">
              {lead.role} at <span className="font-bold text-slate-800">{lead.company}</span>
            </p>
            <div className="flex flex-wrap gap-2 pt-1">
              {lead.email && (
                <span className="inline-flex items-center gap-1 bg-slate-50 border px-2 py-0.5 rounded text-[10px] text-slate-600 font-medium">
                  <Mail className="h-3 w-3" /> {lead.email}
                </span>
              )}
              {lead.linkedin && (
                <a href={lead.linkedin} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 bg-blue-50 border border-blue-100 hover:bg-blue-100 px-2 py-0.5 rounded text-[10px] text-blue-700 font-medium transition-colors">
                  <Linkedin className="h-3 w-3" /> LinkedIn <ExternalLink className="h-2.5 w-2.5" />
                </a>
              )}
              {lead.website && (
                <a href={lead.website} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 bg-slate-50 border hover:bg-slate-100 px-2 py-0.5 rounded text-[10px] text-slate-600 font-medium transition-colors">
                  <Globe className="h-3 w-3" /> Website <ExternalLink className="h-2.5 w-2.5" />
                </a>
              )}
            </div>
          </div>
        </div>

        {/* Quality Score Indicator */}
        <div className="flex gap-4 items-center border-t md:border-t-0 md:border-l pt-4 md:pt-0 md:pl-6 shrink-0">
          <div className="text-center">
            <div className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Quality Score</div>
            <div className={`text-3xl font-black mt-0.5 ${
              lead.lead_quality_score >= 80 ? "text-emerald-600" :
              lead.lead_quality_score >= 50 ? "text-amber-500" :
              "text-slate-500"
            }`}>
              {lead.lead_quality_score || 65}%
            </div>
          </div>
          <div className="text-center">
            <div className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Opportunity Intent</div>
            <div className={`text-xl font-bold mt-1 px-3 py-0.5 rounded-full ${
              opportunity?.urgency === "High" ? "bg-red-50 text-red-700 border border-red-100" :
              opportunity?.urgency === "Medium" ? "bg-amber-50 text-amber-700 border border-amber-100" :
              "bg-blue-50 text-blue-700 border border-blue-100"
            }`}>
              {opportunity?.urgency || "Low"}
            </div>
          </div>
        </div>
      </div>

      {/* Tabs list */}
      <div className="flex gap-1 border-b overflow-x-auto">
        {tabs.map((tab) => {
          const Icon = tab.icon;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-1.5 px-4 py-2.5 text-xs font-semibold border-b-2 transition-colors whitespace-nowrap ${
                activeTab === tab.id
                  ? "border-blue-600 text-blue-600 font-bold"
                  : "border-transparent text-slate-500 hover:text-slate-800 hover:border-slate-300"
              }`}
            >
              <Icon className="h-4 w-4" />
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* Tab Panels */}
      <div className="bg-white border border-slate-100 rounded-2xl p-6 shadow-sm">
        {/* Overview Tab */}
        {activeTab === "overview" && (
          <div className="grid md:grid-cols-2 gap-8">
            <div className="space-y-6">
              <h3 className="font-bold text-slate-900 text-sm border-b pb-2">Contact Details</h3>
              <div className="grid grid-cols-2 gap-4 text-xs">
                <div>
                  <span className="text-slate-400 block">Name</span>
                  <span className="font-semibold text-slate-900 block mt-0.5">{lead.name}</span>
                </div>
                <div>
                  <span className="text-slate-400 block">Status</span>
                  <span className="inline-block mt-0.5 font-bold uppercase px-2 py-0.5 rounded bg-blue-50 text-blue-700 border border-blue-100">
                    {lead.status}
                  </span>
                </div>
                <div>
                  <span className="text-slate-400 block">Primary Email</span>
                  <span className="font-semibold text-slate-900 block mt-0.5">{lead.email || "—"}</span>
                </div>
                <div>
                  <span className="text-slate-400 block">Discovery Source</span>
                  <span className="font-semibold text-slate-900 block mt-0.5 capitalize">{lead.discovery_source}</span>
                </div>
              </div>
            </div>

            <div className="space-y-6">
              <h3 className="font-bold text-slate-900 text-sm border-b pb-2">Opportunity Intelligence</h3>
              {opportunity ? (
                <div className="space-y-4 text-xs">
                  <div className="grid grid-cols-2 gap-4">
                    <div className="bg-slate-50 p-3 rounded-xl border border-slate-100">
                      <span className="text-slate-400 block uppercase text-[9px] font-bold">Recommended Contact</span>
                      <span className="font-bold text-slate-800 mt-1 block">{opportunity.best_contact}</span>
                    </div>
                    <div className="bg-slate-50 p-3 rounded-xl border border-slate-100">
                      <span className="text-slate-400 block uppercase text-[9px] font-bold">Opportunity Confidence</span>
                      <span className="font-bold text-slate-800 mt-1 block">{opportunity.confidence_score}%</span>
                    </div>
                  </div>
                  <div className="bg-blue-50/50 p-3.5 rounded-xl border border-blue-100">
                    <span className="text-blue-800 block uppercase text-[9px] font-bold tracking-wider">Offer Proposition</span>
                    <span className="font-semibold text-blue-950 mt-1 block leading-relaxed italic">
                      "{opportunity.recommended_offer}"
                    </span>
                  </div>
                </div>
              ) : (
                <div className="text-center py-6 text-slate-400 text-xs">
                  No Opportunity Agent evaluation has been triggered yet.
                </div>
              )}
            </div>
          </div>
        )}

        {/* Company Research Tab */}
        {activeTab === "research" && (
          <div className="space-y-6">
            <h3 className="font-bold text-slate-900 text-sm border-b pb-2">Agent Enrichment Details</h3>
            {lead.research_data && Object.keys(lead.research_data).length > 0 ? (
              <div className="grid md:grid-cols-2 gap-6 text-xs leading-relaxed">
                <div className="bg-slate-50 p-4 rounded-xl border border-slate-100 space-y-2">
                  <h4 className="font-bold text-slate-800 uppercase text-[10px]">Company Context</h4>
                  <p className="text-slate-600">{lead.research_data.summary || "No description loaded."}</p>
                </div>
                <div className="bg-slate-50 p-4 rounded-xl border border-slate-100 space-y-2">
                  <h4 className="font-bold text-slate-800 uppercase text-[10px]">Identified Pain Points</h4>
                  <ul className="list-disc pl-4 space-y-1 text-slate-600">
                    {lead.research_data.pain_points ? (
                      lead.research_data.pain_points.map((p: string, idx: number) => (
                        <li key={idx}>{p}</li>
                      ))
                    ) : (
                      <li>No specific pain points identified.</li>
                    )}
                  </ul>
                </div>
              </div>
            ) : (
              <div className="text-center py-12 text-slate-400 text-xs space-y-2">
                <p>No research parameters gathered for {lead.company} yet.</p>
              </div>
            )}
          </div>
        )}

        {/* Signals Feed Tab */}
        {activeTab === "signals" && (
          <div className="space-y-6">
            <h3 className="font-bold text-slate-900 text-sm border-b pb-2">Business Signals Feed</h3>
            {signals.length > 0 ? (
              <div className="grid md:grid-cols-2 gap-4">
                {signals.map((sig, idx) => (
                  <div key={idx} className="bg-white border border-slate-150 p-4 rounded-xl space-y-3 hover:shadow-sm transition-shadow text-xs">
                    <div className="flex items-center justify-between">
                      <span className="px-2 py-0.5 bg-blue-50 text-blue-700 font-bold uppercase rounded border border-blue-100 tracking-wider text-[9px]">
                        {sig.category}
                      </span>
                      <div className="text-right">
                        <span className="font-bold text-indigo-600 block">Score: {sig.score}</span>
                        <span className="text-[9px] text-slate-400 block mt-0.5">Freshness: {sig.signal_freshness_score}%</span>
                      </div>
                    </div>
                    <h4 className="font-bold text-slate-900">{sig.signal}</h4>
                    <p className="text-slate-600 leading-relaxed bg-slate-50 p-2 rounded">{sig.description}</p>
                    {sig.hook && (
                      <div className="bg-emerald-50/50 border border-emerald-100 p-2.5 rounded-lg">
                        <span className="text-emerald-800 font-bold uppercase text-[9px] block">Opener Hook:</span>
                        <p className="text-slate-800 italic mt-1 font-medium">"{sig.hook}"</p>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center py-12 text-slate-400 text-xs">
                No signal scraped events registered for this company.
              </div>
            )}
          </div>
        )}

        {/* Campaign Tab */}
        {activeTab === "campaigns" && (
          <div className="space-y-6">
            <h3 className="font-bold text-slate-900 text-sm border-b pb-2">Campaign Flow Sequence</h3>
            {campaign ? (
              <div className="space-y-4">
                <div className="bg-slate-50 p-4 rounded-xl border border-slate-100 flex items-center justify-between">
                  <div>
                    <h4 className="font-bold text-slate-900 text-sm">{campaign.name}</h4>
                    <p className="text-xs text-slate-500 mt-0.5">{campaign.description}</p>
                  </div>
                  <span className="px-2.5 py-0.5 bg-indigo-50 border border-indigo-100 text-indigo-700 font-bold text-xs rounded-full uppercase">
                    Active
                  </span>
                </div>

                <div className="space-y-3">
                  <h4 className="font-bold text-slate-800 text-xs uppercase tracking-wider">Sequence Progression</h4>
                  <div className="space-y-3">
                    {campaign.sequence_steps ? (
                      campaign.sequence_steps.map((step: any, idx: number) => (
                        <div key={idx} className="flex gap-4 items-start text-xs border border-slate-100 rounded-xl p-3 bg-white hover:bg-slate-50/50">
                          <div className="h-6 w-6 rounded-full bg-slate-100 flex items-center justify-center font-bold text-slate-600 shrink-0 mt-0.5">
                            {idx + 1}
                          </div>
                          <div className="space-y-1">
                            <div className="font-bold text-slate-900 flex items-center gap-2">
                              {step.channel.toUpperCase()} 
                              <span className="text-[10px] text-slate-400 font-normal">Day {step.delay_days}</span>
                            </div>
                            {step.subject_template && (
                              <p className="text-[11px] text-slate-500">Subject: {step.subject_template}</p>
                            )}
                            <p className="text-slate-600 whitespace-pre-wrap">{step.body_template || step.notes}</p>
                          </div>
                        </div>
                      ))
                    ) : (
                      <p className="text-slate-400 text-xs">No sequence steps configured for this campaign.</p>
                    )}
                  </div>
                </div>
              </div>
            ) : (
              <div className="text-center py-12 text-slate-400 text-xs">
                This lead is not enrolled in any campaign.
              </div>
            )}
          </div>
        )}

        {/* Memory Tab */}
        {activeTab === "memory" && (
          <div className="space-y-6">
            <div className="flex items-center justify-between border-b pb-2">
              <h3 className="font-bold text-slate-900 text-sm">Indexed Qdrant Knowledge & RAG Context</h3>
              <span className="text-[9px] bg-slate-50 border px-2 py-0.5 rounded text-slate-500 font-medium">
                FastEmbed bge-small-en-v1.5
              </span>
            </div>
            
            <div className="space-y-4">
              <div className="bg-slate-50 p-4 rounded-xl border border-slate-100 text-xs leading-relaxed space-y-1">
                <span className="text-slate-400 uppercase text-[9px] font-bold">Similarity Retrieval Vector</span>
                <p className="text-slate-700">
                  {lead.name} details have been parsed, vectorised, and stored in the Qdrant knowledge base.
                  Similarity queries search this node first to find tone compatibility for draft outreach emails.
                </p>
              </div>

              {lead.personalization_data && Object.keys(lead.personalization_data).length > 0 ? (
                <div className="bg-indigo-50/30 p-4 rounded-xl border border-indigo-100 text-xs leading-relaxed space-y-2">
                  <span className="text-indigo-800 uppercase text-[9px] font-bold tracking-wider">Derived Outreach Angle Hooks</span>
                  <div className="space-y-2">
                    {lead.personalization_data.icebreakers ? (
                      lead.personalization_data.icebreakers.map((hook: string, idx: number) => (
                        <p key={idx} className="italic text-slate-800">
                          "{hook}"
                        </p>
                      ))
                    ) : (
                      <p className="text-slate-500 italic">No derived icebreaker hooks found.</p>
                    )}
                  </div>
                </div>
              ) : (
                <div className="text-center py-6 text-slate-400 text-xs">
                  No personalization hooks stored in vector memories yet.
                </div>
              )}
            </div>
          </div>
        )}

        {/* Engagement Activity Timeline Tab */}
        {activeTab === "activity" && (
          <div className="space-y-6">
            <h3 className="font-bold text-slate-900 text-sm border-b pb-2">Engagement Timeline</h3>
            {engagement && engagement.events?.length > 0 ? (
              <div className="space-y-4 relative border-l border-slate-100 ml-3 pl-6">
                {engagement.events.map((evt: any, idx: number) => (
                  <div key={idx} className="relative text-xs">
                    <span className="absolute -left-[30px] top-1 h-3.5 w-3.5 rounded-full bg-blue-600 border-2 border-white flex items-center justify-center" />
                    <div className="space-y-0.5">
                      <div className="font-bold text-slate-900 capitalize">{evt.event_type} Event</div>
                      <p className="text-slate-500 text-[10px]">{new Date(evt.timestamp).toLocaleString()}</p>
                      {evt.metadata && (
                        <pre className="mt-1 bg-slate-50 border p-2 rounded text-[10px] text-slate-600 overflow-x-auto">
                          {JSON.stringify(evt.metadata, null, 2)}
                        </pre>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center py-12 text-slate-400 text-xs">
                No tracking actions (opens, clicks, replies) captured for this prospect yet.
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
