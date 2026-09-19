"use client";

import React from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";

interface MarkdownRendererProps {
  content: string;
  className?: string;
}

export function MarkdownRenderer({ content, className = "" }: MarkdownRendererProps) {
  return (
    <div className={`markdown-content text-xs leading-relaxed space-y-2 select-text ${className}`}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkMath]}
        rehypePlugins={[rehypeKatex]}
        components={{
          p: ({ children }) => <p className="mb-2 last:mb-0 text-neutral-200 leading-relaxed">{children}</p>,
          strong: ({ children }) => <strong className="font-semibold text-white">{children}</strong>,
          em: ({ children }) => <em className="italic text-neutral-300">{children}</em>,
          ul: ({ children }) => <ul className="list-disc list-inside space-y-1 my-1 text-neutral-300">{children}</ul>,
          ol: ({ children }) => <ol className="list-decimal list-inside space-y-1 my-1 text-neutral-300">{children}</ol>,
          li: ({ children }) => <li className="text-neutral-300">{children}</li>,
          h1: ({ children }) => <h1 className="text-sm font-bold text-white mt-3 mb-1">{children}</h1>,
          h2: ({ children }) => <h2 className="text-xs font-bold text-white mt-2.5 mb-1">{children}</h2>,
          h3: ({ children }) => <h3 className="text-xs font-semibold text-[#76B900] mt-2 mb-1">{children}</h3>,
          blockquote: ({ children }) => (
            <blockquote className="border-l-2 border-[#76B900]/60 pl-3 my-1 italic text-neutral-400">
              {children}
            </blockquote>
          ),
          code: ({ className, children, ...props }: any) => {
            const isInline = !className && typeof children === "string" && !children.includes("\n");
            if (isInline) {
              return (
                <code
                  className="px-1.5 py-0.5 rounded bg-[#1f2024] text-[#86e810] font-mono text-[11px] border border-white/5"
                  {...props}
                >
                  {children}
                </code>
              );
            }
            return (
              <div className="my-2 rounded-lg bg-[#0d0e11] border border-[#24252a] p-3 overflow-x-auto font-mono text-[11px] text-neutral-200">
                <code {...props}>{children}</code>
              </div>
            );
          },
          table: ({ children }) => (
            <div className="overflow-x-auto my-2 rounded border border-[#24252a]">
              <table className="min-w-full divide-y divide-[#24252a] text-left text-[11px] font-mono">
                {children}
              </table>
            </div>
          ),
          th: ({ children }) => (
            <th className="px-3 py-1.5 bg-[#17181c] text-neutral-200 font-semibold">{children}</th>
          ),
          td: ({ children }) => (
            <td className="px-3 py-1.5 border-t border-[#202126] text-neutral-300">{children}</td>
          ),
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
