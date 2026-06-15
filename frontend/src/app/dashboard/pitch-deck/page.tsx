"use client";

import { useEffect, useState } from "react";
import { generatePitchDeck, getPitchDecks, PitchDeck } from "@/services/pitch-deck-api";
import { getCampaigns } from "@/services/campaign-api";
import { 
  FileText, 
  Sparkles, 
  Loader2, 
  AlertCircle, 
  Download, 
  ArrowRight, 
  Presentation,
  Play
} from "lucide-react";

export default function PitchDecksPage() {
  const [campaigns, setCampaigns] = useState<any[]>([]);
  const [decks, setDecks] = useState<PitchDeck[]>([]);
  const [selectedDeck, setSelectedDeck] = useState<PitchDeck | null>(null);
  const [selectedCampaignId, setSelectedCampaignId] = useState("");
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [downloading, setDownloading] = useState(false);

  // Form states
  const [startupName, setStartupName] = useState("");
  const [problem, setProblem] = useState("");
  const [solution, setSolution] = useState("");
  const [market, setMarket] = useState("");
  const [traction, setTraction] = useState("");
  const [competitors, setCompetitors] = useState("");
  const [fundingAsk, setFundingAsk] = useState("");
  const [formError, setFormError] = useState("");

  useEffect(() => {
    loadData();
  }, []);

  const handleSelectDeck = (deck: PitchDeck) => {
    setSelectedDeck(deck);
    setStartupName(deck.startup_name || "");
    setProblem(deck.problem || "");
    setSolution(deck.solution || "");
    setMarket(deck.market_size || "");
    setTraction(deck.traction || "");
    setCompetitors(deck.competitors || "");
    setFundingAsk(deck.funding_ask || "");
    if (deck.campaign_id) {
      setSelectedCampaignId(deck.campaign_id);
    }
  };

  const loadData = async () => {
    try {
      setLoading(true);
      const [campaignsData, decksData] = await Promise.all([
        getCampaigns().catch(() => []),
        getPitchDecks().catch(() => [])
      ]);
      setCampaigns(campaignsData);
      setDecks(decksData);
      if (campaignsData.length > 0) {
        setSelectedCampaignId(campaignsData[0].id);
      }
      if (decksData.length > 0) {
        handleSelectDeck(decksData[0]);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleGenerate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!startupName || !problem || !solution || !market || !fundingAsk) {
      setFormError("Please fill in all core fields to generate the deck summaries.");
      return;
    }
    setFormError("");
    setGenerating(true);
    try {
      const newDeck = await generatePitchDeck({
        campaign_id: selectedCampaignId,
        startup_name: startupName,
        problem,
        solution,
        market,
        traction,
        competitors,
        funding_ask: fundingAsk
      });
      setDecks(prev => [newDeck, ...prev]);
      setSelectedDeck(newDeck);
      alert("Pitch deck slides layout generated successfully!");
    } catch (err) {
      console.error(err);
      setFormError("Failed to run Pitch Deck Writer Crew.");
    } finally {
      setGenerating(false);
    }
  };

  const handleDownload = async () => {
    if (!selectedDeck) return;
    setDownloading(true);
    try {
      // Dynamically load PptxGenJS bundle from CDN if not globally loaded
      if (!(window as any).PptxGenJS) {
        const script = document.createElement("script");
        script.src = "https://cdn.jsdelivr.net/gh/gitbrent/PptxGenJS@3.12.0/dist/pptxgen.bundle.js";
        script.async = true;
        document.body.appendChild(script);
        await new Promise((resolve) => {
          script.onload = resolve;
        });
      }

      const PptxGenJS = (window as any).PptxGenJS;
      const pptx = new PptxGenJS();
      
      // Define master slide style / premium layout
      pptx.layout = "LAYOUT_16x9";

      selectedDeck.slides.forEach((slideData: any) => {
        const slide = pptx.addSlide();
        const type = slideData.slide_type || "default";

        // Determine theme based on slide type
        const isDark = ["cover", "solution", "ask"].includes(type);
        const bgFill = isDark ? "0F172A" : "F8FAFC";
        const titleColor = isDark ? "F8FAFC" : "0F172A";
        const textColor = isDark ? "94A3B8" : "334155";
        const accentColor = isDark ? "6366F1" : "4F46E5";
        const cardBg = isDark ? "1E293B" : "FFFFFF";
        const cardBorder = isDark ? "334155" : "E2E8F0";

        slide.background = { fill: bgFill };

        // 1. COVER SLIDE
        if (type === "cover") {
          // Large main startup name title
          slide.addText(selectedDeck.startup_name, {
            x: 1.0,
            y: 2.2,
            w: 11.3,
            h: 1.2,
            fontSize: 54,
            bold: true,
            color: "6366F1", // Vibrant Indigo accent
            fontFace: "Arial"
          });
          // Deck title
          slide.addText(slideData.title, {
            x: 1.0,
            y: 3.4,
            w: 11.3,
            h: 0.9,
            fontSize: 32,
            bold: true,
            color: titleColor,
            fontFace: "Arial"
          });
          // Subtitle
          if (slideData.subtitle) {
            slide.addText(slideData.subtitle, {
              x: 1.0,
              y: 4.3,
              w: 11.3,
              h: 0.8,
              fontSize: 18,
              color: textColor,
              fontFace: "Arial"
            });
          }
          
          // Draw a visual accent rectangle line on the left edge
          slide.addShape(pptx.ShapeType.rect, {
            x: 0.5,
            y: 2.3,
            w: 0.15,
            h: 2.5,
            fill: "6366F1",
            line: { type: "none" }
          });
        }

        // 2. PROBLEM SLIDE (Split layout: Big Headline Left, Bullet Cards Right)
        else if (type === "problem") {
          // Slide Title
          slide.addText(slideData.title, {
            x: 0.8, y: 0.6, w: 11.7, h: 0.6,
            fontSize: 24, bold: true, color: titleColor, fontFace: "Arial"
          });
          // Subtitle
          if (slideData.subtitle) {
            slide.addText(slideData.subtitle, {
              x: 0.8, y: 1.1, w: 11.7, h: 0.4,
              fontSize: 14, color: textColor, fontFace: "Arial"
            });
          }

          // Left headline box
          slide.addText("The Massive Problem We Are Tackling", {
            x: 0.8, y: 1.8, w: 4.8, h: 2.2,
            fontSize: 28, bold: true, color: "E11D48", // Rose Red
            fontFace: "Arial"
          });

          // Right cards for bullets
          const bullets = slideData.bullets || [];
          bullets.forEach((bullet: string, index: number) => {
            const cardY = 1.8 + (index * 1.3);
            if (cardY < 6.0) {
              // Draw card shape
              slide.addShape(pptx.ShapeType.rect, {
                x: 6.0, y: cardY, w: 6.5, h: 1.1,
                fill: cardBg,
                line: { color: cardBorder, width: 1 }
              });
              // Add number
              slide.addText(`0${index + 1}`, {
                x: 6.2, y: cardY + 0.15, w: 0.6, h: 0.8,
                fontSize: 20, bold: true, color: "E11D48", fontFace: "Arial"
              });
              // Add bullet text
              slide.addText(bullet, {
                x: 6.9, y: cardY + 0.1, w: 5.4, h: 0.9,
                fontSize: 13, color: titleColor, fontFace: "Arial",
                valign: "middle"
              });
            }
          });
        }

        // 3. SOLUTION SLIDE (Premium layout: Left description, Right side-by-side cards)
        else if (type === "solution") {
          slide.addText(slideData.title, {
            x: 0.8, y: 0.6, w: 11.7, h: 0.6,
            fontSize: 24, bold: true, color: titleColor, fontFace: "Arial"
          });
          if (slideData.subtitle) {
            slide.addText(slideData.subtitle, {
              x: 0.8, y: 1.1, w: 11.7, h: 0.4,
              fontSize: 14, color: textColor, fontFace: "Arial"
            });
          }

          // Left Hero text
          slide.addText("The Ultimate Solution", {
            x: 0.8, y: 1.8, w: 4.2, h: 0.4,
            fontSize: 14, bold: true, color: accentColor, fontFace: "Arial"
          });
          slide.addText("A paradigm shift in how companies execute outreach campaigns.", {
            x: 0.8, y: 2.3, w: 4.2, h: 2.2,
            fontSize: 24, bold: true, color: "FFFFFF", fontFace: "Arial"
          });

          // Right side-by-side cards (2 cards)
          const bullets = slideData.bullets || [];
          const cardW = 3.6;
          const cardH = 3.4;
          
          bullets.forEach((bullet: string, index: number) => {
            if (index < 2) {
              const cardX = 5.4 + (index * 4.0);
              slide.addShape(pptx.ShapeType.rect, {
                x: cardX, y: 1.8, w: cardW, h: cardH,
                fill: cardBg,
                line: { color: cardBorder, width: 1 }
              });
              // Icon marker
              slide.addShape(pptx.ShapeType.rect, {
                x: cardX + 0.3, y: 2.1, w: 0.6, h: 0.6,
                fill: "6366F1",
                line: { type: "none" }
              });
              slide.addText("✓", {
                x: cardX + 0.3, y: 2.1, w: 0.6, h: 0.6,
                fontSize: 20, bold: true, color: "FFFFFF", align: "center", fontFace: "Arial"
              });
              // Bullet Text
              slide.addText(bullet, {
                x: cardX + 0.3, y: 2.9, w: cardW - 0.6, h: 2.0,
                fontSize: 14, color: "FFFFFF", fontFace: "Arial"
              });
            }
          });
        }

        // 4. MARKET SLIDE (Dashboard TAM/SAM/SOM callouts)
        else if (type === "market") {
          slide.addText(slideData.title, {
            x: 0.8, y: 0.6, w: 11.7, h: 0.6,
            fontSize: 24, bold: true, color: titleColor, fontFace: "Arial"
          });
          if (slideData.subtitle) {
            slide.addText(slideData.subtitle, {
              x: 0.8, y: 1.1, w: 11.7, h: 0.4,
              fontSize: 14, color: textColor, fontFace: "Arial"
            });
          }

          // Use key_stats if generated
          const stats = slideData.key_stats || [
            { label: "TAM (Total Market)", value: "$10B+" },
            { label: "SAM (Serviceable Market)", value: "$1.5B" },
            { label: "SOM (Obtainable Market)", value: "$250M" }
          ];

          const boxW = 3.6;
          const boxH = 3.2;
          const gap = 0.5;

          stats.forEach((stat: any, index: number) => {
            if (index < 3) {
              const startX = 0.8 + index * (boxW + gap);
              // Draw stat card
              slide.addShape(pptx.ShapeType.rect, {
                x: startX, y: 1.9, w: boxW, h: boxH,
                fill: cardBg,
                line: { color: cardBorder, width: 1 }
              });
              // Big Number
              slide.addText(stat.value, {
                x: startX + 0.2, y: 2.3, w: boxW - 0.4, h: 1.0,
                fontSize: 40, bold: true, color: accentColor, align: "center", fontFace: "Arial"
              });
              // Label
              slide.addText(stat.label, {
                x: startX + 0.2, y: 3.6, w: boxW - 0.4, h: 0.8,
                fontSize: 14, bold: true, color: titleColor, align: "center", fontFace: "Arial"
              });
            }
          });
        }

        // 5. PRODUCT SLIDE (Dashboard Mockup / Clean 2-column features list)
        else if (type === "product") {
          slide.addText(slideData.title, {
            x: 0.8, y: 0.6, w: 11.7, h: 0.6,
            fontSize: 24, bold: true, color: titleColor, fontFace: "Arial"
          });

          // Left side: Mock Dashboard box
          slide.addShape(pptx.ShapeType.rect, {
            x: 0.8, y: 1.8, w: 6.2, h: 3.6,
            fill: "1E293B",
            line: { color: "475569", width: 1 }
          });
          // Draw header bar for mock dashboard
          slide.addShape(pptx.ShapeType.rect, {
            x: 0.8, y: 1.8, w: 6.2, h: 0.5,
            fill: "0F172A",
            line: { type: "none" }
          });
          slide.addText("Outreach System Dashboard", {
            x: 1.1, y: 1.9, w: 4.0, h: 0.3,
            fontSize: 11, bold: true, color: "94A3B8", fontFace: "Arial"
          });
          // Draw decorative circular button inside mock dashboard header
          slide.addShape(pptx.ShapeType.oval, { x: 6.5, y: 1.95, w: 0.2, h: 0.2, fill: "E11D48", line: { type: "none" } });
          slide.addShape(pptx.ShapeType.oval, { x: 6.2, y: 1.95, w: 0.2, h: 0.2, fill: "10B981", line: { type: "none" } });

          // Decorative stats panel inside dashboard
          slide.addShape(pptx.ShapeType.rect, { x: 1.2, y: 2.6, w: 2.4, h: 1.1, fill: "0F172A", line: { type: "none" } });
          slide.addText("94.2%", { x: 1.2, y: 2.7, w: 2.4, h: 0.5, fontSize: 22, bold: true, color: "10B981", align: "center", fontFace: "Arial" });
          slide.addText("Response Accuracy Rate", { x: 1.2, y: 3.2, w: 2.4, h: 0.4, fontSize: 9, color: "94A3B8", align: "center", fontFace: "Arial" });

          slide.addShape(pptx.ShapeType.rect, { x: 4.0, y: 2.6, w: 2.4, h: 1.1, fill: "0F172A", line: { type: "none" } });
          slide.addText("2.4x", { x: 4.0, y: 2.7, w: 2.4, h: 0.5, fontSize: 22, bold: true, color: "6366F1", align: "center", fontFace: "Arial" });
          slide.addText("Conversion Lift", { x: 4.0, y: 3.2, w: 2.4, h: 0.4, fontSize: 9, color: "94A3B8", align: "center", fontFace: "Arial" });

          // Right side: bullet points
          const bullets = slideData.bullets || [];
          bullets.forEach((bullet: string, index: number) => {
            const bulletY = 1.9 + (index * 1.1);
            if (bulletY < 5.5) {
              slide.addShape(pptx.ShapeType.rect, {
                x: 7.4, y: bulletY, w: 5.1, h: 0.9,
                fill: cardBg,
                line: { color: cardBorder, width: 1 }
              });
              slide.addText(bullet, {
                x: 7.6, y: bulletY + 0.1, w: 4.7, h: 0.7,
                fontSize: 12, color: titleColor, fontFace: "Arial", valign: "middle"
              });
            }
          });
        }

        // 6. BUSINESS MODEL (Pricing Card structure)
        else if (type === "business_model") {
          slide.addText(slideData.title, {
            x: 0.8, y: 0.6, w: 11.7, h: 0.6,
            fontSize: 24, bold: true, color: titleColor, fontFace: "Arial"
          });

          // Business plans cards
          const plans = slideData.pricing_plans || [
            { name: "Starter Tier", price: "$99/mo", features: ["100 automated sequences", "Basic reports"] },
            { name: "Pro Tier", price: "$299/mo", features: ["1000 automated sequences", "Full RAG Integration", "Multi-sender inbox"] },
            { name: "Enterprise", price: "Custom", features: ["Unlimited volume", "Dedicated agents", "Custom integrations"] }
          ];

          const planW = 3.6;
          const planH = 3.4;
          const gap = 0.5;

          plans.forEach((plan: any, index: number) => {
            if (index < 3) {
              const startX = 0.8 + index * (planW + gap);
              // Draw plan card
              slide.addShape(pptx.ShapeType.rect, {
                x: startX, y: 1.8, w: planW, h: planH,
                fill: index === 1 ? "EEF2FF" : cardBg, // Highlight Pro plan
                line: { color: index === 1 ? accentColor : cardBorder, width: index === 1 ? 2 : 1 }
              });
              // Tier name
              slide.addText(plan.name, {
                x: startX + 0.2, y: 2.1, w: planW - 0.4, h: 0.4,
                fontSize: 16, bold: true, color: accentColor, align: "center", fontFace: "Arial"
              });
              // Price
              slide.addText(plan.price, {
                x: startX + 0.2, y: 2.5, w: planW - 0.4, h: 0.6,
                fontSize: 28, bold: true, color: titleColor, align: "center", fontFace: "Arial"
              });
              // Features
              const bulletTexts = (plan.features || []).slice(0, 3).map((f: string) => ({
                text: f,
                options: { bullet: true, color: titleColor, fontSize: 11 }
              }));
              slide.addText(bulletTexts, {
                x: startX + 0.3, y: 3.2, w: planW - 0.6, h: 1.8,
                fontFace: "Arial"
              });
            }
          });
        }

        // 7. TRACTION (Dashboards & Metrics)
        else if (type === "traction") {
          slide.addText(slideData.title, {
            x: 0.8, y: 0.6, w: 11.7, h: 0.6,
            fontSize: 24, bold: true, color: titleColor, fontFace: "Arial"
          });
          if (slideData.subtitle) {
            slide.addText(slideData.subtitle, {
              x: 0.8, y: 1.1, w: 11.7, h: 0.4,
              fontSize: 14, color: textColor, fontFace: "Arial"
            });
          }

          // Traction cards
          const stats = slideData.key_stats || [
            { label: "Monthly Recurring Revenue", value: "$45k MRR" },
            { label: "Active Customers", value: "150+ B2B" },
            { label: "MoM Growth Rate", value: "22% MoM" }
          ];

          const statW = 3.6;
          const startY = 1.8;

          stats.forEach((stat: any, index: number) => {
            if (index < 3) {
              const startX = 0.8 + (index * 4.0);
              slide.addShape(pptx.ShapeType.rect, {
                x: startX, y: startY, w: statW, h: 3.2,
                fill: cardBg,
                line: { color: cardBorder, width: 1 }
              });
              // Draw simple growth line or chart background shape inside
              slide.addShape(pptx.ShapeType.rect, {
                x: startX + 0.3, y: startY + 0.3, w: statW - 0.6, h: 0.8,
                fill: "EEF2FF",
                line: { type: "none" }
              });
              slide.addText("📈", {
                x: startX + 0.3, y: startY + 0.3, w: statW - 0.6, h: 0.8,
                fontSize: 28, align: "center", fontFace: "Arial"
              });

              slide.addText(stat.value, {
                x: startX + 0.2, y: startY + 1.4, w: statW - 0.4, h: 0.7,
                fontSize: 32, bold: true, color: accentColor, align: "center", fontFace: "Arial"
              });
              slide.addText(stat.label, {
                x: startX + 0.2, y: startY + 2.2, w: statW - 0.4, h: 0.6,
                fontSize: 13, bold: true, color: titleColor, align: "center", fontFace: "Arial"
              });
            }
          });
        }

        // 8. COMPETITORS (Matrix Grid Table)
        else if (type === "competitors") {
          slide.addText(slideData.title, {
            x: 0.8, y: 0.6, w: 11.7, h: 0.6,
            fontSize: 24, bold: true, color: titleColor, fontFace: "Arial"
          });

          // Read matrix headers and rows
          const matrix = slideData.competitor_matrix || {
            headers: ["Metric/Feature", `Us (${selectedDeck.startup_name})`, "Traditional Agencies", "Generic CRMs"],
            rows: [
              ["AI Agent Routing", "Yes (Motor + Groq)", "No (Manual)", "No (Text Templates)"],
              ["Context Retrieval", "Yes (Qdrant RAG)", "No", "No"],
              ["LinkedIn Integration", "Yes (Strategic)", "No", "Basic Inbox only"],
              ["Response Time", "Realtime (<10s)", "Slow (Days)", "N/A"]
            ]
          };

          // Render Table
          const formattedHeaders = matrix.headers.map((h: string, idx: number) => ({
            text: h,
            options: { bold: true, color: idx === 1 ? "FFFFFF" : "0F172A", fill: idx === 1 ? "4F46E5" : "E2E8F0", align: "center" }
          }));

          const tableRows = [
            formattedHeaders,
            ...matrix.rows.map((row: string[]) => 
              row.map((val: string, colIdx: number) => ({
                text: val,
                options: { 
                  fill: colIdx === 1 ? "EEF2FF" : "FFFFFF",
                  color: colIdx === 1 ? "4F46E5" : "334155",
                  bold: colIdx === 1,
                  align: colIdx === 0 ? "left" : "center"
                }
              }))
            )
          ];

          slide.addTable(tableRows, {
            x: 0.8, y: 1.8, w: 11.3, h: 3.5,
            border: { color: "CBD5E1", pt: 1 },
            colWidths: [3.3, 2.8, 2.6, 2.6]
          });
        }

        // 9. TEAM SLIDE (Key Founders profiles)
        else if (type === "team") {
          slide.addText(slideData.title, {
            x: 0.8, y: 0.6, w: 11.7, h: 0.6,
            fontSize: 24, bold: true, color: titleColor, fontFace: "Arial"
          });

          const team = slideData.team_members || [
            { name: "Alex Mercer", role: "CEO & Co-Founder", background: "Ex-Scale AI Product Lead" },
            { name: "David Chen", role: "CTO & Co-Founder", background: "Ph.D. in NLP, Ex-OpenAI Engineer" }
          ];

          const memberW = 4.8;
          const memberH = 3.2;

          team.forEach((member: any, index: number) => {
            if (index < 2) {
              const startX = 1.3 + (index * 5.6);
              slide.addShape(pptx.ShapeType.rect, {
                x: startX, y: 1.9, w: memberW, h: memberH,
                fill: cardBg,
                line: { color: cardBorder, width: 1 }
              });
              // Member Avatar circular frame representation
              slide.addShape(pptx.ShapeType.oval, {
                x: startX + 1.8, y: 2.2, w: 1.2, h: 1.2,
                fill: "EEF2FF",
                line: { color: "CBD5E1", width: 1 }
              });
              slide.addText("👤", {
                x: startX + 1.8, y: 2.2, w: 1.2, h: 1.2,
                fontSize: 34, align: "center", fontFace: "Arial"
              });
              // Name
              slide.addText(member.name, {
                x: startX + 0.2, y: 3.6, w: memberW - 0.4, h: 0.4,
                fontSize: 16, bold: true, color: accentColor, align: "center", fontFace: "Arial"
              });
              // Role
              slide.addText(member.role, {
                x: startX + 0.2, y: 4.0, w: memberW - 0.4, h: 0.3,
                fontSize: 12, bold: true, color: titleColor, align: "center", fontFace: "Arial"
              });
              // Background
              slide.addText(member.background, {
                x: startX + 0.2, y: 4.4, w: memberW - 0.4, h: 0.6,
                fontSize: 11, color: textColor, align: "center", fontFace: "Arial"
              });
            }
          });
        }

        // 10. ASK SLIDE (Split funding ask amount and allocation chart)
        else if (type === "ask") {
          slide.addText(slideData.title, {
            x: 0.8, y: 0.6, w: 11.7, h: 0.6,
            fontSize: 24, bold: true, color: titleColor, fontFace: "Arial"
          });

          // Left side: Ask amount card
          slide.addShape(pptx.ShapeType.rect, {
            x: 0.8, y: 1.8, w: 5.0, h: 3.4,
            fill: "1E293B",
            line: { color: "334155", width: 1 }
          });
          slide.addText("TOTAL FUNDING ASK", {
            x: 1.0, y: 2.2, w: 4.6, h: 0.4,
            fontSize: 12, bold: true, color: "94A3B8", align: "center", fontFace: "Arial"
          });
          slide.addText(selectedDeck.funding_ask || "$1.5M Seed", {
            x: 1.0, y: 2.8, w: 4.6, h: 0.8,
            fontSize: 38, bold: true, color: "6366F1", align: "center", fontFace: "Arial"
          });
          slide.addText("Targeting 18-month runway for product scaling and team build.", {
            x: 1.0, y: 3.8, w: 4.6, h: 0.8,
            fontSize: 13, color: "CBD5E1", align: "center", fontFace: "Arial"
          });

          // Right side: Use of funds bar rows
          const allocation = slideData.use_of_funds || [
            { area: "Product & Engineering", pct: "45%" },
            { area: "Sales & Marketing", pct: "30%" },
            { area: "Operations & Overhead", pct: "25%" }
          ];

          allocation.forEach((alloc: any, index: number) => {
            const startY = 1.9 + (index * 1.1);
            if (startY < 5.5) {
              // Labels
              slide.addText(`${alloc.area} (${alloc.pct})`, {
                x: 6.8, y: startY, w: 5.3, h: 0.3,
                fontSize: 12, bold: true, color: "FFFFFF", fontFace: "Arial"
              });
              // Background track bar
              slide.addShape(pptx.ShapeType.rect, {
                x: 6.8, y: startY + 0.4, w: 5.3, h: 0.3,
                fill: "334155",
                line: { type: "none" }
              });
              // Fill progress bar representing percentage
              const pctVal = parseFloat(alloc.pct.replace("%", "")) / 100.0;
              const fillW = Math.max(0.1, 5.3 * pctVal);
              slide.addShape(pptx.ShapeType.rect, {
                x: 6.8, y: startY + 0.4, w: fillW, h: 0.3,
                fill: "6366F1",
                line: { type: "none" }
              });
            }
          });
        }

        // DEFAULT SLIDE fallback
        else {
          // Slide Title
          slide.addText(slideData.title, {
            x: 0.8, y: 0.8, w: 8.5, h: 0.8,
            fontSize: 28, bold: true, color: titleColor, fontFace: "Arial"
          });

          // Bullets list formatting
          const formattedBullets = slideData.bullets.map((b: string) => ({
            text: b,
            options: { bullet: true, color: textColor, fontSize: 15, lineSpacing: 24 }
          }));

          slide.addText(formattedBullets, {
            x: 0.8, y: 1.8, w: 8.5, h: 4.0,
            fontFace: "Arial"
          });
        }

        // Footer
        slide.addText(`${selectedDeck.startup_name} Pitch Deck`, {
          x: 0.8,
          y: 6.8,
          w: 4.0,
          h: 0.3,
          fontSize: 10,
          color: "94A3B8"
        });
      });

      pptx.writeFile({ fileName: `${selectedDeck.startup_name.replace(/\s+/g, "_")}_Pitch_Deck.pptx` });
    } catch (err) {
      console.error(err);
      alert("Failed to download presentation. Check console logs.");
    } finally {
      setDownloading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex h-[80vh] items-center justify-center">
        <div className="text-center space-y-3">
          <div className="h-10 w-10 border-4 border-blue-600 border-t-transparent rounded-full animate-spin mx-auto"></div>
          <p className="text-slate-500 font-medium animate-pulse">Running Pitch Deck layout agents...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto space-y-6 p-4">
      {/* Welcome Header */}
      <div className="rounded-2xl bg-gradient-to-r from-slate-950 via-slate-900 to-indigo-950 border border-slate-800 p-6 shadow-xl text-white">
        <div className="space-y-2">
          <span className="bg-indigo-500/10 text-indigo-400 text-xs px-3 py-1 rounded-full font-bold uppercase tracking-wider border border-indigo-500/20">
            Fundraising Pitch Deck Agent
          </span>
          <h1 className="text-2xl font-black tracking-tight">Startup Slide Outline Writer</h1>
          <p className="text-slate-400 text-sm max-w-xl">
            Auto-generate professional 10-slide outline layouts for VC pitches and compile them into PPTX downloads.
          </p>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        {/* Slide Parameters Form */}
        <div className="lg:col-span-1 bg-white border border-slate-100 p-5 rounded-2xl shadow-sm space-y-5">
          <div className="flex items-center gap-2 border-b pb-3">
            <Presentation className="h-5 w-5 text-indigo-600" />
            <h2 className="font-bold text-slate-950 text-sm">Deck Parameters</h2>
          </div>

          <form onSubmit={handleGenerate} className="space-y-4">
            {formError && (
              <div className="flex items-center gap-1.5 text-xs text-red-600 bg-red-50 p-2 rounded-lg border border-red-100">
                <AlertCircle className="h-3.5 w-3.5 shrink-0" />
                <span>{formError}</span>
              </div>
            )}

            <div>
              <label className="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1.5">Startup Name</label>
              <input
                type="text"
                value={startupName}
                onChange={(e) => setStartupName(e.target.value)}
                placeholder="e.g. SaaSify AI"
                className="w-full rounded-lg border border-slate-200 bg-slate-50/50 px-3 py-2 text-xs text-slate-800 outline-none focus:ring-2 focus:ring-blue-500"
                required
              />
            </div>

            <div>
              <label className="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1.5">Problem Statement</label>
              <textarea
                value={problem}
                onChange={(e) => setProblem(e.target.value)}
                placeholder="What core problem do you solve?"
                className="w-full rounded-lg border border-slate-200 bg-slate-50/50 px-3 py-2 text-xs text-slate-800 outline-none focus:ring-2 focus:ring-blue-500 min-h-[50px] resize-none"
                required
              />
            </div>

            <div>
              <label className="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1.5">Solution Value Prop</label>
              <textarea
                value={solution}
                onChange={(e) => setSolution(e.target.value)}
                placeholder="What is your product solution?"
                className="w-full rounded-lg border border-slate-200 bg-slate-50/50 px-3 py-2 text-xs text-slate-800 outline-none focus:ring-2 focus:ring-blue-500 min-h-[50px] resize-none"
                required
              />
            </div>

            <div>
              <label className="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1.5">Market Size</label>
              <input
                type="text"
                value={market}
                onChange={(e) => setMarket(e.target.value)}
                placeholder="e.g. $10B TAM in SaaS"
                className="w-full rounded-lg border border-slate-200 bg-slate-50/50 px-3 py-2 text-xs text-slate-800 outline-none focus:ring-2 focus:ring-blue-500"
                required
              />
            </div>

            <div>
              <label className="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1.5">Traction (Optional)</label>
              <input
                type="text"
                value={traction}
                onChange={(e) => setTraction(e.target.value)}
                placeholder="e.g. $120k ARR, 15% MoM growth"
                className="w-full rounded-lg border border-slate-200 bg-slate-50/50 px-3 py-2 text-xs text-slate-800 outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            <div>
              <label className="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1.5">Competitors (Optional)</label>
              <input
                type="text"
                value={competitors}
                onChange={(e) => setCompetitors(e.target.value)}
                placeholder="e.g. Apollo, Clay, HubSpot"
                className="w-full rounded-lg border border-slate-200 bg-slate-50/50 px-3 py-2 text-xs text-slate-800 outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            <div>
              <label className="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1.5">Funding Ask</label>
              <input
                type="text"
                value={fundingAsk}
                onChange={(e) => setFundingAsk(e.target.value)}
                placeholder="e.g. Raising $1.5M Seed Round"
                className="w-full rounded-lg border border-slate-200 bg-slate-50/50 px-3 py-2 text-xs text-slate-800 outline-none focus:ring-2 focus:ring-blue-500"
                required
              />
            </div>

            <button
              type="submit"
              disabled={generating}
              className="w-full flex items-center justify-center gap-2 rounded-lg bg-blue-600 py-2.5 text-xs font-bold text-white hover:bg-blue-700 transition-all shadow-md disabled:opacity-50"
            >
              {generating ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" /> Sequencing Outline...
                </>
              ) : (
                "Generate Slide Outlines"
              )}
            </button>
          </form>

          {decks.length > 0 && (
            <div className="border-t pt-4 space-y-2">
              <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">Generated Decks</span>
              <div className="space-y-1.5">
                {decks.map((d, i) => (
                  <button
                    key={i}
                    onClick={() => handleSelectDeck(d)}
                    className={`w-full text-left p-2 border rounded-lg text-xs font-medium truncate block transition-colors ${
                      selectedDeck?.id === d.id || (!selectedDeck && i === 0)
                        ? "bg-indigo-50 border-indigo-200 text-indigo-700 font-bold"
                        : "hover:bg-slate-50 border-slate-100 text-slate-600"
                    }`}
                  >
                    {d.startup_name} Deck ({new Date(d.created_at).toLocaleDateString()})
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Slides Preview Panel */}
        <div className="lg:col-span-2 space-y-4">
          {selectedDeck ? (
            <div className="space-y-4">
              <div className="bg-white border border-slate-100 p-4 rounded-xl shadow-sm flex items-center justify-between">
                <div>
                  <h3 className="font-extrabold text-slate-900 text-sm">{selectedDeck.startup_name} Deck Summary</h3>
                  <p className="text-[10px] text-slate-400">Total: {selectedDeck.slides?.length || 0} slide outlines generated</p>
                </div>
                <button
                  onClick={handleDownload}
                  disabled={downloading}
                  className="flex items-center gap-1.5 bg-green-600 hover:bg-green-700 text-white text-xs font-bold px-4 py-2 rounded-xl transition-all shadow-sm disabled:opacity-50"
                >
                  {downloading ? (
                    <>
                      <Loader2 className="h-4.5 w-4.5 animate-spin" /> Compiling...
                    </>
                  ) : (
                    <>
                      <Download className="h-4.5 w-4.5" /> Download PowerPoint
                    </>
                  )}
                </button>
              </div>

              {/* Slider list */}
              <div className="space-y-6 max-h-[70vh] overflow-y-auto pr-1">
                {selectedDeck.slides?.map((slide, idx) => (
                  <div key={idx} className="bg-slate-900 border border-slate-800 text-white p-6 rounded-2xl shadow-md space-y-4 relative overflow-hidden aspect-video flex flex-col justify-between">
                    <div className="space-y-3 relative z-10">
                      <div className="flex justify-between items-center border-b border-slate-800 pb-2">
                        <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Slide #{slide.slide_number}</span>
                        <span className="px-2 py-0.5 bg-blue-600/10 border border-blue-500/20 text-blue-400 text-[9px] font-bold rounded uppercase">
                          {slide.visual_layout_hint || "Bullets"}
                        </span>
                      </div>
                      <h4 className="font-black text-slate-100 text-base">{slide.title}</h4>
                      <ul className="list-disc pl-5 space-y-1.5 text-xs text-slate-300 leading-relaxed font-medium">
                        {slide.bullets?.map((bullet, bIdx) => (
                          <li key={bIdx}>{bullet}</li>
                        ))}
                      </ul>
                    </div>

                    <div className="text-[9px] text-slate-600 uppercase tracking-widest text-right mt-4 relative z-10">
                      {selectedDeck.startup_name} pitch deck
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <div className="bg-white border border-dashed border-slate-200 py-20 text-center text-slate-400 rounded-2xl min-h-[400px] flex flex-col items-center justify-center">
              <Presentation className="h-12 w-12 text-slate-200 animate-pulse mb-3" />
              <p className="font-semibold text-slate-600 text-sm">No Pitch Deck generated yet</p>
              <p className="text-xs max-w-sm mt-1">Configure your startup metrics in the form to generate the outline and download PPTX.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
