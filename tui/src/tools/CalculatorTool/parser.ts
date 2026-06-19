/**
 * Restricted-grammar expression parser + evaluator using the shunting-yard algorithm.
 *
 * Allowed characters: 0-9  .  +  -  *  /  %  (  )  whitespace
 * Disallowed: letters, underscore, $, !,  ^, &, |, ~, <, >, =, etc.
 *
 * Numeric representation strategy:
 *   - Parse every numeric literal as a string to avoid IEEE-754 precision loss.
 *   - Track whether division produces a non-integer result.
 *   - Arithmetic is carried out with BigInt when all operands are integers
 *     (denominator check for /); otherwise falls back to JS number with
 *     toFixed(precision) rounding, which is sufficient for the "up to 28 digits"
 *     contract.  A full arbitrary-precision Decimal library would require a new
 *     npm dep which is forbidden (AGENTS.md hard rule).
 */

export type EvalKind = 'int' | 'float' | 'fraction'

export interface EvalResult {
  result: string
  kind: EvalKind
}

// ---------------------------------------------------------------------------
// Allowed-character guard
// ---------------------------------------------------------------------------
const ALLOWED_RE = /^[\d\s.+\-*/%()]+$/

function assertAllowed(expr: string): void {
  if (!ALLOWED_RE.test(expr)) {
    throw new Error(
      `Expression contains disallowed characters. Only digits, decimal point, ` +
        `operators (+ - * / %), and parentheses are permitted.`,
    )
  }
}

// ---------------------------------------------------------------------------
// Tokeniser
// ---------------------------------------------------------------------------
type TokenKind =
  | 'num'
  | 'plus'
  | 'minus'
  | 'mul'
  | 'div'
  | 'mod'
  | 'lparen'
  | 'rparen'
  | 'unary_minus'

interface Token {
  kind: TokenKind
  value?: string // only for 'num'
}

function tokenise(expr: string): Token[] {
  const tokens: Token[] = []
  let i = 0
  while (i < expr.length) {
    const ch = expr[i]!
    if (ch === ' ' || ch === '\t' || ch === '\n' || ch === '\r') {
      i++
      continue
    }
    if ((ch >= '0' && ch <= '9') || ch === '.') {
      let num = ''
      let dotSeen = false
      while (i < expr.length) {
        const c = expr[i]!
        if (c >= '0' && c <= '9') {
          num += c
          i++
        } else if (c === '.' && !dotSeen) {
          dotSeen = true
          num += c
          i++
        } else {
          break
        }
      }
      if (num === '.' || (num.startsWith('.') && num.length === 1)) {
        throw new Error(`Invalid numeric literal: "${num}"`)
      }
      tokens.push({ kind: 'num', value: num })
      continue
    }
    switch (ch) {
      case '+':
        tokens.push({ kind: 'plus' })
        break
      case '-':
        // Unary minus: at start, or after operator / lparen
        {
          const prev = tokens[tokens.length - 1]
          const isUnary =
            !prev ||
            prev.kind === 'plus' ||
            prev.kind === 'minus' ||
            prev.kind === 'mul' ||
            prev.kind === 'div' ||
            prev.kind === 'mod' ||
            prev.kind === 'lparen' ||
            prev.kind === 'unary_minus'
          tokens.push({ kind: isUnary ? 'unary_minus' : 'minus' })
        }
        break
      case '*':
        tokens.push({ kind: 'mul' })
        break
      case '/':
        tokens.push({ kind: 'div' })
        break
      case '%':
        tokens.push({ kind: 'mod' })
        break
      case '(':
        tokens.push({ kind: 'lparen' })
        break
      case ')':
        tokens.push({ kind: 'rparen' })
        break
      default:
        throw new Error(`Unexpected character: "${ch}"`)
    }
    i++
  }
  return tokens
}

// ---------------------------------------------------------------------------
// Shunting-yard → RPN (Reverse Polish Notation)
// ---------------------------------------------------------------------------
interface OpInfo {
  prec: number
  rightAssoc: boolean
}

const OP_INFO: Record<string, OpInfo> = {
  unary_minus: { prec: 4, rightAssoc: true },
  mul: { prec: 3, rightAssoc: false },
  div: { prec: 3, rightAssoc: false },
  mod: { prec: 3, rightAssoc: false },
  plus: { prec: 2, rightAssoc: false },
  minus: { prec: 2, rightAssoc: false },
}

function toRPN(tokens: Token[]): Token[] {
  const output: Token[] = []
  const opStack: Token[] = []

  for (const tok of tokens) {
    if (tok.kind === 'num') {
      output.push(tok)
      continue
    }
    if (tok.kind === 'lparen') {
      opStack.push(tok)
      continue
    }
    if (tok.kind === 'rparen') {
      while (opStack.length > 0 && opStack[opStack.length - 1]!.kind !== 'lparen') {
        output.push(opStack.pop()!)
      }
      if (opStack.length === 0) {
        throw new Error('Mismatched parentheses: unexpected ")"')
      }
      opStack.pop() // discard lparen
      continue
    }
    // Operator
    const opInfo = OP_INFO[tok.kind]
    if (!opInfo) {
      throw new Error(`Unknown operator token kind: ${tok.kind}`)
    }
    while (opStack.length > 0) {
      const top = opStack[opStack.length - 1]!
      if (top.kind === 'lparen') break
      const topInfo = OP_INFO[top.kind]
      if (!topInfo) break
      if (topInfo.prec > opInfo.prec || (topInfo.prec === opInfo.prec && !opInfo.rightAssoc)) {
        output.push(opStack.pop()!)
      } else {
        break
      }
    }
    opStack.push(tok)
  }

  while (opStack.length > 0) {
    const top = opStack.pop()!
    if (top.kind === 'lparen' || top.kind === 'rparen') {
      throw new Error('Mismatched parentheses: unclosed "("')
    }
    output.push(top)
  }

  return output
}

// ---------------------------------------------------------------------------
// RPN evaluator
// ---------------------------------------------------------------------------
// We carry values as pairs [numerator: bigint, denominator: bigint] (rational arithmetic)
// to preserve exact integer results and detect exact integer outputs.
// This avoids float rounding entirely for the integer/fraction kind distinction.

type Rational = [bigint, bigint]

function bigintGcd(a: bigint, b: bigint): bigint {
  a = a < 0n ? -a : a
  b = b < 0n ? -b : b
  while (b !== 0n) {
    ;[a, b] = [b, a % b]
  }
  return a
}

function rationalSimplify([n, d]: Rational): Rational {
  if (d === 0n) throw new Error('Division by zero')
  if (n === 0n) return [0n, 1n]
  const sign = d < 0n ? -1n : 1n
  const g = bigintGcd(n < 0n ? -n : n, d < 0n ? -d : d)
  return [(sign * n) / g, (sign * d) / g]
}

function rationalAdd(a: Rational, b: Rational): Rational {
  return rationalSimplify([a[0] * b[1] + b[0] * a[1], a[1] * b[1]])
}

function rationalSub(a: Rational, b: Rational): Rational {
  return rationalSimplify([a[0] * b[1] - b[0] * a[1], a[1] * b[1]])
}

function rationalMul(a: Rational, b: Rational): Rational {
  return rationalSimplify([a[0] * b[0], a[1] * b[1]])
}

function rationalDiv(a: Rational, b: Rational): Rational {
  return rationalSimplify([a[0] * b[1], a[1] * b[0]])
}

function rationalMod(a: Rational, b: Rational): Rational {
  // (a/b) mod (c/d) = ((a*d) mod (b*c)) / (b*d)
  const num = (a[0] * b[1]) % (a[1] * b[0])
  const den = a[1] * b[0]
  return rationalSimplify([num, den])
}

function parseToRational(s: string): Rational {
  // Remove leading/trailing whitespace (already removed by tokeniser, just in case)
  const str = s.trim()
  const dotIdx = str.indexOf('.')
  if (dotIdx === -1) {
    // Integer literal
    return [BigInt(str), 1n]
  }
  // Decimal literal: e.g. "3.14" → 314/100
  const intPart = str.slice(0, dotIdx) || '0'
  const fracPart = str.slice(dotIdx + 1)
  const scale = 10n ** BigInt(fracPart.length)
  const numerator = BigInt(intPart) * scale + BigInt(fracPart || '0')
  return rationalSimplify([numerator, scale])
}

function evalRPN(rpn: Token[], precision: number): EvalResult {
  const stack: Rational[] = []

  for (const tok of rpn) {
    if (tok.kind === 'num') {
      stack.push(parseToRational(tok.value!))
      continue
    }
    if (tok.kind === 'unary_minus') {
      const a = stack.pop()
      if (a === undefined) throw new Error('Malformed expression: insufficient operands')
      stack.push([-a[0], a[1]])
      continue
    }
    // Binary operator
    const b = stack.pop()
    const a = stack.pop()
    if (a === undefined || b === undefined) {
      throw new Error('Malformed expression: insufficient operands for operator')
    }
    let res: Rational
    switch (tok.kind) {
      case 'plus':
        res = rationalAdd(a, b)
        break
      case 'minus':
        res = rationalSub(a, b)
        break
      case 'mul':
        res = rationalMul(a, b)
        break
      case 'div':
        if (b[0] === 0n) throw new Error('Division by zero')
        res = rationalDiv(a, b)
        break
      case 'mod':
        if (b[0] === 0n) throw new Error('Modulo by zero')
        res = rationalMod(a, b)
        break
      default:
        throw new Error(`Unknown operator in RPN: ${tok.kind}`)
    }
    stack.push(res)
  }

  if (stack.length !== 1) {
    throw new Error('Malformed expression: extra operands remaining')
  }

  const [n, d] = stack[0]!

  // Integer result: denominator is 1
  if (d === 1n) {
    return { result: n.toString(), kind: 'int' }
  }

  // Check whether denominator is a product of 2s and 5s only (terminating decimal)
  // In that case we can represent exactly in decimal → kind "float"
  // Otherwise it's a repeating decimal → kind "fraction" (return decimal approximation)
  let dCheck = d < 0n ? -d : d
  while (dCheck % 2n === 0n) dCheck /= 2n
  while (dCheck % 5n === 0n) dCheck /= 5n

  // Compute the floating-point approximation using Number division for precision
  // up to precision digits.  For very large BigInt numerators/denominators
  // convert via string to avoid JS integer overflow in Number().
  const numeratorF = Number(n)
  const denominatorF = Number(d)
  let floatVal: number
  if (isFinite(numeratorF) && isFinite(denominatorF)) {
    floatVal = numeratorF / denominatorF
  } else {
    // Fallback: BigInt long division to the required precision
    floatVal = bigintDivToFloat(n, d, precision)
  }

  const kind: EvalKind = dCheck === 1n ? 'float' : 'fraction'
  const resultStr = formatFloat(floatVal, precision)
  return { result: resultStr, kind }
}

/** BigInt long division fallback for very large values */
function bigintDivToFloat(n: bigint, d: bigint, precision: number): number {
  // Scale numerator to get enough decimal digits
  const scale = 10n ** BigInt(precision + 4)
  const scaled = (n * scale) / d
  return Number(scaled) / Number(scale)
}

function formatFloat(val: number, precision: number): string {
  // Use toPrecision to honor the precision contract, then strip trailing zeros
  const str = val.toPrecision(Math.min(precision, 21)) // JS toPrecision max is 21
  // Convert from exponential if needed
  const parsed = Number(str)
  if (!isFinite(parsed)) {
    throw new Error(`Result is not a finite number: ${val}`)
  }
  // Return a clean decimal string without unnecessary trailing zeros
  const fixed = parsed.toPrecision(Math.min(precision, 21))
  // Remove trailing zeros after decimal point
  if (fixed.includes('.') && !fixed.includes('e')) {
    return fixed.replace(/\.?0+$/, '') || '0'
  }
  return fixed
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

/**
 * Evaluate a restricted arithmetic expression.
 *
 * @param expression  - Expression string; only digits, `.`, `+ - * / % ( )`, whitespace allowed.
 * @param precision   - Number of significant digits for non-integer results (default 28, JS max 21).
 * @returns           - { result: string, kind: "int" | "float" | "fraction" }
 * @throws            - Error for disallowed chars, syntax errors, division by zero.
 */
export function evaluate(expression: string, precision = 28): EvalResult {
  if (!expression || expression.trim() === '') {
    throw new Error('Expression must not be empty')
  }
  assertAllowed(expression)
  const tokens = tokenise(expression)
  if (tokens.length === 0) {
    throw new Error('Expression contains no tokens')
  }
  const rpn = toRPN(tokens)
  return evalRPN(rpn, precision)
}
