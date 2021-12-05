let pkgs = import <nixpkgs> {};
    mach-nix = import (pkgs.fetchFromGitHub {
      owner = "DavHau"; repo = "mach-nix";
      rev = "3.3.0";
      sha256 = "sha256-RvbFjxnnY/+/zEkvQpl85MICmyp9p2EoncjuN80yrYA=";
    }) {
      inherit pkgs;
      pypiDataRev = "99799f6300b2dc4a4063dc3da032f5f169709567";
      pypiDataSha256 = "0kacxgr7cybd0py8d3mshr9h3wab9x3fvrlpr2fd240xg0v2k5gm";
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
      '';
      packagesExtra = let
        pygmentExtension = (name: sha256: mach-nix.buildPythonPackage {
          src = pkgs.fetchFromGitHub {
            owner = "vincentbernat"; repo = "pygments-${name}";
            rev = "master";
            inherit sha256;
          };
        });
      in [
        (mach-nix.buildPythonPackage {
          src = pkgs.fetchFromGitHub {
            owner = "vincentbernat"; repo = "hyde";
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
