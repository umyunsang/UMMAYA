# typed: false
# frozen_string_literal: true

class Kosax < Formula
  desc "Conversational multi-agent harness for Korean public-service channels"
  homepage "https://github.com/umyunsang/KOSAX"
  url "https://registry.npmjs.org/@umyunsang/kosax/-/kosax-0.1.0.tgz"
  sha256 "daf3fe77898d9936baf542fa34e6b37a10cc4a189f07ff8f1a5a2e732bd44c8b"
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
