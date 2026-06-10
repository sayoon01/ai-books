import { getBooks } from "@/lib/github"
import BookCard from "@/components/BookCard"

export default async function HomePage() {
  const books = await getBooks()
  const languages = Array.from(new Set(books.map((b) => b.language)))

  return (
    <main className="max-w-5xl mx-auto px-6 py-12">
      <div className="mb-10">
        <h1 className="text-3xl font-bold text-gray-900">AI Generated Books</h1>
        <p className="text-gray-500 mt-2 text-sm">Gemma 4 31B가 생성한 책 목록</p>
      </div>

      <div className="flex gap-2 mb-8 flex-wrap">
        <span className="text-xs text-gray-500 self-center mr-1">언어:</span>
        {languages.map((lang) => (
          <span key={lang} className="text-xs bg-gray-100 text-gray-700 px-3 py-1 rounded-full">
            {lang}
          </span>
        ))}
      </div>

      {books.length === 0 ? (
        <p className="text-gray-400 text-sm">아직 생성된 책이 없습니다.</p>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4">
          {books.map((book) => (
            <BookCard key={book.slug} book={book} />
          ))}
        </div>
      )}
    </main>
  )
}
