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
  doc_type:           string
  total_chapters:     number   // UI 표시용 (신규 meta의 total 도 여기로 정규화)
  completed_chapters: number
  status:             "done" | "in_progress"
}

// 구(meta: total_chapters/completed_chapters) · 신(meta: total/completed/doc_type) 메타를 UI 형태로 정규화
function normalizeMeta(slug: string, raw: Record<string, unknown>): BookMeta {
  const num = (...vs: unknown[]) =>
    (vs.find((v) => typeof v === "number") as number | undefined) ?? 0
  return {
    slug,
    title:              String(raw.title ?? slug),
    language:           String(raw.language ?? "ko"),
    model:              String(raw.model ?? ""),
    doc_type:           String(raw.doc_type ?? ""),
    total_chapters:     num(raw.total, raw.total_chapters),
    completed_chapters: num(raw.completed, raw.completed_chapters),
    status:             raw.status === "done" ? "done" : "in_progress",
  }
}

export interface Chapter {
  number:   number
  filename: string
  title:    string
}

// 문서 디렉터리가 아닌 루트 폴더 (GitHub API 호출 수·rate limit 절약)
const NON_DOC_DIRS = new Set([
  "web", "generator", "toc", "data", "cache", "output", "node_modules",
])

// 루트 디렉토리에서 폴더 목록 → 각 meta.json 읽어 문서 목록 반환
export async function getBooks(): Promise<BookMeta[]> {
  type Entry = { name: string; type: string }
  let entries: Entry[]
  try {
    entries = await get<Entry[]>(`${BASE}/contents`)
  } catch {
    return []   // 빌드/런타임에 GitHub 접근 실패해도 페이지가 죽지 않도록(배포 안정성)
  }
  const folders = entries.filter(
    (e) => e.type === "dir" && !e.name.startsWith(".") && !NON_DOC_DIRS.has(e.name)
  )

  const books = await Promise.all(
    folders.map(async (f) => {
      try {
        type FileRes = { content: string }
        const file = await get<FileRes>(`${BASE}/contents/${encodeURIComponent(f.name)}/meta.json`)
        const meta = JSON.parse(Buffer.from(file.content, "base64").toString("utf-8"))
        return normalizeMeta(f.name, meta)
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
  return normalizeMeta(slug, meta)
}

// 작성 단위 목록 (chapter-NN.md 구 · unit-NN.md 신 둘 다 인식)
export async function getChapters(slug: string): Promise<Chapter[]> {
  type Entry = { name: string; type: string }
  const entries = await get<Entry[]>(`${BASE}/contents/${encodeURIComponent(slug)}`)

  return entries
    .filter((e) => e.type === "file" && /^(chapter|unit)-\d+\.md$/.test(e.name))
    .sort((a, b) => a.name.localeCompare(b.name))
    .map((e) => {
      const number = parseInt(e.name.replace(/^(chapter|unit)-/, "").replace(".md", ""), 10)
      return { number, filename: e.name, title: `${number}장` }
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
