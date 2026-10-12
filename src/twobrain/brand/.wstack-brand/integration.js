"use strict";
(() => {
  const base = new URL(".", document.currentScript.src);
  const { assets = [], style = "" } = window.wstackBrandData || {};
  const pending = new Map();
  const mounted = new WeakSet();
  const resolve = value => typeof value === "string" ? document.querySelector(value) : value;
  const resource = path => new URL("../" + path.split("/").map(encodeURIComponent).join("/"), base).href;
  function element(tag, text, attributes = {}) {
    const node = document.createElement(tag);
    if (text !== undefined) node.textContent = text;
    for (const [key, value] of Object.entries(attributes)) node.setAttribute(key, value);
    return node;
  }
  function statusFor(target) {
    const root = target.closest("[data-wstack-catalog]") || target.parentElement;
    let status = root.querySelector("[data-wstack-status]");
    if (!status) {
      status = element("p", "", { "data-wstack-status": "", role: "status", "aria-live": "polite" });
      root.append(status);
    }
    return status;
  }
  function payload(row) {
    if (!/^downloads\/[a-f0-9]+\.js$/.test(row.download || "")) {
      return Promise.reject(new Error("Download unavailable. Refresh the brand resources and try again."));
    }
    if (!pending.has(row.download)) {
      const key = row.download.split("/").pop().slice(0, -3);
      const promise = new Promise((accept, reject) => {
        const script = element("script", undefined, { src: new URL(row.download, base).href });
        script.onload = () => {
          const encoded = (window.wstackBrandPayloads || {})[key];
          script.remove();
          if (typeof encoded !== "string") {
            reject(new Error("Download payload is missing. Run brand refresh and retry."));
            return;
          }
          try {
            const bytes = Uint8Array.from(atob(encoded), value => value.charCodeAt(0));
            delete window.wstackBrandPayloads[key];
            accept(new Blob([bytes], { type: "application/octet-stream" }));
          } catch {
            reject(new Error("Download payload is invalid. Run brand refresh and retry."));
          }
        };
        script.onerror = () => {
          script.remove();
          reject(new Error("Could not load this download. Restore its generated files or run brand refresh."));
        };
        document.head.append(script);
      });
      pending.set(row.download, promise);
      promise.catch(() => pending.delete(row.download));
    }
    return pending.get(row.download);
  }
  async function download(path) {
    const row = assets.find(item => item.path === path);
    if (!row) throw new Error(`Resource missing: ${path}. Run brand refresh after asset changes.`);
    const blob = await payload(row);
    const url = URL.createObjectURL(blob);
    const link = element("a", undefined, { href: url, download: row.path.split("/").pop() });
    document.body.append(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    return { path: row.path, bytes: blob.size };
  }
  async function copy(field, status) {
    field = resolve(field);
    status = resolve(status);
    if (!field || typeof field.select !== "function") throw new Error("Provide a textarea for the exact style JSON and manual copy fallback.");
    field.value = style;
    try {
      if (navigator.clipboard && window.isSecureContext) {
        await navigator.clipboard.writeText(style);
      } else {
        field.focus();
        field.select();
        if (!document.execCommand("copy")) throw new Error("Clipboard unavailable");
      }
      if (status) status.textContent = "Style JSON copied.";
      return true;
    } catch {
      field.focus();
      field.select();
      if (status) status.textContent = "Copy unavailable. Style JSON selected; press Ctrl+C or Command+C.";
      return false;
    }
  }
  function preview(row, opener) {
    const dialog = element("dialog", undefined, { "data-wstack-dialog": row.path, "aria-label": row.title });
    const close = element("button", "Close preview", { type: "button" });
    const image = element("img", undefined, { src: resource(row.path), alt: row.title });
    dialog.style.maxWidth = "90vw";
    image.style.width = "min(75vw, 960px)";
    image.style.height = "65vh";
    image.style.maxWidth = "100%";
    image.style.objectFit = "contain";
    dialog.append(close, element("h2", row.title), image);
    document.body.append(dialog);
    close.addEventListener("click", () => dialog.close());
    dialog.addEventListener("close", () => {
      dialog.remove();
      if (opener.isConnected) opener.focus();
    }, { once: true });
    dialog.showModal();
    close.focus();
  }
  function card(row) {
    const article = element("article", undefined, { "data-wstack-path": row.path, "data-wstack-role": row.role || "current" });
    if (row.preview) {
      const button = element("button", undefined, { type: "button", "data-wstack-preview": row.path,
        "aria-label": `Enlarge ${row.title}` });
      button.append(element("img", undefined, { src: resource(row.path), alt: row.title, loading: "lazy", width: "240", height: "160" }));
      button.firstChild.style.objectFit = "contain";
      article.append(button);
    } else {
      article.append(element("p", row.kind));
    }
    article.append(element("h3", row.title), element("p", `${row.category} · ${row.kind} · ${row.role || "current"}`),
      element("p", row.description), element("code", row.path));
    article.append(element("a", "Download", { href: resource(row.path), download: row.path.split("/").pop(),
      "data-wstack-download": row.path }));
    for (const [key, title] of [["license", "License"], ["source", "Original"]]) {
      if (row[key]) article.append(document.createTextNode(" · "), element("a", title, { href: resource(row[key]) }));
    }
    return article;
  }
  function mount(root) {
    root = resolve(root);
    if (!root) throw new Error("Catalog root missing. Pass an element or selector to WstackBrand.mount.");
    if (mounted.has(root)) return root;
    root.setAttribute("data-wstack-catalog", "");
    function hook(name, create) {
      let node = root.querySelector(`[data-wstack-${name}]`);
      if (!node) {
        node = create();
        node.setAttribute(`data-wstack-${name}`, "");
        root.append(node);
      }
      return node;
    }
    const search = hook("search", () => element("input", undefined, { type: "search", "aria-label": "Search resources", placeholder: "Search resources" }));
    const category = hook("category", () => element("select", undefined, { "aria-label": "Resource category" }));
    category.replaceChildren(element("option", "All categories", { value: "" }),
      ...[...new Set(assets.map(row => row.category))].sort().map(value => element("option", value, { value })));
    const scope = hook("scope", () => element("select", undefined, { "aria-label": "Resource scope" }));
    scope.replaceChildren(element("option", "Current assets", { value: "current" }), element("option", "All resources", { value: "all" }));
    const count = hook("count", () => element("p", "", { role: "status", "aria-live": "polite" }));
    const catalog = hook("assets", () => element("div"));
    const cards = assets.map(card);
    catalog.replaceChildren(...cards);
    const empty = hook("empty", () => element("p", "No matching resources. Try another search, category or All resources."));
    function filter() {
      const query = search.value.toLowerCase().trim();
      let visible = 0;
      for (const [index, row] of assets.entries()) {
        cards[index].hidden = (scope.value !== "all" && (row.role || "current") !== "current") ||
          (category.value !== "" && category.value !== row.category) ||
          !JSON.stringify(row).toLowerCase().includes(query);
        if (!cards[index].hidden) visible += 1;
      }
      const total = scope.value === "all" ? assets.length : assets.filter(row => (row.role || "current") === "current").length;
      count.textContent = `${visible} of ${total} ${scope.value === "all" ? "resources" : "current assets"}`;
      empty.hidden = visible !== 0;
    }
    search.addEventListener("input", filter);
    category.addEventListener("change", filter);
    scope.addEventListener("change", filter);
    mounted.add(root);
    filter();
    return root;
  }
  document.addEventListener("click", async event => {
    const opener = event.target.closest("[data-wstack-preview]");
    if (opener) {
      event.preventDefault();
      const row = assets.find(item => item.path === opener.dataset.wstackPreview);
      if (row && row.preview) preview(row, opener);
      else statusFor(opener).textContent = "Preview unavailable. Run brand refresh or open the original resource.";
      return;
    }
    const copyButton = event.target.closest("[data-wstack-copy], [data-wstack-style-copy]");
    if (copyButton) {
      event.preventDefault();
      const root = copyButton.closest("[data-wstack-catalog]") || document;
      const field = copyButton.dataset.wstackCopy ? resolve(copyButton.dataset.wstackCopy) : root.querySelector("[data-wstack-style]");
      const status = statusFor(copyButton);
      try { await copy(field, status); } catch (error) { status.textContent = error.message; }
      return;
    }
    const link = event.target.closest("[data-wstack-download]");
    if (!link) return;
    event.preventDefault();
    const status = statusFor(link);
    status.textContent = "Preparing download…";
    try {
      await download(link.dataset.wstackDownload);
      status.textContent = "Download ready. Check your browser downloads.";
    } catch (error) {
      status.textContent = error.message;
    }
  });
  window.WstackBrand = { assets, style, download, copy, mount };
  const start = () => {
    document.querySelectorAll("[data-wstack-style]").forEach(field => { field.value = style; });
    document.querySelectorAll("[data-wstack-catalog]").forEach(mount);
  };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start, { once: true });
  else start();
})();
