import React from "react";
import ReactMarkdown from "react-markdown";
import rehypeSanitize from "rehype-sanitize";
import remarkGfm from "remark-gfm";
import { slugifyHeading } from "@/lib/utils";

interface MarkdownReportProps {
  content: string;
  onSelectCitation?: (citationNumber: number) => void;
  activeCitation?: number | null;
}

function renderWithCitationButtons(
  node: React.ReactNode,
  onSelectCitation?: (num: number) => void,
  activeCitation?: number | null
): React.ReactNode {
  if (typeof node === "string") {
    const parts = node.split(/(\[\d+\])/g);
    return parts.map((part, idx) => {
      const match = /^\[(\d+)\]$/.exec(part);
      if (match) {
        const num = Number(match[1]);
        const isActive = activeCitation === num;
        return (
          <button
            key={`${num}-${idx}`}
            type="button"
            onClick={() => onSelectCitation?.(num)}
            className={`inline-flex items-center justify-center mx-0.5 px-1.5 py-0.5 rounded text-[11px] font-mono font-semibold align-baseline transition-colors border ${
              isActive
                ? "bg-primary text-primary-foreground border-primary"
                : "bg-primary/15 text-primary border-primary/30 hover:bg-primary/25"
            }`}
            title={`Inspect source [${num}]`}
          >
            [{num}]
          </button>
        );
      }
      return part;
    });
  }
  if (Array.isArray(node)) {
    return node.map((child, idx) => (
      <React.Fragment key={idx}>
        {renderWithCitationButtons(child, onSelectCitation, activeCitation)}
      </React.Fragment>
    ));
  }
  return node;
}

function getTextFromChildren(children: React.ReactNode): string {
  if (typeof children === "string") return children;
  if (Array.isArray(children)) return children.map(getTextFromChildren).join("");
  if (React.isValidElement(children)) {
    return getTextFromChildren((children.props as { children?: React.ReactNode }).children);
  }
  return "";
}

export function MarkdownReport({
  content,
  onSelectCitation,
  activeCitation,
}: MarkdownReportProps) {
  return (
    <div className="prose-report max-w-none">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeSanitize]}
        components={{
          h2: ({ children }) => {
            const text = getTextFromChildren(children);
            return <h2 id={slugifyHeading(text)}>{children}</h2>;
          },
          h3: ({ children }) => {
            const text = getTextFromChildren(children);
            return <h3 id={slugifyHeading(text)}>{children}</h3>;
          },
          p: ({ children }) => (
            <p>{renderWithCitationButtons(children, onSelectCitation, activeCitation)}</p>
          ),
          li: ({ children }) => (
            <li>{renderWithCitationButtons(children, onSelectCitation, activeCitation)}</li>
          ),
          td: ({ children }) => (
            <td>{renderWithCitationButtons(children, onSelectCitation, activeCitation)}</td>
          ),
          a: ({ href, children }) => (
            <a
              href={href}
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary underline underline-offset-2 hover:text-primary/80"
            >
              {children}
            </a>
          ),
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
