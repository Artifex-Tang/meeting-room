const http = require('../../../utils/request')
const { today, formatDate } = require('../../../utils/time')

const WEEKDAYS = [
  { value: 0, label: '周一' },
  { value: 1, label: '周二' },
  { value: 2, label: '周三' },
  { value: 3, label: '周四' },
  { value: 4, label: '周五' },
  { value: 5, label: '周六' },
  { value: 6, label: '周日' },
]

Page({
  data: {
    roomId: null,
    frequency: 'WEEKLY',
    weekdays: [],
    monthDay: 1,
    startDate: '',
    endDate: '',
    startTime: '09:00',
    endTime: '10:00',
    title: '',
    submitting: false,
    weekdayOptions: WEEKDAYS,
    estimatedCount: 0,
  },

  onLoad(options) {
    this.roomId = options.roomId
    const t = today()
    this.setData({ roomId: options.roomId, startDate: t, endDate: t })
  },

  setFrequency(e) {
    this.setData({ frequency: e.currentTarget.dataset.freq, weekdays: [] })
    this._calcEstimate()
  },

  toggleWeekday(e) {
    const { value } = e.currentTarget.dataset
    const weekdays = [...this.data.weekdays]
    const idx = weekdays.indexOf(value)
    if (idx >= 0) weekdays.splice(idx, 1)
    else weekdays.push(value)
    this.setData({ weekdays })
    this._calcEstimate()
  },

  onMonthDayChange(e) {
    this.setData({ monthDay: Number(e.detail.value) })
    this._calcEstimate()
  },

  onStartDateChange(e) {
    this.setData({ startDate: e.detail.value })
    this._calcEstimate()
  },

  onEndDateChange(e) {
    this.setData({ endDate: e.detail.value })
    this._calcEstimate()
  },

  onStartTimeChange(e) {
    this.setData({ startTime: e.detail.value })
  },

  onEndTimeChange(e) {
    this.setData({ endTime: e.detail.value })
  },

  onTitleInput(e) {
    this.setData({ title: e.detail.value })
  },

  _calcEstimate() {
    const { frequency, weekdays, monthDay, startDate, endDate } = this.data
    if (!startDate || !endDate) return
    const start = new Date(startDate)
    const end = new Date(endDate)
    if (end <= start) { this.setData({ estimatedCount: 0 }); return }
    let count = 0
    const cur = new Date(start)
    while (cur <= end) {
      const dow = (cur.getDay() + 6) % 7  // 0=Mon..6=Sun
      if (frequency === 'DAILY') count++
      else if (frequency === 'WEEKLY' && weekdays.includes(dow)) count++
      else if (frequency === 'MONTHLY' && cur.getDate() === monthDay) count++
      cur.setDate(cur.getDate() + 1)
    }
    this.setData({ estimatedCount: count })
  },

  async onSubmit() {
    const { frequency, weekdays, monthDay, startDate, endDate, startTime, endTime, title } = this.data
    if (frequency === 'WEEKLY' && weekdays.length === 0) {
      wx.showToast({ title: '请选择重复的星期', icon: 'none' }); return
    }
    if (!startDate || !endDate) {
      wx.showToast({ title: '请选择日期范围', icon: 'none' }); return
    }

    this.setData({ submitting: true })
    try {
      const payload = {
        room_id: Number(this.roomId),
        frequency,
        weekdays: frequency === 'WEEKLY' ? weekdays : undefined,
        month_day: frequency === 'MONTHLY' ? monthDay : undefined,
        start_date: startDate,
        end_date: endDate,
        start_time: startTime,
        end_time: endTime,
        title: title || undefined,
      }
      const result = await http.post('/bookings/recurrence', payload)
      wx.showModal({
        title: '周期预订成功',
        content: `已创建 ${result.count} 次预订`,
        showCancel: false,
        success: () => wx.navigateBack(),
      })
    } catch (e) {
      if (e.code === 40902 && e.data?.conflicts) {
        const conflicts = e.data.conflicts
        const preview = conflicts.slice(0, 3).map(c => c.date).join('、')
        const more = conflicts.length > 3 ? `等共 ${conflicts.length} 天` : ''
        wx.showModal({
          title: '存在冲突',
          content: `以下日期有冲突：${preview}${more}，请缩短范围或调整时间。`,
          showCancel: false,
        })
      } else {
        wx.showToast({ title: e.message || '提交失败', icon: 'none' })
      }
    } finally {
      this.setData({ submitting: false })
    }
  },
})
