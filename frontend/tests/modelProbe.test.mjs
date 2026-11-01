import { readFileSync } from 'node:fs'
import assert from 'node:assert/strict'
import test from 'node:test'
import ts from 'typescript'

const source = readFileSync(new URL('../src/utils/modelProbe.ts', import.meta.url), 'utf8')
const { outputText } = ts.transpileModule(source, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ES2022 } })
const { readModelProbe } = await import(`data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`)
const messages = { timeout: '超时', invalid: '格式错误', empty: '空响应' }

test('handles fragmented JSON and UTF-8 and a final frame without newline', async () => {
  const bytes = new TextEncoder().encode('{"content":"连接成功"}\n{"content":"2"}')
  const stream = new ReadableStream({ start(controller) { for (const byte of bytes) controller.enqueue(new Uint8Array([byte])); controller.close() } })
  await readModelProbe(async () => new Response(stream), messages)
})
test('propagates upstream error frames', async () => {
  await assert.rejects(readModelProbe(async () => new Response('{"error":"密钥无效"}\n'), messages), /密钥无效/)
})
test('an empty stream is not a successful connection', async () => {
  await assert.rejects(readModelProbe(async () => new Response(''), messages), /空响应/)
})
test('malformed and unsuccessful responses are rejected', async () => {
  await assert.rejects(readModelProbe(async () => new Response('invalid'), messages), /格式错误/)
  await assert.rejects(readModelProbe(async () => new Response('', { status: 401 }), messages), /格式错误/)
})
test('aborts the actual request on timeout', async () => {
  let aborted = false
  await assert.rejects(readModelProbe((controller) => new Promise((_, reject) => {
    controller.signal.addEventListener('abort', () => { aborted = true; reject(new Error('AbortError')) })
  }), messages, 10), /超时/)
  assert.equal(aborted, true)
})
