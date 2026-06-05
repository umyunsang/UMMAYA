import { describe, expect, test } from 'bun:test'

import { validatePermissionRule } from '../../../src/utils/settings/permissionValidation'

describe('validatePermissionRule', () => {
  test('accepts UMMAYA lowercase primitive and adapter permission rules', () => {
    expect(validatePermissionRule('document')).toEqual({ valid: true })
    expect(validatePermissionRule('document_render')).toEqual({ valid: true })
    expect(validatePermissionRule('workspace_glob')).toEqual({ valid: true })
  })
})
