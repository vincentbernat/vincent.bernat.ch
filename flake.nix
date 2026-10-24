{
  inputs = {
    nixpkgs.url = "nixpkgs";
    flake-parts.url = "github:hercules-ci/flake-parts";
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
  };
  outputs = { self, flake-parts, ... }@inputs: flake-parts.lib.mkFlake { inherit inputs; }
    {
      systems = [ "x86_64-linux" "aarch64-linux" ];
      perSystem = { pkgs, system, ... }:
        let
          l = pkgs.lib // builtins;

          fonttools = pkgs.python3Packages.fonttools.overridePythonAttrs (old: {
            dependencies = (old.dependencies or [ ]) ++ old.optional-dependencies.woff;
          });
          python = pkgs.python3;
          pythonEnv =
            let
              pythonBase = pkgs.callPackage inputs.pyproject-nix.build.packages {
                inherit python;
              };
              workspace = inputs.uv2nix.lib.workspace.loadWorkspace {
                workspaceRoot = l.fileset.toSource {
                  root = ./.;
                  fileset = l.fileset.unions [ ./pyproject.toml ./uv.lock ];
                };
              };
              overlay = workspace.mkPyprojectOverlay {
                sourcePreference = "wheel";
              };
              hacks = pkgs.callPackage inputs.pyproject-nix.build.hacks { };
              buildSystemOverrides =
                let
                  overrides = {
                    pygments.hatchling = [ ];
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
                # xxhash from source, as the wheel only uses SSE2, not AVX2
                xxhash = (prev.xxhash.override { sourcePreference = "sdist"; }).overrideAttrs (old: {
                  nativeBuildInputs = old.nativeBuildInputs ++ final.resolveBuildSystem {
                    setuptools = [ ];
                  };
                  env = (old.env or { }) // l.optionalAttrs pkgs.stdenv.hostPlatform.isx86_64 {
                    NIX_CFLAGS_COMPILE = "-march=x86-64-v3";
                  };
                });
                # doit from source, to patch it
                doit = (prev.doit.override { sourcePreference = "sdist"; }).overrideAttrs (old: {
                  nativeBuildInputs = old.nativeBuildInputs ++ final.resolveBuildSystem {
                    setuptools = [ ];
                  };
                  patches = (old.patches or [ ]) ++ [
                    ./tools/patches/doit-refresh-file-dep-state.patch
                    ./tools/patches/doit-cache-uptodate-signature.patch
                  ];
                });
                # No need for tools from fonttools (we pull the Nix version for that)
                fonttools = prev.fonttools.overrideAttrs (old: {
                  postInstall = (old.postInstall or "") + ''
                    rm -rf "$out/bin"
                  '';
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
          svgo = pkgs.svgo.overrideAttrs (old: {
            patches = (old.patches or [ ]) ++ [
              ./tools/patches/svgo-limits.patch
              ./tools/patches/svgo-foreignobject.patch
            ];
          });
          lychee = pkgs.lychee.overrideAttrs (old: {
            patches = (old.patches or [ ]) ++ [
              ./tools/patches/lychee-detailed-stats.patch
            ];
            # This test checks there are no details without --verbose
            checkFlags = old.checkFlags ++ [ "--skip=cli::test_redirect_json" ];
          });
          hlsVersion = (l.importJSON ./package-lock.json).packages."node_modules/hls.js".version;
          nodeEnv = pkgs.importNpmLock.buildNodeModules {
            npmRoot = l.fileset.toSource {
              root = ./.;
              fileset = l.fileset.unions [ ./package.json ./package-lock.json ];
            };
            inherit (pkgs) nodejs;
            derivationArgs = {
              nativeBuildInputs = [ pkgs.esbuild ];
              postInstall = ''
                # baguetteBox's UMD wrapper uses `this` as the global, which is
                # undefined when loaded as an ES module. Use the CommonJS branch
                # instead.
                (
                  cd $out/node_modules/baguettebox.js
                  echo 'self.baguetteBox = require("./dist/baguetteBox.js");' \
                    | esbuild --bundle --format=iife --target=es2015 \
                      --outfile=dist/baguetteBox.global.js
                )

                # The @svta/cml-* packages are dev dependencies of hls.js,
                # pinned there. Check we use the same versions.
                ${./tools/hls-deps} check ${./package.json} \
                  $out/node_modules/hls.js/package.json

                # hls.js ships a full build and a light build. The light one has
                # no alternate audio. Build the same as light, with alternate
                # audio.
                (
                  cd $out/node_modules/hls.js

                  # Read the feature flags from the sources and turn them all
                  # off. A new flag in hls.js then stays off instead of being
                  # left undefined. This fails when a flag we turn on is gone.
                  grep -q __USE_ALT_AUDIO__ src/define-plugin.d.ts
                  off=$(sed -n 's/^declare const \(__USE_[A-Z0-9_]*__\).*/--define:\1=false/p' \
                    src/define-plugin.d.ts)

                  echo 'import Hls from "./src/exports-default"; self.Hls = Hls;' \
                    | esbuild --bundle --loader=js --format=iife --target=es2015 \
                      --banner:js='(function __HLS_WORKER_BUNDLE__(__IN_WORKER__){' \
                      --footer:js='})(false);' \
                      --define:__VERSION__='"${hlsVersion}"' \
                      $off \
                      --define:__USE_ALT_AUDIO__=true \
                      --outfile=dist/hls.light-alt-audio.js
                )
              '';
            };
          };
          # Titles for RFC links.
          rfcIndex =
            let
              index = pkgs.fetchurl {
                url = "https://web.archive.org/web/20260520171049if_/https://www.rfc-editor.org/rfc-index.xml";
                hash = "sha256-IJ7hVCMnqFKpwXiA6iz8Dk0gJTWByTQQRiKhBgz5uio=";
                # archive.org sometimes serves the file gzipped, sometimes not.
                downloadToTemp = true;
                postFetch = "${pkgs.gzip}/bin/gzip -dcf $downloadedFile > $out";
              };
            in
            pkgs.runCommand "rfc-index.json.gz" { } ''
              # Keep only the number and the title of each RFC.
              cat ${index} \
                | ${pkgs.xmlstarlet}/bin/xmlstarlet sel -T \
                    -N r="https://www.rfc-editor.org/rfc-index" \
                    -t -m "//r:rfc-entry" \
                    -v "concat(substring-after(r:doc-id, 'RFC'), '=', normalize-space(r:title))" \
                    -n \
                | ${pkgs.jq}/bin/jq -Rnc '
                    [inputs
                     | capture("^(?<n>[0-9]+)=(?<t>.*)$")
                     | {(.n | tonumber | tostring): .t}] | add' \
                | ${pkgs.gzip}/bin/gzip -9n > $out
            '';
          # Compact sRGB profile to tag images.
          srgbProfile = pkgs.fetchurl (
            let
              commit = "bdd84663061bc4ae95ca70decff54f581e27f702";
              hash = "sha256-CoozrqZqbxVKVkLr4WjvKH5zJl2fe1HEKkXm7tus2no=";
            in
            {
              inherit hash;
              url = "https://github.com/saucecontrol/Compact-ICC-Profiles/raw/${commit}/profiles/sRGB-v2-micro.icc";
            }
          );
          notoSansDisplay = pkgs.runCommand "noto-sans-display" { } ''
            install -Dm444 ${pkgs.fetchurl (
              let
                commit = "503d300da2bbdec7d00e0ff9078876ec7d6dbb92";
                hash = "sha256-EGEFcWEsrYx76Qsi2ClA/5SrTgx0RlEbLkTU45qxiGU=";
              in
              {
                inherit hash;
                url = "https://github.com/notofonts/noto-fonts/raw/${commit}/hinted/ttf/NotoSansDisplay/NotoSansDisplay-SemiBold.ttf";
              }
            )} $out/share/fonts/truetype/NotoSansDisplay-SemiBold.ttf
          '';
          # Fonts to embed in SVG files. Subsetting a WOFF2 font is slow
          # because of the decompression.
          svgFonts = pkgs.runCommand "svg-fonts" { } ''
            mkdir $out
            ${fonttools}/bin/fonttools ttLib.woff2 decompress \
              -o $out/literata.ttf ${./content/media/fonts/literata.woff2}
            ${fonttools}/bin/fonttools ttLib.woff2 decompress \
              -o $out/iosevka.ttf ${./content/media/fonts/iosevka.woff2}
          '';
        in
        {
          legacyPackages = {
            tools.links = pkgs.buildEnv {
              name = "links-env";
              paths = [
                lychee
                (pkgs.python3.withPackages (ps: [ ps.textual ]))
              ];
            };
            tools.image-compare = pkgs.buildEnv {
              name = "image-compare-env";
              paths = with pkgs; [
                python3
                jpegli.bin
                libavif
                libwebp
                lcms
                exiftool
              ];
            };
            build.literata = pkgs.stdenvNoCC.mkDerivation {
              name = "custom-literata";
              dontUnpack = true;
              # Keep only weight 350 and optical size 18 (body text is 16px to
              # 20px). The underline thickness is too thin. It has a value of
              # 50. This could be fixed in CSS with text-decoration-thickness
              # (baseline 2021), but we can also fix it directly in the font.
              buildPhase =
                let
                  literata = { style, hash }: pkgs.fetchurl (
                    let
                      commit = "0c2761b727a1b3a7cffd313c37f0f5163dfc7a63";
                      font = "fonts/variable/Literata${style}%5Bopsz,wght%5D.ttf";
                    in
                    {
                      inherit hash;
                      name = "Literata${style}.ttf";
                      url = "https://github.com/googlefonts/literata/raw/${commit}/${font}";
                    }
                  );
                  regular = literata {
                    style = "";
                    hash = "sha256-tBE4yTcxEvMqu1icwi6GdLBu1ASLDFE76SK90m8nREA=";
                  };
                  italic = literata {
                    style = "-Italic";
                    hash = "sha256-1IPfrrqcv0znHTKlLuZd+C9+NbFf/40QEc2yQtH81GU=";
                  };
                in
                ''
                  fix() {
                    original=$1
                    target=$2
                    echo Fix $1 to $2
                    ${fonttools}/bin/fonttools varLib.instancer \
                      -o $target.ttf $original \
                      wght=350 opsz=18
                    ${fonttools}/bin/ttx -o - $target.ttf > $target.ttx
                    ${pkgs.xmlstarlet}/bin/xmlstarlet \
                      ed -u /ttFont/post/underlineThickness/@value -v 75 $target.ttx \
                      > $target-fixed.ttx
                    ${fonttools}/bin/ttx -o $out/$target.woff2 --flavor=woff2 $target-fixed.ttx
                  }
                  mkdir $out
                  fix ${regular} literata
                  fix ${italic} literata-italic
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
                        cap = 700;
                        ascender = 750;
                        xHeight = 500;
                        leading = 1500; /* Box drawing characters will connect */
                      };
                    };
                  };
                in
                ''
                  cp ${iosevka}/share/fonts/truetype/*.ttf iosevka.ttf
                  ${pkgs.woff2}/bin/woff2_compress iosevka.ttf
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
                SSG_SRGB_PROFILE = "${srgbProfile}";
                SSG_SOURCE_SANS_FONT = "${pkgs.source-sans}/share/fonts/opentype/SourceSans3-Regular.otf";
                SSG_LITERATA_FONT = "${svgFonts}/literata.ttf";
                SSG_IOSEVKA_FONT = "${svgFonts}/iosevka.ttf";
                FONTCONFIG_FILE = "${pkgs.runCommand "fonts.conf" { } ''
                  sed '/<dir prefix="xdg">/d' ${pkgs.makeFontsConf {
                    fontDirectories = [ notoSansDisplay ];
                    impureFontDirectories = [ ];
                    includes = [ ];
                  }} > $out
                ''}";
              };
              packages = with pkgs; [
                pythonEnv
                uv

                # Build tools
                nodejs
                esbuild
                fonttools
                pagefind
                brotli

                # Image optimization
                svgo
                jpegli.bin
                libavif
                libwebp
                pngquant
                lcms
                gifsicle
                exiftool

                # Helper tools
                caddy
                vale
                (writeShellScriptBin "mypy" ''
                  exec ${python.pkgs.mypy}/bin/mypy --python-executable ${pythonEnv}/bin/python "$@"
                '')
              ];
              shellHook = ''
                unset PYTHONPATH
                export PYTHONPYCACHEPREFIX="$PWD/.cache/pycache"
                export SSG_EXPORT_www=$(< ../automation/nixops-take1/cdktf.json \
                  jq -r '.sites.value["vincent.bernat.ch"] | join(" ")')
                export SSG_EXPORT_media=$(< ../automation/nixops-take1/cdktf.json \
                  jq -r '.sites.value["media.bernat.ch"] | join(" ")')
                [ "$(readlink node_modules)" = ${nodeEnv}/node_modules ] \
                  || ln -nsfT ${nodeEnv}/node_modules node_modules
                [ "$(readlink ssg/markdown/rfc-index.json.gz)" = ${rfcIndex} ] \
                  || ln -nsfT ${rfcIndex} ssg/markdown/rfc-index.json.gz
              '';
            };
        };
    };
}
