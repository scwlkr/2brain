export type Entry = {kind: "general" | "tool" | "project"; name: string};
type RecordData = {person?: string; guidance: string[]; pointers: {label: string; target: string}[]};
export type View = {general?: RecordData; context?: RecordData; tool?: string; project?: string; policy?: string; warnings?: string[]; error?: string};

export class Backend {
  constructor(private command: string[]) {}

  read(args: string[] = []): any {
    const result = Bun.spawnSync([...this.command, "--json", ...args], {stdout: "pipe", stderr: "pipe", timeout: 15000});
    let value;
    try { value = JSON.parse(new TextDecoder().decode(result.stdout)); }
    catch { throw new Error(new TextDecoder().decode(result.stderr) || "2brain returned unreadable context."); }
    if (result.exitCode !== 0) throw new Error(value.error || "2brain could not load context.");
    return value;
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
