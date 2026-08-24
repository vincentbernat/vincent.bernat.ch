{
  inputs = {
    nixpkgs.url = "nixpkgs";
    flake-utils.url = "github:numtide/flake-utils";
    pyproject-nix = {
      url = "github:pyproject-nix/pyproject.nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    uv2nix = {
      url = "github:pyproject-nix/uv2nix";
      inputs.pyproject-nix.follows = "pyproject-nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    pyproject-build-systems = {
      url = "github:pyproject-nix/build-system-pkgs";
      inputs.pyproject-nix.follows = "pyproject-nix";
      inputs.uv2nix.follows = "uv2nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    merriweather = {
      url = "github:SorkinType/Merriweather";
      flake = false;
    };
    # hyde = {
    #   url = "path:/home/bernat/code/perso/hyde";
    #   flake = false;
    # };
  };
  outputs = { self, flake-utils, ... }@inputs:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = import inputs.nixpkgs {
          inherit system;
        };
        l = pkgs.lib // builtins;

        python = pkgs.python3;
        pythonEnv =
          let
            pythonBase = pkgs.callPackage inputs.pyproject-nix.build.packages {
              inherit python;
            };
            workspace = inputs.uv2nix.lib.workspace.loadWorkspace { workspaceRoot = ./.; };
            overlay = workspace.mkPyprojectOverlay {
              sourcePreference = "wheel";
            };
            hacks = pkgs.callPackage inputs.pyproject-nix.build.hacks { };
            buildSystemOverrides =
              let
                overrides = {
                  commando.setuptools = [ ];
                  fswrap.setuptools = [ ];
                  pygments-haproxy.setuptools = [ ];
                  pygments-ios.setuptools = [ ];
                  pygments-junos.setuptools = [ ];
                  typogrify.setuptools = [ ];
                  markupsafe.setuptools = [ ];
                  markdown.setuptools = [ ];
                };
              in
              final: prev: l.mapAttrs
                (
                  name: spec: prev.${name}.overrideAttrs (old: {
                    nativeBuildInputs = old.nativeBuildInputs ++ final.resolveBuildSystem spec;
                  })
                )
                overrides;
            moreOverrides = final: prev: {
              # lxml from nixpkgs
              lxml = hacks.nixpkgsPrebuilt {
                from = python.pkgs.lxml;
                prev = prev.lxml;
              };
              # No need for tools from fonttools (we pull the Nix version for that)
              fonttools = prev.fonttools.overrideAttrs (old: {
                postInstall = (old.postInstall or "") + ''
                  rm -rf "$out/bin"
                '';
              });
            } // l.optionalAttrs (inputs ? hyde) {
              hyde = prev.hyde.overrideAttrs (_: {
                src = inputs.hyde;
              });
            };
            pythonSet = pythonBase.overrideScope (
              l.composeManyExtensions [
                inputs.pyproject-build-systems.overlays.wheel
                overlay
                buildSystemOverrides
                moreOverrides
              ]
            );
          in
          pythonSet.mkVirtualEnv "www-env" workspace.deps.default;
        nodeEnv = pkgs.importNpmLock.buildNodeModules {
          npmRoot = ./.;
          inherit (pkgs) nodejs;
          derivationArgs.postInstall = ''
            # baguetteBox's UMD wrapper uses `this` as the global, which is
            # undefined when loaded as an ES module. Fall back to `self`.
            substituteInPlace $out/node_modules/baguettebox.js/dist/baguetteBox.js \
              --replace-fail \
              '}(this, function () {' \
              '}(typeof self !== "undefined" ? self : this, function () {'
          '';
        };
        jpegoptim = pkgs.jpegoptim.override { libjpeg = pkgs.mozjpeg; };
        fonttools = pkgs.python3Packages.fonttools.overridePythonAttrs (old: {
          dependencies = (old.dependencies or [ ]) ++ old.optional-dependencies.woff;
        });
      in
      {
        apps = {
          linkchecker = {
            type = "app";
            program = "${pkgs.linkchecker}/bin/linkchecker";
          };
          goaccess =
            let
              pkg = (pkgs.goaccess.overrideAttrs (old: {
                patches = (old.patches or [ ]) ++ [
                  # Consider "Feeds" as a kind of "Crawlers"
                  (pkgs.writeText "goaccess-feeds.patch" ''
                    diff --git a/src/browsers.c b/src/browsers.c
                    index a8345297d8a3..20a1d28928ea 100644
                    --- a/src/browsers.c
                    +++ b/src/browsers.c
                    @@ -431,7 +431,7 @@ is_crawler (const char *agent) {
                         free (browser);
                       free (a);

                    -  return strcmp (btype, "Crawlers") == 0 ? 1 : 0;
                    +  return (strcmp (btype, "Crawlers") == 0 || strcmp (btype, "Feeds") == 0) ? 1 : 0;
                     }

                     /* Return the Opera 15 and beyond.
                  '')
                ];
              }));
            in
            {
              type = "app";
              program = "${pkg}/bin/goaccess";
            };
        };
        packages = {
          build.subsetFonts =
            # Impure!
            # Subset fonts. Nice tool to quickly look at the result:
            #  http://torinak.com/font/lsfont.html
            let
              monospace = <monospace>;
              regular = <regular>;
            in
            pkgs.stdenvNoCC.mkDerivation {
              name = "subset-fonts";
              src = <fonts>;
              buildPhase = ''
                subset() {
                  font=$1
                  glyphs=$2
                  echo Subset $font with $glyphs
                  shift 2
                  ${fonttools}/bin/pyftsubset $font.woff2 --flavor=woff2 \
                    --text-file=$glyphs \
                    --output-file=$out/$font.woff2 \
                    "$@"
                }
                mkdir $out
                subset iosevka-custom-regular ${monospace} \
                  --layout-features= --desubroutinize --no-hinting
                subset merriweather ${regular} \
                  --layout-features=ccmp,mark,mkmk,kern,liga,clig,calt,ss01,onum,tnum \
                  --desubroutinize
                subset merriweather-italic ${regular} \
                  --layout-features=ccmp,mark,mkmk,kern,liga,clig,calt,ss01,onum,tnum \
                  --desubroutinize
              '';
              # For Iosevka, no features needed as there is none except locl,
              # frac, numr, dnom, onum and we don't use them.

              # For Merriweather, we keep kern (+2KB and +2.5KB) since it helps with
              # quality. liga, clig, calt are small. ccmp, mark and mkmk are not
              # used, but may become useful in the future. ss01, onum, tnum are
              # explicitely used in CSS. frac, numr, dnom are not used. sups,
              # subs, sinf not useful with HTML. smcp, c2sc, case, ordn, salt,
              # zero are not useful (no small caps). aalt is big (8KB).
              installPhase = "true";
            };
          build.optimizeImages =
            # Impure!
            # Optimize SVG, JPG and PNG
            let
              inherit (pkgs) libwebp libavif pngquant lcms gifsicle;
              inherit jpegoptim;
              svgo = pkgs.svgo.overrideAttrs (old: {
                patches = (old.patches or [ ]) ++ [
                  (pkgs.writeText "sax.patch" ''
                    --- a/bin/svgo.js 2018-01-04 01:01:27.000000000 +0100
                    +++ b/bin/svgo.js 2025-04-21 00:43:30.571001925 +0200
                    @@ -1,5 +1,7 @@
                     #!/usr/bin/env node

                    +import sax from 'sax'; sax.MAX_BUFFER_LENGTH = Infinity;
                    +
                     import colors from 'picocolors';
                     import { program } from 'commander';
                     import makeProgram from '../lib/svgo/coa.js';
                    --- a/lib/parser.js 2025-04-21 00:43:30.571001925 +0200
                    +++ b/lib/parser.js 2025-04-21 00:43:30.571001925 +0200
                    @@ -68,6 +68,7 @@
                       xmlns: true,
                       position: true,
                       unparsedEntities: true,
                    +  maxEntityCount: 4096,
                     };

                     /**
                  '')
                ];
              });
              svgoConfig = pkgs.writeText "svgo.config.js" ''
                module.exports = {
                  plugins: [
                    {
                      name: 'preset-default',
                    }
                  ]
                };
              '';
              parallel = "${pkgs.parallel}/bin/parallel --will-cite --null --halt now,fail=1 -j$(nproc)";
              optimizePng = pkgs.writeShellScript "optimize-png" ''
                ${pngquant}/bin/pngquant --skip-if-larger --strip --quiet -o "$2" "$1" || [ $? = 98 ]
              '';
            in
            pkgs.stdenvNoCC.mkDerivation {
              name = "optimize-images";
              src = <target>;
              buildPhase = ''
                find . -type d -print0 | ${parallel} -X mkdir -p $out/{}

                # SVG (skip interactive ones containing <script>)
                for d in $(find . -type d); do
                  find $d -maxdepth 1 -type f -name '*.svg' -print0 \
                    | sort -z \
                    | xargs -r0 sh -c 'grep -LZ "<script" "$@" || [ $? = 1 ]' grep \
                    | ${parallel} -n5 ${svgo}/bin/svgo --config ${svgoConfig} -o $out/$d -i
                done

                # Convert JPG to sRGB
                find . -type f -name '*.jpg' -print0 \
                  | ${parallel} ${lcms}/bin/jpgicc -q100 {} $out/{}

                # JPG→AVIF
                find $out -type f -name '*.jpg' -print0 \
                  | ${parallel} ${libavif}/bin/avifenc --codec aom --yuv 420 \
                                                       --min 0 --max 63 \
                                                       -a end-usage=q -a cq-level=21 -a tune=ssim \
                                                  {} {}.avif

                # Optimize JPG
                for d in $(find $out -type d); do
                  find $d -maxdepth 1 -type f -name '*.jpg' -print0 \
                    | sort -z \
                    | ${parallel} -n5 ${jpegoptim}/bin/jpegoptim \
                                          --max=84 --all-progressive --strip-all --keep-icc
                done

                # Optimize PNG
                find . -type f -name '*.png' -print0 \
                    | ${parallel} ${optimizePng} {} $out/{}

                # PNG→WebP
                find $out -type f -name '*.png' -print0 \
                    | ${parallel} ${libwebp}/bin/cwebp -z 8 {} -o {}.webp

                # GIF→WebP
                find . -type f -name '*.gif' -print0 \
                    | ${parallel} ${libwebp}/bin/gif2webp -quiet {} -o $out/{}.webp

                # Optimize GIF
                find . -type f -name '*.gif' -print0 \
                    | ${parallel} ${gifsicle}/bin/gifsicle --optimize=3 {} -o $out/{}
              '';
              installPhase = "true";
            };
          build.merriweather = pkgs.stdenvNoCC.mkDerivation {
            name = "custom-merriweather";
            dontUnpack = true;
            # The underline thickness of merriweather is too thin. It has a
            # value of 90. This could be fixed in CSS with
            # text-decoration-thickness (baseline 2021), but we can also fix
            # it directly in the font.
            buildPhase = ''
              fix() {
                original=$1
                target=$2
                echo Fix $1 to $2
                ${fonttools}/bin/ttx -o - ${inputs.merriweather}/fonts/otf/$original.otf \
                  > $target.ttx
                ${pkgs.xmlstarlet}/bin/xmlstarlet \
                  ed -u /ttFont/post/underlineThickness/@value -v 150 $target.ttx \
                  > $target-fixed.ttx
                ${fonttools}/bin/ttx -o $out/$target.woff2 --flavor=woff2 $target-fixed.ttx
              }
              mkdir $out
              fix Merriweather-Light merriweather
              fix Merriweather-LightItalic merriweather-italic
            '';
            installPhase = "true";
          };
          build.baskerville = pkgs.stdenvNoCC.mkDerivation {
            name = "custom-baskerville";
            dontUnpack = true;
            # Fetch the canonical italic file from google/fonts. Libre
            # Baskerville is a wght-only VF.
            buildPhase =
              let
                baskervilleItalic = pkgs.fetchurl (
                  let
                    commit = "9e63336c5ec724faa1e1e394745b33dcbb58a9c9";
                    hash = "sha256-IjlZaD3HPsRDe9Yfq6pLPyIgniKFX/067ja6YaURbpc=";
                    font = "librebaskerville/LibreBaskerville-Italic%5Bwght%5D.ttf";
                  in
                  {
                    inherit hash;

                    url = "https://github.com/google/fonts/raw/${commit}/ofl/${font}";
                  }
                );
              in
              ''
                mkdir -p $out
                # Slice wght to 400 (normal) .. 700 (bold).
                ${fonttools}/bin/fonttools varLib.instancer \
                  -o baskerville-vf.ttf \
                  ${baskervilleItalic} \
                  wght=400:700
                # Keep only &, «, and “
                ${fonttools}/bin/pyftsubset baskerville-vf.ttf \
                  --flavor=woff2 \
                  --no-hinting \
                  --unicodes=U+0026,U+00AB,U+201C \
                  --layout-features= \
                  --output-file=$out/baskerville-custom.woff2
              '';
            installPhase = "true";
          };
          build.iosevka = pkgs.stdenvNoCC.mkDerivation {
            name = "custom-iosevka";
            dontUnpack = true;
            buildPhase =
              let
                iosevka = pkgs.iosevka.override {
                  set = "custom";
                  privateBuildPlan = {
                    family = "Iosevka Custom";
                    spacing = "term";
                    serifs = "sans";
                    noLigation = true;
                    noCvSs = true;
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
                    weights.regular = {
                      shape = 350;
                      menu = 400;
                      css = 400;
                    };
                    widths.normal = {
                      shape = 500;
                      menu = 5;
                      css = "normal";
                    };
                    metricOverride = {
                      cap = 790;
                      ascender = 790;
                      xHeight = 570;
                      leading = 1500; /* Box drawing characters will connect */
                    };
                  };
                };
              in
              ''
                for ttf in ${iosevka}/share/fonts/truetype/*.ttf; do
                  cp $ttf .
                  ${pkgs.woff2}/bin/woff2_compress *.ttf
                  rm *.ttf
                done
              '';
            installPhase = ''
              mkdir -p $out
              cp *.woff2 $out
            '';
          };
        };
        devShells.default = pkgs.mkShell
          {
            name = "www";
            env = {
              UV_NO_SYNC = "1";
              UV_PYTHON = "${pythonEnv}/bin/python";
              UV_PYTHON_DOWNLOADS = "never";
              NODE_OPTIONS = "--disable-warning=DEP0169"; # url.parse()
            };
            packages = with pkgs; [
              pythonEnv

              # Build
              git
              git-annex
              nodejs

              # Build support
              esbuild
              uv

              # Helper tools
              mp4v2 # video2hls
              resvg # SVG to PNG
              fonttools
              jpegoptim
            ];
            shellHook = ''
              unset PYTHONPATH
              ln -nsfT ${nodeEnv}/node_modules node_modules
            '';
          };
      });
}
