import { Navigate, createBrowserRouter, type RouteObject } from "react-router";
import { Shell } from "./components/Shell";
import { AuthPage } from "./routes/AuthPage";
import { DocumentPage } from "./routes/DocumentPage";
import { DocumentsPage } from "./routes/DocumentsPage";

export const routes: RouteObject[] = [
  { path: "/sign-in", element: <AuthPage mode="sign-in" /> },
  { path: "/sign-up", element: <AuthPage mode="sign-up" /> },
  {
    element: <Shell />,
    children: [
      { path: "/", element: <Navigate to="/documents" replace /> },
      { path: "/documents", element: <DocumentsPage /> },
      { path: "/documents/:id", element: <DocumentPage /> },
      { path: "*", element: <Navigate to="/documents" replace /> },
    ],
  },
];

export const createRouter = () => createBrowserRouter(routes);
