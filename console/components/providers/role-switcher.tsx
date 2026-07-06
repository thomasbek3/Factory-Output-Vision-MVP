"use client";

import { useState } from "react";

type Role = "owner" | "reviewer" | "ops";

const roles: Role[] = ["owner", "reviewer", "ops"];

export function RoleSwitcher() {
  const [role, setRole] = useState<Role>(() => {
    if (typeof window === "undefined") {
      return "owner";
    }
    const saved = window.localStorage.getItem("factoryvision-role");
    if (saved === "owner" || saved === "reviewer" || saved === "ops") {
      return saved;
    }
    return "owner";
  });

  function updateRole(nextRole: Role) {
    setRole(nextRole);
    window.localStorage.setItem("factoryvision-role", nextRole);
  }

  if (process.env.NODE_ENV === "production") {
    return null;
  }

  return (
    <label className="flex items-center gap-2 text-[11px] font-medium text-[var(--text-dim)]">
      Role
      <select
        value={role}
        onChange={(event) => updateRole(event.target.value as Role)}
        className="h-8 rounded-lg border border-[var(--border)] bg-[var(--panel-2)] px-2 text-[12px] text-[var(--text)]"
      >
        {roles.map((item) => (
          <option key={item} value={item}>
            {item}
          </option>
        ))}
      </select>
    </label>
  );
}
