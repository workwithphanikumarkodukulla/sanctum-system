"use client";

import React, { useState, useEffect, useRef, useCallback } from "react";
import {
  FileText,
  Presentation,
  Table,
  Image as ImageIcon,
  Download,
  ExternalLink,
  Sparkles,
  ChevronLeft,
  ChevronRight,
  ZoomIn,
  ZoomOut,
  RotateCw,
  Search,
  BookOpen,
  Layers,
  FileCode,
  Check,
  AlertCircle,
  Maximize2,
  Minimize2,
  RefreshCw,
  Lock,
  Key,
  ShieldCheck,
} from "lucide-react";
import { FileItem } from "@/types";

export function getDocumentType(
  filename: string
): "pdf" | "docx" | "pptx" | "spreadsheet" | "image" | null {
  const ext = filename.split(".").pop()?.toLowerCase() || "";
  if (ext === "pdf") return "pdf";
  if (["docx", "doc"].includes(ext)) return "docx";
  if (["pptx", "ppt"].includes(ext)) return "pptx";
  if (["xlsx", "xls", "csv"].includes(ext)) return "spreadsheet";
  if (["png", "jpg", "jpeg", "webp", "svg", "gif", "ico", "bmp"].includes(ext))
    return "image";
  return null;
}

interface DocumentViewerProps {
  file: FileItem;
  fileObject?: File | null;
  onAskAgent?: (fileName: string, prompt: string) => void;
}

export const DocumentViewer: React.FC<DocumentViewerProps> = ({
  file,
  fileObject,
  onAskAgent,
}) => {
  const docType = getDocumentType(file.name);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [docData, setDocData] = useState<any>(null);

  // PDF state
  const [pdfMode, setPdfMode] = useState<"embed" | "pages">("embed");
  const [currentPage, setCurrentPage] = useState(1);
  const [pdfZoom, setPdfZoom] = useState(100);

  // PPTX state
  const [currentSlide, setCurrentSlide] = useState(0);
  const [isFullscreen, setIsFullscreen] = useState(false);

  // DOCX state
  const [docxMode, setDocxMode] = useState<"styled" | "markdown">("styled");
  const [showToc, setShowToc] = useState(true);

  // Spreadsheet state
  const [activeSheet, setActiveSheet] = useState<string>("");
  const [tableSearch, setTableSearch] = useState("");

  // Image state
  const [imageZoom, setImageZoom] = useState(100);
  const [imageRotate, setImageRotate] = useState(0);

  // Local object URL for browser File handles
  const [localBlobUrl, setLocalBlobUrl] = useState<string | null>(null);

  // Create local blob URL if File object provided
  useEffect(() => {
    if (fileObject) {
      const url = URL.createObjectURL(fileObject);
      setLocalBlobUrl(url);
      return () => {
        URL.revokeObjectURL(url);
      };
    } else {
      setLocalBlobUrl(null);
    }
  }, [fileObject, file.path]);

  // Load document data
  const loadDocumentData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      if (fileObject) {
        // Upload & parse local file via POST
        const formData = new FormData();
        formData.append("file", fileObject, file.name);
        const res = await fetch("/api/backend/workspace/document-data", {
          method: "POST",
          body: formData,
        });
        if (!res.ok) {
          throw new Error(`Parser returned HTTP ${res.status}`);
        }
        const data = await res.json();
        setDocData(data);
        if (data.type === "spreadsheet" && data.sheet_names?.length > 0) {
          setActiveSheet(data.sheet_names[0]);
        }
      } else {
        // Fetch from backend workspace via GET
        const res = await fetch(
          `/api/backend/workspace/document-data?path=${encodeURIComponent(
            file.path
          )}`
        );
        if (!res.ok) {
          throw new Error(`Failed to load document data (HTTP ${res.status})`);
        }
        const data = await res.json();
        setDocData(data);
        if (data.type === "spreadsheet" && data.sheet_names?.length > 0) {
          setActiveSheet(data.sheet_names[0]);
        }
      }
      setCurrentSlide(0);
      setCurrentPage(1);
    } catch (err: any) {
      console.warn("Document parser error:", err);
      setError(err?.message || "Failed to parse document");
    } finally {
      setLoading(false);
    }
  }, [file.path, file.name, fileObject]);

  useEffect(() => {
    loadDocumentData();
  }, [loadDocumentData]);

  // Keyboard navigation for presentation slides
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (docType === "pptx" && docData?.slides?.length > 0) {
        if (e.key === "ArrowRight" || e.key === "PageDown" || e.key === " ") {
          e.preventDefault();
          setCurrentSlide((prev) =>
            Math.min(docData.slides.length - 1, prev + 1)
          );
        } else if (e.key === "ArrowLeft" || e.key === "PageUp") {
          e.preventDefault();
          setCurrentSlide((prev) => Math.max(0, prev - 1));
        }
      } else if (docType === "pdf" && pdfMode === "pages" && docData?.total_pages > 0) {
        if (e.key === "ArrowRight" || e.key === "PageDown") {
          e.preventDefault();
          setCurrentPage((prev) => Math.min(docData.total_pages, prev + 1));
        } else if (e.key === "ArrowLeft" || e.key === "PageUp") {
          e.preventDefault();
          setCurrentPage((prev) => Math.max(1, prev - 1));
        }
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [docType, docData, pdfMode]);

  // Direct preview URL
  const previewUrl =
    localBlobUrl ||
    `/api/backend/workspace/preview?path=${encodeURIComponent(file.path)}`;

  const downloadUrl =
    localBlobUrl ||
    `/api/backend/workspace/download?path=${encodeURIComponent(file.path)}`;

  // Handle native app opening
  const handleOpenNative = async () => {
    try {
      await fetch(
        `/api/backend/workspace/open-native?path=${encodeURIComponent(file.path)}`,
        { method: "POST" }
      );
    } catch (e) {
      console.warn("Could not trigger open-native:", e);
    }
  };

  // Trigger agent assistance for this document
  const handleAskAgent = () => {
    if (!onAskAgent) return;
    let prompt = `Please review and analyze the document "${file.name}". `;
    if (docType === "pptx") {
      prompt += `It is a presentation with ${docData?.total_slides || 0} slides. Summarize key takeaways, critique slide contents, and suggest improvements.`;
    } else if (docType === "pdf") {
      prompt += `It is a PDF document with ${docData?.total_pages || 0} pages. Extract the core findings and provide an executive summary.`;
    } else if (docType === "docx") {
      prompt += `It is a Word document titled "${docData?.title || file.name}". Review the technical details, structure, and verify key points.`;
    } else if (docType === "spreadsheet") {
      prompt += `It is a spreadsheet with data. Analyze trends, anomalies, and summarize the key figures.`;
    } else if (docType === "image") {
      prompt += `Inspect this visual diagram/image and explain its architecture, components, and workflow.`;
    }
    onAskAgent(file.name, prompt);
  };

  // Render document badge
  const renderBadge = () => {
    switch (docType) {
      case "pdf":
        return (
          <span className="flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-semibold bg-rose-500/10 text-rose-400 border border-rose-500/20">
            <FileText className="w-3 h-3" />
            PDF DOCUMENT
          </span>
        );
      case "pptx":
        return (
          <span className="flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-semibold bg-amber-500/10 text-amber-400 border border-amber-500/20">
            <Presentation className="w-3 h-3" />
            PRESENTATION
          </span>
        );
      case "docx":
        return (
          <span className="flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-semibold bg-blue-500/10 text-blue-400 border border-blue-500/20">
            <BookOpen className="w-3 h-3" />
            WORD DOCUMENT
          </span>
        );
      case "spreadsheet":
        return (
          <span className="flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
            <Table className="w-3 h-3" />
            SPREADSHEET
          </span>
        );
      case "image":
        return (
          <span className="flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-semibold bg-purple-500/10 text-purple-400 border border-purple-500/20">
            <ImageIcon className="w-3 h-3" />
            IMAGE PREVIEW
          </span>
        );
      default:
        return null;
    }
  };

  return (
    <div className="flex flex-col h-full w-full bg-[#0d0d0d] text-neutral-200 select-none overflow-hidden">
      {/* Document Viewer Header Toolbar */}
      <div className="flex items-center justify-between px-4 py-2 bg-[#141414] border-b border-[#242424] shrink-0 gap-3">
        {/* Left: Badge & Name */}
        <div className="flex items-center gap-2.5 min-w-0">
          {renderBadge()}
          <span
            className="text-xs font-medium text-white truncate max-w-[280px]"
            title={file.name}
          >
            {file.name}
          </span>
          {docData?.stats?.words && (
            <span className="text-[11px] text-neutral-400 hidden sm:inline-block">
              · {docData.stats.words} words
            </span>
          )}
          {docData?.total_slides && (
            <span className="text-[11px] text-neutral-400 hidden sm:inline-block">
              · {docData.total_slides} slides
            </span>
          )}
          {docData?.total_pages && (
            <span className="text-[11px] text-neutral-400 hidden sm:inline-block">
              · {docData.total_pages} pages
            </span>
          )}
        </div>

        {/* Center: Controls specific to Document Type */}
        <div className="flex items-center gap-1.5">
          {docType === "pdf" && (
            <div className="flex items-center bg-[#1c1c1c] border border-[#2b2b2b] rounded p-0.5 text-xs">
              <button
                onClick={() => setPdfMode("embed")}
                className={`px-2 py-1 rounded transition-colors ${pdfMode === "embed"
                    ? "bg-[#282828] text-white font-medium"
                    : "text-neutral-400 hover:text-neutral-200"
                  }`}
              >
                Native View
              </button>
              <button
                onClick={() => setPdfMode("pages")}
                className={`px-2 py-1 rounded transition-colors ${pdfMode === "pages"
                    ? "bg-[#282828] text-white font-medium"
                    : "text-neutral-400 hover:text-neutral-200"
                  }`}
              >
                Page Reader
              </button>
            </div>
          )}

          {docType === "docx" && (
            <div className="flex items-center bg-[#1c1c1c] border border-[#2b2b2b] rounded p-0.5 text-xs">
              <button
                onClick={() => setDocxMode("styled")}
                className={`px-2 py-1 rounded transition-colors ${docxMode === "styled"
                    ? "bg-[#282828] text-white font-medium"
                    : "text-neutral-400 hover:text-neutral-200"
                  }`}
              >
                Document
              </button>
              <button
                onClick={() => setDocxMode("markdown")}
                className={`px-2 py-1 rounded transition-colors ${docxMode === "markdown"
                    ? "bg-[#282828] text-white font-medium"
                    : "text-neutral-400 hover:text-neutral-200"
                  }`}
              >
                Markdown
              </button>
            </div>
          )}

          {docType === "pptx" && docData?.slides && (
            <div className="flex items-center gap-1 bg-[#1c1c1c] border border-[#2b2b2b] rounded px-2 py-1 text-xs">
              <button
                onClick={() => setCurrentSlide((p) => Math.max(0, p - 1))}
                disabled={currentSlide === 0}
                className="p-0.5 hover:text-white disabled:opacity-30"
                title="Previous slide (Left Arrow)"
              >
                <ChevronLeft className="w-3.5 h-3.5" />
              </button>
              <span className="font-mono text-[11px] text-neutral-300 px-1">
                {currentSlide + 1} / {docData.slides.length}
              </span>
              <button
                onClick={() =>
                  setCurrentSlide((p) =>
                    Math.min(docData.slides.length - 1, p + 1)
                  )
                }
                disabled={currentSlide >= docData.slides.length - 1}
                className="p-0.5 hover:text-white disabled:opacity-30"
                title="Next slide (Right Arrow)"
              >
                <ChevronRight className="w-3.5 h-3.5" />
              </button>
            </div>
          )}

          {docType === "image" && (
            <div className="flex items-center gap-1 bg-[#1c1c1c] border border-[#2b2b2b] rounded px-1.5 py-1 text-xs">
              <button
                onClick={() => setImageZoom((z) => Math.max(25, z - 25))}
                className="p-0.5 hover:text-white"
                title="Zoom Out"
              >
                <ZoomOut className="w-3.5 h-3.5" />
              </button>
              <span className="text-[11px] font-mono text-neutral-300 w-10 text-center">
                {imageZoom}%
              </span>
              <button
                onClick={() => setImageZoom((z) => Math.min(400, z + 25))}
                className="p-0.5 hover:text-white"
                title="Zoom In"
              >
                <ZoomIn className="w-3.5 h-3.5" />
              </button>
              <button
                onClick={() => setImageRotate((r) => (r + 90) % 360)}
                className="p-0.5 hover:text-white ml-1"
                title="Rotate Clockwise"
              >
                <RotateCw className="w-3.5 h-3.5" />
              </button>
            </div>
          )}
        </div>

        {/* Right: Actions */}
        <div className="flex items-center gap-2">
          {onAskAgent && (
            <button
              onClick={handleAskAgent}
              className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-[#1f2e14] hover:bg-[#283d19] text-[#9ae018] border border-[#76B900]/40 text-xs font-medium transition-all shadow-[0_0_12px_rgba(118,185,0,0.15)]"
              title="Ask Sanctum Agent to analyze or summarize this document"
            >
              <Sparkles className="w-3.5 h-3.5 text-[#76B900]" />
              <span className="hidden sm:inline">Ask Agent</span>
            </button>
          )}

          {!fileObject && (
            <button
              onClick={handleOpenNative}
              className="flex items-center gap-1 px-2 py-1 rounded bg-[#1f1f1f] hover:bg-[#2a2a2a] text-neutral-300 hover:text-white border border-[#2b2b2b] text-xs transition-colors"
              title="Open in native OS app (Word / Pages / Preview)"
            >
              <ExternalLink className="w-3.5 h-3.5" />
              <span className="hidden md:inline">Native</span>
            </button>
          )}

          <a
            href={downloadUrl}
            download={file.name}
            className="flex items-center gap-1 px-2 py-1 rounded bg-[#1f1f1f] hover:bg-[#2a2a2a] text-neutral-300 hover:text-white border border-[#2b2b2b] text-xs transition-colors"
            title="Download file"
          >
            <Download className="w-3.5 h-3.5" />
          </a>
        </div>
      </div>

      {/* Main Body Area */}
      <div className="flex-1 min-h-0 w-full relative overflow-hidden bg-[#0c0c0c]">
        {loading && !docData && (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 bg-[#0d0d0d] z-20">
            <RefreshCw className="w-6 h-6 text-[#76B900] animate-spin" />
            <p className="text-xs text-neutral-400">
              Parsing document structure sovereignly...
            </p>
          </div>
        )}

        {/* 1. PDF VIEWER */}
        {docType === "pdf" && (
          <div className="h-full w-full flex flex-col overflow-hidden">
            {pdfMode === "embed" ? (
              <div className="h-full w-full bg-[#181818]">
                <iframe
                  src={`${previewUrl}#toolbar=1&navpanes=1`}
                  className="w-full h-full border-0"
                  title={file.name}
                />
              </div>
            ) : (
              /* High-res Sovereign Page Reader */
              <div className="flex h-full w-full overflow-hidden">
                {/* Pages sidebar */}
                {docData?.pages && (
                  <div className="w-48 bg-[#121212] border-r border-[#222] overflow-y-auto p-2 flex flex-col gap-2 shrink-0">
                    <div className="text-[10px] font-semibold text-neutral-400 uppercase tracking-wider px-1">
                      Pages ({docData.total_pages})
                    </div>
                    {docData.pages.map((p: any) => (
                      <button
                        key={p.page}
                        onClick={() => setCurrentPage(p.page)}
                        className={`flex items-center justify-between p-2 rounded text-xs transition-all ${currentPage === p.page
                            ? "bg-[#1f2b14] text-[#9ae018] font-medium border border-[#76B900]/40"
                            : "text-neutral-400 hover:bg-[#1a1a1a] hover:text-neutral-200"
                          }`}
                      >
                        <span>Page {p.page}</span>
                        <span className="text-[10px] font-mono text-neutral-500 truncate max-w-[70px]">
                          {p.text?.slice(0, 15) || "..."}
                        </span>
                      </button>
                    ))}
                  </div>
                )}

                {/* Main page image reader */}
                <div className="flex-1 h-full overflow-auto flex flex-col items-center p-6 bg-[#0a0a0a]">
                  <div className="flex items-center gap-3 mb-4 bg-[#141414] border border-[#262626] rounded-full px-4 py-1.5 shadow-lg text-xs">
                    <button
                      onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                      disabled={currentPage === 1}
                      className="p-1 hover:text-white disabled:opacity-30"
                    >
                      <ChevronLeft className="w-4 h-4" />
                    </button>
                    <span className="font-mono text-neutral-300">
                      Page {currentPage} of {docData?.total_pages || 1}
                    </span>
                    <button
                      onClick={() =>
                        setCurrentPage((p) =>
                          Math.min(docData?.total_pages || 1, p + 1)
                        )
                      }
                      disabled={currentPage >= (docData?.total_pages || 1)}
                      className="p-1 hover:text-white disabled:opacity-30"
                    >
                      <ChevronRight className="w-4 h-4" />
                    </button>
                    <div className="h-4 w-px bg-neutral-700 mx-1" />
                    <button
                      onClick={() => setPdfZoom((z) => Math.max(50, z - 25))}
                      className="p-1 hover:text-white"
                      title="Zoom Out"
                    >
                      <ZoomOut className="w-3.5 h-3.5" />
                    </button>
                    <span className="font-mono text-[11px] text-neutral-400 w-10 text-center">
                      {pdfZoom}%
                    </span>
                    <button
                      onClick={() => setPdfZoom((z) => Math.min(250, z + 25))}
                      className="p-1 hover:text-white"
                      title="Zoom In"
                    >
                      <ZoomIn className="w-3.5 h-3.5" />
                    </button>
                  </div>

                  <div
                    style={{ width: `${pdfZoom}%`, maxWidth: "1200px" }}
                    className="shadow-2xl rounded border border-[#2a2a2a] bg-white overflow-hidden transition-all duration-150"
                  >
                    {/* Render page as image from backend */}
                    <img
                      src={`/api/backend/workspace/pdf-page-image?path=${encodeURIComponent(
                        file.path
                      )}&page=${currentPage}&dpi=150`}
                      alt={`Page ${currentPage}`}
                      className="w-full h-auto block"
                      onError={(e) => {
                        // Fallback to iframe if page image rendering fails
                        (e.target as HTMLElement).style.display = "none";
                      }}
                    />
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {/* 2. POWERPOINT PRESENTATION VIEWER */}
        {docType === "pptx" && (
          <div className="flex h-full w-full overflow-hidden bg-[#0a0a0a]">
            {/* Sidebar Slide Thumbnails Strip */}
            <div className="w-56 bg-[#111111] border-r border-[#222] overflow-y-auto p-2.5 flex flex-col gap-2 shrink-0">
              <div className="flex items-center justify-between px-1 mb-1">
                <span className="text-[10px] font-semibold text-neutral-400 uppercase tracking-wider">
                  Slides ({docData?.slides?.length || 0})
                </span>
              </div>
              {docData?.slides?.map((slide: any, idx: number) => (
                <button
                  key={idx}
                  onClick={() => setCurrentSlide(idx)}
                  className={`flex flex-col p-2 rounded-lg text-left transition-all border ${currentSlide === idx
                      ? "bg-[#1d2913] border-[#76B900]/50 shadow-[0_0_12px_rgba(118,185,0,0.15)]"
                      : "bg-[#161616] border-[#242424] hover:border-[#383838]"
                    }`}
                >
                  <div className="flex items-center justify-between mb-1">
                    <span
                      className={`text-[10px] font-mono font-bold ${currentSlide === idx ? "text-[#9ae018]" : "text-neutral-500"
                        }`}
                    >
                      #{slide.slide_number}
                    </span>
                    {slide.images?.length > 0 && (
                      <span className="text-[9px] px-1 py-0.2 rounded bg-neutral-800 text-neutral-400">
                        {slide.images.length} img
                      </span>
                    )}
                  </div>
                  <span className="text-[11px] font-medium text-neutral-200 line-clamp-1">
                    {slide.title || `Slide ${slide.slide_number}`}
                  </span>
                  <span className="text-[10px] text-neutral-500 line-clamp-2 mt-0.5">
                    {slide.bullets?.[0] || "(Visual slide content)"}
                  </span>
                </button>
              ))}
            </div>

            {/* Main Slide Stage */}
            {docData?.slides && docData.slides[currentSlide] ? (
              <div className="flex-1 h-full overflow-y-auto flex flex-col items-center justify-start p-6 bg-[#080808]">
                {/* Presentation Stage Canvas (16:9 Aspect Ratio) */}
                <div className="w-full max-w-4xl bg-gradient-to-b from-[#161616] to-[#121212] border border-[#2b2b2b] rounded-xl shadow-2xl p-8 flex flex-col gap-6 relative min-h-[500px]">
                  {/* Slide Top Bar */}
                  <div className="flex items-center justify-between border-b border-[#252525] pb-4">
                    <div className="flex items-center gap-2">
                      <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-[#76B900]/10 text-[#9ae018] border border-[#76B900]/30">
                        SLIDE {docData.slides[currentSlide].slide_number} OF{" "}
                        {docData.slides.length}
                      </span>
                    </div>
                    <span className="text-xs text-neutral-400 font-mono">
                      {file.name}
                    </span>
                  </div>

                  {/* Slide Title */}
                  <h2 className="text-2xl font-bold text-white tracking-tight">
                    {docData.slides[currentSlide].title ||
                      `Slide ${docData.slides[currentSlide].slide_number}`}
                  </h2>

                  {/* Slide Images (if any) */}
                  {docData.slides[currentSlide].images?.length > 0 && (
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4 w-full my-2">
                      {docData.slides[currentSlide].images.map(
                        (imgSrc: string, imgIdx: number) => (
                          <div
                            key={imgIdx}
                            className="bg-[#0e0e0e] border border-[#262626] rounded-lg overflow-hidden flex items-center justify-center p-2 shadow-inner max-h-72"
                          >
                            <img
                              src={imgSrc}
                              alt={`Slide visual ${imgIdx + 1}`}
                              className="max-h-64 max-w-full object-contain rounded"
                            />
                          </div>
                        )
                      )}
                    </div>
                  )}

                  {/* Slide Bullets / Text Content */}
                  {docData.slides[currentSlide].bullets?.length > 0 && (
                    <div className="flex flex-col gap-2.5">
                      {docData.slides[currentSlide].bullets.map(
                        (bullet: string, bIdx: number) => (
                          <div
                            key={bIdx}
                            className="flex items-start gap-3 text-neutral-200 text-sm leading-relaxed bg-[#191919]/60 p-2.5 rounded-lg border border-[#242424]"
                          >
                            <span className="w-1.5 h-1.5 rounded-full bg-[#76B900] mt-2 shrink-0 shadow-[0_0_6px_#76B900]" />
                            <span className="flex-1">{bullet}</span>
                          </div>
                        )
                      )}
                    </div>
                  )}

                  {/* Slide Tables */}
                  {docData.slides[currentSlide].tables?.length > 0 && (
                    <div className="flex flex-col gap-4 my-2">
                      {docData.slides[currentSlide].tables.map(
                        (tbl: string[][], tIdx: number) => (
                          <div
                            key={tIdx}
                            className="overflow-x-auto border border-[#2b2b2b] rounded-lg"
                          >
                            <table className="w-full text-xs text-left border-collapse">
                              <tbody>
                                {tbl.map((row: string[], rIdx: number) => (
                                  <tr
                                    key={rIdx}
                                    className={`border-b border-[#252525] ${rIdx === 0
                                        ? "bg-[#1f1f1f] text-white font-semibold"
                                        : "bg-[#141414] text-neutral-300"
                                      }`}
                                  >
                                    {row.map((cell: string, cIdx: number) => (
                                      <td
                                        key={cIdx}
                                        className="py-2 px-3 border-r border-[#252525] last:border-r-0"
                                      >
                                        {cell}
                                      </td>
                                    ))}
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                        )
                      )}
                    </div>
                  )}

                  {/* Speaker Notes */}
                  {docData.slides[currentSlide].notes && (
                    <div className="mt-4 p-3 bg-[#111] border border-[#222] rounded-lg text-xs text-neutral-400">
                      <span className="font-semibold text-neutral-300 block mb-1">
                        Speaker Notes:
                      </span>
                      {docData.slides[currentSlide].notes}
                    </div>
                  )}

                  {/* Slide Navigation Footer Bar */}
                  <div className="flex items-center justify-between pt-4 mt-auto border-t border-[#252525]">
                    <button
                      onClick={() => setCurrentSlide((p) => Math.max(0, p - 1))}
                      disabled={currentSlide === 0}
                      className="flex items-center gap-1.5 px-3 py-1.5 rounded bg-[#1c1c1c] hover:bg-[#252525] text-xs text-neutral-300 hover:text-white disabled:opacity-30 transition-colors"
                    >
                      <ChevronLeft className="w-4 h-4" />
                      Previous Slide
                    </button>
                    <span className="text-[11px] font-mono text-neutral-500">
                      Use Left / Right arrow keys to navigate
                    </span>
                    <button
                      onClick={() =>
                        setCurrentSlide((p) =>
                          Math.min(docData.slides.length - 1, p + 1)
                        )
                      }
                      disabled={currentSlide >= docData.slides.length - 1}
                      className="flex items-center gap-1.5 px-3 py-1.5 rounded bg-[#1c1c1c] hover:bg-[#252525] text-xs text-neutral-300 hover:text-white disabled:opacity-30 transition-colors"
                    >
                      Next Slide
                      <ChevronRight className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              </div>
            ) : (
              <div className="flex-1 flex items-center justify-center text-neutral-500 text-xs">
                No slide data available.
              </div>
            )}
          </div>
        )}

        {/* 3. WORD DOCUMENT VIEWER */}
        {docType === "docx" && (
          <div className="flex h-full w-full overflow-hidden bg-[#0c0c0c]">
            {/* Table of Contents sidebar */}
            {showToc && docData?.sections && (
              <div className="w-64 bg-[#111111] border-r border-[#222] overflow-y-auto p-3 flex flex-col gap-2 shrink-0">
                <div className="flex items-center justify-between pb-1 border-b border-[#222]">
                  <span className="text-[10px] font-semibold text-neutral-400 uppercase tracking-wider">
                    Document Outline
                  </span>
                  <span className="text-[10px] font-mono text-neutral-500">
                    {docData.sections.length} items
                  </span>
                </div>
                {docData.sections
                  .filter((s: any) =>
                    ["title", "heading_1", "heading_2"].includes(s.type)
                  )
                  .map((s: any, sIdx: number) => (
                    <a
                      key={sIdx}
                      href={`#sec-${sIdx}`}
                      className={`text-xs block py-1 px-1.5 rounded hover:bg-[#1a1a1a] transition-colors truncate ${s.type === "title"
                          ? "text-white font-bold"
                          : s.type === "heading_1"
                            ? "text-neutral-300 font-semibold pl-2 border-l border-[#76B900]"
                            : "text-neutral-400 pl-4"
                        }`}
                    >
                      {s.text}
                    </a>
                  ))}
              </div>
            )}

            {/* Document Canvas */}
            <div className="flex-1 h-full overflow-y-auto p-6 md:p-10 flex flex-col items-center">
              {docxMode === "styled" ? (
                <div className="w-full max-w-3xl bg-[#141414] border border-[#262626] rounded-xl shadow-2xl p-8 md:p-12 flex flex-col gap-5 text-neutral-200">
                  {/* Document Header */}
                  <div className="border-b border-[#292929] pb-6 mb-2">
                    <div className="flex items-center gap-2 mb-3">
                      <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-blue-500/10 text-blue-400 border border-blue-500/20">
                        MICROSOFT WORD (.DOCX)
                      </span>
                      {docData?.stats?.words && (
                        <span className="text-xs text-neutral-400 font-mono">
                          {docData.stats.words} Words ·{" "}
                          {docData.stats.paragraphs} Paragraphs ·{" "}
                          {docData.stats.tables} Tables
                        </span>
                      )}
                    </div>
                    <h1 className="text-2xl md:text-3xl font-bold text-white tracking-tight">
                      {docData?.title || file.name}
                    </h1>
                  </div>

                  {/* Document Sections */}
                  {docData?.sections?.map((sec: any, idx: number) => {
                    if (sec.type === "title") {
                      return (
                        <h1
                          key={idx}
                          id={`sec-${idx}`}
                          className="text-2xl font-bold text-white tracking-tight mt-2 mb-1"
                        >
                          {sec.text}
                        </h1>
                      );
                    }
                    if (sec.type === "heading_1") {
                      return (
                        <div
                          key={idx}
                          id={`sec-${idx}`}
                          className="pt-4 pb-1 border-b border-[#292929]"
                        >
                          <h2 className="text-lg font-bold text-[#9ae018] tracking-tight">
                            {sec.text}
                          </h2>
                        </div>
                      );
                    }
                    if (sec.type === "heading_2") {
                      return (
                        <h3
                          key={idx}
                          id={`sec-${idx}`}
                          className="text-base font-semibold text-neutral-100 mt-3"
                        >
                          {sec.text}
                        </h3>
                      );
                    }
                    if (sec.type === "heading_3") {
                      return (
                        <h4
                          key={idx}
                          id={`sec-${idx}`}
                          className="text-sm font-semibold text-neutral-300 mt-2"
                        >
                          {sec.text}
                        </h4>
                      );
                    }
                    if (sec.type === "list_item") {
                      return (
                        <div
                          key={idx}
                          className="flex items-start gap-2.5 text-sm text-neutral-300 pl-2"
                        >
                          <span className="w-1.5 h-1.5 rounded-full bg-[#76B900] mt-2 shrink-0" />
                          <span>{sec.text}</span>
                        </div>
                      );
                    }
                    if (sec.type === "table") {
                      return (
                        <div
                          key={idx}
                          className="my-3 overflow-x-auto border border-[#2c2c2c] rounded-lg shadow-sm"
                        >
                          <table className="w-full text-xs text-left border-collapse">
                            <tbody>
                              {sec.rows.map((r: string[], rIdx: number) => (
                                <tr
                                  key={rIdx}
                                  className={`border-b border-[#262626] ${rIdx === 0
                                      ? "bg-[#1f1f1f] text-white font-semibold"
                                      : "bg-[#141414] text-neutral-300 hover:bg-[#1a1a1a]"
                                    }`}
                                >
                                  {r.map((cell: string, cIdx: number) => (
                                    <td
                                      key={cIdx}
                                      className="py-2 px-3 border-r border-[#262626] last:border-r-0"
                                    >
                                      {cell}
                                    </td>
                                  ))}
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      );
                    }
                    // Regular paragraph
                    return (
                      <p
                        key={idx}
                        className="text-sm leading-relaxed text-neutral-300"
                      >
                        {sec.runs?.length > 0
                          ? sec.runs.map((r: any, rIdx: number) => (
                            <span
                              key={rIdx}
                              className={`${r.bold ? "font-bold text-white" : ""
                                } ${r.italic ? "italic" : ""} ${r.underline ? "underline" : ""
                                }`}
                            >
                              {r.text}
                            </span>
                          ))
                          : sec.text}
                      </p>
                    );
                  })}
                </div>
              ) : (
                /* Raw Markdown Representation */
                <div className="w-full max-w-3xl bg-[#141414] border border-[#262626] rounded-xl p-6 font-mono text-xs text-neutral-300 whitespace-pre-wrap">
                  {docData?.markdown || docData?.content || "No text available."}
                </div>
              )}
            </div>
          </div>
        )}

        {/* 4. SPREADSHEET VIEWER */}
        {docType === "spreadsheet" && (
          <div className="flex flex-col h-full w-full overflow-hidden bg-[#0c0c0c]">
            {/* Sheet Tabs and Search Header */}
            <div className="flex items-center justify-between px-4 py-2 bg-[#141414] border-b border-[#242424] gap-3">
              <div className="flex items-center gap-1.5 overflow-x-auto">
                {docData?.sheet_names?.map((sname: string) => (
                  <button
                    key={sname}
                    onClick={() => setActiveSheet(sname)}
                    className={`px-3 py-1 rounded text-xs font-medium transition-colors ${activeSheet === sname
                        ? "bg-[#1f2b14] text-[#9ae018] border border-[#76B900]/40"
                        : "bg-[#1b1b1b] text-neutral-400 hover:text-white"
                      }`}
                  >
                    {sname}
                  </button>
                ))}
              </div>

              <div className="flex items-center gap-2">
                <div className="relative">
                  <Search className="w-3.5 h-3.5 text-neutral-500 absolute left-2.5 top-1/2 -translate-y-1/2" />
                  <input
                    type="text"
                    placeholder="Filter spreadsheet cells..."
                    value={tableSearch}
                    onChange={(e) => setTableSearch(e.target.value)}
                    className="bg-[#181818] border border-[#2b2b2b] rounded pl-8 pr-3 py-1 text-xs text-neutral-200 placeholder:text-neutral-500 focus:outline-none focus:border-[#76B900]/60 w-48 sm:w-64"
                  />
                </div>
                {docData?.total_rows && (
                  <span className="text-[11px] font-mono text-neutral-400">
                    {docData.total_rows} Rows
                  </span>
                )}
              </div>
            </div>

            {/* Spreadsheet Grid */}
            <div className="flex-1 overflow-auto p-4">
              {docData?.sheets && docData.sheets[activeSheet] ? (
                <div className="border border-[#262626] rounded-lg overflow-hidden inline-block min-w-full shadow-lg">
                  <table className="w-full text-xs text-left border-collapse font-mono">
                    <thead>
                      <tr className="bg-[#181818] border-b border-[#262626] sticky top-0 z-10">
                        <th className="py-2 px-3 text-neutral-500 text-center w-12 border-r border-[#262626]">
                          #
                        </th>
                        {docData.sheets[activeSheet].headers?.map(
                          (h: string, hIdx: number) => (
                            <th
                              key={hIdx}
                              className="py-2 px-3 font-semibold text-neutral-200 border-r border-[#262626] whitespace-nowrap bg-[#1c1c1c]"
                            >
                              {h || `Column ${hIdx + 1}`}
                            </th>
                          )
                        )}
                      </tr>
                    </thead>
                    <tbody>
                      {docData.sheets[activeSheet].rows
                        ?.filter((row: string[]) =>
                          tableSearch
                            ? row.some((c) =>
                              String(c)
                                .toLowerCase()
                                .includes(tableSearch.toLowerCase())
                            )
                            : true
                        )
                        .map((row: string[], rIdx: number) => (
                          <tr
                            key={rIdx}
                            className="border-b border-[#202020] hover:bg-[#161f10] transition-colors"
                          >
                            <td className="py-1.5 px-3 text-neutral-500 text-center border-r border-[#202020] bg-[#121212]">
                              {rIdx + 1}
                            </td>
                            {row.map((cell: string, cIdx: number) => (
                              <td
                                key={cIdx}
                                className="py-1.5 px-3 text-neutral-300 border-r border-[#202020] whitespace-nowrap max-w-xs truncate"
                                title={String(cell)}
                              >
                                {String(cell)}
                              </td>
                            ))}
                          </tr>
                        ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="flex items-center justify-center h-48 text-neutral-500 text-xs">
                  No spreadsheet data found.
                </div>
              )}
            </div>
          </div>
        )}

        {/* 5. IMAGE VIEWER */}
        {docType === "image" && (
          <div className="h-full w-full flex items-center justify-center p-6 bg-[#080808] overflow-auto">
            <div
              className="relative p-2 rounded-lg border border-[#252525] shadow-2xl transition-transform duration-150"
              style={{
                backgroundImage:
                  "linear-gradient(45deg, #121212 25%, transparent 25%), linear-gradient(-45deg, #121212 25%, transparent 25%), linear-gradient(45deg, transparent 75%, #121212 75%), linear-gradient(-45deg, transparent 75%, #121212 75%)",
                backgroundSize: "20px 20px",
                backgroundPosition: "0 0, 0 10px, 10px -10px, -10px 0px",
              }}
            >
              <img
                src={previewUrl}
                alt={file.name}
                style={{
                  transform: `scale(${imageZoom / 100}) rotate(${imageRotate}deg)`,
                  transition: "transform 0.15s ease-out",
                }}
                className="max-h-[70vh] max-w-[85vw] object-contain rounded"
              />
            </div>
          </div>
        )}

        {/* Error overlay */}
        {error && (
          <div className="absolute bottom-4 right-4 bg-[#231214] border border-rose-500/40 text-rose-300 px-3 py-2 rounded-lg text-xs flex items-center gap-2 shadow-xl z-30">
            <AlertCircle className="w-4 h-4 text-rose-400 shrink-0" />
            <span>{error}</span>
          </div>
        )}
      </div>
    </div>
  );
};
