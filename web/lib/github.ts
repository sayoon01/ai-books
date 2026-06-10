const OWNER = "sayoon01"
const REPO  = "ai-books"
const BASE  = `https://api.github.com/repos/${OWNER}/${REPO}`

function headers(): Record<string, string> {
  const token = process.env.GITHUB_TOKEN
  const base: Record<string, string> = { "Content-Type": "application/json" }
  if (token) base["Authorization"] = `Bearer ${token}`
  return base
}

async function get<T>(url: string): Promise<T> {
  const res = await fetch(url, { headers: headers(), next: { revalidate: 60 } })
  if (!res.ok) throw new Error(`GitHub API 오류: ${res.status} ${url}`)
  return res.json()
}

export interface BookMeta {
  slug:               string
  title:              string
  language:           string
  model:              string
  total_chapters:     number
  completed_chapters: number
  status:             "done" | "in_progress"
}

export interface Chapter {
  number:   number
  filename: string
  title:    string
}

// 루트 디렉토리에서 폴더 목록 → 각 meta.json 읽어 책 목록 반환
export async function getBooks(): Promise<BookMeta[]> {
  type Entry = { name: string; type: string }
  const entries = await get<Entry[]>(`${BASE}/contents`)
  const folders = entries.filter((e) => e.type === "dir")

  const books = await Promise.all(
    folders.map(async (f) => {
      try {
        type FileRes = { content: string }
        const file = await get<FileRes>(`${BASE}/contents/${encodeURIComponent(f.name)}/meta.json`)
        const meta = JSON.parse(Buffer.from(file.content, "base64").toString("utf-8"))
        return { slug: f.name, ...meta } as BookMeta
      } catch {
        return null
      }
    })
  )

  return books.filter(Boolean) as BookMeta[]
}

// 특정 책 메타 정보
export async function getBookMeta(slug: string): Promise<BookMeta> {
  type FileRes = { content: string }
  const file = await get<FileRes>(`${BASE}/contents/${encodeURIComponent(slug)}/meta.json`)
  const meta = JSON.parse(Buffer.from(file.content, "base64").toString("utf-8"))
  return { slug, ...meta }
}

// 챕터 목록 (chapter-NN.md 파일만 필터링)
export async function getChapters(slug: string): Promise<Chapter[]> {
  type Entry = { name: string; type: string }
  const entries = await get<Entry[]>(`${BASE}/contents/${encodeURIComponent(slug)}`)

  return entries
    .filter((e) => e.type === "file" && /^chapter-\d+\.md$/.test(e.name))
    .sort((a, b) => a.name.localeCompare(b.name))
    .map((e) => {
      const number = parseInt(e.name.replace("chapter-", "").replace(".md", ""), 10)
      return { number, filename: e.name, title: `챕터 ${number}` }
    })
}

// 챕터 본문 (마크다운 텍스트)
export async function getChapterContent(slug: string, filename: string): Promise<string> {
  type FileRes = { content: string }
  const file = await get<FileRes>(
    `${BASE}/contents/${encodeURIComponent(slug)}/${encodeURIComponent(filename)}`
  )
  const raw = Buffer.from(file.content, "base64").toString("utf-8")
  // 첫 번째 h1 제목을 title로 추출해 반환
  return raw
}
