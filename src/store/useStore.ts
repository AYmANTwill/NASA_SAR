import { create } from "zustand";
import type { LayerId, Thresholds } from "../data/types";
export type { LayerId } from "../data/types";
interface State {
  caseId: string;
  screen: "intro" | "dashboard";
  date: number;
  playing: boolean;
  speed: number;
  compare: boolean;
  compareDate: number;
  compareKind: "date" | "optical" | "sentinel1" | "alos2";
  siteId: string | null;
  animationOpen: boolean;
  thresholds: Thresholds;
  swipe: number;
  layers: Record<LayerId, number>;
  locale: "en" | "fr";
  sheet: "layers" | "analysis" | null;
  modal: "about" | "alerts" | "shortcuts" | null;
  tour: boolean;
  layersOpen: boolean;
  extruded: boolean;
  focus: [number, number] | null;
  selectCase: (id: string) => void;
  set: (
    patch: Partial<Omit<State, "set" | "selectCase" | "toggleLayer">>,
  ) => void;
  toggleLayer: (id: LayerId) => void;
}
export const useStore = create<State>((set) => ({
  caseId: "venezuela",
  screen: "intro",
  date: 7,
  playing: false,
  speed: 1,
  compare: false,
  compareDate: 0,
  compareKind: "date",
  siteId: null,
  animationOpen: false,
  thresholds: {deformationCmMonth:5,coherenceLossPct:50,expansionHaMonth:10,goffCm:10},
  swipe: 50,
  layers: {
    sentinel1:0, alos2:0, ps_insar:0, sbas:0, smap:0, grace:0, dem_slope:0, geology:0,
    gcov: 0,
    gunw: 0.8,
    coherence: 0,
    goff: 0,
    ndvi: 0,
    rainfall: 0,
    classification: 0,
    events: 1,
    fires: 0,
    floodExtent: 0,
    infrastructure: 0,
    optical: 0,
    labels: 1,
  },
  locale: "en",
  sheet: null,
  modal: null,
  tour: false,
  layersOpen: true,
  extruded: false,
  focus: null,
  selectCase: (caseId) =>
    set({ caseId, screen: "dashboard", date: 7, compare: false, compareKind:"date",siteId:null,animationOpen:false, focus: null }),
  set: (patch) => set(patch),
  toggleLayer: (id) =>
    set((state) => ({
      layers: { ...state.layers, [id]: state.layers[id] > 0 ? 0 : 0.8 },
    })),
}));
