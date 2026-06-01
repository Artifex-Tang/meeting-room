const http = require('../../utils/request')
const { isLoggedIn } = require('../../utils/auth')

Page({
  data: {
    rooms: [],
    loading: false,
    keyword: '',
  },

  onShow() {
    if (!isLoggedIn()) {
      wx.reLaunch({ url: '/pages/launch/launch' })
      return
    }
    this.loadRooms()
  },

  async loadRooms() {
    this.setData({ loading: true })
    try {
      const rooms = await http.get('/rooms', {
        keyword: this.data.keyword || undefined,
        status: 1,
      })
      this.setData({ rooms })
    } catch (e) {
      wx.showToast({ title: e.message || '加载失败', icon: 'none' })
    } finally {
      this.setData({ loading: false })
    }
  },

  onKeywordInput(e) {
    this.setData({ keyword: e.detail.value })
  },

  onSearch() {
    this.loadRooms()
  },

  goDetail(e) {
    const { id } = e.currentTarget.dataset
    wx.navigateTo({ url: `/pages/room/detail/detail?id=${id}` })
  },
})
