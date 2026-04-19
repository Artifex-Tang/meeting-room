import http from './http'

export interface User {
  id: number
  openid: string
  nickname: string | null
  real_name: string | null
  phone: string | null
  dept_id: number | null
  status: number
}

export interface Department {
  id: number
  name: string
  parent_id: number | null
}

export function listUsers(params: {
  keyword?: string
  dept_id?: number
  status?: number
  page?: number
  page_size?: number
}) {
  return http.get<any, { list: User[]; total: number; page: number }>('/admin/users', { params })
}

export function updateUser(id: number, data: { real_name?: string; dept_id?: number; status?: number }) {
  return http.put<any, User>(`/admin/users/${id}`, data)
}

export function getUserRooms(userId: number) {
  return http.get(`/admin/users/${userId}/rooms`)
}

export function listDepartments() {
  return http.get<any, Department[]>('/admin/departments')
}

export function createDepartment(data: { name: string; parent_id?: number | null }) {
  return http.post<any, Department>('/admin/departments', data)
}

export function updateDepartment(id: number, data: { name?: string; parent_id?: number | null }) {
  return http.put<any, Department>(`/admin/departments/${id}`, data)
}

export function deleteDepartment(id: number) {
  return http.delete(`/admin/departments/${id}`)
}
