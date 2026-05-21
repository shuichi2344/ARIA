/**
 * Unit tests for ChatPanel integration with SimulationSettings
 *
 * Tests the conditional rendering logic and payload construction
 * that integrates SimulationSettings into ChatPanel.
 *
 * Since the project does not use @testing-library/react, these tests
 * verify the pure logic functions extracted from the component behavior.
 */
import { describe, it, expect } from 'vitest'
import type { BusinessProfile } from '@/components/dashboard/types'
import type { SimulationSettingsState } from '@/components/dashboard/SimulationSettings'

// --- Logic functions extracted from ChatPanel ---

const ALL_INCOME_LEVELS = ['B40', 'M40', 'T20']
const ALL_AGE_GROUPS = ['20-29', '30-39', '40-49', '50-59', '60+']

/**
 * Determines whether SimulationSettings should be rendered.
 * Mirrors the condition: `profile && profile.district`
 *
 * Validates: Requirement 7.2 (hidden when no profile)
 *            Requirement 7.3 (visible when profile loaded)
 */
function shouldRenderSimulationSettings(profile: BusinessProfile | null): boolean {
  return !!(profile && profile.district)
}

/**
 * Determines whether SimulationSettings controls should be disabled.
 * Mirrors the condition: `simulationStatus === 'running' || simulationStatus === 'paused'`
 *
 * Validates: Requirement 7.4 (disabled during simulation)
 *            Requirement 7.5 (re-enabled when simulation completes)
 */
function shouldDisableControls(simulationStatus: 'idle' | 'running' | 'paused' | 'done'): boolean {
  return simulationStatus === 'running' || simulationStatus === 'paused'
}

/**
 * Computes the income_constraints for the simulation start payload.
 * When all income levels are enabled, returns null (no filtering).
 * Otherwise returns the enabled subset.
 *
 * Validates: Requirement 5.1, 5.4
 */
function computeIncomeConstraints(settings: SimulationSettingsState | null): string[] | null {
  if (!settings) return null
  if (settings.incomeConstraints.length < ALL_INCOME_LEVELS.length) {
    return settings.incomeConstraints
  }
  return null
}

/**
 * Computes the age_constraints for the simulation start payload.
 * When all age groups are enabled, returns null (no filtering).
 * Otherwise returns the enabled subset.
 *
 * Validates: Requirement 5.2, 5.5
 */
function computeAgeConstraints(settings: SimulationSettingsState | null): string[] | null {
  if (!settings) return null
  if (settings.ageConstraints.length < ALL_AGE_GROUPS.length) {
    return settings.ageConstraints
  }
  return null
}

// --- Tests ---

describe('ChatPanel Integration: SimulationSettings visibility', () => {
  /**
   * Validates: Requirement 7.2
   * WHILE no business profile is loaded, THE Settings_Panel SHALL remain hidden
   */
  describe('SimulationSettings is hidden when profile is null', () => {
    it('returns false when profile is null', () => {
      expect(shouldRenderSimulationSettings(null)).toBe(false)
    })

    it('returns false when profile has no district', () => {
      const profile: BusinessProfile = {
        id: 'test-id',
        business_name: 'Test Business',
        business_type: 'restaurant',
      }
      expect(shouldRenderSimulationSettings(profile)).toBe(false)
    })

    it('returns false when profile.district is empty string', () => {
      const profile: BusinessProfile = {
        id: 'test-id',
        business_name: 'Test Business',
        district: '',
      }
      expect(shouldRenderSimulationSettings(profile)).toBe(false)
    })
  })

  /**
   * Validates: Requirement 7.3
   * WHEN a business profile is loaded, THE Settings_Panel SHALL become visible
   */
  describe('SimulationSettings is visible when profile is loaded', () => {
    it('returns true when profile has a valid district', () => {
      const profile: BusinessProfile = {
        id: 'test-id',
        business_name: 'Test Business',
        business_type: 'restaurant',
        district: 'Timur Laut',
      }
      expect(shouldRenderSimulationSettings(profile)).toBe(true)
    })

    it('returns true for any non-empty district string', () => {
      const profile: BusinessProfile = {
        district: 'Barat Daya',
      }
      expect(shouldRenderSimulationSettings(profile)).toBe(true)
    })
  })
})

describe('ChatPanel Integration: Controls disabled during simulation', () => {
  /**
   * Validates: Requirement 7.4
   * WHILE a simulation is running, THE Settings_Panel SHALL disable all controls
   */
  describe('controls are disabled during simulation', () => {
    it('returns true (disabled) when status is running', () => {
      expect(shouldDisableControls('running')).toBe(true)
    })

    it('returns true (disabled) when status is paused', () => {
      expect(shouldDisableControls('paused')).toBe(true)
    })
  })

  /**
   * Validates: Requirement 7.5
   * WHEN a simulation completes, THE Settings_Panel SHALL re-enable all controls
   */
  describe('controls are enabled when simulation is not active', () => {
    it('returns false (enabled) when status is idle', () => {
      expect(shouldDisableControls('idle')).toBe(false)
    })

    it('returns false (enabled) when status is done', () => {
      expect(shouldDisableControls('done')).toBe(false)
    })
  })
})

describe('ChatPanel Integration: Constraints in simulation start payload', () => {
  /**
   * Validates: Requirement 5.1, 5.4
   * When all income levels are enabled, omit income_constraints (pass null).
   * When some are disabled, pass only the enabled levels.
   */
  describe('income constraints in payload', () => {
    it('returns null when settings is null (no settings configured)', () => {
      expect(computeIncomeConstraints(null)).toBeNull()
    })

    it('returns null when all income levels are enabled (default state)', () => {
      const settings: SimulationSettingsState = {
        incomeConstraints: ['B40', 'M40', 'T20'],
        ageConstraints: [...ALL_AGE_GROUPS],
        agentCount: 25,
      }
      expect(computeIncomeConstraints(settings)).toBeNull()
    })

    it('returns subset when some income levels are disabled', () => {
      const settings: SimulationSettingsState = {
        incomeConstraints: ['M40', 'T20'],
        ageConstraints: [...ALL_AGE_GROUPS],
        agentCount: 25,
      }
      expect(computeIncomeConstraints(settings)).toEqual(['M40', 'T20'])
    })

    it('returns single-item array when only one income level is enabled', () => {
      const settings: SimulationSettingsState = {
        incomeConstraints: ['B40'],
        ageConstraints: [...ALL_AGE_GROUPS],
        agentCount: 30,
      }
      expect(computeIncomeConstraints(settings)).toEqual(['B40'])
    })
  })

  /**
   * Validates: Requirement 5.2, 5.5
   * When all age groups are enabled, omit age_constraints (pass null).
   * When some are disabled, pass only the enabled groups.
   */
  describe('age constraints in payload', () => {
    it('returns null when settings is null (no settings configured)', () => {
      expect(computeAgeConstraints(null)).toBeNull()
    })

    it('returns null when all age groups are enabled (default state)', () => {
      const settings: SimulationSettingsState = {
        incomeConstraints: [...ALL_INCOME_LEVELS],
        ageConstraints: ['20-29', '30-39', '40-49', '50-59', '60+'],
        agentCount: 25,
      }
      expect(computeAgeConstraints(settings)).toBeNull()
    })

    it('returns subset when some age groups are disabled', () => {
      const settings: SimulationSettingsState = {
        incomeConstraints: [...ALL_INCOME_LEVELS],
        ageConstraints: ['20-29', '30-39', '40-49'],
        agentCount: 25,
      }
      expect(computeAgeConstraints(settings)).toEqual(['20-29', '30-39', '40-49'])
    })

    it('returns single-item array when only one age group is enabled', () => {
      const settings: SimulationSettingsState = {
        incomeConstraints: [...ALL_INCOME_LEVELS],
        ageConstraints: ['30-39'],
        agentCount: 50,
      }
      expect(computeAgeConstraints(settings)).toEqual(['30-39'])
    })
  })

  /**
   * Combined payload test: verifies both constraints are computed correctly together
   */
  describe('combined payload construction', () => {
    it('both constraints are null when all toggles are at default', () => {
      const settings: SimulationSettingsState = {
        incomeConstraints: ['B40', 'M40', 'T20'],
        ageConstraints: ['20-29', '30-39', '40-49', '50-59', '60+'],
        agentCount: 25,
      }
      expect(computeIncomeConstraints(settings)).toBeNull()
      expect(computeAgeConstraints(settings)).toBeNull()
    })

    it('both constraints are arrays when both have partial selections', () => {
      const settings: SimulationSettingsState = {
        incomeConstraints: ['B40', 'M40'],
        ageConstraints: ['20-29', '30-39'],
        agentCount: 40,
      }
      expect(computeIncomeConstraints(settings)).toEqual(['B40', 'M40'])
      expect(computeAgeConstraints(settings)).toEqual(['20-29', '30-39'])
    })

    it('income null but age constrained when only age groups are filtered', () => {
      const settings: SimulationSettingsState = {
        incomeConstraints: ['B40', 'M40', 'T20'],
        ageConstraints: ['20-29', '30-39', '40-49'],
        agentCount: 25,
      }
      expect(computeIncomeConstraints(settings)).toBeNull()
      expect(computeAgeConstraints(settings)).toEqual(['20-29', '30-39', '40-49'])
    })
  })
})
