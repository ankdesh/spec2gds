import { describe, expect, it } from "vitest";
import { acceptsView, draftRevisions, saveBaseRevision } from "../src/revision-guards";

describe("delayed source view responses", () => {
  const selected = { epoch: 2, key: "package-b", request: 4 };
  it.each([
    ["older request", { ...selected, request: 3 }],
    ["earlier selection", { ...selected, epoch: 1 }],
    ["another package", { ...selected, key: "package-a" }],
    ["unbound package", { ...selected, key: null }],
  ])("ignores an %s response", (_, response) => {
    expect(acceptsView(response, selected)).toBe(false);
  });
  it("accepts only the current package and request", () => expect(acceptsView(selected, selected)).toBe(true));
});

describe("draft and reviewed save revisions", () => {
  it.each([
    [null, null, "current", "current"],
    [null, "draft", "current", "draft"],
    ["reviewed", "draft", "current", "reviewed"],
    ["reviewed", null, "current", "reviewed"],
  ])("selects the authored or explicitly reviewed revision", (reviewed, draft, current, expected) => {
    expect(saveBaseRevision(reviewed, draft, current)).toBe(expected);
  });
  it("captures a draft base once and clears it after save or cancel", () => {
    const active = draftRevisions(true, "original");
    expect(saveBaseRevision(active.reviewed, active.draft, "external")).toBe("original");
    const finished = draftRevisions(false, "external");
    expect(finished).toEqual({ draft: null, reviewed: null });
    expect(saveBaseRevision(finished.reviewed, finished.draft, "external")).toBe("external");
  });
  it("does not carry an approval into a new draft", () => {
    expect(draftRevisions(true, "new-source")).toEqual({ draft: "new-source", reviewed: null });
  });
});
