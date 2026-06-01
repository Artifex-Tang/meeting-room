const http = require('../../../utils/request')
const { isLoggedIn, getUser, logout } = require('../../../utils/auth')

Page({
  data: {
    userInfo: null,
    editing: false,
    realName: '',
    saving: false,
  },

  onShow() {
    if (!isLoggedIn()) { wx.reLaunch({ url: '/pages/launch/launch' }); return }
    const user = getUser()
    this.setData({ userInfo: user, realName: user?.real_name || '' })
  },

  startEdit() {
    this.setData({ editing: true })
  },

  onRealNameInput(e) {
    this.setData({ realName: e.detail.value })
  },

  async saveProfile() {
    const realName = this.data.realName.trim()
    if (!realName) { wx.showToast({ title: '姓名不能为空', icon: 'none' }); return }
    this.setData({ saving: true })
    try {
      await http.put('/users/me', { real_name: realName })
      const app = getApp()
      if (app.globalData.userInfo) {
        app.globalData.userInfo.real_name = realName
        wx.setStorageSync('userInfo', app.globalData.userInfo)
      }
      this.setData({ userInfo: { ...this.data.userInfo, real_name: realName }, editing: false })
      wx.showToast({ title: '已保存', icon: 'success' })
    } catch (e) {
      wx.showToast({ title: e.message || '保存失败', icon: 'none' })
    } finally {
      this.setData({ saving: false })
    }
  },

  onLogout() {
    wx.showModal({
      title: '退出登录',
      content: '确认退出？',
      success: (res) => {
        if (res.confirm) {
          logout()
          wx.reLaunch({ url: '/pages/launch/launch' })
        }
      },
    })
  },
})
