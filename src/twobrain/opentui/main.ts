import {createCliRenderer} from "@opentui/core";
import {Backend} from "./backend.ts";
import {createBrowser, type Settings} from "./app.ts";

try {
  const backend = new Backend(JSON.parse(process.env.TWOBRAIN_BACKEND || "[]"));
  const settings: Settings = JSON.parse(process.env.TWOBRAIN_UI_SETTINGS || "{}");
  const renderer = await createCliRenderer({exitOnCtrlC: true, useMouse: true, consoleMode: "disabled", openConsoleOnError: false});
  try {
    createBrowser(renderer, backend, settings);
    await renderer.closed;
  } finally {
    renderer.destroy();
    await renderer.closed;
  }
} catch (error) {
  console.error(`2brain: ${error instanceof Error ? error.message : error}`);
  process.exitCode = 1;
}
