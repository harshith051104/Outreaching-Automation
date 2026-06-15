"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { createCampaign } from "@/services/campaign-api";
import { getGmailAccounts } from "@/services/gmail-api";
import { extractErrorMessage } from "@/utils/error";
import type { GmailAccount } from "@/types/gmail";
import Link from "next/link";

export default function NewCampaignPage() {
  const router = useRouter();
  const [form, setForm] = useState({
    name: "",
    description: "",
    subject_template: "",
    body_template: "",
    gmail_account_id: "",
  });
  const [gmailAccounts, setGmailAccounts] = useState<GmailAccount[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    const fetchAccounts = async () => {
      try {
        const accounts = await getGmailAccounts();
        setGmailAccounts(accounts);
        if (accounts.length > 0) {
          setForm((prev) => ({ ...prev, gmail_account_id: accounts[0].id }));
        }
      } catch (err) {
        console.error("Failed to load Gmail accounts:", err);
      }
    };
    fetchAccounts();
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.gmail_account_id) {
      setError("Please select a Gmail account first.");
      return;
    }
    setLoading(true);
    setError("");

    try {
      const campaign = await createCampaign(form);
      router.push(`/dashboard/campaigns/${campaign.id}`);
    } catch (err: any) {
      setError(extractErrorMessage(err, "Failed to create campaign"));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <h1 className="mb-6 text-2xl font-bold text-gray-900">Create Campaign</h1>

      <div className="rounded-lg bg-white p-6 shadow">
        {error && (
          <div className="mb-4 rounded-md bg-red-50 p-3 text-sm text-red-600">{error}</div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700">Campaign Name *</label>
            <input
              type="text"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 shadow-sm focus:border-blue-500 focus:outline-none"
              required
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700">Description</label>
            <textarea
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
              rows={2}
              className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 shadow-sm focus:border-blue-500 focus:outline-none"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700">Gmail Account *</label>
            <select
              value={form.gmail_account_id}
              onChange={(e) => setForm({ ...form, gmail_account_id: e.target.value })}
              className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 shadow-sm focus:border-blue-500 focus:outline-none bg-white"
              required
            >
              <option value="">Select a Gmail Account</option>
              {gmailAccounts.map((account) => (
                <option key={account.id} value={account.id}>
                  {account.email}
                </option>
              ))}
            </select>
            {gmailAccounts.length === 0 && (
              <p className="mt-1 text-xs text-amber-600">
                You haven't connected any Gmail account yet. <Link href="/dashboard/gmail" className="underline font-medium">Connect Gmail account</Link>
              </p>
            )}
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700">Subject Template</label>
            <input
              type="text"
              value={form.subject_template}
              onChange={(e) => setForm({ ...form, subject_template: e.target.value })}
              placeholder="e.g., Quick question about {company}"
              className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 shadow-sm focus:border-blue-500 focus:outline-none"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700">Email Body Template</label>
            <textarea
              value={form.body_template}
              onChange={(e) => setForm({ ...form, body_template: e.target.value })}
              rows={6}
              placeholder="AI will generate personalized emails based on this template..."
              className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 shadow-sm focus:border-blue-500 focus:outline-none"
            />
          </div>

          <div className="flex gap-4">
            <button
              type="submit"
              disabled={loading}
              className="rounded-md bg-blue-600 px-6 py-2 text-white hover:bg-blue-700 disabled:opacity-50"
            >
              {loading ? "Creating..." : "Create Campaign"}
            </button>
            <Link href="/dashboard/campaigns" className="rounded-md bg-gray-200 px-6 py-2 text-gray-700 hover:bg-gray-300">
              Cancel
            </Link>
          </div>
        </form>
      </div>
    </div>
  );
}