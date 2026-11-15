import { Component, type ReactNode } from "react";

/**
 * If the map cannot load or render (no WebGL, chunk failed offline), the page
 * keeps working: the fallback says so, and the legend and ledger stay.
 */
export class MapBoundary extends Component<{ fallback: ReactNode; children: ReactNode }, { failed: boolean }> {
  state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  render() {
    return this.state.failed ? this.props.fallback : this.props.children;
  }
}
