(async () => {
  // Search page using Pagefind API
  const form = document.getElementById("lf-search-form");
  const input = document.getElementById("lf-search-input");
  const results = document.getElementById("lf-search-results");
  const noresultsEl = document.getElementById("lf-search-noresults");
  const fallbackEl = document.getElementById("lf-search-fallback");
  const fallbackLink = document.getElementById("lf-search-fallback-link");
  const devMode = location.pathname.endsWith(".html");
  const pageFindScript = document.querySelector(
    'script[data-name="pagefind.js"]',
  );
  const BATCH_SIZE = 5; // number of elements to load from search
  let observer = null; // observer to check for sentinel element
  let pagefind;

  // Try to load pagefind. This may fail because of CSP and/or lack of
  // webassembly support. In this case, pagefind stays null. SRI is checked
  // because the module is loaded through <script> with an integrity attribute.
  try {
    pagefind = await import(pageFindScript.src);
    await pagefind.options({
      noWorker: true,
      baseUrl: "/",
      basePath: form.dataset.pagefindBundle,
      ranking: {
        metaWeights: {
          author: 2.0,
          date: 0.0,
        },
      },
    });
  } catch (e) {
    console.error("Pagefind failed to load:", e);
  }

  // Clear the result area.
  function clearResults() {
    results
      .querySelectorAll(
        ".lf-search-result, .lf-search-spinner, .lf-search-sentinel",
      )
      .forEach((el) => el.remove());
    noresultsEl.hidden = true;
    fallbackEl.hidden = true;
  }

  // Display a DDG fallback link instead of search results.
  function showFallback(query) {
    clearResults();
    const lang = document.documentElement.lang;
    const params = new URLSearchParams({
      kf: "-1",
      kaf: "1",
      k1: "-1",
      sites: `${location.hostname}/${lang}/`,
      q: query,
    });
    fallbackLink.href = `https://duckduckgo.com/?${params}`;
    fallbackEl.hidden = false;
  }

  // Display a spinner during the execution of an async function.
  async function withSpinner(fn) {
    const spinner = `
    <div class="lf-search-spinner">
      <div class="bounce1"></div>
      <div class="bounce2"></div>
      <div class="bounce3"></div>
  </div>`;
    results.insertAdjacentHTML("beforeend", spinner);
    try {
      return await fn();
    } finally {
      results.querySelector(".lf-search-spinner")?.remove();
    }
  }

  // Render HTML for one result.
  function renderResult(d) {
    const url = devMode ? d.url : d.url.replace(/\.html$/, "");
    const date = d.meta.date ? d.meta.date.split("T")[0] : "";
    const author = d.meta.author || "";
    const meta = [date, author].filter(Boolean).join(" — ");
    return `<div class="lf-search-result">
<h3><a href="${url}">${d.meta.title}</a></h3>
${meta ? `<p class="lf-search-meta">${meta}</p>` : ""}
<p class="lf-search-excerpt">${d.excerpt}</p>
</div>`;
  }

  // Render a batch of results and add it to the result area.
  async function renderBatch(hits, offset) {
    const batch = hits.slice(offset, offset + BATCH_SIZE);
    if (batch.length === 0) return;
    results.querySelector(".lf-search-sentinel")?.remove();
    const data = await withSpinner(() =>
      Promise.all(batch.map((h) => h.data())),
    );
    results.insertAdjacentHTML("beforeend", data.map(renderResult).join(""));
    const nextOffset = offset + BATCH_SIZE;
    if (nextOffset < hits.length) {
      const sentinel = document.createElement("div");
      sentinel.className = "lf-search-sentinel";
      results.appendChild(sentinel);
      observer.observe(sentinel);
    }
  }

  // Execute a search and display results by batch.
  async function search(query) {
    clearResults();
    if (observer) observer.disconnect();
    if (!query) return;
    if (!pagefind) {
      showFallback(query);
      return;
    }

    try {
      // Run a search
      const { results: hits } = await withSpinner(() => pagefind.search(query));

      // Display results by batch
      if (hits.length === 0) {
        noresultsEl.hidden = false;
        return;
      }
      observer = new IntersectionObserver((entries) => {
        for (const entry of entries) {
          if (!entry.isIntersecting) continue;
          observer.unobserve(entry.target);
          const loaded = results.querySelectorAll(".lf-search-result").length;
          renderBatch(hits, loaded);
        }
      });
      await renderBatch(hits, 0);
    } catch (e) {
      console.error("Pagefind search failed:", e);
      showFallback(query);
    }
  }

  // Scroll to show as many elements as possible, in priority order.
  function scrollToShow(elements) {
    const els = elements.filter(Boolean);
    if (els.length === 0) return;
    let top = Infinity,
      bottom = -Infinity;
    for (const el of els) {
      const rect = el.getBoundingClientRect();
      const absTop = window.scrollY + rect.top;
      const absBottom = window.scrollY + rect.bottom;
      const newTop = Math.min(top, absTop);
      const newBottom = Math.max(bottom, absBottom);
      if (newBottom - newTop > window.innerHeight) break;
      top = newTop;
      bottom = newBottom;
    }
    const viewTop = window.scrollY;
    const viewBottom = viewTop + window.innerHeight;
    if (top >= viewTop && bottom <= viewBottom) return;
    if (top < viewTop) {
      window.scrollTo(0, top);
    } else {
      window.scrollTo(0, bottom - window.innerHeight);
    }
  }

  input.addEventListener("focus", () => {
    window.scrollTo(0, 0);
  });

  // Navigate results with arrow keys
  document.addEventListener("keydown", (e) => {
    if (e.key !== "ArrowDown" && e.key !== "ArrowUp") return;
    if (e.ctrlKey || e.altKey || e.metaKey || e.shiftKey) return;
    const links = [...results.querySelectorAll(".lf-search-result a")];
    const active = document.activeElement;
    const idx = links.indexOf(active);
    const resultEl = (i) =>
      i < 0
        ? form
        : links[i]?.closest(".lf-search-result") ||
          results.querySelector(".lf-search-sentinel");
    if (links.length === 0) return;

    if (e.key === "ArrowDown") {
      // Going down.
      let newIdx;
      if (active === input) {
        newIdx = 0;
      } else if (idx >= 0 && idx < links.length - 1) {
        newIdx = idx + 1;
      } else {
        return;
      }
      links[newIdx].focus();
      // Priority: current element, next one, previous one, the second next one.
      scrollToShow([
        resultEl(newIdx),
        resultEl(newIdx + 1),
        resultEl(newIdx - 1),
        resultEl(newIdx + 2),
      ]);
      e.preventDefault();
    } else {
      // Going up.
      if (idx === 0) {
        input.focus();
        e.preventDefault();
      } else if (idx > 0) {
        const newIdx = idx - 1;
        links[newIdx].focus();
        // Priority: current element, previous one, next one, the second previous one.
        scrollToShow([
          resultEl(newIdx),
          resultEl(newIdx - 1),
          resultEl(newIdx + 1),
          resultEl(newIdx - 2),
        ]);
        e.preventDefault();
      }
    }
  });

  // On submit, run the search
  form.addEventListener("submit", (e) => {
    const q = input.value.trim();
    const url = new URL(location);
    url.searchParams.set("q", q);
    history.pushState({}, "", url);
    search(q);
    e.preventDefault();
  });

  // On history event, run the search
  window.addEventListener("popstate", () => {
    const q = new URLSearchParams(location.search).get("q") || "";
    input.value = q;
    search(q);
  });

  // On initial state, look at "q" query parameter and run search
  const q = new URLSearchParams(location.search).get("q") || "";
  if (q) {
    input.value = q;
    search(q);
  }
})();
