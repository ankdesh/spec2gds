import { mkdir, readFile, rename, writeFile } from "node:fs/promises";
import { dirname } from "node:path";
import { randomUUID } from "node:crypto";
import {
  CircuitBackendError,
  createDefaultCircuitDesignerPreferences,
  validateCircuitDesignerPreferences,
  type CircuitDesignerPreferencesV1,
} from "@spec2gds/circuit-core";

export interface StoredCircuitPreferences {
  preferences: CircuitDesignerPreferencesV1;
  persisted: boolean;
}

export class CircuitPreferencesStore {
  constructor(readonly path: string) {}

  async get(): Promise<StoredCircuitPreferences> {
    let contents: string;
    try {
      contents = await readFile(this.path, "utf8");
    } catch (reason) {
      if ((reason as NodeJS.ErrnoException).code === "ENOENT") {
        return { preferences: createDefaultCircuitDesignerPreferences(), persisted: false };
      }
      throw reason;
    }
    if (contents.length > 262_144) {
      throw new CircuitBackendError("validation_failed", "Circuit Designer preference file exceeds 256 KiB.");
    }
    let value: unknown;
    try {
      value = JSON.parse(contents);
    } catch {
      throw new CircuitBackendError("validation_failed", "Circuit Designer preference file is not valid JSON.");
    }
    const checked = validateCircuitDesignerPreferences(value);
    if (!checked.valid) throw new CircuitBackendError("validation_failed", checked.message);
    return { preferences: checked.preferences, persisted: true };
  }

  async put(value: unknown): Promise<CircuitDesignerPreferencesV1> {
    const checked = validateCircuitDesignerPreferences(value);
    if (!checked.valid) throw new CircuitBackendError("validation_failed", checked.message);
    const contents = `${JSON.stringify(checked.preferences, null, 2)}\n`;
    if (contents.length > 262_144) {
      throw new CircuitBackendError("validation_failed", "Circuit Designer preferences exceed 256 KiB.");
    }
    await mkdir(dirname(this.path), { recursive: true });
    const temporary = `${this.path}.${randomUUID()}.tmp`;
    await writeFile(temporary, contents, { encoding: "utf8", mode: 0o600 });
    await rename(temporary, this.path);
    return checked.preferences;
  }
}

