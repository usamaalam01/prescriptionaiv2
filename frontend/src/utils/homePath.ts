import type { User } from './types'

/** Role landing page after login / password change (no welcome page for admin/pharmacist). */
export function homePathForUser(user: Pick<User, 'role' | 'status'>): string {
  if (user.status !== 'active') return '/registration-status'
  if (user.role === 'administrator') return '/admin'
  if (user.role === 'pharmacist') return '/analyzer'
  if (user.role === 'reviewer') return '/research/evaluation'
  return '/'
}
