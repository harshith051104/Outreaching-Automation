/**
 * Integrations API Service
 *
 * Manages per-user encrypted API credentials and integration health checks.
 * All sensitive data is stored server-side (encrypted in MongoDB),
 * never in localStorage.
 */

import api from "./api";

export interface IntegrationStatus {
  provider: string;
  label: string;
  connected: boolean;
  last_tested_at: string | null;
  last_test_ok: boolean | null;
  last_error: string;
  updated_at: string | null;
}

export interface TestResult {
  ok: boolean;
  message: string;
}

export interface HealthStatus {
  mongodb: { ok: boolean; message: string };
  qdrant: { ok: boolean; message: string };
  redis: { ok: boolean | null; message: string };
}

// Provider field definitions for the UI
export const PROVIDER_FIELDS: Record<string, { key: string; label: string; placeholder: string; isTextarea?: boolean }[]> = {
  groq: [{ key: "api_key", label: "API Key", placeholder: "gsk_..." }],
  tavily: [{ key: "api_key", label: "API Key", placeholder: "tvly-..." }],
  firecrawl: [{ key: "api_key", label: "API Key", placeholder: "fc-..." }],
  apollo: [{ key: "api_key", label: "API Key", placeholder: "apollo-api-key..." }],
  hunter: [{ key: "api_key", label: "API Key", placeholder: "hunter-api-key..." }],
  linkedin_session: [
    {
      key: "cookie",
      label: "LinkedIn Cookies (JSON array from browser)",
      placeholder: '[{"name":"li_at","value":"...","domain":".linkedin.com",...}]',
      isTextarea: true,
    },
  ],
  google_sheets: [
    { key: "spreadsheet_id", label: "Spreadsheet ID or URL", placeholder: "1TM5J62Vn-..." },
    {
      key: "service_account_json",
      label: "Service Account JSON",
      placeholder: '{"type":"service_account","project_id":"...","private_key":"..."}',
      isTextarea: true,
    },
  ],
};

export const PROVIDER_ICONS: Record<string, string> = {
  groq: "🤖",
  tavily: "🔍",
  firecrawl: "🕷️",
  apollo: "🚀",
  hunter: "🎯",
  linkedin_session: "💼",
  google_sheets: "📊",
  gmail_oauth: "📧",
};

/**
 * Get all integration statuses for the current user.
 */
export async function getIntegrations(): Promise<IntegrationStatus[]> {
  const res = await api.get("/integrations");
  return res.data;
}

/**
 * Save credentials for a provider.
 */
export async function saveIntegration(
  provider: string,
  credentials: Record<string, string>
): Promise<{ message: string }> {
  const res = await api.put(`/integrations/${provider}`, { credentials });
  return res.data;
}

/**
 * Delete credentials for a provider.
 */
export async function deleteIntegration(provider: string): Promise<{ message: string }> {
  const res = await api.delete(`/integrations/${provider}`);
  return res.data;
}

/**
 * Run a live connection test for a provider.
 */
export async function testIntegration(provider: string): Promise<TestResult> {
  const res = await api.post(`/integrations/${provider}/test`);
  return res.data;
}

/**
 * Get infrastructure health status (MongoDB, Qdrant, Redis).
 */
export async function getHealthStatus(): Promise<HealthStatus> {
  const res = await api.get("/integrations/health/all");
  return res.data;
}

/**
 * Extract spreadsheet ID from a full Google Sheets URL or return as-is if it's already an ID.
 */
export function extractSpreadsheetId(urlOrId: string): string {
  const match = urlOrId.match(/\/spreadsheets\/d\/([a-zA-Z0-9-_]+)/);
  return match ? match[1] : urlOrId.trim();
}

/**
 * Get AI configuration settings.
 */
export async function getAiConfig(): Promise<any> {
  const res = await api.get("/integrations/ai-config");
  return res.data;
}

/**
 * Save AI configuration settings.
 */
export async function saveAiConfig(config: any): Promise<{ message: string }> {
  const res = await api.post("/integrations/ai-config", config);
  return res.data;
}
