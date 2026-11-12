// The kitchen's clock and time zone, as the server tells them.
// The server may run in another zone than the visitor's device, and its clock can be moved forward
// (the fast-forward switch for demos), so the page never trusts Date.now() for "what time is it in
// the kitchen": it keeps the difference to the server's clock from the last answer that carried one.

let zone = "";
let skewMs = 0;
let fmt: Intl.DateTimeFormat | null = null;

/** IANA name from the server's settings; "" = the visitor's own zone. A name the browser does not know is ignored. */
export function setZone(name: string): void {
  zone = "";
  fmt = null;
  if (!name) return;
  try {
    fmt = new Intl.DateTimeFormat("en-US", {
      timeZone: name, hourCycle: "h23", year: "numeric", month: "numeric", day: "numeric", hour: "numeric", minute: "numeric",
    });
    zone = name;
  } catch {
    fmt = null;
  }
}

export function getZone(): string {
  return zone;
}

/** Call with the `now` of a server answer (milliseconds). */
export function syncClock(serverNowMs: number): void {
  if (Number.isFinite(serverNowMs) && serverNowMs > 0) skewMs = serverNowMs - Date.now();
}

/** The kitchen's "now" in milliseconds. */
export function nowMs(): number {
  return Date.now() + skewMs;
}

export interface Wall {
  year: number;
  month: number;
  day: number;
  hour: number;
  minute: number;
}

/** A moment as wall-clock numbers in the kitchen's zone. */
export function wall(ms: number): Wall {
  if (fmt) {
    const p: Record<string, number> = {};
    for (const part of fmt.formatToParts(new Date(ms))) if (part.type !== "literal") p[part.type] = Number(part.value);
    return { year: p.year, month: p.month, day: p.day, hour: p.hour % 24, minute: p.minute };
  }
  const d = new Date(ms);
  return { year: d.getFullYear(), month: d.getMonth() + 1, day: d.getDate(), hour: d.getHours(), minute: d.getMinutes() };
}
