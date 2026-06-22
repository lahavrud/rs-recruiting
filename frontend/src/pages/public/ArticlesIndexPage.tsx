import { Link } from "react-router-dom";

import Eyebrow from "@/components/ui/Eyebrow";
import FadeInImage from "@/components/ui/FadeInImage";
import SeoHead, { SITE_URL, SITE_NAME } from "@/components/ui/SeoHead";
import { articles } from "@/content/articles";
import { formatDateLong as formatDate } from "@/utils/formatDate";

const PAGE_TITLE = "RS Recruiting — מאמרים ומדריכים";
const PAGE_DESCRIPTION =
  "מדריכים, ניתוחי שוק וטיפים לתפקידים בתחום ניהול ותפעול מבנים ונכסים בישראל.";

export default function ArticlesIndexPage() {
  const breadcrumb = {
    "@type": "BreadcrumbList",
    itemListElement: [
      { "@type": "ListItem", position: 1, name: SITE_NAME, item: SITE_URL },
      { "@type": "ListItem", position: 2, name: "מאמרים", item: `${SITE_URL}/articles` },
    ],
  };
  const itemList = {
    "@type": "ItemList",
    name: PAGE_TITLE,
    url: `${SITE_URL}/articles`,
    numberOfItems: articles.length,
    itemListElement: articles.map((a, i) => ({
      "@type": "ListItem",
      position: i + 1,
      name: a.title,
      url: `${SITE_URL}/articles/${a.slug}`,
    })),
  };
  const structuredData = {
    "@context": "https://schema.org",
    "@graph": [breadcrumb, itemList],
  };

  return (
    <div className="mx-auto max-w-4xl px-6 pt-24 pb-16">
      <SeoHead
        title={PAGE_TITLE}
        description={PAGE_DESCRIPTION}
        canonical={`${SITE_URL}/articles`}
        structuredData={structuredData}
      />

      <header className="mb-10">
        <Eyebrow>
          מאמרים
        </Eyebrow>
        <div className="mt-3 h-px w-8 bg-copper/40" />
        <h1 className="mt-4 text-2xl font-semibold text-white/90 sm:text-3xl">
          מדריכים וניתוחי שוק
        </h1>
        <p className="mt-2 text-sm text-white/45">{PAGE_DESCRIPTION}</p>
      </header>

      {articles.length === 0 ? (
        <p className="text-sm text-white/40">אין כרגע מאמרים זמינים.</p>
      ) : (
        <ul className="space-y-5">
          {articles.map((a) => (
            <li key={a.slug}>
              <Link
                to={`/articles/${a.slug}`}
                className="block overflow-hidden rounded-xl border border-white/8 bg-card transition hover:border-copper/40 hover:bg-card-raised sm:flex"
              >
                {a.image && (
                  <div className="relative h-44 shrink-0 overflow-hidden bg-void sm:h-auto sm:w-56">
                    <FadeInImage
                      src={a.image}
                      alt={a.imageAlt || a.title}
                      className="h-full w-full object-cover"
                      loading="lazy"
                      fadeMs={500}
                    />
                    <div className="absolute inset-0 bg-gradient-to-l from-card/30 to-transparent sm:bg-gradient-to-r" />
                  </div>
                )}
                <div className="flex-1 p-6">
                  <p className="text-[10px] font-semibold uppercase tracking-widest text-copper/70">
                    {formatDate(a.date)}
                  </p>
                  <h2 className="mt-2 text-lg font-semibold text-white/90 sm:text-xl">
                    {a.title}
                  </h2>
                  <p className="mt-2 text-sm text-white/55">{a.description}</p>
                </div>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
