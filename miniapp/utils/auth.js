const http = require('./request')

async function wechatLogin() {
  return new Promise((resolve, reject) => {
    wx.login({
      success: async ({ code }) => {
        try {
          const app = getApp()
          const userInfo = await http.post('/auth/wechat', {
            code,
            nickname: app.globalData.userInfo?.nickname || '',
            avatar_url: app.globalData.userInfo?.avatarUrl || '',
          })
          app.globalData.token = userInfo.token
          app.globalData.userInfo = userInfo.user
          wx.setStorageSync('token', userInfo.token)
          wx.setStorageSync('userInfo', userInfo.user)
          resolve(userInfo)
        } catch (e) {
          reject(e)
        }
      },
      fail: reject,
    })
  })
}

function isLoggedIn() {
  const token = wx.getStorageSync('token')
  return !!token
}

function getUser() {
  return wx.getStorageSync('userInfo') || null
}

function logout() {
  const app = getApp()
  app.globalData.token = null
  app.globalData.userInfo = null
  wx.removeStorageSync('token')
  wx.removeStorageSync('userInfo')
}

module.exports = { wechatLogin, isLoggedIn, getUser, logout }
