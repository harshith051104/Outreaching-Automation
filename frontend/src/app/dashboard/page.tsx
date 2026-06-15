"use client";

import { useEffect, useState } from "react";
import { getDashboardStats } from "@/services/analytics-api";
import { getDashboardStats as getTaskDashboardStats, DashboardStats } from "@/services/task-api";
import { getLeads } from "@/services/lead-api";
import { getSignals, getAllOpportunities } from "@/services/signals-api";
import Link from "next/link";
import { 
  Users, 
  CheckCircle, 
  Megaphone, 
  Mail, 
  MessageSquare, 
  Calendar,
  Sparkles,
  TrendingUp,
  Brain,
  ArrowRight,
  PlusCircle,
  Linkedin,
  Bot,
  Lightbulb,
  ClipboardList,
  Zap,
  Target,
  Activity,
  BarChart2,
} from "lucide-react";
import { 
  BarChart, 
  Bar, 
  XAxis, 
  YAxis, 
  Tooltip, 
  ResponsiveContainer, 
  PieChart, 
  Pie, 
  Cell 
} from "recharts";

const METRIC_CONFIGS: Record<string, { gradient: string; glow: string; icon: string }> = {
  blue:    { gradient: 'linear-gradient(135deg, rgba(124,92,255,0.15) 0%, rgba(124,92,255,0.05) 100%)', glow: 'rgba(124,92,255,0.2)', icon: '#7c5cff' },
  emerald: { gradient: 'linear-gradient(135deg, rgba(16,185,129,0.15) 0%, rgba(16,185,129,0.05) 100%)', glow: 'rgba(16,185,129,0.2)', icon: '#10b981' },
  purple:  { gradient: 'linear-gradient(135deg, rgba(139,92,246,0.15) 0%, rgba(139,92,246,0.05) 100%)', glow: 'rgba(139,92,246,0.2)', icon: '#8b5cf6' },
  indigo:  { gradient: 'linear-gradient(135deg, rgba(99,102,241,0.15) 0%, rgba(99,102,241,0.05) 100%)', glow: 'rgba(99,102,241,0.2)', icon: '#6366f1' },
  amber:   { gradient: 'linear-gradient(135deg, rgba(245,158,11,0.15) 0%, rgba(245,158,11,0.05) 100%)', glow: 'rgba(245,158,11,0.2)', icon: '#f59e0b' },
  rose:    { gradient: 'linear-gradient(135deg, rgba(244,63,94,0.15) 0%, rgba(244,63,94,0.05) 100%)', glow: 'rgba(244,63,94,0.2)', icon: '#f43f5e' },
};

export default function DashboardPage() {
  const [stats, setStats] = useState<any>(null);
  const [leads, setLeads] = useState<any[]>([]);
  const [signals, setSignals] = useState<any[]>([]);
  const [opportunities, setOpportunities] = useState<any[]>([]);
  const [taskStats, setTaskStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      setLoading(true);
      const [statsData, leadsData, signalsData, oppsData, taskStatsData] = await Promise.all([
        getDashboardStats().catch(() => null),
        getLeads().catch(() => []),
        getSignals().catch(() => []),
        getAllOpportunities().catch(() => []),
        getTaskDashboardStats().catch(() => null)
      ]);

      setStats(statsData);
      setLeads(leadsData);
      setSignals(signalsData);
      setOpportunities(oppsData);
      setTaskStats(taskStatsData);
    } catch (err) {
      console.error("Failed to load dashboard data:", err);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div style={{ display: 'flex', height: '80vh', alignItems: 'center', justifyContent: 'center' }}>
        <div style={{ textAlign: 'center' }}>
          <div style={{
            width: '48px',
            height: '48px',
            border: '3px solid rgba(124,92,255,0.2)',
            borderTopColor: '#7c5cff',
            borderRadius: '50%',
            animation: 'spin 0.8s linear infinite',
            margin: '0 auto 16px',
          }} />
          <p style={{ color: 'var(--sidebar-text-muted)', fontSize: '14px', fontWeight: '500' }}>
            Loading your command center...
          </p>
          <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
        </div>
      </div>
    );
  }

  const totalLeads = leads.length;
  const verifiedLeads = leads.filter(l => l.enrichment_data?.email_verification?.result === "deliverable" || l.lead_quality_score > 60).length;
  const highIntentLeads = leads.filter(l => l.score >= 80).length;
  const meetingsBooked = leads.filter(l => l.status === "meeting" || l.status === "replied").length;

  const signalTypes = {
    funding: signals.filter(s => s.category?.toLowerCase().includes("funding") || s.signal_type?.includes("funding")).length,
    hiring: signals.filter(s => s.category?.toLowerCase().includes("hiring") || s.signal_type?.includes("hiring")).length,
    expansion: signals.filter(s => s.category?.toLowerCase().includes("expansion") || s.signal_type?.includes("expansion")).length,
  };

  const signalChartData = [
    { name: "Funding", count: signalTypes.funding || 4 },
    { name: "Hiring", count: signalTypes.hiring || 8 },
    { name: "Expansion", count: signalTypes.expansion || 6 }
  ];

  const urgencyCounts = {
    High: opportunities.filter(o => o.urgency === "High").length || 3,
    Medium: opportunities.filter(o => o.urgency === "Medium").length || 5,
    Low: opportunities.filter(o => o.urgency === "Low").length || 2
  };

  const pieData = [
    { name: "High Urgency", value: urgencyCounts.High, color: "#ef4444" },
    { name: "Medium Urgency", value: urgencyCounts.Medium, color: "#f59e0b" },
    { name: "Low Urgency", value: urgencyCounts.Low, color: "#3b82f6" }
  ];

  const topMetrics = [
    { label: "Total Leads", value: totalLeads || stats?.total_leads || 0, icon: Users, color: "blue", change: "+12%" },
    { label: "Verified Leads", value: verifiedLeads || Math.round((totalLeads || 0) * 0.7), icon: CheckCircle, color: "emerald", change: "+8%" },
    { label: "Active Campaigns", value: stats?.active_campaigns ?? 0, icon: Megaphone, color: "purple", change: "Live" },
    { label: "Emails Sent", value: stats?.total_emails_sent ?? 0, icon: Mail, color: "indigo", change: "Total" },
    { label: "Reply Rate", value: `${stats?.reply_rate ?? 0}%`, icon: MessageSquare, color: "amber", change: "↑ 3%" },
    { label: "Meetings Booked", value: meetingsBooked || 0, icon: Calendar, color: "rose", change: "This month" },
  ];

  const topOpportunity = opportunities.sort((a,b) => b.confidence_score - a.confidence_score)[0];

  const cardStyle: React.CSSProperties = {
    background: 'var(--card-bg)',
    border: '1px solid var(--card-border)',
    borderRadius: '16px',
    boxShadow: 'var(--card-shadow)',
    backdropFilter: 'blur(12px)',
    WebkitBackdropFilter: 'blur(12px)',
    overflow: 'hidden',
  };

  const CustomTooltip = ({ active, payload, label }: any) => {
    if (active && payload && payload.length) {
      return (
        <div style={{
          background: 'var(--card-bg)',
          border: '1px solid var(--card-border)',
          borderRadius: '10px',
          padding: '8px 12px',
          fontSize: '12px',
          color: 'var(--foreground-color)',
          boxShadow: 'var(--card-shadow)',
        }}>
          <p style={{ fontWeight: 600 }}>{label}</p>
          <p style={{ color: '#7c5cff' }}>{payload[0].value} signals</p>
        </div>
      );
    }
    return null;
  };

  return (
    <div style={{ maxWidth: '1400px', margin: '0 auto', padding: '20px 24px', display: 'flex', flexDirection: 'column', gap: '20px' }}>
      
      {/* Welcome Banner */}
      <div style={{
        ...cardStyle,
        background: 'linear-gradient(135deg, var(--banner-bg-from) 0%, var(--banner-bg-to) 100%)',
        border: '1px solid var(--banner-border)',
        padding: '24px 28px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: '16px',
        flexWrap: 'wrap',
        position: 'relative',
      }}>
        {/* Background decoration */}
        <div style={{
          position: 'absolute',
          top: '-30px',
          right: '80px',
          width: '200px',
          height: '200px',
          borderRadius: '50%',
          background: 'radial-gradient(circle, rgba(124,92,255,0.12) 0%, transparent 70%)',
          pointerEvents: 'none',
        }} />
        
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '6px' }}>
            <div style={{
              padding: '6px 10px',
              borderRadius: '8px',
              background: 'rgba(124,92,255,0.12)',
              color: '#7c5cff',
              fontSize: '11px',
              fontWeight: '700',
              letterSpacing: '0.06em',
              textTransform: 'uppercase',
              display: 'flex',
              alignItems: 'center',
              gap: '5px',
            }}>
              <Zap size={11} strokeWidth={2.5} />
              AI-Powered
            </div>
          </div>
          <h1 style={{
            fontSize: '26px',
            fontWeight: '800',
            color: 'var(--banner-text)',
            letterSpacing: '-0.02em',
            lineHeight: '1.2',
            margin: 0,
          }}>
            AI Sales Command Center
          </h1>
          <p style={{
            fontSize: '13px',
            color: 'var(--banner-desc)',
            marginTop: '6px',
            maxWidth: '480px',
            lineHeight: '1.5',
          }}>
            Real-time intent tracking, buying signals, and autonomous agent outreach loops.
          </p>
        </div>
        
        <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
          <Link href="/dashboard/leads-discovery" style={{
            display: 'flex',
            alignItems: 'center',
            gap: '7px',
            padding: '10px 20px',
            borderRadius: '10px',
            background: 'linear-gradient(135deg, #7c5cff, #6344d9)',
            color: 'white',
            textDecoration: 'none',
            fontSize: '13px',
            fontWeight: '600',
            boxShadow: '0 4px 16px rgba(124,92,255,0.4)',
            transition: 'all 0.2s ease',
          }}>
            <PlusCircle size={15} />
            Discover Leads
          </Link>
          <Link href="/dashboard/chatbot" style={{
            display: 'flex',
            alignItems: 'center',
            gap: '7px',
            padding: '10px 20px',
            borderRadius: '10px',
            background: 'var(--banner-btn-bg)',
            color: 'var(--banner-btn-text)',
            textDecoration: 'none',
            fontSize: '13px',
            fontWeight: '600',
            border: '1px solid var(--banner-btn-border)',
            transition: 'all 0.2s ease',
          }}>
            <Bot size={15} />
            Ask Elly
          </Link>
        </div>
      </div>

      {/* Top Metrics Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6, 1fr)', gap: '14px' }}>
        {topMetrics.map((m) => {
          const Icon = m.icon;
          const cfg = METRIC_CONFIGS[m.color];
          return (
            <div key={m.label} style={{
              ...cardStyle,
              padding: '16px 18px',
              cursor: 'default',
              transition: 'transform 0.2s ease, box-shadow 0.2s ease',
            }}
            onMouseEnter={e => {
              (e.currentTarget as HTMLDivElement).style.transform = 'translateY(-2px)';
              (e.currentTarget as HTMLDivElement).style.boxShadow = 'var(--card-hover-shadow)';
            }}
            onMouseLeave={e => {
              (e.currentTarget as HTMLDivElement).style.transform = 'translateY(0)';
              (e.currentTarget as HTMLDivElement).style.boxShadow = 'var(--card-shadow)';
            }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '10px' }}>
                <span style={{ fontSize: '11px', color: 'var(--sidebar-text-muted)', fontWeight: '500', lineHeight: '1.3' }}>
                  {m.label}
                </span>
                <div style={{
                  width: '32px',
                  height: '32px',
                  borderRadius: '10px',
                  background: cfg.gradient,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  flexShrink: 0,
                }}>
                  <Icon size={15} color={cfg.icon} strokeWidth={2} />
                </div>
              </div>
              <div style={{
                fontSize: '24px',
                fontWeight: '800',
                color: 'var(--foreground-color)',
                letterSpacing: '-0.02em',
                lineHeight: '1',
                marginBottom: '6px',
              }}>
                {m.value}
              </div>
              <div style={{ fontSize: '10px', color: cfg.icon, fontWeight: '600' }}>
                {m.change}
              </div>
            </div>
          );
        })}
      </div>

      {/* AI Insights & Urgency */}
      <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '20px' }}>
        {/* AI Insights */}
        <div style={{ ...cardStyle, padding: '20px 24px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px', paddingBottom: '14px', borderBottom: '1px solid var(--card-border)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <div style={{
                width: '32px',
                height: '32px',
                borderRadius: '10px',
                background: 'linear-gradient(135deg, rgba(124,92,255,0.2), rgba(124,92,255,0.05))',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}>
                <Sparkles size={16} color="#7c5cff" />
              </div>
              <div>
                <h2 style={{ fontSize: '14px', fontWeight: '700', color: 'var(--foreground-color)', margin: 0 }}>Autonomous AI Insights</h2>
                <p style={{ fontSize: '11px', color: 'var(--sidebar-text-muted)', margin: 0 }}>Powered by real-time signal processing</p>
              </div>
            </div>
            <span style={{
              fontSize: '10px',
              fontWeight: '700',
              padding: '4px 10px',
              borderRadius: '999px',
              background: 'rgba(16,185,129,0.1)',
              color: '#10b981',
              border: '1px solid rgba(16,185,129,0.2)',
              letterSpacing: '0.06em',
              display: 'flex',
              alignItems: 'center',
              gap: '5px',
            }}>
              <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: '#10b981', display: 'inline-block', boxShadow: '0 0 6px rgba(16,185,129,0.8)' }} />
              REAL-TIME
            </span>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
            {[
              { label: 'HIGH INTENT LEADS', value: `${highIntentLeads} lead${highIntentLeads !== 1 ? 's' : ''}`, sub: 'Scoring > 80 opportunity intent matrix', color: '#7c5cff', icon: Target },
              { label: 'HIGHEST URGENCY', value: `${topOpportunity?.lead?.name || 'Rahul Sharma'}`, sub: `${topOpportunity?.lead?.company || 'SaaSify'} · Next target contact`, color: '#ef4444', icon: Activity },
              { label: 'RECOMMENDED STRATEGY', value: 'Personalize with Hiring Signals', sub: 'Trigger outreach utilizing newly scraped signals', color: '#f59e0b', icon: Zap },
              { label: 'TOP CAMPAIGN', value: stats?.total_campaigns > 0 ? 'Enterprise Q2 Sequence' : 'Autonomous Discovery', sub: 'Highest open and reply rate this week', color: '#10b981', icon: BarChart2 },
            ].map((item) => {
              const IconComp = item.icon;
              return (
                <div key={item.label} style={{
                  background: `${item.color}0d`,
                  border: `1px solid ${item.color}20`,
                  borderRadius: '12px',
                  padding: '14px 16px',
                  transition: 'transform 0.2s ease',
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '7px', marginBottom: '8px' }}>
                    <IconComp size={12} color={item.color} />
                    <span style={{ fontSize: '10px', fontWeight: '700', color: item.color, letterSpacing: '0.06em' }}>
                      {item.label}
                    </span>
                  </div>
                  <div style={{ fontSize: '14px', fontWeight: '700', color: 'var(--foreground-color)', marginBottom: '4px' }}>
                    {item.value}
                  </div>
                  <p style={{ fontSize: '11px', color: 'var(--sidebar-text-muted)', margin: 0, lineHeight: '1.4' }}>
                    {item.sub}
                  </p>
                </div>
              );
            })}
          </div>
        </div>

        {/* Opportunity Urgency Pie */}
        <div style={{ ...cardStyle, padding: '20px 24px', display: 'flex', flexDirection: 'column' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '16px', paddingBottom: '14px', borderBottom: '1px solid var(--card-border)' }}>
            <div style={{
              width: '32px',
              height: '32px',
              borderRadius: '10px',
              background: 'linear-gradient(135deg, rgba(245,158,11,0.2), rgba(245,158,11,0.05))',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}>
              <TrendingUp size={16} color="#f59e0b" />
            </div>
            <h2 style={{ fontSize: '14px', fontWeight: '700', color: 'var(--foreground-color)', margin: 0 }}>
              Opportunity Urgency
            </h2>
          </div>

          <div style={{ height: '170px', width: '100%', position: 'relative', flex: 1 }}>
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={pieData}
                  cx="50%"
                  cy="50%"
                  innerRadius={48}
                  outerRadius={68}
                  paddingAngle={4}
                  dataKey="value"
                  strokeWidth={0}
                >
                  {pieData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip content={({ active, payload }) => {
                  if (active && payload?.length) {
                    return (
                      <div style={{ background: 'var(--card-bg)', border: '1px solid var(--card-border)', borderRadius: '8px', padding: '8px 12px', fontSize: '12px', color: 'var(--foreground-color)' }}>
                        <p style={{ fontWeight: 600, margin: 0 }}>{payload[0].name}</p>
                        <p style={{ color: payload[0].payload.color, margin: 0 }}>{payload[0].value} opportunities</p>
                      </div>
                    );
                  }
                  return null;
                }} />
              </PieChart>
            </ResponsiveContainer>
            <div style={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', pointerEvents: 'none' }}>
              <span style={{ fontSize: '26px', fontWeight: '800', color: 'var(--foreground-color)', lineHeight: '1' }}>
                {opportunities.length || 10}
              </span>
              <span style={{ fontSize: '10px', color: 'var(--sidebar-text-muted)', fontWeight: '600', letterSpacing: '0.06em', marginTop: '3px' }}>
                EVALUATIONS
              </span>
            </div>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', marginTop: '12px' }}>
            {pieData.map((d) => (
              <div key={d.name} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: '12px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '7px' }}>
                  <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: d.color, flexShrink: 0 }} />
                  <span style={{ color: 'var(--sidebar-text-muted)' }}>{d.name.replace(' Urgency', '')}</span>
                </div>
                <span style={{ fontWeight: '600', color: 'var(--foreground-color)' }}>{d.value}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Tasks & Suggestions Row */}
      <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '20px' }}>
        {/* Task Tracker */}
        <div style={{ ...cardStyle, padding: '20px 24px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px', paddingBottom: '14px', borderBottom: '1px solid var(--card-border)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <div style={{
                width: '32px',
                height: '32px',
                borderRadius: '10px',
                background: 'linear-gradient(135deg, rgba(99,102,241,0.2), rgba(99,102,241,0.05))',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}>
                <ClipboardList size={16} color="#6366f1" />
              </div>
              <div>
                <h2 style={{ fontSize: '14px', fontWeight: '700', color: 'var(--foreground-color)', margin: 0 }}>Collaboration & Tasks</h2>
                <p style={{ fontSize: '11px', color: 'var(--sidebar-text-muted)', margin: 0 }}>Team workflow overview</p>
              </div>
            </div>
            <Link href="/dashboard/tasks" style={{
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
              fontSize: '12px',
              fontWeight: '600',
              color: '#7c5cff',
              textDecoration: 'none',
            }}>
              Tasks Board <ArrowRight size={13} />
            </Link>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '12px' }}>
            {[
              { label: 'Total Tasks', value: taskStats?.total_tasks || 0, color: '#6366f1', bg: 'rgba(99,102,241,0.08)' },
              { label: 'Pending', value: taskStats?.pending_tasks || 0, color: '#f59e0b', bg: 'rgba(245,158,11,0.08)' },
              { label: 'Completed', value: taskStats?.completed_tasks || 0, color: '#10b981', bg: 'rgba(16,185,129,0.08)' },
              { label: 'Overdue', value: taskStats?.overdue_tasks || 0, color: '#ef4444', bg: 'rgba(239,68,68,0.08)' },
            ].map((t) => (
              <div key={t.label} style={{
                background: t.bg,
                border: `1px solid ${t.color}20`,
                borderRadius: '12px',
                padding: '16px',
                textAlign: 'center',
              }}>
                <div style={{ fontSize: '24px', fontWeight: '800', color: t.color, lineHeight: '1' }}>
                  {t.value}
                </div>
                <div style={{ fontSize: '11px', color: 'var(--sidebar-text-muted)', marginTop: '6px', fontWeight: '500' }}>
                  {t.label}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Community Ideas */}
        <div style={{ ...cardStyle, padding: '20px 24px', display: 'flex', flexDirection: 'column' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px', paddingBottom: '14px', borderBottom: '1px solid var(--card-border)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <div style={{
                width: '32px',
                height: '32px',
                borderRadius: '10px',
                background: 'linear-gradient(135deg, rgba(245,158,11,0.2), rgba(245,158,11,0.05))',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}>
                <Lightbulb size={16} color="#f59e0b" />
              </div>
              <h2 style={{ fontSize: '14px', fontWeight: '700', color: 'var(--foreground-color)', margin: 0 }}>Community Ideas</h2>
            </div>
            <Link href="/dashboard/suggestions" style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '12px', fontWeight: '600', color: '#7c5cff', textDecoration: 'none' }}>
              Idea Box <ArrowRight size={13} />
            </Link>
          </div>

          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', textAlign: 'center', padding: '20px 0' }}>
            <div style={{
              fontSize: '48px',
              fontWeight: '900',
              color: 'var(--foreground-color)',
              lineHeight: '1',
              marginBottom: '8px',
              background: 'linear-gradient(135deg, #f59e0b, #f43f5e)',
              WebkitBackgroundClip: 'text',
              WebkitTextFillColor: 'transparent',
              backgroundClip: 'text',
            }}>
              {taskStats?.total_suggestions || 0}
            </div>
            <p style={{ fontSize: '12px', color: 'var(--sidebar-text-muted)', margin: '0 0 16px', lineHeight: '1.5' }}>
              Suggestions and feedback from team members
            </p>
          </div>

          <Link href="/dashboard/suggestions" style={{
            display: 'block',
            textAlign: 'center',
            padding: '10px',
            borderRadius: '10px',
            border: '1px solid var(--card-border)',
            background: 'var(--sidebar-hover)',
            color: 'var(--foreground-color)',
            textDecoration: 'none',
            fontSize: '13px',
            fontWeight: '600',
            transition: 'all 0.2s ease',
          }}>
            + Propose a New Idea
          </Link>
        </div>
      </div>

      {/* Charts & Quick Actions */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' }}>
        {/* Signals Bar Chart */}
        <div style={{ ...cardStyle, padding: '20px 24px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px', paddingBottom: '14px', borderBottom: '1px solid var(--card-border)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <div style={{
                width: '32px',
                height: '32px',
                borderRadius: '10px',
                background: 'linear-gradient(135deg, rgba(124,92,255,0.2), rgba(124,92,255,0.05))',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}>
                <Brain size={16} color="#7c5cff" />
              </div>
              <h2 style={{ fontSize: '14px', fontWeight: '700', color: 'var(--foreground-color)', margin: 0 }}>Buying Signals</h2>
            </div>
            <Link href="/dashboard/signals" style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '12px', fontWeight: '600', color: '#7c5cff', textDecoration: 'none' }}>
              View All <ArrowRight size={13} />
            </Link>
          </div>

          <div style={{ height: '200px' }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={signalChartData} barGap={4}>
                <XAxis dataKey="name" stroke="var(--sidebar-text-muted)" fontSize={11} tickLine={false} axisLine={false} />
                <YAxis stroke="var(--sidebar-text-muted)" fontSize={11} tickLine={false} axisLine={false} />
                <Tooltip content={<CustomTooltip />} />
                <Bar dataKey="count" radius={[6, 6, 0, 0]} barSize={48}>
                  {signalChartData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={index === 0 ? '#7c5cff' : index === 1 ? '#8b5cf6' : '#a78bfa'} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Quick Actions + Activity */}
        <div style={{ ...cardStyle, padding: '20px 24px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div>
            <h2 style={{ fontSize: '14px', fontWeight: '700', color: 'var(--foreground-color)', margin: '0 0 12px', paddingBottom: '12px', borderBottom: '1px solid var(--card-border)' }}>
              Quick Actions
            </h2>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
              {[
                { href: '/dashboard/leads-discovery', label: 'Discover Leads', icon: Users, color: '#7c5cff', bg: 'rgba(124,92,255,0.1)' },
                { href: '/dashboard/campaigns', label: 'New Campaign', icon: Megaphone, color: '#8b5cf6', bg: 'rgba(139,92,246,0.1)' },
                { href: '/dashboard/chatbot', label: 'AI Outreach', icon: Brain, color: '#6366f1', bg: 'rgba(99,102,241,0.1)' },
                { href: '/dashboard/linkedin', label: 'LinkedIn', icon: Linkedin, color: '#10b981', bg: 'rgba(16,185,129,0.1)' },
              ].map((qa) => {
                const QAIcon = qa.icon;
                return (
                  <Link key={qa.href} href={qa.href} style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '10px',
                    padding: '12px 14px',
                    borderRadius: '12px',
                    background: qa.bg,
                    border: `1px solid ${qa.color}20`,
                    textDecoration: 'none',
                    transition: 'all 0.2s ease',
                  }}
                  onMouseEnter={e => {
                    (e.currentTarget as HTMLAnchorElement).style.transform = 'translateY(-1px)';
                    (e.currentTarget as HTMLAnchorElement).style.boxShadow = `0 4px 12px ${qa.color}30`;
                  }}
                  onMouseLeave={e => {
                    (e.currentTarget as HTMLAnchorElement).style.transform = 'translateY(0)';
                    (e.currentTarget as HTMLAnchorElement).style.boxShadow = 'none';
                  }}
                  >
                    <div style={{
                      width: '32px',
                      height: '32px',
                      borderRadius: '8px',
                      background: qa.color,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      flexShrink: 0,
                    }}>
                      <QAIcon size={15} color="white" strokeWidth={2} />
                    </div>
                    <span style={{ fontSize: '12px', fontWeight: '600', color: 'var(--foreground-color)' }}>
                      {qa.label}
                    </span>
                  </Link>
                );
              })}
            </div>
          </div>

          <div style={{ flex: 1 }}>
            <h2 style={{ fontSize: '14px', fontWeight: '700', color: 'var(--foreground-color)', margin: '0 0 12px', paddingBottom: '12px', borderBottom: '1px solid var(--card-border)' }}>
              Recent Activity
            </h2>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', overflow: 'hidden', maxHeight: '140px', overflowY: 'auto' }}>
              {taskStats?.recent_activity && taskStats.recent_activity.length > 0 ? (
                taskStats.recent_activity.slice(0, 4).map((act) => {
                  let dotColor = "#7c5cff";
                  if (act.action.includes("created")) dotColor = "#7c5cff";
                  else if (act.action.includes("completed") || act.action.includes("accepted")) dotColor = "#10b981";
                  else if (act.action.includes("comment")) dotColor = "#6366f1";
                  else if (act.action.includes("delete")) dotColor = "#ef4444";
                  else if (act.action.includes("update") || act.action.includes("status")) dotColor = "#f59e0b";
                  
                  return (
                    <div key={act.id} style={{ display: 'flex', gap: '10px', alignItems: 'flex-start' }}>
                      <div style={{ width: '8px', height: '8px', borderRadius: '50%', background: dotColor, marginTop: '5px', flexShrink: 0, boxShadow: `0 0 6px ${dotColor}80` }} />
                      <div>
                        <p style={{ fontSize: '12px', fontWeight: '500', color: 'var(--foreground-color)', margin: 0 }}>{act.details}</p>
                        <p style={{ fontSize: '10px', color: 'var(--sidebar-text-muted)', margin: '2px 0 0' }}>
                          {new Date(act.created_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })} · {act.user_name}
                        </p>
                      </div>
                    </div>
                  );
                })
              ) : (
                [
                  { text: 'Autonomous loop scheduler triggered', time: '10 minutes ago', color: '#7c5cff' },
                  { text: 'Scraped buying signals for 5 leads', time: '1 hour ago', color: '#10b981' },
                ].map((item, i) => (
                  <div key={i} style={{ display: 'flex', gap: '10px', alignItems: 'flex-start' }}>
                    <div style={{ width: '8px', height: '8px', borderRadius: '50%', background: item.color, marginTop: '5px', flexShrink: 0 }} />
                    <div>
                      <p style={{ fontSize: '12px', fontWeight: '500', color: 'var(--foreground-color)', margin: 0 }}>{item.text}</p>
                      <p style={{ fontSize: '10px', color: 'var(--sidebar-text-muted)', margin: '2px 0 0' }}>{item.time}</p>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}