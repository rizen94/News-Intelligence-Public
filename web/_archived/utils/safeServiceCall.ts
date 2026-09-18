/**
 * Call an optional API service method without throwing if missing or rejecting.
 */
export async function safeServiceCall<T>(
  service: Record<string, unknown>,
  methodName: string,
  args: unknown[] = []
): Promise<T | null> {
  const fn = service[methodName];
  if (typeof fn !== 'function') return null;
  try {
    return (await (fn as (...a: unknown[]) => Promise<T>).apply(
      service,
      args
    )) as T;
  } catch {
    return null;
  }
}
