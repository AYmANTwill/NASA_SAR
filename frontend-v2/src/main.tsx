import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import "@fontsource/ibm-plex-sans/400.css";
import "@fontsource/ibm-plex-sans/500.css";
import "@fontsource/ibm-plex-sans/600.css";
import "@fontsource/ibm-plex-sans-arabic/400.css";
import "@fontsource/ibm-plex-sans-arabic/500.css";
import "@fontsource/ibm-plex-sans-arabic/600.css";
import "./styles/tokens.css";
import "./styles/base.css";
import "./i18n";
import { ApiProvider } from "./api/ApiProvider";
import type { ApiClient } from "./api/client";
import { AppRoutes } from "./app/routes";
import { DemoContext, type DemoInfo } from "./demo/DemoContext";

/**
 * Online (dev, build): the http client on /api. Offline ("demo", "rehearsal" builds):
 * the replay client on the bundled snapshot. The mode is fixed at build time, so the
 * replay code and the snapshot are not even in an online build.
 */
async function start() {
  let client: ApiClient | undefined;
  let demo: DemoInfo | null = null;
  const mode = import.meta.env.MODE;
  if (mode === "demo" || mode === "rehearsal") {
    const { bundledSnapshot, createReplayClient } = await import("./demo/replay");
    const snapshot = bundledSnapshot();
    if (!snapshot) throw new Error("This offline build has no snapshot: run `npm run snapshot` before building.");
    client = createReplayClient(snapshot);
    demo = { kind: mode, generatedAt: snapshot.generated_at };
  }

  createRoot(document.getElementById("root")!).render(
    <StrictMode>
      <DemoContext.Provider value={demo}>
        <ApiProvider client={client}>
          <BrowserRouter>
            <AppRoutes />
          </BrowserRouter>
        </ApiProvider>
      </DemoContext.Provider>
    </StrictMode>,
  );
}

void start();
