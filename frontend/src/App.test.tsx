import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import App from "./App";
import { AuthProvider } from "./auth";

const session = {
  user: {
    id: "user-1",
    email: "dispatcher@northstar.test",
    firstName: "Dana",
    lastName: "Dispatch",
    fullName: "Dana Dispatch",
  },
  role: "dispatcher",
  organisation: { id: "org-1", name: "Northstar Maintenance", slug: "northstar" },
};

function jsonResponse(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function renderApp() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <MemoryRouter initialEntries={["/login"]}>
          <App />
        </MemoryRouter>
      </AuthProvider>
    </QueryClientProvider>,
  );
}

afterEach(() => vi.restoreAllMocks());

describe("Dispatcher workflow", () => {
  it("signs in and displays persisted dashboard metrics", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const url = String(input);
      if (url.endsWith("/auth/refresh")) return jsonResponse({}, 401);
      if (url.endsWith("/auth/login") && init?.method === "POST") {
        return jsonResponse({ data: { accessToken: "access-token", ...session } });
      }
      if (url.endsWith("/dashboard/summary")) {
        return jsonResponse({
          data: {
            total: 12,
            assigned: 9,
            unassigned: 3,
            byStatus: { draft: 3, scheduled: 4, in_progress: 2, blocked: 1, completed: 2, cancelled: 0 },
            byPriority: { low: 2, medium: 6, high: 3, urgent: 1 },
          },
        });
      }
      if (url.includes("/work-orders?")) {
        return jsonResponse({ data: [], meta: { page: 1, pageSize: 6, total: 0, totalPages: 0 } });
      }
      if (url.endsWith("/realtime/events")) return jsonResponse({}, 503);
      return jsonResponse({}, 404);
    });

    renderApp();
    await screen.findByRole("heading", { name: "Sign in to FieldDesk" });
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));

    expect(await screen.findByText("Total work orders")).toBeInTheDocument();
    expect(screen.getByText("12")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /New work order/i })).toBeInTheDocument();
    await waitFor(() => expect(globalThis.fetch).toHaveBeenCalledWith(
      expect.stringContaining("/dashboard/summary"),
      expect.objectContaining({ credentials: "include" }),
    ));
  });
});
