import { describe, expect, it } from "vitest";
import { browserRandomUuid } from "./browser-id";

describe("browserRandomUuid", () => {
  it("uses the native implementation when available", () => {
    expect(browserRandomUuid({ randomUUID: () => "native-id" })).toBe("native-id");
  });

  it("generates an RFC 4122-shaped UUID when randomUUID is unavailable", () => {
    const uuid = browserRandomUuid({
      getRandomValues: (array) => {
        array.fill(0x2a);
        return array;
      },
    });

    expect(uuid).toBe("2a2a2a2a-2a2a-4a2a-aa2a-2a2a2a2a2a2a");
  });
});
