#!/usr/bin/env node
// SPDX-License-Identifier: Apache-2.0

import { mkdirSync, writeFileSync } from 'node:fs'
import { dirname } from 'node:path'

const [version, sha256, outputPath = 'Formula/kosax.rb'] = process.argv.slice(2)

if (!version || !sha256) {
  throw new Error('Usage: scripts/render-homebrew-formula.mjs <version> <sha256> [output-path]')
}

if (!/^\d+\.\d+\.\d+(-[0-9A-Za-z.-]+)?$/.test(version)) {
  throw new Error(`Invalid formula version: ${version}`)
}
if (!/^[0-9a-f]{64}$/.test(sha256)) {
  throw new Error(`Invalid SHA-256: ${sha256}`)
}

const formula = `# typed: false
# frozen_string_literal: true

class Kosax < Formula
  desc "Conversational multi-agent harness for Korean public-service channels"
  homepage "https://github.com/umyunsang/KOSAX"
  url "https://registry.npmjs.org/@umyunsang/kosax/-/kosax-${version}.tgz"
  sha256 "${sha256}"
  license "Apache-2.0"

  depends_on "node" => :build
  depends_on "uv"
  depends_on "oven-sh/bun/bun"

  def install
    libexec.install Dir["*"]
    bin.install_symlink libexec/"bin/kosax" => "kosax"
  end

  def caveats
    <<~EOS
      KOSAX uses Bun at runtime. If Homebrew cannot resolve the Bun dependency:
        brew tap oven-sh/bun
    EOS
  end

  test do
    assert_match version.to_s, shell_output("#{bin}/kosax --version")
  end
end
`

mkdirSync(dirname(outputPath), { recursive: true })
writeFileSync(outputPath, formula)
console.log(`render-homebrew-formula: wrote ${outputPath}`)
