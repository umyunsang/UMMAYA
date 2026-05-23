# frozen_string_literal: true

cask "ummaya" do
  arch arm: "arm64", intel: "x64"

  version "0.1.16"
  sha256 arm:   "66704302a670fa8efcbba36d7cbd6927d045179db46a51998106bfa202625ecb",
         intel: "9ffe3b85d2e3da65434c1000bcd8831bccc8120ee755ad8faedf6c6a1262b31d"

  url "https://github.com/umyunsang/UMMAYA/releases/download/v#{version}/ummaya-#{version}-macos-#{arch}.tar.gz"
  name "UMMAYA"
  desc "Conversational multi-agent harness for Korean public-service channels"
  homepage "https://github.com/umyunsang/UMMAYA"

  livecheck do
    url :url
    regex(/^v?(\d+(?:\.\d+)+)$/i)
    strategy :github_latest
  end

  depends_on :macos
  depends_on formula: "uv"

  binary "ummaya"

  postflight do
    system_command "/usr/bin/xattr",
                   args: ["-dr", "com.apple.quarantine", staged_path.to_s],
                   sudo: false
  end

  zap trash: "~/.ummaya"
end
