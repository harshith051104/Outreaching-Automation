"use client";

import { useEffect, useState } from "react";
import { getCampaigns } from "@/services/campaign-api";
import {
  getCampaignAnalytics,
  getDailyStats,
  getCampaignInsights,
  exportCampaignAnalyticsToSheets,
} from "@/services/analytics-api";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from "recharts";
import Link from "next/link";
import { FileSpreadsheet, AlertCircle, X } from "lucide-react";

export default function AnalyticsPage() {
  const [campaigns, setCampaigns] = useState<any[]>([]);
  const [selectedCampaign, setSelectedCampaign] = useState<string>("");
  const [stats, setStats] = useState<any>(null);
  const [dailyData, setDailyData] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [statsLoading, setStatsLoading] = useState(false);
  const [selectedMetric, setSelectedMetric] = useState<string | null>(null);

  // AI Insights State
  const [insights, setInsights] = useState<any>(null);
  const [insightsLoading, setInsightsLoading] = useState(false);

  // Sheets Export State
  const [exporting, setExporting] = useState(false);
  const [sheetNotification, setSheetNotification] = useState<{ title: string; url: string } | null>(null);
  const [sheetError, setSheetError] = useState<string | null>(null);

  const handleExportSheets = async () => {
    if (!selectedCampaign) return;
    try {
      setExporting(true);
      setSheetNotification(null);
      setSheetError(null);
      
      const result = await exportCampaignAnalyticsToSheets(selectedCampaign, 30);
      if (result && result.spreadsheet_url) {
        setSheetNotification({ title: result.title, url: result.spreadsheet_url });
      }
    } catch (err: any) {
      console.error("Failed to export campaign stats to Google Sheets:", err);
      const errMsg = err.response?.data?.detail || "Failed to sync stats. Please make sure your Google account is connected under Settings.";
      setSheetError(errMsg);
    } finally {
      setExporting(false);
    }
  };

  const handleMetricClick = (metric: string) => {
    setSelectedMetric(prev => prev === metric ? null : metric);
  };

  useEffect(() => {
    loadCampaigns();
  }, []);

  useEffect(() => {
    if (selectedCampaign) {
      loadCampaignStats(selectedCampaign);
      const interval = setInterval(() => {
        loadCampaignStats(selectedCampaign);
      }, 5000);
      return () => clearInterval(interval);
    }
  }, [selectedCampaign]);

  const loadCampaigns = async () => {
    try {
      const data = await getCampaigns();
      setCampaigns(data);
      if (data.length > 0) {
        setSelectedCampaign(data[0].id);
      }
    } catch (err) {
      console.error("Failed to load campaigns:", err);
    } finally {
      setLoading(false);
    }
  };

  const loadCampaignStats = async (campaignId: string) => {
    setStatsLoading(true);
    setInsightsLoading(true);
    setInsights(null);
    try {
      const [analyticsData, dailyBreakdown, insightsData] = await Promise.all([
        getCampaignAnalytics(campaignId),
        getDailyStats(campaignId),
        getCampaignInsights(campaignId).catch(() => null)
      ]);
      setStats(analyticsData);
      setDailyData(dailyBreakdown);
      setInsights(insightsData);
    } catch (err) {
      console.error("Failed to load campaign statistics:", err);
    } finally {
      setStatsLoading(false);
      setInsightsLoading(false);
    }
  };

  const cardStyle: React.CSSProperties = {
    background: 'var(--card-bg)',
    border: '1px solid var(--card-border)',
    borderRadius: '16px',
    boxShadow: 'var(--card-shadow)',
    backdropFilter: 'blur(12px)',
    WebkitBackdropFilter: 'blur(12px)',
  };

  const selectStyle: React.CSSProperties = {
    padding: '9px 12px',
    fontSize: '13px',
    background: 'var(--card-bg)',
    border: '1px solid var(--card-border)',
    borderRadius: '8px',
    color: 'var(--foreground-color)',
    fontFamily: 'inherit',
    outline: 'none',
  };

  if (loading) return <div className="text-[var(--sidebar-text-muted)] p-6">Loading...</div>;

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-3xl font-extrabold text-[var(--foreground-color)] tracking-tight">Campaign Analytics</h1>
        {campaigns.length > 0 && (
          <button
            onClick={handleExportSheets}
            disabled={exporting}
            className="flex items-center gap-1.5 rounded-lg px-4 py-2 text-xs font-bold transition-all shadow-md hover:opacity-90 disabled:opacity-50"
            style={{ background: "rgba(16,185,129,0.15)", color: "#10b981", border: "1px solid rgba(16,185,129,0.3)" }}
          >
            <FileSpreadsheet className="h-4 w-4" /> {exporting ? "Syncing..." : "Sync to Sheets"}
          </button>
        )}
      </div>

      {/* Google Sheets Export Notifications */}
      {sheetNotification && (
        <div className="p-4 rounded-xl flex items-center justify-between gap-4 animate-in fade-in slide-in-from-top-4 duration-300" style={{ background: "rgba(16,185,129,0.1)", border: "1px solid rgba(16,185,129,0.2)", color: "#10b981" }}>
          <div className="flex items-center gap-2 text-xs font-medium">
            <span className="h-2.5 w-2.5 rounded-full bg-emerald-500 animate-pulse shrink-0" />
            <span>
              Google Spreadsheet created successfully: <strong>{sheetNotification.title}</strong>
            </span>
          </div>
          <div className="flex items-center gap-3">
            <a
              href={sheetNotification.url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-xs font-bold underline hover:opacity-80 transition-opacity flex items-center gap-1"
            >
              Open Spreadsheet →
            </a>
            <button onClick={() => setSheetNotification(null)} className="hover:opacity-75 transition-opacity">
              <X className="h-4 w-4" />
            </button>
          </div>
        </div>
      )}

      {sheetError && (
        <div className="p-4 rounded-xl flex items-center justify-between gap-4 animate-in fade-in slide-in-from-top-4 duration-300" style={{ background: "rgba(239,68,68,0.1)", border: "1px solid rgba(239,68,68,0.2)", color: "#ef4444" }}>
          <div className="flex items-center gap-2 text-xs font-medium">
            <AlertCircle className="h-4 w-4 shrink-0" />
            <span>{sheetError}</span>
          </div>
          <button onClick={() => setSheetError(null)} className="hover:opacity-75 transition-opacity">
            <X className="h-4 w-4" />
          </button>
        </div>
      )}

      {campaigns.length === 0 ? (
        <div style={cardStyle} className="p-12 text-center shadow-sm">
          <svg
            className="mx-auto h-12 w-12 text-[var(--sidebar-text-muted)]"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            aria-hidden="true"
          >
            <path
              vectorEffect="non-scaling-stroke"
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2m0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"
            />
          </svg>
          <h3 className="mt-2 text-sm font-semibold text-[var(--foreground-color)]">No campaigns to analyze</h3>
          <p className="mt-1 text-sm text-[var(--sidebar-text-muted)]">Get started by creating a new outreach campaign.</p>
          <div className="mt-6">
            <Link
              href="/dashboard/campaigns/new"
              className="inline-flex items-center rounded-xl bg-[var(--primary)] px-4 py-2.5 text-sm font-semibold text-white shadow-sm hover:brightness-110 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600 transition-all duration-200"
            >
              + Create Campaign
            </Link>
          </div>
        </div>
      ) : (
        <>
          <div style={cardStyle} className="flex flex-col sm:flex-row gap-4 justify-between items-start sm:items-center p-4 shadow-sm">
            <div>
              <label className="block text-xs font-semibold text-[var(--sidebar-text-muted)] uppercase tracking-wider mb-1">
                Select Active Campaign
              </label>
              <select
                value={selectedCampaign}
                onChange={(e) => setSelectedCampaign(e.target.value)}
                style={selectStyle}
                className="block w-full sm:w-64 font-medium transition-all"
              >
                {campaigns.map((c) => (
                  <option key={c.id} value={c.id} style={{ background: 'var(--card-bg)', color: 'var(--foreground-color)' }}>
                    {c.name}
                  </option>
                ))}
              </select>
            </div>
            {statsLoading && <span className="text-xs text-[var(--primary)] font-semibold animate-pulse">Refreshing data...</span>}
          </div>

          <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
            {/* Sent Emails Card */}
            <div 
              onClick={() => handleMetricClick("emails_sent")}
              style={selectedMetric === "emails_sent" ? { ...cardStyle, borderColor: 'var(--primary)', boxShadow: '0 0 16px rgba(124, 92, 255, 0.2)' } : cardStyle}
              className={`cursor-pointer p-6 transition-all duration-200 select-none hover:shadow-md hover:border-[var(--primary)]/45`}
            >
              <div className="text-xs font-semibold text-[var(--sidebar-text-muted)] uppercase tracking-wider flex justify-between items-center">
                <span>Emails Sent</span>
                {selectedMetric === "emails_sent" && <span className="text-[10px] bg-[var(--primary)]/10 text-[var(--primary)] px-1.5 py-0.5 rounded-full font-bold">Focused</span>}
              </div>
              <div className="mt-2 text-3xl font-extrabold text-[var(--primary)]">
                {stats?.emails_sent !== undefined ? stats.emails_sent : 0}
              </div>
              <p className="mt-1 text-xs text-[var(--sidebar-text-muted)]">Total outreach emails sent</p>
            </div>

            {/* Open Rate Card */}
            <div 
              onClick={() => handleMetricClick("opens")}
              style={selectedMetric === "opens" ? { ...cardStyle, borderColor: '#10b981', boxShadow: '0 0 16px rgba(16, 185, 129, 0.2)' } : cardStyle}
              className={`cursor-pointer p-6 transition-all duration-200 select-none hover:shadow-md hover:border-[#10b981]/45`}
            >
              <div className="text-xs font-semibold text-[var(--sidebar-text-muted)] uppercase tracking-wider flex justify-between items-center">
                <span>Open Rate</span>
                {selectedMetric === "opens" && <span className="text-[10px] bg-green-500/10 text-green-500 px-1.5 py-0.5 rounded-full font-bold">Focused</span>}
              </div>
              <div className="mt-2 text-3xl font-extrabold text-green-600">
                {stats?.open_rate !== undefined ? `${stats.open_rate}%` : "0%"}
              </div>
              <p className="mt-1 text-xs text-[var(--sidebar-text-muted)]">Unique opens / emails sent</p>
            </div>

            {/* Click Rate Card */}
            <div 
              onClick={() => handleMetricClick("clicks")}
              style={selectedMetric === "clicks" ? { ...cardStyle, borderColor: '#8b5cf6', boxShadow: '0 0 16px rgba(139, 92, 246, 0.2)' } : cardStyle}
              className={`cursor-pointer p-6 transition-all duration-200 select-none hover:shadow-md hover:border-[#8b5cf6]/45`}
            >
              <div className="text-xs font-semibold text-[var(--sidebar-text-muted)] uppercase tracking-wider flex justify-between items-center">
                <span>Click Rate</span>
                {selectedMetric === "clicks" && <span className="text-[10px] bg-purple-500/10 text-purple-500 px-1.5 py-0.5 rounded-full font-bold">Focused</span>}
              </div>
              <div className="mt-2 text-3xl font-extrabold text-purple-600">
                {stats?.click_rate !== undefined ? `${stats.click_rate}%` : "0%"}
              </div>
              <p className="mt-1 text-xs text-[var(--sidebar-text-muted)]">Total clicks / emails sent</p>
            </div>

            {/* Reply Rate Card */}
            <div 
              onClick={() => handleMetricClick("replies")}
              style={selectedMetric === "replies" ? { ...cardStyle, borderColor: '#f59e0b', boxShadow: '0 0 16px rgba(245, 158, 11, 0.2)' } : cardStyle}
              className={`cursor-pointer p-6 transition-all duration-200 select-none hover:shadow-md hover:border-[#f59e0b]/45`}
            >
              <div className="text-xs font-semibold text-[var(--sidebar-text-muted)] uppercase tracking-wider flex justify-between items-center">
                <span>Reply Rate</span>
                {selectedMetric === "replies" && <span className="text-[10px] bg-orange-500/10 text-orange-500 px-1.5 py-0.5 rounded-full font-bold">Focused</span>}
              </div>
              <div className="mt-2 text-3xl font-extrabold text-orange-600">
                {stats?.reply_rate !== undefined ? `${stats.reply_rate}%` : "0%"}
              </div>
              <p className="mt-1 text-xs text-[var(--sidebar-text-muted)]">Total replies / emails sent</p>
            </div>
          </div>
          
          <div className="text-xs text-[var(--sidebar-text-muted)] italic">
            💡 Tip: Click on any card above to focus the graph on that metric. Click it again to clear focus and show all.
          </div>

          <div style={cardStyle} className="p-6 shadow-sm">
            <h2 className="text-lg font-bold text-[var(--foreground-color)] mb-6">Daily Activity Timeline</h2>
            <div className="h-96 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={dailyData} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--card-border)" />
                  <XAxis dataKey="date" stroke="var(--sidebar-text-muted)" fontSize={12} tickLine={false} />
                  <YAxis stroke="var(--sidebar-text-muted)" fontSize={12} tickLine={false} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "var(--card-bg)",
                      borderRadius: "12px",
                      border: "1px solid var(--card-border)",
                      color: "var(--foreground-color)",
                      boxShadow: "var(--card-shadow)",
                    }}
                    labelStyle={{ color: "var(--foreground-color)" }}
                  />
                  <Legend verticalAlign="top" height={36} />
                  {(!selectedMetric || selectedMetric === "opens") && (
                    <Line type="monotone" dataKey="opens" stroke="#10B981" strokeWidth={2} dot={{ r: 4 }} activeDot={{ r: 6 }} name="Opens" />
                  )}
                  {(!selectedMetric || selectedMetric === "clicks") && (
                    <Line type="monotone" dataKey="clicks" stroke="#8B5CF6" strokeWidth={2} dot={{ r: 4 }} name="Clicks" />
                  )}
                  {(!selectedMetric || selectedMetric === "replies") && (
                    <Line type="monotone" dataKey="replies" stroke="#F59E0B" strokeWidth={2} dot={{ r: 4 }} name="Replies" />
                  )}
                  {(!selectedMetric || selectedMetric === "emails_sent") && (
                    <Line type="monotone" dataKey="emails_sent" stroke="#3B82F6" strokeWidth={2} dot={{ r: 4 }} name="Sent" />
                  )}
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* AI Insights and Recommendations */}
          <div style={cardStyle} className="p-6 shadow-sm space-y-6">
            <div style={{ borderColor: 'var(--card-border)' }} className="flex items-center justify-between border-b pb-3">
              <div>
                <h2 className="text-lg font-bold text-[var(--foreground-color)] flex items-center gap-2">
                  <svg className="h-5 w-5 text-[var(--primary)]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                  </svg>
                  <span>AI-Driven Optimization & Campaign Insights</span>
                </h2>
                <p className="text-xs text-[var(--sidebar-text-muted)] mt-0.5">Strategic campaign performance breakdown and cross-campaign learning history.</p>
              </div>
              {insights?.summary?.performance_grade && (
                <span className={`inline-flex items-center rounded-full px-3 py-1 text-sm font-extrabold shadow-sm ${
                  insights.summary.performance_grade === "A" ? "bg-green-500/10 text-green-400 border border-green-500/20" :
                  insights.summary.performance_grade === "B" ? "bg-blue-500/10 text-blue-400 border border-blue-500/20" :
                  insights.summary.performance_grade === "C" ? "bg-yellow-500/10 text-yellow-400 border border-yellow-500/20" :
                  "bg-red-500/10 text-red-400 border border-red-500/20"
                }`}>
                  Grade: {insights.summary.performance_grade}
                </span>
              )}
            </div>

            {insightsLoading ? (
              <div className="flex flex-col items-center justify-center py-10 space-y-2">
                <div className="h-6 w-6 animate-spin rounded-full border-4 border-[var(--primary)] border-t-transparent"></div>
                <p className="text-xs text-[var(--sidebar-text-muted)]">Consulting campaign learning memory and performance analyst...</p>
              </div>
            ) : insights ? (
              <div className="space-y-6">
                
                {/* Executive Summary */}
                {insights.summary?.overview && (
                  <div style={{ background: 'var(--sidebar-toggle-bg)', borderColor: 'var(--card-border)' }} className="p-4 border rounded-xl">
                    <div className="text-xs font-bold text-[var(--sidebar-text-muted)] uppercase tracking-wider mb-1.5">Executive Summary</div>
                    <p className="text-sm text-[var(--foreground-color)]/90 leading-relaxed">{insights.summary.overview}</p>
                  </div>
                )}

                {/* Campaign Comparison Section */}
                {insights.campaign_comparison && (
                  <div className="rounded-xl border border-[var(--primary)]/20 bg-[var(--primary)]/5 p-4 space-y-3">
                    <div className="flex items-center gap-1.5">
                      <svg className="h-4.5 w-4.5 text-[var(--primary)]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                      </svg>
                      <span className="text-xs font-bold text-[var(--primary)] uppercase tracking-wider">Comparative Insights (Campaign vs Campaigns)</span>
                    </div>
                    <p className="text-xs text-[var(--foreground-color)]/95 leading-relaxed">{insights.campaign_comparison.comparison_summary || "No comparison data loaded."}</p>
                    {insights.campaign_comparison.key_differentiators && insights.campaign_comparison.key_differentiators.length > 0 && (
                      <ul className="list-disc pl-5 text-xs text-[var(--foreground-color)]/90 space-y-1 mt-2">
                        {insights.campaign_comparison.key_differentiators.map((diff: string, i: number) => (
                          <li key={i}>{diff}</li>
                        ))}
                      </ul>
                    )}
                  </div>
                )}

                {/* Learning Memory Insights */}
                {insights.learning_memory_insights && (
                  <div className="grid gap-4 md:grid-cols-2">
                    <div className="rounded-xl border border-green-500/20 bg-green-500/5 p-4">
                      <div className="text-[10px] font-bold text-green-500 uppercase tracking-wider mb-2">Lessons Applied (From Learning Memory)</div>
                      {insights.learning_memory_insights.lessons_applied && insights.learning_memory_insights.lessons_applied.length > 0 ? (
                        <ul className="list-disc pl-4 text-xs text-[var(--foreground-color)]/90 space-y-1">
                          {insights.learning_memory_insights.lessons_applied.map((l: string, i: number) => (
                            <li key={i}>{l}</li>
                          ))}
                        </ul>
                      ) : (
                        <p className="text-xs text-[var(--sidebar-text-muted)]">No past campaign lessons were applied yet.</p>
                      )}
                    </div>
                    <div className="rounded-xl border border-amber-500/20 bg-amber-500/5 p-4">
                      <div className="text-[10px] font-bold text-amber-500 uppercase tracking-wider mb-2">New Learnings Recorded</div>
                      {insights.learning_memory_insights.new_insights_recorded && insights.learning_memory_insights.new_insights_recorded.length > 0 ? (
                        <ul className="list-disc pl-4 text-xs text-[var(--foreground-color)]/90 space-y-1">
                          {insights.learning_memory_insights.new_insights_recorded.map((l: string, i: number) => (
                            <li key={i}>{l}</li>
                          ))}
                        </ul>
                      ) : (
                        <p className="text-xs text-[var(--sidebar-text-muted)]">No new lessons recorded in this cycle.</p>
                      )}
                    </div>
                  </div>
                )}

                {/* Recommendations */}
                {insights.recommendations && insights.recommendations.length > 0 && (
                  <div className="space-y-3">
                    <div className="text-xs font-bold text-[var(--sidebar-text-muted)] uppercase tracking-wider">Strategic Recommendations</div>
                    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                      {insights.recommendations.map((rec: any, i: number) => (
                        <div key={i} style={{ background: 'var(--card-bg)', borderColor: 'var(--card-border)' }} className="rounded-xl border p-4 shadow-sm space-y-2 hover:shadow transition-shadow">
                          <div className="flex items-center justify-between">
                            <span className="inline-flex items-center rounded-full bg-[var(--primary)]/10 text-[var(--primary)] px-2 py-0.5 text-[10px] font-extrabold uppercase border border-[var(--primary)]/20">
                              Priority #{rec.priority || i + 1}
                            </span>
                            <span className={`inline-flex items-center rounded-full px-1.5 py-0.5 text-[9px] font-bold uppercase ${
                              rec.effort === "low" ? "bg-green-500/10 text-green-500 border border-green-500/20" :
                              rec.effort === "medium" ? "bg-amber-500/10 text-amber-500 border border-amber-500/20" :
                              "bg-red-500/10 text-red-500 border border-red-500/20"
                            }`}>
                              {rec.effort} Effort
                            </span>
                          </div>
                          <p className="text-xs font-bold text-[var(--foreground-color)] leading-tight">{rec.action}</p>
                          <div style={{ borderColor: 'var(--card-border)' }} className="text-[10px] text-[var(--sidebar-text-muted)] pt-1.5 border-t">
                            <div>Impact: <span className="font-semibold text-[var(--foreground-color)]">{rec.expected_impact}</span></div>
                            {rec.timeline && <div className="mt-0.5">Timeline: <span className="font-semibold text-[var(--foreground-color)]">{rec.timeline}</span></div>}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

              </div>
            ) : (
              <div className="text-center py-6 text-xs text-[var(--sidebar-text-muted)]">
                Insights could not be generated or parsed for this campaign.
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}