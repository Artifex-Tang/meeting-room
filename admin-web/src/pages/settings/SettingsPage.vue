<template>
  <div>
    <h2 class="page-title">系统参数</h2>

    <el-card v-loading="loading">
      <el-form :model="form" label-width="200px" style="max-width:640px">
        <el-divider content-position="left">预订规则</el-divider>
        <el-form-item label="提前预订最大天数">
          <el-input-number v-model="form.advance_booking_days" :min="1" :max="365" />
        </el-form-item>
        <el-form-item label="单次预订最大时长（分钟）">
          <el-input-number v-model="form.max_booking_hours" :min="30" :max="1440" :step="30" />
        </el-form-item>
        <el-form-item label="周期预订最大月数">
          <el-input-number v-model="form.max_recurrence_months" :min="1" :max="24" />
        </el-form-item>
        <el-form-item label="用户每日最多预订数">
          <el-input-number v-model="form.max_bookings_per_day" :min="1" :max="20" />
        </el-form-item>
        <el-form-item label="取消截止（小时前）">
          <el-input-number v-model="form.cancel_advance_hours" :min="0" :max="72" />
        </el-form-item>

        <el-divider content-position="left">通知配置（T-ADM-08）</el-divider>
        <el-form-item label="预订成功模板ID">
          <el-input v-model="form.tpl_booking_success" placeholder="微信订阅消息模板ID" style="width:100%" />
        </el-form-item>
        <el-form-item label="即将开始模板ID">
          <el-input v-model="form.tpl_booking_upcoming" placeholder="微信订阅消息模板ID" style="width:100%" />
        </el-form-item>
        <el-form-item label="被取消模板ID">
          <el-input v-model="form.tpl_booking_cancelled" placeholder="微信订阅消息模板ID" style="width:100%" />
        </el-form-item>
        <el-form-item label="每人通知配额上限">
          <el-input-number v-model="form.notify_quota_cap" :min="0" :max="100" />
        </el-form-item>
        <el-form-item label="即将开始提前（分钟）">
          <el-input-number v-model="form.notify_upcoming_minutes" :min="1" :max="60" />
        </el-form-item>

        <el-form-item>
          <el-button type="primary" :loading="saving" @click="save">保存</el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { getConfig, updateConfig } from '@/api/config'

const loading = ref(false)
const saving = ref(false)

const form = reactive({
  advance_booking_days: 7,
  max_booking_hours: 480,
  max_recurrence_months: 3,
  max_bookings_per_day: 3,
  cancel_advance_hours: 2,
  tpl_booking_success: '',
  tpl_booking_upcoming: '',
  tpl_booking_cancelled: '',
  notify_quota_cap: 10,
  notify_upcoming_minutes: 15,
})

onMounted(async () => {
  loading.value = true
  try {
    const cfg = await getConfig()
    for (const key of Object.keys(form) as Array<keyof typeof form>) {
      if (key in cfg) {
        const val = cfg[key]
        if (typeof form[key] === 'number') {
          (form as any)[key] = Number(val)
        } else {
          (form as any)[key] = val
        }
      }
    }
  } finally {
    loading.value = false
  }
})

async function save() {
  saving.value = true
  try {
    await updateConfig(form)
    ElMessage.success('保存成功')
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.page-title { margin-bottom: 20px; }
</style>
