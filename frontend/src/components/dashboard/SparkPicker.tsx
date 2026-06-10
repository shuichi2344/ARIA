'use client'

/**
 * SparkPicker is no longer rendered as a standalone bar above the chat.
 * Spark management has been moved into the Settings drawer (SimulationSettings area).
 * This file is kept as a re-export shim so existing imports don't break during
 * the transition, but the component renders nothing.
 */
export default function SparkPicker() {
  return null
}
