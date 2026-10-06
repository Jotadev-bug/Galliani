import { useEffect, useState } from "react";

export const REPO = "https://github.com/Jotadev-bug/Galliani";
export const RELEASES = `${REPO}/releases`;
// The button never depends on the API (R3, R8): GitHub resolves "latest" to the newest stable release.
export const DOWNLOAD = `${RELEASES}/latest/download/Galliani.exe`;

export type Release = { version: string; sizeMb: string; url: string };

// One request per page load, shared by every component that shows the version (the API allows 60 an hour).
let pending: Promise<Release | null> | null = null;

function fetchLatest(): Promise<Release | null> {
  pending ??= fetch("https://api.github.com/repos/Jotadev-bug/Galliani/releases/latest")
    .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
    .then((data) => {
      const exe = data.assets?.find((a: { name: string }) => a.name === "Galliani.exe");
      if (typeof data.tag_name !== "string" || !exe?.size) return null;
      return { version: data.tag_name, sizeMb: (exe.size / 1048576).toFixed(0), url: data.html_url };
    })
    .catch(() => null);
  return pending;
}

/** Version and size of the latest release, or null while loading or when the API is unavailable (R8). */
export function useLatestRelease(): Release | null {
  const [release, setRelease] = useState<Release | null>(null);
  useEffect(() => {
    let live = true;
    fetchLatest().then((r) => live && setRelease(r));
    return () => {
      live = false;
    };
  }, []);
  return release;
}
