import DOMPurify from "dompurify";
import { marked } from "marked";

export interface ArticleMeta {
  slug: string;
  title: string;
  description: string;
  date: string;
  /** Banner image — path under `frontend/public/` (e.g. `/hero-buildings.jpg`). */
  image?: string;
  /** Alt text for the banner image. Falls back to the title. */
  imageAlt?: string;
  keywords?: string;
}

export interface Article extends ArticleMeta {
  /** Rendered HTML body (markdown → HTML, DOMPurify-sanitized). */
  bodyHtml: string;
}

// Vite glob — eagerly load every .md in this directory as a raw string at
// build time. Markdown bodies are tiny and there's never going to be hundreds
// of them, so eager is fine.
const RAW = import.meta.glob<string>("./articles/*.md", {
  query: "?raw",
  import: "default",
  eager: true,
});

function parseFrontmatter(raw: string): { meta: Record<string, string>; body: string } {
  const match = raw.match(/^---\r?\n([\s\S]*?)\r?\n---\r?\n([\s\S]*)$/);
  if (!match) return { meta: {}, body: raw };
  const meta: Record<string, string> = {};
  for (const line of match[1].split(/\r?\n/)) {
    const m = line.match(/^(\w+):\s*(.*)$/);
    if (m) meta[m[1]] = m[2].trim().replace(/^["']|["']$/g, "");
  }
  return { meta, body: match[2] };
}

function loadAll(): Article[] {
  const out: Article[] = [];
  for (const [path, raw] of Object.entries(RAW)) {
    const slugFromPath = path.replace(/^.*\//, "").replace(/\.md$/, "");
    const { meta, body } = parseFrontmatter(raw);
    if (!meta.title || !meta.description || !meta.date) {
      // Skip drafts missing required metadata rather than crashing the page.
      continue;
    }
    const html = marked.parse(body, { async: false });
    out.push({
      slug: meta.slug || slugFromPath,
      title: meta.title,
      description: meta.description,
      date: meta.date,
      image: meta.image,
      imageAlt: meta.imageAlt,
      keywords: meta.keywords,
      bodyHtml: DOMPurify.sanitize(typeof html === "string" ? html : ""),
    });
  }
  // Newest first.
  return out.sort((a, b) => (a.date < b.date ? 1 : -1));
}

export const ARTICLES: Article[] = loadAll();

export function getArticle(slug: string): Article | undefined {
  return ARTICLES.find((a) => a.slug === slug);
}
