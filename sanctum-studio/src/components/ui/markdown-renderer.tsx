"use client";

import React, { useMemo } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import rehypeRaw from "rehype-raw";

interface MarkdownRendererProps {
  content: string;
  className?: string;
}

/**
 * Preprocesses markdown text to ensure LaTeX math formulas
 * (both \[...\] block and \(...\) inline) are converted to $ / $$
 * so remark-math and rehype-katex render them accurately.
 */
function normalizeMath(text: string): string {
  if (!text) return "";
  let formatted = text;

  // Convert \[ ... \] to $$ ... $$ (display math)
  formatted = formatted.replace(/\\\[([\s\S]*?)\\\]/g, (_match, eq) => `\n\n$$\n${eq.trim()}\n$$\n\n`);

  // Convert \( ... \) to $ ... $ (inline math)
  formatted = formatted.replace(/\\\(([\s\S]*?)\\\)/g, (_match, eq) => `$${eq.trim()}$`);

  // Handle LaTeX equation environments that might not be wrapped in $$
  formatted = formatted.replace(
    /(\\begin\{(?:equation|align|aligned|gather|matrix|pmatrix|bmatrix)\*?\}[\s\S]*?\\end\{(?:equation|align|aligned|gather|matrix|pmatrix|bmatrix)\*?\})/g,
    (match) => `\n\n$$\n${match.trim()}\n$$\n\n`
  );

  return formatted;
}

export function MarkdownRenderer({ content, className = "" }: MarkdownRendererProps) {
  const processedContent = useMemo(() => normalizeMath(content), [content]);

  return (
    <div className={`markdown-content text-xs leading-relaxed space-y-2 select-text ${className}`}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkMath]}
        rehypePlugins={[rehypeRaw, rehypeKatex]}
        components={{
          p: ({ children }) => <p className="mb-2 last:mb-0 text-neutral-200 leading-relaxed font-sans">{children}</p>,
          strong: ({ children }) => <strong className="font-semibold text-white tracking-wide">{children}</strong>,
          b: ({ children }) => <strong className="font-semibold text-white tracking-wide">{children}</strong>,
          em: ({ children }) => <em className="italic text-neutral-300">{children}</em>,
          i: ({ children }) => <em className="italic text-neutral-300">{children}</em>,
          ul: ({ children }) => <ul className="list-disc list-inside space-y-1.5 my-2 text-neutral-300 pl-1">{children}</ul>,
          ol: ({ children }) => <ol className="list-decimal list-inside space-y-1.5 my-2 text-neutral-300 pl-1">{children}</ol>,
          li: ({ children }) => <li className="text-neutral-300 leading-relaxed">{children}</li>,
          h1: ({ children }) => <h1 className="text-sm font-bold text-white mt-3.5 mb-1.5 border-b border-white/10 pb-1">{children}</h1>,
          h2: ({ children }) => <h2 className="text-xs font-bold text-white mt-3 mb-1">{children}</h2>,
          h3: ({ children }) => <h3 className="text-xs font-semibold text-[#86e810] mt-2.5 mb-1">{children}</h3>,
          h4: ({ children }) => <h4 className="text-xs font-semibold text-neutral-200 mt-2 mb-0.5">{children}</h4>,
          blockquote: ({ children }) => (
            <blockquote className="border-l-2 border-[#76B900]/70 pl-3 my-2 italic text-neutral-400 bg-white/[0.02] py-1 rounded-r">
              {children}
            </blockquote>
          ),
          code: ({ className, children, ...props }: any) => {
            const isInline = !className && typeof children === "string" && !children.includes("\n");
            if (isInline) {
              return (
                <code
                  className="px-1.5 py-0.5 rounded bg-[#1c2217] text-[#86e810] font-mono text-[11px] border border-[#76B900]/20"
                  {...props}
                >
                  {children}
                </code>
              );
            }
            return (
              <div className="my-2.5 rounded-lg bg-[#0d0e11] border border-[#24252a] p-3 overflow-x-auto font-mono text-[11px] text-neutral-200 shadow-inner">
                <code {...props}>{children}</code>
              </div>
            );
          },
          table: ({ children }) => (
            <div className="overflow-x-auto my-2.5 rounded-lg border border-[#262626]">
              <table className="min-w-full divide-y divide-[#262626] text-left text-[11px] font-mono">
                {children}
              </table>
            </div>
          ),
          th: ({ children }) => (
            <th className="px-3 py-1.5 bg-[#181818] text-neutral-200 font-semibold">{children}</th>
          ),
          td: ({ children }) => (
            <td className="px-3 py-1.5 border-t border-[#222] text-neutral-300">{children}</td>
          ),
          hr: () => <hr className="my-3 border-[#262626]" />,
        }}
      >
        {processedContent}
      </ReactMarkdown>
    </div>
  );
}
