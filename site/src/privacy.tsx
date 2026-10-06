import { StrictMode, type ReactNode } from "react";
import { createRoot } from "react-dom/client";
import { Page, Reveal } from "./components";
import "./index.css";

/* Spec 016 R10. Must match what the app does: update this page in the same change as any data behavior. */
function Block({ title, children }: { title: string; children: ReactNode }) {
  return (
    <Reveal className="mb-10">
      <h2 className="mb-3 text-xl font-semibold">{title}</h2>
      <div className="space-y-3 text-muted [&_b]:text-fg">{children}</div>
    </Reveal>
  );
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <Page>
      <article className="mx-auto max-w-3xl px-4 py-16 sm:px-6 sm:py-24">
        <Reveal className="mb-12">
          <h1 className="mb-4 text-4xl font-semibold tracking-tight">Privacy</h1>
          <p className="text-lg text-muted">The short version: Galliani runs on your computer, uses your own key, and the project collects nothing.</p>
        </Reveal>
        <Block title="What the app stores on your computer">
          <p><b>Your API keys</b> are saved in Windows Credential Manager, the operating system's secure store. They are never written to a plain file.</p>
          <p><b>The request log</b> (which model answered, tokens and cost) and <b>memory notes</b> you approved are saved in <code className="font-mono">%LOCALAPPDATA%\Galliani</code> on your PC. You can delete that folder at any time. Your <b>settings</b> are also kept only on your PC.</p>
        </Block>
        <Block title="What the app sends, and to whom">
          <p>Your messages, agent tasks, and the file contents an agent task needs are sent to <b>OpenRouter</b>, or to the provider you chose, using <b>your</b> key. That provider's privacy policy applies to that data.</p>
          <p>The app sends nothing to the Galliani project or anyone else.</p>
        </Block>
        <Block title="What the project collects">
          <p><b>Nothing.</b> There is no telemetry, analytics, crash reporting or account, in the app or on this website. This site sets no cookies. To show the latest version number, your browser asks GitHub's public API for the latest release; GitHub's privacy policy applies to that request.</p>
        </Block>
        <Block title="Questions">
          <p>Galliani is open source, so you can check all of this in the code. Questions or concerns: <a className="text-fg underline underline-offset-4" href="https://github.com/Jotadev-bug/Galliani/issues">open an issue on GitHub</a>.</p>
        </Block>
      </article>
    </Page>
  </StrictMode>,
);
