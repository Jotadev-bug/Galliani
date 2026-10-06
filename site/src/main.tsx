import { StrictMode, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import { AnimatePresence, motion, useScroll } from "motion/react";
import {
  ArrowRight, Bot, ChevronDown, Coins, FolderLock, Gauge, KeyRound, Laptop, MessageSquare, Play, ShieldCheck, Terminal,
} from "lucide-react";
import { Card, CopyCommand, DownloadButton, GithubMark, Page, Reveal, Section, VersionLine, asset } from "./components";
import { AgentSteps, CostBars, HeroDemo } from "./demos";
import { RELEASES, REPO, useLatestRelease } from "./release";
import "./index.css";

const EASE = [0.22, 1, 0.36, 1] as const;
const rise = (delay: number) => ({
  initial: { opacity: 0, y: 20 },
  animate: { opacity: 1, y: 0 },
  transition: { duration: 0.7, delay, ease: EASE },
});

function Hero() {
  const release = useLatestRelease();
  return (
    <section className="relative overflow-hidden">
      <div aria-hidden className="dot-grid pointer-events-none absolute inset-0" />
      <motion.div
        aria-hidden
        className="pointer-events-none absolute left-1/2 top-[-25%] size-[760px] -translate-x-1/2 rounded-full blur-3xl"
        style={{ background: "radial-gradient(circle, var(--glow), transparent 65%)" }}
        animate={{ scale: [1, 1.12, 1], opacity: [0.8, 1, 0.8] }}
        transition={{ duration: 8, repeat: Infinity, ease: "easeInOut" }}
      />
      <div className="relative mx-auto grid max-w-6xl grid-cols-1 items-center gap-14 px-4 pb-16 pt-14 sm:px-6 sm:pt-20 lg:grid-cols-[1.15fr_1fr]">
        <div className="flex flex-col items-start gap-6">
          <motion.a
            {...rise(0)}
            href={release?.url ?? RELEASES}
            className="group inline-flex items-center gap-2 rounded-full border border-line-strong bg-surface/60 py-1 pl-1 pr-3 text-sm backdrop-blur hover:bg-surface"
          >
            <span className="rounded-full bg-primary px-2 py-0.5 text-xs font-semibold text-on-primary">New</span>
            <span className="text-muted group-hover:text-fg">{release ? `${release.version} is out` : "First release is out"}</span>
            <ArrowRight aria-hidden className="size-3.5 text-muted transition-transform group-hover:translate-x-0.5" />
          </motion.a>
          <motion.h1 {...rise(0.08)} className="text-[2.6rem] font-semibold leading-[1.05] tracking-tight sm:text-6xl lg:text-[4.1rem]">
            Picks the right model for every message, <span className="text-shine">and shows what you saved.</span>
          </motion.h1>
          <motion.p {...rise(0.16)} className="max-w-xl text-lg text-muted">
            Galliani is a free desktop app for chatting with AI and running agent tasks. Each message goes to the cheapest model that can handle it, using your own key.
          </motion.p>
          <motion.div {...rise(0.24)} className="flex flex-col items-start gap-3">
            <div className="flex flex-wrap items-center gap-3">
              <DownloadButton />
              <a href={REPO} className="inline-flex h-13 items-center gap-2 rounded-xl border border-line-strong px-5 font-medium hover:bg-surface-2">
                <GithubMark className="size-4" /> Source
              </a>
            </div>
            <VersionLine release={release} />
          </motion.div>
        </div>
        <motion.div
          className="flex justify-center lg:justify-end"
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.9, delay: 0.3, ease: EASE }}
        >
          <HeroDemo />
        </motion.div>
      </div>
    </section>
  );
}

/* The models in config/models.yaml that the router picks between. Names only, no vendor logos. */
const ROUTED_MODELS = [
  "Gemini 3.1 Flash Lite", "Claude Haiku 4.5", "GPT-5.4 mini", "Gemini 3.8 Flash", "Claude Sonnet 5.5", "Claude Opus 5.5", "Claude Fable 5.1",
];

function ModelMarquee() {
  const row = (hidden: boolean) => (
    <ul aria-hidden={hidden || undefined} className="flex shrink-0 items-center gap-3 pr-3">
      {ROUTED_MODELS.map((m) => (
        <li key={m} className="whitespace-nowrap rounded-full border border-line bg-surface px-4 py-1.5 text-sm text-muted">{m}</li>
      ))}
    </ul>
  );
  return (
    <section aria-label="Models Galliani routes between" className="border-y border-line py-6">
      <p className="mb-4 px-4 text-center text-xs font-medium uppercase tracking-widest text-muted">Routes between models through OpenRouter</p>
      <div className="marquee-mask flex overflow-hidden">
        <div className="marquee flex">
          {row(false)}
          {row(true)}
        </div>
      </div>
    </section>
  );
}

const CHAT_ROWS = [
  { q: "Quick fact", tier: "Cheap", w: "w-1/5" },
  { q: "Draft an email", tier: "Cheap", w: "w-2/5" },
  { q: "Debug a race condition", tier: "Frontier", w: "w-full" },
];

const EXTRAS = [
  { icon: KeyRound, title: "Your own key", body: "Pay the provider directly. No subscription, no markup." },
  { icon: Gauge, title: "Spending cap", body: "Agent tasks stop at a budget unless you approve more." },
  { icon: Laptop, title: "Runs locally", body: "A single Windows app. Nothing to host, no account." },
];

function Features() {
  return (
    <Section id="features" kicker="What it does" title="Smart routing for chat and agents.">
      <div className="grid grid-cols-1 gap-5 md:grid-cols-2 lg:grid-cols-3">
        <Reveal className="md:row-span-2">
          <Card>
            <Bot aria-hidden className="mb-5 size-6 text-accent" />
            <h3 className="mb-2 text-lg font-semibold">Agent</h3>
            <p className="text-muted">Give it a task and a folder. It plans, uses tools inside that folder, asks before writing any file, and checks the result before it says it's done.</p>
            <AgentSteps />
          </Card>
        </Reveal>
        <Reveal delay={0.08}>
          <Card>
            <MessageSquare aria-hidden className="mb-5 size-6 text-accent" />
            <h3 className="mb-2 text-lg font-semibold">Chat</h3>
            <p className="text-muted">Every message goes to the cheapest model that can handle it well. Easy questions get fast, cheap models; hard ones get a frontier model.</p>
            <div aria-hidden className="mt-6 space-y-3 text-sm">
              {CHAT_ROWS.map((r) => (
                <div key={r.q}>
                  <div className="mb-1.5 flex justify-between gap-3 text-xs">
                    <span className="text-muted">{r.q}</span>
                    <span className="text-muted">{r.tier}</span>
                  </div>
                  <div className="h-1.5 rounded-full bg-surface-2">
                    <motion.div
                      className={`h-full rounded-full bg-accent ${r.w}`}
                      style={{ originX: 0 }}
                      initial={{ scaleX: 0 }}
                      whileInView={{ scaleX: 1 }}
                      viewport={{ once: true }}
                      transition={{ duration: 0.9, ease: EASE }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </Card>
        </Reveal>
        <Reveal delay={0.16}>
          <Card>
            <Coins aria-hidden className="mb-5 size-6 text-accent" />
            <h3 className="mb-2 text-lg font-semibold">Cost</h3>
            <p className="text-muted">Each answer shows the model that wrote it, what it cost, and what you saved compared with always using the top model.</p>
            <CostBars />
          </Card>
        </Reveal>
        <Reveal delay={0.24} className="md:col-span-2 lg:col-span-2">
          <Card>
            <div className="grid gap-6 sm:grid-cols-3">
              {EXTRAS.map((x) => (
                <div key={x.title}>
                  <x.icon aria-hidden className="mb-3 size-5 text-accent" />
                  <h3 className="mb-1 font-semibold">{x.title}</h3>
                  <p className="text-sm text-muted">{x.body}</p>
                </div>
              ))}
            </div>
          </Card>
        </Reveal>
      </div>
    </Section>
  );
}

function Video() {
  const ref = useRef<HTMLVideoElement>(null);
  const [playing, setPlaying] = useState(false);
  const play = () => {
    setPlaying(true);
    requestAnimationFrame(() => {
      ref.current?.play();
      ref.current?.focus();
    });
  };
  return (
    <Section id="video" kicker="See it in 28 seconds" title="One prompt, the right model, the cost on screen.">
      <div className="grid grid-cols-1 items-center gap-8 lg:grid-cols-[1.7fr_1fr]">
        <Reveal>
          <div className="relative">
            <div aria-hidden className="absolute -inset-4 rounded-[2rem] bg-[radial-gradient(closest-side,var(--glow),transparent)] blur-2xl" />
            <div className="relative overflow-hidden rounded-2xl border border-line-strong bg-surface shadow-2xl shadow-black/40">
              <video
                ref={ref}
                className="aspect-video w-full"
                controls={playing}
                muted
                playsInline
                preload="none"
                poster={asset("galliani-showcase-poster.webp")}
                aria-describedby="video-summary"
              >
                <source src={asset("galliani-showcase.mp4")} type="video/mp4" />
              </video>
              {!playing && (
                <button
                  type="button"
                  onClick={play}
                  aria-label="Play the 28-second showcase video"
                  className="absolute inset-0 grid place-items-center bg-black/10 transition-colors hover:bg-black/25"
                >
                  <motion.span
                    whileHover={{ scale: 1.08 }}
                    whileTap={{ scale: 0.95 }}
                    className="grid size-18 place-items-center rounded-full bg-primary/90 text-on-primary shadow-2xl backdrop-blur"
                  >
                    <Play aria-hidden className="ml-1 size-7 fill-current" />
                  </motion.span>
                </button>
              )}
            </div>
          </div>
        </Reveal>
        <Reveal delay={0.1}>
          <p id="video-summary" className="text-muted">
            <span className="font-medium text-fg">What the video shows:</span> a coding prompt is typed into Galliani. The router sends it to Claude Sonnet 5.5, the model name and the cost stay visible while it answers, and at the end Galliani shows how much was saved compared with sending the same prompt to Claude Opus 5.5.
          </p>
        </Reveal>
      </div>
    </Section>
  );
}

/* A drawn stand-in for the SmartScreen dialog, so the step is recognizable without a screenshot. */
function SmartScreenIllustration() {
  return (
    <div role="img" aria-label="Windows SmartScreen dialog: click More info, then Run anyway" className="mt-4 max-w-sm overflow-hidden rounded-xl border border-line text-left text-xs shadow-lg">
      <div className="bg-[#0b5cad] p-4 text-white">
        <p className="mb-2 text-base font-semibold">Windows protected your PC</p>
        <p className="opacity-90">Microsoft Defender SmartScreen prevented an unrecognized app from starting.</p>
        <p className="mt-2 w-fit rounded px-1 underline ring-2 ring-white/70">More info</p>
        <div className="mt-4 flex justify-end gap-2">
          <span className="rounded border border-white px-3 py-1 font-medium ring-2 ring-white/70 ring-offset-2 ring-offset-[#0b5cad]">Run anyway</span>
          <span className="rounded border border-white/40 px-3 py-1 opacity-80">Don't run</span>
        </div>
      </div>
    </div>
  );
}

const STEPS = [
  { title: "Download", body: <>Get <code className="font-mono">Galliani.exe</code> with the button above. It's a single file, no installer.</> },
  {
    title: "Get past SmartScreen once",
    body: (
      <>
        The app isn't code-signed yet, so Windows may warn on first launch. Click <b className="text-fg">More info</b>, then <b className="text-fg">Run anyway</b>. You only do this once.
        <SmartScreenIllustration />
      </>
    ),
  },
  {
    title: "Get an OpenRouter key",
    body: <>Create a free account and a key at <a className="text-fg underline underline-offset-4" href="https://openrouter.ai/keys">openrouter.ai/keys</a>, and add a few dollars of credit.</>,
  },
  { title: "Paste it in", body: <>Paste the key when Galliani asks. It's saved in Windows Credential Manager, and you're ready to go.</> },
];

function Install() {
  const ref = useRef<HTMLOListElement>(null);
  const { scrollYProgress } = useScroll({ target: ref, offset: ["start 75%", "end 60%"] });
  return (
    <Section id="install" kicker="Install" title="Up and running in two minutes.">
      <div className="grid grid-cols-1 gap-10 lg:grid-cols-[1.4fr_1fr]">
        <ol ref={ref} className="relative space-y-10">
          <div aria-hidden className="absolute bottom-2 left-[17px] top-2 w-px bg-line" />
          <motion.div aria-hidden className="absolute bottom-2 left-[17px] top-2 w-px origin-top bg-accent" style={{ scaleY: scrollYProgress }} />
          {STEPS.map((s, i) => (
            <li key={s.title} className="relative flex gap-5">
              <span className="relative grid size-9 shrink-0 place-items-center rounded-full border border-line-strong bg-bg text-sm font-semibold">{i + 1}</span>
              <Reveal delay={0.05} className="min-w-0 pt-1.5">
                <h3 className="mb-2 text-lg font-semibold">{s.title}</h3>
                <div className="text-muted">{s.body}</div>
              </Reveal>
            </li>
          ))}
        </ol>
        <Reveal className="lg:pt-2">
          <Card>
            <p className="mb-3 flex items-center gap-2 font-medium"><Terminal aria-hidden className="size-4" /> Check the download (optional)</p>
            <p className="mb-4 text-sm text-muted">In PowerShell, compare the result with <code className="font-mono">Galliani.exe.sha256</code> on the release page.</p>
            <CopyCommand command="(Get-FileHash Galliani.exe -Algorithm SHA256).Hash" />
          </Card>
        </Reveal>
      </div>
    </Section>
  );
}

const PRIVACY = [
  { icon: KeyRound, title: "Your key stays yours", body: "Stored in Windows Credential Manager and sent only to the AI provider you use." },
  { icon: FolderLock, title: "Logs stay on your PC", body: "The request log, memory and settings live in your user folder. Nothing is uploaded." },
  { icon: ShieldCheck, title: "No telemetry", body: "No analytics, no tracking, no account. The project collects nothing." },
];

function Privacy() {
  return (
    <Section id="privacy" kicker="Privacy" title="Nothing leaves your machine except your prompts.">
      <div className="grid grid-cols-1 gap-5 md:grid-cols-3">
        {PRIVACY.map((p, i) => (
          <Reveal key={p.title} delay={i * 0.08}>
            <Card>
              <p.icon aria-hidden className="mb-5 size-6 text-accent" />
              <h3 className="mb-2 text-lg font-semibold">{p.title}</h3>
              <p className="text-muted">{p.body}</p>
            </Card>
          </Reveal>
        ))}
      </div>
      <Reveal className="mt-6">
        <a href={asset("privacy.html")} className="group inline-flex items-center gap-1.5 text-sm underline underline-offset-4">
          Read the full privacy page <ArrowRight aria-hidden className="size-3.5 transition-transform group-hover:translate-x-0.5" />
        </a>
      </Reveal>
    </Section>
  );
}

function OpenSource() {
  return (
    <Section id="open-source" kicker="Open source" title="Free software, built in the open.">
      <Reveal>
        <Card>
          <div className="flex flex-col gap-5 sm:flex-row sm:items-center sm:justify-between">
            <p className="max-w-2xl text-muted">
              Galliani is licensed under the GNU AGPL-3.0. Every release is built from the tagged source by a public GitHub workflow. Found a bug or have an idea? Open an issue on GitHub.
            </p>
            <div className="flex shrink-0 flex-wrap gap-3">
              <a href={REPO} className="inline-flex h-10 items-center gap-2 rounded-xl border border-line-strong px-4 text-sm font-medium hover:bg-surface-2">
                <GithubMark className="size-4" /> View source
              </a>
              <a href={`${REPO}/issues`} className="inline-flex h-10 items-center rounded-xl border border-line-strong px-4 text-sm font-medium hover:bg-surface-2">
                Report an issue
              </a>
            </div>
          </div>
        </Card>
      </Reveal>
    </Section>
  );
}

const FAQ = [
  { q: "What does a typical task cost?", a: "You pay the provider directly with your own key. Most chat messages cost a fraction of a cent, and a typical agent task costs a few cents. Galliani shows the exact cost of every answer." },
  { q: "Why does Windows warn me?", a: "Galliani isn't code-signed yet, and SmartScreen warns about new apps it hasn't seen often. Click More info, then Run anyway. You can verify the file with its SHA-256 checksum. Never turn off SmartScreen or your antivirus for it." },
  { q: "Is there a Mac or Linux version?", a: "Not yet. The desktop app is Windows only for now." },
  { q: "Which models does it use?", a: "Models from Google (Gemini), Anthropic (Claude) and OpenAI (GPT) through OpenRouter, from cheap and fast to frontier. The router picks one per message." },
  { q: "What can the agent touch?", a: "Only the folder you choose for the task. It asks before writing or changing any file, unless you turn on accept-edits mode. Its file tools are limited to that folder." },
];

function Faq() {
  const [open, setOpen] = useState<number | null>(0);
  return (
    <Section id="faq" kicker="FAQ" title="Questions, answered.">
      <Reveal>
        <div className="divide-y divide-line rounded-2xl border border-line bg-surface">
          {FAQ.map((item, i) => {
            const isOpen = open === i;
            return (
              <div key={item.q}>
                <h3>
                  <button
                    type="button"
                    aria-expanded={isOpen}
                    aria-controls={`faq-${i}`}
                    onClick={() => setOpen(isOpen ? null : i)}
                    className="flex w-full items-center justify-between gap-4 px-6 py-5 text-left font-medium hover:text-fg"
                  >
                    {item.q}
                    <motion.span animate={{ rotate: isOpen ? 180 : 0 }}><ChevronDown aria-hidden className="size-5 text-muted" /></motion.span>
                  </button>
                </h3>
                <AnimatePresence initial={false}>
                  {isOpen && (
                    <motion.div
                      id={`faq-${i}`}
                      initial={{ height: 0, opacity: 0 }}
                      animate={{ height: "auto", opacity: 1 }}
                      exit={{ height: 0, opacity: 0 }}
                      transition={{ duration: 0.25 }}
                      className="overflow-hidden"
                    >
                      <p className="px-6 pb-5 text-muted">{item.a}</p>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            );
          })}
        </div>
      </Reveal>
    </Section>
  );
}

function FinalCta() {
  const release = useLatestRelease();
  return (
    <section className="mx-auto max-w-6xl px-4 pb-24 sm:px-6">
      <Reveal>
        <div className="relative overflow-hidden rounded-3xl border border-line-strong bg-surface px-6 py-16 text-center">
          <div aria-hidden className="dot-grid absolute inset-0" />
          <div aria-hidden className="absolute left-1/2 top-0 size-[520px] -translate-x-1/2 -translate-y-1/2 rounded-full bg-[radial-gradient(closest-side,var(--glow),transparent)]" />
          <div className="relative flex flex-col items-center gap-5">
            <img src={asset("logo.png")} alt="" width={56} height={56} className="size-14 rounded-2xl shadow-xl shadow-black/30" />
            <h2 className="max-w-xl text-3xl font-semibold tracking-tight sm:text-4xl">Stop overpaying for easy questions.</h2>
            <p className="max-w-md text-muted">Free, open source, and yours to run. Bring your own key and see what every answer costs.</p>
            <DownloadButton />
            <VersionLine release={release} />
          </div>
        </div>
      </Reveal>
    </section>
  );
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <Page>
      <Hero />
      <ModelMarquee />
      <Features />
      <Video />
      <Install />
      <Privacy />
      <OpenSource />
      <Faq />
      <FinalCta />
    </Page>
  </StrictMode>,
);

// Links like privacy.html -> index.html#faq arrive before React has rendered the target, so scroll once it exists.
if (location.hash) requestAnimationFrame(() => document.getElementById(location.hash.slice(1))?.scrollIntoView());
