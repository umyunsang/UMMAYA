#!/usr/bin/env node
// SPDX-License-Identifier: Apache-2.0

import { mkdirSync, writeFileSync } from 'node:fs'
import { dirname } from 'node:path'

const [version, arm64Sha256, x64Sha256, outputPath = 'Casks/ummaya.rb'] = process.argv.slice(2)

if (!version || !arm64Sha256 || !x64Sha256) {
  throw new Error(
    'Usage: scripts/render-homebrew-cask.mjs <version> <arm64-sha256> <x64-sha256> [output-path]',
  )
}

if (!/^\d+\.\d+\.\d+(-[0-9A-Za-z.-]+)?$/.test(version)) {
  throw new Error(`Invalid cask version: ${version}`)
}
for (const [label, sha256] of [
  ['arm64', arm64Sha256],
  ['x64', x64Sha256],
]) {
  if (!/^[0-9a-f]{64}$/.test(sha256)) {
    throw new Error(`Invalid ${label} SHA-256: ${sha256}`)
  }
}

const cask = `# frozen_string_literal: true

cask "ummaya" do
  arch arm: "arm64", intel: "x64"

  version "${version}"
  sha256 arm:   "${arm64Sha256}",
         intel: "${x64Sha256}"

  url "https://github.com/umyunsang/UMMAYA/releases/download/v#{version}/ummaya-#{version}-macos-#{arch}.tar.gz",
      verified: "github.com/umyunsang/UMMAYA/"
  name "UMMAYA"
  desc "Conversational multi-agent harness for Korean public-service channels"
  homepage "https://github.com/umyunsang/UMMAYA"

  depends_on formula: "uv"

  binary "ummaya"

  postflight do
    system_command "/usr/bin/xattr",
                   args: ["-dr", "com.apple.quarantine", "#{staged_path}"],
                   sudo: false
  end

  zap trash: "~/.ummaya"
end
`

mkdirSync(dirname(outputPath), { recursive: true })
writeFileSync(outputPath, cask)
console.log(`render-homebrew-cask: wrote ${outputPath}`)
