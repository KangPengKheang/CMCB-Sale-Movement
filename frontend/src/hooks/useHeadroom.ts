import { useState, useRef, useCallback } from "react";

/**
 * Headroom scroll behavior:
 * - Scrolling DOWN hides the element (-translate-y-full).
 * - Scrolling UP even slightly reveals the element (translate-y-0).
 * - At the top (scrollTop <= 20) it is always visible.
 */
export function useHeadroom() {
  const [isVisible, setIsVisible] = useState(true);
  const lastScrollTopRef = useRef(0);

  const handleScroll = useCallback((e: React.UIEvent<HTMLDivElement>) => {
    const current = e.currentTarget.scrollTop;
    const diff = current - lastScrollTopRef.current;

    // At the top of the page -> always visible
    if (current <= 20) {
      setIsVisible(true);
      lastScrollTopRef.current = current;
      return;
    }

    // Scrolled DOWN significantly -> hide
    if (diff > 12 && current > 60) {
      setIsVisible(false);
    }
    // Scrolled UP slightly -> reveal
    else if (diff < -8) {
      setIsVisible(true);
    }

    lastScrollTopRef.current = current;
  }, []);

  return { isVisible, handleScroll };
}
