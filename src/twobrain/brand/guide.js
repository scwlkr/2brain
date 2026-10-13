"use strict";
document.addEventListener("DOMContentLoaded", () => {
  const data = window.wstackBrandData;
  if (!data) return;
  const style = JSON.parse(data.style);
  const colors = Object.fromEntries(style.colors.map(item => item.split(" ")));
  for (const [name, hex] of Object.entries(colors)) {
    document.documentElement.style.setProperty(`--${name}`, hex);
  }
  for (const button of document.querySelectorAll("[data-color]")) {
    const hex = colors[button.dataset.color];
    button.querySelector("code").textContent = hex;
    button.addEventListener("click", async () => {
      const status = document.querySelector("#color-status");
      try {
        await navigator.clipboard.writeText(hex);
        status.textContent = `${hex} copied.`;
      } catch {
        status.textContent = `Copy this color: ${hex}`;
      }
    });
  }
  for (const token of document.querySelectorAll("[data-token]")) {
    token.textContent = colors[token.dataset.token];
  }
});
