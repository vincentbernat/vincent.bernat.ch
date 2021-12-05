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
      packagesExtra = [
        (mach-nix.buildPythonPackage {
          src = "https://github.com/vincentbernat/hyde/archive/refs/heads/vbe/master.tar.gz";
          requirementsExtra = "python-dateutil>=2.8";
        })
        https://github.com/vincentbernat/pygments-haproxy/archive/refs/heads/master.tar.gz
        https://github.com/vincentbernat/pygments-ios/archive/refs/heads/master.tar.gz
        https://github.com/vincentbernat/pygments-junos/archive/refs/heads/master.tar.gz
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
    pkgs.rsync
    pkgs.yarn
    pkgs.less

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
