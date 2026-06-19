import type { LocalCommandResult } from '../../types/command.js'
import { openBrowser } from '../../utils/browser.js'

export async function call(): Promise<LocalCommandResult> {
  const url = 'https://ummaya-docs.pages.dev/en/'
  const success = await openBrowser(url)

  if (success) {
    return { type: 'text', value: 'Opening sticker page in browser…' }
  } else {
    return {
      type: 'text',
      value: `Failed to open browser. Visit: ${url}`,
    }
  }
}
