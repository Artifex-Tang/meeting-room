const { wechatLogin } = require('../../utils/auth')

Page({
  data: {
    loading: true,
    error: '',
    showProfileForm: false,
    realName: '',
  },

  async onLoad() {
    try {
      const result = await wechatLogin()
      if (result.need_profile) {
        this.setData({ loading: false, showProfileForm: true })
      } else {
        this._goHome()
      }
    } catch (e) {
      this.setData({ loading: false, error: e.message || '登录失败，请重试' })
    }
  },

  async submitProfile() {
    const realName = this.data.realName.trim()
    if (!realName) {
      wx.showToast({ title: '请输入真实姓名', icon: 'none' })
      return
    }
    const http = require('../../utils/request')
    try {
      await http.put('/users/me', { real_name: realName })
      const app = getApp()
      if (app.globalData.userInfo) {
        app.globalData.userInfo.real_name = realName
        wx.setStorageSync('userInfo', app.globalData.userInfo)
      }
      this._goHome()
    } catch (e) {
      wx.showToast({ title: e.message || '保存失败', icon: 'none' })
    }
  },

  onRealNameInput(e) {
    this.setData({ realName: e.detail.value })
  },

  retry() {
    this.setData({ loading: true, error: '' })
    this.onLoad()
  },

  _goHome() {
    wx.switchTab({ url: '/pages/index/index' })
  },
})
