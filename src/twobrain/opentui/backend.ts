import {StyledText, bold, fg, type ColorInput, type TextChunk} from "@opentui/core";

export type Entry = {kind: "general" | "tool" | "project"; name: string};
type RecordData = {person?: string; guidance: string[]; pointers: {label: string; target: string}[]};
export type StoredRecord = {schema_version: 1; guidance: string[]; pointers: {label: string; target: string}[]; person?: string};
export type View = {general?: RecordData; context?: RecordData; tool?: string; project?: string; policy?: string; warnings?: string[]; error?: string};
export type DocumentRoles = {accent: ColorInput; muted: ColorInput; fg: ColorInput};
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

const EMPTY_RECORD_CTA = ["No guidance yet.", "e writes guidance · p adds pointers · a creates a record."];

function plainRecord(lines: string[], title: string, data: RecordData) {
  lines.push(title, "");
  for (const guidance of data.guidance) lines.push(`· ${guidance}`, "");
  for (const pointer of data.pointers) lines.push(`→ ${pointer.label}: ${pointer.target}`, "");
  if (!data.guidance.length && !data.pointers.length) lines.push(...EMPTY_RECORD_CTA, "");
}

export function document(view: View): string {
  if (view.error) return view.error;
  const lines: string[] = [];
  if (view.context) plainRecord(lines, view.tool || view.project || "Context", view.context);
  if (view.general) plainRecord(lines, view.general.person || "General", view.general);
  for (const warning of view.warnings || []) lines.push(`Warning: ${warning}`, "");
  lines.push(view.policy || "Current instructions take precedence.");
  return lines.join("\n");
}

function add(chunks: TextChunk[], ...parts: Array<string | TextChunk>) {
  for (const part of parts) {
    chunks.push(typeof part === "string" ? {__isChunk: true, text: part} : part);
  }
}

function styledRecord(chunks: TextChunk[], title: string, data: RecordData, roles: DocumentRoles) {
  add(chunks, bold(fg(roles.accent)(title)), "\n\n");
  for (const guidance of data.guidance) {
    add(chunks, fg(roles.accent)("· "), fg(roles.fg)(guidance), "\n\n");
  }
  for (const pointer of data.pointers) {
    add(chunks,
      fg(roles.muted)("→ "),
      fg(roles.accent)(`${pointer.label}:`),
      " ",
      fg(roles.fg)(pointer.target),
      "\n\n");
  }
  if (!data.guidance.length && !data.pointers.length) {
    add(chunks, fg(roles.muted)(EMPTY_RECORD_CTA[0]), "\n", fg(roles.muted)(EMPTY_RECORD_CTA[1]), "\n\n");
  }
}

export function documentStyled(view: View, roles: DocumentRoles): StyledText {
  if (view.error) return new StyledText([{__isChunk: true, text: view.error}]);
  const chunks: TextChunk[] = [];
  if (view.context) styledRecord(chunks, view.tool || view.project || "Context", view.context, roles);
  if (view.general) styledRecord(chunks, view.general.person || "General", view.general, roles);
  for (const warning of view.warnings || []) {
    add(chunks, fg(roles.muted)(`Warning: ${warning}`), "\n\n");
  }
  add(chunks, fg(roles.muted)(view.policy || "Current instructions take precedence."));
  return new StyledText(chunks);
}
