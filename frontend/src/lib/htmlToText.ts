/** Convert legacy HTML-formatted content to text without inserting it into the document. */
export function htmlToText(value: string): string {
  // Keep this usable during Next.js server rendering as well as in the browser.
  // React renders the result as text, so decoded entities cannot become markup.
  return value
    .replace(/<\/(div|p|li|h[1-6]|br)>/gi, '\n')
    .replace(/<[^>]*>/g, '')
    .replace(/&nbsp;/gi, ' ')
    .replace(/&amp;/gi, '&')
    .replace(/&lt;/gi, '<')
    .replace(/&gt;/gi, '>')
    .replace(/&quot;/gi, '"')
    .replace(/&#39;|&apos;/gi, "'")
}
