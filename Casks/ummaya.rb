# frozen_string_literal: true

cask "ummaya" do
  arch arm: "arm64", intel: "x64"

  version "0.1.18"
  sha256 arm:   "85da24e2240f0fcbf7e4c6098f36db74bb7e4dcaebe138237644167131c4ef0f",
         intel: "23793a77722904e368cfe241c3d8039b382296c65e3482981efcfa4d664d1f15"

  url "https://ummaya-docs.pages.dev/downloads/homebrew/v#{version}/ummaya-#{version}-macos-#{arch}.tar.gz"
  name "UMMAYA"
  desc "Conversational multi-agent harness for Korean public-service channels"
  homepage "https://ummaya-docs.pages.dev/"

  livecheck do
    url "https://ummaya-docs.pages.dev/downloads/homebrew/latest.json"
    strategy :json do |json|
      json["version"]
    end
  end

  depends_on :macos
  depends_on formula: "uv"

  binary "ummaya"

  zap trash: "~/.ummaya"
end
