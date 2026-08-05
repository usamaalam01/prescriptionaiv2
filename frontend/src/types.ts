export type Role = 'administrator' | 'pharmacist' | 'reviewer'

export interface User {
  id: string
  username: string
  role: Role
  status: string
  must_change_password: boolean
}

export interface LoginResponse {
  access_token: string
  refresh_token: string
  token_type: string
  user: User
}
