import { useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { API_BASE, getAccessToken } from "./api";

export function useRealtime(enabled: boolean) {
  const queryClient = useQueryClient();
  useEffect(() => {
    if (!enabled) return;
    const controller = new AbortController();
    let timer: number | undefined;
    let cursor: string | null = null;
    const invalidate = () => {
      for (const key of ["dashboard", "work-orders", "work-order", "attachments", "activity"])
        void queryClient.invalidateQueries({ queryKey: [key] });
    };
    const connect = async () => {
      try {
        const token = getAccessToken();
        if (!token) return;
        const headers: Record<string, string> = { Accept: "text/event-stream", Authorization: `Bearer ${token}` };
        if (cursor) headers["Last-Event-ID"] = cursor;
        const response = await fetch(`${API_BASE}/realtime/events`, { headers, credentials: "include", signal: controller.signal });
        if (!response.ok || !response.body) throw new Error("Realtime unavailable");
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";
        while (!controller.signal.aborted) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          const blocks = buffer.split("\n\n");
          buffer = blocks.pop() ?? "";
          for (const block of blocks) {
            cursor = block.match(/^id:\s*(.+)$/m)?.[1] ?? cursor;
            const event = block.match(/^event:\s*(.+)$/m)?.[1];
            if (event && event !== "connected") invalidate();
          }
        }
      } catch {
        if (!controller.signal.aborted) timer = window.setTimeout(connect, 3000);
      }
    };
    void connect();
    return () => { controller.abort(); if (timer) window.clearTimeout(timer); };
  }, [enabled, queryClient]);
}
