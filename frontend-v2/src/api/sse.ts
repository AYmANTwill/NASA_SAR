export interface SseMessage {
  event: string;
  data: string;
}

/**
 * Reads a text/event-stream from a fetch() body (EventSource cannot POST).
 * Handles CRLF, multi-line data fields, comments and messages split across chunks.
 */
export async function* readSse(body: ReadableStream<Uint8Array>): AsyncGenerator<SseMessage> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  // A chunk may end between "\r" and "\n": that "\r" waits for the next chunk before line endings are normalised.
  let carry = "";
  try {
    for (;;) {
      const { done, value } = await reader.read();
      let incoming = carry + (done ? decoder.decode() : decoder.decode(value, { stream: true }));
      carry = !done && incoming.endsWith("\r") ? "\r" : "";
      if (carry) incoming = incoming.slice(0, -1);
      buffer += incoming.replace(/\r\n?/g, "\n");
      let end: number;
      while ((end = buffer.indexOf("\n\n")) !== -1) {
        const message = parseSseBlock(buffer.slice(0, end));
        buffer = buffer.slice(end + 2);
        if (message) yield message;
      }
      if (done) {
        const last = parseSseBlock(buffer);
        if (last) yield last;
        return;
      }
    }
  } finally {
    reader.releaseLock();
  }
}

export function parseSseBlock(block: string): SseMessage | null {
  let event = "message";
  const data: string[] = [];
  for (const line of block.split("\n")) {
    if (line === "" || line.startsWith(":")) continue;
    const colon = line.indexOf(":");
    const field = colon === -1 ? line : line.slice(0, colon);
    const value = colon === -1 ? "" : line.slice(colon + 1).replace(/^ /, "");
    if (field === "event") event = value;
    else if (field === "data") data.push(value);
  }
  return data.length > 0 ? { event, data: data.join("\n") } : null;
}
