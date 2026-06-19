import type { ValidationResult } from '../../Tool.js'
import {
  getFsImplementation,
  resolveDeepestExistingAncestorSync,
} from '../../utils/fsOperations.js'
import { documentDerivativeMutationValidation } from '../WorkspaceToolAdapter/documentFormatGuards.js'

export function documentDerivativeMutationValidationForResolvedTarget(
  filePath: string,
): ValidationResult | null {
  const directValidation = documentDerivativeMutationValidation(filePath)
  if (directValidation !== null) return directValidation
  if (filePath.startsWith('\\\\') || filePath.startsWith('//')) return null

  const resolvedPath = resolveDeepestExistingAncestorSync(
    getFsImplementation(),
    filePath,
  )
  if (resolvedPath === undefined || resolvedPath === filePath) return null

  return documentDerivativeMutationValidation(resolvedPath)
}
