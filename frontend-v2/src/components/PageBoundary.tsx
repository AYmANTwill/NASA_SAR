import { Component, type ReactNode } from "react";
import { ErrorPanel } from "./ErrorPanel";

export class PageBoundary extends Component<{ children: ReactNode }, { error: unknown }> {
  state: { error: unknown } = { error: null };
  static getDerivedStateFromError(error: unknown) { return { error }; }
  render() {
    return this.state.error ? <div className="page"><ErrorPanel error={this.state.error} onRetry={() => this.setState({ error: null })} /></div> : this.props.children;
  }
}
