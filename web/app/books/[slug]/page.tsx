import { getBookMeta, getChapters, getChapterContent } from "@/lib/github"
import ChapterViewer from "@/components/ChapterViewer"
import Link from "next/link"

interface Props {
  params: Promise<{ slug: string }>
  searchParams: Promise<{ chapter?: string }>
}

export default async function BookPage({ params, searchParams }: Props) {
  const { slug }   = await params
  const { chapter } = await searchParams
  const decodedSlug = decodeURIComponent(slug)

  const [meta, chapters] = await Promise.all([
    getBookMeta(decodedSlug),
    getChapters(decodedSlug),
  ])

  const currentChapter = chapters.find((c) => c.filename === chapter) ?? chapters[0]
  const content = currentChapter
    ? await getChapterContent(decodedSlug, currentChapter.filename)
    : ""

  return (
    <div className="flex min-h-screen">
      {/* 사이드바 */}
      <aside className="w-60 shrink-0 border-r border-gray-200 bg-gray-50 p-5 flex flex-col gap-4">
        <div>
          <Link href="/" className="text-xs text-blue-500 hover:underline">← 목록으로</Link>
          <h2 className="mt-3 font-semibold text-gray-900 text-sm leading-snug">{meta.title}</h2>
          <p className="text-xs text-gray-400 mt-1">{meta.completed_chapters}/{meta.total_chapters} 챕터</p>
        </div>

        <nav className="flex flex-col gap-1">
          {chapters.map((c) => {
            const isActive = c.filename === (currentChapter?.filename ?? "")
            return (
              <Link
                key={c.filename}
                href={`/books/${slug}?chapter=${c.filename}`}
                className={`text-xs px-3 py-2 rounded-lg transition-colors ${
                  isActive
                    ? "bg-blue-100 text-blue-700 font-medium"
                    : "text-gray-600 hover:bg-gray-200"
                }`}
              >
                {c.title}
              </Link>
            )
          })}
        </nav>
      </aside>

      {/* 본문 */}
      <main className="flex-1 px-10 py-10 max-w-3xl">
        {content ? (
          <ChapterViewer content={content} />
        ) : (
          <p className="text-gray-400 text-sm">챕터를 선택하세요.</p>
        )}
      </main>
    </div>
  )
}
