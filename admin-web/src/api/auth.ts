import http from './http'

export interface AdminInfo {
  id: number
  username: string
  real_name: string | null
  must_change_password: number
}

export function adminLogin(username: string, password: string) {
  return http.post<any, { token: string; admin: AdminInfo }>('/auth/admin/login', {
    username,
    password,
  })
}

export function changePassword(oldPassword: string, newPassword: string) {
  return http.put('/admin/me/password', {
    old_password: oldPassword,
    new_password: newPassword,
  })
}
