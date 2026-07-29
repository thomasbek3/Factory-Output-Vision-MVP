"use client";

import {
  OwnerSurfaceStatus,
  useOwnerSurfaceStatus,
} from "@/components/owner-v2/owner-shell";

export function OwnerStatusReporter({
  status,
}: {
  status: OwnerSurfaceStatus;
}) {
  useOwnerSurfaceStatus(status);
  return null;
}
