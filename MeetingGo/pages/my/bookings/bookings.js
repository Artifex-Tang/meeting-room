const http = require('../../../utils/request')
const { isLoggedIn } = require('../../../utils/auth')

Page({
  data: {
    bookings: [],
    loading: false,
    statusTab: 'active',  // 'active' | 'all'
    page: 1,
    total: 0,
    cancelDeadlineMinutes: 30,
  },

  onShow() {
    if (!isLoggedIn()) { wx.reLaunch({ url: '/pages/launch/launch' }); return }
    this.setData({ page: 1 })
    this.loadBookings()
    this.loadConfig()
  },

  async loadConfig() {
    try {
      const cfg = await http.get('/config/public')
      if (cfg.cancel_advance_hours !== undefined) {
        // backend stores hours; convert to minutes for deadline comparison
        this.setData({ cancelDeadlineMinutes: Number(cfg.cancel_advance_hours) * 60 })
      }
    } catch (_) {}
  },

  async loadBookings() {
    this.setData({ loading: true })
    try {
      const res = await http.get('/bookings', {
        scope: 'mine',
        status: this.data.statusTab === 'active' ? 'active' : 'all',
        page: this.data.page,
      })
      this.setData({ bookings: res.list, total: res.total })
    } catch (e) {
      wx.showToast({ title: e.message || '加载失败', icon: 'none' })
    } finally {
      this.setData({ loading: false })
    }
  },

  switchTab(e) {
    this.setData({ statusTab: e.currentTarget.dataset.tab, page: 1 })
    this.loadBookings()
  },

  canCancel(booking) {
    if (!booking.status) return false
    const startMs = new Date(booking.start_at).getTime()
    const nowMs = Date.now()
    const deadlineMs = this.data.cancelDeadlineMinutes * 60 * 1000
    return startMs - nowMs > deadlineMs
  },

  goDetail(e) {
    const { id } = e.currentTarget.dataset
    wx.navigateTo({ url: `/pages/booking/detail/detail?id=${id}` })
  },

  async cancelBooking(e) {
    const { id } = e.currentTarget.dataset
    const confirmed = await new Promise(resolve =>
      wx.showModal({ title: '确认取消', content: '确认取消此预订？', success: r => resolve(r.confirm) })
    )
    if (!confirmed) return
    try {
      await http.post(`/bookings/${id}/cancel`, {})
      wx.showToast({ title: '已取消', icon: 'success' })
      this.loadBookings()
    } catch (e) {
      if (e.code === 42201) {
        wx.showModal({ title: '无法取消', content: `距开始不足 ${this.data.cancelDeadlineMinutes} 分钟，已超过取消截止时间`, showCancel: false })
      } else {
        wx.showToast({ title: e.message || '取消失败', icon: 'none' })
      }
    }
  },

  formatTime(isoStr) {
    if (!isoStr) return ''
    return isoStr.slice(11, 16)
  },
})
