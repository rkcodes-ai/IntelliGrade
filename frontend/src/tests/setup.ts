import "@testing-library/jest-dom/vitest";

// jsdom implements neither the Pointer Events API nor `scrollIntoView` —
// Radix UI's Dialog (see `components/ui/dialog.tsx`) relies on both
// (pointer capture for its dismissable layer, scrollIntoView for its focus
// scope) and hangs indefinitely under `userEvent` without these no-op
// polyfills. Standard, widely-used shims for testing Radix under jsdom.
if (typeof window !== "undefined") {
  if (!window.HTMLElement.prototype.hasPointerCapture) {
    window.HTMLElement.prototype.hasPointerCapture = () => false;
  }
  if (!window.HTMLElement.prototype.setPointerCapture) {
    window.HTMLElement.prototype.setPointerCapture = () => {};
  }
  if (!window.HTMLElement.prototype.releasePointerCapture) {
    window.HTMLElement.prototype.releasePointerCapture = () => {};
  }
  if (!window.HTMLElement.prototype.scrollIntoView) {
    window.HTMLElement.prototype.scrollIntoView = () => {};
  }
}
