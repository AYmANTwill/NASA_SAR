import { render, screen } from "@testing-library/react";
import { MemoryRouter, useLocation } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { ApiProvider } from "@/api/ApiProvider";
import { createHttpClient } from "@/api/client";
import { recorded, recordedFetch, recordedNames } from "@/test/recorded";
import { AppRoutes } from "./routes";

let location = "";
function Spy() {
  location = useLocation().pathname;
  return null;
}

const BASE = "http://test/api";
const { fetcher } = recordedFetch({
  [`${BASE}/cases`]: recorded("cases.json"),
  ...Object.fromEntries(recordedNames("case-").map((n) => [`${BASE}${recorded(n).path}`, recorded(n)])),
});

function renderAt(path: string) {
  render(
    <ApiProvider client={createHttpClient(BASE, fetcher)}>
      <MemoryRouter initialEntries={[path]}>
        <AppRoutes />
        <Spy />
      </MemoryRouter>
    </ApiProvider>,
  );
}

describe("routes", () => {
  it("serves Arabic right to left with Arabic labels", () => {
    renderAt("/ar/");
    expect(document.documentElement.lang).toBe("ar");
    expect(document.documentElement.dir).toBe("rtl");
    expect(screen.getByRole("heading", { level: 1 }).textContent).toBe("دراسات الحالة");
  });

  it("serves French left to right", () => {
    renderAt("/fr/ask");
    expect(document.documentElement.dir).toBe("ltr");
    expect(screen.getByRole("heading", { level: 1 }).textContent).toBe("Enquêter");
  });

  it("language links keep the current page", () => {
    renderAt("/en/library");
    expect(screen.getByRole("link", { name: "العربية" }).getAttribute("href")).toBe("/ar/library");
    expect(screen.getByRole("link", { name: "English" }).getAttribute("aria-current")).toBe("true");
  });

  it("an unknown language is a not-found page, not a guess", () => {
    renderAt("/de/cases");
    expect(screen.getByRole("heading", { level: 1 }).textContent).toMatch(/introuvable|not found|غير موجودة/);
  });

  it("/ redirects to a language", () => {
    renderAt("/");
    expect(location).toMatch(/^\/(fr|en|ar)\/$/);
  });
});
