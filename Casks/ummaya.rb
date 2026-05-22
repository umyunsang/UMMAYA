# frozen_string_literal: true

cask "ummaya" do
  version "0.1.14"
  sha256 "2b757862d71e9bc1d5c3497aa7548e9ac05c4707f48a554fbc7af72ae5d7e690"

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
