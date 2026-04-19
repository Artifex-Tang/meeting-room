// Preset time slots as defined by business convention
const PRESETS = [
  { key: 'morning',   label: '上午',    startTime: '09:00', endTime: '12:00' },
  { key: 'afternoon', label: '下午',    startTime: '14:00', endTime: '18:00' },
  { key: 'evening',   label: '晚上',    startTime: '19:00', endTime: '22:00' },
  { key: 'allday',    label: '全天',    startTime: '09:00', endTime: '18:00' },
]

Component({
  properties: {
    selected: { type: String, value: '' },
    takenSlots: { type: Array, value: [] },
  },

  data: {
    presets: [],
  },

  observers: {
    'selected, takenSlots'() {
      this._buildPresets()
    },
  },

  lifetimes: {
    attached() {
      this._buildPresets()
    },
  },

  methods: {
    _buildPresets() {
      const { slotToTime, timeToSlot, TOTAL_SLOTS } = require('../../utils/time')
      const takenSet = new Set(this.properties.takenSlots)
      const presets = PRESETS.map(p => {
        const from = require('../../utils/time').timeToSlot(p.startTime)
        const to   = require('../../utils/time').timeToSlot(p.endTime)
        let disabled = false
        for (let i = from; i < to; i++) {
          if (takenSet.has(i)) { disabled = true; break }
        }
        return { ...p, disabled, active: this.properties.selected === p.key }
      })
      this.setData({ presets })
    },

    selectPreset(e) {
      const { key } = e.currentTarget.dataset
      const preset = PRESETS.find(p => p.key === key)
      if (!preset) return
      this.triggerEvent('change', { preset: key, startTime: preset.startTime, endTime: preset.endTime })
    },
  },
})
