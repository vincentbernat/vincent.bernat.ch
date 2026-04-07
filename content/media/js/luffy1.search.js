// Search page using Pagefind API
const form = document.getElementById("lf-search-form");
const input = document.getElementById("lf-search-input");
const results = document.getElementById("lf-search-results");
const spinner = `
  <div class="lf-search-spinner">
    <div class="bounce1"></div>
    <div class="bounce2"></div>
    <div class="bounce3"></div></div>`;
const devMode = location.pathname.endsWith(".html");
let pagefind;
const pageFindScript = document.querySelector(
  'script[data-name="pagefind.js"]',
);

function showFallback(query) {
  const lang = document.documentElement.lang;
  const params = new URLSearchParams({
    kf: "-1",
    kaf: "1",
    k1: "-1",
    sites: `${location.hostname}/${lang}/`,
    q: query,
  });
  const url = `https://duckduckgo.com/?${params}`;
  results.innerHTML = `<p>Search is not available. <a href="${url}">Try with DuckDuckGo</a>.</p>`;
}

try {
  pagefind = await import(pageFindScript.src);
  await pagefind.options({
    noWorker: true,
    baseUrl: "/",
    basePath: form.dataset.pagefindBundle,
  });
} catch (e) {
  console.error("Pagefind failed to load:", e);
}

async function search(query) {
  if (!query) {
    results.innerHTML = "";
    return;
  }

  if (!pagefind) {
    showFallback(query);
    return;
  }

  // Trigger search
  results.innerHTML = spinner;
  try {
    const { results: hits } = await pagefind.search(query);

    // Display results if any
    if (hits.length === 0) {
      results.innerHTML = "<p>No results found.</p>";
      return;
    }
    const data = await Promise.all(hits.map((h) => h.data()));
    results.innerHTML = data
      .map((d) => {
        const url = devMode ? d.url.replace(/\.html$/, "") : d.url;
        const date = d.meta.date ? d.meta.date.split("T")[0] : "";
        const author = d.meta.author || "";
        const meta = [date, author].filter(Boolean).join(" — ");
        return `<div class="lf-search-result">
<h3><a href="${url}">${d.meta.title}</a></h3>
${meta ? `<p class="lf-search-meta">${meta}</p>` : ""}
<p class="lf-search-excerpt">${d.excerpt}</p>
</div>`;
      })
      .join("");
  } catch (e) {
    console.error("Pagefind search failed:", e);
    showFallback(query);
  }
}

// On submit, run the search
form.addEventListener("submit", (e) => {
  e.preventDefault();
  const q = input.value.trim();
  const url = new URL(location);
  url.searchParams.set("q", q);
  history.pushState({}, "", url);
  search(q);
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
} else {
  input.focus();
}
