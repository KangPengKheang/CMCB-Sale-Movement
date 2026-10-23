/** Poll without overlapping requests and catch up when the browser reconnects. */
export function startAutoRefresh(load: () => Promise<unknown>, intervalMs = 15000): () => void {
  let stopped = false;
  let inFlight = false;
  let timer: number | undefined;
  const run = async () => {
    if (stopped || inFlight) return;
    window.clearTimeout(timer);
    inFlight = true;
    try {
      await load();
    } catch (error) {
      console.debug("[Auto refresh] Retrying after a failed request:", error);
    } finally {
      inFlight = false;
      if (!stopped) timer = window.setTimeout(run, intervalMs);
    }
  };
  const resume = () => { if (!document.hidden) void run(); };
  window.addEventListener("focus", resume);
  window.addEventListener("online", resume);
  document.addEventListener("visibilitychange", resume);
  void run();
  return () => {
    stopped = true;
    window.clearTimeout(timer);
    window.removeEventListener("focus", resume);
    window.removeEventListener("online", resume);
    document.removeEventListener("visibilitychange", resume);
  };
}
