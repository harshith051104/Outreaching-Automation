"use client";

import { useState, useRef, useEffect } from "react";
import { Camera, Crop, Upload, Check, RotateCcw, Trash, X } from "lucide-react";

// Safe dynamic browser loader for html2canvas-pro from CDN fallback (resolves Tailwind v4 oklab/oklch parsing errors)
const loadHtml2Canvas = (): Promise<any> => {
  return new Promise((resolve, reject) => {
    if (typeof window === "undefined") {
      reject(new Error("window is undefined"));
      return;
    }
    
    // Check if either html2canvas or html2canvasPro is already defined globally
    const getHtml2CanvasGlobal = () => (window as any).html2canvas || (window as any).html2canvasPro;
    const globalObj = getHtml2CanvasGlobal();
    if (globalObj) {
      resolve(globalObj);
      return;
    }
    
    // Check if script already exists to avoid duplicate tags
    const existing = document.querySelector('script[src*="html2canvas"]');
    if (existing) {
      const checkLoaded = setInterval(() => {
        const currentGlobal = getHtml2CanvasGlobal();
        if (currentGlobal) {
          clearInterval(checkLoaded);
          resolve(currentGlobal);
        }
      }, 50);
      setTimeout(() => {
        clearInterval(checkLoaded);
        reject(new Error("html2canvas script load timeout"));
      }, 5000);
      return;
    }

    const script = document.createElement("script");
    script.src = "https://cdn.jsdelivr.net/npm/html2canvas-pro@1.5.8/dist/html2canvas.min.js";
    script.crossOrigin = "anonymous";
    script.async = true;
    script.onload = () => {
      const loadedGlobal = getHtml2CanvasGlobal();
      if (loadedGlobal) {
        resolve(loadedGlobal);
      } else {
        reject(new Error("html2canvas global object not found after script load"));
      }
    };
    script.onerror = (err) => {
      reject(err);
    };
    document.body.appendChild(script);
  });
};

interface ScreenshotCaptureProps {
  onScreenshotConfirmed: (dataUrl: string | null) => void;
  onCaptureStart?: () => void;
  onCaptureEnd?: () => void;
}

export default function ScreenshotCapture({
  onScreenshotConfirmed,
  onCaptureStart,
  onCaptureEnd,
}: ScreenshotCaptureProps) {
  const [preview, setPreview] = useState<string | null>(null);
  const [isConfirmed, setIsConfirmed] = useState(false);
  const [capturing, setCapturing] = useState(false);
  
  // Snipping mode state
  const [isSnippingMode, setIsSnippingMode] = useState(false);
  const [isSelecting, setIsSelecting] = useState(false);
  const [startX, setStartX] = useState(0);
  const [startY, setStartY] = useState(0);
  const [currentX, setCurrentX] = useState(0);
  const [currentY, setCurrentY] = useState(0);

  const fileInputRef = useRef<HTMLInputElement>(null);

  // Escape to cancel snipping
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && isSnippingMode) {
        setIsSnippingMode(false);
        setIsSelecting(false);
        if (onCaptureEnd) onCaptureEnd();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [isSnippingMode, onCaptureEnd]);

  // Capture Full Viewport Page
  const handleCaptureFull = async () => {
    try {
      setCapturing(true);
      if (onCaptureStart) onCaptureStart();

      // Small delay for modal layout hiding animation
      await new Promise((resolve) => setTimeout(resolve, 200));

      const html2canvas = await loadHtml2Canvas();
      const canvas = await html2canvas(document.body, {
        useCORS: true,
        allowTaint: false, // Set to false to avoid SecurityError taint exception on toDataURL
        x: window.scrollX,
        y: window.scrollY,
        width: document.documentElement.clientWidth,
        height: document.documentElement.clientHeight,
        scrollX: 0,
        scrollY: 0,
        ignoreElements: (element) => {
          return (
            element.id === "global-feedback-widget" ||
            element.id === "quick-suggestion-modal"
          );
        },
      });

      const dataUrl = canvas.toDataURL("image/png");
      setPreview(dataUrl);
      setIsConfirmed(false);
      onScreenshotConfirmed(null); // Parent must confirm explicitly
    } catch (err) {
      console.error("Full screen capture failed:", err);
    } finally {
      setCapturing(false);
      if (onCaptureEnd) onCaptureEnd();
    }
  };

  // Trigger Snipping Mode Draw Overlay
  const startSnippingMode = () => {
    setIsSnippingMode(true);
    setIsSelecting(false);
    if (onCaptureStart) onCaptureStart();
  };

  const handleMouseDown = (e: React.MouseEvent) => {
    if (e.button !== 0) return; // Left click only
    setIsSelecting(true);
    setStartX(e.clientX);
    setStartY(e.clientY);
    setCurrentX(e.clientX);
    setCurrentY(e.clientY);
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (!isSelecting) return;
    setCurrentX(e.clientX);
    setCurrentY(e.clientY);
  };

  const handleMouseUp = async (e: React.MouseEvent) => {
    if (!isSelecting) return;
    setIsSelecting(false);
    setIsSnippingMode(false);

    const left = Math.min(startX, currentX);
    const top = Math.min(startY, currentY);
    const width = Math.abs(startX - currentX);
    const height = Math.abs(startY - currentY);

    if (width < 10 || height < 10) {
      // Selection too small, cancel capture
      if (onCaptureEnd) onCaptureEnd();
      return;
    }

    try {
      setCapturing(true);

      // Delay to let overlay unmount and page repaint
      await new Promise((resolve) => setTimeout(resolve, 150));

      const html2canvas = await loadHtml2Canvas();
      const canvas = await html2canvas(document.body, {
        useCORS: true,
        allowTaint: false,
        x: window.scrollX,
        y: window.scrollY,
        width: document.documentElement.clientWidth,
        height: document.documentElement.clientHeight,
        scrollX: 0,
        scrollY: 0,
        ignoreElements: (element) => {
          return (
            element.id === "global-feedback-widget" ||
            element.id === "quick-suggestion-modal"
          );
        },
      });

      // Crop the body canvas to selection rectangle coordinates
      const croppedCanvas = document.createElement("canvas");
      croppedCanvas.width = width;
      croppedCanvas.height = height;
      const ctx = croppedCanvas.getContext("2d");

      if (ctx) {
        // Since the canvas matches the viewport starting at window.scrollY,
        // the client coordinates (left, top) map directly to the canvas!
        ctx.drawImage(
          canvas,
          left,
          top,
          width,
          height,
          0,
          0,
          width,
          height
        );
      }

      const dataUrl = croppedCanvas.toDataURL("image/png");
      setPreview(dataUrl);
      setIsConfirmed(false);
      onScreenshotConfirmed(null);
    } catch (err) {
      console.error("Area screen capture failed:", err);
    } finally {
      setCapturing(false);
      if (onCaptureEnd) onCaptureEnd();
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onloadend = () => {
      const dataUrl = reader.result as string;
      setPreview(dataUrl);
      setIsConfirmed(false);
      onScreenshotConfirmed(null);
    };
    reader.readAsDataURL(file);
  };

  const triggerUpload = () => {
    fileInputRef.current?.click();
  };

  const handleConfirm = () => {
    setIsConfirmed(true);
    onScreenshotConfirmed(preview);
  };

  const handleRemove = () => {
    setPreview(null);
    setIsConfirmed(false);
    onScreenshotConfirmed(null);
  };

  return (
    <div className="space-y-4">
      <input
        type="file"
        ref={fileInputRef}
        onChange={handleFileChange}
        accept="image/*"
        className="hidden"
      />

      {/* Snipping Overlay */}
      {isSnippingMode && (
        <div
          className="fixed inset-0 z-[9999] bg-black/40 cursor-crosshair select-none flex items-center justify-center"
          onMouseDown={handleMouseDown}
          onMouseMove={handleMouseMove}
          onMouseUp={handleMouseUp}
        >
          {/* Top Instruction banner */}
          <div className="absolute top-6 px-4 py-2 bg-slate-900 border border-slate-700 text-white rounded-xl text-xs font-bold shadow-2xl flex items-center gap-2 pointer-events-none">
            <span className="h-2 w-2 rounded-full bg-indigo-500 animate-ping" />
            Click and drag to select selection area. Press ESC to cancel.
          </div>

          {isSelecting && (
            <div
              className="absolute border-2 border-indigo-500 bg-indigo-500/10 shadow-[0_0_0_9999px_rgba(0,0,0,0.5)] pointer-events-none"
              style={{
                left: Math.min(startX, currentX),
                top: Math.min(startY, currentY),
                width: Math.abs(startX - currentX),
                height: Math.abs(startY - currentY),
              }}
            />
          )}
        </div>
      )}

      {!preview ? (
        <div className="grid grid-cols-3 gap-2">
          <button
            type="button"
            onClick={handleCaptureFull}
            disabled={capturing}
            className="flex flex-col items-center justify-center gap-1.5 p-3 rounded-xl border border-dashed border-slate-700 bg-slate-800/40 hover:bg-slate-800 hover:border-indigo-500/50 active:scale-95 transition-all text-slate-350 font-semibold cursor-pointer group"
          >
            <Camera className="h-4.5 w-4.5 text-indigo-400 group-hover:scale-110 transition-transform" />
            <span className="text-[10px] leading-none whitespace-nowrap">Full Screen</span>
          </button>

          <button
            type="button"
            onClick={startSnippingMode}
            disabled={capturing}
            className="flex flex-col items-center justify-center gap-1.5 p-3 rounded-xl border border-dashed border-slate-700 bg-slate-800/40 hover:bg-slate-800 hover:border-purple-500/50 active:scale-95 transition-all text-slate-350 font-semibold cursor-pointer group"
          >
            <Crop className="h-4.5 w-4.5 text-purple-400 group-hover:scale-110 transition-transform" />
            <span className="text-[10px] leading-none whitespace-nowrap">Select Area</span>
          </button>

          <button
            type="button"
            onClick={triggerUpload}
            className="flex flex-col items-center justify-center gap-1.5 p-3 rounded-xl border border-dashed border-slate-700 bg-slate-800/40 hover:bg-slate-800 hover:border-pink-500/50 active:scale-95 transition-all text-slate-350 font-semibold cursor-pointer group"
          >
            <Upload className="h-4.5 w-4.5 text-pink-400 group-hover:scale-110 transition-transform" />
            <span className="text-[10px] leading-none whitespace-nowrap">Upload File</span>
          </button>
        </div>
      ) : (
        <div className="space-y-3">
          <div className="relative rounded-xl overflow-hidden border border-slate-700 bg-slate-950 group">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={preview}
              alt="Screenshot Preview"
              className="max-h-[180px] w-full object-contain mx-auto"
            />
            {isConfirmed && (
              <div className="absolute inset-0 bg-emerald-950/40 backdrop-blur-[1.5px] flex items-center justify-center gap-1.5 animate-in fade-in duration-200">
                <span className="flex items-center justify-center h-8 w-8 rounded-full bg-emerald-500 text-white shadow-lg">
                  <Check className="h-4.5 w-4.5" strokeWidth={3} />
                </span>
                <span className="text-xs font-bold text-white uppercase tracking-wider bg-emerald-900/80 px-2 py-0.5 rounded">
                  Approved
                </span>
              </div>
            )}
          </div>

          <div className="flex items-center justify-between text-xs">
            {!isConfirmed ? (
              <>
                <button
                  type="button"
                  onClick={handleRemove}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-rose-950/30 hover:text-rose-450 text-slate-400 transition-colors cursor-pointer border border-slate-700/60 font-semibold"
                >
                  <Trash className="h-3.5 w-3.5" /> Discard
                </button>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={handleRemove}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 transition-colors cursor-pointer border border-slate-700/60 font-semibold"
                  >
                    <RotateCcw className="h-3.5 w-3.5" /> Retake
                  </button>
                  <button
                    type="button"
                    onClick={handleConfirm}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white font-bold transition-all shadow-md active:scale-95 cursor-pointer"
                  >
                    <Check className="h-3.5 w-3.5" /> Confirm
                  </button>
                </div>
              </>
            ) : (
              <button
                type="button"
                onClick={handleRemove}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-rose-950/30 hover:text-rose-450 text-slate-400 transition-colors cursor-pointer border border-slate-700/60 font-semibold"
              >
                <Trash className="h-3.5 w-3.5" /> Remove Screenshot
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
