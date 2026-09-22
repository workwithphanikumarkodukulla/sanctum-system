"use client";

import React, { useState, useRef, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Folder,
  FolderOpen,
  FileCode,
  FileText,
  File,
  ChevronRight,
  ChevronDown,
  Bot,
  RefreshCw,
  PanelRightClose,
  PanelRightOpen,
  Sparkles,
  Terminal,
  Maximize2,
  Minimize2,
  Play,
  Trash2,
  FilePlus,
  FolderPlus,
  FolderInput,
  FolderSearch,
  Lock,
  X,
  Upload,
  BookOpen,
  Presentation,
  Table as TableIcon,
  Image as ImageIcon,
  Key,
  Shield,
  ShieldCheck,
  Eye,
  Check,
  Copy,
  Unlock,
} from "lucide-react";
import { FileItem } from "@/types";
import { sampleWorkspaceFiles } from "@/lib/mockData";
import { AgentChatPanel } from "@/components/agent-chat/AgentChatPanel";
import { MonacoCodeEditor } from "@/components/editor/MonacoCodeEditor";
import { DocumentViewer, getDocumentType } from "@/components/editor/DocumentViewer";
import { InteractiveTerminal } from "@/components/terminal/InteractiveTerminal";
import { copyToClipboard } from "@/lib/utils";
import { SanctumLogo } from "@/components/ui/sanctum-logo";


interface WorkspaceScreenProps {
  files?: FileItem[];
  onAskAgentAboutFile?: (fileName: string, content: string) => void;
}

export const WorkspaceScreen: React.FC<WorkspaceScreenProps> = ({
  files = sampleWorkspaceFiles,
  onAskAgentAboutFile,
}) => {
  const [workspaceFiles, setWorkspaceFiles] = useState<FileItem[]>(() => {
    if (typeof window !== "undefined") {
      try {
        const saved = localStorage.getItem("sanctum_workspace_files");
        if (saved) {
          const parsed = JSON.parse(saved);
          if (Array.isArray(parsed) && parsed.length > 0) return parsed;
        }
      } catch {}
    }
    return files;
  });

  const [workspacePath, setWorkspacePath] = useState<string>(() => {
    if (typeof window !== "undefined") {
      try {
        const saved = localStorage.getItem("sanctum_workspace_path");
        if (saved) return saved;
      } catch {}
    }
    return "/workspace";
  });

  const [activeFile, setActiveFile] = useState<FileItem | null>(() => {
    if (typeof window !== "undefined") {
      try {
        const saved = localStorage.getItem("sanctum_active_file");
        if (saved) return JSON.parse(saved);
      } catch {}
    }
    return files[0] || null;
  });

  const [openTabs, setOpenTabs] = useState<FileItem[]>(() => {
    if (typeof window !== "undefined") {
      try {
        const saved = localStorage.getItem("sanctum_open_tabs");
        if (saved) {
          const parsed = JSON.parse(saved);
          if (Array.isArray(parsed) && parsed.length > 0) return parsed;
        }
      } catch {}
    }
    return [files[0], files[1]].filter(Boolean);
  });

  const [expandedFolders, setExpandedFolders] = useState<Record<string, boolean>>({
    generated: true,
    app: true,
    src: true,
  });
  const [isCreatingItem, setIsCreatingItem] = useState<"file" | "folder" | null>(null);
  const [newItemName, setNewItemName] = useState("");
  const newItemInputRef = useRef<HTMLInputElement>(null);
  const folderInputRef = useRef<HTMLInputElement>(null);
  const fileStoreRef = useRef<Map<string, any>>(new Map());
  const [activeFileObject, setActiveFileObject] = useState<File | null>(null);
  const refreshWorkspaceFiles = async () => {
    try {
      const res = await fetch("/api/backend/workspace/tree");
      if (res.ok) {
        const data = await res.json();
        if (data && data.tree) {
          const nodes = normalizeBackendTree(data.tree);
          setWorkspaceFiles(nodes);
        }
      }
    } catch {}
  };

  // Helper to render appropriate file icon based on file extension
  const renderItemIcon = (filename: string, className = "w-3.5 h-3.5 shrink-0") => {
    const ext = filename.split(".").pop()?.toLowerCase() || "";
    if (ext === "pdf") {
      return <FileText className={`${className} text-rose-400`} />;
    }
    if (["docx", "doc"].includes(ext)) {
      return <BookOpen className={`${className} text-blue-400`} />;
    }
    if (["pptx", "ppt"].includes(ext)) {
      return <Presentation className={`${className} text-amber-400`} />;
    }
    if (["xlsx", "xls", "csv"].includes(ext)) {
      return <TableIcon className={`${className} text-emerald-400`} />;
    }
    if (["png", "jpg", "jpeg", "webp", "svg", "gif", "ico", "bmp"].includes(ext)) {
      return <ImageIcon className={`${className} text-purple-400`} />;
    }
    if (["py", "rs", "ts", "tsx", "js", "jsx", "json", "html", "css", "sh", "toml", "yaml", "yml"].includes(ext)) {
      return <FileCode className={`${className} text-[#76B900]`} />;
    }
    return <File className={`${className} text-neutral-400`} />;
  };

  // Helper to normalize backend directory tree into FileItem[]
  const normalizeBackendTree = (nodes: any[]): FileItem[] => {
    return nodes
      .filter((n) => {
        const name = n.name || "";
        return (
          name !== ".git" &&
          name !== "node_modules" &&
          name !== "__pycache__" &&
          name !== ".next" &&
          name !== ".DS_Store"
        );
      })
      .map((node) => {
        const isDir = node.type === "directory" || Boolean(node.isDirectory);
        const ext = node.name.split(".").pop()?.toLowerCase() || "";
        return {
          name: node.name,
          path: node.path,
          isDirectory: isDir,
          size: node.size || (isDir ? undefined : "1 KB"),
          language: isDir ? undefined : (langMap[ext] || "plaintext"),
          isLocked: Boolean(node.is_locked),
          children: node.children ? normalizeBackendTree(node.children) : undefined,
        };
      })
      .sort((a, b) => {
        if (a.isDirectory && !b.isDirectory) return -1;
        if (!a.isDirectory && b.isDirectory) return 1;
        return a.name.localeCompare(b.name);
      });
  };

  // Sync workspace state to localStorage safely (without heavy file contents to avoid quota errors)
  useEffect(() => {
    if (typeof window !== "undefined") {
      try {
        const sanitizeForStorage = (items: FileItem[]): FileItem[] =>
          items.map((it) => ({
            name: it.name,
            path: it.path,
            isDirectory: it.isDirectory,
            size: it.size,
            language: it.language,
            children: it.children ? sanitizeForStorage(it.children) : undefined,
          }));

        localStorage.setItem("sanctum_workspace_files", JSON.stringify(sanitizeForStorage(workspaceFiles)));
        localStorage.setItem("sanctum_workspace_path", workspacePath);
        if (activeFile) {
          localStorage.setItem(
            "sanctum_active_file",
            JSON.stringify({
              name: activeFile.name,
              path: activeFile.path,
              isDirectory: activeFile.isDirectory,
            })
          );
        }
      } catch (err) {
        console.warn("localStorage write skipped:", err);
      }
    }
  }, [workspaceFiles, workspacePath, activeFile]);

  // On mount: sync with backend active workspace if available
  useEffect(() => {
    fetch("/api/backend/workspace/tree")
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (data && data.tree && data.tree.length > 0) {
          const nodes = normalizeBackendTree(data.tree);
          if (nodes.length > 0) {
            setWorkspaceFiles(nodes);
            if (data.path) {
              const name = data.path.split("/").filter(Boolean).pop() || "workspace";
              setWorkspacePath(name);
            }
            const newExp: Record<string, boolean> = {};
            nodes.forEach((n) => {
              if (n.isDirectory) {
                newExp[n.path] = true;
                newExp[n.name] = true;
              }
            });
            setExpandedFolders((prev) => ({ ...newExp, ...prev }));
            const first = findFirstCodeFile(nodes);
            if (first && !activeFile) {
              handleSelectFile(first);
            }
          }
        }
      })
      .catch(() => {});
  }, []);

  const langMap: Record<string, string> = {
    py: "python",
    rs: "rust",
    js: "javascript",
    ts: "typescript",
    tsx: "typescript",
    jsx: "javascript",
    json: "json",
    md: "markdown",
    css: "css",
    html: "html",
    sh: "shell",
    sql: "sql",
    txt: "plaintext",
    yml: "yaml",
    yaml: "yaml",
  };

  const findFirstCodeFile = (items: FileItem[]): FileItem | null => {
    for (const item of items) {
      if (!item.isDirectory) return item;
      if (item.children && item.children.length > 0) {
        const found = findFirstCodeFile(item.children);
        if (found) return found;
      }
    }
    return null;
  };

  // ── Fast Directory Iterator for Browser File System Access API ──
  const readDirectoryRecursiveFast = async (
    dirHandle: any,
    parentPath = ""
  ): Promise<FileItem[]> => {
    const items: FileItem[] = [];
    try {
      // Use entries() iterator to get [name, handle]
      const entriesIterator = typeof dirHandle.entries === "function" ? dirHandle.entries() : dirHandle;
      for await (const [name, entry] of entriesIterator) {
        if (
          name === ".git" ||
          name === "node_modules" ||
          name === "__pycache__" ||
          name === ".next" ||
          name === "dist" ||
          name === "build" ||
          name === ".turbo" ||
          name === ".DS_Store"
        ) {
          continue;
        }
        const itemPath = parentPath ? `${parentPath}/${name}` : name;

        if (entry.kind === "file") {
          fileStoreRef.current.set(itemPath, entry);
          const ext = name.split(".").pop()?.toLowerCase() || "";
          items.push({
            name,
            path: itemPath,
            isDirectory: false,
            size: "1 KB",
            modified: "Local",
            language: langMap[ext] || "plaintext",
          });
        } else if (entry.kind === "directory") {
          const children = await readDirectoryRecursiveFast(entry, itemPath);
          items.push({
            name,
            path: itemPath,
            isDirectory: true,
            children,
          });
        }
      }
    } catch (err) {
      console.error("Error reading directory handle:", err);
    }

    return items.sort((a, b) => {
      if (a.isDirectory && !b.isDirectory) return -1;
      if (!a.isDirectory && b.isDirectory) return 1;
      return a.name.localeCompare(b.name);
    });
  };

  // ── Fast HTML5 Native Directory Input Handler ──
  const handleNativeFolderSelected = (e: React.ChangeEvent<HTMLInputElement>) => {
    const fileList = e.target.files;
    if (!fileList || fileList.length === 0) return;

    const files = Array.from(fileList);
    const sampleRel = files[0].webkitRelativePath || files[0].name;
    const rootDirName = sampleRel.includes("/") ? sampleRel.split("/")[0] : "workspace";
    setWorkspacePath(rootDirName);

    const rootNodes: FileItem[] = [];
    const newExp: Record<string, boolean> = {};

    for (const file of files) {
      const rel = file.webkitRelativePath || file.name;
      if (
        rel.includes("/node_modules/") ||
        rel.includes("/.git/") ||
        rel.includes("/.next/") ||
        rel.includes("/dist/") ||
        rel.includes("/__pycache__/") ||
        rel.includes("/.DS_Store")
      ) {
        continue;
      }
      const rawSegments = rel.split("/");
      const segments = rawSegments.length > 1 ? rawSegments.slice(1) : rawSegments;
      if (segments.length === 0) continue;

      let currentChildren = rootNodes;
      let accumulatedPath = "";

      for (let i = 0; i < segments.length; i++) {
        const seg = segments[i];
        const isFile = i === segments.length - 1;
        accumulatedPath = accumulatedPath ? `${accumulatedPath}/${seg}` : seg;

        if (isFile) {
          fileStoreRef.current.set(accumulatedPath, file);
          const ext = seg.split(".").pop()?.toLowerCase() || "";
          currentChildren.push({
            name: seg,
            path: accumulatedPath,
            isDirectory: false,
            size: `${Math.max(1, Math.round(file.size / 1024))} KB`,
            modified: "Local",
            language: langMap[ext] || "plaintext",
          });
        } else {
          let folderNode = currentChildren.find((n) => n.isDirectory && n.name === seg);
          if (!folderNode) {
            folderNode = {
              name: seg,
              path: accumulatedPath,
              isDirectory: true,
              children: [],
            };
            currentChildren.push(folderNode);
          }
          newExp[accumulatedPath] = true;
          newExp[seg] = true;
          currentChildren = folderNode.children || (folderNode.children = []);
        }
      }
    }

    if (rootNodes.length > 0) {
      const sortItems = (items: FileItem[]) => {
        items.sort((a, b) => {
          if (a.isDirectory && !b.isDirectory) return -1;
          if (!a.isDirectory && b.isDirectory) return 1;
          return a.name.localeCompare(b.name);
        });
        for (const item of items) {
          if (item.children) sortItems(item.children);
        }
      };
      sortItems(rootNodes);

      setWorkspaceFiles(rootNodes);
      setExpandedFolders((prev) => ({ ...prev, ...newExp }));

      const first = findFirstCodeFile(rootNodes);
      if (first) {
        handleSelectFile(first);
      }
    }

    e.target.value = "";
  };

  // ── Open Native Directory Picker Directly (VS Code Style) ──
  const handleOpenFolder = async () => {
    // 1. Try Native Desktop macOS Finder Picker via Sanctum Backend
    try {
      const pickRes = await fetch("/api/backend/workspace/pick", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
      });
      if (pickRes.ok) {
        const pickData = await pickRes.json();
        if (pickData.cancelled) return;
        if (pickData.path) {
          const folderName = pickData.path.split("/").filter(Boolean).pop() || "workspace";
          setWorkspacePath(folderName);

          const treeRes = await fetch("/api/backend/workspace/tree");
          if (treeRes.ok) {
            const treeData = await treeRes.json();
            const nodes = normalizeBackendTree(treeData.tree || []);
            if (nodes.length > 0) {
              setWorkspaceFiles(nodes);
              const newExp: Record<string, boolean> = {};
              nodes.forEach((n) => {
                if (n.isDirectory) {
                  newExp[n.path] = true;
                  newExp[n.name] = true;
                }
              });
              setExpandedFolders(newExp);
              const first = findFirstCodeFile(nodes);
              if (first) {
                handleSelectFile(first);
              }
              return;
            }
          }
        }
      }
    } catch (e) {
      console.warn("Backend pick error, trying browser File System API:", e);
    }

    // 2. Try VS Code's exact File System Access API (macOS Chrome/Edge native Finder directory picker)
    if (typeof window !== "undefined" && "showDirectoryPicker" in window) {
      try {
        const dirHandle = await (window as any).showDirectoryPicker();
        if (!dirHandle) return;

        setWorkspacePath(dirHandle.name);
        const rootNodes = await readDirectoryRecursiveFast(dirHandle);
        if (rootNodes.length > 0) {
          setWorkspaceFiles(rootNodes);
          const newExp: Record<string, boolean> = {};
          rootNodes.forEach((n) => {
            if (n.isDirectory) {
              newExp[n.path] = true;
              newExp[n.name] = true;
            }
          });
          setExpandedFolders(newExp);

          const first = findFirstCodeFile(rootNodes);
          if (first) {
            handleSelectFile(first);
          }
        }
        return;
      } catch (err: any) {
        if (err.name === "AbortError") return;
        console.warn("showDirectoryPicker failed, trying input fallback:", err);
      }
    }

    // 3. Fallback: Native <input type="file" webkitdirectory>
    if (folderInputRef.current) {
      folderInputRef.current.value = "";
      folderInputRef.current.click();
    }
  };

  // Listen for global open-folder trigger event
  useEffect(() => {
    const handleTrigger = () => {
      handleOpenFolder();
    };
    window.addEventListener("sanctum:open-folder", handleTrigger);
    return () => window.removeEventListener("sanctum:open-folder", handleTrigger);
  }, []);

  useEffect(() => {
    if (isCreatingItem) {
      setTimeout(() => newItemInputRef.current?.focus(), 40);
    }
  }, [isCreatingItem]);
  const [editorContent, setEditorContent] = useState<string>(files[0]?.content || "");
  const [isChatOpen, setIsChatOpen] = useState(true);

  // ── Panel Resizing State (VS Code / Sanctum Agent Style) ──
  const [explorerWidth, setExplorerWidth] = useState(240);
  const [chatWidth, setChatWidth] = useState(420);
  const [isTerminalOpen, setIsTerminalOpen] = useState(false);
  const [terminalHeight, setTerminalHeight] = useState(160);

  const [isDraggingExplorer, setIsDraggingExplorer] = useState(false);
  const [isDraggingChat, setIsDraggingChat] = useState(false);
  const [isDraggingTerminal, setIsDraggingTerminal] = useState(false);

  const containerRef = useRef<HTMLDivElement>(null);

  // ── Explorer Horizontal Drag Handler ──
  const handleStartResizeExplorer = (e: React.PointerEvent) => {
    e.preventDefault();
    setIsDraggingExplorer(true);
    const startX = e.clientX;
    const startWidth = explorerWidth;
    let rAF: number | null = null;

    const onPointerMove = (ev: PointerEvent) => {
      if (rAF !== null) return;
      rAF = requestAnimationFrame(() => {
        const delta = ev.clientX - startX;
        const newWidth = Math.max(160, Math.min(520, startWidth + delta));
        setExplorerWidth(newWidth);
        rAF = null;
      });
    };

    const onPointerUp = () => {
      if (rAF !== null) cancelAnimationFrame(rAF);
      setIsDraggingExplorer(false);
      document.removeEventListener("pointermove", onPointerMove);
      document.removeEventListener("pointerup", onPointerUp);
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
    };

    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";
    document.addEventListener("pointermove", onPointerMove);
    document.addEventListener("pointerup", onPointerUp);
  };

  // ── Chat Panel Horizontal Drag Handler ──
  const handleStartResizeChat = (e: React.PointerEvent) => {
    e.preventDefault();
    setIsDraggingChat(true);
    const startX = e.clientX;
    const startWidth = chatWidth;
    let rAF: number | null = null;

    const onPointerMove = (ev: PointerEvent) => {
      if (rAF !== null) return;
      rAF = requestAnimationFrame(() => {
        const delta = startX - ev.clientX; // Dragging left increases width
        const newWidth = Math.max(300, Math.min(780, startWidth + delta));
        setChatWidth(newWidth);
        rAF = null;
      });
    };

    const onPointerUp = () => {
      if (rAF !== null) cancelAnimationFrame(rAF);
      setIsDraggingChat(false);
      document.removeEventListener("pointermove", onPointerMove);
      document.removeEventListener("pointerup", onPointerUp);
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
    };

    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";
    document.addEventListener("pointermove", onPointerMove);
    document.addEventListener("pointerup", onPointerUp);
  };

  // ── Terminal Vertical Drag Handler ──
  const handleStartResizeTerminal = (e: React.PointerEvent) => {
    e.preventDefault();
    setIsDraggingTerminal(true);
    const startY = e.clientY;
    const startHeight = terminalHeight;
    let rAF: number | null = null;

    const onPointerMove = (ev: PointerEvent) => {
      if (rAF !== null) return;
      rAF = requestAnimationFrame(() => {
        const delta = startY - ev.clientY; // Dragging up increases height
        const newHeight = Math.max(80, Math.min(420, startHeight + delta));
        setTerminalHeight(newHeight);
        rAF = null;
      });
    };

    const onPointerUp = () => {
      if (rAF !== null) cancelAnimationFrame(rAF);
      setIsDraggingTerminal(false);
      document.removeEventListener("pointermove", onPointerMove);
      document.removeEventListener("pointerup", onPointerUp);
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
    };

    document.body.style.cursor = "row-resize";
    document.body.style.userSelect = "none";
    document.addEventListener("pointermove", onPointerMove);
    document.addEventListener("pointerup", onPointerUp);
  };

  const handleSelectFile = async (file: FileItem) => {
    if (file.isDirectory) {
      setExpandedFolders((prev) => ({
        ...prev,
        [file.path]: !prev[file.path],
        [file.name]: !prev[file.path],
      }));
      return;
    }
    setActiveFile(file);
    if (!openTabs.find((t) => t.path === file.path)) {
      setOpenTabs((prev) => [...prev, file]);
    }

    // Resolve local File object if available in fileStoreRef
    const stored = fileStoreRef.current.get(file.path);
    if (stored) {
      if (typeof window !== "undefined" && stored instanceof window.File) {
        setActiveFileObject(stored as File);
      } else if (typeof stored.getFile === "function") {
        try {
          const f = await stored.getFile();
          setActiveFileObject(f as File);
        } catch {}
      }
    } else {
      setActiveFileObject(null);
    }

    // If file is a visual document (PDF, PPTX, DOCX, Spreadsheet, Image), DocumentViewer handles visual presentation
    if (getDocumentType(file.name)) {
      return;
    }

    // 1. If content already present in memory, use it
    if (file.content) {
      setEditorContent(file.content);
      return;
    }

    // 2. If browser File object or FileSystemFileHandle was stored
    if (stored) {
      try {
        let text = "";
        if (typeof stored.text === "function") {
          text = await stored.text();
        } else if (typeof stored.getFile === "function") {
          const f = await stored.getFile();
          text = await f.text();
        }
        file.content = text;
        setEditorContent(text);
        return;
      } catch (err) {
        console.warn("Error reading stored file handle:", err);
      }
    }

    // 3. If file is from backend workspace
    try {
      const res = await fetch(`/api/backend/workspace/file?path=${encodeURIComponent(file.path)}`);
      if (res.ok) {
        const data = await res.json();
        if (typeof data.content === "string") {
          file.content = data.content;
          setEditorContent(data.content);
          return;
        }
      }
    } catch {}

    setEditorContent(`# ${file.name}\n# Sovereign file ready in workspace.`);
  };

  const handleCloseTab = (e: React.MouseEvent, tabPath: string) => {
    e.stopPropagation();
    const filtered = openTabs.filter((t) => t.path !== tabPath);
    setOpenTabs(filtered);
    if (activeFile?.path === tabPath) {
      if (filtered.length > 0) {
        const next = filtered[filtered.length - 1];
        setActiveFile(next);
        const stored = fileStoreRef.current.get(next.path);
        if (typeof window !== "undefined" && stored instanceof window.File) {
          setActiveFileObject(stored as File);
        } else if (stored && typeof stored.getFile === "function") {
          stored.getFile().then((f: any) => setActiveFileObject(f as File)).catch(() => {});
        } else {
          setActiveFileObject(null);
        }
        if (!getDocumentType(next.name)) {
          setEditorContent(next.content || "");
        }
      } else {
        setActiveFile(null);
        setActiveFileObject(null);
        setEditorContent("");
      }
    }
  };

  const handleCommitNewItem = () => {
    const name = newItemName.trim();
    if (!name) {
      setIsCreatingItem(null);
      setNewItemName("");
      return;
    }

    if (isCreatingItem === "file") {
      const ext = name.split(".").pop()?.toLowerCase() || "";
      const langMap: Record<string, string> = {
        py: "python",
        js: "javascript",
        ts: "typescript",
        tsx: "typescript",
        jsx: "javascript",
        json: "json",
        rs: "rust",
        md: "markdown",
        css: "css",
        html: "html",
        sh: "shell",
        sql: "sql",
      };

      const newFile: FileItem = {
        name,
        path: name,
        isDirectory: false,
        size: "0 B",
        modified: "Just now",
        language: langMap[ext] || "plaintext",
        content: `# ${name}\n\n`,
      };

      setWorkspaceFiles((prev) => [newFile, ...prev]);
      setActiveFile(newFile);
      setEditorContent(newFile.content || "");
      setOpenTabs((prev) => {
        if (!prev.find((t) => t.path === newFile.path)) {
          return [...prev, newFile];
        }
        return prev;
      });
    } else if (isCreatingItem === "folder") {
      const newFolder: FileItem = {
        name,
        path: name,
        isDirectory: true,
        children: [],
      };
      setWorkspaceFiles((prev) => [newFolder, ...prev]);
      setExpandedFolders((prev) => ({ ...prev, [name]: true }));
    }

    setIsCreatingItem(null);
    setNewItemName("");
  };

  const handleDeleteItem = (e: React.MouseEvent, targetPath: string) => {
    e.stopPropagation();
    const deleteRecursive = (items: FileItem[]): FileItem[] => {
      return items
        .filter((item) => item.path !== targetPath)
        .map((item) => {
          if (item.children) {
            return { ...item, children: deleteRecursive(item.children) };
          }
          return item;
        });
    };
    setWorkspaceFiles((prev) => deleteRecursive(prev));
    setOpenTabs((prev) => prev.filter((t) => t.path !== targetPath));
    if (activeFile?.path === targetPath) {
      setActiveFile(null);
      setEditorContent("");
    }
  };

  const renderTreeItem = (item: FileItem, depth = 0) => {
    const isExpanded = expandedFolders[item.path];
    const isSelected = activeFile?.path === item.path;

    return (
      <div key={item.path}>
        <div
          onClick={() => handleSelectFile(item)}
          style={{ paddingLeft: `${depth * 12 + 8}px` }}
          className={`flex items-center justify-between py-1.5 pr-2 rounded-md text-xs cursor-pointer select-none transition-colors group ${
            isSelected
              ? "bg-[#1f2b14] text-[#9ae018] font-medium"
              : "text-neutral-300 hover:bg-[#1c1c1c] hover:text-white"
          }`}
        >
          <div className="flex items-center gap-2 truncate flex-1 min-w-0">
            {item.isDirectory ? (
              <>
                {isExpanded ? (
                  <ChevronDown className="w-3.5 h-3.5 text-neutral-400 shrink-0" />
                ) : (
                  <ChevronRight className="w-3.5 h-3.5 text-neutral-400 shrink-0" />
                )}
                {isExpanded ? (
                  <FolderOpen className="w-4 h-4 text-[#76B900] shrink-0" />
                ) : (
                  <Folder className="w-4 h-4 text-[#76B900] shrink-0" />
                )}
              </>
            ) : (
              <>
                <span className="w-3.5" />
                {renderItemIcon(item.name)}
              </>
            )}
            <span className="truncate">{item.name}</span>
          </div>

          <div className="flex items-center gap-1 shrink-0 ml-1">
            {item.size && (
              <span className="text-[10px] font-mono text-neutral-500 group-hover:hidden">
                {item.size}
              </span>
            )}
            <button
              onClick={(e) => handleDeleteItem(e, item.path)}
              title={`Delete ${item.name}`}
              className="p-0.5 hover:text-rose-400 text-neutral-500 rounded transition-colors opacity-0 group-hover:opacity-100"
            >
              <Trash2 className="w-3 h-3" />
            </button>
          </div>
        </div>

        {item.isDirectory && isExpanded && item.children && (
          <div>
            {item.children.map((child) => renderTreeItem(child, depth + 1))}
          </div>
        )}
      </div>
    );
  };

  const getAllFiles = (items: FileItem[]): string[] => {
    let result: string[] = [];
    for (const item of items) {
      if (!item.isDirectory) {
        result.push(item.name);
      } else if (item.children) {
        result = result.concat(getAllFiles(item.children));
      }
    }
    return result;
  };
  const availableFlatFiles = getAllFiles(workspaceFiles);

  return (
    <div
      ref={containerRef}
      className="h-full flex overflow-hidden select-none bg-[#0a0a0a] relative"
    >
      {/* Global transparent drag capture overlay to prevent Monaco cursor traps */}
      {(isDraggingExplorer || isDraggingChat || isDraggingTerminal) && (
        <div className="fixed inset-0 z-50 bg-transparent select-none pointer-events-auto" />
      )}

      {/* ── PANEL 1: File Tree Explorer Sidebar (Left, Resizable) ── */}
      <div
        style={{ width: `${explorerWidth}px` }}
        className="bg-[#111111] border-r border-[#202020] flex flex-col shrink-0 relative will-change-[width]"
      >
        {/* Explorer Header with VS Code Actions */}
        <div className="p-2.5 px-3 border-b border-[#202020] flex items-center justify-between shrink-0">
          <div className="flex items-center gap-1.5 min-w-0">
            <span className="text-xs font-mono font-semibold uppercase tracking-wider text-neutral-300">
              Explorer
            </span>
            <button
              type="button"
              onClick={handleOpenFolder}
              title="Click to Open/Change Workspace Folder (VS Code style)"
              className="text-[10px] font-mono px-1.5 py-0.5 bg-[#1e1e1e] hover:bg-[#282828] text-[#76B900] rounded flex items-center gap-1 border border-white/5 truncate max-w-[110px] transition-colors cursor-pointer"
            >
              <FolderOpen className="w-3 h-3 shrink-0" />
              <span className="truncate">{workspacePath}</span>
            </button>
          </div>

          <div className="flex items-center gap-1 text-neutral-400">
            <button
              type="button"
              onClick={handleOpenFolder}
              title="Open Folder (Select Directory)..."
              className="p-1 rounded hover:bg-white/10 hover:text-white transition-colors cursor-pointer text-neutral-400 hover:text-[#76B900]"
            >
              <FolderSearch className="w-3.5 h-3.5" />
            </button>
            <button
              onClick={() => {
                setIsCreatingItem("file");
                setNewItemName("");
              }}
              title="New File..."
              className="p-1 rounded hover:bg-white/10 hover:text-white transition-colors cursor-pointer text-neutral-400 hover:text-[#76B900]"
            >
              <FilePlus className="w-3.5 h-3.5" />
            </button>
            <button
              onClick={() => {
                setIsCreatingItem("folder");
                setNewItemName("");
              }}
              title="New Folder..."
              className="p-1 rounded hover:bg-white/10 hover:text-white transition-colors cursor-pointer text-neutral-400 hover:text-[#76B900]"
            >
              <FolderPlus className="w-3.5 h-3.5" />
            </button>
            <button
              onClick={() => setExpandedFolders({})}
              title="Collapse All Folders"
              className="p-1 rounded hover:bg-white/10 hover:text-white transition-colors cursor-pointer text-neutral-400 hover:text-white"
            >
              <FolderInput className="w-3.5 h-3.5" />
            </button>
            <button
              onClick={() => setWorkspaceFiles([...sampleWorkspaceFiles])}
              title="Reset / Refresh Workspace"
              className="p-1 rounded hover:bg-white/10 hover:text-white transition-colors cursor-pointer text-neutral-400 hover:text-white"
            >
              <RefreshCw className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>

        {/* File Tree List */}
        <div className="flex-1 overflow-y-auto p-2 space-y-0.5">
          {/* Quick Open Folder Action */}
          <button
            type="button"
            onClick={handleOpenFolder}
            className="w-full flex items-center justify-center gap-2 py-1.5 px-2 mb-2 rounded bg-white/[0.04] hover:bg-[#76B900]/15 hover:border-[#76B900]/50 text-neutral-300 hover:text-white border border-white/10 text-[11px] font-mono transition-all group cursor-pointer"
          >
            <FolderOpen className="w-3.5 h-3.5 text-[#76B900] group-hover:scale-110 transition-transform" />
            <span>Open Folder...</span>
          </button>

          {/* Inline New Item Creation Box */}
          {isCreatingItem && (
            <div className="flex items-center gap-2 px-2 py-1 bg-[#161616] border border-[#76B900]/70 rounded-md text-xs font-mono shadow-[0_0_10px_rgba(118,185,0,0.2)] mb-1.5">
              {isCreatingItem === "file" ? (
                <FileCode className="w-3.5 h-3.5 text-[#76B900] shrink-0" />
              ) : (
                <Folder className="w-3.5 h-3.5 text-[#76B900] shrink-0" />
              )}
              <input
                ref={newItemInputRef}
                type="text"
                value={newItemName}
                onChange={(e) => setNewItemName(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.preventDefault();
                    handleCommitNewItem();
                  } else if (e.key === "Escape") {
                    setIsCreatingItem(null);
                    setNewItemName("");
                  }
                }}
                onBlur={handleCommitNewItem}
                placeholder={isCreatingItem === "file" ? "file_name.py" : "folder_name"}
                className="w-full bg-transparent border-none outline-none text-white text-xs font-mono p-0 focus:ring-0"
              />
            </div>
          )}

          {workspaceFiles.map((item) => renderTreeItem(item))}
        </div>
      </div>

      {/* ── SPLITTER 1: Explorer / Editor Resize Handle ── */}
      <div
        onPointerDown={handleStartResizeExplorer}
        onDoubleClick={() => setExplorerWidth(240)}
        title="Drag to resize Explorer (Double-click to reset)"
        className="w-1.5 hover:w-2 -ml-1 cursor-col-resize z-30 group relative flex items-center justify-center transition-all bg-transparent"
      >
        <div
          className={`w-[2px] h-full transition-colors ${
            isDraggingExplorer
              ? "bg-[#76B900] shadow-[0_0_10px_#76B900]"
              : "group-hover:bg-[#76B900]/70 group-hover:shadow-[0_0_8px_#76B900]/50"
          }`}
        />
      </div>

      {/* ── PANEL 2: Editor & Code Viewer Area (Center, Flex-1) ── */}
      <div className="flex-1 flex flex-col min-w-[280px] bg-[#0f0f0f] overflow-hidden relative">
        {/* Editor Tab Bar */}
        <div className="h-9 bg-[#141414] border-b border-[#202020] flex items-center justify-between px-2 overflow-x-auto shrink-0">
          <div className="flex items-center gap-1">
            {openTabs.length === 0 ? (
              <span className="text-[11px] font-mono text-neutral-500 px-2 select-none italic">
                No tabs open
              </span>
            ) : (
              openTabs.map((tab) => {
                const isActive = activeFile?.path === tab.path;
                return (
                  <div
                    key={tab.path}
                    onClick={() => {
                      setActiveFile(tab);
                      const stored = fileStoreRef.current.get(tab.path);
                      if (typeof window !== "undefined" && stored instanceof window.File) {
                        setActiveFileObject(stored as File);
                      } else if (stored && typeof stored.getFile === "function") {
                        stored.getFile().then((f: any) => setActiveFileObject(f as File)).catch(() => {});
                      } else {
                        setActiveFileObject(null);
                      }
                      if (!getDocumentType(tab.name)) {
                        setEditorContent(tab.content || "");
                      }
                    }}
                    className={`h-7 px-3 rounded-t text-xs font-mono flex items-center gap-2 cursor-pointer transition-colors border-t-2 ${
                      isActive
                        ? "bg-[#0f0f0f] border-[#76B900] text-white font-medium shadow-sm"
                        : "bg-[#181818] border-transparent text-neutral-400 hover:text-neutral-200"
                    }`}
                  >
                    {renderItemIcon(tab.name, "w-3 h-3")}
                    <span>{tab.name}</span>
                    <span
                      onClick={(e) => handleCloseTab(e, tab.path)}
                      className="hover:text-rose-400 ml-1 text-neutral-500 p-0.5 rounded transition-colors"
                    >
                      ×
                    </span>
                  </div>
                );
              })
            )}
          </div>

          {/* Right Toolbar: Terminal & Sanctum Agent Toggles */}
          <div className="flex items-center gap-2">
            <button
              onClick={() => setIsTerminalOpen((prev) => !prev)}
              title={isTerminalOpen ? "Hide Terminal" : "Show Terminal / Console"}
              className={`px-2 py-1 rounded text-xs font-mono flex items-center gap-1.5 transition-colors cursor-pointer border ${
                isTerminalOpen
                  ? "bg-[#1f2b14] border-[#76B900]/40 text-[#86e810]"
                  : "bg-[#181818] border-[#2e2e2e] text-neutral-400 hover:text-white"
              }`}
            >
              <Terminal className="w-3 h-3" />
              <span className="hidden md:inline">Terminal</span>
            </button>

            <button
              onClick={() => setIsChatOpen((prev) => !prev)}
              title={isChatOpen ? "Hide Sanctum Agent" : "Open Sanctum Agent"}
              className={`px-2.5 py-1 rounded text-xs font-mono flex items-center gap-1.5 transition-colors cursor-pointer border ${
                isChatOpen
                  ? "bg-[#1e2912] border-[#76B900]/40 text-[#86e810]"
                  : "bg-[#181818] border-[#2e2e2e] text-neutral-400 hover:text-white"
              }`}
            >
              <Sparkles className="w-3 h-3 text-[#76B900]" />
              <span className="hidden sm:inline">Sanctum Agent</span>
              {isChatOpen ? (
                <PanelRightClose className="w-3 h-3" />
              ) : (
                <PanelRightOpen className="w-3 h-3" />
              )}
            </button>
          </div>
        </div>


        {/* Editor Area: DocumentViewer for PDF/DOCX/PPTX/Spreadsheets/Images, Monaco Editor for Code, or Sovereign Empty State */}
        {activeFile && openTabs.length > 0 ? (
          <div className="flex-1 min-h-0 w-full relative">
            {getDocumentType(activeFile.name) ? (
              <DocumentViewer
                file={activeFile}
                fileObject={activeFileObject}
                onAskAgent={onAskAgentAboutFile}
              />
            ) : (
              <MonacoCodeEditor
                value={editorContent}
                language={activeFile.language || "python"}
                onChange={(val) => setEditorContent(val)}
              />
            )}
          </div>
        ) : (
          <div className="flex-1 min-h-0 w-full flex flex-col items-center justify-center p-8 bg-[#0b0b0b] text-center select-none relative overflow-hidden">
            {/* Ambient Radial Lighting */}
            <div className="absolute w-96 h-96 rounded-full bg-[#76B900]/5 blur-3xl pointer-events-none" />

            <div className="relative z-10 flex flex-col items-center max-w-sm">
              {/* Sanctum Watermark Emblem */}
              <SanctumLogo
                size={64}
                color="#76B900"
                className="mb-5 drop-shadow-[0_0_35px_rgba(118,185,0,0.35)]"
              />

              <h3 className="text-base font-bold tracking-widest text-white uppercase font-mono mb-1.5">
                SANCTUM
              </h3>
              <p className="text-xs text-neutral-500 mb-6 font-mono leading-relaxed">
                All editor tabs closed. Select a file from the explorer on the left or trigger an action below.
              </p>

              {/* Quick Actions */}
              <div className="flex flex-col gap-2 w-full text-xs font-mono">
                {files[0] && (
                  <button
                    onClick={() => handleSelectFile(files[0])}
                    className="flex items-center justify-between px-3.5 py-2.5 rounded-lg bg-[#141414] hover:bg-[#1a1a1a] border border-white/5 hover:border-[#76B900]/40 text-neutral-300 hover:text-white transition-all text-left group cursor-pointer shadow-sm"
                  >
                    <span className="flex items-center gap-2.5">
                      <FileCode className="w-4 h-4 text-[#76B900]" />
                      <span>Open {files[0].name}</span>
                    </span>
                    <span className="text-[10px] text-neutral-600 group-hover:text-neutral-400">
                      Open
                    </span>
                  </button>
                )}

                <button
                  onClick={() => setIsChatOpen(true)}
                  className="flex items-center justify-between px-3.5 py-2.5 rounded-lg bg-[#141414] hover:bg-[#1a1a1a] border border-white/5 hover:border-[#00f0ff]/40 text-neutral-300 hover:text-white transition-all text-left group cursor-pointer shadow-sm"
                >
                  <span className="flex items-center gap-2.5">
                    <Sparkles className="w-4 h-4 text-[#00f0ff]" />
                    <span>Open Sanctum Agent</span>
                  </span>
                  <span className="text-[10px] text-neutral-600 group-hover:text-neutral-400">
                    ⌘J
                  </span>
                </button>

                <button
                  onClick={() => setIsTerminalOpen(true)}
                  className="flex items-center justify-between px-3.5 py-2.5 rounded-lg bg-[#141414] hover:bg-[#1a1a1a] border border-white/5 hover:border-white/20 text-neutral-300 hover:text-white transition-all text-left group cursor-pointer shadow-sm"
                >
                  <span className="flex items-center gap-2.5">
                    <Terminal className="w-4 h-4 text-neutral-400" />
                    <span>Toggle Terminal</span>
                  </span>
                  <span className="text-[10px] text-neutral-600 group-hover:text-neutral-400">
                    ⌘`
                  </span>
                </button>
              </div>
            </div>
          </div>
        )}


        {/* ── Resizable Bottom Terminal / Console Drawer ── */}
        {isTerminalOpen && (
          <div className="flex flex-col shrink-0">
            {/* Splitter between Code Editor and Terminal */}
            <div
              onPointerDown={handleStartResizeTerminal}
              onDoubleClick={() => setTerminalHeight(160)}
              title="Drag to resize Terminal (Double-click to reset)"
              className="h-1.5 -mt-1 cursor-row-resize z-20 group relative flex items-center justify-center bg-transparent"
            >
              <div
                className={`h-[2px] w-full transition-colors ${
                  isDraggingTerminal
                    ? "bg-[#76B900] shadow-[0_0_10px_#76B900]"
                    : "group-hover:bg-[#76B900]/70 group-hover:shadow-[0_0_8px_#76B900]/50"
                }`}
              />
            </div>

            <div
              style={{ height: `${terminalHeight}px` }}
              className="border-t border-[#222] overflow-hidden"
            >
              <InteractiveTerminal onClose={() => setIsTerminalOpen(false)} />
            </div>
          </div>
        )}

        {/* Editor Status Bar */}
        <div className="h-6 bg-[#0d0d0d] border-t border-[#1e1e1e] px-3 flex items-center justify-between text-[10px] font-mono text-neutral-500 shrink-0">
          <div className="flex items-center gap-3">
            <span className="text-[#76B900] flex items-center gap-1">
              <span className="w-1.5 h-1.5 rounded-full bg-[#76B900]" />
              Host Storage Synchronized
            </span>
            <span>UTF-8</span>
          </div>
          <div className="flex items-center gap-3">
            <span>Ln 1, Col 1</span>
            <span>Spaces: 4</span>
            <span className="capitalize">
              {getDocumentType(activeFile?.name || "")
                ? `${getDocumentType(activeFile?.name || "")?.toUpperCase()} Document`
                : activeFile?.language || "Python"}
            </span>
          </div>
        </div>
      </div>

      {/* ── SPLITTER 2: Editor / Chat Window Resize Handle ── */}
      {isChatOpen && (
        <div
          onPointerDown={handleStartResizeChat}
          onDoubleClick={() => setChatWidth(420)}
          title="Drag to resize Chat Window (Double-click to reset)"
          className="w-1.5 hover:w-2 -mr-1 cursor-col-resize z-30 group relative flex items-center justify-center transition-all bg-transparent"
        >
          <div
            className={`w-[2px] h-full transition-colors ${
              isDraggingChat
                ? "bg-[#00f0ff] shadow-[0_0_10px_#00f0ff]"
                : "group-hover:bg-[#00f0ff]/70 group-hover:shadow-[0_0_8px_#00f0ff]/50"
            }`}
          />
        </div>
      )}

      {/* ── PANEL 3: Agent Chatting Window (Right, Resizable) ── */}
      <AnimatePresence>
        {isChatOpen && (
          <motion.div
            initial={{ width: 0, opacity: 0 }}
            animate={{ width: chatWidth, opacity: 1 }}
            exit={{ width: 0, opacity: 0 }}
            transition={{
              duration: isDraggingChat ? 0 : 0.2,
              ease: "easeInOut",
            }}
            style={{ width: `${chatWidth}px` }}
            className="h-full shrink-0 overflow-hidden flex flex-col"
          >
            <div style={{ width: `${chatWidth}px` }} className="h-full flex flex-col">
              <AgentChatPanel
                activeFile={activeFile?.name}
                availableFiles={availableFlatFiles}
                onClose={() => setIsChatOpen(false)}
              />
            </div>
          </motion.div>
        )}
      </AnimatePresence>



      {/* Native Directory Input (VS Code Style) - Not display:none so browser does not block native click */}
      <input
        id="sanctum-native-folder-input"
        type="file"
        ref={folderInputRef}
        onChange={handleNativeFolderSelected}
        className="fixed -top-[9999px] -left-[9999px] w-px h-px opacity-0 pointer-events-none"
        tabIndex={-1}
        aria-hidden="true"
        {...({ webkitdirectory: "", directory: "", multiple: true } as any)}
      />
    </div>
  );
};
