<template>
  <div>
    <div class="toolbar">
      <el-date-picker
        v-model="dateRange"
        type="daterange"
        range-separator="至"
        start-placeholder="开始日期"
        end-placeholder="结束日期"
        value-format="YYYY-MM-DD"
        style="width:260px"
        @change="loadBookings"
      />
      <el-select v-model="statusFilter" placeholder="状态" clearable style="width:110px;margin-left:8px" @change="loadBookings">
        <el-option label="正常" :value="1" />
        <el-option label="已取消" :value="0" />
      </el-select>
      <el-input
        v-model="roomIdFilter"
        placeholder="会议室ID"
        clearable
        style="width:110px;margin-left:8px"
        @change="loadBookings"
      />
    </div>

    <el-table :data="bookings" v-loading="loading" stripe>
      <el-table-column prop="id" label="ID" width="70" />
      <el-table-column prop="room_id" label="会议室" width="90" />
      <el-table-column prop="date" label="日期" width="110" />
      <el-table-column label="时间">
        <template #default="{ row }">{{ row.start_at }} – {{ row.end_at }}</template>
      </el-table-column>
      <el-table-column prop="title" label="主题" show-overflow-tooltip />
      <el-table-column prop="user_id" label="预订人ID" width="90" />
      <el-table-column label="状态" width="90">
        <template #default="{ row }">
          <el-tag :type="row.status ? 'success' : 'info'">{{ row.status ? '正常' : '已取消' }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="cancel_reason" label="取消原因" show-overflow-tooltip />
      <el-table-column label="操作" width="80">
        <template #default="{ row }">
          <el-button
            v-if="row.status === 1"
            text type="danger"
            @click="handleCancel(row)"
          >取消</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-pagination
      v-model:current-page="page"
      :page-size="20"
      :total="total"
      layout="total, prev, pager, next"
      class="pagination"
      @current-change="loadBookings"
    />

    <!-- Cancel dialog -->
    <el-dialog v-model="cancelVisible" title="取消预订" width="400px">
      <el-form label-width="80px">
        <el-form-item label="取消原因">
          <el-input v-model="cancelReason" type="textarea" :rows="3" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="cancelVisible = false">关闭</el-button>
        <el-button type="danger" :loading="cancelling" @click="confirmCancel">确认取消</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { listBookings, cancelBooking, type Booking } from '@/api/bookings'

const bookings = ref<Booking[]>([])
const total = ref(0)
const page = ref(1)
const dateRange = ref<[string, string] | null>(null)
const statusFilter = ref<number | undefined>(undefined)
const roomIdFilter = ref('')
const loading = ref(false)

const cancelVisible = ref(false)
const cancelling = ref(false)
const cancelTarget = ref<Booking | null>(null)
const cancelReason = ref('')

onMounted(loadBookings)

async function loadBookings() {
  loading.value = true
  try {
    const res = await listBookings({
      date_from: dateRange.value?.[0],
      date_to: dateRange.value?.[1],
      status: statusFilter.value,
      room_id: roomIdFilter.value ? Number(roomIdFilter.value) : undefined,
      page: page.value,
    })
    bookings.value = res.list
    total.value = res.total
  } finally {
    loading.value = false
  }
}

function handleCancel(booking: Booking) {
  cancelTarget.value = booking
  cancelReason.value = ''
  cancelVisible.value = true
}

async function confirmCancel() {
  if (!cancelTarget.value) return
  cancelling.value = true
  try {
    await cancelBooking(cancelTarget.value.id, cancelReason.value || undefined)
    ElMessage.success('已取消')
    cancelVisible.value = false
    loadBookings()
  } finally {
    cancelling.value = false
  }
}
</script>

<style scoped>
.toolbar { display: flex; align-items: center; margin-bottom: 16px; }
.pagination { margin-top: 16px; justify-content: flex-end; }
</style>
