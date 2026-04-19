import http from './http'

export interface Room {
  id: number
  name: string
  location: string | null
  capacity: number | null
  facilities: string | null
  description: string | null
  status: number
}

export interface RoomPermissions {
  users: UserSimple[]
  depts: DeptSimple[]
}

export interface UserSimple {
  id: number
  openid: string
  nickname: string | null
  real_name: string | null
  dept_id: number | null
}

export interface DeptSimple {
  id: number
  name: string
}

export function listRooms(params: {
  keyword?: string
  status?: number
  page?: number
  page_size?: number
}) {
  return http.get<any, { list: Room[]; total: number; page: number }>('/admin/rooms', { params })
}

export function createRoom(data: Partial<Room>) {
  return http.post<any, Room>('/admin/rooms', data)
}

export function updateRoom(id: number, data: Partial<Room>) {
  return http.put<any, Room>(`/admin/rooms/${id}`, data)
}

export function deleteRoom(id: number) {
  return http.delete(`/admin/rooms/${id}`)
}

export function getRoomPermissions(id: number) {
  return http.get<any, RoomPermissions>(`/admin/rooms/${id}/permissions`)
}

export function grantUsers(roomId: number, userIds: number[]) {
  return http.post(`/admin/rooms/${roomId}/permissions/users`, { user_ids: userIds })
}

export function revokeUser(roomId: number, userId: number) {
  return http.delete(`/admin/rooms/${roomId}/permissions/users/${userId}`)
}

export function grantDepts(roomId: number, deptIds: number[]) {
  return http.post(`/admin/rooms/${roomId}/permissions/depts`, { dept_ids: deptIds })
}

export function revokeDept(roomId: number, deptId: number) {
  return http.delete(`/admin/rooms/${roomId}/permissions/depts/${deptId}`)
}
