import { api, cleanParams } from '../api/client'

/** Filename from a Content-Disposition header, or `fallback`. Only a plain quoted/unquoted name is trusted. */
export function filenameFrom(header, fallback) {
  const m = /filename="?([^";]+)"?/i.exec(header || '')
  const name = m?.[1]?.trim()
  return name && !/[\\/]/.test(name) ? name : fallback
}

function readText(blob) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result))
    reader.onerror = () => reject(reader.error)
    reader.readAsText(blob)
  })
}

/** An error response for a blob request arrives as a Blob; turn it back into the API's JSON error body. */
async function readableError(err) {
  const data = err?.response?.data
  if (data instanceof Blob) {
    try { err.response.data = JSON.parse(await readText(data)) } catch { /* not JSON: keep the generic message */ }
  }
  return err
}

/**
 * Download a file from an authenticated endpoint (a plain link can't send the bearer token).
 * Throws the original axios error, with its body readable by errorMessage().
 */
export async function downloadFile(path, params, fallbackName) {
  let r
  try {
    r = await api.get(path, { params: cleanParams(params), responseType: 'blob' })
  } catch (e) {
    throw await readableError(e)
  }
  const filename = filenameFrom(r.headers?.['content-disposition'], fallbackName)
  const url = URL.createObjectURL(r.data)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
  return filename
}
