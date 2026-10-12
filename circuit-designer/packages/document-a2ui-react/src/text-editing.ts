/** Retain a text selection while an application menu has focus. */
import { Transaction } from "@codemirror/state";
import { EditorView } from "@codemirror/view";

export interface SpecTextEditTarget {
  selectedText: string;
  isCurrent(): boolean;
  focus(): void;
  replaceSelection(text: string, operation: "cut" | "paste"): void;
  selectAll(): void;
}

export function captureSpecTextEditTarget(element: Element | null): SpecTextEditTarget | null {
  if (element instanceof HTMLInputElement || element instanceof HTMLTextAreaElement) {
    if (element.disabled || element.readOnly || element.selectionStart === null) return null;
    const field = element;
    const value = field.value;
    const start = field.selectionStart ?? 0;
    const end = field.selectionEnd ?? start;
    const isCurrent = () => field.isConnected && field.getClientRects().length > 0 && !field.disabled && !field.readOnly && field.value === value && field.selectionStart === start && field.selectionEnd === end;
    return {
      selectedText: value.slice(start, end), isCurrent,
      focus() { if (isCurrent()) field.focus(); },
      replaceSelection(text) {
        if (!isCurrent()) throw new Error("The text field changed. Select the text again.");
        const prototype = field instanceof HTMLTextAreaElement ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
        Object.getOwnPropertyDescriptor(prototype, "value")!.set!.call(field, value.slice(0, start) + text + value.slice(end));
        field.dispatchEvent(new Event("input", { bubbles: true }));
        field.focus();
        const insertedLength = field.value.length - (value.length - (end - start));
        const cursor = Math.min(start + insertedLength, field.value.length);
        field.setSelectionRange(cursor, cursor);
      },
      selectAll() { if (isCurrent()) { field.focus(); field.select(); } },
    };
  }
  const host = element?.closest<HTMLElement>(".cm-editor");
  const view = host ? EditorView.findFromDOM(host) : null;
  if (!view || view.state.readOnly || !view.contentDOM.isContentEditable) return null;
  const { doc, selection } = view.state;
  const isCurrent = () => view.dom.isConnected && view.dom.getClientRects().length > 0 && view.contentDOM.isContentEditable && !view.state.readOnly && view.state.doc === doc && view.state.selection.eq(selection);
  return {
    selectedText: selection.ranges.filter(range => !range.empty).map(range => doc.sliceString(range.from, range.to)).join("\n"),
    isCurrent,
    focus() { if (isCurrent()) view.focus(); },
    replaceSelection(text, operation) {
      if (!isCurrent()) throw new Error("The SystemVerilog selection changed. Select the text again.");
      view.dispatch({ ...view.state.replaceSelection(text), annotations: Transaction.userEvent.of(operation === "cut" ? "delete.cut" : "input.paste") });
      view.focus();
    },
    selectAll() { if (isCurrent()) { view.dispatch({ selection: { anchor: 0, head: doc.length } }); view.focus(); } },
  };
}
