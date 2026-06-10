import Link from "next/link"
import { BookMeta } from "@/lib/github"

export default function BookCard({ book }: { book: BookMeta }) {
  const isDone = book.status === "done"

  return (
    <Link href={`/books/${encodeURIComponent(book.slug)}`}>
      <div className="border border-gray-200 rounded-xl p-5 hover:shadow-md hover:border-blue-400 transition-all cursor-pointer h-full flex flex-col gap-3">
        <div className="flex items-start justify-between gap-2">
          <h2 className="font-semibold text-gray-900 text-sm leading-snug">{book.title}</h2>
          <span
            className={`shrink-0 text-xs px-2 py-0.5 rounded-full font-medium ${
              isDone
                ? "bg-green-100 text-green-700"
                : "bg-yellow-100 text-yellow-700"
            }`}
          >
            {isDone ? "완료" : "진행중"}
          </span>
        </div>

        <div className="mt-auto flex items-center gap-3 text-xs text-gray-500">
          <span className="bg-gray-100 px-2 py-0.5 rounded">{book.language}</span>
          <span>{book.completed_chapters} / {book.total_chapters} 챕터</span>
          <span className="ml-auto truncate">{book.model}</span>
        </div>
      </div>
    </Link>
  )
}
