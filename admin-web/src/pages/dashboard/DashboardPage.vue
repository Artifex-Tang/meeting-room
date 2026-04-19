<template>
  <div>
    <h2 class="page-title">数据总览</h2>

    <el-row :gutter="20" class="stat-row">
      <el-col :span="8">
        <el-card class="stat-card">
          <div class="stat-label">今日预订</div>
          <div class="stat-value">{{ stats?.today_bookings ?? '—' }}</div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card class="stat-card">
          <div class="stat-label">本周预订</div>
          <div class="stat-value">{{ stats?.week_bookings ?? '—' }}</div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card class="stat-card">
          <div class="stat-label">活跃会议室数</div>
          <div class="stat-value">{{ stats?.top_rooms.length ?? '—' }}</div>
        </el-card>
      </el-col>
    </el-row>

    <el-card class="mt-20">
      <template #header>使用频次 Top 5 会议室</template>
      <el-table :data="stats?.top_rooms ?? []" stripe>
        <el-table-column label="排名" type="index" width="60" />
        <el-table-column label="会议室" prop="room_name" />
        <el-table-column label="预订次数" prop="count" />
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { getStatsOverview } from '@/api/bookings'

const stats = ref<Awaited<ReturnType<typeof getStatsOverview>> | null>(null)

onMounted(async () => {
  stats.value = await getStatsOverview()
})
</script>

<style scoped>
.page-title { margin-bottom: 20px; }
.stat-row { margin-bottom: 20px; }
.stat-card { text-align: center; }
.stat-label { color: #909399; font-size: 14px; margin-bottom: 8px; }
.stat-value { font-size: 36px; font-weight: bold; color: #303133; }
.mt-20 { margin-top: 20px; }
</style>
