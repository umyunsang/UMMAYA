// utils/secureStorage removed in P1+P2 (Spec 1633); KOSMOS uses process-scoped FriendliAI secrets, not OS keychain.
const getMacOsKeychainStorageServiceName = (): string => 'kosmos'

export async function maybeRemoveApiKeyFromMacOSKeychainThrows(): Promise<void> {
  // KOSMOS: no OS keychain — API keys are session/process-scoped.
  void getMacOsKeychainStorageServiceName()
}

export function normalizeApiKeyForConfig(apiKey: string): string {
  return apiKey.slice(-20)
}
