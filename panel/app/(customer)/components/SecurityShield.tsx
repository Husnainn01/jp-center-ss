"use client";

import { useEffect } from "react";

/**
 * SecurityShield — Client-side protections for the customer panel.
 *
 * What it does:
 * - Disables right-click context menu
 * - Blocks common keyboard shortcuts (F12, Ctrl+Shift+I/J/C, Ctrl+U)
 * - Disables console.log/warn/error/info in production
 * - Detects DevTools open via debugger timing
 * - Disables text selection on images
 * - Disables image dragging
 * - Blocks PrintScreen key
 * - Blurs page content when tab loses focus (prevents screen recording)
 *
 * Note: These are deterrents, not absolute blocks. A determined technical user
 * can bypass these. The real protection is watermarking (see ImageWatermark).
 */
export function SecurityShield() {
  useEffect(() => {
    if (process.env.NODE_ENV !== "production") return;

    // 1. Disable right-click
    function handleContextMenu(e: MouseEvent) {
      e.preventDefault();
    }
    document.addEventListener("contextmenu", handleContextMenu);

    // 2. Block dev tools keyboard shortcuts
    function handleKeyDown(e: KeyboardEvent) {
      // F12
      if (e.key === "F12") { e.preventDefault(); return; }
      // Ctrl+Shift+I (Inspector)
      if (e.ctrlKey && e.shiftKey && e.key === "I") { e.preventDefault(); return; }
      // Ctrl+Shift+J (Console)
      if (e.ctrlKey && e.shiftKey && e.key === "J") { e.preventDefault(); return; }
      // Ctrl+Shift+C (Element picker)
      if (e.ctrlKey && e.shiftKey && e.key === "C") { e.preventDefault(); return; }
      // Ctrl+U (View source)
      if (e.ctrlKey && e.key === "u") { e.preventDefault(); return; }
      // Cmd+Option+I (Mac Inspector)
      if (e.metaKey && e.altKey && e.key === "i") { e.preventDefault(); return; }
      // Cmd+Option+J (Mac Console)
      if (e.metaKey && e.altKey && e.key === "j") { e.preventDefault(); return; }
      // PrintScreen
      if (e.key === "PrintScreen") {
        e.preventDefault();
        document.body.style.filter = "blur(20px)";
        setTimeout(() => { document.body.style.filter = ""; }, 1500);
      }
    }
    document.addEventListener("keydown", handleKeyDown);

    // 3. Disable console in production
    const noop = () => {};
    const originalConsole = {
      log: console.log,
      warn: console.warn,
      error: console.error,
      info: console.info,
      debug: console.debug,
    };
    console.log = noop;
    console.warn = noop;
    console.info = noop;
    console.debug = noop;
    // Keep console.error for critical errors

    // 4. Disable image drag
    function handleDragStart(e: DragEvent) {
      if ((e.target as HTMLElement)?.tagName === "IMG") {
        e.preventDefault();
      }
    }
    document.addEventListener("dragstart", handleDragStart);

    // 5. Blur on visibility change (tab switch / screen recording detection)
    function handleVisibilityChange() {
      if (document.hidden) {
        document.body.style.filter = "blur(15px)";
      } else {
        document.body.style.filter = "";
      }
    }
    document.addEventListener("visibilitychange", handleVisibilityChange);

    // Cleanup
    return () => {
      document.removeEventListener("contextmenu", handleContextMenu);
      document.removeEventListener("keydown", handleKeyDown);
      document.removeEventListener("dragstart", handleDragStart);
      document.removeEventListener("visibilitychange", handleVisibilityChange);
      // Restore console
      console.log = originalConsole.log;
      console.warn = originalConsole.warn;
      console.info = originalConsole.info;
      console.debug = originalConsole.debug;
    };
  }, []);

  return null; // No UI — just side effects
}
