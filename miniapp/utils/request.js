const { BASE_URL } = require('../config')

function request(method, url, data) {
  return new Promise((resolve, reject) => {
    const app = getApp()
    const token = app.globalData.token || wx.getStorageSync('token')

    wx.request({
      url: BASE_URL + url,
      method,
      data,
      header: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      success(res) {
        const body = res.data
        if (body.code === 0) {
          resolve(body.data)
        } else if (body.code === 40101) {
          // Token expired — clear and re-login
          app.globalData.token = null
          app.globalData.userInfo = null
          wx.removeStorageSync('token')
          wx.removeStorageSync('userInfo')
          wx.reLaunch({ url: '/pages/launch/launch' })
          reject(new Error('登录已过期，请重新登录'))
        } else {
          const err = new Error(body.message || '请求失败')
          err.code = body.code
          err.data = body.data
          reject(err)
        }
      },
      fail(err) {
        reject(new Error(err.errMsg || '网络错误'))
      },
    })
  })
}

const http = {
  get: (url, params) => {
    const query = params
      ? '?' + Object.entries(params)
          .filter(([, v]) => v !== undefined && v !== null && v !== '')
          .map(([k, v]) => `${k}=${encodeURIComponent(v)}`)
          .join('&')
      : ''
    return request('GET', url + query)
  },
  post: (url, data) => request('POST', url, data),
  put: (url, data) => request('PUT', url, data),
  delete: (url) => request('DELETE', url),
}

module.exports = http
