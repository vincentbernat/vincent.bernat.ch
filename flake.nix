{
  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs";
    flake-utils.url = "github:numtide/flake-utils";
    merriweather = {
      url = "github:SorkinType/Merriweather";
      flake = false;
    };
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
          build.subsetFonts =
            # Impure!
            # Subset fonts. Nice tool to quickly look at the result:
            #  http://torinak.com/font/lsfont.html
            let
              monospace = <monospace>;
              regular = <regular>;
              fonttools = python-env;
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
                      --layout-features= \
                      --text-file=$glyphs \
                      --no-hinting --desubroutinize \
                      --output-file=$out/$font.woff2 \
                      "$@"
                  }
                  mkdir $out
                  subset iosevka-custom-regular ${monospace}
                  subset merriweather ${regular} --layout-features+=ss01,onum,tnum
                  subset merriweather-italic ${regular} --layout-features+=ss01,onum,tnum
                '';
                installPhase = "true";
              };
          build.optimizeImages =
            # Impure!
            # Optimize JPG and PNG
            let
              jpegoptim = pkgs.jpegoptim.override { libjpeg = pkgs.mozjpeg; };
              inherit (pkgs) libwebp libavif pngquant;
            in
            pkgs.stdenvNoCC.mkDerivation {
              name = "optimize-images";
              src = <target>;
              buildPhase = ''
                find . -type d -print \
                  | sed "s,^,$out/," \
                  | xargs mkdir -p

                # JPG→WebP
                find . -type f -name '*.jpg' -print0 \
                  | xargs -0 -P$(nproc) -i ${libwebp}/bin/cwebp -q 84 -af '{}' -o $out/'{}'.webp

                # JPG→AVIF
                find . -type f -name '*.jpg' -print0 \
                  | xargs -0 -P$(nproc) -i ${libavif}/bin/avifenc --codec aom --yuv 420 \
                                                                       --ignore-icc \
                                                                       --min 20 --max 25 \
                                                                  '{}' $out/'{}'.avif

                # Optimize JPG
                for d in $(find . -type d); do
                  find $d -maxdepth 1 -type f -name '*.jpg' -print0 \
                    | sort -z \
                    | xargs -r0n3 -P$(nproc) ${jpegoptim}/bin/jpegoptim \
                                                -d $out/$d --max=84 --all-progressive --strip-all
                done

                # Optimize PNG
                find . -type f -name '*.png' -print0 \
                    | xargs -0 -P$(nproc) -i ${pngquant}/bin/pngquant --skip-if-larger --strip \
                                                --quiet -o $out/'{}' '{}' \
                    || [ $? -eq 123 ]

                # PNG→WebP
                find $out -type f -name '*.png' -print0 \
                    | xargs -0 -P$(nproc) -i ${libwebp}/bin/cwebp -z 8 '{}' -o '{}'.webp
              '';
              installPhase = "true";
            };
          build.merriweather = pkgs.stdenvNoCC.mkDerivation {
            name = "custom-merriweather";
            dontUnpack = true;
            buildPhase = ''
            fix() {
              original=$1
              target=$2
              echo Fix $1 to $2
              ${python-env}/bin/ttx -o - ${inputs.merriweather}/fonts/otf/$original.otf \
                | tr -d '\000' \
                > $target.ttx
              ${pkgs.xmlstarlet}/bin/xmlstarlet \
                ed -u /ttFont/post/underlineThickness/@value -v 150 $target.ttx \
                > $target-fixed.ttx
              ${python-env}/bin/ttx -o $out/$target.woff2 --flavor=woff2 $target-fixed.ttx
            }
            mkdir $out
            fix Merriweather-Light merriweather
            fix Merriweather-LightItalic merriweather-italic
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
        devShell = python-env.env.overrideAttrs (oldAttrs: {
          name = "www";
          buildInputs = [
            # Build
            pkgs.git
            pkgs.git-annex
            pkgs.nodejs
            pkgs.openssl
            pkgs.python3Packages.invoke
          ];
        });
      });
}
