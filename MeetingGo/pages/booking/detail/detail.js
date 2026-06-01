const http = require('../../../utils/request')

Page({
  data: {
    booking: null,
    loading: true,
  },

  onLoad(options) {
    this.bookingId = options.id
    this.load()
  },

  async load() {
    this.setData({ loading: true })
    try {
      const booking = await http.get(`/bookings/${this.bookingId}`)
      this.setData({ booking })
    } catch (e) {
      wx.showToast({ title: e.message || '加载失败', icon: 'none' })
    } finally {
      this.setData({ loading: false })
    }
  },

  async cancelBooking() {
    const confirmed = await new Promise(resolve =>
      wx.showModal({ title: '确认取消', content: '确认取消此预订？', success: r => resolve(r.confirm) })
    )
    if (!confirmed) return
    try {
      await http.post(`/bookings/${this.bookingId}/cancel`, {})
      wx.showToast({ title: '已取消', icon: 'success' })
      this.load()
    } catch (e) {
      wx.showToast({ title: e.message || '取消失败', icon: 'none' })
    }
  },
})
