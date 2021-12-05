let pkgs = import <nixpkgs> {};
    mach-nix = import (builtins.fetchGit {
      url = "https://github.com/DavHau/mach-nix";
      ref = "refs/tags/3.3.0";
    }) {
      inherit pkgs;
    };
    python-env = mach-nix.mkPython {
      requirements = ''
        Babel==2.9.1
        Pillow==8.3.2
        PyPDF2==1.26.0
        Pygments>=2.8.0
        fonttools==4.14.0
        langcodes==2.0.0
        lxml==4.6.3
        pyquery==1.4.1
        pytz==2020.1
      '';
      packagesExtra = let
        pygmentExtension = (name: sha256: mach-nix.buildPythonPackage {
          src = pkgs.fetchFromGitHub {
            owner = "vincentbernat";
            repo = "pygments-${name}";
            rev = "master";
            inherit sha256;
          };
        });
      in [
        (mach-nix.buildPythonPackage {
          src = pkgs.fetchFromGitHub {
            owner = "vincentbernat";
            repo = "hyde";
            rev = "vbe/master";
            sha256 = "sha256-MtGSUp1ZSbTipsdMLh57O+yZSOS37s6g60u2A1uyUzQ=";
          };
          requirementsExtra = "python-dateutil>=2.8";
        })
        (pygmentExtension "haproxy" "sha256-DzSFS+tKBToFfh2gbKjapmEAZNLp24ufIOvAv9khcQo=")
        (pygmentExtension "ios"     "sha256-Go7x8gZDu55M43/bTE3vUp/l6OGoQkESyguMrH/4yJU=")
        (pygmentExtension "junos"   "sha256-aMwP/ecfawuVRUP7AY3eIxLqZK5rVY45i3yRr9qYW2k=")
      ];
    };
in
pkgs.mkShell {
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
}
