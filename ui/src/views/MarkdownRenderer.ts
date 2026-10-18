import { Marked } from "marked";
import sanitizeHtml from "sanitize-html";

const ALLOWED_TAGS = [
  "p",
  "br",
  "hr",
  "h1",
  "h2",
  "h3",
  "h4",
  "h5",
  "h6",
  "strong",
  "em",
  "del",
  "code",
  "pre",
  "blockquote",
  "ul",
  "ol",
  "li",
  "a",
  "table",
  "thead",
  "tbody",
  "tr",
  "th",
  "td",
];

/**
 * Renders user Markdown to HTML that is safe to embed unescaped.
 *
 * The Markdown parser passes raw HTML through, so its output is treated as untrusted and run
 * through an allow-list sanitiser: no scripts, event handlers, styles, images or iframes, and
 * links only to http, https and mailto URLs.
 */
export class MarkdownRenderer {
  private readonly marked = new Marked({ gfm: true, breaks: true, async: false });

  render(markdown: string): string {
    const html = this.marked.parse(markdown, { async: false });
    return sanitizeHtml(html, {
      allowedTags: ALLOWED_TAGS,
      allowedAttributes: { a: ["href", "title", "rel"], th: ["align"], td: ["align"] },
      allowedSchemes: ["http", "https", "mailto"],
      allowedSchemesAppliedToAttributes: ["href"],
      allowProtocolRelative: false,
      disallowedTagsMode: "discard",
      transformTags: {
        a: sanitizeHtml.simpleTransform("a", { rel: "noopener noreferrer nofollow" }),
      },
    });
  }
}
