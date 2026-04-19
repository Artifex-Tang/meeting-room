<template>
  <div class="profile-wrap">
    <el-card style="max-width:460px">
      <template #header>修改密码</template>

      <el-alert
        v-if="auth.mustChangePassword"
        title="您使用的是初始密码，请先修改后再继续操作。"
        type="warning"
        :closable="false"
        style="margin-bottom:20px"
      />

      <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
        <el-form-item label="原密码" prop="old_password">
          <el-input v-model="form.old_password" type="password" show-password />
        </el-form-item>
        <el-form-item label="新密码" prop="new_password">
          <el-input v-model="form.new_password" type="password" show-password />
        </el-form-item>
        <el-form-item label="确认新密码" prop="confirm">
          <el-input v-model="form.confirm" type="password" show-password />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="saving" @click="submit">修改密码</el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import { changePassword } from '@/api/auth'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()

const formRef = ref<FormInstance>()
const saving = ref(false)
const form = reactive({ old_password: '', new_password: '', confirm: '' })

const rules: FormRules = {
  old_password: [{ required: true, message: '请输入原密码' }],
  new_password: [
    { required: true, message: '请输入新密码' },
    { min: 6, message: '密码至少 6 位' },
  ],
  confirm: [
    { required: true, message: '请再次输入新密码' },
    {
      validator: (_rule, value, callback) => {
        if (value !== form.new_password) callback(new Error('两次密码不一致'))
        else callback()
      },
    },
  ],
}

async function submit() {
  await formRef.value?.validate()
  saving.value = true
  try {
    await changePassword(form.old_password, form.new_password)
    ElMessage.success('密码修改成功，请重新登录')
    auth.logout()
    router.push('/login')
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.profile-wrap { display: flex; justify-content: center; padding-top: 40px; }
</style>
