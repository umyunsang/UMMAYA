# frozen_string_literal: true

cask "ummaya" do
  arch arm: "arm64", intel: "x64"

  version "0.1.16"
  sha256 arm:   "8cf564d9c0ab7a695a0f34968911e2b9403fda8cc2de9ac053731a04e3573900",
         intel: "e0fcf2e7a51689a9b06b185cc47353cb09f40533c8a7805b938ad6366a64ece4"

  url "https://github.com/umyunsang/UMMAYA/releases/download/v#{version}/ummaya-#{version}-macos-#{arch}.tar.gz",
      verified: "github.com/umyunsang/UMMAYA/"
  name "UMMAYA"
  desc "Conversational multi-agent harness for Korean public-service channels"
  homepage "https://github.com/umyunsang/UMMAYA"

  depends_on formula: "uv"

  binary "ummaya"

  zap trash: "~/.ummaya"
end
