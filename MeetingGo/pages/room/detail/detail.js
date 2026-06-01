const http = require('../../../utils/request')
const { buildTakenSlots, today, formatDate } = require('../../../utils/time')

Page({
  data: {
    room: null,
    selectedDate: '',
    availability: null,
    takenSlots: [],
    loading: false,
  },

  onLoad(options) {
    const { id } = options
    this.roomId = id
    this.setData({ selectedDate: today() })
    this.loadRoom()
    this.loadAvailability()
  },

  async loadRoom() {
    try {
      const room = await http.get(`/rooms/${this.roomId}`)
      this.setData({ room })
      wx.setNavigationBarTitle({ title: room.name })
    } catch (e) {
      wx.showToast({ title: e.message || '加载失败', icon: 'none' })
    }
  },

  async loadAvailability() {
    this.setData({ loading: true })
    try {
      const data = await http.get(`/rooms/${this.roomId}/availability`, {
        date: this.data.selectedDate,
      })
      const takenSlots = Array.from(buildTakenSlots(data.slots_taken))
      this.setData({ availability: data, takenSlots })
    } catch (e) {
      wx.showToast({ title: e.message || '加载占用失败', icon: 'none' })
    } finally {
      this.setData({ loading: false })
    }
  },

  onDateChange(e) {
    this.setData({ selectedDate: e.detail.value })
    this.loadAvailability()
  },

  goBook() {
    wx.navigateTo({
      url: `/pages/booking/create/create?roomId=${this.roomId}&date=${this.data.selectedDate}`,
    })
  },

  goRecurrence() {
    wx.navigateTo({
      url: `/pages/booking/recurrence/recurrence?roomId=${this.roomId}`,
    })
  },
})
