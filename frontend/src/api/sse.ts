export interface SseEvent {
  event: string;
  data: string;
}

/**
 * Minimal text/event-stream parser for fetch() bodies (EventSource cannot POST).
 * Handles CRLF, multi-line data fields, comments and chunk boundaries.
 */
export async function* readSse(body: ReadableStream<Uint8Array>): AsyncGenerator<SseEvent> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      yield* drain(false);
    }
    buffer += decoder.decode();
    yield* drain(true);
  } finally {
    reader.releaseLock();
  }

  function* drain(final: boolean): Generator<SseEvent> {
    buffer = buffer.replace(/\r\n?/g, "\n");
    let index: number;
    while ((index = buffer.indexOf("\n\n")) !== -1) {
      const block = buffer.slice(0, index);
      buffer = buffer.slice(index + 2);
      const parsed = parseBlock(block);
      if (parsed) yield parsed;
    }
    if (final && buffer.trim()) {
      const parsed = parseBlock(buffer);
      buffer = "";
      if (parsed) yield parsed;
    }
  }
}

export function parseBlock(block: string): SseEvent | null {
  let event = "message";
  const data: string[] = [];
  for (const line of block.split("\n")) {
    if (!line || line.startsWith(":")) continue;
    const colon = line.indexOf(":");
    const field = colon === -1 ? line : line.slice(0, colon);
    const value = colon === -1 ? "" : line.slice(colon + 1).replace(/^ /, "");
    if (field === "event") event = value;
    else if (field === "data") data.push(value);
  }
  return data.length ? { event, data: data.join("\n") } : null;
}
