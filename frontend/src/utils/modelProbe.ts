export interface ProbeMessages {
  timeout: string
  invalid: string
  empty: string
}

/** NDJSON frames may be split anywhere in the network stream, including UTF-8. */
export async function readModelProbe(
  request: (controller: AbortController) => Promise<Response>,
  messages: ProbeMessages,
  timeoutMs = 30000
): Promise<void> {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeoutMs)
  let reader: ReadableStreamDefaultReader<Uint8Array> | undefined
  try {
    const response = await request(controller)
    if (!response.ok || !response.body) throw new Error(messages.invalid)
    reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    let received = false
    function frame(line: string) {
      if (!line.trim()) return
      let item: { error?: string; content?: string }
      try {
        item = JSON.parse(line)
      } catch {
        throw new Error(messages.invalid)
      }
      if (!item || typeof item !== 'object') throw new Error(messages.invalid)
      if (item.error) throw new Error(item.error)
      if (typeof item.content === 'string' && item.content.trim()) received = true
    }
    while (true) {
      const { done, value } = await reader.read()
      buffer += decoder.decode(value, { stream: !done })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''
      lines.forEach(frame)
      if (done) {
        frame(buffer)
        break
      }
    }
    if (!received) throw new Error(messages.empty)
  } catch (error) {
    if (controller.signal.aborted) throw new Error(messages.timeout)
    throw error
  } finally {
    clearTimeout(timer)
    await reader?.cancel().catch(() => {})
  }
}
