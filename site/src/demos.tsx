import { useEffect, useRef, useState } from "react";
import { animate, motion, useInView, useMotionValue, useReducedMotion, useTransform } from "motion/react";
import { Check, FileText, FolderOpen, ListChecks, ShieldCheck, Sparkles } from "lucide-react";
import { asset } from "./components";

/*
 * Illustrative demos. The numbers are examples, labelled as such on the page;
 * the app shows the real model and cost for every answer.
 */

const MODELS = [
  { name: "Gemini 3.1 Flash Lite", tier: "Cheap" },
  { name: "GPT-5.4 mini", tier: "Cheap" },
  { name: "Claude Sonnet 5.5", tier: "Mid" },
  { name: "Claude Opus 5.5", tier: "Frontier" },
];

const EXAMPLES = [
  { prompt: "What's the capital of Australia?", pick: 0, answer: "Canberra.", cost: 0.00004, saved: 99 },
  { prompt: "Refactor this function to use async/await", pick: 2, answer: "Here's the refactored version…", cost: 0.012, saved: 80 },
  { prompt: "Summarize this email in two lines", pick: 1, answer: "They need the report by Friday…", cost: 0.0003, saved: 97 },
];

type Phase = "typing" | "routing" | "answer";

/** Counts up to `to` once mounted (instantly when reduced motion is on). */
function CountUp({ to, decimals = 0, prefix = "", suffix = "" }: { to: number; decimals?: number; prefix?: string; suffix?: string }) {
  const reduce = useReducedMotion();
  const value = useMotionValue(reduce ? to : 0);
  const text = useTransform(value, (v) => `${prefix}${v.toFixed(decimals)}${suffix}`);
  useEffect(() => {
    if (reduce) return value.set(to);
    const controls = animate(value, to, { duration: 0.9, ease: "easeOut" });
    return () => controls.stop();
  }, [to, reduce, value]);
  return <motion.span>{text}</motion.span>;
}

/** The hero's app window: a prompt is typed, the router scans the models, picks one, and shows cost and savings. */
export function HeroDemo() {
  const reduce = useReducedMotion();
  const [i, setI] = useState(0);
  const [phase, setPhase] = useState<Phase>(reduce ? "answer" : "typing");
  const [typed, setTyped] = useState(0);
  const [scan, setScan] = useState(0);
  const ex = EXAMPLES[i];

  useEffect(() => {
    let cancelled = false;
    const timers: number[] = [];
    const at = (ms: number, fn: () => void) => timers.push(window.setTimeout(() => !cancelled && fn(), ms));
    if (reduce) {
      setPhase("answer");
      setTyped(ex.prompt.length);
      at(5000, () => setI((n) => (n + 1) % EXAMPLES.length));
    } else {
      setPhase("typing");
      setTyped(0);
      setScan(0);
      const typeMs = 28;
      for (let c = 1; c <= ex.prompt.length; c++) at(c * typeMs, () => setTyped(c));
      const routeStart = ex.prompt.length * typeMs + 250;
      at(routeStart, () => setPhase("routing"));
      // Sweep every model once, then come back to the pick.
      const sweep = [...MODELS.keys(), ...MODELS.keys()].slice(0, MODELS.length + ex.pick + 1);
      sweep.forEach((m, k) => at(routeStart + k * 170, () => setScan(m)));
      const answerAt = routeStart + sweep.length * 170 + 200;
      at(answerAt, () => setPhase("answer"));
      at(answerAt + 3200, () => setI((n) => (n + 1) % EXAMPLES.length));
    }
    return () => {
      cancelled = true;
      timers.forEach(clearTimeout);
    };
  }, [i, reduce, ex.prompt.length, ex.pick]);

  const picked = phase === "answer";

  return (
    <div className="relative w-full max-w-md">
      <div aria-hidden className="absolute -inset-6 rounded-[2rem] bg-[radial-gradient(closest-side,var(--glow),transparent)] blur-2xl" />
      <div className="relative overflow-hidden rounded-2xl border border-line-strong bg-surface shadow-2xl shadow-black/40" role="img"
        aria-label={`Example: "${ex.prompt}" is routed to ${MODELS[ex.pick].name}, costing $${ex.cost} and saving ${ex.saved}% compared with the top model.`}>
        {/* Title bar */}
        <div className="flex items-center gap-2 border-b border-line bg-surface-2 px-4 py-2.5">
          <img src={asset("favicon.png")} alt="" width={16} height={16} className="size-4 rounded" />
          <span className="text-xs font-medium">Galliani</span>
          <span className="ml-auto text-[10px] font-medium uppercase tracking-widest text-muted">Example</span>
        </div>

        <div aria-hidden className="space-y-4 p-4">
          {/* Prompt */}
          <div className="ml-auto w-fit max-w-[90%] rounded-2xl rounded-br-md bg-primary px-3.5 py-2 text-sm text-on-primary">
            {ex.prompt.slice(0, typed)}
            {phase === "typing" && <span className="ml-0.5 inline-block h-3.5 w-px translate-y-0.5 animate-pulse bg-on-primary" />}
          </div>

          {/* Router */}
          <div className="rounded-xl border border-line bg-bg/40 p-3">
            <p className="mb-2 flex items-center gap-1.5 text-[11px] font-medium uppercase tracking-widest text-muted">
              <Sparkles className="size-3" /> {picked ? "Routed" : phase === "routing" ? "Routing…" : "Router"}
            </p>
            <ul className="space-y-1">
              {MODELS.map((m, k) => {
                const active = (phase === "routing" && scan === k) || (picked && ex.pick === k);
                return (
                  <li key={m.name} className="relative flex items-center gap-2 rounded-lg px-2.5 py-1.5 text-xs">
                    {active && (
                      <motion.span layoutId="router-highlight" className="absolute inset-0 rounded-lg border border-line-strong bg-surface-2"
                        transition={{ type: "spring", stiffness: 500, damping: 35 }} />
                    )}
                    <span className={`relative font-medium ${active ? "text-fg" : "text-muted"}`}>{m.name}</span>
                    <span className="relative ml-auto text-muted">{m.tier}</span>
                    {picked && ex.pick === k && (
                      <motion.span initial={{ scale: 0 }} animate={{ scale: 1 }} className="relative text-good"><Check className="size-3.5" /></motion.span>
                    )}
                  </li>
                );
              })}
            </ul>
          </div>

          {/* Answer and cost */}
          <div className="min-h-[76px]">
            {picked && (
                <motion.div key={i} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }}>
                  <p className="w-fit max-w-[90%] rounded-2xl rounded-bl-md bg-surface-2 px-3.5 py-2 text-sm">{ex.answer}</p>
                  <div className="mt-2.5 flex items-center gap-3 text-xs">
                    <span className="font-mono text-muted"><CountUp to={ex.cost} decimals={ex.cost < 0.001 ? 5 : 3} prefix="$" /></span>
                    <span className="rounded-full bg-good/10 px-2 py-0.5 font-medium text-good">
                      Saved <CountUp to={ex.saved} suffix="%" />
                    </span>
                  </div>
                </motion.div>
              )}
          </div>
        </div>
      </div>
    </div>
  );
}

const AGENT_STEPS = [
  { icon: ListChecks, label: "Plan", detail: "3 steps" },
  { icon: FolderOpen, label: "Read files", detail: "in your folder" },
  { icon: FileText, label: "Ask to write", detail: "summary.md" },
  { icon: ShieldCheck, label: "Verify", detail: "result checked" },
];

/** The agent's stepper, ticking through plan, tools, approval and verification while in view. */
export function AgentSteps() {
  const reduce = useReducedMotion();
  const ref = useRef<HTMLOListElement>(null);
  const inView = useInView(ref, { amount: 0.6 });
  const [step, setStep] = useState(reduce ? AGENT_STEPS.length : 0);
  useEffect(() => {
    if (reduce || !inView) return;
    const t = setInterval(() => setStep((s) => (s >= AGENT_STEPS.length + 1 ? 0 : s + 1)), 900);
    return () => clearInterval(t);
  }, [inView, reduce]);
  return (
    <ol ref={ref} aria-hidden className="mt-6 space-y-2">
      {AGENT_STEPS.map((s, k) => {
        const done = step > k;
        const current = step === k;
        return (
          <li key={s.label} className={`flex items-center gap-3 rounded-lg border px-3 py-2 text-sm transition-colors duration-300 ${current ? "border-line-strong bg-surface-2" : "border-transparent"}`}>
            <span className={`grid size-6 place-items-center rounded-full border transition-colors duration-300 ${done ? "border-good/40 bg-good/10 text-good" : "border-line-strong text-muted"}`}>
              {done ? <Check className="size-3.5" /> : <s.icon className="size-3.5" />}
            </span>
            <span className={done || current ? "text-fg" : "text-muted"}>{s.label}</span>
            <span className="ml-auto text-xs text-muted">{s.detail}</span>
          </li>
        );
      })}
    </ol>
  );
}

/** Bars comparing a month of routed messages with always using the top model. */
export function CostBars() {
  const bars = [
    { label: "Always the top model", value: 100, cls: "bg-line-strong" },
    { label: "Galliani", value: 22, cls: "bg-accent" },
  ];
  return (
    <div aria-hidden className="mt-6 space-y-4">
      {bars.map((b, k) => (
        <div key={b.label}>
          <div className="mb-1.5 flex justify-between text-xs text-muted">
            <span>{b.label}</span>
            <span className="font-mono">{b.value}%</span>
          </div>
          <div className="h-2.5 overflow-hidden rounded-full bg-surface-2">
            <motion.div
              className={`h-full rounded-full ${b.cls}`}
              initial={{ width: 0 }}
              whileInView={{ width: `${b.value}%` }}
              viewport={{ once: true }}
              transition={{ duration: 1.1, delay: 0.2 + k * 0.25, ease: [0.22, 1, 0.36, 1] }}
            />
          </div>
        </div>
      ))}
      <p className="text-xs text-muted">Illustrative mix of everyday messages.</p>
    </div>
  );
}
