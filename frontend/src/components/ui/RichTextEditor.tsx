"use client";

import { useEffect, useRef, useState } from "react";
import { Bold, Italic, Underline, RotateCcw } from "lucide-react";

interface RichTextEditorProps {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  className?: string;
}

export default function RichTextEditor({
  value,
  onChange,
  placeholder = "Write here...",
  className = "",
}: RichTextEditorProps) {
  const editorRef = useRef<HTMLDivElement>(null);
  const isEditing = useRef(false);

  // Sync value from prop to editor innerHTML (only when not actively editing)
  useEffect(() => {
    if (editorRef.current && !isEditing.current) {
      const currentHTML = editorRef.current.innerHTML;
      if (currentHTML !== value) {
        editorRef.current.innerHTML = value || "";
      }
    }
  }, [value]);

  const handleInput = () => {
    if (editorRef.current) {
      isEditing.current = true;
      let html = editorRef.current.innerHTML;
      
      // If it only contains a break or is empty, normalize it to empty string
      if (html === "<br>" || html === "<p><br></p>" || html === "<div><br></div>") {
        html = "";
      }
      
      onChange(html);
      isEditing.current = false;
    }
  };

  const executeCommand = (command: string) => {
    document.execCommand(command, false);
    handleInput();
  };

  return (
    <div className={`border border-gray-300 rounded-md overflow-hidden bg-white focus-within:border-blue-500 focus-within:ring-1 focus-within:ring-blue-500 ${className}`}>
      {/* Toolbar */}
      <div className="flex items-center gap-1 bg-gray-50 border-b border-gray-200 p-1.5 flex-wrap">
        <button
          type="button"
          onClick={() => executeCommand("bold")}
          className="p-1 hover:bg-gray-200 rounded text-gray-700 transition-colors"
          title="Bold"
        >
          <Bold size={16} />
        </button>
        <button
          type="button"
          onClick={() => executeCommand("italic")}
          className="p-1 hover:bg-gray-200 rounded text-gray-700 transition-colors"
          title="Italic"
        >
          <Italic size={16} />
        </button>
        <button
          type="button"
          onClick={() => executeCommand("underline")}
          className="p-1 hover:bg-gray-200 rounded text-gray-700 transition-colors"
          title="Underline"
        >
          <Underline size={16} />
        </button>
        <button
          type="button"
          onClick={() => executeCommand("removeFormat")}
          className="p-1 hover:bg-gray-200 rounded text-gray-700 transition-colors ml-auto"
          title="Clear formatting"
        >
          <RotateCcw size={14} />
        </button>
      </div>

      {/* Editor Content Area */}
      <div
        ref={editorRef}
        contentEditable
        onInput={handleInput}
        onBlur={handleInput}
        className="rich-text-editor-content override-email-colors p-3 min-h-[150px] outline-none text-sm text-gray-800 font-sans break-words overflow-y-auto"
        data-placeholder={placeholder}
      />

      <style dangerouslySetInnerHTML={{ __html: `
        .rich-text-editor-content:empty:before {
          content: attr(data-placeholder);
          color: #9ca3af;
          cursor: text;
          display: block;
        }
      `}} />
    </div>
  );
}
