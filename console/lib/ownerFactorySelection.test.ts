import { describe, expect, it } from "vitest";
import { selectOwnerFactory } from "@/lib/ownerFactorySelection";

const factory = {
  id: "10000000-0000-0000-0000-000000000001",
  name: "Factory One",
  timezone: "America/New_York",
};

describe("selectOwnerFactory", () => {
  it("never falls back when an explicit foreign factory is requested", () => {
    expect(
      selectOwnerFactory([factory], "20000000-0000-0000-0000-000000000002"),
    ).toEqual({ kind: "choose", factories: [factory] });
  });

  it("selects the sole membership only when no factory was requested", () => {
    expect(selectOwnerFactory([factory])).toEqual({
      kind: "ready",
      factory,
    });
  });

  it("returns the exact requested membership", () => {
    expect(selectOwnerFactory([factory], factory.id)).toEqual({
      kind: "ready",
      factory,
    });
  });
});
