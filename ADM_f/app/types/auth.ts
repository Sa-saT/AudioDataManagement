export type Role = 'guest' | 'user' | 'creator' | 'admin'

export interface AuthUser {
  id: string
  username: string
  role: Exclude<Role, 'guest'>
  licenseCode: string
  monthlyQuotaTokens: number
}

export interface ActivateApiResponse {
  access_token: string
  token_type: string
  expires_at: string
  user: {
    id: string
    username: string
    role: 'user' | 'creator' | 'admin'
    license_code: string
    monthly_quota_tokens: number
  }
}
