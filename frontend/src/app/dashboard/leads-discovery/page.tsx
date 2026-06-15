"use client";

import { useState, useEffect } from "react";
import api from "@/services/api";
import { getCampaigns } from "@/services/campaign-api";
import { gatherSignals } from "@/services/signals-api";
import { aiApi } from "@/services/ai-api";
import { 
  Loader2, 
  Search, 
  Sliders, 
  CheckCircle, 
  AlertCircle, 
  Filter, 
  Network, 
  FileText,
  Mail,
  Zap,
  ArrowRight
} from "lucide-react";
import Link from "next/link";

export default function LeadsDiscoveryPage() {
  const [query, setQuery] = useState("");
  const [jobTitles, setJobTitles] = useState("");
  const [locations, setLocations] = useState("");
  const [industry, setIndustry] = useState("");
  
  // Extra SaaS Filters
  const [country, setCountry] = useState("");
  const [companySize, setCompanySize] = useState("");
  const [fundingStage, setFundingStage] = useState("");
  
  const [limit, setLimit] = useState(10);
  const [selectedCampaignId, setSelectedCampaignId] = useState("");
  const [campaigns, setCampaigns] = useState<any[]>([]);
  
  const [loading, setLoading] = useState(false);
  const [campaignsLoading, setCampaignsLoading] = useState(true);
  const [results, setResults] = useState<any[]>([]);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [runs, setRuns] = useState<any[]>([]);
  const [selectedRun, setSelectedRun] = useState<any | null>(null);

  // Action loading states
  const [actionLoading, setActionLoading] = useState<Record<string, string>>({}); // { leadEmail: 'research' | 'outreach' }

  useEffect(() => {
    async function loadInitialData() {
      try {
        setCampaignsLoading(true);
        const [campaignsData, runsData] = await Promise.all([
          getCampaigns().catch(() => []),
          api.get("/discovery/runs").then(res => res.data?.runs || []).catch(() => [])
        ]);
        setCampaigns(campaignsData);
        setRuns(runsData);
        if (campaignsData.length > 0) {
          setSelectedCampaignId(campaignsData[0].id);
        }
        if (runsData.length > 0) {
          handleSelectRun(runsData[0]);
        }
      } catch (err) {
        console.error("Failed to load initial data:", err);
        setError("Could not load initial data. Please try again.");
      } finally {
        setCampaignsLoading(false);
      }
    }
    loadInitialData();
  }, []);

  const handleSelectRun = (run: any) => {
    setSelectedRun(run);
    setResults(run.leads || []);
    setQuery(run.query || "");
    setJobTitles(run.job_titles ? run.job_titles.join(", ") : "");
    setLocations(run.locations ? run.locations.join(", ") : "");
    setIndustry(run.industry || "");
    setCountry(run.country || "");
    setCompanySize(run.company_size || "");
    setFundingStage(run.funding_stage || "");
    setLimit(run.limit || 10);
    if (run.campaign_id) {
      setSelectedCampaignId(run.campaign_id);
    }
  };

  const handleDiscover = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedCampaignId) {
      setError("Please select a target campaign first.");
      return;
    }
    if (!query) {
      setError("Please provide a search prompt.");
      return;
    }

    setLoading(true);
    setError("");
    setSuccess("");
    setResults([]);

    // Compile filters into prompt to guide AI Discovery fallback agents
    let promptQuery = query;
    if (country) promptQuery += `, based in ${country}`;
    if (companySize) promptQuery += `, company size around ${companySize} employees`;
    if (fundingStage) promptQuery += `, funding stage: ${fundingStage}`;

    const payload = {
      campaign_id: selectedCampaignId,
      query: query,
      job_titles: jobTitles ? jobTitles.split(",").map(t => t.trim()) : [],
      locations: locations ? locations.split(",").map(l => l.trim()) : [],
      industry: industry.trim() || undefined,
      country: country.trim() || undefined,
      company_size: companySize || undefined,
      funding_stage: fundingStage || undefined,
      limit: limit
    };

    try {
      const response = await api.post("/discovery/discover-leads", payload);
      if (response.data?.status === "success") {
        setResults(response.data.leads || []);
        setSuccess(`Discovered and imported ${response.data.count} leads successfully!`);
        
        // Reload runs history
        const runsRes = await api.get("/discovery/runs").catch(() => null);
        if (runsRes?.data?.runs) {
          setRuns(runsRes.data.runs);
          if (runsRes.data.runs.length > 0) {
            setSelectedRun(runsRes.data.runs[0]);
          }
        }
      } else {
        setError("Failed to discover leads.");
      }
    } catch (err: any) {
      console.error(err);
      setError(err.response?.data?.detail || "An error occurred during discovery.");
    } finally {
      setLoading(false);
    }
  };

  const runResearch = async (lead: any) => {
    if (!lead.id) return;
    setActionLoading(prev => ({ ...prev, [lead.email]: 'research' }));
    try {
      await gatherSignals({
        lead_id: lead.id,
        company_name: lead.company,
        website_url: lead.website
      });
      alert(`Successfully gathered signals & evaluated opportunity for ${lead.name}!`);
      // Update results array with updated quality score or signals indicator
      setResults(prev => prev.map(r => r.id === lead.id ? { ...r, researched: true } : r));
    } catch (err) {
      console.error(err);
      alert("Failed to gather signals for lead.");
    } finally {
      setActionLoading(prev => ({ ...prev, [lead.email]: '' }));
    }
  };

  const generateOutreach = async (lead: any) => {
    if (!lead.id || !selectedCampaignId) return;
    setActionLoading(prev => ({ ...prev, [lead.email]: 'outreach' }));
    try {
      const res = await aiApi.generateEmail({
        lead_id: lead.id,
        campaign_id: selectedCampaignId,
        tone: "professional"
      });
      alert(`AI Email Draft Generated!\n\nSubject: ${res.subject}\n\nBody:\n${res.body.slice(0, 300)}...`);
    } catch (err) {
      console.error(err);
      alert("Failed to generate outreach email draft.");
    } finally {
      setActionLoading(prev => ({ ...prev, [lead.email]: '' }));
    }
  };

  return (
    <div className="max-w-7xl mx-auto space-y-6 p-4">
      {/* Header Banner */}
      <div
        className="rounded-2xl p-8 border relative overflow-hidden shadow-xl"
        style={{
          background: "linear-gradient(135deg, var(--banner-bg-from) 0%, var(--banner-bg-to) 100%)",
          border: "1px solid var(--banner-border)",
        }}
      >
        <div className="absolute -right-16 -top-16 h-48 w-48 opacity-10 rounded-full blur-3xl pointer-events-none" style={{ background: "radial-gradient(circle, var(--primary) 0%, transparent 70%)" }} />
        <div className="relative z-10 space-y-3">
          <span className="text-[10px] px-3 py-1 rounded-full font-black uppercase tracking-wider" style={{ background: "rgba(124,92,255,0.1)", color: "var(--primary)", border: "1px solid rgba(124,92,255,0.2)" }}>
            Autonomous Lead Discovery
          </span>
          <h1 className="text-3xl font-extrabold tracking-tight" style={{ color: "var(--banner-text)" }}>AI Prospecting Agent</h1>
          <p className="max-w-2xl text-sm leading-relaxed" style={{ color: "var(--banner-desc)" }}>
            Specify a target prospect description. The discovery agent will resolve queries using a priority fallback workflow:
            <span className="font-semibold" style={{ color: "var(--banner-text)" }}> Apollo.io &rarr; Tavily News API &rarr; Firecrawl Scraping &rarr; Hunter verification</span>.
          </p>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-4">
        {/* Settings and Filters Sidebar */}
        <div className="lg:col-span-1 rounded-2xl p-5 space-y-5" style={{ background: "var(--card-bg)", border: "1px solid var(--card-border)", boxShadow: "var(--card-shadow)" }}>
          <div className="flex items-center gap-2 pb-3" style={{ borderBottom: "1px solid var(--card-border)" }}>
            <Sliders className="h-5 w-5" style={{ color: "var(--primary)" }} />
            <h2 className="font-bold text-sm" style={{ color: "var(--foreground-color)" }}>Prospecting Filters</h2>
          </div>

          <form onSubmit={handleDiscover} className="space-y-4">
            <div>
              <label className="block text-[10px] font-bold uppercase tracking-wider mb-1.5" style={{ color: "var(--sidebar-text-muted)" }}>Target Campaign</label>
              {campaignsLoading ? (
                <div className="flex items-center gap-2 text-xs py-1" style={{ color: "var(--sidebar-text-muted)" }}>
                  <Loader2 className="h-3 w-3 animate-spin" /> Loading campaigns...
                </div>
              ) : (
                <select
                  value={selectedCampaignId}
                  onChange={(e) => setSelectedCampaignId(e.target.value)}
                  style={{ width: "100%", borderRadius: "8px", padding: "8px 12px", fontSize: "12px", background: "var(--sidebar-toggle-bg)", border: "1px solid var(--card-border)", color: "var(--foreground-color)", outline: "none", fontWeight: 600 }}
                >
                  {campaigns.map((c) => (
                    <option key={c.id} value={c.id}>{c.name}</option>
                  ))}
                </select>
              )}
            </div>

            <div>
              <label className="block text-[10px] font-bold uppercase tracking-wider mb-1.5" style={{ color: "var(--sidebar-text-muted)" }}>Search prompt</label>
              <textarea
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="e.g. Find CTOs of SaaS companies in India"
                style={{ width: "100%", borderRadius: "8px", padding: "8px 12px", fontSize: "12px", background: "var(--sidebar-toggle-bg)", border: "1px solid var(--card-border)", color: "var(--foreground-color)", outline: "none", minHeight: "70px", resize: "none" }}
                required
              />
            </div>

            <div className="space-y-2 pt-3" style={{ borderTop: "1px solid var(--card-border)" }}>
              <span className="text-[10px] font-bold uppercase tracking-wider flex items-center gap-1" style={{ color: "var(--sidebar-text-muted)" }}>
                <Filter className="h-3 w-3" /> Filters Context
              </span>

              {[{ value: jobTitles, onChange: setJobTitles, placeholder: "Titles (CTO, VP Engineering)" },
                { value: locations, onChange: setLocations, placeholder: "Locations (India, United States)" },
                { value: industry, onChange: setIndustry, placeholder: "Industry (Software, FinTech)" },
                { value: country, onChange: setCountry, placeholder: "Country" },
              ].map(({ value, onChange, placeholder }) => (
                <input
                  key={placeholder}
                  type="text"
                  value={value}
                  onChange={(e) => onChange(e.target.value)}
                  placeholder={placeholder}
                  style={{ width: "100%", borderRadius: "8px", padding: "6px 10px", fontSize: "12px", background: "var(--sidebar-toggle-bg)", border: "1px solid var(--card-border)", color: "var(--foreground-color)", outline: "none" }}
                />
              ))}

              <select
                value={companySize}
                onChange={(e) => setCompanySize(e.target.value)}
                style={{ width: "100%", borderRadius: "8px", padding: "6px 10px", fontSize: "12px", background: "var(--sidebar-toggle-bg)", border: "1px solid var(--card-border)", color: "var(--foreground-color)", outline: "none", fontWeight: 500 }}
              >
                <option value="">Company Size</option>
                <option value="1-10">1-10 employees</option>
                <option value="11-50">11-50 employees</option>
                <option value="51-200">51-200 employees</option>
                <option value="201-500">201-500 employees</option>
                <option value="500+">500+ employees</option>
              </select>

              <select
                value={fundingStage}
                onChange={(e) => setFundingStage(e.target.value)}
                style={{ width: "100%", borderRadius: "8px", padding: "6px 10px", fontSize: "12px", background: "var(--sidebar-toggle-bg)", border: "1px solid var(--card-border)", color: "var(--foreground-color)", outline: "none", fontWeight: 500 }}
              >
                <option value="">Funding Stage</option>
                <option value="Seed">Seed</option>
                <option value="Series A">Series A</option>
                <option value="Series B">Series B</option>
                <option value="IPO / Public">IPO / Public</option>
                <option value="Bootstrapped">Bootstrapped</option>
              </select>
            </div>

            <div>
              <label className="block text-[10px] font-bold uppercase tracking-wider mb-1.5" style={{ color: "var(--sidebar-text-muted)" }}>Max Prospects</label>
              <input
                type="number"
                value={limit}
                onChange={(e) => setLimit(parseInt(e.target.value) || 10)}
                style={{ width: "100%", borderRadius: "8px", padding: "6px 10px", fontSize: "12px", background: "var(--sidebar-toggle-bg)", border: "1px solid var(--card-border)", color: "var(--foreground-color)", outline: "none" }}
                min={1}
                max={50}
              />
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full flex items-center justify-center gap-2 rounded-lg py-2.5 text-xs font-bold text-white hover:opacity-90 transition-all shadow-md disabled:opacity-50"
              style={{ background: "var(--primary)" }}
            >
              {loading ? (
                <><Loader2 className="h-4 w-4 animate-spin" /> Probing Targets...</>
              ) : (
                "Search & Import Leads"
              )}
            </button>
          </form>

          {runs.length > 0 && (
            <div className="pt-4 space-y-2" style={{ borderTop: "1px solid var(--card-border)" }}>
              <span className="text-[10px] font-bold uppercase tracking-wider block" style={{ color: "var(--sidebar-text-muted)" }}>History Runs</span>
              <div className="space-y-1.5 max-h-[220px] overflow-y-auto pr-1">
                {runs.map((r, i) => (
                  <button
                    key={i}
                    type="button"
                    onClick={() => handleSelectRun(r)}
                    className="w-full text-left p-2 rounded-lg text-[10px] font-medium truncate block transition-colors hover:opacity-80"
                    style={{
                      background: selectedRun?.id === r.id ? "rgba(124,92,255,0.1)" : "var(--sidebar-toggle-bg)",
                      border: selectedRun?.id === r.id ? "1px solid rgba(124,92,255,0.3)" : "1px solid var(--card-border)",
                      color: "var(--foreground-color)",
                    }}
                  >
                    Query: "{r.query}" ({r.count} leads)
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Results Panel */}
        <div className="lg:col-span-3 space-y-4">
          {error && (
            <div className="flex items-center gap-3 px-4 py-3 rounded-xl text-xs" style={{ background: "rgba(239,68,68,0.1)", color: "#ef4444", border: "1px solid rgba(239,68,68,0.2)" }}>
              <AlertCircle className="h-4 w-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {success && (
            <div className="flex items-center gap-3 px-4 py-3 rounded-xl text-xs" style={{ background: "rgba(16,185,129,0.1)", color: "#10b981", border: "1px solid rgba(16,185,129,0.2)" }}>
              <CheckCircle className="h-4 w-4 shrink-0" />
              <span>{success}</span>
            </div>
          )}

          <div className="rounded-2xl overflow-hidden min-h-[450px] flex flex-col" style={{ background: "var(--card-bg)", border: "1px solid var(--card-border)", boxShadow: "var(--card-shadow)" }}>
            <div className="px-6 py-4 flex items-center justify-between" style={{ background: "var(--sidebar-toggle-bg)", borderBottom: "1px solid var(--card-border)" }}>
              <h2 className="font-bold text-sm" style={{ color: "var(--foreground-color)" }}>Discovered Contacts ({results.length})</h2>
              <div className="flex items-center gap-2 text-xs" style={{ color: "var(--sidebar-text-muted)" }}>
                <Network className="h-4 w-4" /> Fallback Pipeline active
              </div>
            </div>

            {results.length > 0 ? (
              <div className="overflow-x-auto flex-1">
                <table className="w-full text-left text-xs border-collapse">
                  <thead>
                    <tr className="font-bold uppercase tracking-wider text-[10px]" style={{ background: "var(--sidebar-toggle-bg)", borderBottom: "1px solid var(--card-border)", color: "var(--sidebar-text-muted)" }}>
                      <th className="px-6 py-3">Prospect Info</th>
                      <th className="px-6 py-3">Company Details</th>
                      <th className="px-6 py-3">Contact Email</th>
                      <th className="px-6 py-3">Lead Quality</th>
                      <th className="px-6 py-3 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {results.map((r, idx) => (
                      <tr key={idx} className="transition-colors hover:opacity-90" style={{ borderBottom: "1px solid var(--card-border)" }}>
                        <td className="px-6 py-4">
                          <div className="font-semibold" style={{ color: "var(--foreground-color)" }}>{r.name}</div>
                          <div className="text-[10px] mt-0.5" style={{ color: "var(--sidebar-text-muted)" }}>{r.role}</div>
                        </td>
                        <td className="px-6 py-4">
                          <div className="font-medium" style={{ color: "var(--foreground-color)" }}>{r.company}</div>
                          {r.website && (
                            <a href={r.website} target="_blank" rel="noreferrer" className="text-[10px] hover:underline" style={{ color: "var(--sidebar-text-muted)" }}>
                              {r.website}
                            </a>
                          )}
                        </td>
                        <td className="px-6 py-4">
                          <span className="font-medium block" style={{ color: "var(--foreground-color)" }}>{r.email}</span>
                          <span className="inline-flex items-center gap-0.5 rounded px-1 text-[8px] font-bold uppercase mt-1" style={{ background: "rgba(124,92,255,0.1)", color: "var(--primary)", border: "1px solid rgba(124,92,255,0.2)" }}>
                            {r.discovery_source || "apollo"}
                          </span>
                        </td>
                        <td className="px-6 py-4">
                          <div className="flex items-center gap-1">
                            <span className={`inline-block px-1.5 py-0.5 rounded text-[10px] font-bold`} style={{
                              background: r.lead_quality_score >= 80 ? "rgba(16,185,129,0.1)" : r.lead_quality_score >= 50 ? "rgba(245,158,11,0.1)" : "rgba(100,116,139,0.1)",
                              color: r.lead_quality_score >= 80 ? "#10b981" : r.lead_quality_score >= 50 ? "#f59e0b" : "#94a3b8",
                              border: `1px solid ${r.lead_quality_score >= 80 ? "rgba(16,185,129,0.3)" : r.lead_quality_score >= 50 ? "rgba(245,158,11,0.3)" : "rgba(100,116,139,0.3)"}`
                            }}>
                              QS: {r.lead_quality_score || 70}/100
                            </span>
                          </div>
                        </td>
                        <td className="px-6 py-4 text-right space-y-1">
                          <div className="flex justify-end gap-1.5">
                            <button
                              onClick={() => runResearch(r)}
                              disabled={actionLoading[r.email] === 'research'}
                              className="px-2.5 py-1 text-[10px] font-bold rounded-lg flex items-center gap-1 disabled:opacity-50 hover:opacity-80 transition-opacity"
                              style={{ background: "var(--sidebar-toggle-bg)", border: "1px solid var(--card-border)", color: "var(--foreground-color)" }}
                              title="Query news, hiring & expansions"
                            >
                              {actionLoading[r.email] === 'research' ? (
                                <Loader2 className="h-3 w-3 animate-spin" />
                              ) : (
                                <Zap className="h-3 w-3" style={{ color: "#fbbf24" }} />
                              )}
                              Research
                            </button>
                            
                            <button
                              onClick={() => generateOutreach(r)}
                              disabled={actionLoading[r.email] === 'outreach'}
                              className="px-2.5 py-1 text-[10px] font-bold rounded-lg flex items-center gap-1 disabled:opacity-50 hover:opacity-80 transition-opacity"
                              style={{ background: "rgba(124,92,255,0.1)", border: "1px solid rgba(124,92,255,0.2)", color: "var(--primary)" }}
                              title="Autogenerate outreach content"
                            >
                              {actionLoading[r.email] === 'outreach' ? (
                                <Loader2 className="h-3 w-3 animate-spin" />
                              ) : (
                                <Mail className="h-3 w-3" />
                              )}
                              Outreach
                            </button>

                            {r.id && (
                              <Link
                                href={`/dashboard/leads/${r.id}`}
                                className="px-2 py-1 text-[10px] font-bold rounded-lg flex items-center hover:opacity-80 transition-opacity"
                                style={{ background: "rgba(59,130,246,0.1)", border: "1px solid rgba(59,130,246,0.2)", color: "#3b82f6" }}
                              >
                                View Signals <ArrowRight className="h-3 w-3 ml-0.5" />
                              </Link>
                            )}
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="flex-1 flex flex-col items-center justify-center p-8 text-center">
                <Search className="h-12 w-12 mb-3 animate-pulse" style={{ color: "var(--card-border)" }} />
                <p className="font-semibold text-sm" style={{ color: "var(--foreground-color)" }}>No discovery runs executed yet.</p>
                <p className="text-xs max-w-sm mt-1" style={{ color: "var(--sidebar-text-muted)" }}>Configure your search prompt and filters to locate targeted prospects.</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
