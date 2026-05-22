# frozen_string_literal: true

cask "ummaya" do
  version "0.1.13"
  sha256 "691fdde26626f97f1bcc13b1c519e93bb029b4625c82d07f4fe981b3d3a2b566"

  url "https://registry.npmjs.org/ummaya/-/ummaya-#{version}.tgz",
      verified: "registry.npmjs.org/ummaya/"
  name "UMMAYA"
  desc "Conversational multi-agent harness for Korean public-service channels"
  homepage "https://github.com/umyunsang/UMMAYA"

  depends_on formula: "oven-sh/bun/bun"
  depends_on formula: "uv"

  binary "ummaya"

  preflight do
    install_args = ["install", "--production", "--cwd", "#{staged_path}/package"]
    install_args << if File.exist?("#{staged_path}/package/bun.lock")
      "--frozen-lockfile"
    else
      "--no-save"
    end

    system_command "#{HOMEBREW_PREFIX}/opt/bun/bin/bun",
                   args: install_args

    wrapper = staged_path/"ummaya"
    wrapper.write <<~SH
      #!/bin/bash
      export PATH="#{HOMEBREW_PREFIX}/opt/bun/bin:#{HOMEBREW_PREFIX}/opt/uv/bin:$PATH"
      exec "#{HOMEBREW_PREFIX}/opt/bun/bin/bun" "#{staged_path}/package/bin/ummaya" "$@"
    SH
    FileUtils.chmod 0755, wrapper
  end

  zap trash: "~/.ummaya"
end
