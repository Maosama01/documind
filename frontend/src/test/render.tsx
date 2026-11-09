import { render } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider, createMemoryRouter } from "react-router";
import { setToken } from "../auth/session";
import { routes } from "../router";

/** Render the real app routes at `path`, signed in unless told otherwise. */
export function renderApp(path: string, { signedIn = true } = {}) {
  if (signedIn) setToken("test-token");
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const router = createMemoryRouter(routes, { initialEntries: [path] });
  const view = render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
  return { ...view, router };
}
