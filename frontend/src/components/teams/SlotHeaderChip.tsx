import type { SlotOverrides } from '../../hooks/useCompareSlots'

interface Props {
  overrides: SlotOverrides
}

// Renders the small italic sub-line under a slot's name showing how
// the slot's scope differs from primary. Stub for Commit 2 — Commit 3
// fills in the formatted diff (tournament / season / venue / series).
export default function SlotHeaderChip({ overrides }: Props) {
  if (Object.keys(overrides).length === 0) return null
  return null
}
