/** Keep the Inspector and creation dialog on the same width/range syntax. */
export function parseBoundaryPortWidth(value: string): number | string {
  const raw = value.trim();
  if (!raw) throw new Error("Enter a wire width or range.");
  if (/^[+-]?\d+(?:\.\d+)?$/.test(raw)) {
    const width = Number(raw);
    if (!Number.isSafeInteger(width) || width < 1) throw new Error("Wire width must be a positive whole number.");
    return width;
  }
  return raw.startsWith("[") || !raw.includes(":") ? raw : `[${raw}]`;
}
