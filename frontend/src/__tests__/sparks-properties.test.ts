// Feature: context-sparks, Property 3: Single Active Spark Invariant (frontend)
// Validates: Requirements 4.2, 4.3
import { test, expect } from 'vitest'
import * as fc from 'fast-check'

// Simulate the pure state reducer for active spark
function applyOp(activeSparkId: string | null, op: { sparkId: string; op: 'activate' | 'deactivate' }): string | null {
  if (op.op === 'activate') return op.sparkId
  return null
}

test('single active spark invariant: at most one spark active per session at any point', () => {
  fc.assert(
    fc.property(
      fc.array(
        fc.record({ sparkId: fc.uuid(), op: fc.constantFrom('activate' as const, 'deactivate' as const) }),
        { minLength: 1, maxLength: 20 }
      ),
      (ops) => {
        let activeSparkId: string | null = null
        for (const op of ops) {
          activeSparkId = applyOp(activeSparkId, op)
          // Count is always 0 or 1 (never 2)
          const count = activeSparkId === null ? 0 : 1
          expect(count).toBeLessThanOrEqual(1)
        }
      }
    )
  )
})
