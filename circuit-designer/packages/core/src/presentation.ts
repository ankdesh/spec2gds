/** Presentation sizes use projected pixels; they never change circuit geometry. */
export function componentTitlePresentation(width: number, height: number, zoom = 1) {
  const scale = Number.isFinite(zoom) && zoom > 0 ? zoom : 1;
  const screenFontSize = Math.min(20, Math.max(12, width * scale / 14));
  return { screenFontSize, fontSize: screenFontSize / scale, visible: height * scale >= 16 };
}
