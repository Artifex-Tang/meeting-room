const { slotToTime, TOTAL_SLOTS } = require('../../utils/time')

Component({
  properties: {
    takenSlots: {  // Set or Array of taken slot indices
      type: Array,
      value: [],
    },
    selectedStart: { type: Number, value: -1 },
    selectedEnd:   { type: Number, value: -1 },  // exclusive
    readonly: { type: Boolean, value: false },
  },

  data: {
    slots: [],
    dragging: false,
    dragStart: -1,
  },

  observers: {
    'takenSlots, selectedStart, selectedEnd'() {
      this._buildSlots()
    },
  },

  lifetimes: {
    attached() {
      this._buildSlots()
    },
  },

  methods: {
    _buildSlots() {
      const takenSet = new Set(this.properties.takenSlots)
      const { selectedStart, selectedEnd } = this.properties
      const slots = []
      for (let i = 0; i < TOTAL_SLOTS; i++) {
        const taken = takenSet.has(i)
        const selected = selectedStart >= 0 && i >= selectedStart && i < selectedEnd
        const label = slotToTime(i)
        slots.push({ index: i, label, taken, selected })
      }
      this.setData({ slots })
    },

    onSlotTap(e) {
      if (this.properties.readonly) return
      const { index } = e.currentTarget.dataset
      const slot = this.data.slots[index]
      if (slot.taken) return

      this.triggerEvent('slotTap', { index })
    },

    onSlotTouchStart(e) {
      if (this.properties.readonly) return
      const { index } = e.currentTarget.dataset
      if (this.data.slots[index].taken) return
      this.setData({ dragging: true, dragStart: index })
      this.triggerEvent('dragStart', { index })
    },

    onSlotTouchMove(e) {
      if (!this.data.dragging || this.properties.readonly) return
      // Touch move: find which slot we're over using touch coordinates
      const touch = e.touches[0]
      const query = this.createSelectorQuery()
      query.selectAll('.slot').boundingClientRect()
      query.exec((res) => {
        if (!res || !res[0]) return
        const rects = res[0]
        for (let i = 0; i < rects.length; i++) {
          const r = rects[i]
          if (touch.clientY >= r.top && touch.clientY <= r.bottom &&
              touch.clientX >= r.left && touch.clientX <= r.right) {
            if (!this.data.slots[i].taken) {
              this.triggerEvent('dragMove', { index: i })
            }
            break
          }
        }
      })
    },

    onSlotTouchEnd() {
      if (this.properties.readonly) return
      this.setData({ dragging: false, dragStart: -1 })
      this.triggerEvent('dragEnd', {})
    },
  },
})
