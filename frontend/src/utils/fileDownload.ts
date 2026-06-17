import { useAuthStore } from '@/stores/authStore'

function getToken(): string | null {
  return useAuthStore.getState().token
}

async function fetchFile(url: string): Promise<Blob> {
  const token = getToken()
  const res = await fetch(url, {
    headers: token ? { Authorization: `Bearer ${token}` } : undefined,
  })
  if (!res.ok) {
    throw new Error(`文件请求失败: ${res.status}`)
  }
  return res.blob()
}

export async function openPreview(url: string): Promise<void> {
  const blob = await fetchFile(url)
  const blobUrl = URL.createObjectURL(blob)
  window.open(blobUrl, '_blank')
}

export async function downloadFile(url: string, filename?: string): Promise<void> {
  const blob = await fetchFile(url)
  const blobUrl = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = blobUrl
  a.download = filename || 'download'
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(blobUrl)
}

export function formatFileSize(bytes?: number): string {
  if (bytes === undefined || bytes === null) return '-'
  if (bytes === 0) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(1024))
  const size = bytes / Math.pow(1024, i)
  return `${size.toFixed(i === 0 ? 0 : 2)} ${units[i]}`
}
