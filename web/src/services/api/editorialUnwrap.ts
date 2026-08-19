/** Unwrap NI API envelope from axios response. */
export function unwrapData<T = unknown>(res: unknown): T {
  const ax = res as { data?: { success?: boolean; data?: T } & T };
  if (ax?.data && typeof ax.data === 'object' && 'data' in ax.data && ax.data.data !== undefined) {
    return ax.data.data as T;
  }
  return (ax?.data as T) ?? (res as T);
}
