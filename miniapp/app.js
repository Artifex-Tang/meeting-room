App({
  globalData: {
    token: null,
    userInfo: null,
  },

  onLaunch() {
    this.globalData.token = wx.getStorageSync('token') || null
    this.globalData.userInfo = wx.getStorageSync('userInfo') || null
  },
})
