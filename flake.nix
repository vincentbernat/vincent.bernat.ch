{
  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs";
    flake-utils.url = "github:numtide/flake-utils";
    pypi-deps-db = {
      url = "github:DavHau/pypi-deps-db";
      flake = false;
    };
    mach-nix = {
      url = "github:DavHau/mach-nix?ref=3.3.0";
      inputs = {
        nixpkgs.follows = "nixpkgs";
        flake-utils.follows = "flake-utils";
        pypi-deps-db.follows = "pypi-deps-db";
      };
    };
    hyde = {
      url = "github:vincentbernat/hyde?ref=vbe/master";
      flake = false;
    };
    pygments-haproxy = {
      url = "github:vincentbernat/pygments-haproxy";
      flake = false;
    };
    pygments-ios = {
      url = "github:vincentbernat/pygments-ios";
      flake = false;
    };
    pygments-junos = {
      url = "github:vincentbernat/pygments-junos";
      flake = false;
    };
  };
  outputs = { self, flake-utils, ... }@inputs:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = inputs.nixpkgs.legacyPackages."${system}";
        mach-nix = inputs.mach-nix.lib."${system}";
        pygments-version = "2.10.0";
        python-env = mach-nix.mkPython {
          requirements = ''
            Babel==2.9.1
            Pillow==8.3.2
            PyPDF2==1.26.0
            Pygments==${pygments-version}
            fonttools==4.14.0
            langcodes==2.0.0
            lxml==4.6.3
            pyquery==1.4.1
          '';
          packagesExtra = let
            pygmentsPackage = name:
              mach-nix.buildPythonPackage {
                src = inputs."pygments-${name}";
                requirementsExtra = "Pygments==${pygments-version}";
              };
          in [
            (mach-nix.buildPythonPackage {
              src = inputs.hyde;
              requirementsExtra = ''
                python-dateutil>=2.8
                Pygments==${pygments-version}
              '';
            })
            (pygmentsPackage "haproxy")
            (pygmentsPackage "ios")
            (pygmentsPackage "junos")
          ];
        };
      in {
        packages.iosevka = pkgs.iosevka.override {
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
        devShell = pkgs.mkShell {
          name = "www";
          buildInputs = [
            python-env

            # Build
            pkgs.git
            pkgs.git-annex
            pkgs.nodejs
            pkgs.openssl
            pkgs.python3Packages.invoke
            pkgs.yarn
            pkgs.less

            # Deploy
            pkgs.rsync
            pkgs.openssh

            # Images
            pkgs.libavif
            (pkgs.jpegoptim.override { libjpeg = pkgs.mozjpeg; })
            pkgs.pngquant
            pkgs.libwebp
            pkgs.ffmpeg

            # Tools
            pkgs.linkchecker
            (pkgs.goaccess.overrideAttrs (old: {
              patches = (old.patches or []) ++ [
                (pkgs.fetchpatch {
                  url = "https://github.com/allinurl/goaccess/pull/2126.patch";
                  sha256 = "sha256-Csb9ooM933m3bcx61LEx+VkmnfzajOMUnAhkcnDPgv4=";
                })
              ];
            }))
          ];
        };
      });
}
