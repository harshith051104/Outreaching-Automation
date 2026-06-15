"use client";

import { useState } from "react";
import { aiApi } from "@/services/ai-api";
import { 
  BookOpen, 
  Search, 
  HelpCircle, 
  ChevronRight, 
  MessageSquare, 
  Mail, 
  Sparkles,
  Award,
  Clock,
  ShieldCheck
} from "lucide-react";

export default function KnowledgeBasePage() {
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<any>(null);
  const [aiAnswer, setAiAnswer] = useState("");

  const handleSearch = async (searchQuery: string) => {
    if (!searchQuery.trim()) return;
    setQuery(searchQuery);
    setLoading(true);
    setResults(null);
    setAiAnswer("");

    try {
      const res = await aiApi.retrieveMemory(searchQuery, 4);
      setResults(res.results);

      // Generate a mock/summarized AI answer based on retrieved vector memories
      const emails = res.results.successful_emails || [];
      const replies = res.results.past_replies || [];
      
      let answer = "";
      if (emails.length > 0 || replies.length > 0) {
        answer = `Based on your semantic search in Qdrant collections, I found relevant matches that may guide your strategy:\n\n`;
        if (emails.length > 0) {
          answer += `1. **Past Successful Emails:** The template matches indicate high performance when emphasizing personalization and immediate values. The best matched hook has a relevance score of ${(emails[0].score * 100).toFixed(0)}%.\n`;
        }
        if (replies.length > 0) {
          answer += `2. **Past Replies Sentiment:** Similar prospects responded favorably to soft CTAs (e.g. "let me know if you have a few minutes next week").\n\n**Recommendation:** Formulate your outreach using conversational tones and refer to signal triggers like "Hiring sales leads" where applicable.`;
        }
      } else {
        answer = "No matching vector records found in Qdrant collections. Try broadening your keywords.";
      }
      setAiAnswer(answer);
    } catch (err) {
      console.error(err);
      setAiAnswer("Failed to retrieve context from the vector database layer.");
    } finally {
      setLoading(false);
    }
  };

  const sampleQuestions = [
    "What hooks worked best?",
    "Which campaign had highest replies?",
    "Show successful healthcare outreach."
  ];

  return (
    <div className="max-w-7xl mx-auto space-y-6 p-4">
      {/* Header Banner */}
      <div className="rounded-2xl bg-gradient-to-r from-slate-950 via-slate-900 to-slate-950 border border-slate-800 p-6 shadow-xl text-white">
        <div className="space-y-2">
          <span className="bg-blue-500/10 text-blue-400 text-xs px-3 py-1 rounded-full font-bold uppercase tracking-wider border border-blue-500/20">
            Qdrant Vector Database
          </span>
          <h1 className="text-2xl font-black tracking-tight">AI Knowledge Base</h1>
          <p className="text-slate-400 text-sm max-w-xl">
            Semantic search query interface searching indexed campaigns, sent emails, and reply logs using FastEmbed embeddings.
          </p>
        </div>
      </div>

      {/* Search Input Card */}
      <div className="bg-white border border-slate-100 p-6 rounded-2xl shadow-sm space-y-4">
        <div className="flex gap-2">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-3 h-4 w-4 text-slate-400" />
            <input
              type="text"
              placeholder="Ask a question or enter keywords to query the vector database..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSearch(query)}
              className="w-full bg-slate-50 border border-slate-200 rounded-xl pl-9 pr-4 py-2.5 text-xs text-slate-900 outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <button
            onClick={() => handleSearch(query)}
            disabled={loading}
            className="px-5 py-2.5 bg-blue-600 hover:bg-blue-700 text-white font-bold text-xs rounded-xl shadow-md transition-all flex items-center gap-1.5 disabled:opacity-50"
          >
            {loading ? "Searching..." : "Search"}
          </button>
        </div>

        <div className="space-y-1.5">
          <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider flex items-center gap-1">
            <HelpCircle className="h-3.5 w-3.5" /> Suggested Queries
          </span>
          <div className="flex flex-wrap gap-2">
            {sampleQuestions.map((q) => (
              <button
                key={q}
                onClick={() => handleSearch(q)}
                className="px-3 py-1.5 bg-slate-50 border border-slate-250 hover:bg-slate-100 hover:border-slate-350 text-xs font-semibold rounded-lg text-slate-700 transition-colors"
              >
                {q}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Results View Grid */}
      {loading ? (
        <div className="flex flex-col items-center justify-center py-20 space-y-3">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-blue-600 border-t-transparent"></div>
          <p className="text-xs text-slate-500 font-medium animate-pulse">Running cosine-similarity search in Qdrant...</p>
        </div>
      ) : results ? (
        <div className="grid gap-6 md:grid-cols-3">
          {/* AI Answer & summary column */}
          <div className="md:col-span-1 bg-white border border-slate-100 rounded-2xl p-5 shadow-sm space-y-4 flex flex-col justify-between">
            <div className="space-y-3">
              <div className="flex items-center gap-1.5 border-b pb-2">
                <Sparkles className="h-4.5 w-4.5 text-indigo-600" />
                <h3 className="font-extrabold text-slate-900 text-xs uppercase tracking-wider">AI Answer Analysis</h3>
              </div>
              <p className="text-xs leading-relaxed text-slate-700 whitespace-pre-wrap">{aiAnswer}</p>
            </div>
            
            <div className="bg-slate-50 border p-3 rounded-xl flex items-center gap-2 mt-4 text-[10px] text-slate-500">
              <ShieldCheck className="h-5 w-5 text-blue-600" />
              <span>Context resolved using bge-small-en-v1.5 and multi-factor ranking algorithms.</span>
            </div>
          </div>

          {/* Retrieved Context Lists */}
          <div className="md:col-span-2 space-y-6">
            {/* Emails Section */}
            <div className="bg-white border border-slate-100 rounded-2xl p-5 shadow-sm space-y-4">
              <div className="flex items-center gap-2 border-b pb-2">
                <Mail className="h-4.5 w-4.5 text-blue-600" />
                <h3 className="font-extrabold text-slate-900 text-xs uppercase tracking-wider">Retrieved Sent Emails ({results.successful_emails?.length || 0})</h3>
              </div>

              {results.successful_emails && results.successful_emails.length > 0 ? (
                <div className="space-y-3">
                  {results.successful_emails.map((item: any, idx: number) => (
                    <div key={idx} className="border border-slate-150 p-3.5 rounded-xl space-y-2 hover:bg-slate-50/20 text-xs">
                      <div className="flex items-center justify-between">
                        <span className="bg-blue-50 border border-blue-150 text-blue-700 text-[10px] font-bold px-2 py-0.5 rounded">
                          Relevance: {(item.score * 100).toFixed(0)}%
                        </span>
                        <div className="text-[10px] text-slate-400 font-semibold space-x-2">
                          <span>Similarity: {(item.qdrant_similarity * 100).toFixed(0)}%</span>
                          <span>Decay: {(item.recency_score * 100).toFixed(0)}%</span>
                        </div>
                      </div>
                      <p className="text-slate-700 italic bg-slate-50/50 p-2.5 rounded-lg font-medium leading-relaxed">
                        "{item.text}"
                      </p>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-slate-400 py-4 italic">No matching emails retrieved.</p>
              )}
            </div>

            {/* Replies Section */}
            <div className="bg-white border border-slate-100 rounded-2xl p-5 shadow-sm space-y-4">
              <div className="flex items-center gap-2 border-b pb-2">
                <MessageSquare className="h-4.5 w-4.5 text-amber-600" />
                <h3 className="font-extrabold text-slate-900 text-xs uppercase tracking-wider">Retrieved Past Replies ({results.past_replies?.length || 0})</h3>
              </div>

              {results.past_replies && results.past_replies.length > 0 ? (
                <div className="space-y-3">
                  {results.past_replies.map((item: any, idx: number) => (
                    <div key={idx} className="border border-slate-150 p-3.5 rounded-xl space-y-2 hover:bg-slate-50/20 text-xs">
                      <div className="flex items-center justify-between">
                        <span className="bg-amber-50 border border-amber-150 text-amber-700 text-[10px] font-bold px-2 py-0.5 rounded">
                          Relevance: {(item.score * 100).toFixed(0)}%
                        </span>
                        <div className="text-[10px] text-slate-400 font-semibold space-x-2">
                          <span>Similarity: {(item.qdrant_similarity * 100).toFixed(0)}%</span>
                          <span>Decay: {(item.recency_score * 100).toFixed(0)}%</span>
                        </div>
                      </div>
                      <p className="text-slate-700 italic bg-slate-50/50 p-2.5 rounded-lg font-medium leading-relaxed">
                        "{item.text}"
                      </p>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-slate-400 py-4 italic">No matching replies retrieved.</p>
              )}
            </div>
          </div>
        </div>
      ) : (
        <div className="bg-white border border-dashed border-slate-200 py-20 text-center text-slate-400 rounded-2xl">
          <BookOpen className="h-10 w-10 mx-auto text-slate-200 mb-2" />
          <h3 className="font-semibold text-slate-600 text-sm">Cosine similarity search is offline</h3>
          <p className="text-xs mt-1">Enter keywords or click a suggested query above to scan long term RAG memories.</p>
        </div>
      )}
    </div>
  );
}
