import { useState, type MouseEvent, type ReactNode } from "react";
import { motion, MotionConfig, useMotionValueEvent, useScroll, useSpring } from "motion/react";
import { Check, Copy, Download } from "lucide-react";
import { DOWNLOAD, REPO, RELEASES, type Release } from "./release";

export const asset = (path: string) => `${import.meta.env.BASE_URL}${path}`;

/** Every page is wrapped in this, so animations follow the OS "reduce motion" setting (R6). */
export function Page({ children }: { children: ReactNode }) {
  return (
    <MotionConfig reducedMotion="user">
      <Header />
      <main id="main">{children}</main>
      <Footer />
    </MotionConfig>
  );
}

/** Fades and lifts its children in the first time they scroll into view. */
export function Reveal({ children, delay = 0, className }: { children: ReactNode; delay?: number; className?: string }) {
  return (
    <motion.div
      className={className}
      initial={{ opacity: 0, y: 24 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-80px" }}
      transition={{ duration: 0.6, delay, ease: [0.22, 1, 0.36, 1] }}
    >
      {children}
    </motion.div>
  );
}

export function Section({ id, title, kicker, children }: { id: string; title: string; kicker?: string; children: ReactNode }) {
  return (
    <section id={id} aria-labelledby={`${id}-title`} className="mx-auto max-w-6xl scroll-mt-20 px-4 py-20 sm:px-6 sm:py-28">
      <Reveal className="mb-10 max-w-2xl">
        {kicker && <p className="mb-3 text-sm font-medium uppercase tracking-widest text-muted">{kicker}</p>}
        <h2 id={`${id}-title`} className="text-3xl font-semibold tracking-tight sm:text-4xl">{title}</h2>
      </Reveal>
      {children}
    </section>
  );
}

/** A surface card that lifts on hover and lights up under the cursor. */
export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  const track = (e: MouseEvent<HTMLDivElement>) => {
    const r = e.currentTarget.getBoundingClientRect();
    e.currentTarget.style.setProperty("--x", `${e.clientX - r.left}px`);
    e.currentTarget.style.setProperty("--y", `${e.clientY - r.top}px`);
  };
  return (
    <motion.div
      onMouseMove={track}
      whileHover={{ y: -4 }}
      transition={{ type: "spring", stiffness: 300, damping: 22 }}
      className={`group relative h-full overflow-hidden rounded-2xl border border-line bg-surface p-6 transition-colors hover:border-line-strong ${className}`}
    >
      <div aria-hidden className="pointer-events-none absolute inset-0 opacity-0 transition-opacity duration-300 group-hover:opacity-100 bg-[radial-gradient(360px_circle_at_var(--x)_var(--y),var(--glow),transparent_70%)]" />
      <div className="relative h-full">{children}</div>
    </motion.div>
  );
}

/** A code line with a copy button. */
export function CopyCommand({ command }: { command: string }) {
  const [copied, setCopied] = useState(false);
  const copy = () =>
    navigator.clipboard?.writeText(command).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1600);
    });
  return (
    <div className="flex items-center gap-2 rounded-lg bg-surface-2 py-1.5 pl-4 pr-1.5">
      <code className="min-w-0 flex-1 overflow-x-auto whitespace-nowrap py-1.5 font-mono text-sm">{command}</code>
      <button type="button" onClick={copy} aria-label={copied ? "Copied" : "Copy command"}
        className="grid size-9 shrink-0 place-items-center rounded-md text-muted hover:bg-surface hover:text-fg">
        {copied ? <Check aria-hidden className="size-4 text-good" /> : <Copy aria-hidden className="size-4" />}
      </button>
      <span className="sr-only" aria-live="polite">{copied ? "Copied to clipboard" : ""}</span>
    </div>
  );
}

export function DownloadButton({ size = "lg" }: { size?: "md" | "lg" }) {
  const pad = size === "lg" ? "h-13 px-7 text-base" : "h-10 px-4 text-sm";
  return (
    <motion.a
      href={DOWNLOAD}
      whileHover={{ scale: 1.03 }}
      whileTap={{ scale: 0.98 }}
      className={`inline-flex shrink-0 items-center gap-2.5 whitespace-nowrap rounded-xl bg-primary font-semibold text-on-primary shadow-lg shadow-black/20 ${pad}`}
    >
      <Download aria-hidden className="size-5" />
      {size === "md" ? (
        <>
          <span className="sm:hidden">Download</span>
          <span className="hidden sm:inline">Download for Windows</span>
        </>
      ) : (
        "Download for Windows"
      )}
    </motion.a>
  );
}

/** "v0.1.0 · 31 MB · Windows 10/11", or a link to the releases page when the API is unavailable (R8). */
export function VersionLine({ release }: { release: Release | null }) {
  return (
    <p className="text-sm text-muted">
      {release ? (
        <>
          <a href={release.url} className="underline-offset-4 hover:underline">{release.version}</a> · {release.sizeMb} MB · Windows 10/11 · Free
        </>
      ) : (
        <>
          Windows 10/11 · Free · <a href={RELEASES} className="underline underline-offset-4">See all releases</a>
        </>
      )}
    </p>
  );
}

function Header() {
  const home = asset("");
  const { scrollY, scrollYProgress } = useScroll();
  const progress = useSpring(scrollYProgress, { stiffness: 200, damping: 30 });
  const [scrolled, setScrolled] = useState(false);
  useMotionValueEvent(scrollY, "change", (y) => setScrolled(y > 8));
  return (
    <header className={`sticky top-0 z-50 border-b backdrop-blur-xl transition-colors duration-300 ${scrolled ? "border-line bg-bg/80" : "border-transparent bg-bg/0"}`}>
      <motion.div aria-hidden className="absolute inset-x-0 bottom-[-1px] h-px origin-left bg-accent" style={{ scaleX: progress }} />
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-3">Skip to content</a>
      <nav aria-label="Main" className="mx-auto flex h-16 max-w-6xl items-center justify-between gap-4 px-4 sm:px-6">
        <a href={home} className="flex items-center gap-2.5 font-semibold">
          <img src={asset("logo.png")} alt="" width={32} height={32} className="size-8 rounded-lg" />
          Galliani
        </a>
        <div className="flex items-center gap-1 text-sm sm:gap-2">
          <a href={`${home}#features`} className="hidden rounded-lg px-3 py-2 text-muted hover:text-fg md:block">Features</a>
          <a href={`${home}#install`} className="hidden rounded-lg px-3 py-2 text-muted hover:text-fg md:block">Install</a>
          <a href={`${home}#faq`} className="hidden rounded-lg px-3 py-2 text-muted hover:text-fg md:block">FAQ</a>
          <a href={REPO} aria-label="Source code on GitHub" className="rounded-lg p-2 text-muted hover:text-fg">
            <GithubMark />
          </a>
          <DownloadButton size="md" />
        </div>
      </nav>
    </header>
  );
}

function Footer() {
  return (
    <footer className="border-t border-line">
      <div className="mx-auto flex max-w-6xl flex-col gap-4 px-4 py-10 text-sm text-muted sm:flex-row sm:items-center sm:justify-between sm:px-6">
        <p>© 2026 Galliani contributors. Free software under the GNU AGPL-3.0.</p>
        <div className="flex flex-wrap gap-x-5 gap-y-2">
          <a href={`${REPO}/blob/main/LICENSE`} className="hover:text-fg">License</a>
          <a href={REPO} className="hover:text-fg">Source code</a>
          <a href={asset("privacy.html")} className="hover:text-fg">Privacy</a>
        </div>
      </div>
    </footer>
  );
}

export function GithubMark({ className = "size-5" }: { className?: string }) {
  return (
    <svg aria-hidden viewBox="0 0 24 24" fill="currentColor" className={className}>
      <path d="M12 .5a11.5 11.5 0 0 0-3.64 22.41c.58.1.79-.25.79-.56v-2c-3.2.7-3.88-1.37-3.88-1.37-.52-1.33-1.28-1.69-1.28-1.69-1.05-.71.08-.7.08-.7 1.16.08 1.77 1.19 1.77 1.19 1.03 1.77 2.7 1.26 3.36.96.1-.75.4-1.26.73-1.55-2.55-.29-5.24-1.28-5.24-5.68 0-1.26.45-2.28 1.19-3.09-.12-.29-.52-1.46.11-3.05 0 0 .97-.31 3.17 1.18a11 11 0 0 1 5.77 0c2.2-1.49 3.17-1.18 3.17-1.18.63 1.59.23 2.76.11 3.05.74.81 1.19 1.83 1.19 3.09 0 4.41-2.69 5.38-5.25 5.67.41.36.78 1.06.78 2.14v3.17c0 .31.21.67.8.56A11.5 11.5 0 0 0 12 .5Z" />
    </svg>
  );
}
