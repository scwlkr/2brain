export type Entry = {kind: "general" | "tool" | "project"; name: string};
type RecordData = {person?: string; guidance: string[]; pointers: {label: string; target: string}[]};
export type StoredRecord = {schema_version: 1; guidance: string[]; pointers: {label: string; target: string}[]; person?: string};
export type View = {general?: RecordData; context?: RecordData; tool?: string; project?: string; policy?: string; warnings?: string[]; error?: string};
export const TUI_REASON = "edited via tui";

export function guidanceToProse(guidance: string[]): string {
  return guidance.join("\n\n");
}

export function proseToGuidance(text: string): string[] {
  return text.replaceAll("\r\n", "\n").replaceAll("\r", "\n").split(/\n{2,}/).map(segment => segment.trim()).filter(segment => segment.length > 0);
}

export class Backend {
  constructor(private command: string[], private env?: Record<string, string>) {}

  private run(args: string[], stdin?: string, timeout = 15000): any {
    const result = Bun.spawnSync([...this.command, "--json", ...args], {
      stdout: "pipe", stderr: "pipe", timeout,
      ...(stdin !== undefined ? {stdin: new TextEncoder().encode(stdin)} : {}),
      ...(this.env ? {env: this.env} : {}),
    });
    const stdout = new TextDecoder().decode(result.stdout);
    const stderr = new TextDecoder().decode(result.stderr);
    let value;
    try { value = JSON.parse(stdout); }
    catch { throw new Error(stderr || "2brain returned unreadable context."); }
    if (result.exitCode !== 0) throw new Error(value.error || stderr || "2brain could not load context.");
    return value;
  }

  read(args: string[] = []): any {
    return this.run(args);
  }

  write(entry: Entry, record: StoredRecord): any {
    const selector = entry.kind === "general" ? ["--general"] : [`--${entry.kind}`, entry.name];
    return this.run(["put", ...selector, "--file", "-", "--reason", TUI_REASON], JSON.stringify(record), 20000);
  }

  entries(): Entry[] {
    const inventory = this.read(["--list"]);
    return [{kind: "general", name: "General"},
      ...inventory.tools.map((name: string) => ({kind: "tool", name})),
      ...inventory.projects.map((name: string) => ({kind: "project", name}))];
  }

  view(entry: Entry): View {
    try { return this.read(entry.kind === "general" ? [] : [`--${entry.kind}`, entry.name]); }
    catch (error) { return {error: String(error instanceof Error ? error.message : error)}; }
  }
}

export function document(view: View): string {
  if (view.error) return view.error;
  const lines: string[] = [];
  function record(title: string, data: RecordData) {
    lines.push(title, "");
    for (const guidance of data.guidance) lines.push(`· ${guidance}`, "");
    for (const pointer of data.pointers) lines.push(pointer.label, pointer.target, "");
    if (!data.guidance.length && !data.pointers.length) lines.push("No guidance saved yet.", "");
  }
  if (view.context) record(view.tool || view.project || "Context", view.context);
  if (view.general) record(view.general.person || "General", view.general);
  for (const warning of view.warnings || []) lines.push(`Warning: ${warning}`, "");
  lines.push(view.policy || "Current instructions take precedence.");
  return lines.join("\n");
}
