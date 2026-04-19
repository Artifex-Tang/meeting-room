import http from './http'

export interface Booking {
  id: number
  room_id: number
  user_id: number
  date: string
  start_at: string
  end_at: string
  preset: string | null
  title: string | null
  status: number
  cancel_reason: string | null
  recurrence_id: number | null
}

export function listBookings(params: {
  room_id?: number
  user_id?: number
  date_from?: string
  date_to?: string
  status?: number
  page?: number
  page_size?: number
}) {
  return http.get<any, { list: Booking[]; total: number; page: number }>('/admin/bookings', {
    params,
  })
}

export function cancelBooking(id: number, reason?: string) {
  return http.post<any, Booking>(`/admin/bookings/${id}/cancel`, { reason })
}

export function getStatsOverview() {
  return http.get<any, {
    today_bookings: number
    week_bookings: number
    top_rooms: { room_id: number; room_name: string; count: number }[]
  }>('/admin/stats/overview')
}
