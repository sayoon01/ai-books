"use client"

import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"

export default function ChapterViewer({ content }: { content: string }) {
  return (
    <article className="prose prose-gray max-w-none prose-headings:font-semibold prose-a:text-blue-600">
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
    </article>
  )
}
