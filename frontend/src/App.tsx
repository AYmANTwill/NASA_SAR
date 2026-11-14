import { lazy, Suspense } from "react";
import { createBrowserRouter, RouterProvider } from "react-router-dom";
import { PersistQueryClientProvider } from "@tanstack/react-query-persist-client";
import { createQueryClient, persister } from "@/api/queries";
import AppShell from "@/components/layout/AppShell";
import RouteError from "@/components/RouteError";
import { Loading } from "@/components/states";
import { TooltipProvider } from "@/components/ui/tooltip";

const CasesPage = lazy(() => import("@/features/cases/CasesPage"));
const DiscoverPage = lazy(() => import("@/features/discover/DiscoverPage"));
const InvestigatePage = lazy(() => import("@/features/investigate/InvestigatePage"));
const WatchPage = lazy(() => import("@/features/watch/WatchPage"));
const LibraryPage = lazy(() => import("@/features/library/LibraryPage"));
const ProofPage = lazy(() => import("@/features/proof/ProofPage"));

const queryClient = createQueryClient();

const page = (node: React.ReactNode) => <Suspense fallback={<div className="px-4"><Loading /></div>}>{node}</Suspense>;

const router = createBrowserRouter([
  {
    element: <AppShell />,
    errorElement: <RouteError />,
    children: [
      { errorElement: <RouteError />, children: [
      { index: true, element: page(<CasesPage />) },
      { path: "cases/:caseId", element: page(<CasesPage />) },
      { path: "discover", element: page(<DiscoverPage />) },
      { path: "investigate", element: page(<InvestigatePage />) },
      { path: "investigate/:answerId", element: page(<InvestigatePage />) },
      { path: "watch", element: page(<WatchPage />) },
      { path: "library", element: page(<LibraryPage />) },
      { path: "proof", element: page(<ProofPage />) },
      { path: "*", element: page(<CasesPage />) },
      ] },
    ],
  },
]);

export default function App() {
  return (
    <PersistQueryClientProvider client={queryClient} persistOptions={{ persister, maxAge: 7 * 24 * 3_600_000, buster: "v2" }}>
      <TooltipProvider delayDuration={200}>
        <RouterProvider router={router} />
      </TooltipProvider>
    </PersistQueryClientProvider>
  );
}
