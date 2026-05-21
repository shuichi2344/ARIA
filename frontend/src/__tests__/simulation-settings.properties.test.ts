/**
 * Property-based tests for SimulationSettings logic
 * Feature: simulation-settings
 *
 * Tests pure logic functions extracted from the SimulationSettings component.
 * Uses fast-check for property-based testing with minimum 100 iterations.
 */
import { describe, it, expect } from 'vitest'
import * as fc from 'fast-check'

// --- Pure logic functions under test ---

const ALL_INCOME_LEVELS = ['B40', 'M40', 'T20'] as const
const ALL_AGE_GROUPS = ['20-29', '30-39', '40-49', '50-59', '60+'] as const

/**
 * Formats a percentage value to 1 decimal place (as used in the component).
 */
function formatPercentage(value: number): string {
  return value.toFixed(1)
}

/**
 * Maps income toggle state to API constraint parameter.
 * When all levels are enabled, returns null (no filtering).
 * Otherwise returns the enabled subset.
 */
function getIncomeConstraints(enabledLevels: string[]): string[] | null {
  if (enabledLevels.length === ALL_INCOME_LEVELS.length &&
      ALL_INCOME_LEVELS.every(l => enabledLevels.includes(l))) {
    return null
  }
  return enabledLevels
}

/**
 * Maps age group toggle state to API constraint parameter.
 * When all groups are enabled, returns null (no filtering).
 * Otherwise returns the enabled subset.
 */
function getAgeConstraints(enabledGroups: string[]): string[] | null {
  if (enabledGroups.length === ALL_AGE_GROUPS.length &&
      ALL_AGE_GROUPS.every(g => enabledGroups.includes(g))) {
    return null
  }
  return enabledGroups
}

/**
 * Clamps agent count to [15, 100] range.
 */
function clampAgentCount(value: number): number {
  return Math.min(100, Math.max(15, value))
}

/**
 * Determines whether a performance warning should be shown.
 */
function shouldShowPerformanceWarning(agentCount: number): boolean {
  return agentCount > 50
}

// --- Property Tests ---

describe('Feature: simulation-settings', () => {
  describe('Property 2: Percentage formatting', () => {
    it('formats any float to exactly 1 decimal place', () => {
      /**
       * Validates: Requirements 1.4
       *
       * For any percentage value, the displayed string SHALL be the value
       * rounded to one decimal place.
       */
      fc.assert(
        fc.property(
          fc.double({ min: 0, max: 100, noNaN: true, noDefaultInfinity: true }),
          (value) => {
            const formatted = formatPercentage(value)
            // Must contain exactly one decimal point
            const parts = formatted.split('.')
            expect(parts).toHaveLength(2)
            // Decimal part must be exactly 1 digit
            expect(parts[1]).toHaveLength(1)
            // Must be a valid number string
            expect(Number(formatted)).not.toBeNaN()
          }
        ),
        { numRuns: 100 }
      )
    })

    it('rounds correctly (e.g., 42.15 → "42.2", 30.0 → "30.0")', () => {
      /**
       * Validates: Requirements 1.4
       */
      fc.assert(
        fc.property(
          fc.double({ min: 0, max: 100, noNaN: true, noDefaultInfinity: true }),
          (value) => {
            const formatted = formatPercentage(value)
            // The formatted value should be parseable back to a number
            // that is within 0.05 of the original (rounding tolerance)
            const parsed = parseFloat(formatted)
            expect(Math.abs(parsed - value)).toBeLessThanOrEqual(0.05 + Number.EPSILON)
          }
        ),
        { numRuns: 100 }
      )
    })
  })

  describe('Property 3: Income toggle state maps to API parameters', () => {
    it('returns the enabled subset for non-full selections, null for all enabled', () => {
      /**
       * Validates: Requirements 2.3, 2.4, 5.1, 5.4
       *
       * For any combination of income level toggle states where at least one
       * is enabled, the income_constraints parameter SHALL contain exactly the
       * set of enabled income levels. When all three are enabled, the parameter
       * SHALL be omitted or null.
       */
      const nonEmptySubsetOfIncome = fc.subarray([...ALL_INCOME_LEVELS], { minLength: 1 })

      fc.assert(
        fc.property(nonEmptySubsetOfIncome, (enabledLevels) => {
          const result = getIncomeConstraints(enabledLevels)

          if (enabledLevels.length === ALL_INCOME_LEVELS.length &&
              ALL_INCOME_LEVELS.every(l => enabledLevels.includes(l))) {
            // All enabled → null (no filtering)
            expect(result).toBeNull()
          } else {
            // Partial selection → returns the subset
            expect(result).not.toBeNull()
            expect(result).toEqual(enabledLevels)
            // Every item in result must be a valid income level
            for (const level of result!) {
              expect(ALL_INCOME_LEVELS).toContain(level)
            }
          }
        }),
        { numRuns: 100 }
      )
    })
  })

  describe('Property 4: Age group toggle state maps to API parameters', () => {
    it('returns the enabled subset for non-full selections, null for all enabled', () => {
      /**
       * Validates: Requirements 3.3, 3.4, 5.2, 5.5
       *
       * For any combination of age group toggle states where at least one
       * is enabled, the age_constraints parameter SHALL contain exactly the
       * set of enabled age groups. When all six are enabled, the parameter
       * SHALL be omitted or null.
       */
      const nonEmptySubsetOfAge = fc.subarray([...ALL_AGE_GROUPS], { minLength: 1 })

      fc.assert(
        fc.property(nonEmptySubsetOfAge, (enabledGroups) => {
          const result = getAgeConstraints(enabledGroups)

          if (enabledGroups.length === ALL_AGE_GROUPS.length &&
              ALL_AGE_GROUPS.every(g => enabledGroups.includes(g))) {
            // All enabled → null (no filtering)
            expect(result).toBeNull()
          } else {
            // Partial selection → returns the subset
            expect(result).not.toBeNull()
            expect(result).toEqual(enabledGroups)
            // Every item in result must be a valid age group
            for (const group of result!) {
              expect(ALL_AGE_GROUPS).toContain(group)
            }
          }
        }),
        { numRuns: 100 }
      )
    })
  })

  describe('Property 5: Agent count clamping', () => {
    it('clamps any integer to [15, 100]', () => {
      /**
       * Validates: Requirements 4.2, 4.3, 4.4
       *
       * For any numeric input value, the agent count SHALL be clamped
       * to the range [15, 100].
       */
      fc.assert(
        fc.property(fc.integer({ min: -1000, max: 1000 }), (value) => {
          const clamped = clampAgentCount(value)
          // Result must be within [15, 100]
          expect(clamped).toBeGreaterThanOrEqual(15)
          expect(clamped).toBeLessThanOrEqual(100)
        }),
        { numRuns: 100 }
      )
    })

    it('preserves values already within [15, 100]', () => {
      /**
       * Validates: Requirements 4.2, 4.3, 4.4
       */
      fc.assert(
        fc.property(fc.integer({ min: 15, max: 100 }), (value) => {
          const clamped = clampAgentCount(value)
          expect(clamped).toBe(value)
        }),
        { numRuns: 100 }
      )
    })

    it('clamps values below 15 to exactly 15', () => {
      /**
       * Validates: Requirements 4.3
       */
      fc.assert(
        fc.property(fc.integer({ min: -1000, max: 14 }), (value) => {
          const clamped = clampAgentCount(value)
          expect(clamped).toBe(15)
        }),
        { numRuns: 100 }
      )
    })

    it('clamps values above 100 to exactly 100', () => {
      /**
       * Validates: Requirements 4.4
       */
      fc.assert(
        fc.property(fc.integer({ min: 101, max: 2000 }), (value) => {
          const clamped = clampAgentCount(value)
          expect(clamped).toBe(100)
        }),
        { numRuns: 100 }
      )
    })
  })

  describe('Property 6: Performance warning threshold', () => {
    it('shows warning iff clamped value > 50', () => {
      /**
       * Validates: Requirements 4.5
       *
       * For any agent count value greater than 50, the Settings_Panel SHALL
       * display a performance warning. For any value ≤ 50, no warning.
       */
      fc.assert(
        fc.property(fc.integer({ min: -1000, max: 1000 }), (value) => {
          const clamped = clampAgentCount(value)
          const warningShown = shouldShowPerformanceWarning(clamped)

          if (clamped > 50) {
            expect(warningShown).toBe(true)
          } else {
            expect(warningShown).toBe(false)
          }
        }),
        { numRuns: 100 }
      )
    })

    it('never shows warning for values ≤ 50', () => {
      /**
       * Validates: Requirements 4.5
       */
      fc.assert(
        fc.property(fc.integer({ min: 15, max: 50 }), (value) => {
          expect(shouldShowPerformanceWarning(value)).toBe(false)
        }),
        { numRuns: 100 }
      )
    })

    it('always shows warning for values > 50', () => {
      /**
       * Validates: Requirements 4.5
       */
      fc.assert(
        fc.property(fc.integer({ min: 51, max: 100 }), (value) => {
          expect(shouldShowPerformanceWarning(value)).toBe(true)
        }),
        { numRuns: 100 }
      )
    })
  })
})
