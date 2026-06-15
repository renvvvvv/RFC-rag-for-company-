export const getErrorMessage = (error: unknown, fallback: string): string => {
  if (error && typeof error === 'object' && 'response' in error) {
    const err = error as { response?: { data?: { detail?: string } } }
    return err.response?.data?.detail || fallback
  }
  return fallback
}
