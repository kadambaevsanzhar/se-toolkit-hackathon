/**
 * Generate a UUID v4 without relying on crypto.randomUUID(),
 * which is unavailable in non-secure (HTTP) contexts.
 */
export function safeUUID() {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
    const r = Math.random() * 16 | 0
    const v = c === 'x' ? r : (r & 0x3 | 0x8)
    return v.toString(16)
  })
}
