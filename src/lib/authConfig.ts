// src/lib/authConfig.ts
// Single source of truth for whether the sign-in gate is active.
// Mirrors AUTH_ENABLED in core/.env — keep the two in step.
// Defaults to enabled: only an explicit "false" turns the gate off.
export const AUTH_ENABLED =
  String(import.meta.env.VITE_AUTH_ENABLED ?? "true").toLowerCase() !== "false";
