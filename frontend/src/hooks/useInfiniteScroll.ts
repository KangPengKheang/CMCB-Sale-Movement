import { useEffect, useRef } from "react";

/**
 * Drives "load the next page as you approach the bottom" without scroll listeners.
 *
 * Attach the returned ref to a sentinel element rendered after the last row.
 * When that sentinel comes within `rootMargin` of the viewport, `onLoadMore`
 * fires once; it re-arms only after the call settles, so a fast scroll cannot
 * fire overlapping requests.
 */
export function useInfiniteScroll({
  onLoadMore,
  hasMore,
  isLoading,
  rootMargin = "600px",
}: {
  onLoadMore: () => void;
  hasMore: boolean;
  isLoading: boolean;
  rootMargin?: string;
}) {
  const sentinelRef = useRef<HTMLDivElement | null>(null);
  // Read the latest callback without re-creating the observer on every render
  const onLoadMoreRef = useRef(onLoadMore);
  onLoadMoreRef.current = onLoadMore;

  useEffect(() => {
    const el = sentinelRef.current;
    if (!el) return;
    if (!hasMore || isLoading) return;

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting)) {
          onLoadMoreRef.current();
        }
      },
      { rootMargin }
    );

    observer.observe(el);
    return () => observer.disconnect();
  }, [hasMore, isLoading, rootMargin]);

  return sentinelRef;
}
