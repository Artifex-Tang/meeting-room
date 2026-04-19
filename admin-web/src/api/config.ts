import http from './http'

export function getConfig() {
  return http.get<any, Record<string, string>>('/admin/config')
}

export function updateConfig(data: Record<string, number | string>) {
  return http.put<any, Record<string, string>>('/admin/config', data)
}
