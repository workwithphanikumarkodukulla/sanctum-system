"use client";

import React, { useRef } from "react";
import Editor, { OnMount } from "@monaco-editor/react";

interface MonacoCodeEditorProps {
  value: string;
  language?: string;
  onChange?: (value: string) => void;
  readOnly?: boolean;
}

export const MonacoCodeEditor: React.FC<MonacoCodeEditorProps> = ({
  value,
  language = "python",
  onChange,
  readOnly = false,
}) => {
  const editorRef = useRef<any>(null);

  // Map file extension/language names to Monaco standard language IDs
  const getMonacoLanguage = (lang: string) => {
    switch (lang.toLowerCase()) {
      case "py":
      case "python":
        return "python";
      case "rs":
      case "rust":
        return "rust";
      case "ts":
      case "typescript":
        return "typescript";
      case "js":
      case "javascript":
        return "javascript";
      case "json":
        return "json";
      case "md":
      case "markdown":
        return "markdown";
      case "sh":
      case "bash":
        return "shell";
      case "css":
        return "css";
      case "html":
        return "html";
      default:
        return "plaintext";
    }
  };

  const handleEditorDidMount: OnMount = (editor, monaco) => {
    editorRef.current = editor;

    // Define custom "sanctum-dark" theme matching Sanctum's obsidian & emerald palette
    monaco.editor.defineTheme("sanctum-dark", {
      base: "vs-dark",
      inherit: true,
      rules: [
        { token: "keyword", foreground: "76B900", fontStyle: "bold" },
        { token: "type", foreground: "4ade80" },
        { token: "string", foreground: "facc15" },
        { token: "number", foreground: "38bdf8" },
        { token: "comment", foreground: "52525b", fontStyle: "italic" },
        { token: "identifier", foreground: "f4f4f5" },
        { token: "delimiter", foreground: "a1a1aa" },
      ],
      colors: {
        "editor.background": "#0d0d0d",
        "editor.foreground": "#f4f4f5",
        "editor.lineHighlightBackground": "#141414",
        "editor.selectionBackground": "#76B90033",
        "editor.selectionHighlightBackground": "#76B90022",
        "editorCursor.foreground": "#76B900",
        "editorWhitespace.foreground": "#27272a",
        "editorIndentGuide.background": "#1e1e24",
        "editorIndentGuide.activeBackground": "#76B90066",
        "editorLineNumber.foreground": "#4b5563",
        "editorLineNumber.activeForeground": "#76B900",
        "editorGutter.background": "#0d0d0d",
        "minimap.background": "#0a0a0a",
      },
    });

    monaco.editor.setTheme("sanctum-dark");
  };

  return (
    <div className="w-full h-full relative overflow-hidden bg-[#0d0d0d]">
      <Editor
        height="100%"
        width="100%"
        language={getMonacoLanguage(language)}
        theme="sanctum-dark"
        value={value}
        onChange={(val) => onChange?.(val || "")}
        onMount={handleEditorDidMount}
        loading={
          <div className="flex items-center justify-center h-full w-full bg-[#0d0d0d] text-neutral-500 font-mono text-xs gap-2">
            <span className="w-3.5 h-3.5 rounded-full border-2 border-neutral-600 border-t-[#76B900] animate-spin" />
            <span>Initializing Monaco Engine...</span>
          </div>
        }
        options={{
          readOnly,
          fontSize: 13,
          fontFamily: "'JetBrains Mono', 'Fira Code', ui-monospace, monospace",
          lineHeight: 22,
          minimap: {
            enabled: false,
          },
          scrollBeyondLastLine: false,
          automaticLayout: true,
          smoothScrolling: true,
          cursorBlinking: "smooth",
          cursorSmoothCaretAnimation: "on",
          renderLineHighlight: "all",
          padding: { top: 12, bottom: 12 },
          bracketPairColorization: { enabled: true },
          guides: {
            bracketPairs: true,
            indentation: true,
          },
          scrollbar: {
            vertical: "visible",
            horizontal: "auto",
            verticalScrollbarSize: 8,
            horizontalScrollbarSize: 8,
            useShadows: false,
          },
          overviewRulerBorder: false,
          hideCursorInOverviewRuler: true,
          contextmenu: true,
          folding: true,
          wordWrap: "off",
        }}
      />
    </div>
  );
};
