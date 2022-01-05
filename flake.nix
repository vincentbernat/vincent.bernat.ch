{
  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs";
    flake-utils.url = "github:numtide/flake-utils";
  };
  outputs = { self, flake-utils, ... }@inputs:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = inputs.nixpkgs.legacyPackages."${system}";
        python-env = pkgs.poetry2nix.mkPoetryEnv {
          projectDir = ./.;
          overrides = pkgs.poetry2nix.overrides.withDefaults (self: super: {
            # For langcodes
            marisa-trie-m = super.marisa-trie-m.overridePythonAttrs (
              old: { buildInputs = (old.buildInputs or [ ]) ++ [ self.pytest-runner ]; }
            );
          });
        };
      in
      {
        apps = {
          linkchecker = pkgs.linkchecker;
          goaccess = (pkgs.goaccess.overrideAttrs (old: {
            patches = (old.patches or [ ]) ++ [
              (pkgs.fetchpatch {
                url = "https://github.com/allinurl/goaccess/pull/2126.patch";
                sha256 = "sha256-Csb9ooM933m3bcx61LEx+VkmnfzajOMUnAhkcnDPgv4=";
              })
            ];
          }));
          yarn = pkgs.yarn;
          poetry = pkgs.poetry;
        };
        packages = {
          iosevka = pkgs.iosevka.override {
            set = "custom";
            privateBuildPlan = {
              family = "Iosevka Custom";
              spacing = "term";
              serifs = "sans";
              no-ligation = true;
              no-cv-ss = true;
              variants = {
                inherits = "ss05";
                design = {
                  ampersand = "closed";
                  number-sign = "upright";
                  zero = "dotted";
                };
              };
              slopes.upright = {
                angle = 0;
                shape = "upright";
                menu = "upright";
                css = "normal";
              };
              weights = {
                regular = {
                  shape = 350;
                  menu = 400;
                  css = 400;
                };
              };
              metric-override = {
                cap = 790;
                xheight = 570;
              };
            };
          };
        };
        devShell = python-env.env.overrideAttrs (oldAttrs: {
          name = "www";
          buildInputs = [
            # Build
            pkgs.git
            pkgs.git-annex
            pkgs.nodejs
            pkgs.openssl
            pkgs.python3Packages.invoke

            # Images
            pkgs.libavif
            (pkgs.jpegoptim.override { libjpeg = pkgs.mozjpeg; })
            pkgs.pngquant
            pkgs.libwebp
            pkgs.ffmpeg
          ];
        });
      });
}
