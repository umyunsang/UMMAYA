import { describe, test } from 'bun:test'
import {
  expectDanglingFileWriteSymlinkRejected,
  expectFileEditSymlinkAliasRejected,
  expectFileWriteSymlinkAliasRejected,
  expectNonDocumentSymlinkAliasMutationAllowed,
  expectNotebookSymlinkAliasRejected,
} from './documentMutationGuardAssertions.js'
import {
  expectDirectFileEditHelperRejected,
  expectDirectFileWriteHelperRejected,
  expectDirectNotebookEditHelperRejected,
  expectRawDocumentMutationValidationBlocked,
} from './documentMutationGuardDirectAssertions.js'

describe('document file write bypass policy', () => {
  test('rejects_direct_file_write_helper_for_document_derivatives_when_validation_is_skipped', async () => {
    await expectDirectFileWriteHelperRejected()
  })

  test('rejects_direct_file_edit_helper_for_document_derivatives_when_validation_is_skipped', async () => {
    await expectDirectFileEditHelperRejected()
  })

  test('rejects_direct_notebook_edit_helper_for_document_derivatives_when_validation_is_skipped', async () => {
    await expectDirectNotebookEditHelperRejected()
  })

  test('rejects_file_write_symlink_alias_to_document_derivative_and_preserves_target_bytes', async () => {
    await expectFileWriteSymlinkAliasRejected()
  })

  test('rejects_file_write_dangling_symlink_alias_to_document_derivative_without_creating_target', async () => {
    await expectDanglingFileWriteSymlinkRejected()
  })

  test('rejects_file_edit_symlink_alias_to_document_derivative_and_preserves_target_bytes', async () => {
    await expectFileEditSymlinkAliasRejected()
  })

  test('rejects_notebook_edit_symlink_alias_to_document_derivative_and_preserves_target_bytes', async () => {
    await expectNotebookSymlinkAliasRejected()
  })

  test('allows_file_write_and_edit_symlink_alias_to_non_document_text_target', async () => {
    await expectNonDocumentSymlinkAliasMutationAllowed()
  })

  test('blocks_raw_file_write_for_document_derivative_mutation', async () => {
    await expectRawDocumentMutationValidationBlocked()
  })
})
