// SPDX-License-Identifier: Apache-2.0

import { readdirSync, readFileSync, statSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'bun:test'
import * as ts from 'typescript'

type Offender = {
  file: string
  line: number
  column: number
  flag: string
  source: string
}

const tuiRoot = dirname(dirname(dirname(fileURLToPath(import.meta.url))))
const sourceRoot = join(tuiRoot, 'src')

function collectSourceFiles(directory: string): string[] {
  const files: string[] = []
  for (const name of readdirSync(directory)) {
    const path = join(directory, name)
    const stats = statSync(path)
    if (stats.isDirectory()) {
      files.push(...collectSourceFiles(path))
    } else if (/\.(ts|tsx)$/.test(name)) {
      files.push(path)
    }
  }
  return files
}

function containsNode(parent: ts.Node, child: ts.Node, sourceFile: ts.SourceFile): boolean {
  return (
    child.getStart(sourceFile) >= parent.getStart(sourceFile) &&
    child.getEnd() <= parent.getEnd()
  )
}

function isFeatureCall(node: ts.Node): node is ts.CallExpression {
  return (
    ts.isCallExpression(node) &&
    ts.isIdentifier(node.expression) &&
    node.expression.text === 'feature' &&
    node.arguments.length > 0 &&
    ts.isStringLiteralLike(node.arguments[0])
  )
}

function importsBunBundleFeature(sourceFile: ts.SourceFile): boolean {
  return sourceFile.statements.some(
    statement =>
      ts.isImportDeclaration(statement) &&
      ts.isStringLiteral(statement.moduleSpecifier) &&
      statement.moduleSpecifier.text === 'bun:bundle' &&
      statement.importClause?.namedBindings !== undefined &&
      ts.isNamedImports(statement.importClause.namedBindings) &&
      statement.importClause.namedBindings.elements.some(
        element => element.name.text === 'feature',
      ),
  )
}

function isInsideAllowedFeatureCondition(
  node: ts.Node,
  parents: ts.Node[],
  sourceFile: ts.SourceFile,
): boolean {
  for (let index = parents.length - 1; index >= 0; index -= 1) {
    const parent = parents[index]
    if (ts.isIfStatement(parent) && containsNode(parent.expression, node, sourceFile)) {
      return true
    }
    if (
      ts.isConditionalExpression(parent) &&
      containsNode(parent.condition, node, sourceFile)
    ) {
      return true
    }
  }
  return false
}

function collectForbiddenFeatureCalls(): Offender[] {
  const offenders: Offender[] = []
  for (const file of collectSourceFiles(sourceRoot)) {
    const text = readFileSync(file, 'utf8')
    if (!text.includes('bun:bundle')) continue

    const sourceFile = ts.createSourceFile(
      file,
      text,
      ts.ScriptTarget.Latest,
      true,
      file.endsWith('.tsx') ? ts.ScriptKind.TSX : ts.ScriptKind.TS,
    )
    if (!importsBunBundleFeature(sourceFile)) continue

    const parents: ts.Node[] = []
    const visit = (node: ts.Node): void => {
      if (
        isFeatureCall(node) &&
        !isInsideAllowedFeatureCondition(node, parents, sourceFile)
      ) {
        const position = sourceFile.getLineAndCharacterOfPosition(
          node.getStart(sourceFile),
        )
        const flag = node.arguments[0]
        offenders.push({
          file: file.slice(tuiRoot.length + 1),
          line: position.line + 1,
          column: position.character + 1,
          flag: ts.isStringLiteralLike(flag) ? flag.text : '<non-literal>',
          source: text.split(/\r?\n/)[position.line]?.trim() ?? '',
        })
      }

      parents.push(node)
      ts.forEachChild(node, visit)
      parents.pop()
    }
    visit(sourceFile)
  }
  return offenders
}

describe('bun:bundle feature syntax', () => {
  it('keeps feature calls directly inside if statements or ternary conditions', () => {
    expect(collectForbiddenFeatureCalls()).toEqual([])
  })
})
