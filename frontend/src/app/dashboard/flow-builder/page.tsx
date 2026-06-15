"use client";

import { useState, useEffect, useRef } from "react";
import api from "@/services/api";
import {
  Play,
  Save,
  CheckCircle,
  AlertCircle,
  Clock,
  UserCheck,
  Send,
  Linkedin,
  Mail,
  Zap,
  Sliders,
  Plus,
  Trash2,
  List,
  Eye,
  FileText,
  Search,
  Users,
  Grid,
  Bot,
  HelpCircle,
  ThumbsUp,
  ThumbsDown,
  ChevronRight,
  Info,
  Bell
} from "lucide-react";

// Types
interface FlowNode {
  id: string;
  type: string;
  label: string;
  position: { x: number; y: number };
  parameters: Record<string, any>;
}

interface FlowEdge {
  id: string;
  source: string;
  target: string;
  sourceHandle?: string; // 'default' | 'true' | 'false'
}

interface FlowTemplate {
  id: string;
  name: string;
  description: string;
  nodes: FlowNode[];
  edges: FlowEdge[];
  status: string; // 'draft' | 'active'
  created_at: string;
}

interface FlowRun {
  id: string;
  flow_id: string;
  flow_name: string;
  lead_name?: string;
  lead_id?: string;
  status: string; // 'running' | 'completed' | 'failed' | 'waiting_for_approval' | 'waiting_for_delay'
  current_step_id?: string;
  node_states: Record<string, {
    status: string;
    completed_at?: string;
    output?: any;
    error?: string;
    approved?: boolean;
  }>;
  logs: Array<{ timestamp: string; level: string; message: string }>;
  wait_until?: string;
  created_at: string;
}

export default function FlowBuilderPage() {
  const [activeTab, setActiveTab] = useState<"builder" | "monitor">("builder");
  const [flows, setFlows] = useState<FlowTemplate[]>([]);
  const [selectedFlow, setSelectedFlow] = useState<FlowTemplate | null>(null);
  
  // Toast notifications state
  const [toast, setToast] = useState<{ message: string; type: "success" | "error" | "info" } | null>(null);

  const showToast = (message: string, type: "success" | "error" | "info" = "info") => {
    setToast({ message, type });
  };

  // Auto-dismiss toast
  useEffect(() => {
    if (toast) {
      const timer = setTimeout(() => setToast(null), 4000);
      return () => clearTimeout(timer);
    }
  }, [toast]);
  
  // Canvas State
  const [nodes, setNodes] = useState<FlowNode[]>([]);
  const [edges, setEdges] = useState<FlowEdge[]>([]);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  
  // Drag-and-Drop / Interaction
  const [isPanning, setIsPanning] = useState(false);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [zoom, setZoom] = useState(1);
  const [draggingNodeId, setDraggingNodeId] = useState<string | null>(null);
  const [dragOffset, setDragOffset] = useState({ x: 0, y: 0 });
  const [connectingSource, setConnectingSource] = useState<{ nodeId: string; handleId: string } | null>(null);
  const [mousePos, setMousePos] = useState({ x: 0, y: 0 });
  
  // Flows / Monitor
  const [runs, setRuns] = useState<FlowRun[]>([]);
  const [selectedRun, setSelectedRun] = useState<FlowRun | null>(null);
  const [runLogs, setRunLogs] = useState<any[]>([]);
  
  // Form variables
  const [flowName, setFlowName] = useState("");
  const [flowDescription, setFlowDescription] = useState("");

  const canvasRef = useRef<HTMLDivElement>(null);

  // Fetch all templates
  const loadFlows = async () => {
    try {
      const res = await api.get("/flows");
      setFlows(res.data);
      if (res.data.length > 0 && !selectedFlow) {
        selectFlow(res.data[0]);
      }
    } catch (err) {
      console.error("Failed to load flows:", err);
    }
  };

  // Fetch runs
  const loadRuns = async () => {
    try {
      if (selectedFlow) {
        const res = await api.get(`/flows/${selectedFlow.id}/runs`);
        setRuns(res.data);
      }
    } catch (err) {
      console.error("Failed to load flow runs:", err);
    }
  };

  useEffect(() => {
    loadFlows();
  }, []);

  // Live run execution polling
  useEffect(() => {
    if (!selectedFlow) return;

    loadRuns();

    // Fast polling (1.5s) if inspecting an active execution; slower (5s) otherwise
    const isRunActive = selectedRun && (
      selectedRun.status === "running" || 
      selectedRun.status === "waiting_for_approval" || 
      selectedRun.status === "waiting_for_delay"
    );
    const pollInterval = isRunActive ? 1500 : 5000;

    const interval = setInterval(() => {
      loadRuns();
      if (selectedRun) {
        refreshSelectedRun(selectedRun.id);
      }
    }, pollInterval);

    return () => clearInterval(interval);
  }, [selectedFlow, selectedRun?.id, selectedRun?.status]);

  const selectFlow = (flow: FlowTemplate) => {
    setSelectedFlow(flow);
    setFlowName(flow.name);
    setFlowDescription(flow.description);
    setNodes(flow.nodes || []);
    setEdges(flow.edges || []);
    setSelectedNodeId(null);
  };

  const refreshSelectedRun = async (runId: string) => {
    try {
      const res = await api.get(`/flows/runs/${runId}`);
      setSelectedRun(res.data);
      setRunLogs(res.data.logs || []);
    } catch (err) {
      console.error("Failed to get run details:", err);
    }
  };

  // Node templates helper
  const getNodeIcon = (type: string) => {
    switch (type) {
      case "linkedinSearch":
      case "linkedinConnect":
      case "linkedinMessage":
        return <Linkedin className="w-4 h-4 text-sky-400" />;
      case "sendEmail":
        return <Mail className="w-4 h-4 text-emerald-400" />;
      case "delay":
        return <Clock className="w-4 h-4 text-amber-400" />;
      case "condition":
        return <Sliders className="w-4 h-4 text-indigo-400" />;
      case "humanApproval":
        return <UserCheck className="w-4 h-4 text-purple-400" />;
      case "enrichment":
        return <Search className="w-4 h-4 text-pink-400" />;
      case "aiAction":
        return <Bot className="w-4 h-4 text-violet-400" />;
      case "sendNotification":
        return <Bell className="w-4 h-4 text-teal-400" />;
      case "csvUpload":
        return <FileText className="w-4 h-4 text-sky-300" />;
      default:
        return <Zap className="w-4 h-4 text-purple-400" />;
    }
  };

  const getNodeColorClass = (type: string) => {
    switch (type) {
      case "linkedinSearch":
      case "linkedinConnect":
      case "linkedinMessage":
        return "border-sky-500/30 bg-sky-950/40 text-sky-200 shadow-[0_0_12px_rgba(56,189,248,0.05)]";
      case "sendEmail":
        return "border-emerald-500/30 bg-emerald-950/40 text-emerald-200 shadow-[0_0_12px_rgba(52,211,153,0.05)]";
      case "delay":
        return "border-amber-500/30 bg-amber-950/40 text-amber-200 shadow-[0_0_12px_rgba(251,191,36,0.05)]";
      case "condition":
        return "border-indigo-500/30 bg-indigo-950/40 text-indigo-200 shadow-[0_0_12px_rgba(99,102,241,0.05)]";
      case "humanApproval":
        return "border-purple-500/30 bg-purple-950/40 text-purple-200 shadow-[0_0_12px_rgba(168,85,247,0.05)]";
      case "enrichment":
        return "border-pink-500/30 bg-pink-950/40 text-pink-200 shadow-[0_0_12px_rgba(244,114,182,0.05)]";
      case "aiAction":
        return "border-violet-500/30 bg-violet-950/40 text-violet-200 shadow-[0_0_12px_rgba(139,92,246,0.05)]";
      case "sendNotification":
        return "border-teal-500/30 bg-teal-950/40 text-teal-200 shadow-[0_0_12px_rgba(20,184,166,0.05)]";
      default:
        return "border-purple-500/30 bg-purple-950/40 text-purple-200 shadow-[0_0_12px_rgba(124,92,255,0.05)]";
    }
  };

  // Node Dragging Handlers
  const handleNodeMouseDown = (e: React.MouseEvent, nodeId: string) => {
    e.stopPropagation();
    const node = nodes.find(n => n.id === nodeId);
    if (!node) return;
    
    // Calculate click offset inside the node box
    const rect = (e.currentTarget as HTMLElement).getBoundingClientRect();
    setDraggingNodeId(nodeId);
    setDragOffset({
      x: e.clientX - rect.left,
      y: e.clientY - rect.top
    });
    setSelectedNodeId(nodeId);
  };

  // Canvas Handlers
  const handleCanvasMouseMove = (e: React.MouseEvent) => {
    if (!canvasRef.current) return;
    const rect = canvasRef.current.getBoundingClientRect();
    
    // Track relative canvas position under zoom/pan
    const x = (e.clientX - rect.left - pan.x) / zoom;
    const y = (e.clientY - rect.top - pan.y) / zoom;
    setMousePos({ x, y });

    if (draggingNodeId) {
      // Drag node
      const nextNodes = nodes.map(node => {
        if (node.id === draggingNodeId) {
          return {
            ...node,
            position: {
              x: Math.round((e.clientX - rect.left - dragOffset.x - pan.x) / zoom),
              y: Math.round((e.clientY - rect.top - dragOffset.y - pan.y) / zoom)
            }
          };
        }
        return node;
      });
      setNodes(nextNodes);
    } else if (isPanning) {
      // Pan canvas
      setPan(prev => ({
        x: prev.x + e.movementX,
        y: prev.y + e.movementY
      }));
    }
  };

  const handleCanvasMouseUp = (e: React.MouseEvent) => {
    setDraggingNodeId(null);
    setIsPanning(false);
    setConnectingSource(null);
  };

  const handleCanvasMouseDown = (e: React.MouseEvent) => {
    // Left-click pan startup
    if (e.target === canvasRef.current || (e.target as HTMLElement).tagName === "svg") {
      setIsPanning(true);
      setSelectedNodeId(null);
    }
  };

  // Connections
  const handleConnectorMouseDown = (e: React.MouseEvent, nodeId: string, handleId: string) => {
    e.stopPropagation();
    e.preventDefault();
    setConnectingSource({ nodeId, handleId });
  };

  const handleConnectorMouseUp = (e: React.MouseEvent, targetNodeId: string) => {
    e.stopPropagation();
    if (connectingSource && connectingSource.nodeId !== targetNodeId) {
      // Verify duplicate edge doesn't exist
      const edgeId = `e-${connectingSource.nodeId}-${targetNodeId}`;
      const duplicate = edges.some(edge => edge.source === connectingSource.nodeId && edge.target === targetNodeId);
      
      if (!duplicate) {
        const newEdge: FlowEdge = {
          id: edgeId,
          source: connectingSource.nodeId,
          target: targetNodeId,
          sourceHandle: connectingSource.handleId
        };
        setEdges(prev => [...prev, newEdge]);
      }
    }
    setConnectingSource(null);
  };

  // Add Node from Palette
  const addNode = (type: string, label: string) => {
    const defaultParams: Record<string, any> = {};
    if (type === "delay") {
      defaultParams.delay = 1;
      defaultParams.unit = "days";
    } else if (type === "condition") {
      defaultParams.condition_type = "has_email";
    }

    const newNode: FlowNode = {
      id: `${type}-${Date.now()}`,
      type,
      label,
      position: {
        x: Math.round((400 - pan.x) / zoom),
        y: Math.round((250 - pan.y) / zoom)
      },
      parameters: defaultParams
    };

    setNodes(prev => [...prev, newNode]);
    setSelectedNodeId(newNode.id);
  };

  const deleteNode = (nodeId: string) => {
    setNodes(prev => prev.filter(n => n.id !== nodeId));
    setEdges(prev => prev.filter(edge => edge.source !== nodeId && edge.target !== nodeId));
    if (selectedNodeId === nodeId) {
      setSelectedNodeId(null);
    }
  };

  const deleteEdge = (edgeId: string) => {
    setEdges(prev => prev.filter(edge => edge.id !== edgeId));
  };

  // Math coordinates helpers for drawing connections
  const getNodeCoordinates = (nodeId: string) => {
    const node = nodes.find(n => n.id === nodeId);
    if (!node) return { inX: 0, inY: 0, outX: 0, outY: 0, outTrueX: 0, outTrueY: 0, outFalseX: 0, outFalseY: 0 };
    
    const w = 210; // width
    const h = 76;  // height
    
    return {
      inX: node.position.x,
      inY: node.position.y + h / 2,
      outX: node.position.x + w,
      outY: node.position.y + h / 2,
      // Condition handles
      outTrueX: node.position.x + w,
      outTrueY: node.position.y + 24,
      outFalseX: node.position.x + w,
      outFalseY: node.position.y + 52
    };
  };

  const getBezierPath = (x1: number, y1: number, x2: number, y2: number) => {
    const dx = Math.abs(x2 - x1) * 0.5;
    return `M ${x1} ${y1} C ${x1 + dx} ${y1}, ${x2 - dx} ${y2}, ${x2} ${y2}`;
  };

  // Flow template operations
  const saveFlow = async () => {
    if (!selectedFlow) return;
    try {
      await api.put(`/flows/${selectedFlow.id}`, {
        name: flowName,
        description: flowDescription,
        nodes,
        edges
      });
      loadFlows();
      showToast("Flow successfully saved.", "success");
    } catch (err) {
      console.error(err);
      showToast("Failed to save flow template.", "error");
    }
  };

  const publishFlow = async () => {
    if (!selectedFlow) return;
    try {
      await api.post(`/flows/${selectedFlow.id}/publish`);
      loadFlows();
      showToast("Flow successfully published and active.", "success");
    } catch (err) {
      console.error(err);
      showToast("Failed to publish flow.", "error");
    }
  };

  const createNewFlow = async () => {
    try {
      const res = await api.post("/flows", {
        name: "New Flow Builder Template",
        description: "Visual automation sequence",
        nodes: [
          { id: "trigger-1", type: "csvUpload", label: "CSV Upload Source", position: { x: 50, y: 150 }, parameters: {} }
        ],
        edges: []
      });
      setFlows(prev => [...prev, res.data]);
      selectFlow(res.data);
      showToast("New flow canvas template initialized.", "success");
    } catch (err) {
      console.error(err);
      showToast("Failed to create new flow.", "error");
    }
  };

  const deleteFlowTemplate = async (id: string) => {
    if (!confirm("Are you sure you want to delete this visual campaign flow?")) return;
    try {
      await api.delete(`/flows/${id}`);
      setFlows(prev => prev.filter(f => f.id !== id));
      if (selectedFlow?.id === id) {
        setSelectedFlow(null);
        setNodes([]);
        setEdges([]);
      }
      showToast("Flow successfully deleted.", "success");
    } catch (err) {
      console.error(err);
      showToast("Failed to delete campaign flow.", "error");
    }
  };

  const triggerFlowRun = async () => {
    if (!selectedFlow) return;
    try {
      const res = await api.post(`/flows/${selectedFlow.id}/trigger`);
      const runsCount = res.data.run_ids?.length || 0;
      showToast(`Visual execution run triggered! Active execution threads: ${runsCount}`, "success");
      loadRuns();
      if (res.data.run_ids && res.data.run_ids.length > 0) {
        const newRunId = res.data.run_ids[0];
        // Automatically select the new run to display the visual execution paths in real-time
        await refreshSelectedRun(newRunId);
      }
    } catch (err) {
      console.error(err);
      showToast("Failed to manually execute campaign flow runs.", "error");
    }
  };

  // Human approval handlers
  const handleApproval = async (runId: string, approved: boolean) => {
    try {
      await api.post(`/flows/runs/${runId}/approve`, { approved });
      showToast(`Step successfully ${approved ? "Approved" : "Rejected"}. Advancing run.`, "success");
      refreshSelectedRun(runId);
      loadRuns();
    } catch (err) {
      console.error(err);
      showToast("Failed to process step approval.", "error");
    }
  };

  return (
    <div className="flow-builder-container flex flex-col h-[calc(100vh-80px)] w-full text-slate-100 bg-[#0c0a17] font-sans">
      <style>{`
        .flow-builder-container {
          --white: #ffffff !important;
          
          --slate-50: #f8fafc !important;
          --slate-100: #f1f5f9 !important;
          --slate-200: #e2e8f0 !important;
          --slate-300: #cbd5e1 !important;
          --slate-400: #94a3b8 !important;
          --slate-500: #64748b !important;
          --slate-600: #475569 !important;
          --slate-700: #334155 !important;
          --slate-800: #1e293b !important;
          --slate-900: #0f172a !important;
          --slate-950: #020617 !important;

          --gray-50: #f8fafc !important;
          --gray-100: #f1f5f9 !important;
          --gray-200: #e2e8f0 !important;
          --gray-300: #cbd5e1 !important;
          --gray-400: #94a3b8 !important;
          --gray-500: #64748b !important;
          --gray-600: #475569 !important;
          --gray-700: #334155 !important;
          --gray-800: #1e293b !important;
          --gray-900: #0f172a !important;
          --gray-950: #020617 !important;
        }
      `}</style>
      
      {/* Save Bar / Header */}
      <div className="flex flex-wrap items-center justify-between px-6 py-4 border-b border-[#2d2554] bg-[#120f26]/80 backdrop-blur-md z-30">
        <div className="flex items-center gap-4">
          <div className="flex flex-col">
            <span className="text-xs uppercase tracking-wider text-purple-400 font-bold">Campaign Visual Sequence</span>
            {selectedFlow ? (
              <div className="flex items-center gap-3">
                <input
                  type="text"
                  value={flowName}
                  onChange={(e) => setFlowName(e.target.value)}
                  className="bg-transparent text-lg font-bold text-white border-b border-transparent hover:border-[#6366f1] focus:border-[#7c5cff] focus:outline-none py-0.5"
                />
                <span className={`text-[10px] px-2 py-0.5 rounded-full font-bold uppercase ${
                  selectedFlow.status === "active" ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30" : "bg-zinc-500/20 text-zinc-400 border border-zinc-500/30"
                }`}>
                  {selectedFlow.status}
                </span>
              </div>
            ) : (
              <span className="text-lg font-bold text-zinc-500">No Flow Loaded</span>
            )}
          </div>
        </div>

        <div className="flex items-center gap-3 mt-2 sm:mt-0">
          {selectedFlow && runs.length > 0 && (
            <div className="flex items-center gap-2 bg-[#191533] p-1.5 px-3 rounded-lg border border-[#2d2554] mr-2">
              <span className="text-[10px] uppercase font-bold text-zinc-500">Inspect Run:</span>
              <select
                value={selectedRun?.id || ""}
                onChange={(e) => {
                  const val = e.target.value;
                  if (val) {
                    refreshSelectedRun(val);
                  } else {
                    setSelectedRun(null);
                  }
                }}
                className="bg-transparent border-none text-xs font-semibold text-purple-300 focus:outline-none cursor-pointer"
              >
                <option value="" className="bg-[#0c0a17] text-zinc-400">None (Design Mode)</option>
                {runs.map(r => (
                  <option key={r.id} value={r.id} className="bg-[#0c0a17] text-slate-200">
                    {r.lead_name || "General"} ({r.status})
                  </option>
                ))}
              </select>
            </div>
          )}

          <div className="flex bg-[#191533] p-1 rounded-lg border border-[#2d2554] mr-3">
            <button
              onClick={() => setActiveTab("builder")}
              className={`flex items-center gap-2 px-3 py-1.5 rounded-md text-xs font-semibold transition-all ${
                activeTab === "builder" ? "bg-[#7c5cff] text-white shadow-md" : "text-zinc-400 hover:text-zinc-200"
              }`}
            >
              <Grid className="w-3.5 h-3.5" />
              Workflow Canvas
            </button>
            <button
              onClick={() => setActiveTab("monitor")}
              className={`flex items-center gap-2 px-3 py-1.5 rounded-md text-xs font-semibold transition-all ${
                activeTab === "monitor" ? "bg-[#7c5cff] text-white shadow-md" : "text-zinc-400 hover:text-zinc-200"
              }`}
            >
              <Eye className="w-3.5 h-3.5" />
              Executions Log
            </button>
          </div>

          {selectedFlow && activeTab === "builder" && (
            <>
              <button
                onClick={saveFlow}
                className="flex items-center gap-1.5 px-3.5 py-2 rounded-lg bg-[#27214d] hover:bg-[#342b66] border border-[#4c3f8f]/40 text-xs font-semibold transition-all"
              >
                <Save className="w-4 h-4 text-purple-300" />
                Save Draft
              </button>
              <button
                onClick={publishFlow}
                className="flex items-center gap-1.5 px-3.5 py-2 rounded-lg bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-xs font-semibold transition-all shadow-[0_0_15px_rgba(16,185,129,0.2)]"
              >
                <CheckCircle className="w-4 h-4" />
                Publish Flow
              </button>
              <button
                onClick={triggerFlowRun}
                className="flex items-center gap-1.5 px-3.5 py-2 rounded-lg bg-gradient-to-r from-[#7c5cff] to-[#a78bfa] hover:from-[#6d4be0] hover:to-[#906ffa] text-xs font-semibold transition-all shadow-[0_0_15px_rgba(124,92,255,0.2)]"
              >
                <Play className="w-4 h-4 fill-white" />
                Run Flow
              </button>
            </>
          )}
        </div>
      </div>

      {activeTab === "builder" ? (
        <div className="flex flex-1 relative overflow-hidden">
          
          {/* Left Panel - Template List & Node Palette */}
          <div className="w-72 border-r border-[#2d2554] bg-[#0c0a17]/95 flex flex-col z-20">
            {/* Flow selector dropdown */}
            <div className="p-4 border-b border-[#2d2554]">
              <div className="flex justify-between items-center mb-2">
                <span className="text-xs uppercase tracking-wider text-zinc-400 font-bold">Select Sequence</span>
                <button
                  onClick={createNewFlow}
                  className="p-1 rounded bg-[#1e1a38] text-purple-400 hover:text-purple-300 hover:bg-[#2b254d] transition-all"
                  title="Create new flow"
                >
                  <Plus className="w-4 h-4" />
                </button>
              </div>
              <div className="space-y-1.5 max-h-48 overflow-y-auto pr-1">
                {flows.map((flow) => (
                  <div
                    key={flow.id}
                    onClick={() => selectFlow(flow)}
                    className={`flex items-center justify-between p-2 rounded-lg cursor-pointer transition-all ${
                      selectedFlow?.id === flow.id
                        ? "bg-[#211b47] border border-[#4c3f8f] text-white"
                        : "bg-[#110e26] hover:bg-[#1a1538] border border-transparent text-zinc-400"
                    }`}
                  >
                    <span className="text-xs truncate font-medium">{flow.name}</span>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        deleteFlowTemplate(flow.id);
                      }}
                      className="text-zinc-500 hover:text-red-400 p-0.5 rounded transition-all"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                ))}
              </div>
            </div>

            {/* Nodes palette */}
            <div className="flex-1 overflow-y-auto p-4 space-y-5">
              <div>
                <span className="text-xs font-bold uppercase tracking-wider text-purple-400">1. Drag Triggers</span>
                <div className="grid grid-cols-1 gap-2 mt-2">
                  <div
                    onClick={() => addNode("csvUpload", "CSV Lead List Source")}
                    className="flex items-center gap-2 p-2.5 rounded-lg border border-[#302561] bg-[#15122e] hover:bg-[#201c45] cursor-pointer transition-all group"
                  >
                    <div className="p-1.5 rounded bg-sky-500/10 text-sky-400 group-hover:scale-105 transition-all">
                      <FileText className="w-4 h-4" />
                    </div>
                    <div className="flex flex-col">
                      <span className="text-xs font-semibold text-sky-200">CSV List Import</span>
                      <span className="text-[10px] text-zinc-500">Starts run for file leads</span>
                    </div>
                  </div>
                  <div
                    onClick={() => addNode("linkedinSearch", "LinkedIn Discovery Source")}
                    className="flex items-center gap-2 p-2.5 rounded-lg border border-[#302561] bg-[#15122e] hover:bg-[#201c45] cursor-pointer transition-all group"
                  >
                    <div className="p-1.5 rounded bg-sky-500/10 text-sky-400 group-hover:scale-105 transition-all">
                      <Linkedin className="w-4 h-4" />
                    </div>
                    <div className="flex flex-col">
                      <span className="text-xs font-semibold text-sky-200">LinkedIn Search</span>
                      <span className="text-[10px] text-zinc-500">Automated lead discovery</span>
                    </div>
                  </div>
                </div>
              </div>

              <div>
                <span className="text-xs font-bold uppercase tracking-wider text-emerald-400">2. outreach Actions</span>
                <div className="grid grid-cols-1 gap-2 mt-2">
                  <div
                    onClick={() => addNode("linkedinConnect", "LinkedIn Connect")}
                    className="flex items-center gap-2 p-2.5 rounded-lg border border-[#234d40] bg-[#0c261e] hover:bg-[#163b30] cursor-pointer transition-all group"
                  >
                    <div className="p-1.5 rounded bg-sky-500/10 text-sky-400 group-hover:scale-105 transition-all">
                      <Linkedin className="w-4 h-4" />
                    </div>
                    <div className="flex flex-col">
                      <span className="text-xs font-semibold text-sky-200">LinkedIn Connection</span>
                      <span className="text-[10px] text-zinc-500">Sends connection invite</span>
                    </div>
                  </div>
                  <div
                    onClick={() => addNode("linkedinMessage", "Send LinkedIn Message")}
                    className="flex items-center gap-2 p-2.5 rounded-lg border border-[#234d40] bg-[#0c261e] hover:bg-[#163b30] cursor-pointer transition-all group"
                  >
                    <div className="p-1.5 rounded bg-sky-500/10 text-sky-400 group-hover:scale-105 transition-all">
                      <Linkedin className="w-4 h-4" />
                    </div>
                    <div className="flex flex-col">
                      <span className="text-xs font-semibold text-sky-200">LinkedIn Message</span>
                      <span className="text-[10px] text-zinc-500">Sends direct DM</span>
                    </div>
                  </div>
                  <div
                    onClick={() => addNode("sendEmail", "Send Gmail Email")}
                    className="flex items-center gap-2 p-2.5 rounded-lg border border-[#234d40] bg-[#0c261e] hover:bg-[#163b30] cursor-pointer transition-all group"
                  >
                    <div className="p-1.5 rounded bg-emerald-500/10 text-emerald-400 group-hover:scale-105 transition-all">
                      <Mail className="w-4 h-4" />
                    </div>
                    <div className="flex flex-col">
                      <span className="text-xs font-semibold text-emerald-200">Send Email</span>
                      <span className="text-[10px] text-zinc-500">Send via Gmail account</span>
                    </div>
                  </div>
                </div>
              </div>

              <div>
                <span className="text-xs font-bold uppercase tracking-wider text-amber-400">3. Intelligence & Control</span>
                <div className="grid grid-cols-1 gap-2 mt-2">
                  <div
                    onClick={() => addNode("delay", "Wait Delay")}
                    className="flex items-center gap-2 p-2.5 rounded-lg border border-[#524422] bg-[#292211] hover:bg-[#3d3319] cursor-pointer transition-all group"
                  >
                    <div className="p-1.5 rounded bg-amber-500/10 text-amber-400 group-hover:scale-105 transition-all">
                      <Clock className="w-4 h-4" />
                    </div>
                    <div className="flex flex-col">
                      <span className="text-xs font-semibold text-amber-200">Wait Delay</span>
                      <span className="text-[10px] text-zinc-500">Pauses flow execution</span>
                    </div>
                  </div>
                  <div
                    onClick={() => addNode("condition", "Branch Condition")}
                    className="flex items-center gap-2 p-2.5 rounded-lg border border-[#524422] bg-[#292211] hover:bg-[#3d3319] cursor-pointer transition-all group"
                  >
                    <div className="p-1.5 rounded bg-indigo-500/10 text-indigo-400 group-hover:scale-105 transition-all">
                      <Sliders className="w-4 h-4" />
                    </div>
                    <div className="flex flex-col">
                      <span className="text-xs font-semibold text-indigo-200">Branching Logic</span>
                      <span className="text-[10px] text-zinc-500">Splits run true/false</span>
                    </div>
                  </div>
                  <div
                    onClick={() => addNode("humanApproval", "Human Approval Check")}
                    className="flex items-center gap-2 p-2.5 rounded-lg border border-[#524422] bg-[#292211] hover:bg-[#3d3319] cursor-pointer transition-all group"
                  >
                    <div className="p-1.5 rounded bg-purple-500/10 text-purple-400 group-hover:scale-105 transition-all">
                      <UserCheck className="w-4 h-4" />
                    </div>
                    <div className="flex flex-col">
                      <span className="text-xs font-semibold text-purple-200">Human Approval</span>
                      <span className="text-[10px] text-zinc-500">Requires manual click</span>
                    </div>
                  </div>
                  <div
                    onClick={() => addNode("enrichment", "Verify Email Deliverability")}
                    className="flex items-center gap-2 p-2.5 rounded-lg border border-[#524422] bg-[#292211] hover:bg-[#3d3319] cursor-pointer transition-all group"
                  >
                    <div className="p-1.5 rounded bg-pink-500/10 text-pink-400 group-hover:scale-105 transition-all">
                      <Search className="w-4 h-4" />
                    </div>
                    <div className="flex flex-col">
                      <span className="text-xs font-semibold text-pink-200">Email Verification</span>
                      <span className="text-[10px] text-zinc-500">Enriches contact info</span>
                    </div>
                  </div>
                  <div
                    onClick={() => addNode("aiAction", "AI Content Draft")}
                    className="flex items-center gap-2 p-2.5 rounded-lg border border-[#524422] bg-[#292211] hover:bg-[#3d3319] cursor-pointer transition-all group"
                  >
                    <div className="p-1.5 rounded bg-violet-500/10 text-violet-400 group-hover:scale-105 transition-all">
                      <Bot className="w-4 h-4" />
                    </div>
                    <div className="flex flex-col">
                      <span className="text-xs font-semibold text-violet-200">AI Writer Agent</span>
                      <span className="text-[10px] text-zinc-500">Drafts personalized copy</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Center Canvas */}
          <div
            ref={canvasRef}
            onMouseMove={handleCanvasMouseMove}
            onMouseUp={handleCanvasMouseUp}
            onMouseDown={handleCanvasMouseDown}
            className={`flex-1 relative overflow-hidden bg-[#0a0815] cursor-grab select-none ${
              isPanning ? "cursor-grabbing" : ""
            }`}
            style={{
              backgroundImage: 'radial-gradient(#2d2554 1px, transparent 1px)',
              backgroundSize: '24px 24px',
              backgroundPosition: `${pan.x}px ${pan.y}px`,
            }}
          >
            {/* Empty Canvas Overlay */}
            {!selectedFlow && (
              <div className="absolute inset-0 flex flex-col items-center justify-center text-center p-6 bg-[#0a0815]/90 z-20">
                <div className="p-4 rounded-full bg-[#1b153f] border border-[#3e347d] text-purple-400 mb-4 animate-bounce">
                  <Zap className="w-8 h-8" />
                </div>
                <h3 className="text-lg font-bold text-white mb-2">No Campaign Flow Selected</h3>
                <p className="text-sm text-zinc-400 max-w-sm mb-6">
                  Select a workflow sequence from the left menu or create a new automation path to start designing.
                </p>
                <button
                  onClick={createNewFlow}
                  className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-gradient-to-r from-[#7c5cff] to-[#a78bfa] hover:from-[#6d4be0] hover:to-[#906ffa] text-sm font-semibold text-white transition-all shadow-[0_0_15px_rgba(124,92,255,0.3)] hover:scale-[1.02]"
                >
                  <Plus className="w-4 h-4" />
                  Create Your First Flow
                </button>
              </div>
            )}

            {/* Run Inspection Banner */}
            {selectedRun && (
              <div className="absolute top-4 left-1/2 -translate-x-1/2 px-4 py-2 rounded-full border border-sky-500/30 bg-[#120f26]/90 backdrop-blur-md text-xs font-semibold text-sky-200 shadow-[0_0_20px_rgba(56,189,248,0.25)] flex items-center gap-3 z-30 pointer-events-auto">
                <span className="relative flex h-2 w-2">
                  <span className={`animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 ${
                    selectedRun.status === "completed" ? "bg-emerald-400" : selectedRun.status === "failed" ? "bg-red-400" : "bg-sky-400"
                  }`}></span>
                  <span className={`relative inline-flex rounded-full h-2 w-2 ${
                    selectedRun.status === "completed" ? "bg-emerald-500" : selectedRun.status === "failed" ? "bg-red-500" : "bg-sky-500"
                  }`}></span>
                </span>
                <span>
                  Inspecting Execution Run: <strong className="text-white">{selectedRun.lead_name || "General Lead"}</strong> 
                  <span className="ml-1.5 opacity-60">({selectedRun.status.replace("_", " ")})</span>
                </span>
                <button
                  onClick={() => setSelectedRun(null)}
                  className="ml-2 px-2.5 py-0.5 rounded bg-sky-800/40 hover:bg-sky-700/60 text-white text-[10px] font-bold border border-sky-500/20 transition-all cursor-pointer"
                >
                  Exit Inspect
                </button>
              </div>
            )}

            {/* Zoom / Pan controls indicator */}
            <div className="absolute bottom-6 left-6 p-2 rounded-lg bg-[#141226]/90 border border-[#2d2554] flex items-center gap-3 text-xs text-zinc-400 z-10">
              <span className="font-semibold text-purple-400">Scale: {Math.round(zoom * 100)}%</span>
              <div className="flex gap-1">
                <button onClick={() => setZoom(z => Math.max(0.5, z - 0.1))} className="px-2 py-0.5 rounded bg-[#1e1a38] text-white hover:bg-[#2b254d]">-</button>
                <button onClick={() => { setZoom(1); setPan({ x: 0, y: 0 }); }} className="px-2 py-0.5 rounded bg-[#1e1a38] text-white hover:bg-[#2b254d]">Reset</button>
                <button onClick={() => setZoom(z => Math.min(2, z + 0.1))} className="px-2 py-0.5 rounded bg-[#1e1a38] text-white hover:bg-[#2b254d]">+</button>
              </div>
            </div>

            {/* SVG Edges Canvas */}
            <svg
              className="absolute inset-0 pointer-events-none z-0"
              style={{
                width: '100%',
                height: '100%',
              }}
            >
              <style>{`
                @keyframes dash {
                  to {
                    stroke-dashoffset: -20;
                  }
                }
                @keyframes slide-in {
                  from {
                    transform: translateY(20px);
                    opacity: 0;
                  }
                  to {
                    transform: translateY(0);
                    opacity: 1;
                  }
                }
                .animate-slide-in {
                  animation: slide-in 0.3s cubic-bezier(0.16, 1, 0.3, 1) forwards;
                }
              `}</style>
              <g transform={`translate(${pan.x}, ${pan.y}) scale(${zoom})`}>
                {edges.map((edge) => {
                  const srcCoords = getNodeCoordinates(edge.source);
                  const tgtCoords = getNodeCoordinates(edge.target);
                  
                  // Compute starting handle coordinate based on handleId
                  let fromX = srcCoords.outX;
                  let fromY = srcCoords.outY;
                  
                  const isCondition = nodes.find(n => n.id === edge.source)?.type === "condition";
                  if (isCondition) {
                    if (edge.sourceHandle === "true") {
                      fromX = srcCoords.outTrueX;
                      fromY = srcCoords.outTrueY;
                    } else if (edge.sourceHandle === "false") {
                      fromX = srcCoords.outFalseX;
                      fromY = srcCoords.outFalseY;
                    }
                  }

                  // Trace edges
                  const srcState = selectedRun?.node_states?.[edge.source];
                  const tgtState = selectedRun?.node_states?.[edge.target];
                  const isTraversed = srcState?.status === "completed" && tgtState;
                  const isRunningEdge = srcState?.status === "completed" && selectedRun?.current_step_id === edge.target;

                  let strokeColor = "#4c3f8f";
                  let strokeWidth = "2.5";
                  let isAnimated = false;

                  if (isTraversed) {
                    strokeColor = "#10b981"; // emerald traversed path
                    strokeWidth = "3.5";
                  } else if (isRunningEdge) {
                    strokeColor = "#38bdf8"; // sky blue active run path
                    strokeWidth = "3.5";
                    isAnimated = true;
                  }

                  return (
                    <g key={edge.id} className="pointer-events-auto group">
                      <path
                        d={getBezierPath(fromX, fromY, tgtCoords.inX, tgtCoords.inY)}
                        fill="none"
                        stroke={strokeColor}
                        strokeWidth={strokeWidth}
                        strokeDasharray={isAnimated ? "5,5" : undefined}
                        className={`${isAnimated ? "animate-[dash_1s_linear_infinite]" : ""} group-hover:stroke-purple-400 transition-colors`}
                        style={isAnimated ? { animation: 'dash 1s linear infinite' } : {}}
                      />
                      <path
                        d={getBezierPath(fromX, fromY, tgtCoords.inX, tgtCoords.inY)}
                        fill="none"
                        stroke="transparent"
                        strokeWidth="12"
                        className="cursor-pointer"
                        onClick={() => deleteEdge(edge.id)}
                        title="Click to delete connection"
                      />
                      {/* Arrow tip at target */}
                      <polygon
                        points={`${tgtCoords.inX},${tgtCoords.inY} ${tgtCoords.inX - 6},${tgtCoords.inY - 4} ${tgtCoords.inX - 6},${tgtCoords.inY + 4}`}
                        fill={strokeColor}
                        className="group-hover:fill-purple-400"
                      />
                    </g>
                  );
                })}

                {/* Temporary connection edge dragging */}
                {connectingSource && (
                  <path
                    d={(() => {
                      const srcCoords = getNodeCoordinates(connectingSource.nodeId);
                      let fromX = srcCoords.outX;
                      let fromY = srcCoords.outY;
                      
                      const isCondition = nodes.find(n => n.id === connectingSource.nodeId)?.type === "condition";
                      if (isCondition) {
                        if (connectingSource.handleId === "true") {
                          fromX = srcCoords.outTrueX;
                          fromY = srcCoords.outTrueY;
                        } else if (connectingSource.handleId === "false") {
                          fromX = srcCoords.outFalseX;
                          fromY = srcCoords.outFalseY;
                        }
                      }
                      return getBezierPath(fromX, fromY, mousePos.x, mousePos.y);
                    })()}
                    fill="none"
                    stroke="#a78bfa"
                    strokeWidth="2.5"
                    strokeDasharray="5,5"
                  />
                )}
              </g>
            </svg>

            {/* DOM Nodes */}
            <div
              className="absolute inset-0 pointer-events-none z-10"
              style={{
                transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`,
                transformOrigin: '0 0',
              }}
            >
              {nodes.map((node) => {
                const isSelected = selectedNodeId === node.id;
                
                // Active Run node visual overrides
                const nodeState = selectedRun?.node_states?.[node.id];
                const isCurrent = selectedRun?.current_step_id === node.id;
                
                let runBorderClass = "";
                let statusBadge = null;

                if (selectedRun) {
                  if (isCurrent) {
                    runBorderClass = "border-sky-500 shadow-[0_0_15px_rgba(56,189,248,0.3)] ring-2 ring-sky-500/20";
                    statusBadge = (
                      <span className="absolute -top-2 -right-2 w-5 h-5 rounded-full bg-sky-500 flex items-center justify-center text-white border border-[#0c0a17] shadow-md animate-pulse">
                        <Clock className="w-3 h-3" />
                      </span>
                    );
                  } else if (nodeState) {
                    if (nodeState.status === "completed") {
                      runBorderClass = "border-emerald-500 shadow-[0_0_15px_rgba(16,185,129,0.2)]";
                      statusBadge = (
                        <span className="absolute -top-2 -right-2 w-5 h-5 rounded-full bg-emerald-500 flex items-center justify-center text-white border border-[#0c0a17] shadow-md">
                          <CheckCircle className="w-3 h-3" />
                        </span>
                      );
                    } else if (nodeState.status === "failed") {
                      runBorderClass = "border-red-500 shadow-[0_0_15px_rgba(239,68,68,0.25)]";
                      statusBadge = (
                        <span className="absolute -top-2 -right-2 w-5 h-5 rounded-full bg-red-500 flex items-center justify-center text-white border border-[#0c0a17] shadow-md">
                          <AlertCircle className="w-3 h-3" />
                        </span>
                      );
                    } else if (nodeState.status === "waiting_for_approval") {
                      runBorderClass = "border-amber-500 shadow-[0_0_15px_rgba(245,158,11,0.3)] ring-2 ring-amber-500/10";
                      statusBadge = (
                        <span className="absolute -top-2 -right-2 w-5 h-5 rounded-full bg-amber-500 flex items-center justify-center text-white border border-[#0c0a17] shadow-md animate-bounce">
                          <UserCheck className="w-3 h-3" />
                        </span>
                      );
                    } else if (nodeState.status === "waiting_for_delay") {
                      runBorderClass = "border-purple-500 shadow-[0_0_15px_rgba(124,92,255,0.2)]";
                      statusBadge = (
                        <span className="absolute -top-2 -right-2 w-5 h-5 rounded-full bg-purple-500 flex items-center justify-center text-white border border-[#0c0a17] shadow-md">
                          <Clock className="w-3 h-3" />
                        </span>
                      );
                    }
                  }
                }

                return (
                  <div
                    key={node.id}
                    className={`absolute pointer-events-auto rounded-xl border flex flex-col w-[210px] min-h-[76px] transition-all shadow-lg select-none ${
                      isSelected
                        ? "border-[#7c5cff] shadow-[0_0_18px_rgba(124,92,255,0.25)] scale-[1.02]"
                        : runBorderClass || "border-[#2d2554]/60 bg-[#120f26]/90 text-zinc-300 hover:border-purple-500/40"
                    } ${getNodeColorClass(node.type)}`}
                    style={{
                      left: `${node.position.x}px`,
                      top: `${node.position.y}px`,
                      cursor: draggingNodeId === node.id ? "grabbing" : "grab"
                    }}
                    onMouseDown={(e) => handleNodeMouseDown(e, node.id)}
                  >
                    
                    {/* Status Badge overlay */}
                    {statusBadge}

                    {/* Header */}
                    <div className="flex items-center justify-between p-2.5 border-b border-white/5 bg-white/5 rounded-t-xl">
                      <div className="flex items-center gap-1.5 truncate">
                        {getNodeIcon(node.type)}
                        <span className="text-xs font-bold truncate">{node.label}</span>
                      </div>
                      <button
                        onClick={(e) => { e.stopPropagation(); deleteNode(node.id); }}
                        className="text-zinc-500 hover:text-red-400 p-0.5 rounded transition-colors"
                      >
                        <Trash2 className="w-3 h-3" />
                      </button>
                    </div>

                    {/* Content preview */}
                    <div className="p-2.5 flex-1 flex flex-col justify-center">
                      <span className="text-[10px] text-zinc-400 line-clamp-2 italic">
                        {node.type === "delay"
                          ? `Sleep for ${node.parameters.delay || 1} ${node.parameters.unit || "days"}`
                          : node.type === "condition"
                          ? `Check: ${node.parameters.condition_type || "has_email"}`
                          : node.type === "sendEmail"
                          ? `Draft: ${node.parameters.subject_template || "Outreach Subject"}`
                          : node.type === "linkedinMessage"
                          ? `Msg: ${node.parameters.message || "Outreach Message"}`
                          : node.type === "enrichment"
                          ? "Verify contact list deliverability"
                          : node.type === "aiAction"
                          ? `Agent: ${node.parameters.prompt || "Generate draft text"}`
                          : "Visual execution sequence step"}
                      </span>
                    </div>

                    {/* Live approval buttons inside canvas card */}
                    {selectedRun && nodeState?.status === "waiting_for_approval" && (
                      <div className="p-2 border-t border-amber-500/20 bg-amber-500/10 flex items-center justify-center gap-2 rounded-b-xl z-20 pointer-events-auto">
                        <button
                          onClick={(e) => { e.stopPropagation(); handleApproval(selectedRun.id, true); }}
                          className="bg-emerald-600 hover:bg-emerald-500 text-white font-semibold text-[9px] px-2 py-0.5 rounded flex items-center gap-1 transition-all hover:scale-105 active:scale-95"
                        >
                          <ThumbsUp className="w-2.5 h-2.5" /> Approve
                        </button>
                        <button
                          onClick={(e) => { e.stopPropagation(); handleApproval(selectedRun.id, false); }}
                          className="bg-red-600 hover:bg-red-500 text-white font-semibold text-[9px] px-2 py-0.5 rounded flex items-center gap-1 transition-all hover:scale-105 active:scale-95"
                        >
                          <ThumbsDown className="w-2.5 h-2.5" /> Reject
                        </button>
                      </div>
                    )}

                    {/* Connections Sockets (Handles) */}
                    
                    {/* Input handle (left) - Hidden on triggers */}
                    {node.type !== "csvUpload" && node.type !== "linkedinSearch" && (
                      <div
                        className="absolute w-3.5 h-3.5 rounded-full border border-purple-400 bg-[#0c0a17] hover:bg-purple-400 -left-1.5 top-1/2 -translate-y-1/2 flex items-center justify-center cursor-crosshair group"
                        onMouseUp={(e) => handleConnectorMouseUp(e, node.id)}
                      >
                        <div className="w-1.5 h-1.5 rounded-full bg-purple-400 group-hover:bg-[#0c0a17]" />
                      </div>
                    )}

                    {/* Output handle (right) */}
                    {node.type !== "condition" ? (
                      <div
                        className="absolute w-3.5 h-3.5 rounded-full border border-purple-400 bg-[#0c0a17] hover:bg-purple-400 -right-1.5 top-1/2 -translate-y-1/2 flex items-center justify-center cursor-crosshair group"
                        onMouseDown={(e) => handleConnectorMouseDown(e, node.id, "default")}
                      >
                        <div className="w-1.5 h-1.5 rounded-full bg-purple-400 group-hover:bg-[#0c0a17]" />
                      </div>
                    ) : (
                      /* Condition true/false outputs */
                      <>
                        {/* True handle */}
                        <div
                          className="absolute w-3.5 h-3.5 rounded-full border border-emerald-400 bg-[#0c0a17] hover:bg-emerald-400 -right-1.5 top-[24px] -translate-y-1/2 flex items-center justify-center cursor-crosshair group"
                          onMouseDown={(e) => handleConnectorMouseDown(e, node.id, "true")}
                          title="True path"
                        >
                          <div className="w-1.5 h-1.5 rounded-full bg-emerald-400 group-hover:bg-[#0c0a17]" />
                          <span className="absolute left-4 text-[8px] text-emerald-400 font-bold bg-[#0c0a17]/90 px-1 py-0.5 rounded border border-emerald-500/20">YES</span>
                        </div>
                        {/* False handle */}
                        <div
                          className="absolute w-3.5 h-3.5 rounded-full border border-red-400 bg-[#0c0a17] hover:bg-red-400 -right-1.5 top-[52px] -translate-y-1/2 flex items-center justify-center cursor-crosshair group"
                          onMouseDown={(e) => handleConnectorMouseDown(e, node.id, "false")}
                          title="False path"
                        >
                          <div className="w-1.5 h-1.5 rounded-full bg-red-400 group-hover:bg-[#0c0a17]" />
                          <span className="absolute left-4 text-[8px] text-red-400 font-bold bg-[#0c0a17]/90 px-1 py-0.5 rounded border border-red-500/20">NO</span>
                        </div>
                      </>
                    )}

                  </div>
                );
              })}
            </div>
          </div>

          {/* Right Panel - Parameters Config panel */}
          <div className="w-80 border-l border-[#2d2554] bg-[#0c0a17]/95 flex flex-col z-20 overflow-y-auto p-5">
            {selectedNodeId ? (
              (() => {
                const node = nodes.find(n => n.id === selectedNodeId);
                if (!node) return null;
                
                const updateParam = (key: string, value: any) => {
                  setNodes(prev => prev.map(n => {
                    if (n.id === selectedNodeId) {
                      return {
                        ...n,
                        parameters: {
                          ...n.parameters,
                          [key]: value
                        }
                      };
                    }
                    return n;
                  }));
                };

                return (
                  <div className="space-y-5">
                    <div className="flex items-center gap-2 pb-3 border-b border-[#2d2554]">
                      <Sliders className="w-4 h-4 text-purple-400" />
                      <span className="font-bold text-sm uppercase text-purple-200">Configure Node</span>
                    </div>

                    <div className="space-y-1.5">
                      <label className="text-xs text-zinc-400 font-bold">Node Label</label>
                      <input
                        type="text"
                        value={node.label}
                        onChange={(e) => {
                          const val = e.target.value;
                          setNodes(prev => prev.map(n => n.id === selectedNodeId ? { ...n, label: val } : n));
                        }}
                        className="w-full px-3 py-2 rounded-lg bg-[#14112c] border border-[#2d2554] text-xs text-white focus:border-[#7c5cff] focus:outline-none"
                      />
                    </div>

                    <div className="pt-3 border-t border-white/5 space-y-4">
                      
                      {/* CSV Upload Node */}
                      {node.type === "csvUpload" && (
                        <div className="text-xs text-zinc-400 leading-relaxed bg-[#191533]/40 p-3 rounded-lg border border-[#2d2554]">
                          <Info className="w-4 h-4 text-sky-400 mb-1" />
                          Matches active campaign csv leads automatically. Run processes individual flow loops for contacts set to status <code className="bg-[#100c24] px-1 py-0.5 rounded text-sky-300">new</code>.
                        </div>
                      )}

                      {/* LinkedIn Search Node */}
                      {node.type === "linkedinSearch" && (
                        <>
                          <div className="space-y-1.5">
                            <label className="text-xs text-zinc-400 font-bold">Search Keywords / Query</label>
                            <input
                              type="text"
                              value={node.parameters.query || ""}
                              onChange={(e) => updateParam("query", e.target.value)}
                              placeholder="e.g. Founder New York"
                              className="w-full px-3 py-2 rounded-lg bg-[#14112c] border border-[#2d2554] text-xs text-white focus:border-[#7c5cff] focus:outline-none"
                            />
                          </div>
                          <div className="space-y-1.5">
                            <label className="text-xs text-zinc-400 font-bold">Max Limit Leads</label>
                            <input
                              type="number"
                              value={node.parameters.limit || 10}
                              onChange={(e) => updateParam("limit", parseInt(e.target.value))}
                              className="w-full px-3 py-2 rounded-lg bg-[#14112c] border border-[#2d2554] text-xs text-white focus:border-[#7c5cff] focus:outline-none"
                            />
                          </div>
                        </>
                      )}

                      {/* Send Email Node */}
                      {node.type === "sendEmail" && (
                        <>
                          <div className="space-y-1.5">
                            <label className="text-xs text-zinc-400 font-bold">Email Subject</label>
                            <input
                              type="text"
                              value={node.parameters.subject_template || ""}
                              onChange={(e) => updateParam("subject_template", e.target.value)}
                              placeholder="e.g. Partnership Opportunity for {{company}}"
                              className="w-full px-3 py-2 rounded-lg bg-[#14112c] border border-[#2d2554] text-xs text-white focus:border-[#7c5cff] focus:outline-none"
                            />
                          </div>
                          <div className="space-y-1.5">
                            <label className="text-xs text-zinc-400 font-bold">Email Body Template</label>
                            <textarea
                              rows={8}
                              value={node.parameters.body_template || ""}
                              onChange={(e) => updateParam("body_template", e.target.value)}
                              placeholder="Hi {{first_name}},&#10;&#10;Loved your profile at {{company}}..."
                              className="w-full px-3 py-2 rounded-lg bg-[#14112c] border border-[#2d2554] text-xs text-white focus:border-[#7c5cff] focus:outline-none font-mono"
                            />
                            <span className="text-[10px] text-zinc-500">Supports templates: `{{first_name}}`, `{{company}}`, `{{role}}`</span>
                          </div>
                        </>
                      )}

                      {/* LinkedIn Connect Node */}
                      {node.type === "linkedinConnect" && (
                        <div className="space-y-1.5">
                          <label className="text-xs text-zinc-400 font-bold">Personalized Connection Note</label>
                          <textarea
                            rows={4}
                            value={node.parameters.note || ""}
                            onChange={(e) => updateParam("note", e.target.value)}
                            placeholder="Hi {{first_name}}, would love to connect!"
                            maxLength={300}
                            className="w-full px-3 py-2 rounded-lg bg-[#14112c] border border-[#2d2554] text-xs text-white focus:border-[#7c5cff] focus:outline-none font-mono"
                          />
                          <div className="flex justify-between text-[10px] text-zinc-500">
                            <span>Max 300 characters</span>
                            <span>{300 - (node.parameters.note || "").length} left</span>
                          </div>
                        </div>
                      )}

                      {/* LinkedIn Message Node */}
                      {node.type === "linkedinMessage" && (
                        <div className="space-y-1.5">
                          <label className="text-xs text-zinc-400 font-bold">Direct Message Body</label>
                          <textarea
                            rows={6}
                            value={node.parameters.message || ""}
                            onChange={(e) => updateParam("message", e.target.value)}
                            placeholder="Hi {{first_name}}, thanks for connecting!"
                            className="w-full px-3 py-2 rounded-lg bg-[#14112c] border border-[#2d2554] text-xs text-white focus:border-[#7c5cff] focus:outline-none font-mono"
                          />
                        </div>
                      )}

                      {/* Wait Delay Node */}
                      {node.type === "delay" && (
                        <>
                          <div className="space-y-1.5">
                            <label className="text-xs text-zinc-400 font-bold">Duration</label>
                            <input
                              type="number"
                              value={node.parameters.delay || 1}
                              onChange={(e) => updateParam("delay", parseInt(e.target.value))}
                              className="w-full px-3 py-2 rounded-lg bg-[#14112c] border border-[#2d2554] text-xs text-white focus:border-[#7c5cff] focus:outline-none"
                            />
                          </div>
                          <div className="space-y-1.5">
                            <label className="text-xs text-zinc-400 font-bold">Unit</label>
                            <select
                              value={node.parameters.unit || "days"}
                              onChange={(e) => updateParam("unit", e.target.value)}
                              className="w-full px-3 py-2 rounded-lg bg-[#14112c] border border-[#2d2554] text-xs text-white focus:border-[#7c5cff] focus:outline-none"
                            >
                              <option value="minutes">Minutes (testing)</option>
                              <option value="hours">Hours</option>
                              <option value="days">Days</option>
                            </select>
                          </div>
                        </>
                      )}

                      {/* Branch Condition Node */}
                      {node.type === "condition" && (
                        <>
                          <div className="space-y-1.5">
                            <label className="text-xs text-zinc-400 font-bold">Condition Rule</label>
                            <select
                              value={node.parameters.condition_type || "has_email"}
                              onChange={(e) => updateParam("condition_type", e.target.value)}
                              className="w-full px-3 py-2 rounded-lg bg-[#14112c] border border-[#2d2554] text-xs text-white focus:border-[#7c5cff] focus:outline-none"
                            >
                              <option value="has_email">Email Address Exists</option>
                              <option value="has_linkedin">LinkedIn URL Exists</option>
                              <option value="replied">Lead Has Replied</option>
                              <option value="ai_classification">AI Text Classification</option>
                            </select>
                          </div>
                          
                          {node.parameters.condition_type === "ai_classification" && (
                            <div className="space-y-1.5">
                              <label className="text-xs text-zinc-400 font-bold">AI Decision Criteria</label>
                              <input
                                type="text"
                                value={node.parameters.ai_prompt || ""}
                                onChange={(e) => updateParam("ai_prompt", e.target.value)}
                                placeholder="e.g. Did the lead show high interest?"
                                className="w-full px-3 py-2 rounded-lg bg-[#14112c] border border-[#2d2554] text-xs text-white focus:border-[#7c5cff] focus:outline-none"
                              />
                            </div>
                          )}
                        </>
                      )}

                      {/* AI Action Node */}
                      {node.type === "aiAction" && (
                        <div className="space-y-1.5">
                          <label className="text-xs text-zinc-400 font-bold">AI Prompt / Task</label>
                          <textarea
                            rows={5}
                            value={node.parameters.prompt || ""}
                            onChange={(e) => updateParam("prompt", e.target.value)}
                            placeholder="Draft a highly customized outreach hook based on user's job description..."
                            className="w-full px-3 py-2 rounded-lg bg-[#14112c] border border-[#2d2554] text-xs text-white focus:border-[#7c5cff] focus:outline-none font-mono"
                          />
                        </div>
                      )}

                      {/* Send Notification Node */}
                      {node.type === "sendNotification" && (
                        <>
                          <div className="space-y-1.5">
                            <label className="text-xs text-zinc-400 font-bold">Notification Title</label>
                            <input
                              type="text"
                              value={node.parameters.title || ""}
                              onChange={(e) => updateParam("title", e.target.value)}
                              placeholder="e.g. Lead Enriched Successfully"
                              className="w-full px-3 py-2 rounded-lg bg-[#14112c] border border-[#2d2554] text-xs text-white focus:border-[#7c5cff] focus:outline-none"
                            />
                          </div>
                          <div className="space-y-1.5">
                            <label className="text-xs text-zinc-400 font-bold">Notification Message</label>
                            <input
                              type="text"
                              value={node.parameters.message || ""}
                              onChange={(e) => updateParam("message", e.target.value)}
                              placeholder="e.g. {{name}}'s business email verified."
                              className="w-full px-3 py-2 rounded-lg bg-[#14112c] border border-[#2d2554] text-xs text-white focus:border-[#7c5cff] focus:outline-none"
                            />
                          </div>
                        </>
                      )}

                      {/* Human Approval Node */}
                      {node.type === "humanApproval" && (
                        <div className="space-y-1.5">
                          <label className="text-xs text-zinc-400 font-bold">Approval Alert Message</label>
                          <input
                            type="text"
                            value={node.parameters.message || ""}
                            onChange={(e) => updateParam("message", e.target.value)}
                            placeholder="e.g. Please approve LinkedIn direct message copy."
                            className="w-full px-3 py-2 rounded-lg bg-[#14112c] border border-[#2d2554] text-xs text-white focus:border-[#7c5cff] focus:outline-none"
                          />
                        </div>
                      )}

                    </div>
                  </div>
                );
              })()
            ) : (
              <div className="flex flex-col items-center justify-center h-full text-center text-zinc-500">
                <Sliders className="w-10 h-10 mb-2 stroke-zinc-600" />
                <span className="text-xs">Select a node in the canvas to configure parameters</span>
              </div>
            )}
          </div>

        </div>
      ) : (
        /* Monitor / Executions Log Tab */
        <div className="flex-1 flex overflow-hidden">
          
          {/* Active / Past Runs List */}
          <div className="w-1/3 border-r border-[#2d2554] bg-[#0c0a17] flex flex-col">
            <div className="p-4 border-b border-[#2d2554] flex justify-between items-center bg-[#120f26]/40">
              <span className="text-xs uppercase tracking-wider text-zinc-400 font-bold">Execution Runs</span>
              <button
                onClick={loadRuns}
                className="text-xs text-purple-400 hover:text-purple-300 font-semibold"
              >
                Refresh
              </button>
            </div>
            
            <div className="flex-1 overflow-y-auto p-3 space-y-2">
              {runs.length === 0 ? (
                <div className="text-center text-zinc-500 text-xs py-10">
                  No execution runs found for this flow template.
                </div>
              ) : (
                runs.map((run) => {
                  const isSelected = selectedRun?.id === run.id;
                  let statusColor = "bg-zinc-500/10 text-zinc-400 border border-zinc-500/30";
                  if (run.status === "completed") statusColor = "bg-emerald-500/10 text-emerald-400 border border-emerald-500/30";
                  if (run.status === "failed") statusColor = "bg-red-500/10 text-red-400 border border-red-500/30";
                  if (run.status === "running") statusColor = "bg-sky-500/10 text-sky-400 border border-sky-500/30 anim-pulse";
                  if (run.status === "waiting_for_approval") statusColor = "bg-amber-500/10 text-amber-400 border border-amber-500/30";
                  if (run.status === "waiting_for_delay") statusColor = "bg-purple-500/10 text-purple-400 border border-purple-500/30";

                  return (
                    <div
                      key={run.id}
                      onClick={() => refreshSelectedRun(run.id)}
                      className={`p-3 rounded-xl cursor-pointer border transition-all ${
                        isSelected
                          ? "border-[#7c5cff] bg-[#211b47]/80 text-white"
                          : "border-transparent bg-[#141228] hover:bg-[#1f1b3d] text-zinc-300"
                      }`}
                    >
                      <div className="flex items-center justify-between gap-2 mb-1.5">
                        <span className="text-xs font-semibold truncate">{run.lead_name || "General Execute"}</span>
                        <span className={`text-[9px] px-2 py-0.5 rounded-full font-bold uppercase ${statusColor}`}>
                          {run.status.replace("_", " ")}
                        </span>
                      </div>
                      
                      <div className="flex justify-between items-center text-[10px] text-zinc-500">
                        <span>ID: `{run.id.slice(0, 8)}`</span>
                        <span>{new Date(run.created_at).toLocaleTimeString()}</span>
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          </div>

          {/* Selected Run Details, Visual Step Progress & Logs */}
          <div className="flex-1 bg-[#0a0815] flex flex-col overflow-y-auto p-6 space-y-6">
            {selectedRun ? (
              <>
                {/* Status card */}
                <div className="p-4 rounded-xl border border-[#2d2554] bg-[#141226]/80 flex flex-wrap items-center justify-between gap-4">
                  <div className="flex items-center gap-3">
                    <div className="p-2 rounded-lg bg-purple-500/15 text-purple-400">
                      <Zap className="w-5 h-5" />
                    </div>
                    <div>
                      <h4 className="text-sm font-bold text-white">Execution Run: {selectedRun.lead_name || "Campaign Flow"}</h4>
                      <p className="text-xs text-zinc-400">Flow ID: `{selectedRun.flow_id}` | Run ID: `{selectedRun.id}`</p>
                    </div>
                  </div>

                  {selectedRun.status === "waiting_for_approval" && (
                    <div className="flex items-center gap-2.5 p-2 px-3.5 rounded-lg border border-amber-500/20 bg-amber-500/10">
                      <span className="text-xs font-bold text-amber-300">Approval Required:</span>
                      <button
                        onClick={() => handleApproval(selectedRun.id, true)}
                        className="flex items-center gap-1 text-[11px] font-semibold bg-emerald-600 hover:bg-emerald-500 text-white px-2.5 py-1 rounded transition-colors"
                      >
                        <ThumbsUp className="w-3.5 h-3.5" /> Approve
                      </button>
                      <button
                        onClick={() => handleApproval(selectedRun.id, false)}
                        className="flex items-center gap-1 text-[11px] font-semibold bg-red-600 hover:bg-red-500 text-white px-2.5 py-1 rounded transition-colors"
                      >
                        <ThumbsDown className="w-3.5 h-3.5" /> Reject
                      </button>
                    </div>
                  )}

                  {selectedRun.status === "waiting_for_delay" && (
                    <div className="text-xs text-purple-300 font-medium flex items-center gap-1.5">
                      <Clock className="w-4 h-4 text-purple-400" />
                      Waiting until: {selectedRun.wait_until ? new Date(selectedRun.wait_until).toLocaleString() : "..."}
                    </div>
                  )}
                </div>

                {/* Node Execution States Checker */}
                <div className="space-y-3">
                  <span className="text-xs font-bold uppercase tracking-wider text-zinc-400">Nodes Step Trace</span>
                  <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
                    {nodes.map((node) => {
                      const nodeState = selectedRun.node_states?.[node.id];
                      let borderClass = "border-[#2d2554] bg-[#141226]/50 opacity-60";
                      let badge = "waiting";
                      let badgeColor = "bg-zinc-500/10 text-zinc-400";
                      
                      if (selectedRun.current_step_id === node.id) {
                        borderClass = "border-sky-500 bg-sky-950/20 shadow-[0_0_12px_rgba(56,189,248,0.15)]";
                        badge = "active";
                        badgeColor = "bg-sky-500/20 text-sky-400";
                      } else if (nodeState) {
                        if (nodeState.status === "completed") {
                          borderClass = "border-emerald-500 bg-emerald-950/20";
                          badge = "completed";
                          badgeColor = "bg-emerald-500/20 text-emerald-400";
                        } else if (nodeState.status === "failed") {
                          borderClass = "border-red-500 bg-red-950/20";
                          badge = "failed";
                          badgeColor = "bg-red-500/20 text-red-400";
                        } else if (nodeState.status === "running") {
                          borderClass = "border-sky-500 bg-sky-950/20";
                          badge = "running";
                          badgeColor = "bg-sky-500/20 text-sky-400";
                        }
                      }

                      return (
                        <div key={node.id} className={`p-3 rounded-xl border flex flex-col justify-between min-h-[76px] transition-all ${borderClass}`}>
                          <div className="flex items-center justify-between mb-2">
                            <div className="flex items-center gap-1.5 text-xs font-bold text-white">
                              {getNodeIcon(node.type)}
                              <span>{node.label}</span>
                            </div>
                            <span className={`text-[8px] px-1.5 py-0.5 rounded uppercase font-bold ${badgeColor}`}>
                              {badge}
                            </span>
                          </div>
                          
                          {nodeState?.error && (
                            <span className="text-[10px] text-red-400 truncate mt-1">Error: {nodeState.error}</span>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>

                {/* Execution logs output */}
                <div className="flex flex-col flex-1 border border-[#2d2554] rounded-xl bg-[#0c0a17] overflow-hidden min-h-[300px]">
                  <div className="p-3 border-b border-[#2d2554] bg-[#141226]/80 text-xs font-bold text-zinc-300">
                    Execution Logs Stream
                  </div>
                  <div className="flex-1 p-4 overflow-y-auto font-mono text-xs space-y-2.5 max-h-[350px]">
                    {runLogs.length === 0 ? (
                      <span className="text-zinc-600 italic">No logs emitted yet.</span>
                    ) : (
                      runLogs.map((log, i) => {
                        let textClass = "text-zinc-400";
                        if (log.level === "ERROR") textClass = "text-red-400 font-bold";
                        if (log.level === "WARNING") textClass = "text-amber-400";
                        return (
                          <div key={i} className="flex gap-4 items-start select-text">
                            <span className="text-zinc-600 shrink-0">{new Date(log.timestamp).toLocaleTimeString()}</span>
                            <span className={`shrink-0 font-bold uppercase text-[9px] px-1.5 rounded bg-white/5 ${
                              log.level === "ERROR" ? "text-red-500" : log.level === "WARNING" ? "text-amber-500" : "text-sky-500"
                            }`}>{log.level}</span>
                            <span className={textClass}>{log.message}</span>
                          </div>
                        );
                      })
                    )}
                  </div>
                </div>
              </>
            ) : (
              <div className="flex flex-col items-center justify-center h-full text-center text-zinc-500 py-20">
                <List className="w-12 h-12 mb-3 stroke-zinc-600" />
                <h4 className="font-bold text-sm text-zinc-400">No Run Selected</h4>
                <p className="text-xs text-zinc-500 max-w-sm mt-1">Select an active or historical execution run from the left panel to examine its steps, approval status, and output logs.</p>
              </div>
            )}
          </div>

        </div>
      )}

      {/* Toast Notification Popup */}
      {toast && (
        <div className={`fixed bottom-6 right-6 p-4 rounded-xl border shadow-xl flex items-center gap-3 z-50 animate-slide-in backdrop-blur-md transition-all ${
          toast.type === "success" 
            ? "bg-emerald-950/90 border-emerald-500/30 text-emerald-200 shadow-[0_0_20px_rgba(16,185,129,0.15)]"
            : toast.type === "error"
            ? "bg-red-950/90 border-red-500/30 text-red-200 shadow-[0_0_20px_rgba(239,68,68,0.15)]"
            : "bg-purple-950/90 border-purple-500/30 text-purple-200 shadow-[0_0_20px_rgba(124,92,255,0.15)]"
        }`}>
          {toast.type === "success" ? (
            <CheckCircle className="w-5 h-5 text-emerald-400 shrink-0" />
          ) : toast.type === "error" ? (
            <AlertCircle className="w-5 h-5 text-red-400 shrink-0" />
          ) : (
            <Info className="w-5 h-5 text-purple-400 shrink-0" />
          )}
          <span className="text-xs font-semibold">{toast.message}</span>
        </div>
      )}

    </div>
  );
}
