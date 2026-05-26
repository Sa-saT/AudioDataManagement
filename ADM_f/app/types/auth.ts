export type Role = 'guest' | 'user' | 'creator' | 'admin'

export interface LicensePayload {
  username: string
  role: Exclude<Role, 'guest'>
  licenseId: string
  issuedAt: string
  expiresAt?: string
}
