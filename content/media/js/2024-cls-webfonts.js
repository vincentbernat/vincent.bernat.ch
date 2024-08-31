{
  const getElementById = (name) =>
    document.getElementById(`lf1-support-${name}`);

  // Create the two blocks of text and keep them in sync
  {
    const container = getElementById("container");
    const underlay = document.createElement("div");
    const overlay = document.createElement("div");
    underlay.id = "lf1-support-underlay";
    overlay.id = "lf1-support-overlay";
    for (let el of [underlay, overlay]) {
      el.innerHTML = container.innerHTML;
      el.contentEditable = true;
      el.spellcheck = false;
    }
    container.innerHTML = "";
    container.appendChild(underlay);
    container.appendChild(overlay);
    underlay.addEventListener("input", () => {
      overlay.innerHTML = underlay.innerHTML;
    });
    overlay.addEventListener("input", () => {
      underlay.innerHTML = overlay.innerHTML;
    });
  }

  // Fill in system fonts
  {
    const systemFonts = new Map([
      [
        "Windows",
        [
          "Arial",
          "Calibri",
          "Courier New",
          "Garamond",
          "Georgia",
          "Palatino",
          "Segoe UI",
          "Tahoma",
          "Times New Roman",
          "Trebuchet MS",
          "Verdana",
        ],
      ],
      [
        "macOS",
        [
          "Bookman",
          "Courier",
          "Georgia",
          "Helvetica Neue",
          "Helvetica",
          "Impact",
          "San Francisco",
          "Times",
        ],
      ],
      [
        "Android",
        [
          "Noto Serif",
          "Noto Sans",
          "Noto Sans Mono",
          "Droid Serif",
          "Droid Sans",
          "Droid Sans Mono",
          "Roboto Mono",
          "Roboto",
        ],
      ],
    ]);
    const select = getElementById("font-fallback-select");
    for (let [group, fonts] of systemFonts) {
      const optGroup = document.createElement("optgroup");
      optGroup.label = group;
      for (let font of fonts) {
        const option = document.createElement("option");
        option.value = font;
        option.text = font;
        optGroup.appendChild(option);
      }
      select.appendChild(optGroup);
    }
  }

  // Helper to switch a font
  const updateFont = (fontFace, elementName) => {
    const el = getElementById(elementName);
    for (let font of document.fonts) {
      if (font.family === fontFace.family) {
        document.fonts.delete(font);
      }
    }
    document.fonts.add(fontFace);
    el.style.fontFamily = fontFace.family;
  };

  // Handle change of the custom font.
  getElementById("font-custom-file").addEventListener("change", (e) => {
    const reader = new FileReader();
    reader.onload = async (e) => {
      const fontFace = new FontFace("custom-font", `url(${e.target.result})`);
      const loadedFace = await fontFace.load();
      updateFont(loadedFace, "underlay");
    };
    reader.readAsDataURL(e.target.files[0]);
  });

  // Handle changes related to the fallback font
  const updateFallbackFont = () => {
    const customFontSelected = getElementById("font-fallback-select");
    const customFontName = getElementById("font-fallback-name");
    const customFontFile = getElementById("font-fallback-file");
    const useUploadedFile =
      customFontSelected.value === "-lf1-font-fallback-file";
    customFontName.disabled = useUploadedFile;
    customFontFile.disabled = !useUploadedFile;

    // Update propertie helper
    const updateProps = (fontFace) => {
      for (const prop of [
        "ascentOverride",
        "descentOverride",
        "lineGapOverride",
        "sizeAdjust",
      ]) {
        const val = getElementById(prop).value;
        getElementById(prop).disabled =
          useUploadedFile && customFontFile.files.length === 0;
        getElementById(`${prop}-value`).textContent = val + "%";
        fontFace[prop] = val + "%";
      }
    };

    // Load font helper
    const loadFont = (fontFace) => {
      fontFace.load().then(
        (loadedFace) => {
          customFontName.classList.remove("invalid");
          customFontFile.classList.remove("invalid");
          updateFont(loadedFace, "overlay");
        },
        () => {
          console.error("Cannot load font face", fontFace);
          if (!useUploadedFile) {
            customFontName.classList.add("invalid");
          } else {
            customFontFile.classList.add("invalid");
          }
        },
      );
    };

    if (!useUploadedFile) {
      const fontFace = new FontFace(
        "fallback-font",
        `local(${customFontName.value})`,
      );
      updateProps(fontFace);
      loadFont(fontFace);
    } else {
      if (customFontFile.files.length === 0) {
        // Do nothing if we don't have a custom file uploaded
        return;
      }
      const reader = new FileReader();
      reader.onload = (e) => {
        const fontFace = new FontFace(
          "fallback-font",
          `url(${e.target.result})`,
        );
        updateProps(fontFace);
        loadFont(fontFace);
      };
      reader.readAsDataURL(customFontFile.files[0]);
    }
  };

  // Listen for change of selected font and copy its name.
  getElementById("font-fallback-select").addEventListener("change", (e) => {
    if (e.target.value !== "-lf1-font-fallback-file") {
      getElementById("font-fallback-name").value = e.target.value;
    } else {
      getElementById("font-fallback-name").value = "";
    }
    updateFallbackFont();
  });

  // Listen for change of font name or change of uploaded fonts.
  for (let name of ["font-fallback-name", "font-fallback-file"]) {
    getElementById(name).addEventListener("change", updateFallbackFont);
  }
  // Listen for change of properties
  for (let name of [
    "ascentOverride",
    "descentOverride",
    "lineGapOverride",
    "sizeAdjust",
  ]) {
    getElementById(name).addEventListener("input", () => updateFallbackFont());
  }
  getElementById("line-height").addEventListener("change", (e) => {
    const lineHeight = e.target.checked ? "inherit" : "normal";
    getElementById("underlay").style.lineHeight = lineHeight;
    getElementById("overlay").style.lineHeight = lineHeight;
  });

  // Set initial values
  window.addEventListener("load", () => {
    for (let font of document.fonts) {
      if (font.family === "Fallback for Merriweather") {
        for (let name of [
          "ascentOverride",
          "descentOverride",
          "lineGapOverride",
          "sizeAdjust",
        ]) {
          getElementById(name).value = parseFloat(font[name]);
        }
        getElementById("font-fallback-select").value = "Georgia";
        getElementById("font-fallback-name").value = "Georgia";
      }
    }
    updateFallbackFont();
  });
}
