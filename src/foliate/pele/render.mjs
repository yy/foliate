// Render Mermaid sources to SVG with the vendored Pele bundle.
// stdin: {"sources": [...], "options": {...}}
// stdout: one {"svg": ...} or {"error": ...} per source, as a JSON array.
import { render } from "./pele.mjs";

process.stdin.setEncoding("utf8");
let input = "";
for await (const chunk of process.stdin) input += chunk;

const { sources, options } = JSON.parse(input);
const results = sources.map((source, index) => {
  try {
    return { svg: render(source, { ...options, idPrefix: `pele-${index}-` }).svg };
  } catch (error) {
    // Pele's parse errors span lines: summary, source excerpt, caret, expectation.
    const lines = String(error.message).split("\n").filter((line) => line.trim());
    return { error: lines.length > 1 ? `${lines[0]} ${lines.at(-1)}` : lines[0] };
  }
});
process.stdout.write(JSON.stringify(results));
