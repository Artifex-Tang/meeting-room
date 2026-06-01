const http = require('../../../utils/request')
const { buildTakenSlots, slotToTime, timeToSlot } = require('../../../utils/time')

// Template IDs configured in WeChat MP backend (must match notify templates)
const SUBSCRIBE_TMPL_IDS = [
  'booking_success_tmpl_id',   // replace with actual template IDs
  'booking_upcoming_tmpl_id',
  'booking_cancelled_tmpl_id',
]

Page({
  data: {
    roomId: null,
    date: '',
    takenSlots: [],
    mode: 'preset',  // 'preset' | 'custom'
    selectedPreset: '',
    customStart: -1,
    customEnd: -1,
    title: '',
    submitting: false,
    availability: null,
  },

  onLoad(options) {
    this.roomId = options.roomId
    this.setData({ date: options.date, roomId: options.roomId })
    this.loadAvailability()
  },

  async loadAvailability() {
    try {
      const data = await http.get(`/rooms/${this.roomId}/availability`, { date: this.data.date })
      const takenSlots = Array.from(buildTakenSlots(data.slots_taken))
      this.setData({ availability: data, takenSlots })
    } catch (e) {
      wx.showToast({ title: e.message || '加载失败', icon: 'none' })
    }
  },

  switchMode(e) {
    const { mode } = e.currentTarget.dataset
    this.setData({ mode, selectedPreset: '', customStart: -1, customEnd: -1 })
  },

  onPresetChange(e) {
    const { preset, startTime, endTime } = e.detail
    this.setData({ selectedPreset: preset, customStart: -1, customEnd: -1 })
    this._presetStartTime = startTime
    this._presetEndTime = endTime
  },

  onSlotTap(e) {
    if (this.data.mode !== 'custom') return
    const { index } = e.detail
    const { customStart, customEnd } = this.data
    if (customStart < 0) {
      this.setData({ customStart: index, customEnd: index + 1 })
    } else if (index < customStart) {
      // extend selection upward
      if (!this._hasConflictBetween(index, customStart)) {
        this.setData({ customStart: index })
      } else {
        wx.showToast({ title: '跨越已占用时段', icon: 'none' })
      }
    } else if (index >= customEnd) {
      // extend selection downward
      if (!this._hasConflictBetween(customEnd, index + 1)) {
        this.setData({ customEnd: index + 1 })
      } else {
        wx.showToast({ title: '跨越已占用时段', icon: 'none' })
      }
    } else {
      // tap inside existing selection — reset
      this.setData({ customStart: index, customEnd: index + 1 })
    }
  },

  _hasConflictBetween(from, to) {
    const takenSet = new Set(this.data.takenSlots)
    for (let i = from; i < to; i++) {
      if (takenSet.has(i)) return true
    }
    return false
  },

  onTitleInput(e) {
    this.setData({ title: e.detail.value })
  },

  async onSubmit() {
    const { mode, selectedPreset, customStart, customEnd, title, date, roomId } = this.data

    if (mode === 'preset' && !selectedPreset) {
      wx.showToast({ title: '请选择预设时段', icon: 'none' }); return
    }
    if (mode === 'custom' && customStart < 0) {
      wx.showToast({ title: '请选择时间段', icon: 'none' }); return
    }

    // T-MP-09: request subscribe before submitting booking
    await this._requestSubscribe()

    this.setData({ submitting: true })
    try {
      const payload = { room_id: Number(roomId), date, title: title || undefined }
      if (mode === 'preset') {
        payload.preset = selectedPreset
      } else {
        payload.start_time = slotToTime(customStart)
        payload.end_time   = slotToTime(customEnd)
      }

      await http.post('/bookings', payload)
      wx.showToast({ title: '预订成功', icon: 'success' })
      setTimeout(() => wx.navigateBack(), 1500)
    } catch (e) {
      if (e.code === 40901) {
        const c = e.data?.conflict_with
        const msg = c ? `与${c.user}的预订冲突（${c.start_at?.slice(11,16)}–${c.end_at?.slice(11,16)}）` : '时间冲突'
        wx.showModal({ title: '预订失败', content: msg, showCancel: false })
      } else {
        wx.showToast({ title: e.message || '预订失败', icon: 'none' })
      }
    } finally {
      this.setData({ submitting: false })
    }
  },

  // T-MP-09: wx.requestSubscribeMessage must be triggered by user tap
  _requestSubscribe() {
    return new Promise((resolve) => {
      wx.requestSubscribeMessage({
        tmplIds: SUBSCRIBE_TMPL_IDS,
        success(res) {
          const results = {}
          for (const id of SUBSCRIBE_TMPL_IDS) {
            results[id] = res[id] || 'reject'
          }
          http.post('/notify/subscribe-report', { results }).catch(() => {})
          resolve()
        },
        fail() { resolve() },  // subscribe failure must not block booking
      })
    })
  },
})
