import { type ReactNode, useEffect, useState } from "react";

import { createPortal } from "react-dom";
import { useTranslation } from "react-i18next";
import { Link, useLocation } from "react-router-dom";

import Logo from "@/components/ui/Logo";
import Toaster from "@/components/ui/Toaster";
import { ToastProvider } from "@/contexts/ToastContext";
import { useAuth } from "@/hooks/useAuth";

import Header from "./Header";
import Sidebar from "./Sidebar";


interface Props {
  children: ReactNode;
}

/* ── Public footer ───────────────────────────────────────────────────────── */
export function PublicFooter() {
  const { t } = useTranslation(["auth", "common", "http", "landing", "nav"]);
  return (
    <footer className="border-t border-white/8 bg-void">
      <div className="mx-auto flex max-w-4xl flex-col items-center gap-5 px-6 py-8 sm:flex-row sm:justify-between">
        <Link to="/" className="shrink-0">
          <Logo size={24} />
        </Link>
        <nav className="flex flex-wrap justify-center gap-x-6 gap-y-2 text-sm text-white/30">
          <Link to="/jobs" className="transition hover:text-white/60">
            {t("nav:jobs")}
          </Link>
          <Link to="/articles" className="transition hover:text-white/60">
            {t("nav:articles")}
          </Link>
          <Link to="/about" className="transition hover:text-white/60">
            {t("nav:about")}
          </Link>
          <Link to="/contact" className="transition hover:text-white/60">
            {t("nav:contact")}
          </Link>
          <Link to="/privacy-policy" className="transition hover:text-white/60">
            {t("nav:privacy-policy")}
          </Link>
          <Link to="/terms" className="transition hover:text-white/60">
            {t("nav:terms")}
          </Link>
        </nav>
        <p className="text-xs text-white/20">
          &copy; {new Date().getFullYear()}{" "}
          <span className="text-copper/60">RS Recruiting</span>.{" "}
          {t("landing:footer.copyright")}
        </p>
      </div>
    </footer>
  );
}

/* ── Public header ───────────────────────────────────────────────────────── */
export function PublicHeader({ transparent = false }: { transparent?: boolean }) {
  const { t } = useTranslation(["auth", "common", "http", "landing", "nav"]);
  const { isAuthenticated } = useAuth();
  const { pathname } = useLocation();
  const [open, setOpen] = useState(false);
  // When transparent=true, track scroll to solidify the bar
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    document.body.style.overflow = open ? "hidden" : "";
    return () => {
      document.body.style.overflow = "";
    };
  }, [open]);

  useEffect(() => {
    if (!transparent) return;
    const onScroll = () => setScrolled(window.scrollY > 60);
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, [transparent]);

  // Stagger delay for the mobile menu links cascading in on open
  const STAGGER_BASE_MS = 80;
  const STAGGER_STEP_MS = 40;

  const links = [
    { to: "/jobs", label: t("nav:jobs") },
    { to: "/articles", label: t("nav:articles") },
    { to: "/about", label: t("nav:about") },
    { to: "/contact", label: t("nav:contact") },
  ];

  // Glass style (landing page at top): white-tinted frosted glass
  // Solid style (all other pages, or after scrolling): dark void bar
  const solid = !transparent || scrolled;

  const isLinkActive = (to: string) => pathname === to || pathname.startsWith(`${to}/`);

  return (
    <>
      {/* ── Navbar — full-width, fixed to top ─────────────────────────── */}
      <header
        className="fixed inset-x-0 top-0 z-40 transition-all duration-300"
        style={{
          background: solid
            ? "color-mix(in srgb, var(--color-void) 95%, transparent)"
            : "rgba(255,255,255,0.06)",
          backdropFilter: "blur(12px)",
          borderBottom: solid
            ? "1px solid rgba(255,255,255,0.06)"
            : "1px solid rgba(255,255,255,0.08)",
          boxShadow: solid ? "0 8px 24px -16px rgba(0,0,0,0.6)" : "none",
        }}
      >
        <div className="mx-auto flex max-w-5xl items-center justify-between px-6 py-4">
          {/* Logo */}
          <Link to="/" className="flex items-center gap-2.5 shrink-0">
            <Logo size={26} />
            <span className="font-wordmark text-[15px] tracking-widest text-gold/60 transition hover:text-gold/90">
              RS Recruiting
            </span>
          </Link>

          {/* Desktop links */}
          <nav className="hidden items-center gap-7 sm:flex">
            {links.map((l) => {
              const active = isLinkActive(l.to);
              return (
                <Link
                  key={l.to}
                  to={l.to}
                  className={`relative py-1 text-sm transition after:absolute after:inset-x-0 after:-bottom-1 after:h-px after:origin-center after:bg-copper after:transition-transform after:duration-300 ${
                    active
                      ? "text-white/90 after:scale-x-100"
                      : "text-white/45 after:scale-x-0 hover:text-white/80 hover:after:scale-x-100"
                  }`}
                >
                  {l.label}
                </Link>
              );
            })}
            <div className="h-5 w-px bg-white/10" />
            {isAuthenticated ? (
              <Link
                to="/dashboard"
                className="relative inline-flex items-center gap-2 border border-white/15 px-5 py-2 text-xs font-semibold uppercase tracking-[0.15em] text-white/70 transition-colors duration-300 hover:border-copper/50 hover:text-copper"
                style={{
                  clipPath:
                    "polygon(0 0, 100% 0, 100% 100%, 10px 100%, 0 calc(100% - 10px))",
                }}
              >
                {t("nav:dashboard")}
              </Link>
            ) : (
              <Link
                to="/login"
                className="relative inline-flex items-center gap-2 bg-copper-dark px-5 py-2 text-xs font-semibold uppercase tracking-[0.15em] text-white transition-colors duration-300 hover:bg-copper"
                style={{
                  clipPath:
                    "polygon(0 0, 100% 0, 100% 100%, 10px 100%, 0 calc(100% - 10px))",
                }}
              >
                <span className="brass-hairline absolute inset-x-0 top-0 h-px" />
                {t("auth:login.submitText")}
              </Link>
            )}
          </nav>

          {/* Mobile hamburger — morphs into an × when the menu is open */}
          <button
            onClick={() => setOpen((o) => !o)}
            aria-label={t("nav:menu")}
            aria-expanded={open}
            className="relative z-[60] flex size-9 flex-col items-center justify-center gap-[5px] sm:hidden"
          >
            <span
              className="block h-px w-5 rounded-full bg-white/55 transition-all duration-300"
              style={{
                transform: open ? "translateY(5.5px) rotate(45deg)" : "none",
              }}
            />
            <span
              className="block h-px w-5 rounded-full bg-white/55 transition-all duration-300"
              style={{ opacity: open ? 0 : 1 }}
            />
            <span
              className="block h-px w-3.5 self-end rounded-full bg-white/55 transition-all duration-300"
              style={{
                width: open ? "1.25rem" : undefined,
                transform: open ? "translateY(-5.5px) rotate(-45deg)" : "none",
              }}
            />
          </button>
        </div>
      </header>

      {/* ── Mobile overlay — portal to document.body so it's never clipped ── */}
      {createPortal(
        <div
          className="fixed inset-0 z-50 flex flex-col bg-void"
          style={{
            opacity: open ? 1 : 0,
            pointerEvents: open ? "auto" : "none",
            visibility: open ? "visible" : "hidden",
            transition: "opacity 0.25s ease",
            backgroundImage:
              "radial-gradient(circle at 85% 0%, color-mix(in srgb, var(--color-copper) 12%, transparent), transparent 55%)",
          }}
        >
          {/* Top bar */}
          <div className="flex items-center border-b border-white/8 px-5 py-3.5">
            <Link
              to="/"
              onClick={() => setOpen(false)}
              className="flex items-center gap-2.5"
            >
              <Logo size={26} />
              <span className="font-wordmark text-[15px] font-light tracking-widest text-gold/55">
                RS Recruiting
              </span>
            </Link>
          </div>

          {/* Links */}
          <nav className="flex flex-1 flex-col justify-center px-7">
            {links.map((l, i) => {
              const active = isLinkActive(l.to);
              return (
                <Link
                  key={l.to}
                  to={l.to}
                  onClick={() => setOpen(false)}
                  className={`group flex items-center justify-between border-b border-white/8 py-6 text-2xl font-light transition-all duration-300 ${
                    active ? "text-white" : "text-white/60 hover:text-white"
                  }`}
                  style={{
                    opacity: open ? 1 : 0,
                    transform: open ? "translateY(0)" : "translateY(8px)",
                    transitionDelay: open
                      ? `${STAGGER_BASE_MS + i * STAGGER_STEP_MS}ms`
                      : "0ms",
                  }}
                >
                  <span className="flex items-center gap-3">
                    {active && <span className="size-1.5 rounded-full bg-copper" />}
                    {l.label}
                  </span>
                  <svg
                    xmlns="http://www.w3.org/2000/svg"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth={1.5}
                    className="size-4 text-copper/35 transition-transform duration-200 group-hover:-translate-x-1"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      d="M15.75 19.5 8.25 12l7.5-7.5"
                    />
                  </svg>
                </Link>
              );
            })}

            {isAuthenticated ? (
              <Link
                to="/dashboard"
                onClick={() => setOpen(false)}
                className="relative mt-8 inline-flex items-center gap-2 self-start border border-white/15 px-7 py-3 text-xs font-semibold uppercase tracking-[0.15em] text-white/70 transition-colors duration-300 hover:border-copper/50 hover:text-copper"
                style={{
                  clipPath:
                    "polygon(0 0, 100% 0, 100% 100%, 14px 100%, 0 calc(100% - 14px))",
                  opacity: open ? 1 : 0,
                  transform: open ? "translateY(0)" : "translateY(8px)",
                  transitionDelay: open
                    ? `${STAGGER_BASE_MS + links.length * STAGGER_STEP_MS}ms`
                    : "0ms",
                  transitionProperty: "opacity, transform, color, border-color",
                  transitionDuration: "300ms",
                }}
              >
                {t("nav:dashboard")}
              </Link>
            ) : (
              <Link
                to="/login"
                onClick={() => setOpen(false)}
                className="relative mt-8 inline-flex items-center gap-2 self-start bg-copper-dark px-7 py-3 text-xs font-semibold uppercase tracking-[0.15em] text-white transition-colors duration-300 hover:bg-copper"
                style={{
                  clipPath:
                    "polygon(0 0, 100% 0, 100% 100%, 14px 100%, 0 calc(100% - 14px))",
                  opacity: open ? 1 : 0,
                  transform: open ? "translateY(0)" : "translateY(8px)",
                  transitionDelay: open
                    ? `${STAGGER_BASE_MS + links.length * STAGGER_STEP_MS}ms`
                    : "0ms",
                  transitionProperty: "opacity, transform, background-color",
                  transitionDuration: "300ms",
                }}
              >
                <span className="brass-hairline absolute inset-x-0 top-0 h-px" />
                {t("auth:login.submitText")}
              </Link>
            )}
          </nav>

          <p className="px-7 py-6 text-xs text-white/18">
            &copy; {new Date().getFullYear()} RS Recruiting
          </p>
        </div>,
        document.body,
      )}
    </>
  );
}

// Path checks for the "always public shell" set (landing, jobs board,
// articles, about, contact, legal pages, /activate). These pages never make
// sense in the authenticated chrome — a candidate browsing /jobs or reading
// the privacy policy should see the same layout an anonymous visitor sees,
// not their dashboard sidebar.
const PUBLIC_SHELL_PREFIXES = ["/jobs", "/articles"];
const PUBLIC_SHELL_EXACT = new Set([
  "/",
  "/about",
  "/contact",
  "/privacy-policy",
  "/terms",
  "/activate",
]);

function isPublicShellPath(pathname: string): boolean {
  if (PUBLIC_SHELL_EXACT.has(pathname)) return true;
  return PUBLIC_SHELL_PREFIXES.some(
    (p) => pathname === p || pathname.startsWith(`${p}/`),
  );
}

/* ── Shell ───────────────────────────────────────────────────────────────── */
function ShellContent({ children }: Props) {
  const { isAuthenticated } = useAuth();
  const { pathname } = useLocation();
  const [sidebarOpen, setSidebarOpen] = useState(false);

  // Auth pages and the triage reviewer manage their own full-screen layout.
  // Triage uses `fixed inset-0` which would otherwise be contained by the
  // transformed AppShell main element (page-enter animation creates a
  // containing block, so the fixed overlay can't escape it).
  if (
    pathname === "/login" ||
    pathname === "/register" ||
    pathname === "/register-candidate" ||
    pathname === "/forgot-password" ||
    pathname === "/reset-password" ||
    pathname === "/admin/applications/triage"
  ) {
    return <>{children}</>;
  }

  // Public-content pages render in the public shell regardless of auth
  // state. PublicHeader switches its CTA based on `isAuthenticated`, so a
  // logged-in candidate still sees the "Dashboard" affordance there.
  const publicShell = isPublicShellPath(pathname);

  if (isAuthenticated && !publicShell) {
    return (
      <div className="flex h-screen flex-col">
        <Header onMenuToggle={() => setSidebarOpen((o) => !o)} />
        <div className="flex flex-1 overflow-hidden">
          <Sidebar isOpen={sidebarOpen} onClose={() => setSidebarOpen(false)} />
          <main
            key={pathname}
            className="page-enter flex-1 overflow-y-auto bg-page p-4 sm:p-6"
          >
            {children}
          </main>
        </div>
      </div>
    );
  }

  // Hero pages start their own full-bleed section from y=0 (navbar floats over it)
  const heroRoutes = new Set(["/", "/about", "/contact", "/jobs"]);
  // Single-screen pages: constrain to viewport height so nothing scrolls
  const singleScreenRoutes = new Set(["/contact"]);

  // All public pages: single shell — header and footer owned here (DRY)
  return (
    <div
      className={`flex flex-col bg-void ${singleScreenRoutes.has(pathname) ? "h-dvh overflow-hidden" : "min-h-screen"}`}
    >
      <PublicHeader transparent={heroRoutes.has(pathname)} />
      {/* flex flex-col so children can use flex-1 to fill remaining height */}
      <main key={pathname} className="page-enter flex flex-1 flex-col">
        {children}
      </main>
      <PublicFooter />
    </div>
  );
}

export default function AppShell({ children }: Props) {
  return (
    <ToastProvider>
      <ShellContent>{children}</ShellContent>
      <Toaster />
    </ToastProvider>
  );
}
