import { beforeEach, describe, expect, it, vi } from "vitest";
import React from "react";
import { OwnerShell } from "@/components/owner-v2/owner-shell";
import { OwnerDataUnavailable } from "@/components/owner-v2/owner-surface-state";

const mocks = vi.hoisted(() => ({
  authorize: vi.fn(),
  cookies: vi.fn(),
  headers: vi.fn(),
  redirect: vi.fn(),
}));

vi.mock("next/headers", () => ({
  cookies: mocks.cookies,
  headers: mocks.headers,
}));
vi.mock("next/navigation", () => ({ redirect: mocks.redirect }));
vi.mock("@/lib/ownerServer", () => ({
  authorizeOwnerAccessToken: mocks.authorize,
  ownerAccessCookie: "fv_owner_access",
  ownerRefreshCookie: "fv_owner_refresh",
}));

import OwnerLayout from "@/app/(owner)/layout";

function cookieStore(values: Record<string, string>) {
  return {
    get(name: string) {
      return values[name] ? { value: values[name] } : undefined;
    },
  };
}

describe("OwnerLayout authorization boundary", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.headers.mockResolvedValue(
      new Headers({ "x-fv-owner-return-to": "/history?factory_id=factory-1" }),
    );
    mocks.redirect.mockImplementation((destination: string) => {
      throw new Error(`REDIRECT:${destination}`);
    });
  });

  it("renders the truthful unavailable state when authorization infrastructure fails", async () => {
    mocks.cookies.mockResolvedValue(
      cookieStore({ fv_owner_access: "valid-access" }),
    );
    mocks.authorize.mockRejectedValue(new Error("provider unavailable"));

    const result = await OwnerLayout({ children: <div>owner child</div> });

    expect(result.type).toBe(OwnerShell);
    expect(result.props.status).toBe("unavailable");
    expect(result.props.children.type).toBe(OwnerDataUnavailable);
    expect(mocks.redirect).not.toHaveBeenCalled();
  });

  it("refreshes an unauthorized access token when a refresh cookie exists", async () => {
    mocks.cookies.mockResolvedValue(
      cookieStore({
        fv_owner_access: "expired-access",
        fv_owner_refresh: "refresh-token",
      }),
    );
    mocks.authorize.mockResolvedValue({
      authorized: false,
      status: 401,
      factories: [],
    });

    await expect(
      OwnerLayout({ children: <div>owner child</div> }),
    ).rejects.toThrow(
      "REDIRECT:/api/owner/session?action=refresh&return_to=%2Fhistory%3Ffactory_id%3Dfactory-1",
    );
  });

  it("renders the owner shell only after authorization succeeds", async () => {
    mocks.cookies.mockResolvedValue(
      cookieStore({ fv_owner_access: "valid-access" }),
    );
    mocks.authorize.mockResolvedValue({
      authorized: true,
      factories: [{ id: "factory-1", name: "ForgeWorks" }],
    });
    const child = <div>owner child</div>;

    const result = await OwnerLayout({ children: child });

    expect(result.type).toBe(OwnerShell);
    expect(result.props.factories).toEqual([
      { id: "factory-1", name: "ForgeWorks" },
    ]);
    expect(result.props.children).toBe(child);
  });
});
